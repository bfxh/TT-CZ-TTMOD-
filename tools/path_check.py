#!/usr/bin/env python
"""路径纪律门（P1-P5）——判据对齐 D:\\开发\\unified-rx-mcp scripts/path_gate.py。

为什么需要它：本项目的构建脚本会在大量目录上读写文件，路径是最容易出逃逸面的一环
（软链接指到仓库外、`..` 拼接写到仓外、大二进制混入、文件名带设备名或控制字符）。
这些既不会被动明门抓（不是凭据），也不会被测试抓（测试不查仓库卫生）。

判据（命中即红）：
  P1 无符号链接（git mode 120000）；
  P2 文件名卫生：不得含 `..` / 绝对路径形态 / Windows 设备名（CON/PRN/AUX/NUL/COM1-9/LPT1-9）
     / 结尾空格或点 / 控制字符；
  P3 单文件 ≤ 1 MiB（大二进制/数据混入仓库的典型信号）；
  P4 源码里不得出现「`..` 与写文件原语同现」的越界写路径（启发式）；
  P5 工作树里不得有指向仓库外的软链接（realpath 逃逸）。

用法：python tools/path_check.py [--root .] [--max-kb 1024]
退出码：0 = 通过；1 = 命中；2 = 用法错。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEVICE = re.compile(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", re.IGNORECASE)
CTRL = re.compile(r"[\x00-\x1f\x7f]")
# P4：一行里同时出现 `..` 字面量与写/拷贝原语 ⇒ 可疑越界写
DANGEROUS = re.compile(r"""(["']\.\.["']|\.\./|\.\.\\)""")
WRITE_PRIM = re.compile(r"(open\(|write_text\(|write_bytes\(|os\.path\.join|shutil\.copy|Path\()")
SRC_EXT = (".py", ".sh", ".rs", ".yml", ".yaml", ".toml", ".bat")


def git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", *args], cwd=str(root), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", shell=False, check=False)
    return p.stdout


def tracked(root: Path) -> list[str]:
    """优先用 git 索引（只查将入仓的文件）；不是 git 仓时退化为遍历。"""
    out = git(root, "ls-files")
    if out.strip():
        return [x for x in out.splitlines() if x.strip()]
    skip = {".git", "__pycache__", ".ruff_cache", ".mypy_cache", "node_modules"}
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        files.extend(Path(dirpath, fn).relative_to(root).as_posix() for fn in filenames)
    return files


def check_p1p2p3(root: Path, files: list[str], max_bytes: int) -> list[str]:
    fails: list[str] = []
    # P1 符号链接（git 索引里 mode=120000）
    fails.extend("P1 符号链接入仓: %s" % line.split("\t")[-1]
                 for line in git(root, "ls-files", "-s").splitlines()
                 if line.startswith("120000"))
    for rel in files:
        name = rel.replace("\\", "/").split("/")[-1]
        # P2 文件名卫生
        if ".." in rel.replace("\\", "/").split("/")[:-1] or ".." in name:
            fails.append("P2 路径含 `..`: %s" % rel)
        if Path(rel).is_absolute() or re.match(r"^[A-Za-z]:", rel):
            fails.append("P2 绝对路径形态: %s" % rel)
        if DEVICE.match(name):
            fails.append("P2 Windows 设备名: %s" % rel)
        if name != name.rstrip(" ."):
            fails.append("P2 结尾空格或点: %r" % rel)
        if CTRL.search(rel):
            fails.append("P2 控制字符: %r" % rel)
        # P3 体积
        full = root / rel
        if full.is_file():
            size = full.stat().st_size
            if size > max_bytes:
                fails.append("P3 文件 %.1f MB > %d KB: %s" % (size / 1048576, max_bytes // 1024, rel))
    return fails


def check_p4(root: Path, files: list[str]) -> list[str]:
    fails: list[str] = []
    for rel in files:
        if not rel.lower().endswith(SRC_EXT):
            continue
        full = root / rel
        if not full.is_file():
            continue
        text = full.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if DANGEROUS.search(line) and WRITE_PRIM.search(line):
                fails.append("P4 可疑越界写 (%s:%d): %s" % (rel, n, line.strip()[:90]))
    return fails


def check_p5(root: Path) -> list[str]:
    fails: list[str] = []
    real_root = root.resolve()
    for dirpath, dirnames, _ in os.walk(root):
        for d in list(dirnames):
            p = Path(dirpath, d)
            if p.is_symlink():
                try:
                    target = p.resolve()
                except OSError:  # 断链软链接本身就是问题，按逃逸报
                    fails.append("P5 断链软链接: %s" % p)
                    continue
                if not str(target).startswith(str(real_root)):
                    fails.append("P5 软链接逃逸仓库: %s -> %s" % (p, target))
                dirnames.remove(d)
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--max-kb", type=int, default=1024)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        print("PATH-GATE FAIL: 目录不存在 %s" % root)
        return 2

    files = tracked(root)
    fails = check_p1p2p3(root, files, a.max_kb * 1024) + check_p4(root, files) + check_p5(root)
    if fails:
        print("PATH-GATE FAIL  root=%s  命中 %d 条" % (root, len(fails)))
        for f in fails[:40]:
            print("   " + f)
        if len(fails) > 40:
            print("   …另有 %d 条" % (len(fails) - 40))
        return 1
    print("PATH-GATE OK  root=%s  文件 %d 个，P1-P5 全过" % (root, len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
