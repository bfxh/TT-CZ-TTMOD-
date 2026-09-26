/* ============================================================
   符号系统 ICON SYSTEM  —  资产库 UI v4
   24×24 网格 · 线性 · stroke-width 1.7 · 圆头圆角
   同一语义 = 同一符号，全站不得二次发明
   ============================================================ */
window.ICONS = {
  /* — 导航 / 结构 — */
  all:    '<rect x="3.2" y="3.2" width="7.2" height="7.2" rx="2"/><rect x="13.6" y="3.2" width="7.2" height="7.2" rx="2"/><rect x="3.2" y="13.6" width="7.2" height="7.2" rx="2"/><rect x="13.6" y="13.6" width="7.2" height="7.2" rx="2"/>',
  game:   '<path d="M12 2.8 20.2 7.2 12 11.6 3.8 7.2Z"/><path d="M3.8 12 12 16.4 20.2 12"/><path d="M3.8 16.6 12 21 20.2 16.6"/>',
  kind:   '<path d="M12 3.2 20 7.6v8.8L12 20.8 4 16.4V7.6Z"/><path d="M12 8.4 16 10.6v4.4L12 17.2 8 15V10.6Z"/>',
  group:  '<path d="M3.2 6.6c0-1.1.9-2 2-2h3.4l1.9 2.3h6.3c1.1 0 2 .9 2 2v8.3c0 1.1-.9 2-2 2H5.2c-1.1 0-2-.9-2-2Z"/>',
  star:   '<path d="M12 3.6l2.6 5.3 5.8.85-4.2 4.1 1 5.8-5.2-2.75-5.2 2.75 1-5.8-4.2-4.1 5.8-.85Z"/>',
  dup:    '<rect x="3.4" y="7.4" width="8.2" height="9.2" rx="2"/><rect x="12.4" y="7.4" width="8.2" height="9.2" rx="2"/><path d="M7.5 4.6h9"/>',

  /* — 工具 — */
  search: '<circle cx="10.6" cy="10.6" r="6.1"/><path d="M15.1 15.1 20 20"/>',
  sort:   '<path d="M7.4 20V5.2"/><path d="M4.4 8.2l3-3 3 3"/><path d="M16.6 4v14.8"/><path d="M13.6 15.8l3 3 3-3"/>',
  grid:   '<rect x="3.2" y="3.2" width="7.2" height="7.2" rx="2"/><rect x="13.6" y="3.2" width="7.2" height="7.2" rx="2"/><rect x="3.2" y="13.6" width="7.2" height="7.2" rx="2"/><rect x="13.6" y="13.6" width="7.2" height="7.2" rx="2"/>',
  list:   '<rect x="3.2" y="4.6" width="4.4" height="3.6" rx="1.1"/><path d="M10.4 6.4H20.8"/><rect x="3.2" y="10.2" width="4.4" height="3.6" rx="1.1"/><path d="M10.4 12H20.8"/><rect x="3.2" y="15.8" width="4.4" height="3.6" rx="1.1"/><path d="M10.4 17.6H20.8"/>',
  density:'<path d="M3.6 6.4h16.8"/><path d="M6.4 12h11.2"/><path d="M9.2 17.6h5.6"/>',
  filter: '<path d="M3.4 5.2h17.2l-6.7 7.7v6.3l-3.8-2.1v-4.2Z"/>',
  theme:  '<circle cx="12" cy="12" r="8.2"/><path d="M12 3.8a8.2 8.2 0 0 1 0 16.4Z" fill="currentColor" stroke="none"/>',
  more:   '<circle cx="12" cy="12" r="8.2"/><circle cx="8" cy="12" r="1.25" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.25" fill="currentColor" stroke="none"/><circle cx="16" cy="12" r="1.25" fill="currentColor" stroke="none"/>',
  reset:  '<path d="M4.6 12a7.4 7.4 0 1 0 2.5-5.6"/><path d="M4.6 4.4V9h4.6"/>',
  stats:  '<path d="M3.6 20.4h16.8"/><rect x="5.8" y="11.4" width="3.4" height="6" rx="1.1"/><rect x="11" y="7.2" width="3.4" height="10.2" rx="1.1"/><rect x="16.2" y="13.8" width="3.4" height="3.6" rx="1.1"/>',
  close:  '<path d="M6.6 6.6 17.4 17.4M17.4 6.6 6.6 17.4"/>',
  chev:   '<path d="M9.6 5.4 16.2 12l-6.6 6.6"/>',

  /* — 几何指标（信息首要的核心符号） — */
  vtx:    '<path d="M12 4.2 20.6 19.2H3.4Z"/><circle cx="12" cy="4.2" r="1.7" fill="currentColor" stroke="none"/><circle cx="20.6" cy="19.2" r="1.7" fill="currentColor" stroke="none"/><circle cx="3.4" cy="19.2" r="1.7" fill="currentColor" stroke="none"/>',
  face:   '<path d="M12 4.2 20.6 19.2H3.4Z"/><path d="M12 4.2v15"/><path d="M7.7 11.7h8.6"/><path d="M5.5 15.5h13"/>',
  bbox:   '<path d="M12 3.4 20 7.8v8.4L12 20.6 4 16.2V7.8Z" stroke-dasharray="3.2 2.4"/><path d="M4 7.8 12 12.2l8-4.4M12 12.2v8.4"/>',
  dim:    '<rect x="2.8" y="8.2" width="18.4" height="7.6" rx="1.8"/><path d="M7.2 8.2v3.1M10.9 8.2v4.6M14.6 8.2v3.1M18.3 8.2v4.6"/>',
  tex:    '<rect x="3.2" y="4.6" width="17.6" height="14.8" rx="2.8"/><circle cx="8.4" cy="9.4" r="1.8"/><path d="M3.8 17.6 9.6 12.4l3.5 3.3 2.9-2.3 4.4 4.2"/>',
  doc:    '<path d="M13.6 3.4H7.2a2 2 0 0 0-2 2v13.2a2 2 0 0 0 2 2h9.6a2 2 0 0 0 2-2V8.6Z"/><path d="M13.6 3.4v5.2h5.2"/>',

  /* — 状态 — */
  ok:     '<circle cx="12" cy="12" r="8.2"/><path d="M8.2 12.2l2.7 2.7 5-5.3"/>',
  no:     '<circle cx="12" cy="12" r="8.2"/><path d="M8.9 8.9l6.2 6.2M15.1 8.9l-6.2 6.2"/>',
  warn:   '<path d="M12 4.2 21 19.4H3Z"/><path d="M12 9.4v4.3"/><circle cx="12" cy="16.6" r=".95" fill="currentColor" stroke="none"/>',
  sync:   '<path d="M4.6 12a7.4 7.4 0 0 1 12.6-5.2"/><path d="M17.2 3.8v3.6h-3.6"/><path d="M19.4 12a7.4 7.4 0 0 1-12.6 5.2"/><path d="M6.8 20.2v-3.6h3.6"/>',

  /* — 操作 — */
  cube:   '<path d="M12 3.4 20 7.8v8.4L12 20.6 4 16.2V7.8Z"/><path d="M4 7.8 12 12.2l8-4.4M12 12.2v8.4"/><path d="M12 3.4l8 4.4-8 4.4-8-4.4Z" fill="currentColor" opacity=".16" stroke="none"/>',
  dl:     '<path d="M12 3.8v10.6"/><path d="M7.6 10.4 12 14.8l4.4-4.4"/><path d="M4.4 17.4v1.6c0 1.2 1 2.2 2.2 2.2h10.8c1.2 0 2.2-1 2.2-2.2v-1.6"/>',
  copy:   '<rect x="9" y="9" width="11" height="11" rx="2.8"/><path d="M15.2 5.8A2.6 2.6 0 0 0 12.8 3.6H6.8A2.6 2.6 0 0 0 4.2 6.2v6A2.6 2.6 0 0 0 6.6 14.8"/>',
  reveal: '<path d="M3.2 6.6c0-1.1.9-2 2-2h3.4l1.9 2.3h6.3c1.1 0 2 .9 2 2v2.4"/><path d="M2.8 11.6h18.4l-2 8.2c-.2.9-1 1.6-2 1.6H6.8c-1 0-1.8-.7-2-1.6Z"/>',
  info:   '<circle cx="12" cy="12" r="8.2"/><path d="M12 11.2v5.2"/><circle cx="12" cy="7.9" r=".95" fill="currentColor" stroke="none"/>',
  pin:    '<path d="M8.6 3.6h6.8l-.9 5.4 3.4 3.6H6.1l3.4-3.6Z"/><path d="M12 12.6v7.8"/>',

  /* — 游戏标识 — */
  'g-hex':   '<path d="M12 3.2 20 7.6v8.8L12 20.8 4 16.4V7.6Z" fill="currentColor" opacity=".18" stroke="none"/><path d="M12 3.2 20 7.6v8.8L12 20.8 4 16.4V7.6Z"/>',
  'g-shield':'<path d="M12 3.4 19.4 6v6.2c0 4-3.1 6.9-7.4 8.4-4.3-1.5-7.4-4.4-7.4-8.4V6Z"/>',
  'g-gear':  '<circle cx="12" cy="12" r="3.2"/><path d="M12 2.6v3.2M12 18.2v3.2M4.4 12H1.4M22.6 12h-3M6.7 6.7 4.5 4.5M19.5 19.5l-2.2-2.2M17.3 6.7l2.2-2.2M4.5 19.5l2.2-2.2"/>',

  /* — 统一分类 kind（13） — */
  'k-module':  '<rect x="5.6" y="5.6" width="12.8" height="12.8" rx="2.8"/><circle cx="12" cy="12" r="2.4"/>',
  'k-weapon':  '<circle cx="12" cy="12" r="7.6"/><path d="M12 2.6v4.3M12 17.1v4.3M2.6 12h4.3M17.1 12h4.3"/><circle cx="12" cy="12" r="2.1" fill="currentColor" stroke="none"/>',
  'k-mech':    '<path d="M8.6 6.2h6.8v4.6H8.6Z"/><path d="M5.4 10.8h13.2v7.6a2 2 0 0 1-2 2H7.4a2 2 0 0 1-2-2Z"/><path d="M9.6 14.6h4.8"/>',
  'k-mobile':  '<rect x="3.2" y="9.2" width="17.6" height="6.4" rx="2.2"/><circle cx="7.2" cy="15.4" r="2.6"/><circle cx="16.8" cy="15.4" r="2.6"/>',
  'k-struct':  '<path d="M3.4 20.4h17.2"/><path d="M5.6 20.4V9.4h5.2v11"/><path d="M13.2 20.4V5.2h5.2v15.2"/><path d="M6.8 12.6h2.8M6.8 15.8h2.8M14.4 8.4h2.8M14.4 11.6h2.8M14.4 14.8h2.8"/>',
  'k-terrain': '<path d="M2.6 19.4 9.2 8.2l4.2 6.6 2.4-3.2 5.6 7.8Z"/>',
  'k-foliage': '<path d="M12 3.4 19.4 13.8H4.6Z"/><path d="M12 8.6 20.4 19.6H3.6Z"/><path d="M12 19.6v1.2"/>',
  'k-prop':    '<path d="M12 3.6 20 8v8l-8 4.4L4 16V8Z"/><path d="M4 8l8 4.4L20 8M12 12.4v8"/>',
  'k-drone':   '<rect x="9" y="9" width="6" height="6" rx="1.7"/><circle cx="5.4" cy="5.4" r="2.7"/><circle cx="18.6" cy="5.4" r="2.7"/><circle cx="5.4" cy="18.6" r="2.7"/><circle cx="18.6" cy="18.6" r="2.7"/><path d="M7.7 7.7 9.4 9.4M16.3 7.7 14.6 9.4M7.7 16.3 9.4 14.6M16.3 16.3 14.6 14.6"/>',
  'k-vfx':     '<path d="M10.6 3.2 12.4 7.9 17.1 9.7 12.4 11.5 10.6 16.2 8.8 11.5 4.1 9.7 8.8 7.9Z"/><path d="M17.6 14.4 18.4 16.6 20.6 17.4 18.4 18.2 17.6 20.4 16.8 18.2 14.6 17.4 16.8 16.6Z"/>',
  'k-ui':      '<rect x="3.4" y="4.6" width="17.2" height="14.8" rx="2.6"/><path d="M3.4 9.2h17.2"/><path d="M7 13.4h6.4M7 16.4h4"/>',
  'k-collider':'<circle cx="12" cy="12" r="8" stroke-dasharray="3 2.6"/>',
  'k-misc':    '<circle cx="12" cy="12" r="8.2"/><circle cx="8.2" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none"/><circle cx="15.8" cy="12" r="1.2" fill="currentColor" stroke="none"/>'
};

/* 注入 <symbol> 雪碧 —— 虚拟滚动节点池靠切换 <use href> 换图标，避免重建 SVG DOM */
window.buildSprite = function () {
  if (document.getElementById('isprite')) return;
  var syms = Object.keys(window.ICONS).map(function (k) {
    return '<symbol id="i-' + k + '" viewBox="0 0 24 24">' + window.ICONS[k] + '</symbol>';
  }).join('');
  /* 必须走 HTML 解析器插入：createElement('svg') 会得到 HTMLUnknownElement，
     里面的 <symbol> 也落在 XHTML 命名空间，<use> 引用会渲染成 0×0 的空盒子 */
  document.body.insertAdjacentHTML('afterbegin',
    '<svg id="isprite" aria-hidden="true" style="position:absolute;width:0;height:0;overflow:hidden">' +
    syms + '</svg>');
};
/* 取符号名 → 供 <use href> 使用 */
window.IREF = function (n) { return '#i-' + n; };
/* 输出完整 svg 标记（静态文档用） */
window.SVGICON = function (n, cls, style) {
  if (!window.ICONS[n]) return '';
  return '<svg class="ic' + (cls ? ' ' + cls : '') + '"' + (style ? ' style="' + style + '"' : '') +
    ' aria-hidden="true"><use href="' + window.IREF(n) + '"/></svg>';
};
/* 把文档里所有 [data-i] 占位替换成符号。
   注意两点（都是踩过坑的）：
   ① 判定「已画好」要同时看 data-painted **和** 里面真的有 svg ——
      只信 data-painted 的话，一次失败的绘制会被永久记为已完成，再也不会补；
   ② 图标名不存在时不写 data-painted，留给下一次调用重试，并把名字报出来。 */
window.PAINT_ICONS = function (root) {
  window.buildSprite();
  var missing = [];
  (root || document).querySelectorAll('[data-i]').forEach(function (e) {
    if (e.dataset.painted && e.querySelector('svg')) return;
    var html = window.SVGICON(e.dataset.i);
    if (!html) { missing.push(e.dataset.i); return; }
    e.innerHTML = html;
    e.dataset.painted = '1';
  });
  if (missing.length) console.warn('[icons] 未知图标名，未能绘制：', missing.join(', '));
  return missing;
};
