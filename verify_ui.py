#!/usr/bin/env python
"""真实浏览器自检：
   · 页面把诊断结果 POST 到 /diag → 落盘 _diag.txt
   · 每个探针截图，并用像素分析 + ASCII 版面缩略图核实分区
关键：profile 目录要保留、必须带 --no-first-run，否则 Edge 停在首启页出白图。

用法：
  python verify_ui.py                              # 完整跑（需本地服务在 8800）
  python verify_ui.py --route                      # 只跑命令路由点击链路
  python verify_ui.py --page _site/index.html --base http://localhost:8801 \
                      --diag _site/_diag.txt       # 直接验 CD 产物（Pages 上线前先本地过一遍）
"""
import argparse
import contextlib
import os
import subprocess
import sys
import time

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMP = os.environ.get('TEMP') or r"C:\Windows\Temp"

# 浏览器可执行文件：本机是 Edge，Linux runner 上通常是 Google Chrome。
# 用 VERIFY_BROWSER 环境变量可以覆盖，省得为了换个浏览器改代码。
BROWSER_CANDIDATES = [
    os.environ.get('VERIFY_BROWSER', ''),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
]


def pick_browser() -> str:
    for p in BROWSER_CANDIDATES:
        if p and os.path.isfile(p):
            return p
    return BROWSER_CANDIDATES[1]


EDGE = pick_browser()


def _parse_args():
    ap = argparse.ArgumentParser(description='真实浏览器界面自检')
    ap.add_argument('--page', default='index.html', help='被测页面（相对本目录或绝对路径）')
    ap.add_argument('--base', default='http://localhost:8800', help='静态服务地址')
    ap.add_argument('--diag', default='_diag.txt',
                    help='诊断回传落盘位置，必须与服务根目录一致')
    ap.add_argument('--shots', default='_shots',
                    help='截图输出目录（反复跑时换个空目录可避免清理旧图）')
    ap.add_argument('--route', action='store_true', help='只跑命令路由点击链路测试')
    return ap.parse_args()


ARGS = _parse_args()
PAGE = ARGS.page if os.path.isabs(ARGS.page) else os.path.join(ROOT, ARGS.page)
PAGEDIR = os.path.dirname(PAGE)
BASE = ARGS.base.rstrip('/')
DIAG = ARGS.diag if os.path.isabs(ARGS.diag) else os.path.join(ROOT, ARGS.diag)
SHOT = ARGS.shots if os.path.isabs(ARGS.shots) else os.path.join(ROOT, ARGS.shots)

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
  // 图标名写错时 SVGICON 返回空串 ⇒ 占位 span 被清空，一个 <use> 都不产生，
  // 上面那条「use 失效」检查抓不到这类静默消失，必须单独查
  var holes=[];
  document.querySelectorAll('[data-i]').forEach(function(e){
    if(!e.querySelector('svg')) holes.push(e.dataset.i+'@'+(e.parentNode.className||e.parentNode.tagName));
  });
  out.push('图标占位 '+document.querySelectorAll('[data-i]').length+' 个 · 画成空的 '+holes.length+
    (holes.length?' → '+holes.slice(0,6).join(','):''));
  // 会影响文字清晰度的样式（合成层/重采样源头）
  var bad=[];
  ['.ov','.ovp','.pane-l','.pane-r'].forEach(function(sel){
    var e=document.querySelector(sel); if(!e) return;
    var c=getComputedStyle(e);
    if(c.backdropFilter && c.backdropFilter!=='none') bad.push(sel+' backdrop-filter');
    if(c.willChange && c.willChange!=='auto') bad.push(sel+' will-change='+c.willChange);
    if(c.filter && c.filter!=='none') bad.push(sel+' filter');
  });
  // 斜切必须用 clip-path 做外形，不能真 3D 旋转 —— 实测 rotateY 把文字锐度砍到 35%
  // 外形现在由装饰层 .pane-bg 承载（.pane 负责裁切、.pane-in 只放文字），所以查 .pane-bg
  var rolled=[];
  ['.pane-l .pane-in','.pane-r .pane-in'].forEach(function(sel){
    var e=document.querySelector(sel); if(!e) return;
    if(getComputedStyle(e).transform!=='none') rolled.push(sel);
  });
  var clipped=['.pane-l','.pane-r'].filter(function(sel){
    var e=document.querySelector(sel);
    return e && getComputedStyle(e).clipPath!=='none';
  });
  var tiltNote = rolled.length ? ('真 3D 旋转 ← 文字会糊 ' + rolled.join(','))
                               : ('clip-path 外形 ' + clipped.length + '/2 块，文字 1:1');
  var anim=getComputedStyle(document.querySelector('.ovp')).animationName;
  var kf=(function(){
    for(var i=0;i<document.styleSheets.length;i++){
      var rs; try{ rs=document.styleSheets[i].cssRules; }catch(e){ continue; }
      for(var j=0;j<rs.length;j++){ if(rs[j].type===7 && rs[j].name===anim) return rs[j].cssText; }
    }
    return '';
  })();
  out.push('清晰度隐患：'+(bad.length?bad.join(' / '):'无')+
    ' · 斜切实现 '+tiltNote+
    ' · 入场动画 ['+anim+'] '+(/scale/.test(kf)?'含 scale ← 会整体重采样':'只动 opacity'));
  // 头部控件绝对不许藏（曾经用媒体查询 display:none 静默消失）
  var hidden=[];
  ['#dens','#btnDup','#btnStats','.sbox','#view','#btnSort','#th'].forEach(function(sel){
    var e=document.querySelector(sel);
    if(!e) { hidden.push(sel+' 不存在'); return; }
    var c=getComputedStyle(e), r=e.getBoundingClientRect();
    if(c.display==='none') hidden.push(sel+' display:none');
    else if(r.width<1) hidden.push(sel+' 宽度 0');
    else if(c.visibility==='hidden') hidden.push(sel+' visibility');
  });
  var topEl=document.querySelector('.top');
  out.push('头部控件 '+7+' 项 · 被隐藏 '+hidden.length+(hidden.length?' → '+hidden.join(','):'')+
    ' · 头部 scrollW '+topEl.scrollWidth+' clientW '+topEl.clientWidth+
    (topEl.scrollWidth>topEl.clientWidth+1?'（可横向滚动，控件没丢）':''));
  out.push('头部：'+[].map.call(document.querySelectorAll('.top .seg button,.top .tbtn,.top .ib'),
    function(b){return b.textContent.trim()||b.title}).join(' / '));
  out.push('没有排序条（.mbar 应为 0）：'+document.querySelectorAll('.mbar').length+
    ' · 排序菜单项 '+document.querySelectorAll('#sortMenu [data-s]').length);
  out.push('没有右侧停靠栏（.dock 应为 0）：'+document.querySelectorAll('.dock').length);
  out.push('轨道按钮 '+document.querySelectorAll('.rbtn').length+' 个');
  var cds=document.querySelectorAll('.cd');
  var ok=[].filter.call(document.querySelectorAll('.cd .th>img'),function(i){return i.naturalWidth>0;});
  out.push('卡片 '+cds.length+' 个，缩略图解码 '+ok.length+' 张');
  // 无缩略图的卡片必须是「说得清的状态」，不能是一片空白
  var ni=0, niBad=[];
  document.querySelectorAll('.cd.noimg').forEach(function(c){
    ni++;
    var t=c.querySelector('.ph .tx');
    if(!t || !t.textContent.trim()) niBad.push(c.querySelector('.nm')?c.querySelector('.nm').textContent:'?');
  });
  out.push('「无缩略图 / 空模型」占位卡片 '+ni+' 张 · 标签为空的 '+niBad.length+
    (niBad.length?' → '+niBad.join(','):'')+' · 判定为空模型 '+document.querySelectorAll('.cd.blank-model').length+
    ' 张 · 加载中 '+document.querySelectorAll('.cd.loading').length+' 张');
  if(cds[0]) out.push('卡片文本：'+cds[0].textContent.replace(/\s+/g,' ').trim());
  /* 两条几何判据。它们各自对应一个真实踩过的坑，而且都是「看起来正常、量出来不对」那类：
     ① 缩略图被裁：.th 的高度按 CARD_W 算（141），但网格列被 1fr 拉到 218，
        img 按固有比例要 155.7 —— 被 overflow:hidden 裁掉底部 15px，下顶点整片切掉；
     ② 行距不一致：卡片真实高 258.84 而 unit 算 255，三万多条滚到后面累计漂移上万像素，
        滚动窗口与内容错位（演示库里只有十几行，看不出来；真实库才会炸）。 */
  var vis=[].slice.call(document.querySelectorAll('.cd')).filter(function(e){return e.style.display!=='none';});
  if(vis[0]){
    var t0=vis[0].querySelector('.th'), i0=t0&&t0.querySelector('.th>img');
    if(i0 && i0.getBoundingClientRect().height>1){
      var tb=t0.getBoundingClientRect(), ib=i0.getBoundingClientRect();
      var over=ib.bottom-tb.bottom;
      out.push('缩略图裁切：.th 底 '+Math.round(tb.bottom)+' · img 底 '+Math.round(ib.bottom)+
        ' · 溢出 '+over.toFixed(1)+'px '+((over>1)?'← 底部被裁':'✓ 完整'));
    }
    var pr=perRow();
    if(vis.length>pr && S.view.length>pr){
      var pitch=vis[pr].getBoundingClientRect().top-vis[0].getBoundingClientRect().top;
      var per=$('spacer').clientHeight/Math.ceil(S.view.length/pr);
      out.push('虚拟滚动几何：实测行距 '+pitch.toFixed(2)+'px · spacer 推算 '+per.toFixed(2)+
        'px · 差 '+Math.abs(pitch-per).toFixed(2)+
        ((Math.abs(pitch-per)>0.6)?' ← 不一致，滚远会漂移':' ✓ 一致'));
    }
  }
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
      // 斜切是 clip-path 做在装饰层 .pane-bg 上，文字层 .pane-in 必须保持无变换（否则会重采样变糊）
      function skew(el){
        var t=el.querySelector('.pane-in');
        return 'clip='+getComputedStyle(el).clipPath.replace(/px/g,'')+
               ' / 文字层 transform='+getComputedStyle(t||el).transform;
      }
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
        ' · 平铺档 '+[].map.call(document.querySelectorAll('#texbar [data-act^="tile:"]'),function(b){return b.textContent}).join('')+
        ' · 亮度滑杆 '+(document.querySelector('#tbBright')?'有':'无'));
      o.push('默认覆盖 '+TEX.path+' / 高亮项 '+document.querySelectorAll('#texbar .tb-th.on').length);
      if(ths.length>1){
        ths[1].click();
        o.push('点第 2 张贴图后 TEX.path='+TEX.path.split('/').pop()+
          ' / 高亮项 '+document.querySelectorAll('#texbar .tb-th.on').length);
      }
      document.querySelector('#texbar .tb-chip').click();
      o.push('点「原始材质」后 TEX.path='+TEX.path+' / 高亮 chip '+document.querySelectorAll('#texbar .tb-chip.on').length);
      var tile2=document.querySelectorAll('#texbar [data-act^="tile:"]')[1];
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


# ── 命令路由探针：把「点击 → 命令 → 能力」这条链路真的走一遍 ──────────────
# 判据刻意分两层：
#   ① 派发层 —— 点击确实到达了 ACTIONS 里对应的那个命令（用包装器记录，与具体能力无关）
#   ② 能力层 —— 状态类命令必须留下可验证的后果（筛选生效 / 面板收起 / 换到另一个模型）
# 只测 ① 会漏掉「命令名写对、函数体是空的」；只测 ② 会漏掉「绕开路由直接改状态」。
# 另外还有一层静态判据：页面上每个 data-act 的命令名都必须真的存在于 ACTIONS ——
# 命令名打错时点击会静默无反应，这是这一类设计里最难查的坏法。
ROUTE = r"""
<script>
window.__errs=[]; window.onerror=function(m,s,l){__errs.push(m+'@'+l);};
setTimeout(function(){
  var L=[], BAD=[];
  var ok=function(c,m){ L.push((c?'  ✓ ':'  ✗ ')+m); if(!c) BAD.push(m); };
  var sleep=function(ms){ return new Promise(function(r){ setTimeout(r,ms); }); };
  var wait=async function(f,ms,tag){ var t0=Date.now();
    while(!f()){ if(Date.now()-t0>ms) throw new Error('等待超时 '+tag); await sleep(80); } };
  var vis=function(sel){ return [].slice.call(document.querySelectorAll(sel))
    .filter(function(e){ return e.getBoundingClientRect().width>0; }); };
  var cmdOf=function(e){ return String(e.dataset.act).split(':')[0]; };
  /* 参数一律从 data-act 里读、URL 解码 —— 页面侧同理（index.html 的 actArg）。
     曾经验证脚本自己另存了一份 data-t 来比对，属性一改名就整片误判。 */
  var actArg=function(e){ var r=String(e.dataset.act||''), i=r.indexOf(':');
    return i<0?'':decodeURIComponent(r.slice(i+1)); };
  var unknownCmd=function(root){
    var bad={}, n=0;
    [].forEach.call((root||document).querySelectorAll('[data-act]'), function(e){
      n++; var c=cmdOf(e); if(!(c in ACTIONS)) bad[c]=String(e.dataset.act).slice(0,48);
    });
    return {n:n, bad:bad};
  };
  (async function(){
    try{
      /* 注意：index.html 里 S / ACTIONS / MESH / R3 都是顶层 const|let，
         它们进的是全局**词法**环境，不挂到 window 上 —— 所以只能写裸名，
         想判存在性要用 typeof（`window.S` 恒为 undefined，这个坑探针里踩过一次）。 */
      await wait(function(){ return typeof S!=='undefined' && S.items && S.items.length>0; },
                 25000, '目录载入');
      await wait(function(){ return vis('.cd,.lrow').length>0; }, 12000, '卡片渲染');
      L.push('  目录 '+S.items.length+' 条 · 屏上卡片 '+vis('.cd,.lrow').length+' 张');

      /* 挂派发记录：包装 ACTIONS 而不改任何调用点 */
      var seen=[];
      Object.keys(ACTIONS).forEach(function(k){
        var f=ACTIONS[k];
        ACTIONS[k]=function(){ seen.push(k); return f.apply(ACTIONS, arguments); };
      });
      var fired=function(k){ return seen.indexOf(k)>=0; };
      var reset=function(){ seen.length=0; };
      var clearAll=function(){
        var b=document.querySelector('#fbar .clr'); if(b) b.click();
        S.f={game:null,kind:null,fac:null}; S.tag=null; S.q=''; document.getElementById('q').value='';
        recount(); apply();
      };

      /* ① 点卡片 → 详情面板 */
      vis('.cd,.lrow')[0].click();
      await wait(function(){ return document.getElementById('ov').classList.contains('on'); }, 10000, '详情面板');
      ok(!!S.cur, '点卡片 → 详情面板打开（当前 #'+(S.cur?S.cur.id:'-')+'）');

      /* ② 命令名全覆盖：此刻页面上能点的组件最多（筛选条 + 两个信息板 + 顶部操作），
             逐个核对 data-act 的命令名真的存在于 ACTIONS。命令名写错时点击会**静默无反应**，
             这是这类设计里最难查的坏法，所以放在这里当静态判据。
             判据必须要求「至少扫到 N 个」—— 扫到 0 个时「全部合法」是空真，不算通过。 */
      var u0=unknownCmd();
      ok(u0.n>=8 && Object.keys(u0.bad).length===0,
         '面板展开时全页 '+u0.n+' 个可点组件，命令名全部存在于 ACTIONS'+
         (Object.keys(u0.bad).length?'　← 非法: '+JSON.stringify(u0.bad):''));

      /* ③ 面板里的命令区：条数**刻意克制**，且每条命令名合法、需要后端的带了 local 标记。
             「信息对象 → 可点组件 → 命令 → 能力」不是把每个字段都做成按钮 ——
             所以这里同时盯上限：命令区超过 6 条就说明又开始铺按钮了。 */
      var u1=unknownCmd(document.querySelector('.js-cmd')||document);
      var cb=document.querySelectorAll('.js-cmd .cbtn');
      var loc=document.querySelectorAll('.js-cmd .cbtn.local');
      ok(cb.length>=4 && cb.length<=6,
         '命令区 '+cb.length+' 条命令（刻意的克制区间 4~6 条，不是把字段铺满）');
      ok(u1.n>=4 && Object.keys(u1.bad).length===0,
         '命令区 '+u1.n+' 个命令名全部合法'+(Object.keys(u1.bad).length?'　← '+JSON.stringify(u1.bad):''));
      ok(loc.length>=2, '其中 '+loc.length+' 个标注了「需要本地服务」（能力边界提前说明）');

      /* ③ 分类 chip → filter：命令被派发 + 面板收起 + 结果真的变了 */
      var before=S.view.length;
      var chipKind=document.querySelector('.js-kind .chip.act');
      if(chipKind){
        reset(); chipKind.click(); await sleep(350);
        ok(fired('filter'), '点分类 chip「'+chipKind.textContent.trim()+'」→ filter 被派发');
        ok(!document.getElementById('ov').classList.contains('on'), '执行后详情面板自动收起');
        ok(S.view.length!==before, '筛选有真实后果：结果 '+before+' → '+S.view.length+' 条');
      } else { ok(false, '找不到 .js-kind .chip.act'); }

      /* ④ 标记 chip → filter:tag */
      clearAll();
      vis('.cd,.lrow')[0].click();
      await wait(function(){ return document.getElementById('ov').classList.contains('on'); }, 10000, '详情面板2');
      var chipTag=document.querySelector('.js-tags .chip.act');
      if(chipTag){
        var n0=S.view.length; reset(); chipTag.click(); await sleep(350);
        ok(fired('filter') && !!S.tag,
           '点标记 chip → filter:tag 生效（tag='+S.tag+'，结果 '+n0+' → '+S.view.length+' 条）');
      } else { ok(false, '找不到 .js-tags .chip.act'); }

      /* ⑤ 关联「同名族 / 共用首张贴图」→ goto：必须真的换到另一个模型 */
      clearAll();
      var jumped=false;
      for(var attempt=0; attempt<6 && !jumped; attempt++){
        var cards=vis('.cd,.lrow'); if(!cards[attempt]) break;
        cards[attempt].click();
        await wait(function(){ return document.getElementById('ov').classList.contains('on'); }, 8000, '详情面板3');
        var g=document.querySelector('.js-rel [data-act^="goto:"]');
        if(!g) continue;
        var id0=S.cur.id; reset(); g.click();
        await sleep(400);
        if(fired('goto') && S.cur && S.cur.id!==id0){
          jumped=true;
          ok(true, '点关联「'+g.parentNode.querySelector('.k').textContent.trim()+
                   '」→ goto 跳到 #'+id0+' → #'+S.cur.id);
        }
      }
      if(!jumped) ok(false, '关联里的 goto 没有换到别的模型');

      /* ⑥ 缩略图相关：「索引」是记录级信息、不该重复摆一张和中间 3D 一样的图；
             「标识」区才给缩略图的**文件路径**。 */
      clearAll();
      vis('.cd,.lrow')[0].click();
      await wait(function(){ return document.getElementById('ov').classList.contains('on'); }, 8000, '详情面板4');
      var idxBox=document.querySelector('.js-idx');
      ok(idxBox && !idxBox.querySelector('img'),
         '索引区没有重复摆缩略图（那边只回答「这条在第几位」）');
      var thumbRow=[].slice.call(document.querySelectorAll('.js-ident .r')).filter(function(r){
        return (r.querySelector('.k')||{}).textContent === '缩略图'; });
      ok(thumbRow.length===1 && /_thumbs\//.test(thumbRow[0].textContent),
         '标识区给出缩略图的真实文件路径「'+(thumbRow.length?thumbRow[0].textContent.trim():'缺')+'」');
      ok(!/内联|演示缩略图|_res\/|data:image/.test(document.getElementById('ov').textContent||''),
         '界面文案里没有把打包/实现细节写给用户看');

      /* ⑥b 贴图覆盖：tex 命令的「能力层」判据 —— 不只是命令被派发，
             而是纹理真的换了一茬（TEX.path 变了、TEX.tex 非空）。
             优先找有两张贴图的模型（这样能验证「换」这个动作），找不到就退而验单张。 */
      clearAll();
      var tex2=false, tex1=false;
      for(var t=0; t<20 && !tex2; t++){
        var cs=vis('.cd,.lrow'); if(!cs[t]) break;
        cs[t].click();
        await wait(function(){ return document.getElementById('ov').classList.contains('on'); }, 8000, '详情面板T');
        var ths=[].slice.call(document.querySelectorAll('#texbar .tb-th')).filter(function(b){
          return !b.classList.contains('miss'); });
        if(!ths.length) continue;

        if(ths.length>=2){
          var p0=TEX.path;
          reset(); ths[1].click(); await sleep(700);
          ok(fired('tex') && actArg(ths[1])===TEX.path && TEX.path!==p0,
             '点第 2 张贴图缩略图 → tex 覆盖：'+String(p0).split('/').pop()+' → '+
             String(TEX.path).split('/').pop());
          ok(!!TEX.tex, '贴图纹理真的挂进了材质（TEX.tex 非空）');
          tex2=true;
        } else if(!tex1){
          reset(); ths[0].click(); await sleep(700);
          ok(fired('tex') && actArg(ths[0])===TEX.path,
             '点贴图缩略图 → tex 覆盖：'+String(TEX.path).split('/').pop()+'（该模型只有 1 张）');
          tex1=true;
        }
      }
      if(!tex1 && !tex2) ok(false, '20 个模型里都没找到一张可点的贴图');
      else if(!tex2) L.push('  ○ 前 20 个模型都没有第 2 张贴图，本次只走了「单张覆盖」这条路径');

      /* ⑥c 平铺档：tile 命令必须真的改到 TEX.tile（贴图排此前绕开路由自己绑事件，已被这次自检抓出） */
      if(document.getElementById('ov').classList.contains('on')){
        var t2=document.querySelectorAll('#texbar [data-act^="tile:"]')[1];
        if(t2){
          reset(); t2.click(); await sleep(300);
          ok(fired('tile') && TEX.tile===+String(t2.dataset.act).slice(5),
             '点平铺档「'+t2.textContent+'」→ tile 命令生效，TEX.tile='+TEX.tile);
        } else { ok(false, '贴图排里没有平铺档按钮'); }
      } else { L.push('  ○ 贴图排未打开，平铺档未验'); }

      /* ⑦ 3D：真的加载出网格才算这条链路的终点成立。
             但要区分「环境没有 WebGL」与「页面真的加载不出模型」——前者是运行环境的能力
             边界，判成失败会让整套自检在无 GPU 的 CI 上永远红；后者才是真 bug。 */
      clearAll();
      vis('.cd,.lrow')[0].click();
      await wait(function(){ return document.getElementById('ov').classList.contains('on'); }, 10000, '详情面板5');
      try{
        await wait(function(){ return typeof MESH!=='undefined' && !!MESH; }, 15000, '3D 网格');
        var st=document.getElementById('shstat').textContent||'';
        ok(true, '3D 预览加载出网格：'+st.slice(0,70));
      }catch(e){
        if(typeof R3!=='undefined' && R3){ ok(false, '3D 渲染器已建立，但网格没加载出来（'+S.cur.p+'）'); }
        else { L.push('  ○ 本环境拿不到 WebGL 上下文，3D 预览无法判定（不计入通过/失败）'); }
      }

      /* ⑧ 图标健康度：命令区的图标必须真的画出来 */
      var holes=[], nIcon=0;
      [].forEach.call(document.querySelectorAll('[data-i]'), function(e){
        nIcon++; if(!e.querySelector('svg')) holes.push(e.dataset.i);
      });
      ok(nIcon>=20 && holes.length===0, '全页 '+nIcon+' 个图标占位全部画成实心符号'+
         (holes.length?'　← 空: '+holes.slice(0,8).join(','):''));
      /* ⑨ 注入自测：目录里的文件名 / 路径 / 分组名**来自磁盘，可以是任意的**。
             一个叫 `<img src=x onerror=…>.obj` 的文件既能把界面拼坏，也是一条注入路径。
             所以这里现场喂一个恶意条目，断言它只作为**文本**出现：
             不新增元素、不触发任何脚本，而且确实看得见（说明是转义而不是被丢掉）。 */
      window.__inj = 0;
      clearAll();
      var it0 = S.view[0];
      var evil = {
        dn: '<img src=x onerror="window.__inj=1">',
        n:  '<b>n</b>',
        rn: '<svg onload="window.__inj=2">',
        c:  '<script>window.__inj=3<\/script>',
        f:  '<b>grp</b>',
        p:  'models/" onmouseover="window.__inj=4'
      };
      var keep = {};
      Object.keys(evil).forEach(function(k){ keep[k] = it0[k]; it0[k] = evil[k]; });
      it0.tl = ['<img src=x onerror="window.__inj=5">.png']; it0.tn = 1; it0.tr = ['diffuse'];
      it0.dn0 = it0.dn;
      open(0);
      await wait(function(){ return document.getElementById('ov').classList.contains('on'); }, 8000, '注入测试面板');
      await sleep(400);
      var probeSel = '.js-ident img, .js-ident b, .js-ident svg, .js-ident script,' +
                     '#texbar img[src^="<"], .tw img[src^="<"]';
      var injected = document.querySelectorAll(probeSel).length;
      var identText = (document.querySelector('.js-ident')||{}).textContent || '';
      ok(window.__inj === 0 && injected === 0,
         '注入自测：恶意文件名没有被当成 HTML（触发脚本 '+window.__inj+' 次 · 新增元素 '+injected+' 个）');
      ok(identText.indexOf('<img') >= 0 && identText.indexOf('onerror') >= 0,
         '注入自测：恶意名字确实以**文本**显示出来了（不是被静默丢掉）');
      Object.keys(keep).forEach(function(k){ it0[k] = keep[k]; });

    }catch(e){
      ok(false, '探针异常：'+(e && e.message || e));
    }
    L.push('  JS 错误 '+(window.__errs && window.__errs.length ? window.__errs.join(';') : '无'));
    L.push('');
    L.push(BAD.length ? ('路由自检：'+BAD.length+' 项未过') : '路由自检：全部通过');
    try{ fetch('/diag',{method:'POST',body:L.join('\n')}); }catch(e){}
  })();
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
    with open(PAGE, encoding='utf-8') as fh:
        src = fh.read()
    src = src.replace('</body>', probe, 1)
    # 注入后的临时页必须落在**被服务的那棵树下**，否则相对路径（_res/、models/）全断
    tmp = os.path.join(PAGEDIR, '_t.html')
    with open(tmp, 'w', encoding='utf-8') as fh:
        fh.write(src)
    prof = os.path.join(TEMP, '_vh_' + name)          # 保留 profile，不要删
    warm(prof)
    cmd = [EDGE, '--headless=new', '--disable-gpu', '--no-sandbox', '--no-first-run',
           '--disable-extensions', '--hide-scrollbars', '--enable-unsafe-swiftshader',
           '--user-data-dir=' + prof, '--window-size=1680,1000',
           # 「截图抓到早帧」的解药。无头 + --virtual-time-budget 下，虚拟时间里跑完的
           # 动画/WebGL 取景未必被合成器画出来，--screenshot 于是可能拿到「总览层刚打开、
           # 还在 opacity 淡入」的那一帧 —— 实测同一页面状态连拍 4 张出过 3 种画面
           # （最大差 67 万像素），其中一张的面板半透明、3D 没取景，
           # 看起来就像「信息板透光」的真 bug。
           # 只加这一个开关就够，别再加 --disable-new-content-rendering-timeout：
           # 它会把「内容已稳定」的计时器一起关掉，页面只要还有持续动画就永远不返回，
           # 实测直接把自检挂死在 300s 超时上。
           '--run-all-compositor-stages-before-draw',
           '--virtual-time-budget=%d' % budget]
    if shot:
        cmd.append('--screenshot=' + shot)
    cmd.append(BASE + '/_t.html')
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=180, errors='replace')
    except subprocess.TimeoutExpired as exc:
        # 单张截图挂死不该把整轮自检带走：报出来、继续跑后面的探针
        with contextlib.suppress(OSError): os.remove(tmp)
        raise SystemExit('浏览器在探针「%s」上超时（180s）—— 多半是页面里有永不停止的动画，'
                         '或 --virtual-time-budget 没能在预算内让页面静止。%s' % (name, exc)) from exc
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
# 只清旧的截图，不要把子目录也一起 os.remove 掉 —— 那会抛 PermissionError
# 把整个自检在第 592 行炸掉（真发生过：手工裁图的 _shots/crop/ 撞出这个错）
for _f in os.listdir(SHOT):
    _p = os.path.join(SHOT, _f)
    if os.path.isfile(_p):
        os.remove(_p)

if ARGS.route:
    print('══ 命令路由点击链路（信息对象 → UI 组件 → 点击 → 命令 → 能力）══')
    print('   被测页面 %s  ·  服务 %s' % (os.path.relpath(PAGE, ROOT), BASE))
    run('route', ROUTE, 40000)
    print(read_diag('route'))
    sys.exit(0)

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
