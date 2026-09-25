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
  out.push('头部：'+[].map.call(document.querySelectorAll('.top .seg button,.top .tbtn,.top .ib'),
    function(b){return b.textContent.trim()||b.title}).join(' / '));
  out.push('没有排序条（.mbar 应为 0）：'+document.querySelectorAll('.mbar').length+
    ' · 排序菜单项 '+document.querySelectorAll('#sortMenu [data-s]').length);
  out.push('没有右侧停靠栏（.dock 应为 0）：'+document.querySelectorAll('.dock').length);
  out.push('轨道按钮 '+document.querySelectorAll('.rbtn').length+' 个');
  var cds=document.querySelectorAll('.cd');
  var ok=[].filter.call(document.querySelectorAll('.cd .th>img'),function(i){return i.naturalWidth>0;});
  out.push('卡片 '+cds.length+' 个，缩略图解码 '+ok.length+' 张');
  if(cds[0]) out.push('卡片文本：'+cds[0].textContent.replace(/\s+/g,' ').trim());
  // 筛选条：加条件应出现，点 ✕ 应消失
  try{
    document.querySelector('.rbtn[data-p=kind]').click();
    setTimeout(function(){
      var op=document.querySelector('#flyL .opt'); if(op) op.click();
      var bar=document.querySelector('#fbar');
      out.push('筛选条 '+(bar.classList.contains('on')?'出现':'未出现')+' · chip '+bar.querySelectorAll('.fchip').length+
        ' · 内容 '+bar.textContent.replace(/\s+/g,' ').trim());
      var x=bar.querySelector('.fchip .x'); if(x) x.click();
      out.push('点 ✕ 后筛选条 '+(document.querySelector('#fbar').classList.contains('on')?'仍在':'收起'));
      // 排序菜单
      document.querySelector('#btnSort').click();
      out.push('排序菜单 '+(document.querySelector('#sortMenu').classList.contains('on')?'打开':'未打开')+
        ' · 选项 '+document.querySelectorAll('#sortMenu [data-s]').length+
        ' · 标签 '+document.querySelector('#sortLab').textContent+document.querySelector('#sortDir').textContent);
      document.querySelectorAll('#sortMenu [data-s]')[2].click();
      out.push('选第 3 项后 → '+document.querySelector('#sortLab').textContent+document.querySelector('#sortDir').textContent+
        ' · 菜单已收起 '+(document.querySelector('#sortMenu').classList.contains('on')?'否':'是'));
      out.push('状态条：'+document.querySelector('#sbar').textContent.replace(/\s+/g,' ').trim());
      out.push('JS 错误：'+(__errs.length?__errs.join(';'):'无'));
      try{ fetch('/diag',{method:'POST',body:out.join('\n')}); }catch(e){}
    },600);
  }catch(e){ out.push('筛选/排序检查异常 '+e.message); try{ fetch('/diag',{method:'POST',body:out.join('\n')}); }catch(e2){} }
},3200);
</script>
</body>"""

LIST = r"""
<script>
setTimeout(function(){
  document.querySelector('[data-v=list]').click();
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
      var pans=document.querySelectorAll('.pane');
      var vw=innerWidth, vh=innerHeight;
      function skew(el){ return getComputedStyle(el.querySelector('.pane-in')).transform; }
      var ov=document.querySelector('#ov'), ovp=document.querySelector('#ovp');
      function R(e){ var r=e.getBoundingClientRect();
        return Math.round(r.left)+','+Math.round(r.top)+' '+Math.round(r.width)+'×'+Math.round(r.height); }
      o.push('总览层 '+(ov.classList.contains('on')?'打开':'关闭')+' · 面板 '+R(ovp)+
        ' · 占屏 '+(ovp.getBoundingClientRect().width/vw*100).toFixed(1)+'% × '+
        (ovp.getBoundingClientRect().height/vh*100).toFixed(1)+'%');
      var pr=ovp.getBoundingClientRect();
      o.push('面板居中：左 '+Math.round(pr.left)+' 右 '+Math.round(vw-pr.right)+
        ' 上 '+Math.round(pr.top)+' 下 '+Math.round(vh-pr.bottom)+
        ((Math.abs(pr.left-(vw-pr.right))<2 && Math.abs(pr.top-(vh-pr.bottom))<2)?'（对称）':'（不对称）'));
      o.push('canvas '+(cv?Math.round(cv.getBoundingClientRect().width)+'×'+Math.round(cv.getBoundingClientRect().height):'未创建'));
      o.push('信息板 '+pans.length+' 块 / 各 '+[].map.call(pans,function(p){
        return (p.getBoundingClientRect().width/vw*100).toFixed(1)+'%'}).join(',')+
        ' · 斜切左 '+(pans.length?skew(pans[0]).slice(0,34):'-')+'…');
      var ths=document.querySelectorAll('#texbar .tb-th');
      o.push('贴图排 '+(document.querySelector('#texbar').classList.contains('on')?'显示':'隐藏')+
        ' · 缩略图 '+ths.length+' · 原始材质钮 '+document.querySelectorAll('#texbar .tb-chip').length+
        ' · 平铺档 '+[].map.call(document.querySelectorAll('#texbar [data-tile]'),function(b){return b.textContent}).join('')+
        ' · 亮度滑杆 '+(document.querySelector('#tbBright')?'有':'无'));
      o.push('默认覆盖 '+TEX.path+' / 高亮项 '+document.querySelectorAll('#texbar .tb-th.on').length);
      if(ths.length>1){
        ths[1].click();
        o.push('点第 2 张贴图后 TEX.path='+TEX.path.split('/').pop()+
          ' / 高亮项 '+document.querySelectorAll('#texbar .tb-th.on').length);
      }
      document.querySelector('#texbar .tb-chip').click();
      o.push('点「原始材质」后 TEX.path='+TEX.path+' / 高亮 chip '+document.querySelectorAll('#texbar .tb-chip.on').length);
      var tile2=document.querySelectorAll('#texbar [data-tile]')[1];
      if(tile2){ tile2.click(); o.push('点平铺 ×2 后 TEX.tile='+TEX.tile); }
      o.push('HUD '+[].map.call(document.querySelectorAll('#shhud .vbtn'),function(b){return b.textContent}).join(' / '));
      o.push('状态行 '+document.querySelector('#shstat').textContent);
      o.push('左板字段 '+['显示名','文件名','资源原名','所属目录','相对目录','完整路径','贴图','来源']
        .filter(function(t){ return pans[0].textContent.indexOf(t)>=0; }).join(' / '));
      o.push('右板字段 '+['顶点','三角面','包围盒 X','最长边','面/顶点比','文件大小','同游戏','同名族','共用首张贴图','标记','入库序号','缩略图']
        .filter(function(t){ return pans[1].textContent.indexOf(t)>=0; }).join(' / '));
      o.push('右板正文 '+pans[1].textContent.replace(/\s+/g,' ').trim().slice(0,150));
      // 把包围盒 8 角投到屏幕，直接判定模型有没有被裁切／被 UI 压住
      try{
        if(typeof MESH !== 'undefined' && MESH && typeof CAM !== 'undefined' && CAM){
          var bb=new THREE.Box3().setFromObject(MESH);
          var r=cv.getBoundingClientRect(), band=safeBand();
          var minX=1e9,maxX=-1e9,minY=1e9,maxY=-1e9,back=0;
          [[0,0,0],[1,0,0],[0,1,0],[0,0,1],[1,1,0],[1,0,1],[0,1,1],[1,1,1]].forEach(function(k){
            var p=new THREE.Vector3(bb.min.x+(bb.max.x-bb.min.x)*k[0],
                                    bb.min.y+(bb.max.y-bb.min.y)*k[1],
                                    bb.min.z+(bb.max.z-bb.min.z)*k[2]).project(CAM);
            if(Math.abs(p.z)>1) back++;
            var x=(p.x*.5+.5)*r.width, y=(-p.y*.5+.5)*r.height;
            minX=Math.min(minX,x); maxX=Math.max(maxX,x);
            minY=Math.min(minY,y); maxY=Math.max(maxY,y);
          });
          o.push('模型投影 x '+Math.round(minX)+'~'+Math.round(maxX)+' / y '+Math.round(minY)+'~'+Math.round(maxY)+
                 '（画布 '+Math.round(r.width)+'×'+Math.round(r.height)+'）· 相机距离 '+
                 CAM.position.distanceTo(CT.target).toFixed(0)+' · 远角超界 '+back);
          o.push('安全区 y '+Math.round(band.top)+'~'+Math.round(band.top+band.heff));
          var over=(minX<11||maxX>band.w-11||minY<band.top-1||maxY>band.top+band.heff+1);
          o.push('是否超出安全区：'+(over?'是 ← 有裁切':'否，完整落在安全区内')+
                 ' · 占画布 '+(100*(maxY-minY)/r.height).toFixed(0)+'% 高 / '+(100*(maxX-minX)/r.width).toFixed(0)+'% 宽');
        } else { o.push('投影检查跳过：MESH/CAM 不可见'); }
      }catch(e){ o.push('投影检查异常 '+e.message); }
      o.push('JS 错误 '+(window.__errs&&window.__errs.length?window.__errs.join(';'):'无'));
      try{ fetch('/diag',{method:'POST',body:o.join('\n')}); }catch(e){}
    },7000);
  },500);
},3200);
</script>
</body>"""


def warm(prof):
    """全新 profile 直接跑 --headless=new 会静默不出结果（首启初始化吃掉虚拟时间预算），
    先空跑一次捂热；已存在的 profile 直接跳过。"""
    if os.path.isdir(prof):
        return
    subprocess.run([EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
                    '--user-data-dir=' + prof, '--window-size=800,600',
                    '--virtual-time-budget=3000', 'about:blank'],
                   capture_output=True, timeout=180)


def run(name, probe, budget, shot=None):
    with open(os.path.join(ROOT, 'index.html'), encoding='utf-8') as fh:
        src = fh.read()
    src = src.replace('</body>', probe, 1)
    tmp = os.path.join(ROOT, '_t.html')
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(src)
    prof = os.path.join(TEMP, '_vh_' + name)          # 保留 profile，不要删
    warm(prof)
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


def regions(path, kind='page'):
    """分区暗像素数。
    用「绝对暗像素数」而不是「墨迹率」——信息板内容只占上半截，
    按全高算比率会被下半截留白稀释成假空白（这个坑踩过）。
    kind='page' 看书目页（轨道 / 头部 / 筛选条 / 内容 / 状态条）；
    kind='ov'   看详情总览面板（遮罩 / 左板 / 中间 3D / 右板 / 顶条）。"""
    with Image.open(path) as raw:
        rgb = np.asarray(raw.convert('RGB'), dtype=np.int16)
    h, w = rgb.shape[:2]
    kb_size = os.path.getsize(path) / 1024

    def dark(x0, y0, x1, y1):
        blk = rgb[max(0, y0):y1, max(0, x0):x1]
        return int((blk < 200).any(axis=2).sum()) if blk.size else 0

    def avg(x0, y0, x1, y1):
        blk = rgb[max(0, y0):y1, max(0, x0):x1]
        if blk.size == 0:
            return (0, 0, 0)
        m = blk.reshape(-1, 3).mean(axis=0)
        return (int(m[0]), int(m[1]), int(m[2]))

    head = '尺寸 %d×%d  %.0f KB\n' % (w, h, kb_size)
    if kind == 'ov':
        # 总览面板占 4%~96%：左板 4~24%、中间 24~76%、右板 76~96%
        return head + (
            '   遮罩(0-4%%)        暗像素 %6d  均色 %s\n'
            '   左信息板(5-23%%)   暗像素 %6d  均色 %s\n'
            '   中间 3D(26-74%%)   暗像素 %6d\n'
            '   右信息板(77-95%%)  暗像素 %6d  均色 %s'
        ) % (
            dark(0, 0, int(w * .04), h), avg(2, int(h * .3), int(w * .03), int(h * .7)),
            dark(int(w * .05), int(h * .06), int(w * .23), int(h * .96)),
            avg(int(w * .06), int(h * .08), int(w * .22), int(h * .3)),
            dark(int(w * .26), int(h * .12), int(w * .74), int(h * .96)),
            dark(int(w * .77), int(h * .06), int(w * .95), int(h * .96)),
            avg(int(w * .78), int(h * .08), int(w * .94), int(h * .3)))
    return head + (
        '   左轨道(0-48)      暗像素 %6d\n'
        '   头部(0-52)        暗像素 %6d\n'
        '   内容区            暗像素 %6d\n'
        '   状态条(底 24)     暗像素 %6d'
    ) % (
        dark(0, 60, 46, h - 30),
        dark(0, 0, w, 52),
        dark(60, 60, w - 10, h - 30),
        dark(0, h - 24, w, h))


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
for f, label, kind in [('1-grid.png', '网格视图', 'page'), ('2-list.png', '列表视图', 'page'),
                       ('3-viewer.png', '详情总览', 'ov')]:
    p = os.path.join(SHOT, f)
    print('── %s ──' % label)
    print(regions(p, kind) if os.path.exists(p) else '   截图缺失')
print()
print(ascii_map(os.path.join(SHOT, '1-grid.png')))
print()
print(ascii_map(os.path.join(SHOT, '2-list.png')))
