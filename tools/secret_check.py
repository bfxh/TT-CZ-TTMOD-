#!/usr/bin/env python
"""明文门——扫描仓库里混入的凭据，输出一律掩码（不把明文回显进日志/CI 摘要）。

判据对齐 D:\\开发\\unified-rx-mcp 的 secrets 门：命中即红；只报「文件:行 + 类型 + 掩码片段」，
绝不完整回显。已知的示例/占位形态（如 `ghp_xxx`、`AKIAIOSFODNN7EXAMPLE`）默认放行。

用法：python tools/secret_check.py [--root .] [--allow-placeholder]
退出码：0 = 干净；1 = 命中；2 = 用法错。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# (类型, 正则, 严重级别)
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("aws_access_key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "critical"),
    ("github_token", re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{36,255})\b"), "critical"),
    ("github_pat_fine", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b"), "critical"),
    ("slack_token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "critical"),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b"), "critical"),
    ("openai_key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"), "critical"),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"), "critical"),
    ("private_key_block", re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"), "critical"),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"), "high"),
    ("basic_auth_url", re.compile(r"://[^\s/:@]{2,}:[^\s/@]{6,}@"), "high"),
    ("generic_assign", re.compile(
        r"""(?i)\b(api[_-]?key|secret|passwd|password|token|credential)\b\s*[:=]\s*['"]([^'"\s]{16,})['"]"""),
     "high"),
]

# 官方文档/示例里的公开占位值，命中不算违规
PLACEHOLDER = re.compile(
    r"(?i)(EXAMPLE|PLACEHOLDER|DUMMY|FAKE|CHANGEME|YOUR[_-]?KEY|XXX{3,}|<[^>]+>|\*{6,})")

TEXT_EXT = {".py", ".js", ".ts", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg",
            ".md", ".txt", ".html", ".htm", ".bat", ".sh", ".env", ".properties"}
MAX_BYTES = 4 * 1024 * 1024


def mask(s: str) -> str:
    """掩码：保留头 4 尾 2，中间全部打星；长度不足则全星。"""
    s = s.strip()
    if len(s) <= 8:
        return "*" * len(s)
    return s[:4] + "*" * (len(s) - 6) + s[-2:]


def tracked(root: Path) -> list[str]:
    import subprocess
    p = subprocess.run(["git", "ls-files"], cwd=str(root), capture_output=True,
                       text=True, encoding="utf-8", errors="replace", shell=False, check=False)
    if p.stdout.strip():
        return [x for x in p.stdout.splitlines() if x.strip()]
    return [str(f.relative_to(root)).replace("\\", "/") for f in root.rglob("*") if f.is_file()
            and ".git" not in f.parts]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--allow-placeholder", action="store_true", default=True)
    a = ap.parse_args()
    root = Path(a.root).resolve()
    if not root.is_dir():
        print("SECRETS-GATE FAIL: 目录不存在 %s" % root)
        return 2

    hits: list[str] = []
    scanned = 0
    for rel in tracked(root):
        full = root / rel
        if not full.is_file() or full.suffix.lower() not in TEXT_EXT:
            continue
        if full.stat().st_size > MAX_BYTES:
            continue
        scanned += 1
        text = full.read_text(encoding="utf-8", errors="replace")
        for n, line in enumerate(text.splitlines(), 1):
            for name, pat, level in PATTERNS:
                m = pat.search(line)
                if not m:
                    continue
                frag = m.group(m.lastindex or 0) if m.groups() else m.group(0)
                if a.allow_placeholder and PLACEHOLDER.search(frag):
                    continue
                hits.append("%s  %s:%d  %s" % (level.upper(), rel, n, name + " " + mask(frag)))

    if hits:
        print("SECRETS-GATE FAIL  root=%s  命中 %d 条（掩码输出）" % (root, len(hits)))
        for h in hits:
            print("   " + h)
        return 1
    print("SECRETS-GATE OK  root=%s  扫描文本文件 %d 个，无凭据命中" % (root, scanned))
    return 0


if __name__ == "__main__":
    sys.exit(main())
