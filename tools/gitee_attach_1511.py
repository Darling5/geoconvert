# -*- coding: utf-8 -*-
"""重试 v1.5.11 附件上传（Release id=1128575 已创建，仅补传安装包）。"""
import json
import os
import subprocess
import time
import urllib.request
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OWNER_REPO = 'darling5/geoconvert'
API = 'https://gitee.com/api/v5/repos/%s' % OWNER_REPO
ASSET = os.path.join(ROOT, 'dist', 'geoconvert-setup-1.5.11.exe')
REL_ID = '1128575'


def gitee_token():
    p = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=gitee.com\n\n',
                       capture_output=True, text=True, encoding='utf-8')
    for line in p.stdout.splitlines():
        if line.startswith('password='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('未从凭据管理器取到 gitee.com 令牌')


def direct():
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def attach(tok):
    fn = os.path.basename(ASSET)
    with open(ASSET, 'rb') as f:
        payload = f.read()
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in (('access_token', tok), ('description', fn)):
        parts.append(('--%s\r\nContent-Disposition: form-data; name="%s"\r\n\r\n%s\r\n'
                      % (boundary, k, v)).encode('utf-8'))
    parts.append(('--%s\r\nContent-Disposition: form-data; name="file"; filename="%s"\r\n'
                  'Content-Type: application/octet-stream\r\n\r\n' % (boundary, fn)
                  ).encode('utf-8'))
    parts.append(payload)
    parts.append(('\r\n--%s--\r\n' % boundary).encode('utf-8'))
    data = b''.join(parts)
    for attempt in range(1, 8):
        try:
            req = urllib.request.Request(API + '/releases/%s/attach_files' % REL_ID,
                                         data=data, method='POST')
            req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary)
            with direct().open(req, timeout=300) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            print('  第 %d 次失败: %s' % (attempt, e))
            if attempt == 7:
                raise
            time.sleep(5 * attempt)


tok = gitee_token()
print('令牌已取得，重试附件上传（%.1f MB）…' % (os.path.getsize(ASSET) / 1048576))
attach(tok)
print('附件上传成功')
