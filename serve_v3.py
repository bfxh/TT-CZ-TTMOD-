"""Asset Vault 静态服务器

以 3D查看 目录为根，提供：
  /                -> index.html (新 UI) / viewer.html (旧 UI)
  /catalog_v3.json -> 统一目录
  /open?path=...   -> 在资源管理器中定位文件
"""
import gzip
import os
import socket
import subprocess
import sys
import urllib.parse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))

# 启动时预压缩大文件，避免每次请求都压
GZIP_TARGETS = ['catalog_v3.json', '_res/three.min.js', '_res/OBJLoader.js', '_res/OrbitControls.js']


def ensure_gzip():
    for rel in GZIP_TARGETS:
        src = os.path.join(ROOT, rel)
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


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT, **kwargs)

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
        rel = urllib.parse.unquote(self.path.split('?')[0]).lstrip('/')
        gz = os.path.join(ROOT, rel + '.gz')
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
        body = self.rfile.read(n) if n else b''
        with open(os.path.join(ROOT, '_diag.txt'), 'wb') as f:
            f.write(body)
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        return None

    def handle_open(self):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        rel = (q.get('path', [''])[0] or '').replace('..', '').lstrip('/\\')
        full = os.path.normpath(os.path.join(ROOT, rel))
        if not full.startswith(ROOT):
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
    print('准备静态资源…')
    ensure_gzip()
    port = find_port()
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print('Asset Vault  ->  http://localhost:%d' % port)
    print('旧版查看器   ->  http://localhost:%d/viewer.html' % port)
    print('目录根       :  %s' % ROOT)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print('\n已停止')
        srv.server_close()
