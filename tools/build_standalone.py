#!/usr/bin/env python
"""把资产目录打包成「双击即用」的两种形态。

为什么需要它：`index.html` 用 `fetch('catalog_v3.json')` 取数据，而浏览器在 `file://`
协议下会拦掉 fetch，所以直接双击打不开、必须先起服务。这个脚本把数据改成
`<script>` 能加载的形态 —— 脚本标签不受 file:// 同源限制。

产出：
  1. `_res/catalog.js`     —— `window.CATALOG = {...}`，index.html 优先读它，读不到再退回 fetch
  2. `dist/资产库.html`     —— 真·单文件：图标系统 + 目录数据全部内联，拷到哪都能双击打开
                              （3D 预览与「打开文件位置」仍需本地服务，页面会给出提示）
  3. `--demo --assets-dir D` —— 合成数据 + 合成 OBJ 落到 D/ 下，给在线演示站用

用法：
  python tools/build_standalone.py                # 两个都生成
  python tools/build_standalone.py --only-js      # 只生成 _res/catalog.js
  python tools/build_standalone.py --demo --assets-dir _site --out _site/index.html
                                                  # CI 用：不含任何资产信息的可跑演示站
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'catalog_v3.json'
CATALOG_JS = ROOT / '_res' / 'catalog.js'
DIST = ROOT / 'dist'
ICONS = ROOT / '_res' / 'icons.js'
INDEX = ROOT / 'index.html'

# 与 index.html 的 KINDS 调色板保持一致：演示缩略图按类型着色，看起来才像一份真目录
KIND_HUE = {
    'module': '#3D7BE0', 'weapon': '#C0503F', 'mech': '#B4791F', 'mobile': '#3E8FA8',
    'struct': '#5A5AA8', 'terrain': '#8A7355', 'foliage': '#3E8A4E', 'prop': '#B04A66',
    'drone': '#3E9A96', 'vfx': '#A08A20', 'ui': '#7A7A82', 'collider': '#6A6A70',
    'misc': '#8E8E96',
}

# 演示缩略图的画布（与 index.html 的 thumbH()=cardW*0.72 同比例，2:1.44）
TW, TH_ = 200, 144
_ISO_C, _ISO_S = math.cos(math.pi / 6), math.sin(math.pi / 6)


def _iso(px: float, py: float, pz: float) -> tuple[float, float]:
    """等轴测投影：+y 朝上。x/z 张成水平面，y 是高度。"""
    return ((px - pz) * _ISO_C, (px + pz) * _ISO_S - py)


def demo_thumb(x: float, y: float, z: float, kind: str) -> str:
    """按包围盒画一个等轴测线框盒，作为演示数据的缩略图（data URI）。

    为什么需要：`_thumbs/` 是 156 MB 的离线渲染产物、不入仓，所以 CI 打出来的
    Pages 站点与单文件产物必然没有缩略图。若什么都不给，演示站上每张卡片都会写
    「无缩略图 · 渲染未产出」—— 那是**错误的结论**（不是渲染失败，是本来就没有），
    会让人误判成页面坏了。这里用包围盒三边现场画一张，比例真实、不需要任何资产。
    """
    hx, hy, hz = x / 2, y / 2, z / 2
    corners = [(sx * hx, sy * hy, sz * hz)
               for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
    pts = [_iso(*c) for c in corners]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    span_x = max(max(xs) - min(xs), 1e-6)
    span_y = max(max(ys) - min(ys), 1e-6)
    pad = 22
    k = min((TW - 2 * pad) / span_x, (TH_ - 2 * pad) / span_y)
    cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

    def P(px: float, py: float, pz: float) -> tuple[float, float]:
        u, v = _iso(px, py, pz)
        return ((u - cx) * k + TW / 2, (v - cy) * k + TH_ / 2)

    def quad(p0, p1, p2, p3, op: float, n: int) -> str:
        """把一个面画成 n×n 的网格片 —— 有几条内部分割线才像「模型线框」而不是一个立方体"""
        corners2 = [P(*p0), P(*p1), P(*p2), P(*p3)]
        out = ['<path d="M%.1f %.1fL%.1f %.1fL%.1f %.1fL%.1f %.1fZ" fill="%s" fill-opacity="%.2f"/>'
               % (corners2[0][0], corners2[0][1], corners2[1][0], corners2[1][1],
                  corners2[2][0], corners2[2][1], corners2[3][0], corners2[3][1],
                  KIND_HUE.get(kind, KIND_HUE['misc']), op)]
        # 双线性插值取内部网格线
        segs = []
        for i in range(1, n):
            t = i / n
            a = tuple(p0[j] + (p1[j] - p0[j]) * t for j in range(3))
            b = tuple(p3[j] + (p2[j] - p3[j]) * t for j in range(3))
            segs.append((P(*a), P(*b)))
            c = tuple(p0[j] + (p3[j] - p0[j]) * t for j in range(3))
            d = tuple(p1[j] + (p2[j] - p1[j]) * t for j in range(3))
            segs.append((P(*c), P(*d)))
        for (ax, ay), (bx, by) in segs:
            out.append('<path d="M%.1f %.1fL%.1f %.1f"/>' % (ax, ay, bx, by))
        return ''.join(out)

    hue = KIND_HUE.get(kind, KIND_HUE['misc'])
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %d" width="%d" height="%d">'
        '<g stroke="%s" stroke-width="1.1" stroke-opacity=".55" fill="none" '
        'stroke-linecap="round" stroke-linejoin="round">'
        % (TW, TH_, TW, TH_, hue)
        + quad((-hx, hy, -hz), (hx, hy, -hz), (hx, hy, hz), (-hx, hy, hz), 0.20, 3)     # 顶面
        + quad((hx, -hy, -hz), (hx, hy, -hz), (hx, hy, hz), (hx, -hy, hz), 0.10, 3)     # 右侧面
        + quad((-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz), 0.15, 3)     # 前侧面
        + '</g></svg>'
    )
    return 'data:image/svg+xml;charset=utf-8,' + urllib.parse.quote(svg, safe='')


def demo_mesh(x: float, y: float, z: float, seg: int) -> tuple[str, int, int]:
    """合成一个小盒体（主体 + 顶面方台），返回 (OBJ 文本, 顶点数, 三角面数)。

    为什么是「合成网格」而不是「干脆不生成模型」：演示站上 3D 查看器是主功能，
    没有可加载的 OBJ 就只剩一个空壳，等于把最关键的一环演示不了。
    这里按包围盒三边现场造一个，并**用真实网格数覆盖 fa / v / s** ——
    卡片上的面数、查看器里的统计、文件大小三者必须与眼前这个网格完全一致，
    不许出现「界面写着 8 万面、实际看到 24 个三角面」这种不一致。
    """
    verts: list[tuple[float, float, float]] = []
    normals: list[tuple[float, float, float]] = []
    faces: list[tuple[int, int, int, int]] = []

    def unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
        m = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2) or 1.0
        return (round(v[0] / m, 4), round(v[1] / m, 4), round(v[2] / m, 4))

    def patch(o, e1, e2, nrm, n: int) -> None:
        """一个矩形面，切成 n×n 片、每片两个三角，朝外法线固定 —— OBJ 没有 vn 时
        MeshStandardMaterial 法线全零会渲染成死黑，所以必须自己写 vn。"""
        normals.append(nrm)
        ni = len(normals)
        for i in range(n):
            for j in range(n):
                t0, t1 = i / n, (i + 1) / n
                u0, u1 = j / n, (j + 1) / n

                def put(t: float, u: float) -> int:
                    verts.append(tuple(o[k] + e1[k] * t + e2[k] * u for k in range(3)))
                    return len(verts)

                a, b = put(t0, u0), put(t1, u0)
                c, d = put(t1, u1), put(t0, u1)
                faces.append((a, b, c, ni))
                faces.append((a, c, d, ni))

    def box(cx: float, cy: float, cz: float, dx: float, dy: float, dz: float, n: int) -> None:
        hx, hy, hz = dx / 2, dy / 2, dz / 2
        patch((cx - hx, cy - hy, cz - hz), (dx, 0, 0), (0, 0, dz), unit((0, -1, 0)), n)
        patch((cx - hx, cy + hy, cz - hz), (dx, 0, 0), (0, 0, dz), unit((0, 1, 0)), n)
        patch((cx - hx, cy - hy, cz + hz), (dx, 0, 0), (0, dy, 0), unit((0, 0, 1)), n)
        patch((cx - hx, cy - hy, cz - hz), (dx, 0, 0), (0, dy, 0), unit((0, 0, -1)), n)
        patch((cx + hx, cy - hy, cz - hz), (0, 0, dz), (0, dy, 0), unit((1, 0, 0)), n)
        patch((cx - hx, cy - hy, cz - hz), (0, 0, dz), (0, dy, 0), unit((-1, 0, 0)), n)

    box(0, 0, 0, x, y, z, seg)
    box(0, y * 0.68, 0, x * 0.52, y * 0.36, z * 0.52, max(1, seg - 2))

    lines = ['# 合成演示模型：由 tools/build_standalone.py 生成，不含任何真实资产数据',
             'o demo']
    lines += ['v %.4f %.4f %.4f' % v for v in verts]
    lines += ['vn %.4f %.4f %.4f' % n for n in normals]
    lines += ['f %d//%d %d//%d %d//%d' % (a, ni, b, ni, c, ni) for a, b, c, ni in faces]
    return '\n'.join(lines) + '\n', len(verts), len(faces)


def _png(w: int, h: int, rows: list[bytes]) -> bytes:
    """够用的最小 PNG 编码器（真彩色、无滤波）。用 stdlib 写，不引 Pillow ——
    这个脚本要在 CI 上零依赖跑，为了几张演示贴图不值得加一条依赖。"""
    import struct
    import zlib

    raw = b''.join(b'\x00' + r for r in rows)

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF))

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
            + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b''))


def demo_texture(kind: str, role: str = 'd') -> bytes:
    """合成一张 64×64 棋盘格贴图。

    为什么贴图也要真造出来：演示站上「点贴图即覆盖」是被明确要求过的功能，
    如果 `tl` 指向一堆 404 的假路径，这条链路上每个按钮都只能用一次「加载失败」来演示自己 ——
    那不叫演示功能，那叫演示报错。棋盘格还有个额外好处：平铺 ×2 / ×4 一眼就能看出来。
    role='n' 造法线贴图色（偏蓝紫），让「漫反射 / 法线」两张缩略图一眼可区分。
    """
    n, px = 8, 8
    base = KIND_HUE.get(kind, KIND_HUE['misc'])
    if role == 'n':
        r, g, b = 128, 138, 250
    else:
        r, g, b = int(base[1:3], 16), int(base[3:5], 16), int(base[5:7], 16)
    light = (r, g, b)
    dark = (int(r * 0.45), int(g * 0.45), int(b * 0.45))
    rows = []
    for y in range(n * px):
        row = bytearray()
        for x in range(n * px):
            c = light if ((x // px) + (y // px)) % 2 == 0 else dark
            # 边框压深一档，平铺时格与格的接缝看得清
            if x % px == 0 or y % px == 0:
                c = (int(c[0] * 0.6), int(c[1] * 0.6), int(c[2] * 0.6))
            row += bytes(c)
        rows.append(bytes(row))
    return _png(n * px, n * px, rows)


def write_demo_assets(items: list[dict], base: Path) -> tuple[int, int]:
    """把合成网格与合成贴图按 items 里的 `p` / `tl` 落到磁盘，路径与真实资产完全一致 ——
    这样 3D 查看器与贴图覆盖都不需要任何「演示模式」分支。"""
    n_obj = n_tex = 0
    for it in items:
        dst = base / it['p']
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(it.pop('_obj'), encoding='utf-8')
        n_obj += 1
        for rel in it.get('tl', []):
            t = base / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(demo_texture(it['k'], 'n' if rel.endswith('_n.png') else 'd'))
            n_tex += 1
    return n_obj, n_tex


def demo_items() -> list[dict]:
    """CI 用的合成数据：结构真实、内容虚构，不含任何游戏资产信息。

    规模刻意做够（3 游戏 × 13 类型 × 若干档），这样 Pages 上的演示站能真的跑出
    虚拟滚动、排序、筛选、标记计数这些交互，而不是十来张卡片晃一圈。
    面数 / 顶点数 / 文件大小 / 缩略图**全部来自真实生成的网格**，不手编数字。
    """
    kinds = ['module', 'weapon', 'mech', 'mobile', 'struct', 'terrain', 'foliage',
             'prop', 'drone', 'vfx', 'ui', 'collider', 'misc']
    games = ['tt', 'wr', 'is']
    out: list[dict] = []
    i = 0
    for gi, g in enumerate(games):
        for ki, k in enumerate(kinds):
            for rep in range(3 if (gi + ki) % 4 else 2):
                # 三款游戏的「原始单位」量级本就不同（TT 2.0 / WR 10.7 / IS 60.0），演示数据照此分化
                unit = (2.0, 10.7, 60.0)[gi] * (1 + rep * 0.35)
                x = round(unit * (0.6 + 0.09 * ki), 2)
                y = round(unit * (0.45 + 0.05 * rep), 2)
                z = round(unit * (0.7 + 0.06 * ki), 2)
                obj, nv, nfa = demo_mesh(x, y, z, 1 + (i * 5) % 7)
                # 标记阈值贴着**真实生成的面数区间**（24 ~ 888）取，不要照搬真实目录的
                # 量级（那里动辄上万面）—— 否则演示站上 low / hi / big 三个标记永远不出现，
                # 「按标记筛选」这条链路就演示不出来。
                tg = ['low'] if nfa < 400 else ['hi']
                if rep == 2:
                    tg.append('lod')
                has_tex = (gi + ki) % 3 == 0
                if has_tex:
                    tg.append('tex')
                if nfa >= 800:
                    tg.append('big')
                # 贴图清单与实际落盘的 PNG 一一对应：tn（张数）必须等于 len(tl)，
                # 否则界面会说「贴图 2 张」却只列出 1 张 —— 数据自相矛盾比缺数据更糟。
                texs = []
                if has_tex:
                    texs.append('models/demo/%s/tex/%s_%02d_d.png' % (g, k, rep + 1))
                    if rep >= 1:
                        texs.append('models/demo/%s/tex/%s_%02d_n.png' % (g, k, rep + 1))
                out.append({
                    'id': i, 'g': g, 'k': k,
                    'f': 'DemoGroup%d' % (ki % 5 + 1), 'c': 'DemoFolder%02d' % (ki + 1),
                    'n': 'demo_%s_%s_%02d' % (g, k, rep + 1),
                    'rn': '演示 · %s %02d' % (k, rep + 1),
                    'p': 'models/demo/%s/demo_%s_%s_%02d.obj' % (g, g, k, rep + 1),
                    's': round(len(obj.encode('utf-8')) / 1024, 1),   # KB，与真实目录同一口径
                    'v': nv, 'fa': nfa,
                    'x': x, 'y': y, 'z': z,
                    'tn': len(texs), 'tl': texs,
                    'tr': (['diffuse'] + (['normal'] if len(texs) > 1 else [])) if has_tex else [],
                    'tq': 2 if has_tex else 0,
                    'tg': tg,
                    'th': demo_thumb(x, y, z, k),
                    '_obj': obj,
                })
                i += 1
    return out


def load_items(use_demo: bool) -> list[dict]:
    if use_demo:
        return demo_items()
    if not CATALOG.is_file():
        sys.exit('找不到 %s —— 先跑 build_catalog_v3.py，或用 --demo 生成合成数据' % CATALOG)
    with open(CATALOG, encoding='utf-8') as fh:
        doc = json.load(fh)
    return doc['items'] if isinstance(doc, dict) else doc


def write_catalog_js(items: list[dict], demo: bool = False) -> Path:
    """写成脚本而不是 JSON：file:// 下 fetch 被同源策略拦，script 标签不受限。"""
    CATALOG_JS.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(_doc(items, demo), ensure_ascii=False, separators=(',', ':'))
    header = ('/* 由 tools/build_standalone.py 生成，不要手改；已加入 .gitignore。\n'
              '   作用：让 index.html 在 file://（双击打开）下也能拿到目录数据。 */\n')
    CATALOG_JS.write_text(header + 'window.CATALOG = ' + payload + ';\n', encoding='utf-8')
    return CATALOG_JS


def _doc(items: list[dict], demo: bool) -> dict:
    """demo 标记会传到前端 → 页面顶部出一条「演示数据」提示条。
    演示数据必须自我声明，否则 CI 产物会被当成真实目录。"""
    doc: dict = {'items': items}
    if demo:
        doc['demo'] = True
    return doc


def build_single_file(items: list[dict], out: Path, demo: bool = False) -> Path:
    """把图标系统与目录数据内联进 HTML，得到一个真正可以双击打开的单文件。"""
    html = INDEX.read_text(encoding='utf-8')
    icons = ICONS.read_text(encoding='utf-8')

    # 1) 图标系统内联，替换掉外链
    for tag in ('<script src="_res/icons.js?v=7"></script>',
                '<script src="_res/icons.js"></script>'):
        if tag in html:
            html = html.replace(tag, '<script>\n' + icons + '\n</script>')
            break
    else:
        sys.exit('index.html 里找不到 icons.js 的外链标签，单文件打包中止')

    # 2) 目录数据内联，插在应用脚本之前
    payload = json.dumps(_doc(items, demo), ensure_ascii=False, separators=(',', ':'))
    marker = 'PAINT_ICONS();'
    if marker not in html:
        sys.exit('index.html 里找不到脚本入口标记，单文件打包中止')
    html = html.replace(marker,
                        'window.CATALOG = ' + payload + ';\n' + marker, 1)

    # 3) 标注这是打包产物
    html = html.replace('</title>', '</title>\n<!-- 单文件打包产物：图标与目录数据已内联，双击即可打开 -->', 1)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding='utf-8')
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--demo', action='store_true', help='用合成数据（CI 用）')
    ap.add_argument('--only-js', action='store_true', help='只生成 _res/catalog.js')
    ap.add_argument('--out', default=str(DIST / '资产库.html'))
    ap.add_argument('--assets-dir', default='',
                    help='把合成 OBJ 落到该目录下（配合 --demo 做在线演示站用）')
    a = ap.parse_args()

    items = load_items(a.demo)

    # 合成 OBJ 只对「起服务的演示站」有意义：单文件版在 file:// 下根本发不出请求，
    # 内联进去除了让文件更大没有任何收益，所以默认丢弃。
    if a.assets_dir and a.demo:
        n_obj, n_tex = write_demo_assets(items, Path(a.assets_dir))
        print('已写 %d 个合成 OBJ + %d 张合成贴图到 %s' % (n_obj, n_tex, a.assets_dir))
    else:
        for it in items:
            it.pop('_obj', None)

    js = write_catalog_js(items, a.demo)
    print('已写 %s  （%d 个模型，%.1f MB）%s' % (js.relative_to(ROOT), len(items),
                                             js.stat().st_size / 1048576,
                                             '  [演示数据]' if a.demo else ''))

    if not a.only_js:
        out = build_single_file(items, Path(a.out), a.demo)
        print('已写 %s  （%.1f MB）' % (out.relative_to(ROOT) if ROOT in out.parents else out,
                                       out.stat().st_size / 1048576))
        print('\n双击这个文件即可打开资产库；3D 预览与「打开文件位置」需要本地服务，')
        print('页面会给出提示，或双击 start_vault.bat 启动服务。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
