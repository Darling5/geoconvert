# -*- coding: utf-8 -*-
"""geoconvert 共享参数逻辑：格式识别、参数校验、CLI 参数组装。"""
import os

FORMATS = ('OBJ', 'OSGB', 'TIF')

FMT_HINTS = {
    'OBJ': '多分块目录自动合并 · 超 25 万三角形空间切块 → 三级 LOD',
    'OSGB': 'Smart3D 倾斜摄影 → b3dm LOD 树',
    'TIF': '正射影像 → 贴图 3D 平面（自动网格切块）',
}

GEO_HINTS = {
    'OBJ': '留空经纬度 = 赤道 ENU，导入系统后用「调整位置」功能移动',
    'OSGB': '留空 = 自动读取数据目录 metadata.xml 定位',
    'TIF': '中心 = 影像中心点 WGS-84 经纬度，地面宽度 = 影像覆盖的东西向真实米数',
}


def _dir_has_obj(p):
    """顶层或一级子目录内是否存在 .obj（与 objconv.find_obj_blocks 的发现规则一致）。"""
    try:
        for f in os.listdir(p):
            if f.lower().endswith('.obj'):
                return True
        for name in os.listdir(p):
            d = os.path.join(p, name)
            if os.path.isdir(d):
                for f in os.listdir(d):
                    if f.lower().endswith('.obj'):
                        return True
    except OSError:
        pass
    return False


def detect_format(path):
    """按扩展名/目录内容识别输入格式；识别不了返回 None。

    目录扫描优先级：.osgb → OSGB；.obj（含一级子目录）→ OBJ；
    仅 metadata.xml → OSGB 兜底（Smart3D 根目录，osgb 藏得更深）。
    注意 ContextCapture 多分块 OBJ 根目录也带 metadata.xml，不能单凭它判 OSGB。
    """
    p = str(path).strip()
    if not p:
        return None
    low = p.lower()
    if low.endswith('.obj'):
        return 'OBJ'
    if low.endswith(('.tif', '.tiff')):
        return 'TIF'
    if os.path.isdir(p):
        has_obj = has_meta = False
        for root, dirs, files in os.walk(p):
            rel = os.path.relpath(root, p)
            if rel != '.' and rel.count(os.sep) >= 2:  # 只扫浅 3 层，避免大目录卡顿
                dirs[:] = []
                continue
            for f in files:
                fl = f.lower()
                if fl.endswith('.osgb'):
                    return 'OSGB'
                if fl.endswith('.obj'):
                    has_obj = True
                elif fl == 'metadata.xml':
                    has_meta = True
        if has_obj:
            return 'OBJ'
        if has_meta:
            return 'OSGB'
    return None


def validate(fmt, src, dst, loc_mode='ll', lat='', lon='', ts='', center='', width='',
             height='', max_tris='', tex_fmt='png', tiles='1.0'):
    """校验表单参数；返回 (vals, None) 或 (None, 错误消息)。"""
    fmt = str(fmt).upper()
    if fmt not in FORMATS:
        return None, '未知格式：%s' % fmt
    src = str(src).strip()
    dst = str(dst).strip()
    lat = str(lat).strip()
    lon = str(lon).strip()
    ts = str(ts).strip()
    center = str(center).strip().replace('，', ',')
    width = str(width).strip()
    height = str(height).strip()
    max_tris = str(max_tris).strip()
    tiles = str(tiles).strip() or '1.0'

    if not src:
        return None, '请选择输入文件/目录'
    if not os.path.exists(src):
        return None, '输入路径不存在：%s' % src
    if not dst:
        return None, '请选择输出目录'
    if fmt == 'TIF' and not os.path.isfile(src):
        return None, 'TIF 输入应为 .tif 影像文件'
    if fmt == 'OBJ' and not os.path.isfile(src):
        if not os.path.isdir(src):
            return None, 'OBJ 输入应为 .obj 文件或多分块根目录'
        if not _dir_has_obj(src):
            return None, 'OBJ 目录内未找到 .obj 文件（支持顶层或每子目录一个 OBJ）'
    if fmt == 'OSGB' and not os.path.isdir(src):
        return None, 'OSGB 输入应为数据目录'
    if fmt == 'TIF':
        parts = [x.strip() for x in center.split(',')]
        if not center or len(parts) != 2:
            return None, '请填写影像中心经纬度（lon,lat），例如 116.3,39.9'
        try:
            float(parts[0])
            float(parts[1])
        except ValueError:
            return None, '中心经纬度必须是数字'
        if not width:
            return None, '请填写地面宽度（米）'
        try:
            if float(width) <= 0:
                raise ValueError
        except ValueError:
            return None, '地面宽度必须是正数'
    else:
        if loc_mode == 'ts':
            if not ts:
                return None, '请选择参考 tileset.json，或改用经纬度定位'
            if not os.path.isfile(ts):
                return None, '参考 tileset 不存在：%s' % ts
        elif lat or lon:
            if not (lat and lon):
                return None, '经纬度需同时填写纬度和经度'
            try:
                float(lat)
                float(lon)
            except ValueError:
                return None, '经纬度必须是数字'
    if height:
        try:
            float(height)
        except ValueError:
            return None, '离地高度必须是数字'
    if max_tris:
        try:
            int(max_tris)
        except ValueError:
            return None, '单块最大三角形数必须是整数'
    return dict(fmt=fmt, src=os.path.abspath(src), dst=os.path.abspath(dst),
                loc_mode=loc_mode, lat=lat, lon=lon, ts=ts, center=center,
                width=width, height=height, max_tris=max_tris,
                tex_fmt=str(tex_fmt).lower() if str(tex_fmt).lower() in ('png', 'jpeg') else 'png',
                tiles=tiles if tiles in ('1.0', '1.1') else '1.0'), None


def build_argv(v):
    """把 validate() 的结果组装成 geoconvert CLI 参数列表。"""
    argv = [v['fmt'].lower(), v['src']]
    if v['fmt'] == 'OSGB':
        argv += ['--out', v['dst']]
    else:
        argv.append(v['dst'])
    if v['loc_mode'] == 'ts' and v['fmt'] != 'TIF' and v['ts']:
        argv += ['--transform-from', v['ts']]
    elif v['fmt'] != 'TIF' and v['lat'] and v['lon']:
        # TIF 的 CLI 只认 --center，不认 --lat/--lon（表单残留值直接忽略）
        argv += ['--lat', v['lat'], '--lon', v['lon']]
    if v['fmt'] == 'TIF':
        if v['center']:
            argv += ['--center', v['center']]
        if v['width']:
            argv += ['--width', v['width']]
        argv += ['--format', v['tex_fmt']]
    elif v['fmt'] == 'OBJ' and v['max_tris']:
        argv += ['--max-tris', v['max_tris']]
    if v['height']:
        argv += ['--height', v['height']]
    if v.get('tiles') == '1.1':
        argv += ['--tiles-version', '1.1']
    return argv
