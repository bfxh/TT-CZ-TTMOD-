# 资产库 · 三游戏统一资产浏览器

把三款游戏（TerraTech / War Robots / Iron Saga）导出的 3D 模型堆成一个**可搜、可比、可预览**的本地资产库。
纯静态前端 + 一个零依赖 Python 服务，没有构建步骤，双击 `start_vault.bat` 就能用。

```
31,611 个 OBJ · 17,217 唯一资产 · 14,394 重复副本 · 2.5 GB · 31,396 张离线渲染缩略图
```

## 为什么仓库里没有模型文件

`models/` 里的 OBJ 与贴图是**各游戏厂商的版权内容**（Payload Studios 等），且总量 2.5 GB / 3 万余文件。
本仓只承载**工具链与界面**，不承载资产与派生数据。`.gitignore` 已屏蔽：

| 屏蔽项 | 体积 | 说明 |
|---|---|---|
| `models/` | 2.5 GB | 上游游戏资产，只读输入 |
| `_thumbs/` | 156 MB | `build_thumbs.py` 离屏渲染的缩略图 |
| `catalog_v3.json` | 13 MB | `build_catalog_v3.py` 扫描生成的目录 |
| `_res/catalog.json`、`_res/geom_cache.json` | 11 MB | 旧版目录与几何缓存 |
| `viewer.html` | 7.8 MB | 旧版单文件查看器（已被 `index.html` 取代） |

换句话说：**克隆下来能跑代码，跑之前要自己准备一份资产目录。**

## 快速开始

```bash
# 1) 准备资产（把三款游戏导出的模型放到 models/ 下，目录名按 GAMES 常量来）
#    01_泰拉科技/  02_战争机器人/  03_重装上阵/

# 2) 生成目录（多进程扫描 OBJ，几何信息带缓存，重跑秒过）
python build_catalog_v3.py

# 3) 生成缩略图（纯 numpy 软件光栅化，31,611 个约 3 分钟）
python build_thumbs.py            # 先 --sample 300 看效果

# 4) 起服务（自动找 8800-8899 空闲端口）
python serve_v3.py                # 或双击 start_vault.bat（自动开浏览器）
```

`build_catalog_v3.py` 会合并 `terra_manifest.json` / `warrobots_manifest.json` /
`ironsaga_manifest.json`（若存在）以取得真实资源名与贴图角色；缺这些清单也能跑，
只是重装上阵的模型会退回数字编号名。

## 目录结构

```
index.html              前端全部（单文件，无构建）：符号轨道 + 虚拟滚动 + 停靠详情 + 居中 3D 查看器
_res/icons.js           符号系统单一来源：43 枚自绘 SVG，导出 <symbol> 雪碧
_res/three.min.js       three.js r*（MIT，随仓内置以便离线运行）
_res/OBJLoader.js       three.js 官方扩展（MIT）
_res/OrbitControls.js   three.js 官方扩展（MIT）
serve_v3.py             静态服务：gzip 预压、/open 定位文件、/diag 自检回传
build_catalog_v3.py     扫描 models/ → catalog_v3.json
build_thumbs.py         软件光栅化每个 OBJ → _thumbs/<id//1000>/<id>.webp
verify_ui.py            真实浏览器自检（结构 + 截图 + 版面像素分析）
process_obj.py          旧版 OBJ→JS 转义缓存（保留，新界面不依赖）
tools/                  CI 门禁：路径纪律 / 明文 / 语法
docs/DESIGN.md          设计规范（现行）
docs/archive/           过期设计稿（留痕，非规范）
start_vault.bat         一键启动
```

## 界面用法

| 操作 | 说明 |
|---|---|
| `Ctrl K` | 聚焦搜索（名称 / 资源原名 / 路径） |
| `Ctrl 1` / `Ctrl 2` | 网格 / 列表 |
| 左侧图标 | 全部 / 游戏 / 统一分类 / 分组 / 收藏（点开为筛选面板，带实时计数） |
| 排序条 | 面数 / 顶点 / 贴图 / 大小，点一次降序、再点升序 |
| 点卡片 | 右侧停靠详情（不遮挡列表，可继续对比） |
| 双击卡片 / `Enter` | 居中 3D 查看器（实体·线框·贴图·网格·自动旋转，`←→` 连续翻） |
| 底部 ⧉ | 隐藏 / 显示 14,394 个重复副本 |

视图模式、卡片尺寸、深浅色、收藏都会记在 `localStorage`。

## 数据字典（`catalog_v3.json` 的 `items[]`）

| 字段 | 含义 | 备注 |
|---|---|---|
| `id` | 序号 | 同时是缩略图文件名 `_thumbs/<id//1000>/<id>.webp` |
| `g` `k` `f` | 游戏 / 统一分类 / 分组 | 跨游戏双层分类，解决三套目录体系打架 |
| `c` `n` `rn` `p` | 原始目录 / 文件名 / 资源原名 / 相对路径 | |
| `s` | 文件大小 | **单位是 KB**（`round(size/1024,1)`），不是字节 |
| `v` `fa` | 顶点数 / 三角面数 | |
| `x` `y` `z` | 包围盒三边 | **原始单位，跨游戏不可比**（中位值 TT 2.0 / WR 10.7 / IS 60.0） |
| `tl` `tn` `tr` `tq` | 贴图列表 / 张数 / 角色集 / 关联质量 | `tq`：1=旧清单精确映射，2=文件名前缀推断 |
| `tg` | 标记 | `tex` `low` `hi` `lod` `dup` `col` `empty` `big` |
| `dup` | 重复副本指向的 id | 同游戏 + 同文件名主干，按路径保留第一个 |

> ⚠️ 两个已踩过的坑，改代码前先看这里：
> ① `s` 是 KB。当成字节会让 4 MB 的模型显示成 "4 KB"、总容量显示成 "0.0 GB"。
> ② `x/y/z` 是三款游戏各自的原始单位，**不要**做跨游戏的体积比较或排序。

## 质量门

本地与 CI 跑的是同一套脚本，`.github/workflows/gates.yml` 里逐条对应。

```bash
# 自包含三门（零依赖，只用 stdlib）
python tools/path_check.py       # 路径纪律 P1-P5：软链接 / 文件名卫生 / 单文件 ≤1MB / 越界写
python tools/secret_check.py     # 明文门：凭据模式匹配，输出掩码，不回显明文
python tools/syntax_check.py     # 语法门：Python 编译 + 内联 JS（node --check）+ JSON 解析

# 静态门（ruff 逐规则棘轮 / mypy 默认档零容忍），配置在 ruff.toml 与 mypy.ini
ruff check .                     # 当前 0 命中
mypy --config-file mypy.ini build_catalog_v3.py build_thumbs.py serve_v3.py verify_ui.py process_obj.py

# 界面回归（需要 Edge + 本地服务）
python verify_ui.py
```

`verify_ui.py` 把探针脚本注进页面，页面通过 `POST /diag` 把 DOM 诊断回传落盘，再截三张图
做像素级版面分析。之所以这样绕：无头 Edge 的 `--dump-dom` 在部分环境下不出内容，而截图
路径必须是 Windows 绝对路径、且**必须带 `--no-first-run` 并保留 user-data-dir**，否则会停在首启页出白图。

## 许可

本仓自有代码以 MIT 发布（见 `LICENSE`）。
`_res/three.min.js`、`_res/OBJLoader.js`、`_res/OrbitControls.js` 为 three.js 项目（MIT）的副本，
版权归其作者所有。
`models/` 下的游戏资产**不在本仓范围内**，其版权归各游戏厂商所有。
