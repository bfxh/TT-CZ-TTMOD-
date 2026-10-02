# 归档

这里放**已被取代**的实现，只为留个历史记录，不要拿它们当入口用。

| 文件 | 说明 |
|---|---|
| `viewer.html` | 旧版单文件查看器，已被仓库根目录的 `index.html` 取代。它靠 `models/**/*.obj.js`（每份 OBJ 的 `<script>` 包裹副本）绕过 `file://` 下 fetch 被拦的问题；那批 `.obj.js` 共 2.46 GB，已于 2026-10-02 随「资源默认压缩」一起清理，**所以这个页面现在取不到模型数据**。 |
| `design-proposal-v3.html` | 早期设计稿。 |

> 注：`tools/syntax_check.py` 会扫描 `docs/archive/` 下的 HTML。`viewer.html` 里的内联脚本
> 自身含 `'<script src="'` 这类字符串，给它前面加注释会把脚本切分带偏、直接把门打红 ——
> 所以**别改这个文件**，要留说明就写在本文里。
