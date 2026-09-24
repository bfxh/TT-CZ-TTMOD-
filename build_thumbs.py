#!/usr/bin/env python
"""
build_thumbs.py — 给每个 OBJ 渲染一张属于自己的缩略图

问题：原缩略图直接用「贴图文件」当预览，结果是
  · 31,611 个模型只对应 2,942 张不同的图，14,975 个在共用别人的贴图
  · 43% 的模型根本没有贴图 → 回退成图标，整屏一半图一半图标
  · 贴图与原图平均 357 KB，一屏 40 张 ≈ 14 MB

方案：纯 Python / numpy 软件光栅化器，正交等轴测投影 + Lambert 明暗 + z-buffer，
      输出 256×256 透明底 WebP，按「统一分类 kind」上色 —— 缩略图本身携带分类信息。

用法：
  build_thumbs.py --sample 300     # 先渲 300 个看效果与耗时
  build_thumbs.py                  # 全量（可中断，重跑自动跳过已生成）
  build_thumbs.py --workers 12
"""
import argparse
import json
import os
import random
import time
from multiprocessing import Pool

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, '_thumbs')
CATALOG = os.path.join(ROOT, 'catalog_v3.json')

SS = 2                 # 超采样倍数
SIZE = 256             # 输出边长
RS = SIZE * SS         # 实际渲染边长
MAX_FACES = 6000       # 面数上限（缩略图不需要那么细，超出随机采样）
MAX_VERTS = 60000

# 统一分类 → 缩略图颜色（与 design/icons.js 保持一致）
KIND_COLOR = {
    'module': (10, 132, 255), 'weapon': (255, 69, 58), 'mech': (255, 159, 10),
    'mobile': (100, 210, 255), 'struct': (94, 92, 230), 'terrain': (172, 142, 104),
    'foliage': (48, 209, 88), 'prop': (255, 55, 95), 'drone': (99, 230, 226),
    'vfx': (255, 214, 10), 'ui': (142, 142, 147), 'collider': (99, 99, 102),
    'misc': (152, 152, 157),
}
DEFAULT_COLOR = (152, 152, 157)

# 等轴测：yaw -35° / pitch 26°
def _rot():
    y, p = np.deg2rad(-35.0), np.deg2rad(26.0)
    Ry = np.array([[np.cos(y), 0, np.sin(y)], [0, 1, 0], [-np.sin(y), 0, np.cos(y)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(p), -np.sin(p)], [0, np.sin(p), np.cos(p)]])
    return Rx @ Ry
ROT = _rot()
LIGHT = np.array([-0.38, 0.60, 0.71]); LIGHT /= np.linalg.norm(LIGHT)
AMB = 0.34


def parse_obj(path):
    """只读 v / f 行，返回 (verts float32, tris int32)。失败返回 (None, None)。"""
    try:
        with open(path, 'rb') as fh:
            data = fh.read()
    except Exception:  # noqa: BLE001 单个 OBJ 读盘失败不应中断整批渲染
        return None, None
    vs, fs = [], []
    for line in data.split(b'\n'):
        if line[:2] == b'v ':
            t = line[2:].split()
            if len(t) >= 3:
                vs.append((t[0], t[1], t[2]))
        elif line[:2] == b'f ':
            fs.append(line[2:].split())
    if len(vs) < 3 or not fs:
        return None, None
    try:
        v = np.array(vs, dtype=np.float32)
    except Exception:  # noqa: BLE001 顶点文本畸形时放弃该文件，不计入失败原因以外的影响
        return None, None
    if not np.isfinite(v).all():
        return None, None
    idx: list[tuple[int, int, int]] = []
    ap = idx.append
    n = len(v)
    for parts in fs:
        m = len(parts)
        if m < 3:
            continue
        try:
            a = int(parts[0].split(b'/')[0])
            prev = int(parts[1].split(b'/')[0])
        except Exception:  # noqa: BLE001 面索引畸形跳过该面，保留其余可解析面
            continue
        for i in range(2, m):
            try:
                c = int(parts[i].split(b'/')[0])
            except Exception:  # noqa: BLE001 整文件解析兜底：任何异常都归为该文件失败
                break
            if 0 < a <= n and 0 < prev <= n and 0 < c <= n:
                ap((a - 1, prev - 1, c - 1))
            prev = c
    if not idx:
        return None, None
    return v, np.array(idx, dtype=np.int32)


def raster(v, f, color):
    """正交投影 + z-buffer + Lambert，返回 RGBA uint8 (RS,RS,4)。"""
    if len(f) > MAX_FACES:
        f = f[np.random.choice(len(f), MAX_FACES, replace=False)]
    p = v @ ROT.T
    xy, z = p[:, :2], p[:, 2]
    mn, mx = xy.min(0), xy.max(0)
    ext = float(max(mx[0] - mn[0], mx[1] - mn[1]))
    if ext <= 0:
        return None
    sc = (RS * 0.86) / ext
    w = (mx[0] - mn[0]) * sc
    h = (mx[1] - mn[1]) * sc
    px = (xy[:, 0] - mn[0]) * sc + (RS - w) * 0.5
    py = (mx[1] - xy[:, 1]) * sc + (RS - h) * 0.5

    a, b, c = f[:, 0], f[:, 1], f[:, 2]
    x0, y0, z0 = px[a], py[a], z[a]
    x1, y1, z1 = px[b], py[b], z[b]
    x2, y2, z2 = px[c], py[c], z[c]

    # 面法线（旋转后空间），双面取朝向相机
    e1 = p[b] - p[a]
    e2 = p[c] - p[a]
    nrm = np.cross(e1, e2)
    ln = np.linalg.norm(nrm, axis=1)
    ok = ln > 1e-12
    nrm[ok] /= ln[ok, None]
    nrm[nrm[:, 2] < 0] *= -1.0
    shade = AMB + (1 - AMB) * np.clip(nrm @ LIGHT, 0.0, 1.0)

    zbuf = np.full((RS, RS), -np.inf, dtype=np.float32)
    sbuf = np.zeros((RS, RS), dtype=np.float32)
    abuf = np.zeros((RS, RS), dtype=bool)

    den = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    good = np.abs(den) > 1e-9
    order = np.nonzero(good)[0]
    inv = np.where(good, 1.0 / np.where(good, den, 1.0), 0.0)

    for t in order:
        tx0, ty0 = x0[t], y0[t]
        tx1, ty1 = x1[t], y1[t]
        tx2, ty2 = x2[t], y2[t]
        lo_x = max(int(np.floor(min(tx0, tx1, tx2))), 0)
        hi_x = min(int(np.ceil(max(tx0, tx1, tx2))), RS - 1)
        lo_y = max(int(np.floor(min(ty0, ty1, ty2))), 0)
        hi_y = min(int(np.ceil(max(ty0, ty1, ty2))), RS - 1)
        if lo_x > hi_x or lo_y > hi_y:
            continue
        xs = np.arange(lo_x, hi_x + 1, dtype=np.float32) + 0.5
        ys = np.arange(lo_y, hi_y + 1, dtype=np.float32) + 0.5
        dx = xs[:, None] - tx0
        dy = ys[None, :] - ty0
        v0x, v0y = tx1 - tx0, ty1 - ty0
        v1x, v1y = tx2 - tx0, ty2 - ty0
        b1 = (dx * v1y - v1x * dy) * inv[t]
        b2 = (v0x * dy - dx * v0y) * inv[t]
        b0 = 1.0 - b1 - b2
        inside = (b0 >= -1e-6) & (b1 >= -1e-6) & (b2 >= -1e-6)
        if not inside.any():
            continue
        zz = b0 * z0[t] + b1 * z1[t] + b2 * z2[t]
        sub_z = zbuf[lo_x:hi_x + 1, lo_y:hi_y + 1]
        win = inside & (zz > sub_z)
        if not win.any():
            continue
        sub_z[win] = zz[win]
        sbuf[lo_x:hi_x + 1, lo_y:hi_y + 1][win] = shade[t]
        abuf[lo_x:hi_x + 1, lo_y:hi_y + 1] |= win

    if not abuf.any():
        return None
    cr, cg, cb = color
    img = np.zeros((RS, RS, 4), dtype=np.float32)
    img[..., 0] = cr * sbuf
    img[..., 1] = cg * sbuf
    img[..., 2] = cb * sbuf
    img[..., 3] = abuf * 255.0
    return img.astype(np.uint8)


def thumb_path(i):
    return os.path.join(OUT, str(i // 1000), '%d.webp' % i)


def work(task):
    i, rel, kind = task
    dst = thumb_path(i)
    if os.path.exists(dst):
        return 'skip'
    src = os.path.join(ROOT, rel)
    if not os.path.exists(src):
        return 'miss'
    try:
        v, f = parse_obj(src)
        if v is None or len(v) > MAX_VERTS or len(f) == 0:
            return 'empty'
        img = raster(v, f, KIND_COLOR.get(kind, DEFAULT_COLOR))
        if img is None:
            return 'empty'
        im = Image.fromarray(img, 'RGBA')
        if SS > 1:
            im = im.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst, 'WEBP', quality=82, method=4)
        return 'ok'
    except Exception:  # noqa: BLE001 单文件渲染兜底，绝不让一个坏模型拖垮整批
        return 'err'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sample', type=int, default=0)
    ap.add_argument('--workers', type=int, default=os.cpu_count() or 8)
    ap.add_argument('--shuffle', action='store_true')
    a = ap.parse_args()

    with open(CATALOG, encoding='utf-8') as fh:
        data = json.load(fh)
    items = data['items'] if isinstance(data, dict) else data
    tasks = [(it['id'], it['p'], it.get('k')) for it in items if it.get('p')]
    if a.shuffle or a.sample:
        random.seed(7)
        random.shuffle(tasks)
    if a.sample:
        tasks = tasks[:a.sample]

    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    stat: dict[str, int] = {}
    done = 0
    n = len(tasks)
    with Pool(a.workers) as pool:
        for r in pool.imap_unordered(work, tasks, chunksize=16):
            stat[r] = stat.get(r, 0) + 1
            done += 1
            if done % 500 == 0 or done == n:
                el = time.time() - t0
                eta = el / done * (n - done)
                print('  %6d/%d  %.0fs  ETA %.0fs  %s' % (done, n, el, eta, stat), flush=True)
    el = time.time() - t0
    print('完成 %d 个，用时 %.1fs，%.1f ms/个' % (n, el, el / max(n, 1) * 1000))
    print(stat)
    tot = sum(os.path.getsize(os.path.join(d, f))
              for d, _, fs in os.walk(OUT) for f in fs)
    print('输出 %s  共 %.1f MB' % (OUT, tot / 1048576))


if __name__ == '__main__':
    main()
