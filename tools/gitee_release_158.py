# -*- coding: utf-8 -*-
"""Gitee Release v1.5.8 发布脚本（凭据从 Windows 凭据管理器读取，不落盘）。

用法: python tools/gitee_release_158.py
大附件上传带 3 次重试（Gitee attach_files 大文件偶发 SSL EOF 断连）。
"""
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TAG = 'v1.5.8'
OWNER_REPO = 'darling5/geoconvert'
API = 'https://gitee.com/api/v5/repos/%s' % OWNER_REPO
ASSET = os.path.join(ROOT, 'dist', 'geoconvert-setup-%s.exe' % TAG.lstrip('v'))
NOTES = os.path.join(HERE, 'release_notes_%s.md' % TAG)
SHA = '0bff4099fb4c14853a9856a487b58b3c3ce9d050'


def gitee_token():
    """从 Windows 凭据管理器取 gitee.com 私人令牌（git credential fill）。"""
    p = subprocess.run(['git', 'credential', 'fill'], input='protocol=https\nhost=gitee.com\n\n',
                       capture_output=True, text=True, encoding='utf-8')
    for line in p.stdout.splitlines():
        if line.startswith('password='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('未从凭据管理器取到 gitee.com 令牌')


def direct():
    """强制直连不走系统代理（Clash 代理节点对 Gitee 大上传不稳）。"""
    return urllib.request.build_opener(urllib.request.ProxyHandler({}))


def create_release(tok):
    with open(NOTES, encoding='utf-8') as f:
        body = f.read()
    data = json.dumps({'access_token': tok, 'tag_name': TAG,
                       'name': 'geoconvert %s — 离线转换兜底：断网可继续转换，联网自动同步' % TAG,
                       'body': body, 'target_commitish': SHA,
                       'prerelease': False}, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(API + '/releases', data=data, method='POST')
    req.add_header('Content-Type', 'application/json')
    with direct().open(req, timeout=30) as r:
        return json.loads(r.read().decode('utf-8'))


def attach(tok, rel_id):
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
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(API + '/releases/%s/attach_files' % rel_id,
                                         data=data, method='POST')
            req.add_header('Content-Type', 'multipart/form-data; boundary=%s' % boundary)
            with direct().open(req, timeout=300) as r:
                return json.loads(r.read().decode('utf-8'))
        except Exception as e:
            print('  附件上传第 %d 次失败: %s' % (attempt, e))
            if attempt == 3:
                raise
            time.sleep(3)


def main():
    tok = gitee_token()
    print('令牌已取得（不入库）')
    rel = create_release(tok)
    print('Release 已创建: id=%s tag=%s' % (rel.get('id'), rel.get('tag_name')))
    print('上传附件 %s（%.1f MB）…' % (os.path.basename(ASSET),
                                       os.path.getsize(ASSET) / 1048576))
    attach(tok, rel['id'])
    print('附件上传成功')
    print('https://gitee.com/%s/releases/tag/%s' % (OWNER_REPO, TAG))


if __name__ == '__main__':
    main()
