#!/usr/bin/env python
"""用 GitHub Git Data API 推送当前 HEAD 的内容（绕过本地 git 的 schannel 吊销检查故障）。

本地 `git push` 报 CRYPT_E_NO_REVOCATION_CHECK，而 `gh` 走 Go 的 TLS 栈一切正常，
所以改走「blob → tree → commit → 更新 ref」四步，TLS 验证保持开启。

用法：python tools/_push_via_api.py --repo bfxh/TT-CZ-TTMOD- --branch main --message-file <path>
"""
from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def gh(*args: str, body: dict | None = None, expect_json: bool = True):
    """调 gh api；对 5xx / 网络抖动做三次退避重试（GitHub 偶发 502）。"""
    last = ""
    for attempt in range(3):
        cmd = ["gh", "api", *args]
        tmp = None
        if body is not None:
            fd, tmp = tempfile.mkstemp(suffix=".json")
            with open(fd, "w", encoding="utf-8") as fh:
                json.dump(body, fh)
            cmd += ["--input", tmp]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace", shell=False, check=False)
        finally:
            if tmp:
                Path(tmp).unlink(missing_ok=True)
        if p.returncode == 0:
            return json.loads(p.stdout) if expect_json and p.stdout.strip() else p.stdout
        last = (p.stderr or p.stdout).strip()
        if "502" in last or "503" in last or "timeout" in last.lower():
            time.sleep(2 + 3 * attempt)
            continue
        break
    raise SystemExit("gh api 失败：%s\n%s" % (" ".join(args[-2:]), last[:400]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--message-file", required=True)
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    msg = Path(a.message_file).read_text(encoding="utf-8")

    files = subprocess.run(["git", "ls-files"], cwd=str(root), capture_output=True,
                           text=True, encoding="utf-8", errors="replace",
                           shell=False, check=True).stdout.split()
    print("待推送文件 %d 个" % len(files))

    ref = gh("/repos/%s/git/ref/heads/%s" % (a.repo, a.branch))
    head_sha = ref["object"]["sha"]
    base_tree = gh("/repos/%s/git/commits/%s" % (a.repo, head_sha))["tree"]["sha"]
    print("远端 HEAD %s  base_tree %s" % (head_sha[:7], base_tree[:7]))

    # 远端已有 blob 的 sha → 本地算同样口径的 sha，只上传真正变化的文件
    remote = {}
    for e in gh("/repos/%s/git/trees/%s?recursive=1" % (a.repo, base_tree)).get("tree", []):
        if e.get("type") == "blob":
            remote[e["path"]] = e["sha"]

    tree = []
    uploaded = 0
    for i, rel in enumerate(files, 1):
        local_sha = subprocess.run(["git", "hash-object", rel], cwd=str(root),
                                   capture_output=True, text=True, encoding="utf-8",
                                   shell=False, check=True).stdout.strip()
        if remote.get(rel) == local_sha:
            tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": local_sha})
            print("  [%2d/%d] %-46s 未变，跳过" % (i, len(files), rel))
            continue
        data = (root / rel).read_bytes()
        blob = gh("-X", "POST", "/repos/%s/git/blobs" % a.repo,
                  body={"content": base64.b64encode(data).decode(), "encoding": "base64"})
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": blob["sha"]})
        uploaded += 1
        print("  [%2d/%d] %-46s %7d B 上传" % (i, len(files), rel, len(data)))
    print("上传 %d 个，复用 %d 个" % (uploaded, len(files) - uploaded))

    new_tree = gh("-X", "POST", "/repos/%s/git/trees" % a.repo,
                  body={"base_tree": base_tree, "tree": tree})["sha"]
    commit = gh("-X", "POST", "/repos/%s/git/commits" % a.repo,
                body={"message": msg, "tree": new_tree, "parents": [head_sha]})["sha"]
    gh("-X", "PATCH", "/repos/%s/git/refs/heads/%s" % (a.repo, a.branch),
       body={"sha": commit, "force": False})
    print("已推送 commit %s → %s/%s" % (commit[:7], a.repo, a.branch))
    print("https://github.com/%s/commit/%s" % (a.repo, commit))
    return 0


if __name__ == "__main__":
    sys.exit(main())
