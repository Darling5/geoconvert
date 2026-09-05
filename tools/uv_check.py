# -*- coding: utf-8 -*-
"""UV V 方向终极判定：OBJ(已知渲染正确) × OSGB 颜色交叉采样。

顶点位置在 OBJ 导出与 OSGB 最深 LOD 间精确匹配（同一重建网格）。
对每个匹配顶点，在 OBJ 纹理与 OSGB 图集的 (u,v) 与 (u,1-v) 两处采样窗口平均色，
四个组合中颜色距离最小的即正确的 V 约定组合：
- obj_top / osgb_top：v=0 在图像顶部（glTF 约定）
- obj_bot / osgb_bot：v=0 在图像底部（OpenGL/OSG 约定）
窗口平均色对图集内 patch 旋转（90° 倍数）不敏感。
"""
import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from PIL import Image
from geoconvert.osgb.reader import read_osgb

Image.MAX_IMAGE_PIXELS = None
OBJDIR = r'D:\BaiduNetdiskDownload\库米什压气站模型\OBJ\Data\Tile_+002_+003'
DATADIR = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data\Tile_+002_+003'


def parse_obj():
    verts, uvs, faces = [], [], []
    mtl = None
    for line in open(os.path.join(OBJDIR, 'Tile_+002_+003.obj'), 'r'):
        if line.startswith('v '):
            p = line.split()
            verts.append((round(float(p[1]), 4), round(float(p[2]), 4), round(float(p[3]), 4)))
        elif line.startswith('vt '):
            p = line.split()
            uvs.append((float(p[1]), float(p[2])))
        elif line.startswith('usemtl'):
            mtl = line.split()[1]
        elif line.startswith('f '):
            for tok in line.split()[1:]:
                vi, ti = tok.split('/')[:2]
                faces.append((int(vi) - 1, int(ti) - 1, mtl))
    # mtl -> 贴图文件
    mtlmap = {}
    cur = None
    for line in open(os.path.join(OBJDIR, 'Tile_+002_+003.mtl'), 'r'):
        if line.startswith('newmtl'):
            cur = line.split()[1]
        elif line.strip().startswith('map_Kd') and cur:
            mtlmap[cur] = os.path.join(OBJDIR, line.split()[-1])
    return verts, uvs, faces, mtlmap


def parse_osgb():
    osgb = {}  # position -> (u, v, image_bytes)
    for fn in sorted(os.listdir(DATADIR)):
        if not fn.lower().endswith('.osgb') or '_L2' not in fn:
            continue
        root = read_osgb(open(os.path.join(DATADIR, fn), 'rb').read())
        stack = [root]
        while stack:
            n = stack.pop()
            for g in n.drawables:
                if not g.vertices or not g.texcoords:
                    continue
                img = None
                if g.state_set:
                    for unit in g.state_set.texture_attributes:
                        for o in unit:
                            if o is not None and getattr(o, 'image', None) and o.image.data:
                                img = o.image.data
                                break
                        if img:
                            break
                if img is None:
                    continue
                tc = g.texcoords[0]
                for i, v in enumerate(g.vertices):
                    key = (round(v[0], 4), round(v[1], 4), round(v[2], 4))
                    osgb[key] = (tc[i][0], tc[i][1], img)
            stack.extend(n.children)
    return osgb


def avg_color(img, px, py, r=5):
    w, h = img.size
    x0, x1 = max(0, px - r), min(w, px + r + 1)
    y0, y1 = max(0, py - r), min(h, py + r + 1)
    if x0 >= x1 or y0 >= y1:
        return None
    n = 0
    rs = gs = bs = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            p = img.getpixel((x, y))
            rs += p[0]
            gs += p[1]
            bs += p[2]
            n += 1
    return (rs / n, gs / n, bs / n)


def dist(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def main():
    verts, uvs, faces, mtlmap = parse_obj()
    print('OBJ: %d v / %d vt / %d face-verts / %d 材质' % (len(verts), len(uvs), len(faces), len(mtlmap)))
    osgb = parse_osgb()
    print('OSGB 顶点: %d' % len(osgb))

    obj_imgs = {p: Image.open(p).convert('RGB') for p in set(mtlmap.values())}
    osgb_imgs = {}
    for key, (u, v, data) in osgb.items():
        if id(data) not in osgb_imgs:
            osgb_imgs[id(data)] = Image.open(io.BytesIO(data)).convert('RGB')
    print('OBJ 纹理: %d 张, OSGB 图集: %d 张' % (len(obj_imgs), len(osgb_imgs)))

    samples = []
    seen = set()
    for vi, ti, m in faces:
        key = verts[vi]
        if key not in osgb or m not in mtlmap:
            continue
        sk = (key, m)
        if sk in seen:
            continue
        seen.add(sk)
        ou, ov = uvs[ti]
        gu, gv, gdata = osgb[key]
        # 跳过贴图边缘 3%（避免窗口跨界+wrap 问题）
        if not (0.03 < ou < 0.97 and 0.03 < ov < 0.97 and 0.03 < gu < 0.97 and 0.03 < gv < 0.97):
            continue
        oimg = obj_imgs[mtlmap[m]]
        gimg = osgb_imgs[id(gdata)]
        ow, oh = oimg.size
        gw, gh = gimg.size
        c_ot = avg_color(oimg, int(ou * ow), int(ov * oh))
        c_ob = avg_color(oimg, int(ou * ow), int((1 - ov) * oh))
        c_gt = avg_color(gimg, int(gu * gw), int(gv * gh))
        c_gb = avg_color(gimg, int(gu * gw), int((1 - gv) * gh))
        if None in (c_ot, c_ob, c_gt, c_gb):
            continue
        samples.append((c_ot, c_ob, c_gt, c_gb))
        if len(samples) >= 3000:
            break
    print('有效采样: %d 个' % len(samples))

    combos = {
        'obj_top & osgb_top': lambda s: dist(s[0], s[2]),
        'obj_top & osgb_bot': lambda s: dist(s[0], s[3]),
        'obj_bot & osgb_top': lambda s: dist(s[1], s[2]),
        'obj_bot & osgb_bot': lambda s: dist(s[1], s[3]),
    }
    results = {}
    for name, f in combos.items():
        ds = sorted(f(s) for s in samples)
        results[name] = ds[len(ds) // 2]
        print('%s: 中位色距 %.0f' % (name, results[name]))
    best = min(results, key=results.get)
    print('结论: %s' % best)


if __name__ == '__main__':
    main()
