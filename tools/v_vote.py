# -*- coding: utf-8 -*-
"""逐三角形投票判定 OSGB 纹理 V 方向（抗图集内 patch 旋转干扰）。

对每个近垂直墙面三角形：比较最高顶点与最低顶点的 v 值。
- v(高点) > v(低点)：几何越高 v 越大 → v=1 在图像顶部 → bottom-left → 转 glTF 需翻转
- v(高点) < v(低点)：几何越高 v 越小 → v=0 在图像顶部 → top-left → 不翻转
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from geoconvert.osgb.reader import read_osgb

ROOT = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data'
Z_SPAN = 1.5
PER_TILE = 40


def leaf_files():
    out = []
    for name in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, name)
        if not os.path.isdir(d):
            continue
        leaves = [os.path.join(d, f) for f in sorted(os.listdir(d))
                  if f.lower().endswith('.osgb') and ('_L21' in f or '_L22' in f)]
        out.extend(leaves[:PER_TILE])
    return out


def main():
    files = leaf_files()
    print('采样叶子文件: %d 个' % len(files))
    votes_flip = votes_noflip = 0  # flip=v随高度增大(bottom-left)
    w_flip = w_noflip = 0.0
    for fp in files:
        try:
            root = read_osgb(open(fp, 'rb').read())
        except Exception:
            continue
        stack = [root]
        while stack:
            n = stack.pop()
            for g in n.drawables:
                if not g.vertices or not g.texcoords:
                    continue
                uvs = g.texcoords[0]
                verts = g.vertices
                for p in g.primitives:
                    idx = p.get('indices')
                    if not idx or p['mode'] != 4:
                        continue
                    for i in range(0, len(idx) - 2, 3):
                        tri = idx[i:i + 3]
                        vs = [verts[k] for k in tri]
                        zs = [v[2] for v in vs]
                        if max(zs) - min(zs) < Z_SPAN:
                            continue
                        ux, uy = vs[1][0] - vs[0][0], vs[1][1] - vs[0][1]
                        vx, vy = vs[2][0] - vs[0][0], vs[2][1] - vs[0][1]
                        nz = ux * vy - uy * vx
                        nx = uy * (vs[2][2] - vs[0][2]) - (vs[1][2] - vs[0][2]) * vy
                        ny = (vs[1][2] - vs[0][2]) * vx - ux * (vs[2][2] - vs[0][2])
                        if (nx * nx + ny * ny) ** 0.5 <= abs(nz) * 2.0:
                            continue
                        hi = zs.index(max(zs))
                        lo = zs.index(min(zs))
                        dv = uvs[tri[hi]][1] - uvs[tri[lo]][1]
                        area = ((nx * nx + ny * ny + nz * nz) ** 0.5) / 2.0
                        if abs(dv) < 1e-4:
                            continue
                        if dv > 0:
                            votes_flip += 1
                            w_flip += area
                        else:
                            votes_noflip += 1
                            w_noflip += area
            stack.extend(n.children)
    tot = votes_flip + votes_noflip
    print('墙面三角形票数: 需翻转(bottom-left) %d / 不翻转(top-left) %d / 共 %d'
          % (votes_flip, votes_noflip, tot))
    print('面积加权: 需翻转 %.1f m² / 不翻转 %.1f m²' % (w_flip, w_noflip))
    if tot == 0:
        print('结论: 无有效样本')
    elif votes_flip > votes_noflip * 1.5:
        print('结论: v=0 在图像底部（bottom-left）→ 转 glTF 需要 --flip-v')
    elif votes_noflip > votes_flip * 1.5:
        print('结论: v=0 在图像顶部（top-left）→ 不需要翻转')
    else:
        print('结论: 信号不明确（图集内 patch 旋转混杂），需浏览器目视验证')


if __name__ == '__main__':
    main()
