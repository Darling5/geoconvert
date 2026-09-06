# -*- coding: utf-8 -*-
"""license.py 离线兜底单元测试（不依赖 GUI）。

Phase A 纯本地：断网扣次 / 上限 / 月度耗尽 / 退还 / 账本篡改检测 / status 离线视图。
Phase B 联网同步：需先起本地授权服务器
    python geo-license-server/server.py --port 8900 --no-tls
  验证离线账本逐笔补扣（note 带 [离线补扣] 前缀）且服务器侧真实扣次。
"""
import json
import os
import sqlite3
import sys
import tempfile
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from geoconvert import license as lic  # noqa: E402

DEAD = 'http://127.0.0.1:59999'  # 保证无监听 → 连接拒绝 → status 0
LIVE = 'http://127.0.0.1:8900'
DBP = os.path.normpath(os.path.join(HERE, '..', '..', 'geo-license-server',
                                    'data', 'geo_license.db'))


def call(path, method='GET', body=None, token=None):
    req = urllib.request.Request(LIVE + path, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except (ValueError, OSError):
            return e.code, {}
    except OSError as e:
        return 0, {'error': str(e)}


def reset(path, data):
    """重置 license.py 缓存并指向临时凭据文件（先落盘再清缓存）。"""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    lic._license_path = lambda: path
    lic._state['data'] = None
    lic._load()


def main():
    passed = [0]

    def check(name, cond, extra=''):
        print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))
        if cond:
            passed[0] += 1

    tmp = os.path.join(tempfile.gettempdir(), 'gc_lic_test_%d.json' % os.getpid())
    dev = 'offtest%08x' % (os.getpid() ^ int(time.time()))

    # ---------------- Phase A：断网（纯本地） ----------------
    reset(tmp, {'device_id': dev, 'token': 'tokA', 'username': '离线甲',
                'server_url': DEAD, 'expires': time.time() + 3600})

    r = lic.deduct('OBJ')
    check('无快照断网拦截', not r['ok'] and r['code'] == 'offline_no_snapshot',
          'code=%s' % r.get('code'))

    # 注入在线时拿到的配额快照
    d = lic._load()
    lic._save_snap(d, {'code': 'ok', 'monthly_left': 2, 'monthly_used': 0,
                       'monthly_limit': 2, 'yearly_left': 12, 'yearly_used': 0,
                       'yearly_limit': 12, 'total_used': 0,
                       'valid_until': time.time() + 86400 * 365})
    r = lic.deduct('OBJ')
    check('断网扣次成功', r['ok'] and r.get('offline') is True
          and str(r.get('tx_id')).startswith('offline:'))
    check('本地额度视图 2→1', r['quota']['monthly_left'] == 1
          and r['quota']['yearly_left'] == 11,
          'm=%s y=%s' % (r['quota'].get('monthly_left'), r['quota'].get('yearly_left')))
    tx1 = r['tx_id']

    r = lic.deduct('GLB')
    check('第二笔离线扣次', r['ok'] and r['quota']['monthly_left'] == 0)
    r = lic.deduct('GLB')
    check('月度耗尽拦截(本地)', not r['ok'] and r['code'] == 'monthly_exhausted',
          'code=%s' % r.get('code'))

    # 退还一笔后额度恢复
    lic.refund(tx1)
    r = lic.deduct('GLB')
    check('退还后可再扣', r['ok'] and r['quota']['monthly_left'] == 0)
    r = lic.deduct('GLB')
    check('退还后再耗尽', not r['ok'] and r['code'] == 'monthly_exhausted')

    # 重置账本并抬高月度快照（否则月度 2 次先耗尽，验不到 OFFLINE_MAX=3 上限）
    d = lic._load()
    d['quota_snap']['quota']['monthly_left'] = 5
    lic._save(d)
    lic._write_ledger(d, [])
    txs = []
    for i in range(3):
        r = lic.deduct('OBJ', note='n%d' % i)
        check('离线第 %d 笔' % (i + 1), r['ok'])
        txs.append(r['tx_id'])
    r = lic.deduct('OBJ')
    check('离线上限拦截', not r['ok'] and r['code'] == 'offline_limit',
          'code=%s' % r.get('code'))

    # status 离线视图
    st = lic.status()
    check('status 离线标记', st['logged_in'] and st['online'] is False
          and st.get('offline_pending') == 3,
          'online=%s pending=%s' % (st.get('online'), st.get('offline_pending')))
    check('status 本地额度', st['quota']['monthly_left'] == 5 - 3
          and st['quota']['monthly_used'] == 3,
          'm=%s used=%s' % (st['quota'].get('monthly_left'),
                            st['quota'].get('monthly_used')))

    # 账本篡改：改 items 不改 sig → 整本作废
    d = lic._load()
    items = d['ledger']['items']
    items.append({'ts': 1, 'fmt': 'X', 'nonce': 'fake', 'note': ''})
    d['ledger'] = {'items': items, 'sig': d['ledger']['sig']}
    lic._save(d)
    check('账本篡改作废', lic._load_ledger(lic._load()) == [])

    # 登出清理
    lic.logout()
    check('登出清快照与账本', 'quota_snap' not in lic._load()
          and 'ledger' not in lic._load())

    # ---------------- Phase B：联网补扣同步（需本地服务器） ----------------
    s, _ = call('/api/quota')
    if s == 0:
        print('\n(跳过 Phase B：本地服务器未启动)')
        print('\n结果: %d 通过' % passed[0])
        return
    try:
        import sqlite3 as _sq
        con = _sq.connect(DBP, timeout=10)
        con.execute('DELETE FROM devices WHERE device_id=?', (dev,))
        con.commit()
        con.close()
    except Exception as e:
        print('(设备清理跳过: %s)' % e)

    ts = str(int(time.time()))[-6:]
    user = '离线兜底' + ts
    reset(tmp, {'device_id': dev, 'server_url': LIVE})
    # 无码注册会进 pending（离线扣次被账号状态拦截）→ 用邀请码免审核
    cfgp = os.path.normpath(os.path.join(HERE, '..', '..', 'geo-license-server',
                                         'config.json'))
    with open(cfgp, encoding='utf-8') as f:
        admin_pw = json.load(f)['admin_password']
    s, r = call('/admin/api/login', 'POST', {'password': admin_pw})
    s, r = call('/admin/api/invite_create', 'POST', {'count': 1, 'note': 'offtest'},
                token=r.get('token'))
    invite = (r.get('codes') or [''])[0]
    r = lic.register(user, 'off12345', invite_code=invite)
    check('注册拿在线快照', r['ok'] and r['quota']['monthly_left'] == 2,
          str(r.get('quota')))

    # 断网 2 笔
    d = lic._load()
    d['server_url'] = DEAD
    lic._save(d)
    r1 = lic.deduct('OBJ', note='断网转换1')
    r2 = lic.deduct('OBJ', note='断网转换2')
    check('断网两笔均成功', r1['ok'] and r2['ok']
          and r2['quota']['monthly_left'] == 0)

    # 恢复网络 → status 触发自动同步
    d = lic._load()
    d['server_url'] = LIVE
    lic._save(d)
    st = lic.status()
    for _ in range(40):
        if st.get('online') and st.get('offline_pending') == 0:
            break
        time.sleep(0.5)
        st = lic.status()
    check('联网自动补扣清零', st.get('online') is True
          and st.get('offline_pending') == 0,
          'pending=%s' % st.get('offline_pending'))
    check('同步后服务器额度 0', st['quota']['monthly_left'] == 0
          and st['quota']['yearly_left'] == 10,
          'm=%s y=%s' % (st['quota'].get('monthly_left'),
                         st['quota'].get('yearly_left')))

    # 服务器侧账目带 [离线补扣] 标记
    try:
        con = sqlite3.connect(DBP, timeout=10)
        rows = con.execute(
            "SELECT note FROM tx WHERE user_id=(SELECT id FROM users "
            "WHERE username=?) ORDER BY id", (user,)).fetchall()
        con.close()
        off_notes = [r[0] for r in rows if '[离线补扣]' in str(r[0])]
        check('服务器账目带离线标记', len(off_notes) == 2,
              'notes=%s' % off_notes)
    except Exception as e:
        check('服务器账目带离线标记', False, str(e))

    # 清理测试用户
    try:
        con = sqlite3.connect(DBP, timeout=10)
        con.execute('DELETE FROM tx WHERE user_id=(SELECT id FROM users WHERE username=?)',
                    (user,))
        con.execute('DELETE FROM devices WHERE user_id=(SELECT id FROM users WHERE username=?)',
                    (user,))
        con.execute('DELETE FROM users WHERE username=?', (user,))
        con.commit()
        con.close()
        print('(测试用户已清理)')
    except Exception as e:
        print('(清理失败: %s)' % e)

    try:
        os.remove(tmp)
    except OSError:
        pass
    print('\n结果: %d 通过' % passed[0])


if __name__ == '__main__':
    main()
