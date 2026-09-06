# -*- coding: utf-8 -*-
"""geoconvert 客户端许可链路端到端测试（走本地 webui 8898 → 授权服务器 8900）。"""
import json
import os
import time
import urllib.request

GUI = 'http://127.0.0.1:8898'
LIC = 'http://127.0.0.1:8900'
SMOKE_OBJ = r'D:\WEB\zicaiduck\geo-convert\tools\smoke\obj\smoke.obj'
OUT = r'D:\WEB\zicaiduck\geo-convert\tools\_t\lic_e2e_out'


def call(base, path, method='GET', body=None, token=None):
    req = urllib.request.Request(base + path, method=method)
    req.add_header('Content-Type', 'application/json')
    if token:
        req.add_header('Authorization', 'Bearer ' + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(req, data, timeout=20) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except (ValueError, OSError):
            return e.code, {}


def main():
    passed = [0]
    def check(name, cond, extra=''):
        print('%s %s %s' % ('PASS' if cond else 'FAIL', name, extra))
        if cond:
            passed[0] += 1

    # 幂等：清掉本设备在测试库里的绑定/拉黑记录（本地联调专用）
    try:
        import sqlite3
        lp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          'license.json')
        with open(lp, encoding='utf-8-sig') as f:
            dev = json.load(f).get('device_id', '')
        dbp = os.path.normpath(os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), '..', 'geo-license-server', 'data', 'geo_license.db'))
        con = sqlite3.connect(dbp, timeout=10)
        con.execute('DELETE FROM devices WHERE device_id=?', (dev,))
        con.execute('DELETE FROM device_block WHERE device_id=?', (dev,))
        con.commit()
        con.close()
    except Exception as e:
        print('(跳过设备清理: %s)' % e)

    # 0. 未登录状态（先兜底登出，清掉上一轮残留登录态）
    call(GUI, '/api/license/logout', 'POST')
    s, r = call(GUI, '/api/license/status')
    check('初始未登录', s == 200 and r['logged_in'] is False)

    # 1. 未登录点转换 → 402 login_required
    s, r = call(GUI, '/api/start', 'POST', {
        'fmt': 'OBJ', 'src': SMOKE_OBJ, 'dst': OUT,
        'lat': '39.9', 'lon': '116.3'})
    check('未登录门禁拦截', s == 402 and r.get('code') == 'login_required',
          'status=%s code=%s' % (s, r.get('code')))

    # 1b. 无码注册 → pending → 转换拦截 pending_review
    ts = str(int(time.time()))[-6:]
    s, r = call(GUI, '/api/license/register', 'POST', {
        'username': '无码用户' + ts, 'password': 'e2e12345'})
    check('无码注册进审核', s == 200 and r.get('ok') and r.get('status') == 'pending',
          str(r.get('status')))
    s, r = call(GUI, '/api/start', 'POST', {
        'fmt': 'OBJ', 'src': SMOKE_OBJ, 'dst': OUT,
        'lat': '39.9', 'lon': '116.3'})
    check('审核中转换拦截', s == 402 and r.get('code') == 'pending_review',
          'status=%s code=%s err=%s' % (s, r.get('code'), r.get('error')))
    call(GUI, '/api/license/logout', 'POST')

    # 1c. 管理端生成邀请码 → 有码注册免审核
    cfgp = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        '..', 'geo-license-server', 'config.json')
    with open(os.path.normpath(cfgp), encoding='utf-8') as f:
        admin_pw = json.load(f)['admin_password']
    s, r = call(LIC, '/admin/api/login', 'POST', {'password': admin_pw})
    atok = r.get('token', '')
    s, r = call(LIC, '/admin/api/invite_create', 'POST',
                {'count': 1, 'note': 'e2e'}, token=atok)
    check('生成邀请码', s == 200 and len(r.get('codes', [])) == 1)
    invite = r['codes'][0]

    # 2. 注册（客户端代理，带邀请码 → 免审核）
    s, r = call(GUI, '/api/license/register', 'POST', {
        'username': '端到端用户' + ts, 'password': 'e2e12345',
        'invite_code': invite,
        'phone': '13900002222', 'company': 'E2E公司'})
    check('客户端注册(邀请码)', s == 200 and r.get('ok') and r.get('status') == 'ok',
          str(r.get('status')))
    check('注册配额 2/12', r['quota']['monthly_left'] == 2,
          'm=%s' % r['quota']['monthly_left'])

    # 3. 状态已登录
    s, r = call(GUI, '/api/license/status')
    check('登录态查询', s == 200 and r['logged_in'] and r['quota']['monthly_left'] == 2)

    # 4. 正常转换 → 扣次
    s, r = call(GUI, '/api/start', 'POST', {
        'fmt': 'OBJ', 'src': SMOKE_OBJ, 'dst': OUT,
        'lat': '39.9', 'lon': '116.3'})
    check('登录后放行转换', s == 200 and r.get('ok'), r.get('error', ''))
    q = r.get('quota') or {}
    check('转换扣次 2→1', q.get('monthly_left') == 1 and q.get('yearly_left') == 11,
          'm=%s y=%s' % (q.get('monthly_left'), q.get('yearly_left')))

    # 5. 等转换完成
    for _ in range(60):
        time.sleep(1)
        s, r = call(GUI, '/api/status?since=99999')
        if r.get('done') and not r.get('running'):
            break
    check('转换完成', r.get('code') == 0, 'code=%s' % r.get('code'))

    # 6. 成功后配额保持（不退）
    s, r = call(GUI, '/api/license/status')
    check('成功不退款', r['quota']['monthly_left'] == 1 and r['quota']['total_used'] == 1)

    # 7. 再扣一次（月度 1→0），立即取消 → 退款
    s, r = call(GUI, '/api/start', 'POST', {
        'fmt': 'OBJ', 'src': SMOKE_OBJ, 'dst': OUT,
        'lat': '39.9', 'lon': '116.3'})
    q = r.get('quota') or {}
    check('第二次扣次 1→0', s == 200 and q.get('monthly_left') == 0)
    s, r = call(GUI, '/api/cancel', 'POST')
    check('取消转换', s == 200 and r.get('ok'))
    for _ in range(30):
        time.sleep(1)
        s, r = call(GUI, '/api/status?since=99999')
        if r.get('done') and not r.get('running'):
            break
    time.sleep(2)  # 退款在后台线程

    # 8. 取消退款（取消成功：第1次成功保留 m=1/total=1；若取消前来不及完成则 m=0/total=2）
    s, r = call(GUI, '/api/license/status')
    m = r['quota']['monthly_left']
    check('取消自动退款', (m == 1 and r['quota']['total_used'] == 1)
          or (m == 0 and r['quota']['total_used'] == 2),
          'm=%s total=%s' % (m, r['quota']['total_used']))

    # 9. 提交线索 → +5
    s, r = call(GUI, '/api/license/lead', 'POST', {
        'contact': '13900002222', 'company': 'E2E公司', 'requirement': '批量转换'})
    check('客户端提交线索', s == 200 and r.get('ok') and r['granted'] == 5,
          'granted=%s' % r.get('granted'))

    # 10. 登出
    s, r = call(GUI, '/api/license/logout', 'POST')
    check('登出', s == 200 and r.get('ok'))
    s, r = call(GUI, '/api/license/status')
    check('登出后未登录', r['logged_in'] is False)

    # 11. 重新登录（同设备）
    s, r = call(GUI, '/api/license/login', 'POST', {
        'username': '端到端用户' + ts, 'password': 'e2e12345'})
    check('重新登录', s == 200 and r.get('ok'), r.get('error', ''))
    s, r = call(GUI, '/api/license/status')
    check('线索后配额', r['quota']['monthly_left'] in (5, 6)
          and r['quota']['yearly_left'] in (15, 16),
          'm=%s y=%s' % (r['quota']['monthly_left'], r['quota']['yearly_left']))

    print('\n结果: %d 通过' % passed[0])


if __name__ == '__main__':
    main()
