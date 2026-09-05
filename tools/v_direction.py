# -*- coding: utf-8 -*-
"""判定 OSGB 纹理 V 方向约定：墙面三角形 z-v 回归斜率。

照片上方=更高几何（俯拍为主）：
- 斜率 dz/dv > 0 → v=0 在图像底部（bottom-left 约定）→ 转 glTF 需翻转 v
- 斜率 dz/dv < 0 → v=0 在图像顶部（top-left 约定）→ 不翻转
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from geoconvert.osgb.reader import read_osgb

ROOT = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data'
Z_SPAN = 1.0  # 米，墙面三角形最小高度跨度
PER_TILE = 40  # 每个根瓦片取的叶子数


def leaf_files():
    out = []
    for name in sorted(os.listdir(ROOT)):
        d = os.path.join(ROOT, name)
        if not os.path.isdir(d):
            continue
        leaves = []
        for f in sorted(os.listdir(d)):
            # 最深两层（L21/L22）才是叶子
            if f.lower().endswith('.osgb') and ('_L21' in f or '_L22' in f):
                leaves.append(os.path.join(d, f))
        out.extend(leaves[:PER_TILE])
    return out


def file_slope(fp):
    try:
        root = read_osgb(open(fp, 'rb').read())
    except Exception:
        return None
    geoms = []
    stack = [root]
    while stack:
        n = stack.pop()
        geoms.extend(n.drawables)
        stack.extend(n.children)
    sum_vz = sum_v = sum_z = sum_vv = 0.0
    cnt = 0
    for g in geoms:
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
                a, b, c = (verts[k] for k in tri)
                zs = (a[2], b[2], c[2])
                if max(zs) - min(zs) < Z_SPAN:
                    continue
                # 三角形法线（未归一化的叉积）：地面法线 z≈±1，墙面 z≈0
                ux, uy = b[0] - a[0], b[1] - a[1]
                vx, vy = c[0] - a[0], c[1] - a[1]
                nx = uy * (c[2] - a[2]) - (b[2] - a[2]) * vy
                ny = (b[2] - a[2]) * vx - ux * (c[2] - a[2])
                nz = ux * vy - uy * vx
                horiz = (nx * nx + ny * ny) ** 0.5
                if horiz <= abs(nz) * 2.0:  # 法线与水平面夹角 <63° → 不是墙面
                    continue
                vc = sum(uvs[k][1] for k in tri) / 3
                zc = sum(zs) / 3
                sum_vz += vc * zc
                sum_v += vc
                sum_z += zc
                sum_vv += vc * vc
                cnt += 1
    if cnt < 30:
        return None
    cov = sum_vz - sum_v * sum_z / cnt
    var = sum_vv - sum_v * sum_v / cnt
    if var <= 0:
        return None
    return cov / var, cnt


def main():
    files = leaf_files()
    print('采样叶子文件: %d 个' % len(files))
    slopes = []
    for fp in files:
        r = file_slope(fp)
        if r:
            slopes.append(r)
    pos = [s for s, _ in slopes if s > 0]
    neg = [s for s, _ in slopes if s < 0]
    print('有效文件: %d 个（dz/dv>0: %d 个，均值 %.2f；dz/dv<0: %d 个，均值 %.2f）'
          % (len(slopes), len(pos), sum(pos) / max(1, len(pos)),
             len(neg), sum(neg) / max(1, len(neg))))
    if len(pos) > len(neg) * 3 and pos:
        print('结论: v=0 在图像底部（bottom-left）→ 转 glTF 需要 --flip-v')
    elif len(neg) > len(pos) * 3 and neg:
        print('结论: v=0 在图像顶部（top-left）→ 不需要翻转')
    else:
        print('结论: 信号不明确，需浏览器目视验证')


if __name__ == '__main__':
    main()
