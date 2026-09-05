# -*- coding: utf-8 -*-
"""批量解析所有 OSGB 文件，统计失败与数据完整性。"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from geoconvert.osgb.reader import read_osgb
from geoconvert.osgb import reader as _r

ROOT = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data'


def collect(node, stats):
    for d in getattr(node, 'drawables', []):
        stats['geoms'] += 1
        stats['verts'] += len(d.vertices or ())
        stats['prims'] += len(d.primitives)
        stats['idx'] += sum(len(p.get('indices', ())) for p in d.primitives)
        if d.texcoords:
            stats['tex'] += len(d.texcoords[0])
        if d.state_set:
            for unit in d.state_set.texture_attributes:
                for o in unit:
                    if o is not None and getattr(o, 'image', None):
                        stats['imgs'] += 1
                        stats['imgbytes'] += len(o.image.data)
    for c in getattr(node, 'children', []):
        collect(c, stats)


def main():
    files = []
    for dp, _, fns in os.walk(ROOT):
        for f in fns:
            if f.lower().endswith('.osgb'):
                files.append(os.path.join(dp, f))
    print('files:', len(files))
    t0 = time.time()
    fails = []
    totals = dict(geoms=0, verts=0, prims=0, idx=0, tex=0, imgs=0, imgbytes=0)
    eof_mismatch = []
    for i, fp in enumerate(files):
        data = open(fp, 'rb').read()
        try:
            root = read_osgb(data)
        except Exception as e:
            fails.append((fp, str(e)))
            continue
        st = dict(geoms=0, verts=0, prims=0, idx=0, tex=0, imgs=0, imgbytes=0)
        collect(root, st)
        for k in totals:
            totals[k] += st[k]
        # 文件应精确读完（未压缩 osgb 末尾无 padding）
        p = _r._LAST_READER.p
        if p != len(data):
            eof_mismatch.append((fp, p, len(data)))
        if (i + 1) % 400 == 0:
            print('  ...%d/%d (%.1fs)' % (i + 1, len(files), time.time() - t0))
    print('done in %.1fs' % (time.time() - t0))
    print('FAILS: %d' % len(fails))
    for fp, e in fails[:12]:
        print('  FAIL %s: %s' % (os.path.basename(fp), e))
    print('EOF MISMATCH: %d' % len(eof_mismatch))
    for fp, p, n in eof_mismatch[:12]:
        print('  EOF %s: read %d / %d (diff %d)' % (os.path.basename(fp), p, n, n - p))
    print('TOTALS:', totals)


if __name__ == '__main__':
    main()
