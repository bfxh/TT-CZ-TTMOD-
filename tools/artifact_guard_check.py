#!/usr/bin/env python
"""产物安全门：内联目录数据必须对 HTML 安全，坏文件名不许打穿单文件。

为什么单独成门：目录数据来自磁盘上的文件名，可以是任意的。`json.dumps` **不转义**
`<` `>` `&`，所以一个叫 `</script>` 的文件名会让单文件版的 `<script>` 提前闭合，
后面的内容变成标记 —— 页面被拼坏，同时也是注入路径。这个错在正常资产上永远不出现，
只有遇到「名字里带尖括号」的文件才暴露，所以必须用构造出来的恶意数据当判据。

判据：
  1. `write_catalog_js()` 的产物里不含裸 `<` `>` `&`
  2. `build_single_file()` 的产物里，恶意文件名只以 `\\u003c` 形式存在，
     且 `<script>` 标签数量与原始 index.html 一致（没有多出来的标签）
  3. 解析回来内容不失真（转义只影响写法，不影响数据）

退出码：0 = 通过；1 = 命中；2 = 环境错。
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOSTILE = {
    'f': '</script><img src=x onerror=alert(1)>',
    'n': '<b>n</b>',
    'rn': '&amp;<svg onload=alert(2)>',
    'c': 'c"><script>',
    'p': 'models/x" onmouseover="alert(3).obj',
}


def load_builder():
    spec = importlib.util.spec_from_file_location('build_standalone',
                                                  ROOT / 'tools' / 'build_standalone.py')
    if spec is None or spec.loader is None:
        raise ImportError('无法加载 tools/build_standalone.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def item(i: int) -> dict:
    base = {'id': i, 'g': 'tt', 'k': 'misc', 's': 1.0, 'v': 3, 'fa': 1,
            'x': 1, 'y': 1, 'z': 1, 'tn': 0, 'tl': [], 'tr': [], 'tq': 0, 'tg': []}
    base.update({k: '%s-%d' % (v, i) for k, v in HOSTILE.items()})
    return base


def main() -> int:
    try:
        mod = load_builder()
        index_src = (ROOT / 'index.html').read_text(encoding='utf-8')
    except Exception as exc:  # noqa: BLE001 环境问题与判据问题要分开报
        print('ARTIFACT-GUARD FAIL 环境错：%s' % exc)
        return 2

    items = [item(1), item(2)]
    tmp = Path(tempfile.mkdtemp(prefix='artifact-guard-'))
    fails: list[str] = []
    try:
        # 1) catalog.js
        mod.CATALOG_JS = tmp / 'catalog.js'
        js = mod.write_catalog_js(items).read_text(encoding='utf-8')
        raw = [c for c in '<>&' if c in js]
        ok1 = not raw
        print('  %s catalog.js 无裸尖括号/&（发现：%s）' % ('✓' if ok1 else '✗',
                                                          ''.join(raw) or '无'))
        if not ok1:
            fails.append('catalog.js 里还有裸的 %s' % ''.join(raw))

        # 2) 单文件
        out = tmp / 'single.html'
        html = mod.build_single_file(items, out).read_text(encoding='utf-8')
        body = html.split('window.CATALOG = ', 1)[1].split(';\n', 1)[0]
        ok2 = '</script>' not in body and '<img' not in body and 'onerror' in body
        n_src = index_src.count('<script')
        n_out = html.count('<script')
        ok3 = n_out == n_src
        print('  %s 单文件内联数据不含可闭合的 </script>（长 %d 字符）' % ('✓' if ok2 else '✗',
                                                                    len(body)))
        print('  %s <script> 标签数不变：原 %d → 产物 %d' % ('✓' if ok3 else '✗', n_src, n_out))
        if not ok2:
            fails.append('单文件内联数据里出现了可闭合的 </script>')
        if not ok3:
            fails.append('单文件标签数变了：%d → %d' % (n_src, n_out))

        # 3) 转义只改写法，不改数据
        parsed = json.loads(body)
        ok4 = parsed['items'][0]['f'] == HOSTILE['f'] + '-1'
        print('  %s 转义后解析回来的数据与原值一致' % ('✓' if ok4 else '✗'))
        if not ok4:
            fails.append('转义改变了数据内容：%r' % parsed['items'][0]['f'])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if fails:
        print('\nARTIFACT-GUARD FAIL  命中 %d 条' % len(fails))
        for x in fails:
            print('   ' + x)
        print('   提示：内联 JSON 必须把 < > & 转成 \\u003c \\u003e \\u0026。')
        return 1
    print('\nARTIFACT-GUARD OK  内联数据 HTML 安全（4 条判据）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
