# -*- coding: utf-8 -*-
"""岛切块打包的往返采样校验：原 UV→源纹理 与 打包 UV→新图集 颜色一致。"""
import os
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, r'D:\WEB\zicaiduck\geo-convert')
from geoconvert.objconv.convert import (ObjToTiles, build_islands,
                                        split_islands, _shelf_pack)

tmp = tempfile.mkdtemp(prefix='isltest_')
# 两张 256x256 纹理：红色左半/绿右半，蓝色上/黄下（分块可分辨）
tex_a = os.path.join(tmp, 'a.jpg')
tex_b = os.path.join(tmp, 'b.jpg')
ima = Image.new('RGB', (256, 256))
for x in range(256):
    for half, y0 in ((0, 0), (1, 128)):
        pass
px_a = ima.load()
for y in range(256):
    for x in range(256):
        px_a[x, y] = (200, 30, 30) if x < 128 else (30, 200, 30)
ima.save(tex_a, 'JPEG', quality=95)
imb = Image.new('RGB', (256, 256))
px_b = imb.load()
for y in range(256):
    for x in range(256):
        px_b[x, y] = (30, 60, 220) if y < 128 else (220, 200, 30)
imb.save(tex_b, 'JPEG', quality=95)


def grid_sub(x0, z0, w, d, uv0, uv1, n=4):
    """生成一个 (n x n) 网格面的 pos/uv/tri（一块连续 UV 岛）。"""
    xs = x0 + np.linspace(0, w, n + 1)
    zs = z0 + np.linspace(0, d, n + 1)
    us = np.linspace(uv0[0], uv1[0], n + 1)
    vs = np.linspace(uv0[1], uv1[1], n + 1)
    pos, uv, tri = [], [], []
    vid = 0
    for i in range(n + 1):
        for j in range(n + 1):
            pos.append((xs[i], 0.0, zs[j]))
            uv.append((us[i], vs[j]))
    for i in range(n):
        for j in range(n):
            a = i * (n + 1) + j
            b = a + 1
            c = a + (n + 1)
            d2 = c + 1
            tri.extend([(a, c, b), (b, c, d2)])
    return (np.array(pos, dtype=np.float64), np.array(uv, dtype=np.float64),
            np.array(tri, dtype=np.int64))


# 材质 A：两个 UV 岛（左半贴图两块区域），空间上东西分离
pa1, ua1, ta1 = grid_sub(0, 0, 10, 10, (0.02, 0.02), (0.4, 0.4))
pa2, ua2, ta2 = grid_sub(30, 0, 10, 10, (0.6, 0.6), (0.95, 0.95))
posA = np.vstack([pa1, pa2])
uvA = np.vstack([ua1, ua2])
triA = np.vstack([ta1, ta2 + pa1.shape[0]])
# 材质 B：两个 UV 岛，南北分离（与 A 空间交错）
pb1, ub1, tb1 = grid_sub(15, -20, 8, 8, (0.05, 0.05), (0.7, 0.45))
pb2, ub2, tb2 = grid_sub(15, 20, 8, 8, (0.05, 0.55), (0.7, 0.95))
posB = np.vstack([pb1, pb2])
uvB = np.vstack([ub1, ub2])
triB = np.vstack([tb1, tb2 + pb1.shape[0]])

subs = [
    {'pos': posA, 'uv': uvA, 'tri': triA, 'tex': tex_a},
    {'pos': posB, 'uv': uvB, 'tri': triB, 'tex': tex_b},
]

# 1) 岛识别
islands = build_islands(subs)
print('岛数:', len(islands), '(期望 4)',
      [(i['sub'], i['n']) for i in islands])
assert len(islands) == 4

# 2) 空间切分（阈值设 40 → 必切）
parts = split_islands(islands, 40)
print('块数:', len(parts), '每块三角形:', [sum(i['n'] for i in p) for p in parts])
assert sum(sum(i['n'] for i in p) for p in parts) == triA.shape[0] + triB.shape[0]

# 3) 搁架装箱冒烟
pl, lo = _shelf_pack([(50, 40), (40, 30), (60, 20), (10, 10)], 100, 100)
assert not lo, lo
print('shelf_pack ok:', pl)

# 4) 打包 + 往返颜色采样
c = ObjToTiles(os.path.join(tmp, 'out'), max_tris=0)  # 不触发转换流程
all_tri = 0
for pi, chunk in enumerate(parts):
    csubs = c._chunk_subs(subs, chunk)
    print('块 %d: %d 个子网格' % (pi, len(csubs)))
    for s in csubs:
        assert s['uv'] is not None
        all_tri += s['tri'].shape[0]
        # UV 在 [0,1]
        assert s['uv'].min() >= -1e-9 and s['uv'].max() <= 1 + 1e-9
        # 解码图集并采样
        import io
        atlas = Image.open(io.BytesIO(s['tex_blobs'][None])).convert('RGB')
        W, H = atlas.size
        apx = atlas.load()
        # 找到该子网格对应的源材质：用位置匹配原 subs
        src = None
        for k, o in enumerate(subs):
            lut = {o['pos'][v].tobytes(): v for v in range(o['pos'].shape[0])}
            if any(p.tobytes() in lut for p in s['pos'][:5]):
                src = o
                break
        assert src is not None
        spx = Image.open(src['tex']).convert('RGB').load()
        # 每个三角形质心处采样比对
        bad = 0
        rng = np.random.default_rng(3)
        for t in s['tri'][:: max(1, len(s['tri']) // 20)]:
            uvs = s['uv'][t]
            ps = s['pos'][t]
            # 找原 UV：位置匹配
            orig_uv = []
            for p in ps:
                for v in range(src['pos'].shape[0]):
                    if np.allclose(src['pos'][v], p):
                        orig_uv.append(src['uv'][v])
                        break
            if len(orig_uv) != 3:
                bad += 1
                continue
            for (nu, nv), (ou, ov) in zip(uvs, orig_uv):
                a = apx[min(W - 1, int(nu * W)), min(H - 1, int(nv * H))]
                b = spx[min(255, int(ou * 256)), min(255, int(ov * 256))]
                if sum(abs(x - y) for x, y in zip(a, b)) > 90:
                    bad += 1
                    break
        print('   子网格 tris=%d 采样异常=%d atlas=%dx%d' %
              (s['tri'].shape[0], bad, W, H))
        assert bad == 0, '采样颜色不匹配'
assert all_tri == triA.shape[0] + triB.shape[0]
print('三角形守恒:', all_tri)
print('全部通过')
