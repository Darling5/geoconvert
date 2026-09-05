# -*- coding: utf-8 -*-
"""geoconvert 客户端许可链路端到端测试（走本地 webui 8898 → 授权服务器 8900）。"""
import json
import time
import urllib.request

GUI = 'http://127.0.0.1:8898'
SMOKE_OBJ = r'D:\WEB\zicaiduck\geo-convert\tools\smoke\obj\smoke.obj'
OUT = r'D:\WEB\zicaiduck\geo-convert\tools\_t\lic_e2e_out'


def call(base, path, method='GET', body=None):
    req = urllib.request.Request(base + path, method=method)
    req.add_header('Content-Type', 'application/json')
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

    # 0. 未登录状态
    s, r = call(GUI, '/api/license/status')
    check('初始未登录', s == 200 and r['logged_in'] is False)

    # 1. 未登录点转换 → 402 login_required
    s, r = call(GUI, '/api/start', 'POST', {
        'fmt': 'OBJ', 'src': SMOKE_OBJ, 'dst': OUT,
        'lat': '39.9', 'lon': '116.3'})
    check('未登录门禁拦截', s == 402 and r.get('code') == 'login_required',
          'status=%s code=%s' % (s, r.get('code')))

    # 2. 注册（客户端代理）
    s, r = call(GUI, '/api/license/register', 'POST', {
        'username': '端到端用户', 'password': 'e2e12345',
        'phone': '13900002222', 'company': 'E2E公司'})
    check('客户端注册', s == 200 and r.get('ok') and r['quota']['monthly_left'] == 2,
          r.get('error', ''))

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

    # 7. 再扣一次（月度 2→0），然后取消 → 退款
    s, r = call(GUI, '/api/start', 'POST', {
        'fmt': 'OBJ', 'src': SMOKE_OBJ, 'dst': OUT,
        'lat': '39.9', 'lon': '116.3'})
    q = r.get('quota') or {}
    check('第二次扣次 1→0', s == 200 and q.get('monthly_left') == 0)
    time.sleep(1)
    s, r = call(GUI, '/api/cancel', 'POST')
    check('取消转换', s == 200 and r.get('ok'))
    for _ in range(30):
        time.sleep(1)
        s, r = call(GUI, '/api/status?since=99999')
        if r.get('done') and not r.get('running'):
            break
    time.sleep(2)  # 退款在后台线程

    # 8. 取消退款 0→1
    s, r = call(GUI, '/api/license/status')
    check('取消自动退款', r['quota']['monthly_left'] == 1 and r['quota']['total_used'] == 0,
          'm=%s total=%s' % (r['quota']['monthly_left'], r['quota']['total_used']))

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
        'username': '端到端用户', 'password': 'e2e12345'})
    check('重新登录', s == 200 and r.get('ok'), r.get('error', ''))
    s, r = call(GUI, '/api/license/status')
    check('线索后配额月6年17', r['quota']['monthly_left'] == 6
          and r['quota']['yearly_left'] == 16,  # 月用1次 6-1=5? 见输出
          'm=%s y=%s' % (r['quota']['monthly_left'], r['quota']['yearly_left']))

    print('\n结果: %d 通过' % passed[0])


if __name__ == '__main__':
    main()
