# -*- coding: utf-8 -*-
"""验证 OSGB reader 字段对齐：解析 + dump 关键节点。"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from geoconvert.osgb.reader import read_osgb

FILE = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data\Tile_+002_+003\Tile_+002_+003.osgb'


def dump(node, depth=0, maxdepth=3):
    ind = '  ' * depth
    if isinstance(node, type(None)):
        print(ind + 'None')
        return
    cls = node.cls if hasattr(node, 'cls') else 'Geometry'
    extra = ''
    if hasattr(node, 'name') and node.name:
        extra += ' name=%r' % node.name
    if hasattr(node, 'file_names') and node.file_names:
        extra += ' files=%r' % (node.file_names[:2],)
    if hasattr(node, 'range_list') and node.range_list:
        extra += ' ranges=%r' % (node.range_list[:3],)
    if hasattr(node, 'center') and node.center:
        extra += ' center=%s radius=%.1f' % (node.center, node.radius or -1)
    if hasattr(node, 'matrix') and node.matrix:
        extra += ' matrix=[%s...]' % node.matrix[0]
    if cls == 'Geometry':
        nv = len(node.vertices or ())
        prim = node.primitives[0] if node.primitives else {}
        nidx = len(prim.get('indices', ()))
        extra += ' verts=%d prims=%d idx0=%d mode=%d tex=%d' % (
            nv, len(node.primitives), nidx, prim.get('mode', -1),
            len(node.texcoords))
        if nv:
            extra += ' v0=%s v1=%s' % (node.vertices[0], node.vertices[1])
        if node.texcoords and node.texcoords[0]:
            extra += ' uv0=%s' % (node.texcoords[0][0],)
        if node.state_set:
            ss = node.state_set
            extra += ' ss[modes=%d attrs=%d texattrs=%s]' % (
                len(ss.modes), len(ss.attributes),
                [len(x) for x in ss.texture_attributes])
    print(ind + '- %s%s' % (cls, extra))
    if depth >= maxdepth:
        return
    for c in getattr(node, 'children', []):
        dump(c, depth + 1, maxdepth)
    for c in getattr(node, 'drawables', []):
        dump(c, depth + 1, maxdepth)


def walk_texattr(node, found):
    ss = getattr(node, 'state_set', None)
    if ss is not None:
        for unit in ss.texture_attributes:
            for o in unit:
                if o is not None and hasattr(o, 'image'):
                    found.append(o)
    for c in getattr(node, 'children', []):
        walk_texattr(c, found)
    for c in getattr(node, 'drawables', []):
        ss = getattr(c, 'state_set', None)
        if ss is not None:
            for unit in ss.texture_attributes:
                for o in unit:
                    if o is not None and hasattr(o, 'image'):
                        found.append(o)


def main():
    data = open(FILE, 'rb').read()
    print('file size:', len(data))
    from geoconvert.osgb import reader as _r
    try:
        root = read_osgb(data, verbose=True)
    except Exception as e:
        r = _r._LAST_READER
        if r is not None:
            print('=== FAIL @%d/%d: %s' % (r.p, len(r.d), e))
            print('=== log tail ===')
            for line in r._log[-60:]:
                print(line)
        raise SystemExit(1)
    print('=== tree ===')
    dump(root)
    print('=== textures ===')
    texs = []
    walk_texattr(root, texs)
    for t in texs:
        img = t.image
        print('Texture2D: image=%s data=%dB' % (
            img.filename if img else None,
            len(img.data) if img else 0))


if __name__ == '__main__':
    main()
