#!/usr/bin/env python
"""组装「可发布的资产库站点」（本地与 CI 同源）。

为什么单独抽一个脚本：`cd.yml` 里如果直接内联一串 mkdir/cp，本地就复现不了，
只能拿 CI 试错 —— 这个项目从守卫到打包都要求「本地跑什么、CI 就跑什么」。

本地验 CD 产物只要三条命令：

    python tools/build_site.py --out _site
    python serve_v3.py --root _site --port 8801
    python verify_ui.py --page _site/index.html --base http://localhost:8801 \
                        --diag _site/_diag.txt --route

跑完看到的页面与 GitHub Pages 上的完全一致（相对路径都一样）。

范围说明：仓库不承载游戏资产（`models/` 与 `catalog_v3.json` 都不入仓），
所以这个脚本只生产**合成数据**的演示站，页面顶部会自己声明「演示数据」。
本机完整版不要走这里 —— 直接在仓库根目录跑：

    python build_catalog_v3.py && python tools/build_standalone.py
    python serve_v3.py
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 站点要的运行时资源：图标系统 + three.js 三件套（都在仓里，MIT）
RUNTIME_FILES = ['_res/icons.js', '_res/three.min.js', '_res/OBJLoader.js', '_res/OrbitControls.js']


def build(out: Path) -> None:
    if out.exists():
        shutil.rmtree(out)
    (out / '_res').mkdir(parents=True)

    # 1) 页面 + 目录数据；--js-out 把数据直接写进站点自己的 _res/，不去碰本机的真实目录
    #    （默认落点就是本机那份 _res/catalog.js，演示构建一覆盖，双击 index.html 的人
    #     会在毫不知情的情况下看到合成数据）。--assets-dir 顺带把合成 OBJ 与贴图落到
    #    models/demo/ 下，走的是与真实资产完全相同的相对路径，所以 3D 查看器不需要任何
    #    「演示模式」分支。
    subprocess.run(
        [sys.executable, '-X', 'utf8', str(ROOT / 'tools' / 'build_standalone.py'),
         '--demo', '--form', 'both', '--out', str(out / 'index.html'),
         '--assets-dir', str(out), '--js-out', str(out / '_res' / 'catalog.js')],
        cwd=str(ROOT), check=True)

    # 2) 运行时资源 + 许可
    for rel in RUNTIME_FILES:
        src = ROOT / rel
        if not src.is_file():
            sys.exit('缺少运行时资源 %s —— 它应当随仓提供' % rel)
        shutil.copy2(src, out / rel)
    if (ROOT / 'LICENSE').is_file():
        shutil.copy2(ROOT / 'LICENSE', out / 'LICENSE')


def os_rel(p: Path) -> str:
    """尽量给出相对仓库根的短路径，方便把命令直接复制出去用"""
    try:
        return str(p.relative_to(ROOT)).replace('\\', '/')
    except ValueError:
        return str(p)


def main() -> int:
    ap = argparse.ArgumentParser(description='组装可发布的演示站点')
    ap.add_argument('--out', default='_site', help='输出目录（默认 _site/）')
    a = ap.parse_args()
    out = Path(a.out)
    if not out.is_absolute():
        out = ROOT / out

    build(out)

    page = out / 'index.html'
    if not page.is_file():
        sys.exit('组装失败：没有生成 index.html')
    n_obj = len(list((out / 'models').rglob('*.obj')))
    total = sum(f.stat().st_size for f in out.rglob('*') if f.is_file())
    print('站点已就绪：%s' % out)
    print('  index.html %.0f KB · 合成 OBJ %d 个 · 整站 %.1f MB'
          % (page.stat().st_size / 1024, n_obj, total / 1048576))
    print('本地预览：python serve_v3.py --root %s --port 8801' % os_rel(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
