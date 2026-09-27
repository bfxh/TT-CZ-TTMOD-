#!/usr/bin/env python
"""把**真实目录数据**打包成「双击即用」的形态。

为什么需要它：`index.html` 用 `fetch('catalog_v3.json')` 取数据，而浏览器在 `file://`
协议下会拦掉 fetch，所以直接双击打不开、必须先起服务。这个脚本把数据改成
`<script>` 能加载的形态 —— 脚本标签不受 file:// 同源限制。

用法：
  python tools/build_standalone.py                 # 出 _res/catalog.js（双击 index.html 即可用）
  python tools/build_standalone.py --form single   # 另出 dist/资产库.html（单文件，可拷走）
  python tools/build_standalone.py --form both

前置：先跑 `python build_catalog_v3.py` 生成 `catalog_v3.json`。

关于「单文件」的边界（踩过，写清楚）：
  `file://` 下相对路径按**文件自身位置**解析。单文件一旦放进 `dist/`，里面的
  `_thumbs/…` 就会解析成 `dist/_thumbs/…`（不存在），三万多张卡片全写「无缩略图」；
  而真实缩略图有 150+ MB，也内联不进去。所以**全量库的双击入口是仓库根目录的
  `index.html`**，单文件只在「拷到别处、只求能打开看条目」时才用。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'catalog_v3.json'
CATALOG_JS = ROOT / '_res' / 'catalog.js'
DIST = ROOT / 'dist'
ICONS = ROOT / '_res' / 'icons.js'
INDEX = ROOT / 'index.html'


def load_items() -> list[dict]:
    if not CATALOG.is_file():
        sys.exit('找不到 %s —— 先跑 build_catalog_v3.py 扫描 models/ 生成它' % CATALOG)
    with open(CATALOG, encoding='utf-8') as fh:
        doc = json.load(fh)
    return doc['items'] if isinstance(doc, dict) else doc


def json_for_html(obj) -> str:
    """把对象序列化成可以安全内联进 `<script>` 的 JSON。

    `json.dumps` 不转义 `<` `>` `&`，于是文件名里只要有一个 `</script>`，
    单文件版的 `<script>` 就会被**提前闭合**，剩下的内容变成标记 —— 既能把页面拼坏，
    也是一条注入路径（目录数据来自磁盘，文件名可以是任意的）。
    `\\u003c` 这类转义在 JSON 与 JS 里都合法，解析结果完全一致。
    """
    out = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    out = out.replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    # 失败即失败：转义漏了就让构建直接报错，不要发布一个能被文件名打穿的单文件
    if any(ch in out for ch in '<>&'):
        raise SystemExit('内联数据里还有裸的 < > &，HTML 安全转义没生效')
    return out


def write_catalog_js(items: list[dict]) -> Path:
    """写成脚本而不是 JSON：file:// 下 fetch 被同源策略拦，script 标签不受限。"""
    CATALOG_JS.parent.mkdir(parents=True, exist_ok=True)
    payload = json_for_html({'items': items})
    header = ('/* 由 tools/build_standalone.py 生成，不要手改；已加入 .gitignore。\n'
              '   作用：让 index.html 在 file://（双击打开）下也能拿到目录数据。 */\n')
    CATALOG_JS.write_text(header + 'window.CATALOG = ' + payload + ';\n', encoding='utf-8')
    return CATALOG_JS


def build_single_file(items: list[dict], out: Path) -> Path:
    """把图标系统与目录数据内联进 HTML，得到一个可以拷到别处双击打开的单文件。

    注意它**不带缩略图**（真实缩略图 150+ MB）—— 拷走后卡片会显示「无缩略图」，
    那是实话。要完整效果就在仓库根目录双击 index.html。
    """
    html = INDEX.read_text(encoding='utf-8')
    icons = ICONS.read_text(encoding='utf-8')

    for tag in ('<script src="_res/icons.js?v=7"></script>',
                '<script src="_res/icons.js"></script>'):
        if tag in html:
            html = html.replace(tag, '<script>\n' + icons + '\n</script>')
            break
    else:
        sys.exit('index.html 里找不到 icons.js 的外链标签，单文件打包中止')

    payload = json_for_html({'items': items})
    marker = 'PAINT_ICONS();'
    if marker not in html:
        sys.exit('index.html 里找不到脚本入口标记，单文件打包中止')
    html = html.replace(marker, 'window.CATALOG = ' + payload + ';\n' + marker, 1)
    html = html.replace('</title>', '</title>\n<!-- 单文件打包产物：图标与目录数据已内联 -->', 1)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    return out


def os_rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT)).replace('\\', '/')
    except ValueError:
        return str(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--form', choices=('js', 'single', 'both'), default='js',
                    help='js=只出 _res/catalog.js（双击 index.html 用）；single=只出单文件；both=都要')
    ap.add_argument('--out', default=str(DIST / '资产库.html'), help='单文件的落点')
    a = ap.parse_args()

    items = load_items()

    if a.form in ('js', 'both'):
        js = write_catalog_js(items)
        print('已写 %s  （%d 个模型，%.1f MB）' % (os_rel(js), len(items),
                                                js.stat().st_size / 1048576))
    if a.form in ('single', 'both'):
        out = build_single_file(items, Path(a.out))
        print('已写 %s  （%.1f MB）' % (os_rel(out), out.stat().st_size / 1048576))

    print('\n双击入口：仓库根目录的 index.html —— 数据走 _res/catalog.js，'
          '缩略图走 _thumbs/，3D 预览走 models/。')
    print('（3D 预览与「在资源管理器中定位」需要本地服务：双击 start_vault.bat）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
