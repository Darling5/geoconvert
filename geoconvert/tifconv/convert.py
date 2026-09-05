# -*- coding: utf-8 -*-
"""TIF 正射影像 → 贴图 3D 平面（3D Tiles b3dm，大纹理网格切块）。

把影像贴到对应地面尺寸的 3D 平面（unlit 材质、黑边转透明），
复用应用内 3D 模型调整控件（XYZ 轴/旋转/斜移/缩放/透明度/保存）。

切块策略：纹理任一边超过 --cell-max（默认 2048px）时按网格切块——
根节点为整幅低清总览（1024px，REPLACE 细化），子块为各网格的高清贴图平面。
远视角只加载总览，拉近后按视野加载所在格网块，避免单张大纹理一次性下载/解码。

与 www/tif_to_plane.py 语义一致：rotation 北偏东顺时针为正，
widthMeters 为影像对应的地面宽度（米），高度默认抬 1 米防深度冲突。
"""
import argparse
import io
import json
import math
import os
import time
import urllib.request

from PIL import Image, ImageChops

Image.MAX_IMAGE_PIXELS = None

from ..coords import enu_to_ecef_transform
from ..gltf import GlbBuilder, to_b3dm

BLACK_THRESHOLD = 16


def black_to_transparent(im, threshold):
    """近黑像素（三通道都 ≤ threshold）转透明，返回 RGBA。"""
    r, g, b = im.split()
    tr = r.point(lambda v: 255 if v > threshold else 0)
    tg = g.point(lambda v: 255 if v > threshold else 0)
    tb = b.point(lambda v: 255 if v > threshold else 0)
    alpha = ImageChops.lighter(ImageChops.lighter(tr, tg), tb)  # 任一通道亮即不透明
    im = im.convert('RGBA')
    im.putalpha(alpha)
    return im


def load_texture(tif_path, tex_max, threshold, fmt):
    """TIF → RGB → 降采样到 tex_max →（png）黑边转透明，返回 PIL Image。"""
    im = Image.open(tif_path)
    if im.mode != 'RGB':
        im = im.convert('RGB')
    w, h = im.size
    scale = tex_max / max(w, h)
    if scale < 1:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                       Image.LANCZOS)
    if fmt == 'png':
        im = black_to_transparent(im, threshold)
    return im


def encode_image(im, fmt):
    buf = io.BytesIO()
    if fmt == 'png':
        im.save(buf, format='PNG', compress_level=6)
    else:
        im.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def build_plane_b3dm(w_m, h_m, tex_bytes):
    """单四边形贴图平面（ENU 原始坐标，中心在原点，z=0，法线朝上）。"""
    hw, hh = w_m / 2.0, h_m / 2.0
    # v0 西北(图像左上) v1 东北(右上) v2 东南(右下) v3 西南(左下)
    b = GlbBuilder(unlit=True, alpha=True)
    b.add_primitive(
        [(-hw, hh, 0.0), (hw, hh, 0.0), (hw, -hh, 0.0), (-hw, -hh, 0.0)],
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        [0, 2, 1, 0, 3, 2],
        texture=tex_bytes)
    return to_b3dm(b.finish())


def build_cell_b3dm(x0, x1, y0, y1, tex_bytes):
    """网格块平面：ENU 坐标 (x0..x1)×(y0..y1)，z=0，UV 全幅映射裁出的纹理。"""
    # v0 西北(左上) v1 东北(右上) v2 东南(右下) v3 西南(左下)
    b = GlbBuilder(unlit=True, alpha=True)
    b.add_primitive(
        [(x0, y1, 0.0), (x1, y1, 0.0), (x1, y0, 0.0), (x0, y0, 0.0)],
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        [0, 2, 1, 0, 3, 2],
        texture=tex_bytes)
    return to_b3dm(b.finish())


def fetch_backend_params(backend, timeout=8):
    """从后端 /files/dom-imagery.json 读已保存的配准参数（DomImagery 页面）。"""
    url = backend.rstrip('/') + '/files/dom-imagery.json'
    with urllib.request.urlopen(url, timeout=timeout) as res:
        return json.loads(res.read().decode('utf-8'))


def convert_tif_plane(tif_path, out_dir, center_lon, center_lat, rotation=0.0,
                      width_meters=3000.0, height=0.0, tex_max=4096,
                      threshold=BLACK_THRESHOLD, fmt='png', cell_max=2048,
                      verbose=True):
    t0 = time.time()
    if height <= 0:
        height = 1.0  # 与地面（椭球高 0）完全共面会深度冲突
    im = load_texture(tif_path, tex_max, threshold, fmt)
    img_w, img_h = im.size
    h_m = width_meters * img_h / img_w
    hw, hh = width_meters / 2.0, h_m / 2.0
    os.makedirs(out_dir, exist_ok=True)

    transform = enu_to_ecef_transform(center_lat, center_lon, height, rotation)
    radius = math.hypot(hw, hh)
    zhalf = max(1.0, width_meters * 0.0002)
    whole_box = [0, 0, 0, hw, 0, 0, 0, hh, 0, 0, 0, zhalf]

    nx = max(1, math.ceil(img_w / cell_max))
    ny = max(1, math.ceil(img_h / cell_max))
    n_files = 0
    total_bytes = 0

    if nx == 1 and ny == 1:
        tex = encode_image(im, fmt)
        data = build_plane_b3dm(width_meters, h_m, tex)
        with open(os.path.join(out_dir, 'plane.b3dm'), 'wb') as f:
            f.write(data)
        tileset = {
            'asset': {'gltfUpAxis': 'Z', 'version': '1.0'},
            'geometricError': max(100, math.ceil(radius * 2)),
            'root': {
                'transform': transform,
                'boundingVolume': {'box': whole_box},
                'geometricError': 0,
                'content': {'uri': 'plane.b3dm'},
            },
        }
        n_files, total_bytes = 1, len(data)
        if verbose:
            print('纹理 %dx%d（%s）单平面 %.1f MB，%.1fs' %
                  (img_w, img_h, fmt, len(data) / 1048576, time.time() - t0))
    else:
        # 根节点：整幅低清总览；子块：网格高清贴图（REPLACE 细化）
        ov_w = min(1024, img_w)
        ov_h = max(1, round(img_h * ov_w / img_w))
        ov = im.resize((ov_w, ov_h), Image.LANCZOS)
        data = build_plane_b3dm(width_meters, h_m, encode_image(ov, fmt))
        with open(os.path.join(out_dir, 'overview.b3dm'), 'wb') as f:
            f.write(data)
        n_files, total_bytes = 1, len(data)

        cw, ch = width_meters / nx, h_m / ny
        px_w, px_h = img_w / nx, img_h / ny
        children = []
        for j in range(ny):  # 行：图像自上而下 = 北 → 南
            y1 = hh - j * ch
            y0 = hh - (j + 1) * ch
            for i in range(nx):  # 列：图像自左向右 = 西 → 东
                x0 = -hw + i * cw
                x1 = -hw + (i + 1) * cw
                cell = im.crop((round(i * px_w), round(j * px_h),
                                round((i + 1) * px_w), round((j + 1) * px_h)))
                data = build_cell_b3dm(x0, x1, y0, y1, encode_image(cell, fmt))
                uri = 'cell_r%02dc%02d.b3dm' % (j, i)
                with open(os.path.join(out_dir, uri), 'wb') as f:
                    f.write(data)
                n_files += 1
                total_bytes += len(data)
                cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
                children.append({
                    'boundingVolume': {'box': [cx, cy, 0, cw / 2, 0, 0,
                                               0, ch / 2, 0, 0, 0, zhalf]},
                    'geometricError': 0,
                    'content': {'uri': uri},
                })
        # SSE=16 下细化距离≈GE×58m；总览在 ~radius 米外即可被格网替换
        ge_root = max(32, round(radius * 0.02))
        tileset = {
            'asset': {'gltfUpAxis': 'Z', 'version': '1.0'},
            'geometricError': max(100, math.ceil(radius * 2)),
            'root': {
                'transform': transform,
                'boundingVolume': {'box': whole_box},
                'refine': 'REPLACE',
                'geometricError': ge_root,
                'content': {'uri': 'overview.b3dm'},
                'children': children,
            },
        }
        if verbose:
            print('纹理 %dx%d → 网格 %dx%d 块 + 总览，共 %d 文件 %.1f MB，%.1fs' %
                  (img_w, img_h, nx, ny, n_files, total_bytes / 1048576,
                   time.time() - t0))

    out = os.path.join(out_dir, 'tileset.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(tileset, f, ensure_ascii=False, separators=(',', ':'))
    if verbose:
        print('中心 (%.6f, %.6f) 旋转 %.2f° 高度 %.2fm -> %s' %
              (center_lon, center_lat, rotation, height, out))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='geoconvert tif',
        description='TIF 正射影像 → 贴图 3D 平面（3D Tiles b3dm）')
    ap.add_argument('tif', help='TIF 影像路径')
    ap.add_argument('output', help='输出目录')
    ap.add_argument('--center', help="中心经纬度 'lon,lat'（WGS-84）")
    ap.add_argument('--rotation', type=float, default=None,
                    help='旋转角（度，北偏东顺时针为正）')
    ap.add_argument('--width', type=float, default=None,
                    help='影像对应的地面宽度（米）')
    ap.add_argument('--height', type=float, default=None,
                    help='平面离地高度（米，≤0 自动抬升至 1 米）')
    ap.add_argument('--tex-max', type=int, default=4096, help='纹理最大边像素')
    ap.add_argument('--cell-max', type=int, default=2048,
                    help='网格块纹理最大边像素，超过则切块（0=不切块）')
    ap.add_argument('--threshold', type=int, default=BLACK_THRESHOLD,
                    help='黑边判定阈值')
    ap.add_argument('--format', choices=['png', 'jpeg'], default='png',
                    help='png=黑边透明（默认），jpeg=更小但黑角保留')
    ap.add_argument('--backend', help='后端地址：从 /files/dom-imagery.json 读参数'
                    '（center/rotation/width/height 未显式给出时生效）')
    ap.add_argument('-q', '--quiet', action='store_true')
    args = ap.parse_args(argv)

    lon, lat, rot, width, height = None, None, None, None, None
    if args.backend:
        try:
            saved = fetch_backend_params(args.backend)
            lon = float(saved.get('centerLon', 0.0))
            lat = float(saved.get('centerLat', 0.0))
            rot = float(saved.get('rotation', 0.0))
            width = float(saved.get('widthMeters', 0.0)) or None
            height = float(saved.get('height', 0.0))
        except Exception as e:
            print('后端参数读取失败（%s），使用命令行参数' % e)
    if args.center:
        a, b = args.center.split(',')
        lon, lat = float(a), float(b)
    if args.rotation is not None:
        rot = args.rotation
    if args.width is not None:
        width = args.width
    if args.height is not None:
        height = args.height
    if lon is None or lat is None:
        ap.error('必须指定 --center lon,lat 或提供可用的 --backend')
    if rot is None:
        rot = 0.0
    if height is None:
        height = 0.0
    if not width or width <= 0:
        ap.error('地面宽度必须为正数（--width 或后端 widthMeters）')

    convert_tif_plane(args.tif, args.output, lon, lat, rot, width, height,
                      args.tex_max, args.threshold, args.format,
                      cell_max=args.cell_max or 10 ** 9,
                      verbose=not args.quiet)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
