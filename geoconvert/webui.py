# -*- coding: utf-8 -*-
"""geoconvert Web 图形界面：本地 HTTP 服务（127.0.0.1）+ 系统默认浏览器。

双击 exe（无参数）→ 起服务并自动打开浏览器操作页。
转换在独立子进程执行（大模型内存峰值不影响界面），可取消，日志增量轮询。
全部基于标准库，浏览器端做真实路径的服务器端文件浏览。
"""
import base64
import glob
import json
import math
import os
import re
import shutil
import string
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote, quote

from .params import build_argv, detect_format, validate
from . import license as lic

APP_VERSION = '1.5.5'
GITEE_API = 'https://gitee.com/api/v5/repos/darling5/geoconvert/releases/latest'
GITEE_URL = 'https://gitee.com/darling5/geoconvert/releases/latest'
RELEASES_API = 'https://api.github.com/repos/Darling5/geoconvert/releases/latest'
RELEASES_URL = 'https://github.com/Darling5/geoconvert/releases/latest'

_update_cache = {'t': 0.0, 'data': None}


def _ver_tuple(v):
    v = str(v).strip().lstrip('vV')
    parts = []
    for seg in v.split('.'):
        m = re.match(r'(\d+)', seg.strip())
        parts.append(int(m.group(1)) if m else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_update(force=False):
    """比对最新 Release：Gitee 优先（国内访问快），失败回退 GitHub。结果缓存 30 分钟。"""
    now = time.time()
    if not force and _update_cache['data'] and now - _update_cache['t'] < 1800:
        return _update_cache['data']
    out = {'version': APP_VERSION, 'latest': None, 'url': GITEE_URL,
           'update': False, 'error': None, 'source': None}
    # 1) Gitee（国内源）
    try:
        req = urllib.request.Request(
            GITEE_API, headers={'User-Agent': 'geoconvert/' + APP_VERSION})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode('utf-8'))
        latest = str(data.get('tag_name') or '').strip()
        if latest:
            out['latest'] = latest
            out['url'] = 'https://gitee.com/darling5/geoconvert/releases/tag/' + latest
            out['update'] = _ver_tuple(latest) > _ver_tuple(APP_VERSION)
            out['source'] = 'gitee'
    except Exception:
        pass
    # 2) GitHub 兜底（Gitee 不可达或未发布时）
    if not out['latest']:
        try:
            req = urllib.request.Request(
                RELEASES_API, headers={'User-Agent': 'geoconvert/' + APP_VERSION,
                                       'Accept': 'application/vnd.github+json'})
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read().decode('utf-8'))
            latest = str(data.get('tag_name') or '').strip()
            if latest:
                out['latest'] = latest
                out['url'] = data.get('html_url') or RELEASES_URL
                out['update'] = _ver_tuple(latest) > _ver_tuple(APP_VERSION)
                out['source'] = 'github'
        except Exception as e:
            out['error'] = '网络检查失败：%s' % e
    _update_cache['data'] = out
    _update_cache['t'] = now
    return out


# 地图短链/地理编码：目标均为国内服务，强制直连不走系统代理（用户机器挂代理时更稳）
_direct_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
DEFAULT_TIDT_KEY = '654e9ced28089ca0b5caff0d5c23d5b6'
_UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}


def expand_share_url(url):
    """跟随重定向展开地图短链（如 surl.amap.com/xxx → uri.amap.com/marker?position=…）。"""
    url = (url or '').strip()
    if not re.match(r'^https?://', url, re.I):
        return {'error': '仅支持 http/https 链接'}
    low = url.lower()
    if not any(k in low for k in ('amap', 'qq.com', 'baidu', 'bing', 'google', 'map')):
        return {'error': '不是可识别的地图链接'}
    try:
        req = urllib.request.Request(url, headers=_UA)
        with _direct_opener.open(req, timeout=10) as r:
            return {'url': r.url or url}
    except Exception as e:
        return {'error': '链接展开失败：%s' % e}


def geocode_addr(addr):
    """天地图地理编码：地址文本 → WGS-84(CGCS2000) 经纬度。"""
    addr = (addr or '').strip()
    if not addr:
        return {'error': '地址为空'}
    key = (load_config().get('tianditu_key') or '').strip() or DEFAULT_TIDT_KEY
    ds = json.dumps({'keyWord': addr}, ensure_ascii=False)
    api = ('https://api.tianditu.gov.cn/geocoder?ds=' + quote(ds) + '&tk=' + key)
    try:
        req = urllib.request.Request(api, headers=_UA)
        with _direct_opener.open(req, timeout=10) as r:
            j = json.loads(r.read().decode('utf-8'))
    except Exception as e:
        return {'error': '地址检索失败（网络不可用）：%s' % e}
    loc = j.get('location') or {}
    if str(j.get('status')) == '0' and loc.get('lon') and loc.get('lat'):
        return {'lon': float(loc['lon']), 'lat': float(loc['lat']),
                'addr': addr, 'vendor': 'tianditu'}
    return {'error': '地址检索无结果，请换个写法（如加上城市名，例：深圳 臣田工业区36）'}


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.proc = None
        self.cancelled = False
        self.running = False
        self.t0 = 0.0
        self.code = None
        self.done = True
        self.lines = []  # 日志行（含命令行首行）

    def start(self, argv, license_tx=None):
        with self.lock:
            if self.running:
                return False, '已有转换在进行'
            if getattr(sys, 'frozen', False):
                cmd = [sys.executable] + argv
                cwd = None
            else:
                cmd = [sys.executable, '-m', 'geoconvert'] + argv
                cwd = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            try:
                proc = subprocess.Popen(
                    cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    encoding='utf-8', errors='replace',
                    env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUTF8='1'),
                    creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            except OSError as e:
                return False, '无法启动转换进程：%s' % e
            self.proc = proc
            self.cancelled = False
            self.running = True
            self.done = False
            self.code = None
            self.t0 = time.time()
            self.license_tx = license_tx
            self.lines = ['$ geoconvert ' + ' '.join(argv)]
            threading.Thread(target=self._pump, daemon=True).start()
            return True, None

    def cancel(self):
        with self.lock:
            if self.proc is not None and self.running:
                self.cancelled = True
                try:
                    self.proc.terminate()
                except Exception:
                    pass
                return True
            return False

    def _pump(self):
        proc = self.proc
        try:
            for line in proc.stdout:
                with self.lock:
                    self.lines.append(line.rstrip('\r\n'))
        except Exception:
            pass
        code = proc.wait()
        with self.lock:
            self.running = False
            self.proc = None
            self.code = code
            self.done = True
            if self.cancelled:
                self.lines.append('已取消')
            elif code == 0:
                self.lines.append('完成：用时 %.1fs，输出目录已就绪' % (time.time() - self.t0))
            else:
                self.lines.append('失败：退出码 %s（详见上方日志）' % code)
            license_tx = self.license_tx
            self.license_tx = None
        # 转换未成功（失败/取消）→ 退还本次转换次数，不冤枉用户
        if license_tx and (code != 0 or self.cancelled):
            threading.Thread(target=lic.refund, args=(license_tx,), daemon=True).start()
            with self.lock:
                self.lines.append('本次转换未完成，已退还转换次数')

    def status(self, since):
        with self.lock:
            return {
                'running': self.running,
                'done': self.done,
                'code': self.code,
                'seq': len(self.lines),
                'lines': self.lines[since:] if since > 0 else self.lines,
            }


STATE = State()


def _resource_path(rel):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'geoconvert', rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


def _config_path():
    """config.json 与可执行文件/项目根同目录（用户可编辑，不随源码分发）。"""
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'config.json')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')


def load_config():
    try:
        with open(_config_path(), encoding='utf-8-sig') as f:
            cfg = json.load(f)
        if isinstance(cfg, dict):
            return {'tianditu_key': str(cfg.get('tianditu_key') or ''),
                    'version': APP_VERSION}
    except (OSError, ValueError):
        pass
    return {'tianditu_key': '', 'version': APP_VERSION}


def save_config(cfg):
    try:
        with open(_config_path(), 'w', encoding='utf-8') as f:
            json.dump({'tianditu_key': str(cfg.get('tianditu_key') or '').strip()}, f,
                      ensure_ascii=False, indent=2)
        return None
    except OSError as e:
        return str(e)


def list_drives():
    return ['%s:\\' % d for d in string.ascii_uppercase
            if os.path.exists('%s:\\' % d)]


def browse(path):
    """返回 {path, parent, entries, selected}；path 为空时列"此电脑"（所有盘符）。

    path 指向文件时自动转到其父目录并把该文件标记为 selected（前端高亮）。
    """
    if not path:
        return {'path': '', 'parent': None,
                'entries': [{'name': d, 'type': 'dir'} for d in list_drives()],
                'selected': None}
    path = os.path.normpath(unquote(path))
    selected = None
    if os.path.isfile(path):
        path, selected = os.path.dirname(path), os.path.basename(path)
    if not os.path.isdir(path):
        return {'path': '', 'parent': None, 'entries': [],
                'error': '路径不存在'}
    entries = []
    if os.path.isdir(path):
        try:
            for name in os.listdir(path):
                full = os.path.join(path, name)
                try:
                    if os.path.isdir(full):
                        entries.append({'name': name, 'type': 'dir'})
                    else:
                        entries.append({'name': name, 'type': 'file',
                                        'size': os.path.getsize(full)})
                except OSError:
                    continue
        except OSError:
            return {'path': path, 'parent': None, 'entries': [], 'selected': None,
                    'error': '无法读取目录'}
        entries.sort(key=lambda e: (e['type'] != 'dir', e['name'].lower()))
    parent = os.path.dirname(path)
    if parent == path:  # 盘符根
        parent = ''
    return {'path': path, 'parent': parent or None, 'entries': entries,
            'selected': selected}


def find_models_json():
    """自动探测系统 models.json 及其模型根目录。

    返回 [{json, root}]：root 用既有条目的 url（'/xxx/tileset.json'）反查——
    候选 = json 所在目录 / 其上一级，谁下面存在同名模型目录谁就是根。
    """
    paths = []
    bases = []
    for start in (os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  os.getcwd()):
        d = start
        for _ in range(5):
            if d not in bases:
                bases.append(d)
            parent = os.path.dirname(d)
            if parent == d:
                break
            d = parent
    for b in bases:
        for p in sorted(glob.glob(os.path.join(b, 'www', 'public', '*', 'models.json'))):
            if p not in paths and os.path.isfile(p):
                paths.append(p)
        for p in (os.path.join(b, 'www', 'public', 'models.json'),):
            if os.path.isfile(p) and p not in paths:
                paths.append(p)
    return [{'json': p, 'root': _detect_model_root(p)} for p in paths]


def _detect_model_root(models_json):
    d = os.path.dirname(models_json)
    parent = os.path.dirname(d)
    try:
        with open(models_json, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    for m in (data.get('models') or []):
        if not isinstance(m, dict):
            continue
        seg = str(m.get('url') or '').strip('/').split('/')[0]
        if not seg or seg == 'tileset.json':
            continue
        for cand in (d, parent):
            if os.path.isdir(os.path.join(cand, seg)):
                return cand
    # 回退：json 在 public 的子目录里（terra_b3dms 布局）→ 根 = 上一级；直接在 public 下 → 根 = 所在目录
    return d if os.path.basename(d).lower() == 'public' else parent


def bake_transform(src_dir, matrix):
    """把预览调整烘焙进 tileset.json（新 root.transform = R×A，列主序 16 数）。"""
    src_dir = os.path.abspath(str(src_dir or ''))
    ts = os.path.join(src_dir, 'tileset.json')
    if not os.path.isfile(ts):
        return None, 'tileset.json 不存在：%s' % (src_dir or '（未填写）')
    try:
        vals = [float(x) for x in (matrix or [])]
    except (TypeError, ValueError):
        return None, '矩阵参数无效'
    if len(vals) != 16 or not all(math.isfinite(v) for v in vals):
        return None, '矩阵必须为 16 个有效数字'
    try:
        with open(ts, 'r', encoding='utf-8-sig') as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return None, 'tileset.json 读取失败：%s' % e
    if not isinstance(data, dict) or not isinstance(data.get('root'), dict):
        return None, 'tileset.json 缺少 root'
    try:
        shutil.copyfile(ts, ts + '.bak')  # 保留上一版便于回退
        data['root']['transform'] = vals
        with open(ts, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        return None, 'tileset.json 写入失败：%s' % e
    return {'ok': True, 'backup': ts + '.bak'}, None


def register_model(models_json, root, dir_name, mid, name, src_dir):
    """把转换产物拷贝到模型根目录下，并在 models.json 写入注册条目。"""
    models_json = os.path.abspath(str(models_json or ''))
    root = os.path.abspath(str(root or ''))
    dir_name = str(dir_name or '').strip()
    mid = str(mid or '').strip() or dir_name
    name = str(name or '').strip()
    src_dir = os.path.abspath(str(src_dir or ''))
    if not os.path.isfile(models_json):
        return None, 'models.json 不存在：%s' % (models_json or '（未填写）')
    if not os.path.isdir(root):
        return None, '模型文件根目录不存在：%s' % (root or '（未填写）')
    if not re.fullmatch(r'[A-Za-z0-9_.\-]+', dir_name):
        return None, '目录名只能包含字母、数字、点、下划线、连字符'
    if not name:
        return None, '请填写模型显示名称'
    if not os.path.isfile(os.path.join(src_dir, 'tileset.json')):
        return None, '产物目录缺少 tileset.json：%s' % (src_dir or '（未填写）')
    try:
        with open(models_json, 'r', encoding='utf-8-sig') as f:  # 兼容带 BOM 的 json
            data = json.load(f)
    except (OSError, ValueError) as e:
        return None, 'models.json 读取失败：%s' % e
    models = data.get('models') if isinstance(data, dict) else None
    if not isinstance(models, list):
        return None, 'models.json 缺少 models 数组'
    dst = os.path.join(root, dir_name)
    if os.path.isdir(dst) and not os.path.isfile(os.path.join(dst, 'tileset.json')):
        return None, '目标目录已存在且不是模型目录（拒绝覆盖）：%s' % dst
    try:
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src_dir, dst)
    except OSError as e:
        return None, '拷贝失败：%s' % e
    entry = {'id': mid, 'name': name, 'url': '/%s/tileset.json' % dir_name,
             'type': '3d-tiles'}
    updated = False
    for i, m in enumerate(models):
        if isinstance(m, dict) and m.get('id') == mid:
            models[i] = entry
            updated = True
            break
    if not updated:
        models.append(entry)
    try:
        with open(models_json, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
    except OSError as e:
        return None, 'models.json 写入失败：%s' % e
    n = sum(len(fs) for _, _, fs in os.walk(dst))
    return {'url': entry['url'], 'modelsJson': models_json, 'dir': dst,
            'updated': updated, 'files': n}, None


MIME = {
    '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
    '.wasm': 'application/wasm', '.png': 'image/png', '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg', '.gif': 'image/gif', '.svg': 'image/svg+xml',
    '.glb': 'model/gltf-binary', '.b3dm': 'application/octet-stream',
    '.ktx2': 'image/ktx2', '.html': 'text/html; charset=utf-8',
    '.bin': 'application/octet-stream', '.xml': 'application/xml; charset=utf-8',
    '.bmp': 'image/bmp', '.webp': 'image/webp',
}


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        pass  # 静默访问日志

    # ---- helpers ----
    def _send(self, code, body, ctype='application/json; charset=utf-8', cache=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', cache or 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def _serve_file(self, path, cache=None):
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError:
            self._send(404, {'error': 'not found'})
            return
        ext = os.path.splitext(path)[1].lower()
        self._send(200, data, MIME.get(ext, 'application/octet-stream'), cache)

    def _body(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b'{}'
        try:
            return json.loads(raw.decode('utf-8') or '{}')
        except ValueError:
            return {}

    # ---- routes ----
    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if u.path == '/' or u.path == '/index.html':
            self._serve_file(_resource_path('webui/index.html'))
        elif u.path == '/preview.js':
            self._serve_file(_resource_path('webui/preview.js'))
        elif u.path.startswith('/cesium/'):
            self._serve_static(_resource_path('webui/cesium'),
                               u.path[len('/cesium/'):], cache='public, max-age=86400')
        elif u.path.startswith('/model/'):
            self._serve_model(u.path[len('/model/'):])
        elif u.path == '/api/detect':
            self._send(200, {'fmt': detect_format((q.get('path') or [''])[0])})
        elif u.path == '/api/browse':
            self._send(200, browse((q.get('path') or [''])[0]))
        elif u.path == '/api/status':
            since = int((q.get('since') or ['0'])[0] or 0)
            self._send(200, STATE.status(since))
        elif u.path == '/api/find-models':
            q = parse_qs(u.query)
            p = (q.get('path') or [''])[0].strip()
            if p:
                if not os.path.isfile(p):
                    self._send(404, {'error': '文件不存在：%s' % p})
                else:
                    self._send(200, {'models': [{'json': p, 'root': _detect_model_root(p)}]})
            else:
                self._send(200, {'models': find_models_json()})
        elif u.path == '/api/config':
            self._send(200, load_config())
        elif u.path == '/api/check-update':
            force = (q.get('force') or [''])[0] in ('1', 'true')
            self._send(200, check_update(force))
        elif u.path == '/api/expand-url':
            self._send(200, expand_share_url((q.get('url') or [''])[0]))
        elif u.path == '/api/geocode':
            self._send(200, geocode_addr((q.get('addr') or [''])[0]))
        elif u.path == '/api/license/status':
            self._send(200, lic.status())
        else:
            self._send(404, {'error': 'not found'})

    def _serve_static(self, base, rel, cache=None):
        """在 base 目录内安全地提供静态文件（拒绝 .. 越界）。"""
        base = os.path.normpath(base)
        full = os.path.normpath(os.path.join(base, unquote(rel)))
        if full == base or full.startswith(base + os.sep):
            self._serve_file(full, cache)
        else:
            self._send(404, {'error': 'not found'})

    def _serve_model(self, rest):
        """/model/<b64url(产物目录)>/<相对路径> → 产物目录内静态文件（离线 Cesium 预览用）。"""
        rest = unquote(rest)
        enc, _, rel = rest.partition('/')
        if not enc or not rel:
            self._send(404, {'error': 'not found'})
            return
        try:
            srcdir = os.path.normpath(base64.urlsafe_b64decode(
                enc + '=' * (-len(enc) % 4)).decode('utf-8'))
        except Exception:
            self._send(400, {'error': 'bad path'})
            return
        self._serve_static(srcdir, rel)

    def do_POST(self):
        u = urlparse(self.path)
        body = self._body()
        if u.path == '/api/start':
            vals, err = validate(
                body.get('fmt'), body.get('src'), body.get('dst'),
                loc_mode=body.get('locMode') or 'll',
                lat=body.get('lat') or '', lon=body.get('lon') or '',
                ts=body.get('ts') or '', center=body.get('center') or '',
                width=body.get('width') or '', height=body.get('height') or '',
                max_tris=body.get('maxTris') or '', tex_fmt=body.get('texFmt') or 'png',
                tiles=body.get('tiles') or '1.0')
            if err:
                self._send(400, {'error': err})
                return
            # 转换门禁：先扣 1 次配额（失败/取消会自动退还）
            gate = lic.deduct(str(body.get('fmt') or ''),
                              note=str(body.get('src') or '')[:120])
            if not gate.get('ok'):
                self._send(402, gate)
                return
            ok, err = STATE.start(build_argv(vals), license_tx=gate.get('tx_id'))
            self._send(200 if ok else 409, {'ok': ok, 'error': err,
                                            'quota': gate.get('quota')})
        elif u.path == '/api/cancel':
            self._send(200, {'ok': STATE.cancel()})
        elif u.path == '/api/open':
            p = str(body.get('path') or '')
            try:
                if os.path.isdir(p):
                    os.startfile(p)
                    self._send(200, {'ok': True})
                elif os.path.isfile(p):
                    # 文件：打开所在文件夹并选中
                    subprocess.Popen(['explorer', '/select,', os.path.normpath(p)],
                                     creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    self._send(200, {'ok': True})
                else:
                    self._send(400, {'error': '路径不存在'})
            except OSError as e:
                self._send(500, {'error': str(e)})
        elif u.path == '/api/mkdir':
            p = os.path.normpath(str(body.get('path') or '').strip())
            name = os.path.basename(p.rstrip('\\/'))
            if not p or not name:
                self._send(400, {'error': '路径不能为空'})
                return
            if not re.fullmatch(r'[^\\/:*?"<>|]+', name):
                self._send(400, {'error': '文件夹名称不能包含 \\ / : * ? " < > |'})
                return
            parent = os.path.dirname(p.rstrip('\\/'))
            if not os.path.isdir(parent):
                self._send(400, {'error': '父目录不存在：%s' % parent})
                return
            try:
                os.makedirs(p, exist_ok=False)
            except FileExistsError:
                self._send(409, {'error': '已存在同名文件夹'})
            except OSError as e:
                self._send(500, {'error': '创建失败：%s' % e})
            else:
                self._send(200, {'ok': True, 'path': p})
        elif u.path == '/api/bake-transform':
            vals, err = bake_transform(body.get('dir'), body.get('matrix'))
            if err:
                self._send(400, {'error': err})
            else:
                self._send(200, vals)
        elif u.path == '/api/register':
            vals, err = register_model(
                body.get('modelsJson'), body.get('root'), body.get('dirName'),
                body.get('id'), body.get('name'), body.get('srcDir'))
            if err:
                self._send(400, {'error': err})
            else:
                self._send(200, vals)
        elif u.path == '/api/config':
            key = str(body.get('tianditu_key') or '').strip()
            if len(key) > 128:
                self._send(400, {'error': 'key 过长'})
            else:
                err = save_config({'tianditu_key': key})
                self._send(200 if not err else 500,
                           {'ok': not err, 'error': err})
        elif u.path == '/api/license/login':
            r = lic.login(str(body.get('username') or '').strip(),
                          str(body.get('password') or ''))
            self._send(200 if r.get('ok') else 401, r)
        elif u.path == '/api/license/register':
            r = lic.register(str(body.get('username') or '').strip(),
                             str(body.get('password') or ''),
                             phone=str(body.get('phone') or '').strip(),
                             email=str(body.get('email') or '').strip(),
                             company=str(body.get('company') or '').strip(),
                             invite_code=str(body.get('invite_code') or '').strip())
            self._send(200 if r.get('ok') else 400, r)
        elif u.path == '/api/license/logout':
            self._send(200, lic.logout())
        elif u.path == '/api/license/lead':
            r = lic.submit_lead(str(body.get('contact') or '').strip(),
                                company=str(body.get('company') or '').strip(),
                                requirement=str(body.get('requirement') or '').strip())
            self._send(200 if r.get('ok') else 400, r)
        elif u.path == '/api/license/profile-get':
            r = lic.get_profile()
            self._send(200 if r.get('ok') else 400, r)
        elif u.path == '/api/license/profile-set':
            r = lic.set_profile(phone=str(body.get('phone') or '').strip(),
                                email=str(body.get('email') or '').strip(),
                                company=str(body.get('company') or '').strip())
            self._send(200 if r.get('ok') else 400, r)
        elif u.path == '/api/license/password':
            r = lic.change_password(str(body.get('old_password') or ''),
                                    str(body.get('new_password') or ''))
            self._send(200 if r.get('ok') else 400, r)
        else:
            self._send(404, {'error': 'not found'})


def run_gui(argv=None, force_browser=False):
    argv = list(argv or [])
    if sys.stdout is None:  # windowed exe（console=False）双击启动时无控制台
        sys.stdout = open(os.devnull, 'w', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = open(os.devnull, 'w', encoding='utf-8')
    port = 0
    for i, a in enumerate(argv):
        if a == '--port' and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                pass
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    url = 'http://127.0.0.1:%d' % srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    # 优先内嵌 WebView2 单窗口（无需切浏览器）；失败回退系统浏览器
    if not force_browser and _run_webview(url):
        srv.shutdown()
        return 0

    threading.Thread(target=lambda: (time.sleep(0.4), _open(url)), daemon=True).start()
    try:
        print('geoconvert 图形界面：%s' % url)
        print('浏览器未自动打开时请手动访问上面的地址；关闭本窗口（或按 Ctrl+C）退出。')
    except (OSError, ValueError):
        pass
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        srv.shutdown()
    return 0


def _run_webview(url):
    """pywebview（WebView2）内嵌单窗口；返回 False 表示不可用需回退浏览器。"""
    try:
        import webview
    except Exception as e:
        _safe_print('内嵌窗口组件不可用（%s），回退系统浏览器' % e)
        return False
    try:
        # 显式指定窗口/任务栏图标（winforms 后端不传 icon 时任务栏可能显示默认图标）
        icon = _resource_path('webui/appicon.ico')
        webview.create_window('geoconvert 图形界面', url,
                              background_color='#050d1d', maximized=True)
        webview.start(icon=icon if os.path.isfile(icon) else None)  # 阻塞至窗口关闭
        return True
    except Exception as e:
        _safe_print('内嵌窗口启动失败（%s），回退系统浏览器' % e)
        return False


def _safe_print(msg):
    try:
        print(msg)
    except (OSError, ValueError):
        pass


def _open(url):
    try:
        webbrowser.open(url)
    except Exception:
        pass
