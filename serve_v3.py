"""Asset Vault 静态服务器

以 3D查看 目录为根，提供：
  /                -> index.html (新 UI) / viewer.html (旧 UI)
  /catalog_v3.json -> 统一目录
  /open?path=...   -> 在资源管理器中定位文件

用法：
  python serve_v3.py                                   # 本地资产库（默认 8800 起找空位）
  python serve_v3.py --root _site --port 8801          # 本地预览 CD 产物，与 Pages 同一套相对路径
"""
import argparse
import gzip
import os
import re
import socket
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
# 实际对外服务的根。默认就是本目录；`--root _site` 时可以原样预览 CD 打出来的站点，
# 相对路径（_res/、models/）与线上完全一致 —— 上线前先本地过一遍，别拿线上当调试环境。
SITEDIR = ROOT
# 自检回传的正文上限：_diag.txt 只有几 KB，给个明确的天花板
MAX_DIAG_BYTES = 4 * 1024 * 1024

# 启动时预压缩大文件，避免每次请求都压
GZIP_TARGETS = ['catalog_v3.json', '_res/three.min.js', '_res/OBJLoader.js', '_res/OrbitControls.js']


def ensure_gzip():
    for rel in GZIP_TARGETS:
        src = os.path.join(SITEDIR, rel)
        dst = src + '.gz'
        if not os.path.exists(src):
            continue
        if os.path.exists(dst) and os.path.getmtime(dst) >= os.path.getmtime(src):
            continue
        try:
            with open(src, 'rb') as f:
                raw = f.read()
            with gzip.open(dst, 'wb', compresslevel=6) as f:
                f.write(raw)
            print('  gzip %-28s %.1f MB -> %.1f MB' % (rel, len(raw) / 1048576, os.path.getsize(dst) / 1048576))
        except Exception as e:  # noqa: BLE001 预压缩失败只提示，不影响服务启动
            print('  gzip %s 失败: %s' % (rel, e))
MIME = {
    '.webp': 'image/webp',
    '.obj': 'text/plain; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.html': 'text/html; charset=utf-8',
}


def inside(rel):
    """把请求里的相对路径解析成 SITEDIR 内的绝对路径；越界一律返回 None。

    为什么不能只用 `replace('..', '')` 或 `startswith(SITEDIR)` —— 三种绕法都实测过：
      · `....//`：过一遍 replace 会**变回** `../`；
      · `/C:/Windows/win.ini`：lstrip('/') 之后是 `C:/…`，`os.path.join` 见到盘符会
        **丢掉** SITEDIR 直接拼上去；
      · `...3D查看_bak`：`startswith` 是前缀匹配，同前缀的兄弟目录也会被放行。
    正确做法：先剥掉 URL 形态的前导 `/`、挡掉盘符与 NUL，再用 realpath 解析
    （顺带解掉软链接逃逸），最后用 commonpath 判断是否真的落在 SITEDIR 里面。
    注意顺序：HTTP 请求路径**总是**以 `/` 开头，所以前导斜杠必须先剥掉，
    否则一条正常请求也会被判成绝对路径（第一版就是这么写的，整站 403）。
    """
    rel = urllib.parse.unquote(rel or '').replace('\\', '/').lstrip('/')
    if not rel or '\x00' in rel or re.match(r'^[A-Za-z]:', rel):
        return None
    full = os.path.realpath(os.path.join(SITEDIR, rel))
    if full == SITEDIR:
        return full
    try:
        if os.path.commonpath([SITEDIR, full]) != SITEDIR:
            return None
    except ValueError:      # 不同盘符，commonpath 直接抛
        return None
    return full


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SITEDIR, **kwargs)

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        if ext in MIME:
            return MIME[ext]
        return super().guess_type(path)

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        # 页面与目录数据不缓存（便于迭代），模型/贴图/库文件长缓存
        ext = os.path.splitext(self.path.split('?')[0])[1].lower()
        if ext in ('.html', '.htm', '.json', '', '.json.gz'):
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.send_header('Pragma', 'no-cache')
        else:
            self.send_header('Cache-Control', 'public, max-age=604800')
        super().end_headers()

    def do_GET(self):
        if self.path.startswith('/open?'):
            return self.handle_open()
        if self.path.split('?')[0] in ('', '/', '/index.html'):
            self.path = '/index.html'
        rel = self.path.split('?')[0]
        full = inside(rel)
        if full is None:
            return self.send_error(403)
        gz = full + '.gz'
        if os.path.isfile(gz) and 'gzip' in self.headers.get('Accept-Encoding', ''):
            self.send_response(200)
            self.send_header('Content-Type', self.guess_type(rel))
            self.send_header('Content-Encoding', 'gzip')
            self.send_header('Vary', 'Accept-Encoding')
            self.end_headers()
            try:
                with open(gz, 'rb') as f:
                    self.wfile.write(f.read())
            except (BrokenPipeError, ConnectionResetError):
                pass
            return None
        return super().do_GET()

    def do_POST(self):
        """浏览器自检回传通道：页面把诊断结果 POST 过来，落盘到 _diag.txt"""
        if self.path.split('?')[0] != '/diag':
            return self.send_error(404)
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_DIAG_BYTES:
            return self.send_error(413)
        body = self.rfile.read(n) if n else b''
        with open(os.path.join(SITEDIR, '_diag.txt'), 'wb') as f:
            f.write(body)
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        return None

    def handle_open(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        full = inside(q.get('path', [''])[0])
        if full is None:
            return self.json(403, {'ok': False, 'error': 'forbidden'})
        if not os.path.exists(full):
            return self.json(404, {'ok': False, 'error': 'not found'})
        try:
            subprocess.Popen(['explorer', '/select,', os.path.normpath(full)])
            return self.json(200, {'ok': True})
        except Exception as e:  # noqa: BLE001 日志写失败不应影响请求处理
            return self.json(500, {'ok': False, 'error': str(e)})

    def json(self, code, obj):
        import json
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def log_message(self, fmt, *args):
        msg = fmt % args
        if ' 404 ' in msg:
            return
        sys.stderr.write('%s - %s\n' % (self.address_string(), msg))


def find_port(start=8800, end=8900):
    for p in range(start, end):
        try:
            with socket.socket() as s:
                s.bind(('', p))
                return p
        except OSError:  # noqa: PERF203 端口探测本身就靠逐个试，异常即"该端口被占"
            continue
    return start


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='Asset Vault 静态服务器')
    ap.add_argument('--root', default=ROOT, help='站点根目录（默认本目录）')
    ap.add_argument('--port', type=int, default=0, help='端口，0 = 从 8800 起自动找空位')
    a = ap.parse_args()
    SITEDIR = os.path.realpath(os.path.abspath(a.root))
    if not os.path.isdir(SITEDIR):
        sys.exit('目录不存在：%s' % SITEDIR)

    print('准备静态资源…')
    ensure_gzip()
    port = a.port or find_port()
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print('Asset Vault  ->  http://localhost:%d' % port)
    print('后端诊断通道 ->  POST /diag 落盘到 %s' % os.path.join(SITEDIR, '_diag.txt'))
    print('目录根       :  %s' % SITEDIR)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
        srv.server_close()
