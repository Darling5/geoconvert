# -*- coding: utf-8 -*-
"""register_model / find_models_json 单元测试（临时目录模拟系统结构）。"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from geoconvert.webui import bake_transform, find_models_json, register_model

base = tempfile.mkdtemp(prefix='gc_reg_')
try:
    # 模拟系统结构：<base>/www/public/terra_b3dms/models.json + <base>/www/public/
    root = os.path.join(base, 'www', 'public')
    os.makedirs(os.path.join(root, 'terra_b3dms'))
    models_json = os.path.join(root, 'terra_b3dms', 'models.json')
    with open(models_json, 'w', encoding='utf-8') as f:
        json.dump({'models': [{'id': 'a', 'name': 'A', 'url': '/a/tileset.json',
                               'type': '3d-tiles'}], 'activeModelId': 'a'}, f)
    # 模拟转换产物
    out = os.path.join(base, 'out')
    os.makedirs(os.path.join(out, 'sub'))
    with open(os.path.join(out, 'tileset.json'), 'w', encoding='utf-8') as f:
        f.write('{}')
    with open(os.path.join(out, 'sub', 'x.b3dm'), 'wb') as f:
        f.write(b'1234')

    # 1. find_models_json 应探测到（cwd 切到 base，模拟系统目录结构在探测范围内）
    old_cwd = os.getcwd()
    os.chdir(base)
    try:
        found = find_models_json()
    finally:
        os.chdir(old_cwd)
    entry = next((e for e in found if e['json'] == models_json), None)
    assert entry, 'find_models_json 未探测到：%s' % found
    assert entry['root'] == root, 'root 嗅探错误：%s != %s' % (entry['root'], root)
    print('FIND-OK', entry)

    # 2. 首次注册（追加）
    vals, err = register_model(models_json, root, 'my_model', '', '我的模型', out)
    assert err is None, err
    assert vals['updated'] is False and vals['files'] == 2, vals
    assert os.path.isfile(os.path.join(root, 'my_model', 'tileset.json'))
    assert os.path.isfile(os.path.join(root, 'my_model', 'sub', 'x.b3dm'))
    with open(models_json, encoding='utf-8') as f:
        d = json.load(f)
    assert d['models'][-1] == {'id': 'my_model', 'name': '我的模型',
                               'url': '/my_model/tileset.json', 'type': '3d-tiles'}
    assert d['activeModelId'] == 'a', '无关字段被改动'
    assert d['models'][0]['id'] == 'a', '既有条目被改动'
    print('REGISTER-NEW-OK', vals)

    # 3. 同 id 再注册（更新，条目数不变）
    vals, err = register_model(models_json, root, 'my_model', 'my_model', '改名模型', out)
    assert err is None, err
    assert vals['updated'] is True, vals
    with open(models_json, encoding='utf-8') as f:
        d = json.load(f)
    assert len(d['models']) == 2
    assert d['models'][1]['name'] == '改名模型'
    print('REGISTER-UPDATE-OK')

    # 4. 拒绝覆盖非模型目录
    os.makedirs(os.path.join(root, 'keepme'))
    open(os.path.join(root, 'keepme', 'data.txt'), 'w').close()
    _, err = register_model(models_json, root, 'keepme', '', 'x', out)
    assert err and '拒绝覆盖' in err, err
    assert os.path.isfile(os.path.join(root, 'keepme', 'data.txt')), '目标被误删'
    print('REJECT-NONMODEL-OK')

    # 5. 校验分支
    _, err = register_model(models_json, root, '非法 名', '', 'x', out)
    assert err and '目录名' in err, err
    _, err = register_model(models_json, root, 'm2', '', '', out)
    assert err and '显示名称' in err, err
    _, err = register_model(models_json, root, 'm2', '', 'x', os.path.join(base, 'none'))
    assert err and 'tileset.json' in err, err
    print('VALIDATE-OK')

    # 6. bake_transform：缺 root 报错 / 写入 16 数并备份
    _, err = bake_transform(out, list(range(16)))
    assert err and 'root' in err, err
    with open(os.path.join(out, 'tileset.json'), 'w', encoding='utf-8') as f:
        json.dump({'root': {'transform': [0] * 16, 'box': [0] * 12}}, f)
    vals, err = bake_transform(out, [i + 0.5 for i in range(16)])
    assert err is None, err
    assert os.path.isfile(os.path.join(out, 'tileset.json.bak')), '未生成备份'
    with open(os.path.join(out, 'tileset.json'), encoding='utf-8') as f:
        d = json.load(f)
    assert d['root']['transform'] == [i + 0.5 for i in range(16)], d
    assert d['root']['box'] == [0] * 12, '无关字段被改动'
    _, err = bake_transform(out, 'bad')
    assert err, '非法矩阵未报错'
    _, err = bake_transform(out, [1.0] * 15)
    assert err and '16' in err, err
    print('BAKE-OK')
    print('ALL-PASS')
finally:
    shutil.rmtree(base, ignore_errors=True)
