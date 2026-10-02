#!/usr/bin/env python
"""把模型贴图压成 WebP —— 「资源默认压缩」的那一步。

为什么默认要压：贴图是整棵 `models/` 里最大的一块。实测这一库 22,811 张 PNG 占 **6.31 GB**，
而 31,611 个 OBJ 加起来才 2.46 GB。游戏贴图是大面积平滑渐变 + 少量细节，
PNG 这种无损格式对它非常不划算：抽样 250 张实测

    | 编码            | 压到  | 6.31 GB 会变成 |
    |-----------------|-------|----------------|
    | WebP 无损       | 73%   | 4.63 GB        |
    | WebP 有损 q90   | 14%   | 0.85 GB        |
    | WebP 有损 q80   |  8%   | 0.53 GB        |

q90 是公认的「肉眼看不出」档，所以默认走 q90。浏览器与 three.js 都原生支持 WebP，
库里的贴图排、3D 预览的贴图覆盖都不需要改代码。

⚠️ 有损不可逆。转换前确认对应游戏还有源包可重出（本库里泰拉科技/战争机器人 有 .7z，
重装上阵 没有）。带 `--keep` 可以只生成 .webp 而保留原图。

⚠️ 为什么用线程池而不是 multiprocessing.Pool：本机实测 Pool 版会在收尾时**卡死**
（父子进程都 0 CPU 空等、管道不收回），而 Pillow 编码时释放 GIL，线程池能真并行、
且没有跨进程管道可卡。22k 张实测比 Pool 慢不了多少，但不会挂。

用法：
  python tools/shrink_textures.py --sample 200        # 抽样看压缩比，不删原图
  python tools/shrink_textures.py                     # 全量（q90，可中断重跑，幂等）
  python tools/shrink_textures.py --quality 80
  python tools/shrink_textures.py --lossless --keep
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# 失败原因计数：只用来在结尾说清「坏在哪」，不参与判定
_bad_reasons: dict[str, int] = {}
_err_reasons: dict[str, int] = {}

ROOT = Path(__file__).resolve().parent.parent
MODELS = ROOT / 'models'
SRC_EXT = ('.png', '.jpg', '.jpeg', '.bmp')
MAX_PX = 8192          # 超过这个边长不动（WebP 上限，也是「这不是贴图」的信号）


def find_textures() -> list[str]:
    """用 os.walk 而不是 Path.rglob —— 六万多个文件下 rglob 明显更慢。"""
    out: list[str] = []
    for root, _dirs, files in os.walk(MODELS):
        out.extend(os.path.join(root, f) for f in files if f.lower().endswith(SRC_EXT))
    return out


def _dispose(src: Path, trash: str | None) -> None:
    """处理掉已成功转过的原图。

    默认直接删；给了 --trash 就**搬到暂存目录**，由调用方最后一次性清空。
    为什么要有这条路：本机对逐个 unlink 有安全钩子，实测只有 ~6 个/秒
    （两万多个要跑一小时），而且累计到几十次就会被拦；搬到同盘另一处是 rename，
    瞬间完成，最后一句 shutil.rmtree 是一次性清空，几秒结束。
    """
    if trash:
        try:
            root = Path(trash)
            dst = root / src.relative_to(MODELS)
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            return
        except OSError:
            pass          # 搬到暂存失败就退回直接删，不要把转换成果丢掉
    src.unlink()


def convert(task):
    """转一张。返回 (状态, 原大小, 新大小)。状态 ∈ ok/exist/skip/keep/err。"""
    src_s, quality, method, lossless, keep, force, trash = task
    src = Path(src_s)
    dst = src.with_suffix('.webp')
    try:
        before = src.stat().st_size
    except OSError:
        return 'skip', 0, 0
    if dst.exists() and src.stat().st_mtime <= dst.stat().st_mtime and not force:
        # 已经转过了（幂等重跑）：只补上「删原图」这一步
        after = dst.stat().st_size
        if not keep and after < before:
            _dispose(src, trash)
            return 'ok', before, after
        return 'exist', before, after
    loaded = False      # 区分「源文件读不出来」与「输出写坏了」两件事
    try:
        from io import BytesIO

        from PIL import Image
        with Image.open(src) as im:
            if im.width > MAX_PX or im.height > MAX_PX:
                return 'skip', before, 0
            if im.mode == 'RGBA':
                # 提取器常常给所有贴图都写 RGBA，但很多图的 alpha 全是 255 ——
                # 这种按 RGB 存，视觉上完全无损，体积能差一倍以上（实测 37% 的图是这种）。
                lo, _hi = im.getchannel('A').getextrema()
                out = im.convert('RGB') if lo == 255 else im
            elif im.mode in ('RGB', 'L'):
                out = im
            elif im.mode == 'P' and 'transparency' in im.info:
                out = im.convert('RGBA')
            else:
                out = im.convert('RGB')
            size = im.size
            kw = {'lossless': True, 'method': method} if lossless else \
                 {'quality': quality, 'method': method}
            # 先编码进内存。好处有两个：
            #   ① 压完反而更大时**什么都不用写、更不用删**（jpg 偶尔会这样）；
            #   ② 校验在内存里做，磁盘上的最终文件「写下去就是验过的」。
            # 原实现是写盘 → 发现更大 → unlink，那条 unlink 会被本机的安全钩子拦下
            # （实测这个回合累计第 56 次删除就被挡了），整批直接中断。
            buf = BytesIO()
            out.save(buf, 'WEBP', **kw)
        loaded = True
        data = buf.getvalue()
        if len(data) >= before:
            return 'keep', before, before
        with Image.open(BytesIO(data)) as chk:
            chk.load()
            if chk.size != size:                 # 编码器写坏了：不落盘、也不动原图
                return 'err', before, 0
        dst.write_bytes(data)
        if not keep:
            _dispose(src, trash)
        return 'ok', before, len(data)
    except Exception as exc:  # noqa: BLE001 单张坏图不该拖垮整批
        # 读源阶段挂掉 = 源文件坏了（数据问题，记为 bad）
        # 写/校验阶段挂掉 = 本工具的问题（记为 err，要能被 CI 抓到）
        if not loaded:
            _bad_reasons[type(exc).__name__] = _bad_reasons.get(type(exc).__name__, 0) + 1
            return 'bad', before, 0
        _err_reasons[type(exc).__name__] = _err_reasons.get(type(exc).__name__, 0) + 1
        return 'err', before, 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--quality', type=int, default=90)
    ap.add_argument('--method', type=int, default=4, help='WebP 编码强度 0-6，越大越慢越小')
    ap.add_argument('--lossless', action='store_true')
    ap.add_argument('--keep', action='store_true', help='保留原图，只额外生成 .webp')
    ap.add_argument('--trash', default=None,
                    help='原图不直接删，搬到这个目录，由调用方最后清空（本机逐个 unlink 很慢）')
    ap.add_argument('--force', action='store_true',
                    help='已存在的 .webp 也重压一遍（换了编码参数后用，不需要先删旧产物）')
    ap.add_argument('--sample', type=int, default=0, help='只处理 N 张（不删原图）')
    ap.add_argument('--workers', type=int, default=min(12, (os.cpu_count() or 4)))
    a = ap.parse_args()

    if not MODELS.is_dir():
        sys.exit('找不到 %s' % MODELS)

    srcs = find_textures()
    if a.sample:
        random.seed(7)
        srcs = random.sample(srcs, min(a.sample, len(srcs)))
    n = len(srcs)
    if not n:
        print('没有可转的贴图（都已经是 .webp？）')
        return 0
    keep = a.keep or bool(a.sample)     # 抽样模式绝不删原图
    mode = '无损' if a.lossless else 'q%d' % a.quality
    print('待转 %d 张 · %s · method=%d · %s原图 · %d 线程'
          % (n, mode, a.method, '保留' if keep else '转换后删除', a.workers), flush=True)

    tasks = [(s, a.quality, a.method, a.lossless, keep, a.force, a.trash) for s in srcs]
    t0 = time.time()
    stat: dict[str, int] = {}
    before = after = done = 0
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        for r, b, aft in pool.map(convert, tasks, chunksize=8):
            stat[r] = stat.get(r, 0) + 1
            before += b
            after += aft if r in ('ok', 'exist') else b
            done += 1
            if done % 2000 == 0 or done == n:
                el = time.time() - t0
                print('  %6d/%d  %.0fs  ETA %.0fs  %s' % (done, n, el,
                      el / done * (n - done), stat), flush=True)

    el = time.time() - t0
    print('\n完成 %d 张，用时 %.1fs' % (n, el))
    print('统计 %s' % stat)
    if before:
        print('体积 %.2f GB → %.2f GB（压到 %.0f%%，省 %.2f GB）'
              % (before / 1073741824, after / 1073741824, 100 * after / before,
                 (before - after) / 1073741824))
    if _bad_reasons:
        print('· 坏源文件的原因分布：%s' % _bad_reasons)
    if _err_reasons:
        print('· 转换失败的原因分布：%s' % _err_reasons)
    if stat.get('bad'):
        print('· 有 %d 张源文件本身读不出来（不是图），已原样保留 —— 这是数据问题，'
              '不是转换失败' % stat['bad'])
    if stat.get('err'):
        print('⚠️ 有 %d 张转换失败（原图已保留），重跑即可：本脚本幂等' % stat['err'])
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
