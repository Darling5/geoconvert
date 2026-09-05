# -*- coding: utf-8 -*-
"""geoconvert 授权客户端：注册/登录 + 转换配额（12 次/年 + 2 次/月）。

本地凭据存 license.json（与 exe 同目录，.gitignore 已排除，不随源码分发）；
服务端为公司云服务器上的 geo-license 服务（HTTPS + 证书固定防中间人）。
服务器地址可通过 license.json 的 server_url 字段覆盖（本地联调用 http://127.0.0.1:8900）。
"""
import hashlib
import json
import os
import secrets
import ssl
import sys
import time
import urllib.error
import urllib.request

LICENSE_SERVER = 'https://103.78.229.17:8443'
TIMEOUT = 12

# 服务端自签证书（公钥部分固定在客户端，防中间人；私钥只在服务器上）
SERVER_CERT = '''-----BEGIN CERTIFICATE-----
MIIDPjCCAiagAwIBAgIUSTRpfh93IkBOY1szEbDaJM9b9vAwDQYJKoZIhvcNAQEL
BQAwHTEbMBkGA1UEAwwSZ2VvY29udmVydC1saWNlbnNlMB4XDTI2MDkwNTE2MzU0
MFoXDTM2MDkwMjE2MzU0MFowHTEbMBkGA1UEAwwSZ2VvY29udmVydC1saWNlbnNl
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAkKdyISLqQzz7r+KEluqQ
x+bxHi5Df0Xx6uUitUi0JeivdY1RmgPuhQ+qXcjl/3op8En15x1nPhaDWuejqS+L
4nWIvbp10R6K+GgbToRoBvHzX/vWnJfdPahCv5JFoG8K7uqBncB7SBohBAHjPT10
+sVv6BDQVgHIdY5n5lWwXg5EyIUVBzHz4DRqfRmSwg1o4vkbb/nzKmhFBFp93n21
m9i+3JQDSYXlDGa5kgnBtK19uEITXcU1/Go69Rk8/9kJ7PuclTkFvoiLG0E4dcYe
ofdRH6jP8itKdtZJ8goW5FQsZiDULz41a3ZmU7OVO8Olg+p1E8ojlf+AO1vPZgxF
nQIDAQABo3YwdDAdBgNVHQ4EFgQUFY9UyfAFFg2VDhNediZ4z3ewE0QwHwYDVR0j
BBgwFoAUFY9UyfAFFg2VDhNediZ4z3ewE0QwDwYDVR0TAQH/BAUwAwEB/zAhBgNV
HREEGjAYhwRnTuURghB6aGVuZGFvamlzaHUuY29tMA0GCSqGSIb3DQEBCwUAA4IB
AQCDsS8Rt/X41vT6rnGgcqqwS9ngyr4OuilcEZdlufTFyevrTmsvFwc8PvqG2Phb
vsgXiU/qZ7QuLdSMwVeNwYZKfYVy79DJvOKx/e3Y0r0kvD365fn0X8ghRweeUXGv
0f7y/2YU1Yi/XhkLpDm/mG3Eo0ziQjBuXRfTLdomptxiLag8u7JAZBbgAvhnqCFJ
H/gfIH9qn4+6LLu8QTfzcyfSh3ZTAPfdAi24No8QSyaFA2ScZ7Pn03lJNuaxu+2q
RXFDFoGQUmf3lchoJBxWpiApSnpumUg9DmGfKD94lo8WN8ezF1KJvPVXdQxmXkJm
fJkUVvrvnPFvsgcnZV194rYh
-----END CERTIFICATE-----'''

_state = {'path': None, 'data': None}


def _license_path():
    if getattr(sys, 'frozen', False):
        return os.path.join(os.path.dirname(sys.executable), 'license.json')
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        'license.json')


def _load():
    if _state['data'] is not None:
        return _state['data']
    data = {}
    try:
        with open(_license_path(), encoding='utf-8-sig') as f:
            d = json.load(f)
        if isinstance(d, dict):
            data = d
    except (OSError, ValueError):
        pass
    if not data.get('device_id'):
        raw = '%s-%s' % (uuid_node(), secrets.token_hex(8))
        data['device_id'] = hashlib.sha256(raw.encode()).hexdigest()[:32]
        _save(data)
    _state['data'] = data
    return data


def uuid_node():
    try:
        import uuid
        return str(uuid.getnode())
    except Exception:
        return '0'


def _save(data):
    _state['data'] = data
    try:
        with open(_license_path(), 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def server_url():
    return str(_load().get('server_url') or LICENSE_SERVER).rstrip('/')


def _ctx():
    """https 走证书固定；http（本地联调）不校验。"""
    if server_url().startswith('https://'):
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cadata=SERVER_CERT)
        ctx.check_hostname = True
        ctx.verify_mode = ssl.CERT_REQUIRED
        return ctx
    return None


def _http(path, method='GET', body=None, auth=True):
    """返回 (status, json)。status 0 = 网络不可达。"""
    url = server_url() + path
    data = json.dumps(body).encode('utf-8') if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Content-Type', 'application/json')
    if auth:
        tok = _load().get('token') or ''
        if tok:
            req.add_header('Authorization', 'Bearer ' + tok)
    try:
        r = urllib.request.urlopen(req, timeout=TIMEOUT, context=_ctx())
        with r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode('utf-8'))
        except (ValueError, OSError):
            return e.code, {}
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return 0, {}


# ---------------------------------------------------------------- 对外接口


def _offline(extra=None):
    out = {'logged_in': bool(_load().get('token')), 'online': False,
           'username': _load().get('username') or '',
           'error': '无法连接授权服务器，请检查网络后重试'}
    if extra:
        out.update(extra)
    return out


def status():
    """登录态 + 最新配额（供界面常驻显示）。"""
    d = _load()
    if not d.get('token'):
        return {'logged_in': False, 'online': True, 'username': '',
                'quota': None}
    if d.get('expires') and d['expires'] < time.time():
        return {'logged_in': False, 'online': True, 'username': '',
                'quota': None, 'error': '登录已过期，请重新登录'}
    s, j = _http('/api/quota')
    if s == 0:
        return _offline()
    if s == 401:
        return {'logged_in': False, 'online': True, 'username': '', 'quota': None}
    if s != 200:
        return _offline({'error': j.get('error') or '服务器异常'})
    return {'logged_in': True, 'online': True, 'username': j.get('username') or '',
            'quota': j.get('quota')}


def login(username, password):
    s, j = _http('/api/login', 'POST',
                 {'username': username, 'password': password,
                  'device_id': _load().get('device_id')}, auth=False)
    if s == 200 and j.get('token'):
        d = _load()
        d['username'] = j.get('username') or username
        d['token'] = j['token']
        d['expires'] = j.get('expires') or 0
        _save(d)
        return {'ok': True, 'quota': j.get('quota')}
    if s == 0:
        return {'ok': False, 'error': '无法连接授权服务器，请检查网络'}
    return {'ok': False, 'error': j.get('error') or '登录失败（%s）' % s,
            'code': j.get('code') or ''}


def register(username, password, phone='', email='', company=''):
    s, j = _http('/api/register', 'POST',
                 {'username': username, 'password': password, 'phone': phone,
                  'email': email, 'company': company,
                  'device_id': _load().get('device_id')}, auth=False)
    if s == 200 and j.get('token'):
        d = _load()
        d['username'] = j.get('username') or username
        d['token'] = j['token']
        d['expires'] = j.get('expires') or 0
        _save(d)
        return {'ok': True, 'quota': j.get('quota')}
    if s == 0:
        return {'ok': False, 'error': '无法连接授权服务器，请检查网络'}
    return {'ok': False, 'error': j.get('error') or '注册失败（%s）' % s}


def logout():
    d = _load()
    d['token'] = ''
    d['username'] = ''
    d['expires'] = 0
    _save(d)
    return {'ok': True}


def deduct(fmt, note=''):
    """转换开始前扣 1 次。返回 ok / code（login_required|offline|monthly_exhausted|…）。"""
    d = _load()
    if not d.get('token'):
        return {'ok': False, 'code': 'login_required', 'error': '请先登录'}
    if d.get('expires') and d['expires'] < time.time():
        return {'ok': False, 'code': 'login_required', 'error': '登录已过期，请重新登录'}
    s, j = _http('/api/deduct', 'POST', {'fmt': fmt, 'note': note})
    if s == 0:
        return {'ok': False, 'code': 'offline', 'error': '无法连接授权服务器'}
    if s == 200:
        return {'ok': True, 'tx_id': j.get('tx_id'), 'quota': j.get('quota')}
    if s == 401:
        return {'ok': False, 'code': 'login_required', 'error': '请先登录'}
    if s == 402:
        e = j.get('error') or {}
        return {'ok': False, 'code': e.get('code') or 'quota', 'error': '转换次数不足',
                'quota': e.get('quota')}
    return {'ok': False, 'code': 'server_error', 'error': j.get('error') or '服务器异常'}


def refund(tx_id):
    """转换失败退还次数（后台线程调用，失败不影响主流程）。"""
    try:
        _http('/api/refund', 'POST', {'tx_id': tx_id})
    except Exception:
        pass
    return True


def submit_lead(contact, company='', requirement=''):
    s, j = _http('/api/lead', 'POST',
                 {'contact': contact, 'company': company, 'requirement': requirement})
    if s == 200:
        return {'ok': True, 'granted': j.get('granted') or 0, 'quota': j.get('quota')}
    if s == 0:
        return {'ok': False, 'error': '无法连接授权服务器'}
    return {'ok': False, 'error': j.get('error') or '提交失败'}


def get_profile():
    s, j = _http('/api/profile')
    if s == 200 and j.get('ok'):
        return {'ok': True, 'profile': j.get('profile') or {}}
    if s == 0:
        return {'ok': False, 'error': '无法连接授权服务器，请检查网络'}
    return {'ok': False, 'error': j.get('error') or '查询失败（%s）' % s}


def set_profile(phone='', email='', company=''):
    s, j = _http('/api/profile', 'POST',
                 {'phone': phone, 'email': email, 'company': company})
    if s == 200 and j.get('ok'):
        return {'ok': True, 'profile': j.get('profile') or {}}
    if s == 0:
        return {'ok': False, 'error': '无法连接授权服务器，请检查网络'}
    return {'ok': False, 'error': j.get('error') or '保存失败（%s）' % s}


def change_password(old_password, new_password):
    s, j = _http('/api/password', 'POST',
                 {'old_password': old_password, 'new_password': new_password})
    if s == 200 and j.get('ok'):
        return {'ok': True}
    if s == 0:
        return {'ok': False, 'error': '无法连接授权服务器，请检查网络'}
    return {'ok': False, 'error': j.get('error') or '修改失败（%s）' % s}
