# -*- coding: utf-8 -*-
"""geoconvert 授权客户端：注册/登录 + 转换配额（12 次/年 + 2 次/月）。

本地凭据存 license.json（与 exe 同目录，.gitignore 已排除，不随源码分发）；
服务端为公司云服务器上的 geo-license 服务（HTTPS + 证书固定防中间人）。
服务器地址可通过 license.json 的 server_url 字段覆盖（本地联调用 http://127.0.0.1:8900）。
"""
import hashlib
import hmac
import json
import os
import secrets
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request

LICENSE_SERVER = 'https://103.78.229.17:8443'
TIMEOUT = 12

# 离线兜底：断网时按最近一次在线配额快照本地扣次（上限 OFFLINE_MAX 笔），
# 恢复网络后逐笔补扣同步到服务器。账本 HMAC 签名（密钥=设备+token）防低门槛篡改。
OFFLINE_MAX = 3
OFFLINE_SNAP_TTL = 7 * 86400
_ledger_lock = threading.Lock()
_syncing = False

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


# ---------------------------------------------------------------- 离线兜底

def _save_snap(d, quota, status='ok'):
    """在线拿到的配额实时存快照（离线扣次与界面显示的依据）。"""
    if isinstance(quota, dict) and quota.get('code') == 'ok':
        d['quota_snap'] = {'quota': quota, 'status': status or 'ok', 'ts': time.time()}
        _save(d)


def _ledger_key(d):
    return hashlib.sha256(('%s|%s' % (d.get('device_id') or '',
                                      d.get('token') or '')).encode()).hexdigest()


def _ledger_sig(items, key):
    body = json.dumps(items, ensure_ascii=False, sort_keys=True).encode('utf-8')
    return hmac.new(key.encode('utf-8'), body, hashlib.sha256).hexdigest()


def _load_ledger(d):
    """读离线账本（校验签名，被篡改视为作废清零）。"""
    led = d.get('ledger')
    if not isinstance(led, dict):
        return []
    raw = led.get('items')
    if not isinstance(raw, list):
        return []
    items = [x for x in raw if isinstance(x, dict) and x.get('nonce') and x.get('ts')]
    if str(led.get('sig') or '') != _ledger_sig(items, _ledger_key(d)):
        return []
    return items


def _write_ledger(d, items):
    d['ledger'] = {'items': items, 'sig': _ledger_sig(items, _ledger_key(d))}
    _save(d)


def _snap_valid(d):
    snap = d.get('quota_snap')
    if not isinstance(snap, dict):
        return None
    if time.time() - (snap.get('ts') or 0) > OFFLINE_SNAP_TTL:
        return None
    q = snap.get('quota')
    if not isinstance(q, dict) or q.get('code') != 'ok':
        return None
    return snap


def _local_quota(q, pending):
    """快照配额减去未同步笔数 → 本地视图。"""
    lq = dict(q)
    ml, yl = q.get('monthly_left'), q.get('yearly_left')
    if isinstance(ml, int):
        lq['monthly_left'] = ml - pending
        lq['monthly_used'] = (q.get('monthly_used') or 0) + pending
    if isinstance(yl, int):
        lq['yearly_left'] = yl - pending
        lq['yearly_used'] = (q.get('yearly_used') or 0) + pending
    return lq


def _offline_deduct(d, fmt, note):
    snap = _snap_valid(d)
    if not snap:
        return {'ok': False, 'code': 'offline_no_snapshot',
                'error': '无法连接授权服务器，且离线额度未激活（需联网成功使用一次后可离线转换）'}
    if snap.get('status') and snap['status'] != 'ok':
        code = snap['status']
        return {'ok': False, 'code': code, 'error': _CODE_MSG.get(code, '账号状态异常')}
    q = snap['quota']
    if q.get('expired') or (q.get('valid_until') and q['valid_until'] < time.time()):
        return {'ok': False, 'code': 'expired', 'error': _CODE_MSG['expired']}
    with _ledger_lock:
        items = _load_ledger(d)
        pending = len(items)
        if pending >= OFFLINE_MAX:
            return {'ok': False, 'code': 'offline_limit',
                    'error': '离线转换次数已用完（最多 %d 次），恢复网络后自动同步即可继续' % OFFLINE_MAX}
        ml, yl = q.get('monthly_left'), q.get('yearly_left')
        if isinstance(ml, int) and ml - pending <= 0:
            return {'ok': False, 'code': 'monthly_exhausted',
                    'error': _CODE_MSG['monthly_exhausted'], 'quota': _local_quota(q, pending)}
        if isinstance(yl, int) and yl - pending <= 0:
            return {'ok': False, 'code': 'yearly_exhausted',
                    'error': _CODE_MSG['yearly_exhausted'], 'quota': _local_quota(q, pending)}
        nonce = secrets.token_hex(8)
        items.append({'ts': time.time(), 'fmt': str(fmt or ''), 'nonce': nonce,
                      'note': str(note or '')[:120]})
        _write_ledger(d, items)
    return {'ok': True, 'offline': True, 'tx_id': 'offline:' + nonce,
            'quota': _local_quota(q, pending + 1)}


def _maybe_sync():
    """在线且有未同步账目时，后台线程逐笔补扣（与服务器 /api/deduct 兼容，服务端零改动）。"""
    global _syncing
    if _syncing:
        return
    with _ledger_lock:
        d0 = _load()
        if not _load_ledger(d0):
            return
        _syncing = True
    threading.Thread(target=_sync_worker, daemon=True).start()


def _sync_worker():
    global _syncing
    try:
        while True:
            with _ledger_lock:
                d = _load()
                items = _load_ledger(d)
                if not items:
                    return
                it = items[0]
            s, j = _http('/api/deduct', 'POST',
                         {'fmt': it.get('fmt') or '',
                          'note': '[离线补扣] ' + str(it.get('note') or '')})
            with _ledger_lock:
                d = _load()
                items = _load_ledger(d)
                if not items or items[0].get('nonce') != it.get('nonce'):
                    return  # 并发变化（如离线退还）——退出重来
                if s == 200 or s == 402:
                    # 200=补扣成功；402=服务器额度不足（离线期间被其他设备消耗）→ 该笔记损继续
                    _write_ledger(d, items[1:])
                    if s == 200:
                        _save_snap(d, j.get('quota'))
                    continue
                return  # 网络又断 / 401 / 5xx：下次在线再试
    finally:
        _syncing = False


# ---------------------------------------------------------------- 对外接口


def _offline(extra=None):
    d = _load()
    out = {'logged_in': bool(d.get('token')), 'online': False,
           'username': d.get('username') or '',
           'error': '无法连接授权服务器（离线模式：可继续转换，次数联网后自动同步）'}
    snap = _snap_valid(d)
    pending = len(_load_ledger(d))
    out['offline_pending'] = pending
    if snap:
        out['quota'] = _local_quota(snap['quota'], pending)
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
        return {'logged_in': False, 'online': True, 'username': '', 'quota': None,
                'error': '登录已过期，请重新登录'}
    s, j = _http('/api/quota')
    if s == 0:
        return _offline()
    if s == 401:
        return {'logged_in': False, 'online': True, 'username': '', 'quota': None}
    if s != 200:
        return _offline({'error': j.get('error') or '服务器异常'})
    _save_snap(d, j.get('quota'), j.get('status'))
    _maybe_sync()
    return {'logged_in': True, 'online': True, 'username': j.get('username') or '',
            'status': j.get('status') or 'ok', 'quota': j.get('quota'),
            'offline_pending': len(_load_ledger(d))}


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
        _save_snap(d, j.get('quota'), j.get('status'))
        return {'ok': True, 'quota': j.get('quota')}
    if s == 0:
        return {'ok': False, 'error': '无法连接授权服务器，请检查网络'}
    return {'ok': False, 'error': j.get('error') or '登录失败（%s）' % s,
            'code': j.get('code') or ''}


def register(username, password, phone='', email='', company='', invite_code=''):
    s, j = _http('/api/register', 'POST',
                 {'username': username, 'password': password, 'phone': phone,
                  'email': email, 'company': company,
                  'invite_code': (invite_code or '').strip(),
                  'device_id': _load().get('device_id')}, auth=False)
    if s == 200 and j.get('token'):
        d = _load()
        d['username'] = j.get('username') or username
        d['token'] = j['token']
        d['expires'] = j.get('expires') or 0
        _save(d)
        _save_snap(d, j.get('quota'), j.get('status'))
        return {'ok': True, 'quota': j.get('quota'),
                'status': j.get('status') or 'ok'}
    if s == 0:
        return {'ok': False, 'error': '无法连接授权服务器，请检查网络'}
    return {'ok': False, 'error': j.get('error') or '注册失败（%s）' % s,
            'code': j.get('code') or ''}


def logout():
    d = _load()
    d['token'] = ''
    d['username'] = ''
    d['expires'] = 0
    d.pop('quota_snap', None)
    d.pop('ledger', None)
    _save(d)
    return {'ok': True}


def deduct(fmt, note=''):
    """转换开始前扣 1 次。返回 ok / code（login_required|offline|monthly_exhausted|…）。
    断网时走离线兜底（本地记账，联网后自动补扣同步）。"""
    d = _load()
    if not d.get('token'):
        return {'ok': False, 'code': 'login_required', 'error': '请先登录'}
    if d.get('expires') and d['expires'] < time.time():
        return {'ok': False, 'code': 'login_required', 'error': '登录已过期，请重新登录'}
    s, j = _http('/api/deduct', 'POST', {'fmt': fmt, 'note': note})
    if s == 0:
        return _offline_deduct(d, fmt, note)
    if s == 200:
        _save_snap(d, j.get('quota'))
        return {'ok': True, 'tx_id': j.get('tx_id'), 'quota': j.get('quota')}
    if s == 401:
        return {'ok': False, 'code': 'login_required', 'error': '请先登录'}
    if s == 402:
        e = j.get('error') or {}
        code = e.get('code') or 'quota'
        msg = _CODE_MSG.get(code, '转换次数不足')
        return {'ok': False, 'code': code, 'error': msg, 'quota': e.get('quota')}
    if s == 403:
        e = j.get('error') or {}
        if isinstance(e, dict):
            return {'ok': False, 'code': e.get('code') or 'rejected',
                    'error': _CODE_MSG.get(e.get('code') or '', '账号状态异常'),
                    'quota': e.get('quota')}
        return {'ok': False, 'code': j.get('code') or 'rejected',
                'error': j.get('error') or '账号状态异常'}
    return {'ok': False, 'code': 'server_error', 'error': j.get('error') or '服务器异常'}


_CODE_MSG = {
    'pending_review': '账号审核中（注册后最长 24 小时自动通过），审核通过后即可转换',
    'rejected': '该账号未通过审核，如有疑问请联系商务',
    'monthly_exhausted': '本月免费次数已用完，下月自动重置（可提交需求申请增加次数）',
    'yearly_exhausted': '年度免费次数已用完（可提交需求申请增加次数）',
    'expired': '账号有效期已过，请联系商务续期',
    'device_limit': '该账号绑定的设备数已达上限（如需更换设备请联系商务）',
    'device_blocked': '该设备已被限制使用，如有疑问请联系商务',
    'device_register_limit': '该设备注册的账号数已达上限，请联系商务',
    'bad_invite': '邀请码无效或已被使用',
}


def refund(tx_id):
    """转换失败退还次数（后台线程调用，失败不影响主流程）。
    离线扣次（offline:nonce）→ 从本地账本删除该笔。"""
    tid = str(tx_id or '')
    if tid.startswith('offline:'):
        with _ledger_lock:
            d = _load()
            items = _load_ledger(d)
            nonce = tid[len('offline:'):]
            left = [x for x in items if x.get('nonce') != nonce]
            if len(left) != len(items):
                _write_ledger(d, left)
        return True
    try:
        s, j = _http('/api/refund', 'POST', {'tx_id': tx_id})
        if s == 200 and isinstance(j.get('quota'), dict):
            with _ledger_lock:
                _save_snap(_load(), j['quota'])
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
