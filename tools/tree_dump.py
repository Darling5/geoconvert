# -*- coding: utf-8 -*-
"""查看 Smart3D OSGB LOD 树结构：file_names、range_list、顶点范围。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from geoconvert.osgb.reader import read_osgb

ROOT = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data'


def dump(node, depth=0, prefix=''):
    ind = '  ' * depth
    extra = []
    if node.matrix:
        extra.append('matrix')
    if node.center:
        extra.append('center=(%.1f,%.1f,%.1f) r=%.1f' % (
            node.center[0], node.center[1], node.center[2], node.radius or 0))
    if node.file_names:
        extra.append('files=%r' % node.file_names)
    if node.range_list:
        extra.append('ranges=%r mode=%d' % (node.range_list, node.range_mode))
    if node.drawables:
        extra.append('draw=%d' % len(node.drawables))
    print('%s%s %s %s' % (ind, prefix, node.cls, ' '.join(str(e) for e in extra)))
    for i, c in enumerate(node.children):
        dump(c, depth + 1, '[%d]' % i)


def bounds(node, lo=None, hi=None):
    if lo is None:
        lo = [1e30] * 3
        hi = [-1e30] * 3
    for d in node.drawables:
        for v in (d.vertices or ()):
            for i in range(3):
                lo[i] = min(lo[i], v[i])
                hi[i] = max(hi[i], v[i])
    for c in node.children:
        lo, hi = bounds(c, lo, hi)
    return lo, hi


def main():
    fp = os.path.join(ROOT, 'Tile_+002_+003', 'Tile_+002_+003.osgb')
    data = open(fp, 'rb').read()
    root = read_osgb(data)
    print('=== root tile %s (%d bytes) ===' % (os.path.basename(fp), len(data)))
    dump(root)
    lo, hi = bounds(root)
    print('vertex bounds: %s .. %s' % (['%.1f' % v for v in lo], ['%.1f' % v for v in hi]))

    for rel in ('Tile_+002_+003_L16_0u.osgb', 'Tile_+002_+003_L17_0uu.osgb',
                'Tile_+002_+003_L19_0uuuu.osgb', 'Tile_+002_+003_L20_0uuuu1.osgb',
                'Tile_+002_+003_L21_0uuuu10.osgb',
                'Tile_+002_+003_L20_0uuuu0.osgb',
                'Tile_+002_+003_L22_0uuuu110.osgb'):
        fp = os.path.join(ROOT, 'Tile_+002_+003', rel)
        data = open(fp, 'rb').read()
        n = read_osgb(data)
        print('\n=== %s (%d bytes) ===' % (rel, len(data)))
        dump(n)
        lo, hi = bounds(n)
        print('vertex bounds: %s .. %s' % (['%.1f' % v for v in lo], ['%.1f' % v for v in hi]))
        # 纹理信息
        for d in n.drawables:
            if d.state_set:
                for unit in d.state_set.texture_attributes:
                    for o in unit:
                        if o is not None and getattr(o, 'image', None):
                            img = o.image
                            print('  tex %s s=%d t=%d bytes=%d head=%r' % (
                                img.filename, img.s, img.t, len(img.data), img.data[:4]))


if __name__ == '__main__':
    main()
