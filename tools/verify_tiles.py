# -*- coding: utf-8 -*-
"""验证生成的 3D Tiles：tileset 结构 + b3dm 可解析 + 顶点范围与 OSGB 一致。"""
import json
import math
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from geoconvert.osgb.reader import read_osgb

OUT = r'D:\WEB\zicaiduck\geo-convert\out\kumishi'
OSGB_DATA = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data'


def parse_glb(glb):
    assert glb[:4] == b'glTF', glb[:4]
    total = struct.unpack('<I', glb[8:12])[0]
    assert total == len(glb), 'glb total %d != %d' % (total, len(glb))
    jLen = struct.unpack('<I', glb[12:16])[0]
    assert glb[16:20] == b'JSON'
    gltf = json.loads(glb[20:20 + jLen])
    p0 = 20 + jLen + (4 - jLen % 4) % 4
    assert glb[p0 + 4:p0 + 8] == b'BIN\x00'
    bLen = struct.unpack('<I', glb[p0:p0 + 4])[0]
    bin_ = glb[p0 + 8:p0 + 8 + bLen]
    assert gltf['buffers'][0]['byteLength'] <= len(bin_)
    return gltf, bin_


def parse_b3dm(fp):
    data = open(fp, 'rb').read()
    assert data[:4] == b'b3dm', fp
    ver, total, ftLen, ftBin, btLen, btBin = struct.unpack('<6I', data[4:28])
    assert ver == 1 and total == len(data), fp
    p = 28 + ftLen + ftBin + btLen + btBin
    return parse_glb(data[p:])


def main():
    ts = json.load(open(os.path.join(OUT, 'tileset.json'), encoding='utf-8'))
    assert ts['asset'] == {'version': '1.0', 'gltfUpAxis': 'Z'}
    assert len(ts['root']['transform']) == 16

    stats = {'tiles': 0, 'content': 0, 'group': 0, 'leaf': 0}
    problems = []

    def walk(t, parent_ge):
        stats['tiles'] += 1
        box = t['boundingVolume']['box']
        if len(box) != 12 or any(not math.isfinite(v) for v in box):
            problems.append('bad box: %r' % box)
        ge = t['geometricError']
        if parent_ge is not None and ge > parent_ge + 1e-6 and t.get('content'):
            problems.append('child GE %.3f > parent %.3f' % (ge, parent_ge))
        uri = (t.get('content') or {}).get('uri')
        if uri:
            stats['content'] += 1
            fp = os.path.join(OUT, uri.replace('/', os.sep))
            if not os.path.isfile(fp):
                problems.append('missing b3dm: %s' % uri)
            else:
                gltf, bin_ = parse_b3dm(fp)
                # 校验 accessor 越界
                for i, acc in enumerate(gltf['accessors']):
                    bv = gltf['bufferViews'][acc['bufferView']]
                    end = bv['byteOffset'] + bv['byteLength']
                    if end > len(bin_):
                        problems.append('%s accessor %d overflow' % (uri, i))
                # 校验图片 magic
                for img in gltf.get('images', []):
                    bv = gltf['bufferViews'][img['bufferView']]
                    head = bin_[bv['byteOffset']:bv['byteOffset'] + 4]
                    if img['mimeType'] == 'image/jpeg' and head[:3] != b'\xff\xd8\xff':
                        problems.append('%s bad jpeg' % uri)
        else:
            stats['group'] += 1
        kids = t.get('children') or []
        if not kids:
            stats['leaf'] += 1
        for c in kids:
            walk(c, ge)

    for c in ts['root']['children']:
        walk(c, ts['root']['geometricError'])
    print('tileset stats:', stats)
    print('problems: %d' % len(problems))
    for p in problems[:20]:
        print('  ', p)

    # 顶点范围对比：root tile 的 full 叶子 vs L22 源文件
    def find_tile(t, uri_suffix):
        if (t.get('content') or {}).get('uri', '').endswith(uri_suffix):
            return t
        for c in t.get('children') or []:
            r = find_tile(c, uri_suffix)
            if r:
                return r
        return None

    for suffix, src in (
            ('Tile_+002_+003_L22_0uuuu110.b3dm',
             os.path.join(OSGB_DATA, 'Tile_+002_+003', 'Tile_+002_+003_L22_0uuuu110.osgb')),
            ('Tile_+002_+003.b3dm',
             os.path.join(OSGB_DATA, 'Tile_+002_+003', 'Tile_+002_+003.osgb'))):
        t = find_tile(ts['root'], suffix)
        assert t, suffix
        gltf, _ = parse_b3dm(os.path.join(OUT, t['content']['uri'].replace('/', os.sep)))
        acc = gltf['accessors'][gltf['meshes'][0]['primitives'][0]['attributes']['POSITION']]
        src_node = read_osgb(open(src, 'rb').read())
        mn = [1e30] * 3
        mx = [-1e30] * 3
        stack = [src_node]
        while stack:
            n = stack.pop()
            for d in n.drawables:
                for v in (d.vertices or ()):
                    for i in range(3):
                        mn[i] = min(mn[i], v[i])
                        mx[i] = max(mx[i], v[i])
            stack.extend(n.children)
        diff = max(abs(a - b) for a, b in zip(acc['min'] + acc['max'], mn + mx))
        print('%s: b3dm verts=%d bounds diff vs osgb=%.6f' %
              (suffix, acc['count'], diff))


if __name__ == '__main__':
    main()
