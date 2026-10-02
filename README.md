# 资产库 · 多游戏统一资产浏览器

把多款游戏导出的 3D 模型堆成一个**可搜、可比、可预览**的本地资产库。
纯静态前端 + 一个零依赖 Python 服务，没有构建步骤。

当前已入库三款：TerraTech / War Robots / Iron Saga；第四款 **Battle of Titans（战斗泰坦）**
已留好接入位（`models/04_战斗泰坦/`），资源一到就自动生效 —— 见「加第 N 个游戏」。

```
31,611 个 OBJ · 17,217 唯一资产 · 14,394 重复副本 · 2.5 GB · 31,396 张离线渲染缩略图
```

## 开箱即用

按「用户要动几下手」从少到多排：

| 方式 | 要做什么 | 得到什么 |
|---|---|---|
| **双击**（最少） | `python tools/build_standalone.py` 后双击 `index.html` | **三款游戏的全部 31,611 个真实条目 + 真实缩略图**，缩略图/筛选/排序/收藏全可用 |
| **起服务** | 双击 `start_vault.bat` | 再加 3D 预览（加载真实 OBJ）、贴图覆盖、在资源管理器中定位 |
| **单文件**（可选） | `python tools/build_standalone.py --form single` | `dist/资产库.html`，拷到别处也能打开看条目；**不含缩略图** |
| **在线** | 见下文「CI / CD」 | 目前不发 —— 真实数据不在仓库里，见该节说明 |

不需要「先读文档找到入口，再进到某个子目录下找那个文件」——`index.html` 就在仓库根目录，双击即可。

关于两种「一个文件」的边界（这里踩过坑，写清楚）：

- `index.html` 是**全量库**的双击入口。它旁边有 `_res/` 与 `_thumbs/`，相对路径正常，
  打开就是真实的三个游戏。
- `dist/资产库.html` 是**单文件**形态，只内联图标与目录数据。`file://` 下相对路径按
  **文件自身位置**解析，单文件一旦放进 `dist/`，里面的 `_thumbs/…` 就变成
  `dist/_thumbs/…`（不存在），三万多张卡片会全部写「无缩略图」；而真实缩略图有 153 MB，
  也内联不进去。所以它默认不生成，只在「拷到别处、只求能打开看条目」时才用。

> 为什么双击也能读数据：浏览器在 `file://` 下会拦掉 `fetch()`，但**脚本标签不受同源限制**。
> 所以 `tools/build_standalone.py` 把目录数据写成 `_res/catalog.js`（`window.CATALOG = {...}`），
> `index.html` 优先读它、读不到再退回 `fetch('catalog_v3.json')`、都没有就给出可执行的下一步。

## 加第 N 个游戏（换一批资产）

三步，没有别的机关：

```bash
# 1) 把导出的模型放进 models/<NN>_<中文名>/，然后往 GAMES 表末尾**追加**一条
#    build_catalog_v3.py:  ('bot', '04_战斗泰坦', '战斗泰坦', 'Battle of Titans', '#0FB5C9')
#    index.html:           bot:['战斗泰坦','#12A5C6']
python build_catalog_v3.py      # 扫出目录；新素材没缩略图，下一步补
python build_thumbs.py          # 只渲缺的那些（已存在的自动跳过）
```

**⚠️ 只能往 GAMES 末尾追加，不能在中间插。** 入库序号 `<id>` 是按「GAMES 顺序 + 目录遍历顺序」
递增分配的，而缩略图文件名就是 `_thumbs/<id//1000>/<id>.webp` —— 中间插一条会把后面所有游戏的
序号整体挪位，等于三万多张缩略图集体错位。追加不会动到已有序号（实测重建前后
`id → 路径` 映射 0 处变化）。

界面侧不需要额外改：

- 游戏筛选面板与统计是**数据驱动**的，会自动列出目录里存在的 gid；
- **0 条的游戏不出现**（点了只会得到空结果，那是死入口），所以接入位留好了也不会有空 chip；
- `index.html` 的 `GAMES` 里没有的 gid 会退回「用 gid 当名字 + 中性灰」，不会消失 ——
  但如果想显示正常的中文名与点色，还是补一条。

### 战斗泰坦（B.o.T）的现状

`B.o.T.apk`（58 MB，包名 `com.rbuttongames.battlemechs`）**里面没有模型**，别白翻：
它是 Unreal Engine 4，APK 只装了引擎运行时（`lib/arm64-v8a/libUnreal.so` 116 MB 解压后）
与腾讯/微博 SDK；`assets/` 下没有任何 `.pak`/`.uasset`，`.res`/`.nrm`/`.spp` 全是 IBM ICU 的
Unicode 数据。工程名从 `assets/UECommandLine.txt` 可读到是 `BattleMechs.uproject`，
`classes.dex` 里引用 `application/vnd.android.obb` —— 内容走 **OBB / Play Asset Delivery**，
或者运行时从 CDN 下载到应用数据目录。完整安装约 1.3 GB，对比之下 APK 的 58 MB 就很说明问题。

要拿到模型，三条路（按省事程度）：

1. **同一个镜像站下载 XAPK / APK+OBB 变体**（而不是纯 `.apk`）。OBB 名为
   `main.<版本号>.com.rbuttongames.battlemechs.obb`，里面是 UE 的 `Content/Paks/*.pak`。
2. **装到手机上跑一次再 adb pull**：内容会落在
   `/sdcard/Android/data/com.rbuttongames.battlemechs/`（UE 的 PersistentDownloadDir）
   与 `/sdcard/Android/obb/com.rbuttongames.battlemechs/`。
3. 找现成的 dump（像本机已有的 `TerraTech.7z` / `WarRobots.7z` 那样）。

拿到 `.pak` 之后的流程：UE4 的 pak 用 umodel / FModel / repak 解包导出 meshes（psk/obj）
与贴图，再落进 `models/04_战斗泰坦/`。注意 pak 可能带 AES 加密，届时需要对应的密钥。

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
# 1) 准备资产（模型放到 models/ 下，目录名按 build_catalog_v3.py 的 GAMES 常量来）
#    01_泰拉科技/  02_战争机器人/  03_重装上阵/  04_战斗泰坦/（可选，缺了就跳过）

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
tools/build_standalone.py  出「双击即用」形态：_res/catalog.js（与可选的单文件）
tools/check_doubleclick.py 以 file:// 打开页面截图，验「双击就能看到东西」
tools/thumb_orient_check.py 缩略图朝向门：不对称网格的着墨范围必须等于投影范围
tools/serve_guard_check.py  静态服务路径守卫门：起真服务 + 原始请求路径打穿越
tools/artifact_guard_check.py 产物安全门：内联目录数据必须对 HTML 安全
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
| 点卡片 / `Enter` | 居中详情面板（占屏 92%）：中间 3D 可拖动观察，两侧斜切（56px，左右镜像）信息板 |
| 面板内 `←→` | 连续翻上一个 / 下一个模型 |
| 贴图排（中心上方） | 点任意贴图缩略图即覆盖到模型；平铺 ×1/×2/×4；亮度滑杆 |
| 底部 ⧉ | 隐藏 / 显示 14,394 个重复副本 |
| 带虚线的字段 | 可点，点了执行对应命令（悬停会说明是什么命令） |
| 命令区 | 四条真实能力：复制路径 / 拷贝条目 JSON / 在资源管理器中定位 / 下载 OBJ |

左板「分类 / 标识 / 贴图」是**信息板**：只有「完整路径」等少数几个值可点（复制路径），
其余字段就是文字。右板「几何 / 关联 / 标记 / 命令 / 索引」里，「标记」是筛选入口、
「关联」只把别处没有入口的（同名族 / 共用首张贴图）做成可点、「命令」是真正的动作列表。
判断标准见上文「不要给每个字段都做成按钮」。

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

> ⚠️ 三个已踩过的坑，改代码前先看这里：
> ① `s` 是 KB。当成字节会让 4 MB 的模型显示成 "4 KB"、总容量显示成 "0.0 GB"。
> ② `x/y/z` 是三款游戏各自的原始单位，**不要**做跨游戏的体积比较或排序。
> ③ 卡片尺寸不要用 `CARD_W` 去「算」。`#win` 的网格列被 `1fr` 拉伸（dens=中 时实际 218 而不是
>    196），按常量算出来的缩略图高度会短 15px，被 `overflow:hidden` 裁掉底部；同一处偏差
>    还会让虚拟滚动的行距差 3.84px，三万多条滚到后面累计漂移上万像素。现在高度由 `--thumbH`
>    下发、行距**实测**标定，两个数不可能再对不上。

## CI / CD

`.github/workflows/` 下两个工作流：

| 工作流 | 管什么 | 内容 |
|---|---|---|
| `gates.yml`（**CI**） | 能不能合 | 自包含三门（路径纪律 / 明文 / 语法）+ ruff 逐规则棘轮 + mypy；另一组把 unified-rx-mcp 工具链钉在固定提交上复核；缩略图朝向门 |
| `cd.yml`（**CD**） | 能不能用 | 把仓库内容变成可打开的东西，再挂到 Pages / Release |

### CD 为什么**不**发布任何东西（以及什么条件下会）

真实数据**不在仓库里**：`models/` 2.5 GB（版权归各厂商）、`catalog_v3.json` 13 MB、
`_thumbs/` 153 MB，全部被 `.gitignore` 挡住。所以 CI 里没有任何可发布的内容。

CD 于是只有两种诚实的做法：**明确跳过并说明**，或者**先合成一份假目录把流程跑通**。
这里选前者 —— 后者能产出一个「看起来能用、实际全是编造内容」的站点，
而这正是本项目明确不要的东西（曾经真这么做过一版：`--demo` 造的合成模型 + 合成缩略图 +
GitHub Pages 上的假库，已被全部删除）。

`cd.yml` 现在会先探测仓库里有没有 `catalog_v3.json` 与 `_thumbs/`：
没有就 `::notice` 说明缺什么、本地怎么用；有就自动开始打包发布。
也就是说 —— **一旦你决定把数据入仓，CD 不需要再改就能工作**。

### 推送通道（本机的坑）

本机 `git push` 走不通：schannel 报 `CRYPT_E_NO_REVOCATION_CHECK`，换 openssl 报
`unable to get local issuer certificate`（本机有 TLS 拦截，两条路都堵），
`http.schannelCheckRevoke=false` / `sslVerify=false` / `GIT_SSL_NO_VERIFY=1` 全试过，都无效。
所以推送走 `tools/_push_via_api.py`（Git Data API，`gh` 的 Go TLS 栈正常）。

**代价**：commit 是在服务端重建的，本地那个 commit 对象根本没上传，
于是**本地与远端是两条内容一致、SHA 不同的平行历史**。后果是：
`git log` 的 SHA 与 GitHub 上对不上、将来 `git push` 会被拒（非快进）、
`git status` 看着干净但历史已经分叉。脚本在推送末尾会把这件事打出来。

**根治**：把本机公钥（`~/.ssh/id_ed25519.pub`）加到 GitHub 账号的 SSH keys，
然后 `git remote set-url origin git@github.com:bfxh/TT-CZ-TTMOD-.git` ——
SSH 完全绕开 TLS 拦截。实测本机 SSH **能连到 GitHub**（握手正常），
只是公钥还没注册，所以现在是 `Permission denied (publickey)`。

本地复现线上产物（三条命令，与 CD 同源）：

```bash
python tools/build_standalone.py --form js
python serve_v3.py                       # 或直接双击 index.html
python verify_ui.py --route              # 命令路由点击链路自检
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
     tools/_push_via_api.py tools/build_standalone.py tools/check_doubleclick.py

# 界面回归（需要浏览器 + 本地服务 + numpy/Pillow）
python verify_ui.py              # 结构 + 截图 + 版面像素
python verify_ui.py --route      # 命令路由：点卡片/分类 chip/标记 chip/关联/贴图/平铺，
                                 # 逐条断言「命令被派发」与「能力留下可验证的后果」
python verify_ui.py --shots /tmp/s1   # 换个截图目录（反复跑时避免清理旧图）

# 缩略图朝向（需要 numpy）：不对称网格的着墨范围必须等于投影范围
python tools/thumb_orient_check.py

# 静态服务路径守卫（零依赖）：起真服务，用原始请求路径打穿越
python tools/serve_guard_check.py

# 产物安全（零依赖）：拿恶意文件名让构建器内联，产物必须对 HTML 安全
python tools/artifact_guard_check.py

# 双击可用性（无头浏览器以 file:// 打开并截图，不需要服务）
python tools/check_doubleclick.py
```

### 无头截图必须是**确定**的，否则像素判据全是噪声

`verify_ui.py` 的浏览器启动参数里 `--run-all-compositor-stages-before-draw` 不是可选项。
没有它时，无头 + `--virtual-time-budget` 会在虚拟时间里跑完脚本、却拿到合成器**还没画出来**
的那一帧：实测同一页面状态连拍 4 张出过 3 种画面（最大差 67 万像素 / 总像素 168 万），
其中一张是「总览层刚打开、还在 opacity 淡入」的半透明面板 —— 看起来就像「信息板透光」的
真 bug，我为此查了很久。加上开关后 4 张逐像素相同。

反过来也**不要**加 `--disable-new-content-rendering-timeout`：它把「内容已稳定」的计时器
一起关掉，页面只要还有持续动画就永远不返回，实测把自检挂死在 300s 超时上。

`check_doubleclick.py` 是唯一一条**不依赖本地服务**的界面判据：它要验的恰恰是没有服务时的表现。
没有 `POST /diag` 回传通道，就直接看截图 —— 出了卡片网格的截图都在 60 KB 以上，
白图/报错页是近乎纯色的小图，一量就知道。这条判据抓到过 `dist/资产库.html` 在 `dist/` 下
缩略图全断的问题（`file://` 下相对路径按文件自身位置解析，不是按仓库根）。

`thumb_orient_check.py` 抓的是一个**极安静**的错误：`raster()` 的帧缓冲轴序写成 `[x][y]`，
而 `Image.fromarray` 按 axis 0 分行 ⇒ 每张缩略图都是投影的转置（躺倒 90°）。
它不报错、不崩溃、不缺图，三万多张一起看也看不出（每张都错就没有参照物），
只有**不对称**网格能钉死它 —— 立方体、球这类对称形状转了 90° 照样「看着对」。

`verify_ui.py` 把探针脚本注进页面，页面通过 `POST /diag` 把 DOM 诊断回传落盘，再截三张图
做像素级版面分析。之所以这样绕：无头 Edge 的 `--dump-dom` 在部分环境下不出内容，而截图
路径必须是 Windows 绝对路径、且**必须带 `--no-first-run` 并保留 user-data-dir**，否则会停在首启页出白图。

`--route` 的判据刻意分两层：**派发层**（点击确实到达 `ACTIONS` 里那个命令）
与**能力层**（状态类命令必须留下后果：筛选生效、面板收起、换到另一个模型、纹理真的换了一茬）。
只测前者会漏掉「命令名写对但函数体是空的」，只测后者会漏掉「绕开路由直接改状态」——
贴图排就曾自己绑了一套 `onclick` 绕过路由，是这条自检抓出来的。

## 安全

这个项目是本机工具（服务只绑 `127.0.0.1`），但「本机工具」不等于「不用管安全」：
目录数据来自磁盘上的文件名，可以是任意的。2026-09-28 做过一次针对性审计，
找到并修掉三处，每条都配了能**回退验证**的门（把修复改回去，门必须变红）。

| 问题 | 表现 | 修法 | 门 |
|---|---|---|---|
| **前端 HTML 注入** | `esc()` 原来只在筛选条用了 2 处，详情面板的显示名 / 路径 / 分组名 / 贴图名全是裸拼进 `innerHTML`。一个叫 `<img src=x onerror=…>.obj` 的文件就能执行脚本（回退验证实测：**触发脚本 1 次、新增元素 4 个**） | 在 `row()` / `chip()` / `cbtn()` 三个「数据 → HTML」出口统一转义，颜色值加白名单，贴图名的 `title` 属性同样转义 | `verify_ui.py --route` 里的注入自测 |
| **内联数据可提前闭合 `<script>`** | `json.dumps` 不转义 `<` `>` `&`，单文件版把目录数据内联进 `<script>` 时，一个叫 `</script>` 的文件名会让标签提前闭合、后面的内容变成标记（回退验证实测：`<script>` 数 **4 → 6**） | 序列化时把 `<` `>` `&` 转成 `\u003c` `\u003e` `\u0026`，并做「失败即失败」断言 | `tools/artifact_guard_check.py` |
| **静态服务路径穿越** | `do_GET` 的 gzip 快速路径自己拼了一次路径、绕过 `SimpleHTTPRequestHandler` 的保护：`GET /../decoy.txt` 用**原始请求路径**发（`curl --path-as-is`，浏览器会自动规范化所以测不出来）能拿到站外文件 —— 回退验证实测**返回 200 并吐出站外内容**。另有 `replace('..','')` 过滤（`....//` 可绕）与 `startswith(SITEDIR)` 前缀匹配（同前缀兄弟目录可穿） | 统一走 `inside()`：剥掉 URL 前导 `/` → 挡盘符与 NUL → `realpath` → `commonpath` 判断；`/diag` 加正文上限 | `tools/serve_guard_check.py`（8 条判据） |

顺带记两条判据本身踩过的坑：

- **测穿越必须用原始请求路径**。浏览器和 `requests` 都会先规范化 `/../x`，从它们那边看永远是安全的。
- **门自己也会挂**：`inside()` 第一版把「HTTP 路径总以 `/` 开头」当成绝对路径，整站 403，
  门于是在启动探测上超时；而失败分支里去 `proc.stdout.read()` 收子进程输出又会**永久阻塞**。
  现在的写法是：先剥前导斜杠，收输出前先 terminate。

## 许可

本仓自有代码以 MIT 发布（见 `LICENSE`）。
`_res/three.min.js`、`_res/OBJLoader.js`、`_res/OrbitControls.js` 为 three.js 项目（MIT）的副本，
版权归其作者所有。
`models/` 下的游戏资产**不在本仓范围内**，其版权归各游戏厂商所有。
