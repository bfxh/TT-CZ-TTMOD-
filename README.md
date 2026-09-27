# 资产库 · 三游戏统一资产浏览器

把三款游戏（TerraTech / War Robots / Iron Saga）导出的 3D 模型堆成一个**可搜、可比、可预览**的本地资产库。
纯静态前端 + 一个零依赖 Python 服务，没有构建步骤。

```
31,611 个 OBJ · 17,217 唯一资产 · 14,394 重复副本 · 2.5 GB · 31,396 张离线渲染缩略图
```

## 开箱即用

按「用户要动几下手」从少到多排：

| 方式 | 要做什么 | 得到什么 |
|---|---|---|
| **在线看**（最少） | 点开 GitHub Pages 链接 | 完整界面 + 3D 预览，跑的是**合成数据**（页面顶部有提示条） |
| **单文件** | 下载 `dist/资产库.html`，双击 | 完整界面，数据已内联；3D 预览与「定位文件」需要本地服务 |
| **本地目录** | `python tools/build_standalone.py --only-js` 后双击 `index.html` | 完整界面 + 真实目录；缩略图要另跑 `build_thumbs.py` |
| **本地全量** | 双击 `start_vault.bat` | 全部功能（3D、贴图覆盖、在资源管理器中定位） |

不需要「先读文档找到入口，再进到某个子目录下找那个文件」——`dist/资产库.html` 是单个 HTML，
`index.html` 就在仓库根目录，两个都能直接双击。

> 为什么双击也能读数据：浏览器在 `file://` 下会拦掉 `fetch()`，但**脚本标签不受同源限制**。
> 所以 `tools/build_standalone.py` 把目录数据写成 `_res/catalog.js`（`window.CATALOG = {...}`），
> `index.html` 优先读它、读不到再退回 `fetch('catalog_v3.json')`、都没有就给出可执行的下一步。

## 为什么仓库里没有模型文件

`models/` 里的 OBJ 与贴图是**各游戏厂商的版权内容**（Payload Studios 等），且总量 2.5 GB / 3 万余文件。
本仓只承载**工具链与界面**，不承载资产与派生数据。`.gitignore` 已屏蔽：

| 屏蔽项 | 体积 | 说明 |
|---|---|---|
| `models/` | 2.5 GB | 上游游戏资产，只读输入 |
| `_thumbs/` | 156 MB | `build_thumbs.py` 离屏渲染的缩略图 |
| `catalog_v3.json` | 13 MB | `build_catalog_v3.py` 扫描生成的目录 |
| `_res/catalog.js` | 13 MB | 同一份目录的「双击可读」写法，`build_standalone.py` 生成 |
| `_res/catalog.json`、`_res/geom_cache.json` | 11 MB | 旧版目录与几何缓存 |
| `dist/`、`_site/` | — | 打包产物（单文件 / 发布站点），由脚本生成 |
| `viewer.html` | 7.8 MB | 旧版单文件查看器（已被 `index.html` 取代） |

换句话说：**克隆下来能跑代码，跑之前要自己准备一份资产目录**；不想准备就点 Pages 上的演示站。

## 快速开始（本地全量）

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

## 设计理念：信息对象 → UI 组件 → 命令 → 能力

一条链路，贯穿整个界面：

```
信息对象          UI 组件                点击事件         命令/动作        系统或网络能力
资产条目(it)  →  图标/卡片/chip  →  data-act="…"  →  ACTIONS[cmd]  →  筛选 · 定位文件 · 下载 · 覆盖贴图 · 剪贴板
```

组件只写 `data-act="命令:参数"`，由**一处** `document` 级监听统一派发到 `ACTIONS` 表：

```html
<button class="chip act" data-act="filter:kind=weapon">武器</button>
<button class="cbtn act" data-act="path:models%2F...%2Fx.obj">复制路径</button>
<button class="cbtn act local" data-act="reveal:models%2F...%2Fx.obj">在资源管理器中定位</button>
```

好处不是「少写几行事件绑定」，而是**可审计**：页面上每一个可点组件的命令名，
都能在 `ACTIONS` 里找到对应函数；找不到就是坏的（点击静默无反应是最难查的一类 bug）。
`verify_ui.py --route` 把这件事当成一条硬判据来跑。

### 但不要给每个字段都做成按钮

判据是：这个信息上是否存在一个「用户真的会想做的事」，而且**这件事在别处没有入口**。

- ✅ 分类 chip → 筛选；标记 chip → 筛选；贴图缩略图 → 覆盖材质；同名族 → 跳到同族下一个
- ✅ 「完整路径」→ 复制路径（路径是唯一真的会想拿出去用的值）
- ❌ 关联里的「同游戏 / 同类型 / 同分组」只是计数 —— 上面分类 chip 已经是它们的入口，再做一遍就是两个入口同一件事
- ❌ 一个字段配三个复制变体（名称 / 一行信息 / JSON）—— 留一个最全的就够

三处入口同一个筛选、或者一片下划线的信息面板，得到的不是「更语义化的界面」，
而是一片点不动重点的噪音。**命令区的条数应当等于真的独立能力的条数**，而不是字段数。

### 同源实践：`unified-rx-mcp`

`D:\开发\unified-rx-mcp` 是这条理念的另一半：它把**代码对象**渲染成 MCP 工具面 ——
`代码对象 → 工具（名字 + 描述 + schema）→ 调用 → 系统能力`。本项目把**资产对象**渲染成语义化界面 ——
`资产对象 → 组件 → 点击 → 能力`。两者都是「把对象包成有语义、可调用的一层壳，
调用落到真实能力上」，只是一个面向 agent、一个面向人。

## 目录结构

```
index.html              前端全部（单文件，无构建）：符号轨道 + 虚拟滚动 + 居中查看器
_res/icons.js           符号系统单一来源：SVG 符号雪碧，统一由 PAINT_ICONS 绘制
_res/three.min.js       three.js r*（MIT，随仓内置以便离线运行）
_res/OBJLoader.js       three.js 官方扩展（MIT）
_res/OrbitControls.js   three.js 官方扩展（MIT）
serve_v3.py             静态服务：gzip 预压、/open 定位文件、/diag 自检回传、--root 预览 CD 产物
build_catalog_v3.py     扫描 models/ → catalog_v3.json
build_thumbs.py         软件光栅化每个 OBJ → _thumbs/<id//1000>/<id>.webp
verify_ui.py            真实浏览器自检：结构 + 截图 + 版面像素 + --route 命令路由点击链路
process_obj.py          旧版 OBJ→JS 转义缓存（保留，新界面不依赖）
tools/build_standalone.py  出「双击即用」两种形态：_res/catalog.js 与 dist/资产库.html
tools/build_site.py        组装可发布的演示站点（本地与 CI 同源，cd.yml 直接调它）
tools/                     门禁：路径纪律 / 明文 / 语法 / GitHub API 推送
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
| 点卡片 / `Enter` | 居中详情面板（占屏 92%）：中间 3D 可拖动观察，两侧斜切信息板 |
| 面板内 `←→` | 连续翻上一个 / 下一个模型 |
| 贴图排（中心上方） | 点任意贴图缩略图即覆盖到模型；平铺 ×1/×2/×4；亮度滑杆 |
| 底部 ⧉ | 隐藏 / 显示 14,394 个重复副本 |
| 带虚线的字段 | 可点，点了执行对应命令（悬停会说明是什么命令） |
| 命令区 | 四条真实能力：复制路径 / 拷贝条目 JSON / 在资源管理器中定位 / 下载 OBJ |

视图模式、卡片尺寸、深浅色、收藏都会记在 `localStorage`。
URL 加 `?diag=1` 是界面自检页，逐项列出每个 UI 元素的存在性与尺寸。

## 数据字典（`catalog_v3.json` 的 `items[]`）

| 字段 | 含义 | 备注 |
|---|---|---|
| `id` | 序号 | 同时是缩略图文件名 `_thumbs/<id//1000>/<id>.webp` |
| `g` `k` `f` | 游戏 / 统一分类 / 分组 | 跨游戏双层分类，解决三套目录体系打架 |
| `c` `n` `rn` `p` | 原始目录 / 文件名 / 资源原名 / 相对路径 | |
| `s` | 文件大小 | **单位是 KB**（`round(size/1024,1)`），不是字节 |
| `v` `fa` | 顶点数 / 三角面数 | |
| `x` `y` `z` | 包围盒三边 | **原始单位，跨游戏不可比**（中位值 TT 2.0 / WR 10.7 / IS 60.0） |
| `tl` `tn` `tr` `tq` | 贴图列表 / 张数 / 角色集 / 关联质量 | `tq`：1=旧清单精确映射，2=文件名前缀推断；`tn` 必须等于 `len(tl)` |
| `tg` | 标记 | `tex` `low` `hi` `lod` `dup` `col` `empty` `big` |
| `dup` | 重复副本指向的 id | 同游戏 + 同文件名主干，按路径保留第一个 |
| `th` | 缩略图覆盖值（可省） | 演示数据用内联 SVG；**`data:` URI 不能再过一遍 `encodeURI`** |

> ⚠️ 三个已踩过的坑，改代码前先看这里：
> ① `s` 是 KB。当成字节会让 4 MB 的模型显示成 "4 KB"、总容量显示成 "0.0 GB"。
> ② `x/y/z` 是三款游戏各自的原始单位，**不要**做跨游戏的体积比较或排序。
> ③ `data:` URI 不能过 `encodeURI` —— 它会把已经 %-编码的内容再编一遍（`%23` → `%2523`），
>    缩略图会静默变成 0×0 而不报错。

## CI / CD

`.github/workflows/` 下两个工作流，分工明确：

| 工作流 | 管什么 | 内容 |
|---|---|---|
| `gates.yml`（**CI**） | 能不能合 | 自包含三门（路径纪律 / 明文 / 语法）+ ruff 逐规则棘轮 + mypy；另一组把 unified-rx-mcp 工具链钉在固定提交上复核 |
| `cd.yml`（**CD**） | 能不能用 | `tools/build_site.py` 打演示站点 → 部署 GitHub Pages；`build_standalone.py --demo` 出单文件 → 打 `v*` tag 时发 Release |

CD 里有一个必须先说清的前提：CI 中不存在真实资产（`models/` 与 catalog 都不入仓），
所以它打的是**合成数据**产物。做法不是偷偷替换，而是让产物**自报家门**：

- 目录数据带 `demo: true` → 页面顶部出一条「演示数据」提示条
- 合成数据不是随手编的：包围盒 → 等轴测缩略图、合成 OBJ 网格、棋盘格贴图**三者同源**，
  卡片上的顶点 / 面数 / 文件大小就是那个 OBJ 的真实统计值
- 3D 查看器与贴图覆盖因此**不需要任何「演示模式」分支**，走的是和真实资产一样的相对路径

CD 自己也有门（`产物自检` 步）：数据缺 `demo` 标记、缺图标雪碧、缺 `data-act`、
OBJ 数为 0、条目少于 60，一律直接红 —— 免得把一个打不开的空壳发布出去。

本地复现 CD 产物（与线上同一条路径）：

```bash
python tools/build_site.py --out _site
python serve_v3.py --root _site --port 8801
python verify_ui.py --page _site/index.html --base http://localhost:8801 \
                    --diag _site/_diag.txt --route
```

## 质量门

本地与 CI 跑的是同一套脚本，`.github/workflows/gates.yml` 里逐条对应。

```bash
# 自包含三门（零依赖，只用 stdlib）
python tools/path_check.py       # 路径纪律 P1-P5：软链接 / 文件名卫生 / 单文件 ≤1MB / 越界写
python tools/secret_check.py     # 明文门：凭据模式匹配，输出掩码，不回显明文
python tools/syntax_check.py     # 语法门：Python 编译 + 内联 JS（node --check）+ JSON 解析

# 静态门（ruff 逐规则棘轮 / mypy 默认档零容忍），配置在 ruff.toml 与 mypy.ini
ruff check .                     # 当前 0 命中
mypy --config-file mypy.ini build_catalog_v3.py build_thumbs.py serve_v3.py verify_ui.py \
     process_obj.py tools/path_check.py tools/secret_check.py tools/syntax_check.py \
     tools/_push_via_api.py tools/build_standalone.py tools/build_site.py

# 界面回归（需要浏览器 + 本地服务 + numpy/Pillow）
python verify_ui.py              # 结构 + 截图 + 版面像素
python verify_ui.py --route      # 命令路由：点卡片/分类 chip/标记 chip/关联/贴图/平铺，
                                 # 逐条断言「命令被派发」与「能力留下可验证的后果」
```

`verify_ui.py` 把探针脚本注进页面，页面通过 `POST /diag` 把 DOM 诊断回传落盘，再截三张图
做像素级版面分析。之所以这样绕：无头 Edge 的 `--dump-dom` 在部分环境下不出内容，而截图
路径必须是 Windows 绝对路径、且**必须带 `--no-first-run` 并保留 user-data-dir**，否则会停在首启页出白图。

`--route` 的判据刻意分两层：**派发层**（点击确实到达 `ACTIONS` 里那个命令）
与**能力层**（状态类命令必须留下后果：筛选生效、面板收起、换到另一个模型、纹理真的换了一茬）。
只测前者会漏掉「命令名写对但函数体是空的」，只测后者会漏掉「绕开路由直接改状态」——
贴图排就曾自己绑了一套 `onclick` 绕过路由，是这条自检抓出来的。

## 许可

本仓自有代码以 MIT 发布（见 `LICENSE`）。
`_res/three.min.js`、`_res/OBJLoader.js`、`_res/OrbitControls.js` 为 three.js 项目（MIT）的副本，
版权归其作者所有。
`models/` 下的游戏资产**不在本仓范围内**，其版权归各游戏厂商所有。
