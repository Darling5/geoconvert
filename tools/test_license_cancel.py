# -*- coding: utf-8 -*-
"""取消转换 → 自动退款 专项测试（用马兰多分块 OBJ，转换耗时足够长）。"""
import json
import time
import urllib.request

GUI = 'http://127.0.0.1:8898'
SRC = r'D:\BaiduNetdiskDownload\马兰输油站模型\OBJ\Data'
OUT = r'D:\WEB\zicaiduck\geo-convert\tools\_t\lic_cancel_out'


def call(path, method='GET', body=None):
    req = urllib.request.Request(GUI + path, method=method)
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
    s, r = call('/api/license/status')
    assert r['logged_in'], '请先登录（跑 test_license_e2e.py 后重跑本测试）'
    m0, t0 = r['quota']['monthly_left'], r['quota']['total_used']
    print('转换前: 月剩 %d, 累计 %d' % (m0, t0))

    s, r = call('/api/start', 'POST', {
        'fmt': 'OBJ', 'src': SRC, 'dst': OUT,
        'lat': '38.7', 'lon': '91.2'})
    assert s == 200 and r.get('ok'), '启动失败: %s' % r
    q = r.get('quota') or {}
    print('启动扣次后: 月剩 %d（期望 %d）' % (q.get('monthly_left'), m0 - 1))
    assert q.get('monthly_left') == m0 - 1

    time.sleep(8)  # 让转换跑起来（马兰模型转换远大于 8 秒）
    s, r = call('/api/status?since=99999')
    print('8秒后状态: running=%s' % r.get('running'))
    assert r.get('running'), '模型转换太快，请换更大的模型测试'

    s, r = call('/api/cancel', 'POST')
    print('取消请求: ok=%s' % r.get('ok'))
    assert r.get('ok')

    for _ in range(30):
        time.sleep(1)
        s, r = call('/api/status?since=99999')
        if r.get('done') and not r.get('running'):
            break
    print('转换已终止，日志末行: %s' % (r.get('lines') or ['?'])[-1])

    time.sleep(3)  # 等后台退款线程完成
    s, r = call('/api/license/status')
    m1, t1 = r['quota']['monthly_left'], r['quota']['total_used']
    print('取消退款后: 月剩 %d, 累计 %d' % (m1, t1))
    assert m1 == m0, '月度次数未退还！'
    assert t1 == t0, '累计次数未退还！'
    lines = ' '.join(call('/api/status?since=99999')[1].get('lines') or [])
    assert '退还' in lines, '日志缺少退还提示'
    print('PASS: 取消转换已自动退还次数，日志含退还提示')


if __name__ == '__main__':
    main()
