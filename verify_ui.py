#!/usr/bin/env python
"""真实浏览器自检：
   · 页面把诊断结果 POST 到 /diag → 落盘 _diag.txt
   · 每个探针截图，并用像素分析 + ASCII 版面缩略图核实分区
关键：profile 目录要保留、必须带 --no-first-run，否则 Edge 停在首启页出白图。
"""
import contextlib
import os
import subprocess
import time

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
TEMP = os.environ.get('TEMP') or r"C:\Windows\Temp"
SHOT = os.path.join(ROOT, '_shots')
DIAG = os.path.join(ROOT, '_diag.txt')

CHECK = r"""
<script>
window.__errs=[]; window.onerror=function(m,s,l){__errs.push(m+'@'+l);};
setTimeout(function(){
  var out=[], bad=[], tot=0;
  document.querySelectorAll('svg.ic use').forEach(function(u){
    tot++;
    var t=document.getElementById((u.getAttribute('href')||'').slice(1));
    if(!t || !(t instanceof SVGElement)){ bad.push(u.getAttribute('href')); return; }
    var s=u.closest('svg');
    if(s && s.getBoundingClientRect().width>0){
      try{ var b=s.getBBox(); if(b.width<0.5&&b.height<0.5) bad.push('空'+u.getAttribute('href')); }catch(e){}
    }
  });
  out.push('图标 <use> '+tot+'，失效 '+bad.length+(bad.length?' → '+bad.slice(0,6).join(','):''));
  out.push('顶栏：'+[].map.call(document.querySelectorAll('.top .seg button,.top .tbtn'),
    function(b){return b.textContent.trim()}).join(' / '));
  out.push('排序条：'+[].map.call(document.querySelectorAll('.mb'),
    function(b){return b.textContent.trim()}).join(' / '));
  out.push('轨道按钮 '+document.querySelectorAll('.rbtn').length+' 个');
  var cds=document.querySelectorAll('.cd');
  var ok=[].filter.call(document.querySelectorAll('.cd .th>img'),function(i){return i.naturalWidth>0;});
  out.push('卡片 '+cds.length+' 个，缩略图解码 '+ok.length+' 张');
  if(cds[0]) out.push('卡片文本：'+cds[0].textContent.replace(/\s+/g,' ').trim());
  if(cds[1]) out.push('第二张：'+cds[1].textContent.replace(/\s+/g,' ').trim());
  try{ open(0); }catch(e){ out.push('open 异常 '+e.message); }
  var d=document.querySelector('#dock');
  out.push('停靠面板 '+(d.classList.contains('on')?'打开':'关闭'));
  out.push('详情字段：'+['显示名','文件名','资源原名','原始目录','相对路径','顶点','三角面','包围盒','文件大小','贴图','标记']
    .filter(function(t){ return d.textContent.indexOf(t)>=0; }).join(' / '));
  out.push('详情正文：'+d.textContent.replace(/\s+/g,' ').trim().slice(0,170));
  out.push('状态条：'+document.querySelector('#sbar').textContent.replace(/\s+/g,' ').trim());
  out.push('JS 错误：'+(__errs.length?__errs.join(';'):'无'));
  try{ fetch('/diag',{method:'POST',body:out.join('\n')}); }catch(e){}
},3200);
</script>
</body>"""

LIST = r"""
<script>
setTimeout(function(){
  document.querySelector('[data-v=list]').click();
  setTimeout(function(){ open(0); }, 600);
},3200);
</script>
</body>"""

VIEW = r"""
<script>
setTimeout(function(){
  open(0);
  setTimeout(function(){
    openViewer();
    setTimeout(function(){
      var o=[], cv=document.querySelector('#shview canvas');
      o.push('查看器 '+(document.querySelector('#sheet').classList.contains('on')?'打开':'关闭'));
      o.push('canvas '+(cv?Math.round(cv.getBoundingClientRect().width)+'×'+Math.round(cv.getBoundingClientRect().height):'未创建'));
      o.push('HUD '+[].map.call(document.querySelectorAll('#shhud .vbtn'),function(b){return b.textContent}).join(' / '));
      o.push('状态行 '+document.querySelector('#shstat').textContent);
      o.push('右侧字段 '+['显示名','顶点','三角面','包围盒','文件大小','贴图','标记']
        .filter(function(t){ return document.querySelector('.shinfo').textContent.indexOf(t)>=0; }).join(' / '));
      try{ fetch('/diag',{method:'POST',body:o.join('\n')}); }catch(e){}
    },7000);
  },500);
},3200);
</script>
</body>"""


def run(name, probe, budget, shot=None):
    with open(os.path.join(ROOT, 'index.html'), encoding='utf-8') as fh:
        src = fh.read()
    src = src.replace('</body>', probe, 1)
    tmp = os.path.join(ROOT, '_t.html')
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(src)
    prof = os.path.join(TEMP, '_vh_' + name)          # 保留 profile，不要删
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
           '--disable-extensions', '--hide-scrollbars', '--enable-unsafe-swiftshader',
           '--user-data-dir=' + prof, '--window-size=1680,1000',
           '--virtual-time-budget=%d' % budget]
    if shot:
        cmd.append('--screenshot=' + shot)
    cmd.append('http://localhost:8800/_t.html')
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, errors='replace')
    time.sleep(1.5)
    with contextlib.suppress(OSError): os.remove(tmp)
    return r


def read_diag(label):
    for _ in range(40):
        if os.path.exists(DIAG):
            with open(DIAG, encoding='utf-8', errors='replace') as fh:
                t = fh.read()
            os.remove(DIAG)
            return t
        time.sleep(0.25)
    return '(未收到 ' + label + ')'


def ascii_map(path, cw=88, ch=38):
    """把截图降采样成字符画——用于在没有图像阅读能力时"看"版面结构"""
    with Image.open(path) as raw:
        gray = raw.convert('L').resize((cw, ch), Image.Resampling.LANCZOS)
        arr = np.asarray(gray, dtype=np.int16)
    ramp = ' .:-=+*#%@'
    idx = np.clip((255 - arr) * 10 // 256, 0, 9)
    return '\n'.join('   ' + ''.join(ramp[k] for k in row) for row in idx)


def regions(path):
    """分区墨迹率：判断版面各区域到底有没有内容（模型读不了图，只能量化）"""
    with Image.open(path) as raw:
        rgb = np.asarray(raw.convert('RGB'), dtype=np.int16)
    h, w = rgb.shape[:2]
    kb_size = os.path.getsize(path) / 1024

    def ink(x0, y0, x1, y1, step=3):
        blk = rgb[y0:y1:step, x0:x1:step]
        if blk.size == 0:
            return 0.0
        return float((blk < 205).any(axis=2).mean())

    def avg(x0, y0, x1, y1, step=4):
        blk = rgb[y0:y1:step, x0:x1:step]
        if blk.size == 0:
            return (0, 0, 0)
        m = blk.reshape(-1, 3).mean(axis=0)
        return (int(m[0]), int(m[1]), int(m[2]))

    right = int(w * (0.52 if kb_size < 200000 else 0.72))
    return ('尺寸 %d×%d  %.0f KB\n'
            '   左轨道区(0-48)      墨迹 %.3f  均色 %s\n'
            '   主内容区            墨迹 %.3f  均色 %s\n'
            '   顶栏(0-44)          墨迹 %.3f\n'
            '   右侧面板(右 392)    墨迹 %.3f') % (
        w, h, kb_size,
        ink(0, 60, 46, h - 30), avg(10, 200, 40, h - 200),
        ink(60, 130, right, h - 40), avg(200, 900, 1000, 990),
        ink(0, 0, w, 42),
        ink(w - 392, 60, w - 4, h - 40))


os.makedirs(SHOT, exist_ok=True)
for f in os.listdir(SHOT): os.remove(os.path.join(SHOT, f))

print('══ 1. 结构自检（真实浏览器 DOM）══')
run('check', CHECK, 22000)
print(read_diag('check'))
print()
print('══ 2. 居中查看器 ══')
run('view', VIEW, 30000, os.path.join(SHOT, '3-viewer.png'))
print(read_diag('view'))
print()
print('══ 3. 截图与版面分析 ══')
run('grid', '', 22000, os.path.join(SHOT, '1-grid.png'))
run('list', LIST, 24000, os.path.join(SHOT, '2-list.png'))
for f, label in [('1-grid.png', '网格视图'), ('2-list.png', '列表视图'), ('3-viewer.png', '居中查看器')]:
    p = os.path.join(SHOT, f)
    print('── %s ──' % label)
    print(regions(p) if os.path.exists(p) else '   截图缺失')
print()
print(ascii_map(os.path.join(SHOT, '1-grid.png')))
print()
print(ascii_map(os.path.join(SHOT, '2-list.png')))
