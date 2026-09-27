#!/usr/bin/env python
"""缩略图朝向门：渲染结果的着墨范围必须等于投影范围。

为什么需要这道门：`build_thumbs.raster()` 的帧缓冲轴序曾经写成 `[x][y]`，
而最后是 `Image.fromarray(img)` —— 它按 axis 0 分行。于是缓冲区的 x 被当成了行号，
**每一张缩略图都成了投影的转置**（躺倒 90°、左右也翻）：高瘦的模型渲成扁宽的，
车头朝侧边。这个错极其安静：

  · 单看一张渲染图，只觉得「这个模型怎么怪怪的」，看不出是转置；
  · 三万多张一起看，更看不出 —— 每张都错，就没有参照物；
  · 它不报错、不崩溃、不缺图，任何「有没有图 / 图能不能解码」的判据都抓不到。

所以必须用**不对称网格**把它钉死：造几个宽高比明确不同的盒子，
分别算出「按投影该落在哪些像素」与「实际着墨在哪些像素」，两者必须一致。
对称的模型（立方体、球）转了 90° 也看不出来，正是它们让这个 bug 活了很久。

判据：着墨包围盒 == 投影包围盒，容差 2px（只允许栅格化边缘的半像素差）。
退出码：0 = 通过；1 = 命中；2 = 缺依赖。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOL = 2.0


def boxes(specs):
    """按 [(中心, 尺寸), …] 拼一个多盒网格，返回 (顶点, 三角索引)。

    刻意手写而不是复用 build_standalone.demo_mesh：这道门要验的是**渲染器**，
    测试数据不该来自被验对象的下游生产者。
    """
    verts: list[tuple[float, float, float]] = []
    tris: list[tuple[int, int, int]] = []

    def quad(o, e1, e2):
        b = len(verts)
        verts.extend(tuple(o[k] + e1[k] * t + e2[k] * u for k in range(3))
                     for t in (0, 1) for u in (0, 1))
        tris.extend([(b, b + 1, b + 3), (b, b + 3, b + 2)])

    for (cx, cy, cz), (dx, dy, dz) in specs:
        hx, hy, hz = dx / 2, dy / 2, dz / 2
        quad((cx - hx, cy - hy, cz - hz), (dx, 0, 0), (0, 0, dz))
        quad((cx - hx, cy + hy, cz - hz), (dx, 0, 0), (0, 0, dz))
        quad((cx - hx, cy - hy, cz + hz), (dx, 0, 0), (0, dy, 0))
        quad((cx - hx, cy - hy, cz - hz), (dx, 0, 0), (0, dy, 0))
        quad((cx + hx, cy - hy, cz - hz), (0, 0, dz), (0, dy, 0))
        quad((cx - hx, cy - hy, cz - hz), (0, 0, dz), (0, dy, 0))
    return verts, tris


def projected(v, rot, rs):
    """把顶点投到像素空间，返回 (px, py) —— 与 raster() 内部同一套公式。"""
    import numpy as np
    p = np.asarray(v, dtype=np.float32) @ rot.T
    xy = p[:, :2]
    mn, mx = xy.min(0), xy.max(0)
    ext = float(max(mx[0] - mn[0], mx[1] - mn[1]))
    sc = (rs * 0.86) / ext
    w = (mx[0] - mn[0]) * sc
    h = (mx[1] - mn[1]) * sc
    return (xy[:, 0] - mn[0]) * sc + (rs - w) * 0.5, (mx[1] - xy[:, 1]) * sc + (rs - h) * 0.5


def main() -> int:
    try:
        import numpy as np
        sys.path.insert(0, str(ROOT))
        import build_thumbs as bt
    except ImportError as exc:
        print('ORIENT-GATE SKIP 缺依赖（这张门需要 numpy）：%s' % exc)
        return 2

    # (名称, 盒子规格, 期望的宽高关系)
    cases = [
        ('高瘦 0.5×4×0.5', [((0, 0, 0), (0.5, 4.0, 0.5))], 'tall'),
        ('扁宽 4×0.5×4', [((0, 0, 0), (4.0, 0.5, 4.0))], 'wide'),
        ('立方 2×2×2', [((0, 0, 0), (2.0, 2.0, 2.0))], 'cube'),
        # 偏置柱：只有 +x+z 方向立一根高柱，转置会让它的重心跑到错误的一侧
        ('偏置柱', [((0, 0, 0), (4.0, 0.4, 4.0)), ((1.5, 2.0, 1.5), (0.4, 3.6, 0.4))], 'offset'),
    ]

    fails = []
    for name, specs, kind in cases:
        v, t = boxes(specs)
        img = bt.raster(np.asarray(v, dtype=np.float32), np.asarray(t, dtype=np.int32),
                        bt.KIND_COLOR['module'])
        if img is None:
            fails.append('%s：渲染返回空' % name)
            continue
        ink = img[..., 3] > 0
        iy, ix = np.nonzero(ink)
        px, py = projected(v, bt.ROT, bt.RS)
        got = (float(ix.min()), float(ix.max()), float(iy.min()), float(iy.max()))
        want = (float(px.min()), float(px.max()), float(py.min()), float(py.max()))
        d = max(abs(a - b) for a, b in zip(got, want, strict=True))
        ok = d <= TOL
        iw, ih = ix.max() - ix.min(), iy.max() - iy.min()
        pw, ph = px.max() - px.min(), py.max() - py.min()

        extra = ''
        if kind == 'tall' and not iw < ih:
            ok, extra = False, '（高瘦盒子被渲成扁宽 → 转置）'
        if kind == 'wide' and not iw > ih:
            ok, extra = False, '（扁宽盒子被渲成高瘦 → 转置）'
        if kind == 'offset':
            # 柱子在 +x+z，着墨重心必须偏右（转置后会偏下）
            cx = (ix * ink[iy, ix]).sum() / max(ink.sum(), 1)
            if not float(cx) > bt.RS * 0.5:
                ok, extra = False, '（偏置柱的重心跑到左半边 → 转置）'
        # 立方体不做形状判据：等轴测下它本来就投成 405×439（不是正方形），
        # 而且对称形状转了 90° 也「看着对」—— 它在这里的作用恰恰是反例：
        # 只靠对称形状根本发现不了转置，所以上面那几个不对称用例才是这道门的证据。

        flag = '✓' if ok else '✗'
        print('  %s %-14s 实测 %4d×%-4d 投影 %4.0f×%-4.0f 包围盒最大差 %4.1fpx %s'
              % (flag, name, iw, ih, pw, ph, d, extra))
        if not ok:
            fails.append('%s：着墨包围盒 %s ≠ 投影包围盒 %s%s'
                         % (name, tuple(round(x) for x in got), tuple(round(x) for x in want), extra))

    if fails:
        print('\nORIENT-GATE FAIL  命中 %d 条' % len(fails))
        for f in fails:
            print('   ' + f)
        print('   提示：缓冲区的轴序必须是 [行=y, 列=x]（Image.fromarray 按 axis 0 分行）')
        return 1
    print('\nORIENT-GATE OK  缩略图朝向正确（%d 个不对称用例）' % len(cases))
    return 0


if __name__ == '__main__':
    sys.exit(main())
