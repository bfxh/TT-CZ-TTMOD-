#!/usr/bin/env python
"""静态服务的路径守卫门：起一个真服务器，用**原始请求路径**打穿越。

为什么必须用原始路径（`http.client` 而不是浏览器）：浏览器和 requests 都会先把
`/../x` 规范化成 `/x`，所以从浏览器侧永远测不出穿越 —— 而攻击面恰恰是**规范化之前**
的那一段。`SimpleHTTPRequestHandler.translate_path` 本身是安全的，但 `serve_v3.py`
在调它之前自己拼了一次路径（gzip 快速路径），那一段绕过了它的保护。

判据（全部要守住）：
  1. 正常文件能取到（否则是门自己坏了）
  2. `/../decoy.txt` 拿不到站外文件
  3. `/C:/Windows/win.ini` 这类**绝对路径/盘符**拿不到（os.path.join 会丢掉根）
  4. 同前缀的兄弟目录（`site` vs `site_evil`）拿不到 —— 前缀匹配 startswith 的经典洞
  5. `/open?path=../../decoy.txt` 被拒（403），且**不去执行** explorer

退出码：0 = 通过；1 = 命中；2 = 用法/环境错。
"""
from __future__ import annotations

import http.client
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVE = ROOT / 'serve_v3.py'


def free_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def raw_get(port: int, path: str, gzip_ok: bool = True) -> tuple[int, bytes]:
    """用原始路径发请求 —— 不做任何规范化。"""
    c = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
    try:
        c.putrequest('GET', path, skip_host=False, skip_accept_encoding=True)
        c.putheader('Host', '127.0.0.1:%d' % port)
        if gzip_ok:
            c.putheader('Accept-Encoding', 'gzip')
        c.endheaders()
        r = c.getresponse()
        return r.status, r.read()
    finally:
        c.close()


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix='serve-guard-'))
    site = tmp / 'site'
    (site / 'sub').mkdir(parents=True)
    (site / 'index.html').write_text('ok', encoding='utf-8')
    (site / 'ok.txt').write_text('OK-INSIDE', encoding='utf-8')
    (site / 'sub' / 'a.txt').write_text('DEEP-INSIDE', encoding='utf-8')
    # 站外诱饵：故意用 .gz 后缀，正是 gzip 快速路径会去读的那个名字
    (tmp / 'decoy.txt.gz').write_text('DECOY-OUTSIDE', encoding='utf-8')
    # 同前缀的兄弟目录：startswith 前缀匹配会把它放行
    evil = tmp / 'site_evil'
    evil.mkdir()
    (evil / 'secret.txt').write_text('SIBLING-OUTSIDE', encoding='utf-8')

    port = free_port()
    # 不接 stdout 管道：子进程活着时 read() 会永久阻塞（第一版就卡死在这里）。
    # 失败时先 terminate 再 communicate 收输出。
    proc = subprocess.Popen([sys.executable, '-X', 'utf8', str(SERVE),
                             '--root', str(site), '--port', str(port)],
                            cwd=str(ROOT), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        ok_boot = False
        for _ in range(80):
            try:
                if raw_get(port, '/index.html')[0] == 200:
                    ok_boot = True
                    break
            except OSError:
                pass
            time.sleep(0.1)
        if not ok_boot:
            print('SERVE-GUARD FAIL 服务没起来（或 /index.html 不是 200）')
            try:
                st, _ = raw_get(port, '/ok.txt')
                print('  探测 /ok.txt 返回 %s' % st)
            except OSError as exc:
                print('  连不上：%s' % exc)
            return 2

        leaks = []
        checks = [
            ('正常文件可取', '/ok.txt', lambda s, b: s == 200 and b'OK-INSIDE' in b),
            ('子目录文件可取', '/sub/a.txt', lambda s, b: s == 200 and b'DEEP-INSIDE' in b),
            ('`..` 不能出站', '/../decoy.txt', lambda s, b: b'DECOY-OUTSIDE' not in b),
            ('多层 `..` 不能出站', '/../../decoy.txt', lambda s, b: b'DECOY-OUTSIDE' not in b),
            ('绝对路径/盘符不能出站', '/C:/Windows/win.ini', lambda s, b: s in (403, 404, 400)),
            ('同前缀兄弟目录不能出站', '/../site_evil/secret.txt',
             lambda s, b: b'SIBLING-OUTSIDE' not in b),
            ('/open 拒绝 `..`', '/open?path=../decoy.txt', lambda s, b: s == 403),
            ('/open 拒绝绝对路径', '/open?path=C:/Windows/win.ini', lambda s, b: s == 403),
        ]
        for name, path, ok_fn in checks:
            try:
                st, body = raw_get(port, path)
            except OSError as exc:
                leaks.append('%s（%s）请求异常：%s' % (name, path, exc))
                print('  ✗ %-24s %-32s 请求异常' % (name, path))
                continue
            ok = ok_fn(st, body)
            print('  %s %-24s %-32s → %s %s' % ('✓' if ok else '✗', name, path, st,
                                                '' if ok else '泄露/未按预期拒绝'))
            if not ok:
                leaks.append('%s：%s 返回 %s' % (name, path, st))
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    if leaks:
        print('\nSERVE-GUARD FAIL  命中 %d 条' % len(leaks))
        for x in leaks:
            print('   ' + x)
        print('   提示：路径必须先挡掉绝对路径/盘符，再 realpath + commonpath 判断，'
              '不能只靠 replace("..","") 或 startswith。')
        return 1
    print('\nSERVE-GUARD OK  静态服务的路径守卫（%d 条判据）' % len(checks))
    return 0


if __name__ == '__main__':
    sys.exit(main())
