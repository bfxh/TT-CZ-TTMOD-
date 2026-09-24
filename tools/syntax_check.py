#!/usr/bin/env python
"""语法门——三类产物一次校验，能力缺席如实上报（不静默通过）。

  · Python：`compile()` 全量编译（等价 py_compile，但不落 __pycache__）
  · HTML  ：抽出每段内联 <script> 交给 `node --check`；node 不在则记 skipped
  · JS     ：_res/*.js 直接交给 node --check
  · JSON   ：catalog 之类的数据文件按 UTF-8 解析

用法：python tools/syntax_check.py [--root .]
退出码：0 = 全过（含 skipped 项如实列出）；1 = 有真错误；2 = 用法错。
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_RE = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL | re.IGNORECASE)
SKIP_DIRS = {".git", "__pycache__", ".ruff_cache", ".mypy_cache", "node_modules",
             "models", "_thumbs", "_shots"}


def walk(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in suffixes:
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        out.append(p)
    return sorted(out)


def compile_one(f: Path) -> str | None:
    """编译单个文件，返回错误描述或 None（抽成函数，避免在循环里写 try）"""
    try:
        compile(f.read_text(encoding="utf-8", errors="replace"), str(f), "exec")
    except SyntaxError as e:
        return "%s:%s %s" % (f, e.lineno, e.msg)
    return None


def check_python(files: list[Path]) -> tuple[list[str], int]:
    fails = [msg for f in files if (msg := compile_one(f))]
    return fails, len(files)


def check_js_via_node(pairs: list[tuple[str, str]], node: str | None) -> tuple[list[str], int, int]:
    """pairs = [(显示名, 源码)]；返回 (失败, 检查数, 跳过的脚本段数)"""
    if not node:
        return [], 0, sum(1 for _, src in pairs if src.strip())
    fails: list[str] = []
    checked = 0
    for label, src in pairs:
        if not src.strip():
            continue
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False,
                                         encoding="utf-8", newline="\n") as fh:
            fh.write(src)
            tmp = fh.name
        try:
            p = subprocess.run([node, "--check", tmp], capture_output=True,
                               text=True, encoding="utf-8", errors="replace",
                               shell=False, check=False)
            if p.returncode != 0:
                first = (p.stderr or "").strip().splitlines()[:3]
                fails.append("%s → %s" % (label, " / ".join(first)))
            else:
                checked += 1
        finally:
            Path(tmp).unlink(missing_ok=True)
    return fails, checked, 0


def parse_one(f: Path) -> str | None:
    try:
        json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return "%s → %s" % (f, e)
    return None


def check_json(files: list[Path]) -> tuple[list[str], int]:
    fails = [msg for f in files if (msg := parse_one(f))]
    return fails, len(files) - len(fails)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        print("SYNTAX-GATE FAIL: 目录不存在 %s" % root)
        return 2

    node = shutil.which("node")
    py_files = walk(root, (".py",))
    js_files = walk(root, (".js",))
    html_files = walk(root, (".html", ".htm"))
    json_files = walk(root, (".json",))

    py_fail, py_n = check_python(py_files)

    js_pairs = [(str(f.relative_to(root)), f.read_text(encoding="utf-8", errors="replace"))
                for f in js_files]
    for h in html_files:
        text = h.read_text(encoding="utf-8", errors="replace")
        for i, m in enumerate(SCRIPT_RE.findall(text)):
            js_pairs.append(("%s <inline script #%d>" % (h.relative_to(root), i + 1), m))
    js_fail, js_n, js_skipped = check_js_via_node(js_pairs, node)

    json_fail, json_n = check_json(json_files)
    fails = py_fail + js_fail + json_fail

    if fails:
        print("SYNTAX-GATE FAIL  root=%s  错误 %d 条" % (root, len(fails)))
        for f in fails[:40]:
            print("   " + f)
        return 1

    print("SYNTAX-GATE OK  root=%s" % root)
    print("   Python 编译 %d 个 · JS/内联脚本 %d 段 · JSON %d 个" % (py_n, js_n, json_n))
    if js_skipped:
        print("   skipped: node 不在 PATH，%d 段 JS 未做语法校验（能力缺席如实上报）" % js_skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
