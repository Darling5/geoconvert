# -*- coding: utf-8 -*-
"""TIF 正射影像 → 贴图 3D 平面（3D Tiles b3dm，三级 LOD 金字塔）。

把影像贴到对应地面尺寸的 3D 平面（unlit 材质、黑边转透明），
复用应用内 3D 模型调整控件（XYZ 轴/旋转/斜移/缩放/透明度/保存）。

LOD 金字塔（纹理任一边超过 --cell-max 默认 2048px 时启用）：
  L0 总览   整幅 ≤1024px（root content，REPLACE 细化）
  L1 中清   每块覆盖 2×2 个 L2 块，纹理 ≤1024px（REPLACE 细化）
  L2 高清   原分辨率上限 tex_max（默认 16384px），网格块 ≤cell_max
远视角只加载总览，中距离换中清块，拉近后按视野加载所在高清块；
L2 网格 ≤2×2 时 L1 与总览同级，自动退化为两级；单块时为单平面。

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


def _black_fill_transparent(im):
    """a==0 像素的 RGB 填黑（jpeg 黑角、png 透明区 RGB 干净），原地修改。

    Pillow ≥9.1 对 RGBA 缩放内部已预乘，半透明边缘色无背景渗色，无需修正。
    """
    a = im.getchannel('A')
    inv = a.point(lambda v: 255 if v == 0 else 0)
    im.paste((0, 0, 0, 0), mask=inv)
    return im


def open_base(tif_path):
    """TIF → 全分辨率 RGBA/RGB（不降采样）。返回 (im, use_alpha)。

    自带 alpha 的 TIF（DJI Terra / Pix4D 等 DOM 导出，无数据区是纯白 RGB +
    alpha=0）沿用其 alpha 通道——丢 alpha 透明底会变实心白边。
    """
    src = Image.open(tif_path)
    use_alpha = False
    if src.mode in ('RGBA', 'LA', 'PA') or (src.mode == 'P' and 'transparency' in src.info):
        if src.mode != 'RGBA':
            src = src.convert('RGBA')
        if src.histogram()[768] > 0:  # 存在全透明像素：TIF 自带边缘透明
            use_alpha = True
    if not use_alpha and src.mode != 'RGB':
        src = src.convert('RGB')
    return src, use_alpha


def finish_level(im, use_alpha, threshold, fmt):
    """单级纹理收尾：透明区填黑 / 近黑边缘转透明。返回编码用 Image。"""
    if use_alpha:
        im = _black_fill_transparent(im)
        if fmt == 'png':
            return im
        return im.convert('RGB')  # jpeg：透明区已填黑，黑角保留
    if im.mode != 'RGB':
        im = im.convert('RGB')
    if fmt == 'png':
        im = black_to_transparent(im, threshold)
    return im


def load_texture(tif_path, tex_max, threshold, fmt):
    """TIF → 降采样到 tex_max →（png）边缘转透明，返回 PIL Image（单级旧接口）。"""
    im, use_alpha = open_base(tif_path)
    w, h = im.size
    scale = tex_max / max(w, h)
    if scale < 1:
        im = im.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                       Image.LANCZOS)
    return finish_level(im, use_alpha, threshold, fmt)


def encode_image(im, fmt):
    buf = io.BytesIO()
    if fmt == 'png':
        im.save(buf, format='PNG', compress_level=6)
    else:
        im.save(buf, format='JPEG', quality=85)
    return buf.getvalue()


def build_plane_b3dm(w_m, h_m, tex_bytes, tiles11=False):
    """单四边形贴图平面（ENU 原始坐标，中心在原点，z=0，法线朝上）。"""
    hw, hh = w_m / 2.0, h_m / 2.0
    # v0 西北(图像左上) v1 东北(右上) v2 东南(右下) v3 西南(左下)
    b = GlbBuilder(unlit=True, alpha=True)
    b.add_primitive(
        [(-hw, hh, 0.0), (hw, hh, 0.0), (hw, -hh, 0.0), (-hw, -hh, 0.0)],
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        [0, 2, 1, 0, 3, 2],
        texture=tex_bytes)
    glb = b.finish(yup=tiles11)
    return glb if tiles11 else to_b3dm(glb)


def build_cell_b3dm(x0, x1, y0, y1, tex_bytes, tiles11=False):
    """网格块平面：ENU 坐标 (x0..x1)×(y0..y1)，z=0，UV 全幅映射裁出的纹理。"""
    # v0 西北(左上) v1 东北(右上) v2 东南(右下) v3 西南(左下)
    b = GlbBuilder(unlit=True, alpha=True)
    b.add_primitive(
        [(x0, y1, 0.0), (x1, y1, 0.0), (x1, y0, 0.0), (x0, y0, 0.0)],
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        [0, 2, 1, 0, 3, 2],
        texture=tex_bytes)
    glb = b.finish(yup=tiles11)
    return glb if tiles11 else to_b3dm(glb)


def _box_edges(box):
    """box（中心 + 半边长）→ (x0, x1, y0, y1)。"""
    return (box[0] - box[3], box[0] + box[3],
            box[1] - box[7], box[1] + box[7])


def fetch_backend_params(backend, timeout=8):
    """从后端 /files/dom-imagery.json 读已保存的配准参数（DomImagery 页面）。"""
    url = backend.rstrip('/') + '/files/dom-imagery.json'
    with urllib.request.urlopen(url, timeout=timeout) as res:
        return json.loads(res.read().decode('utf-8'))


def convert_tif_plane(tif_path, out_dir, center_lon, center_lat, rotation=0.0,
                      width_meters=3000.0, height=0.0, tex_max=16384,
                      threshold=BLACK_THRESHOLD, fmt='png', cell_max=2048,
                      verbose=True, tiles11=False):
    t0 = time.time()
    if height <= 0:
        height = 1.0  # 与地面（椭球高 0）完全共面会深度冲突
    base, use_alpha = open_base(tif_path)
    bw, bh = base.size
    h_m = width_meters * bh / bw
    hw, hh = width_meters / 2.0, h_m / 2.0
    os.makedirs(out_dir, exist_ok=True)
    # 1.1：glb 内容为标准 Y-up，不带 1.0 前私有的 gltfUpAxis
    asset = {'version': '1.1'} if tiles11 else {'gltfUpAxis': 'Z', 'version': '1.0'}
    ext = 'glb' if tiles11 else 'b3dm'

    transform = enu_to_ecef_transform(center_lat, center_lon, height, rotation)
    radius = math.hypot(hw, hh)
    zhalf = max(1.0, width_meters * 0.0002)
    whole_box = [0, 0, 0, hw, 0, 0, 0, hh, 0, 0, 0, zhalf]

    # L2 高清级：原分辨率上限 tex_max；边缘透明处理在本级做一次，
    # L1/L0 从处理后的 L2 取材（RGBA 缩放内部预乘，各级边缘一致）
    scale = tex_max / max(bw, bh)
    if scale < 1:
        l2 = base.resize((max(1, round(bw * scale)), max(1, round(bh * scale))),
                         Image.LANCZOS)
        base = None  # 释放整幅解码缓冲（超大图）
    else:
        l2 = base
        base = None
    l2 = finish_level(l2, use_alpha, threshold, fmt)
    l2w, l2h = l2.size

    # 整数网格边界（相邻块共享边界像素行/列，块间无缝）
    nx = max(1, math.ceil(l2w / cell_max))
    ny = max(1, math.ceil(l2h / cell_max))
    xs = [round(i * l2w / nx) for i in range(nx + 1)]
    ys = [round(j * l2h / ny) for j in range(ny + 1)]
    n_files = 0
    total_bytes = 0

    def uv_box(u0, v0, u1, v1):
        """图像像素区 → ENU box（图像左上=西北，x 向东 y 向北）。"""
        x0 = -hw + u0 / l2w * width_meters
        x1 = -hw + u1 / l2w * width_meters
        y1 = hh - v0 / l2h * h_m
        y0 = hh - v1 / l2h * h_m
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return [cx, cy, 0, (x1 - x0) / 2, 0, 0, 0, (y1 - y0) / 2, 0, 0, 0, zhalf]

    def emit(name, u0, v0, u1, v1, box):
        data = build_cell_b3dm(*_box_edges(box), encode_image(
            l2.crop((u0, v0, u1, v1)), fmt), tiles11)
        with open(os.path.join(out_dir, name), 'wb') as f:
            f.write(data)
        return len(data)

    if nx == 1 and ny == 1:
        tex = encode_image(l2, fmt)
        data = build_plane_b3dm(width_meters, h_m, tex, tiles11)
        with open(os.path.join(out_dir, 'plane.' + ext), 'wb') as f:
            f.write(data)
        tileset = {
            'asset': asset,
            'geometricError': max(100, math.ceil(radius * 2)),
            'root': {
                'transform': transform,
                'boundingVolume': {'box': whole_box},
                'geometricError': 0,
                'content': {'uri': 'plane.' + ext},
            },
        }
        n_files, total_bytes = 1, len(data)
        if verbose:
            print('纹理 %dx%d（%s）单平面 %.1f MB，%.1fs' %
                  (l2w, l2h, fmt, len(data) / 1048576, time.time() - t0))
    else:
        # L0 总览：整幅 ≤1024px
        ov_w = min(1024, l2w)
        ov_h = max(1, round(l2h * ov_w / l2w))
        ov = l2.resize((ov_w, ov_h), Image.LANCZOS)
        data = build_plane_b3dm(width_meters, h_m, encode_image(ov, fmt), tiles11)
        with open(os.path.join(out_dir, 'overview.' + ext), 'wb') as f:
            f.write(data)
        n_files, total_bytes = 1, len(data)
        del ov

        # L2 高清网格块（叶子，GE=0）
        l2_tiles = {}
        for j in range(ny):
            for i in range(nx):
                uri = 'cell_r%02dc%02d.%s' % (j, i, ext)
                total_bytes += emit(uri, xs[i], ys[j], xs[i + 1], ys[j + 1],
                                    uv_box(xs[i], ys[j], xs[i + 1], ys[j + 1]))
                n_files += 1
                l2_tiles[(j, i)] = {
                    'boundingVolume': {'box': uv_box(
                        xs[i], ys[j], xs[i + 1], ys[j + 1])},
                    'geometricError': 0,
                    'content': {'uri': uri},
                }

        # L1 中清级：每块覆盖 2×2 个 L2 块，纹理 ≤1024px；
        # L2 网格 ≤2×2 时 L1 与总览同级 → 退化为两级
        mx, my = math.ceil(nx / 2), math.ceil(ny / 2)
        # SSE=16 下细化距离≈GE×58m：中清→高清在 ~radius 内，总览→中清在 ~4.6×radius 外
        ge_mid = max(16, radius * 0.02)
        ge_root = max(32, radius * 0.02 if (mx == 1 and my == 1)
                      else radius * 0.08)

        if mx == 1 and my == 1:
            children = [l2_tiles[(j, i)] for j in range(ny) for i in range(nx)]
            ge_mid = None  # 无中清级
        else:
            children = []
            for J in range(my):
                for I in range(mx):
                    i0, i1 = 2 * I, min(2 * I + 2, nx)
                    j0, j1 = 2 * J, min(2 * J + 2, ny)
                    u0, u1 = xs[i0], xs[i1]
                    v0, v1 = ys[j0], ys[j1]
                    uri = 'cellm_r%02dc%02d.%s' % (J, I, ext)
                    cw = min(1024, u1 - u0)
                    ch = max(1, round((v1 - v0) * cw / max(1, u1 - u0)))
                    cell = l2.crop((u0, v0, u1, v1)).resize((cw, ch), Image.LANCZOS)
                    data = build_cell_b3dm(*_box_edges(uv_box(u0, v0, u1, v1)),
                                           encode_image(cell, fmt), tiles11)
                    with open(os.path.join(out_dir, uri), 'wb') as f:
                        f.write(data)
                    n_files += 1
                    total_bytes += len(data)
                    box = uv_box(u0, v0, u1, v1)
                    children.append({
                        'boundingVolume': {'box': box},
                        'refine': 'REPLACE',
                        'geometricError': ge_mid,
                        'content': {'uri': uri},
                        'children': [l2_tiles[(j, i)]
                                     for j in range(j0, j1) for i in range(i0, i1)],
                    })

        tileset = {
            'asset': asset,
            'geometricError': max(100, math.ceil(radius * 2)),
            'root': {
                'transform': transform,
                'boundingVolume': {'box': whole_box},
                'refine': 'REPLACE',
                'geometricError': ge_root,
                'content': {'uri': 'overview.' + ext},
                'children': children,
            },
        }
        if verbose:
            if ge_mid is None:
                print('纹理 %dx%d → 网格 %dx%d 块 + 总览（两级），共 %d 文件 %.1f MB，%.1fs' %
                      (l2w, l2h, nx, ny, n_files, total_bytes / 1048576,
                       time.time() - t0))
            else:
                print('纹理 %dx%d → 三级金字塔：总览 + 中清 %dx%d + 高清 %dx%d 块，'
                      '共 %d 文件 %.1f MB，%.1fs' %
                      (l2w, l2h, mx, my, nx, ny, n_files, total_bytes / 1048576,
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
    ap.add_argument('--tex-max', type=int, default=16384,
                    help='金字塔高清级整幅最大边像素（默认 16384，三级 LOD）')
    ap.add_argument('--cell-max', type=int, default=2048,
                    help='网格块纹理最大边像素，超过则切块（0=不切块）')
    ap.add_argument('--threshold', type=int, default=BLACK_THRESHOLD,
                    help='黑边判定阈值')
    ap.add_argument('--format', choices=['png', 'jpeg'], default='png',
                    help='png=边缘透明（默认，alpha 或近黑边），jpeg=更小但黑角保留')
    ap.add_argument('--backend', help='后端地址：从 /files/dom-imagery.json 读参数'
                    '（center/rotation/width/height 未显式给出时生效）')
    ap.add_argument('--tiles-version', choices=['1.0', '1.1'], default='1.0',
                    help='3D Tiles 版本：1.0=b3dm（默认），1.1=glb 内容（需 Cesium 1.83+）')
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
                      verbose=not args.quiet, tiles11=args.tiles_version == '1.1')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
