#!/usr/bin/env python
"""双击可用性自检：用无头浏览器以 file:// 打开页面截图，确认「双击就能看到东西」。

为什么单独一个脚本：`verify_ui.py` 依赖本地服务（页面要 POST /diag 回传诊断），
而这里要验的恰恰是**没有服务**时的表现 —— 双击 `dist/资产库.html` 或 `index.html`。
没有回传通道，就直接看截图：有没有卡片、有没有报错文案，一眼能看出来。
"""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.parse

EDGE = os.environ.get('VERIFY_BROWSER') or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # 本脚本在 tools/ 下
SHOT = os.path.join(ROOT, '_shots')
TEMP = os.environ.get('TEMP') or r"C:\Windows\Temp"

TARGETS = [
    ('index.html', 'file-index.png'),
    (os.path.join('dist', '资产库.html'), 'file-dist.png'),
]


def warm(prof: str) -> None:
    if os.path.isdir(prof):
        return
    subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
                    '--user-data-dir=' + prof, '--window-size=800,600',
                    '--virtual-time-budget=3000', 'about:blank'],
                   capture_output=True, timeout=180)


def main() -> int:
    os.makedirs(SHOT, exist_ok=True)
    prof = os.path.join(TEMP, '_vh_file')
    warm(prof)
    bad = 0
    for rel, shot in TARGETS:
        page = os.path.join(ROOT, rel)
        if not os.path.isfile(page):
            print('  ✗ %-22s 文件不存在（先跑 tools/build_standalone.py）' % rel)
            bad += 1
            continue
        url = 'file:///' + urllib.parse.quote(page.replace(os.sep, '/'))
        out = os.path.join(SHOT, shot).replace('/', os.sep)
        subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
                        '--disable-extensions', '--hide-scrollbars', '--enable-unsafe-swiftshader',
                        '--user-data-dir=' + prof, '--window-size=1680,1000',
                        '--virtual-time-budget=25000', '--screenshot=' + out, url],
                       capture_output=True, text=True, timeout=300, errors='replace')
        size = os.path.getsize(out) if os.path.exists(out) else 0
        ok = size > 60000          # 出了卡片网格的截图都在 60 KB 以上；失败页是近乎纯色的小图
        print('  %s %-22s 截图 %6.0f KB  %s' % ('✓' if ok else '✗', rel, size / 1024, shot))
        if not ok:
            bad += 1
    print('\n双击可用性：' + ('全部通过' if bad == 0 else '%d 项未过' % bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
