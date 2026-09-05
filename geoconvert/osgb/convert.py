# -*- coding: utf-8 -*-
"""OSGB (Smart3D/ContextCapture 倾斜摄影) → 3D Tiles (b3dm) 转换器。

用法:
    python -m geoconvert.osgb.convert <OSGB根目录> --out <输出目录>
        [--height 0] [--flip-v] [--only Tile_+002_+003]

OSGB 根目录需含 metadata.xml（SRS=EPSG:326xx/327xx UTM）与 Data/Tile_*/Tile_*.osgb。
输出 tileset.json + 每个源文件一个 b3dm：
- 局部坐标保持 OSGB 原始 ENU 坐标（x=东, y=北, z=上，相对 SRSOrigin）
- root.transform = ENU(SRSOrigin 经纬度, height) → ECEF（列主序 16 元素）
- LOD 层级复刻 PagedLOD 树，geometricError = 32·radius/像素阈值
"""
import argparse
import array
import json
import math
import os
import struct
import time
import xml.etree.ElementTree as ET

from .reader import read_osgb, OsgError

WGS84_A = 6378137.0
WGS84_F = 1.0 / 298.257223563
WGS84_E2 = WGS84_F * (2 - WGS84_F)
WGS84_EP2 = WGS84_E2 / (1 - WGS84_E2)
UTM_K0 = 0.9996


# ---------- 坐标工具 ----------

def utm_to_latlon(easting, northing, zone, northern=True):
    x = easting - 500000.0
    y = northing if northern else northing - 10000000.0
    m = y / UTM_K0
    mu = m / (WGS84_A * (1 - WGS84_E2 / 4 - 3 * WGS84_E2 ** 2 / 64 - 5 * WGS84_E2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - WGS84_E2)) / (1 + math.sqrt(1 - WGS84_E2))
    j1 = 3 * e1 / 2 - 27 * e1 ** 3 / 32
    j2 = 21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32
    j3 = 151 * e1 ** 3 / 96
    j4 = 1097 * e1 ** 4 / 512
    fp = mu + j1 * math.sin(2 * mu) + j2 * math.sin(4 * mu) + \
        j3 * math.sin(6 * mu) + j4 * math.sin(8 * mu)
    c1 = WGS84_EP2 * math.cos(fp) ** 2
    t1 = math.tan(fp) ** 2
    r1 = WGS84_A * (1 - WGS84_E2) / (1 - WGS84_E2 * math.sin(fp) ** 2) ** 1.5
    n1 = WGS84_A / math.sqrt(1 - WGS84_E2 * math.sin(fp) ** 2)
    d = x / (n1 * UTM_K0)
    lat = fp - (n1 * math.tan(fp) / r1) * (
        d ** 2 / 2
        - (5 + 3 * t1 + 10 * c1 - 4 * c1 ** 2 - 9 * WGS84_EP2) * d ** 4 / 24
        + (61 + 90 * t1 + 298 * c1 + 45 * t1 ** 2 - 252 * WGS84_EP2 - 3 * c1 ** 2) * d ** 6 / 720)
    lon = math.radians(zone * 6 - 183) + (
        d - (1 + 2 * t1 + c1) * d ** 3 / 6
        + (5 - 2 * c1 + 28 * t1 - 3 * c1 ** 2 + 8 * WGS84_EP2 + 24 * t1 ** 2) * d ** 5 / 120) / math.cos(fp)
    return math.degrees(lat), math.degrees(lon)


def geodetic_to_ecef(lat_deg, lon_deg, h):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    s = math.sin(lat)
    n = WGS84_A / math.sqrt(1 - WGS84_E2 * s * s)
    return (
        (n + h) * math.cos(lat) * math.cos(lon),
        (n + h) * math.cos(lat) * math.sin(lon),
        (n * (1 - WGS84_E2) + h) * math.sin(lat),
    )


def enu_to_ecef_transform(lat_deg, lon_deg, h):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sl, cl = math.sin(lon), math.cos(lon)
    sp, cp = math.sin(lat), math.cos(lat)
    org = geodetic_to_ecef(lat_deg, lon_deg, h)
    return [
        -sl, cl, 0.0, 0.0,
        -sp * cl, -sp * sl, cp, 0.0,
        cp * cl, cp * sl, sp, 0.0,
        org[0], org[1], org[2], 1.0,
    ]


def read_metadata(osgb_root):
    for cand in (osgb_root, os.path.dirname(os.path.abspath(osgb_root))):
        p = os.path.join(cand, 'metadata.xml')
        if os.path.isfile(p):
            root = ET.parse(p).getroot()
            srs = (root.findtext('SRS') or '').strip()
            origin_txt = (root.findtext('SRSOrigin') or '').strip()
            if not srs or not origin_txt:
                raise OsgError('metadata.xml 缺少 SRS/SRSOrigin: %s' % p)
            parts = [float(v) for v in origin_txt.replace(',', ' ').split()]
            if len(parts) < 2:
                raise OsgError('SRSOrigin 解析失败: %r' % origin_txt)
            return {'srs': srs, 'origin': (parts[0], parts[1], parts[2] if len(parts) > 2 else 0.0)}
    raise OsgError('未找到 metadata.xml（在 %s 及其父目录）' % osgb_root)


def transform_from_tileset(path):
    """读取参考 tileset.json 的 root.transform（16 元列表）。"""
    with open(path, 'r', encoding='utf-8') as f:
        t = json.load(f)
    tr = t.get('root', {}).get('transform')
    if not tr or len(tr) != 16:
        raise OsgError('%s 缺少有效的 root.transform' % path)
    return [float(v) for v in tr]


def parse_srs(srs):
    s = srs.strip().upper()
    if s.startswith('EPSG:'):
        try:
            code = int(s[5:])
        except ValueError:
            code = 0
        if 32601 <= code <= 32660:
            return code - 32600, True
        if 32701 <= code <= 32760:
            return code - 32700, False
    raise OsgError('不支持的 SRS %r（当前仅支持 UTM EPSG:326xx/327xx）' % srs)


def find_tile_roots(osgb_root):
    data = os.path.join(osgb_root, 'Data')
    if not os.path.isdir(data):
        data = osgb_root
    roots = []
    for name in sorted(os.listdir(data)):
        d = os.path.join(data, name)
        if os.path.isdir(d):
            f = os.path.join(d, name + '.osgb')
            if os.path.isfile(f):
                roots.append(f)
    if not roots:
        for name in sorted(os.listdir(data)):
            if name.lower().endswith('.osgb'):
                roots.append(os.path.join(data, name))
    if not roots:
        raise OsgError('%s 下未找到瓦片根文件' % data)
    return roots


# ---------- 矩阵工具（OSG 行主序，v' = M·v） ----------

def _mat_mul(a, b):
    return [
        [sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)]
        for i in range(4)
    ]


def _mat_vec(m, v):
    return tuple(
        m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] + m[i][3]
        for i in range(3)
    )


# ---------- 图元三角化 ----------

def _triangulate(prim):
    if 'indices' in prim:
        idx = prim['indices']
    elif 'count' in prim:  # DrawArrays
        idx = list(range(prim['first'], prim['first'] + prim['count']))
    elif 'lengths' in prim:  # DrawArrayLengths
        idx = []
        p = prim['first']
        for ln in prim['lengths']:
            idx.extend(range(p, p + ln))
            p += ln
    else:
        return []
    mode = prim['mode']
    if mode == 4:  # TRIANGLES
        return idx
    if mode == 5:  # TRIANGLE_STRIP（doubleSided，绕序不翻转）
        out = []
        for i in range(len(idx) - 2):
            out.extend((idx[i], idx[i + 1], idx[i + 2]))
        return out
    if mode == 6:  # TRIANGLE_FAN
        out = []
        for i in range(1, len(idx) - 1):
            out.extend((idx[0], idx[i], idx[i + 1]))
        return out
    return []


def _image_mime(data):
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:4] == b'\x89PNG':
        return 'image/png'
    return None


# ---------- glTF / b3dm 构建 ----------

class GlbBuilder:
    def __init__(self, flip_v):
        self.flip_v = flip_v
        self.buffer_views = []
        self.accessors = []
        self.bin_parts = []
        self.bin_len = 0
        self.images = []
        self.materials = []
        self.textures = []
        self.samplers = [{'magFilter': 9729, 'minFilter': 9987,
                          'wrapS': 10497, 'wrapT': 10497}]
        self.prims = []
        self._tex_by_img = {}
        self._plain_mat = None
        self.pos_min = None
        self.pos_max = None

    def _push(self, data):
        pad = (4 - self.bin_len % 4) % 4
        if pad:
            self.bin_parts.append(b'\x00' * pad)
            self.bin_len += pad
        start = self.bin_len
        self.bin_parts.append(data)
        self.bin_len += len(data)
        return start

    def _tex_material(self, geom):
        tex_obj = None
        if geom.state_set:
            for unit in geom.state_set.texture_attributes:
                for o in unit:
                    if o is not None and getattr(o, 'image', None) and o.image.data:
                        tex_obj = o
                        break
                if tex_obj:
                    break
        if tex_obj is None:
            if self._plain_mat is None:
                self._plain_mat = len(self.materials)
                self.materials.append({
                    'pbrMetallicRoughness': {
                        'baseColorFactor': [0.85, 0.85, 0.85, 1.0],
                        'metallicFactor': 0.0, 'roughnessFactor': 1.0},
                    'doubleSided': True})
            return self._plain_mat

        img = tex_obj.image
        key = id(img)
        if key in self._tex_by_img:
            return self._tex_by_img[key]
        mime = _image_mime(img.data)
        if mime is None:
            if self._plain_mat is None:
                self._plain_mat = len(self.materials)
                self.materials.append({
                    'pbrMetallicRoughness': {
                        'baseColorFactor': [0.85, 0.85, 0.85, 1.0],
                        'metallicFactor': 0.0, 'roughnessFactor': 1.0},
                    'doubleSided': True})
            return self._plain_mat
        start = self._push(img.data)
        self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                  'byteLength': len(img.data)})
        img_idx = len(self.images)
        self.images.append({'mimeType': mime, 'bufferView': len(self.buffer_views) - 1})
        tex_idx = len(self.textures)
        self.textures.append({'sampler': 0, 'source': img_idx})
        mat_idx = len(self.materials)
        self.materials.append({
            'pbrMetallicRoughness': {
                'baseColorTexture': {'index': tex_idx},
                'metallicFactor': 0.0, 'roughnessFactor': 1.0},
            'doubleSided': True})
        self._tex_by_img[key] = mat_idx
        return mat_idx

    def add_geometry(self, geom, matrix):
        verts = geom.vertices or ()
        if not verts:
            return
        indices = []
        for p in geom.primitives:
            indices.extend(_triangulate(p))
        if not indices:
            return
        if max(indices) >= len(verts):
            return  # 索引越界，脏数据跳过

        pos = array.array('f')
        mn = [1e30] * 3
        mx = [-1e30] * 3
        for v in verts:
            if matrix is not None:
                v = _mat_vec(matrix, v)
            pos.extend(v)
            for i in range(3):
                if v[i] < mn[i]:
                    mn[i] = v[i]
                if v[i] > mx[i]:
                    mx[i] = v[i]
        start = self._push(pos.tobytes())
        self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                  'byteLength': len(pos) * 4, 'target': 34962})
        self.accessors.append({'componentType': 5126, 'count': len(verts),
                               'type': 'VEC3', 'min': mn, 'max': mx,
                               'bufferView': len(self.buffer_views) - 1})
        pos_acc = len(self.accessors) - 1
        if self.pos_min is None:
            self.pos_min = mn
            self.pos_max = mx
        else:
            for i in range(3):
                self.pos_min[i] = min(self.pos_min[i], mn[i])
                self.pos_max[i] = max(self.pos_max[i], mx[i])

        attributes = {'POSITION': pos_acc}
        uvs = geom.texcoords[0] if geom.texcoords else None
        if uvs and len(uvs) == len(verts):
            uv = array.array('f')
            if self.flip_v:
                for t in uvs:
                    uv.extend((t[0], 1.0 - t[1]))
            else:
                for t in uvs:
                    uv.extend(t)
            start = self._push(uv.tobytes())
            self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                      'byteLength': len(uv) * 4, 'target': 34962})
            self.accessors.append({'componentType': 5126, 'count': len(uvs),
                                   'type': 'VEC2',
                                   'bufferView': len(self.buffer_views) - 1})
            attributes['TEXCOORD_0'] = len(self.accessors) - 1

        comp, fmt = (5123, 'H') if len(verts) < 65536 else (5125, 'I')
        idx = array.array(fmt, indices)
        start = self._push(idx.tobytes())
        self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                  'byteLength': len(idx) * idx.itemsize, 'target': 34963})
        self.accessors.append({'componentType': comp, 'count': len(indices),
                               'type': 'SCALAR', 'min': [min(indices)],
                               'max': [max(indices)],
                               'bufferView': len(self.buffer_views) - 1})

        self.prims.append({'attributes': attributes,
                           'indices': len(self.accessors) - 1,
                           'material': self._tex_material(geom), 'mode': 4})

    def finish(self):
        bin_data = b''.join(self.bin_parts)
        gltf = {
            'asset': {'generator': 'geoconvert-osgb', 'version': '2.0'},
            'scene': 0,
            'scenes': [{'nodes': [0]}],
            'nodes': [{'mesh': 0}],
            'meshes': [{'primitives': self.prims}],
            'accessors': self.accessors,
            'bufferViews': self.buffer_views,
            'buffers': [{'byteLength': self.bin_len}],
        }
        if self.materials:
            gltf['materials'] = self.materials
        if self.textures:
            gltf['textures'] = self.textures
            gltf['samplers'] = self.samplers
        if self.images:
            gltf['images'] = self.images
        return _glb(gltf, bin_data)


def _glb(gltf, bin_data):
    js = json.dumps(gltf, separators=(',', ':')).encode('utf-8')
    jpad = (4 - len(js) % 4) % 4
    if jpad:
        js += b' ' * jpad
    bpad = (4 - len(bin_data) % 4) % 4
    if bpad:
        bin_data += b'\x00' * bpad
    total = 12 + 8 + len(js) + 8 + len(bin_data)
    out = bytearray(total)
    struct.pack_into('<4sII', out, 0, b'glTF', 2, total)
    struct.pack_into('<I4s', out, 12, len(js), b'JSON')
    out[20:20 + len(js)] = js
    struct.pack_into('<I4s', out, 20 + len(js), len(bin_data), b'BIN\x00')
    out[28 + len(js):] = bin_data
    return bytes(out)


def _b3dm(glb):
    ft = b'{"BATCH_LENGTH":0}'.ljust(24, b' ')
    bt = b'{}'.ljust(8, b' ')
    total = 28 + len(ft) + len(bt) + len(glb)
    out = bytearray(total)
    struct.pack_into('<4sII', out, 0, b'b3dm', 1, total)
    struct.pack_into('<IIII', out, 12, len(ft), 0, len(bt), 0)
    out[28:28 + len(ft)] = ft
    out[28 + len(ft):28 + len(ft) + len(bt)] = bt
    out[28 + len(ft) + len(bt):] = glb
    return bytes(out)


# ---------- 包围盒工具 ----------

def _box_from_minmax(mn, mx):
    cx = [(mn[i] + mx[i]) / 2 for i in range(3)]
    return [cx[0], cx[1], cx[2],
            (mx[0] - mn[0]) / 2, 0, 0,
            0, (mx[1] - mn[1]) / 2, 0,
            0, 0, (mx[2] - mn[2]) / 2]


def _box_radius(box):
    return math.sqrt(box[3] ** 2 + box[7] ** 2 + box[11] ** 2)


def _union_boxes(boxes):
    it = iter(boxes)
    first = next(it, None)
    if first is None:
        return None
    mn = [first[0] - first[3], first[1] - first[7], first[2] - first[11]]
    mx = [first[0] + first[3], first[1] + first[7], first[2] + first[11]]
    for b in it:
        for i in range(3):
            mn[i] = min(mn[i], b[i * 3] - b[i * 3 + 3])
            mx[i] = max(mx[i], b[i * 3] + b[i * 3 + 3])
    return _box_from_minmax(mn, mx)


def _union2(a, b):
    if a is None:
        return b
    if b is None:
        return a
    return _union_boxes([a, b])


# ---------- 主转换器 ----------

def _safe_name(s):
    # Smart3D 瓦片名带 '+'（Tile_+002_+003）：部分静态服务器会把 '+' 二次编码或当空格，
    # 输出文件名/URI 一律去掉 '+'（与既有 tileset 命名约定 Tile_002_003 一致）
    return s.replace('+', '')


def _collect_geoms(nodes, matrix, out):
    for n in nodes:
        m = matrix
        if n.cls == 'osg::MatrixTransform' and n.matrix is not None:
            m = _mat_mul(n.matrix, matrix) if matrix is not None else n.matrix
        for d in n.drawables:
            if d.vertices:
                out.append((d, m))
        _collect_geoms(n.children, m, out)


class OsgbToTiles:
    def __init__(self, out_dir, flip_v=True, height=0.0, only=None, verbose=True,
                 transform=None):
        self.out_dir = out_dir
        self.flip_v = flip_v
        self.height = height
        self.only = only
        self.verbose = verbose
        self.transform_override = transform
        self.data_root = None
        self.transform = None
        self.visited = set()
        self.failures = []
        self.n_files = 0
        self.n_b3dm = 0
        self.n_bytes = 0

    def log(self, msg):
        if self.verbose:
            print(msg, flush=True)

    def convert(self, osgb_root):
        t0 = time.time()
        meta = read_metadata(osgb_root)
        zone, northern = parse_srs(meta['srs'])
        ox, oy, oz = meta['origin']
        lat, lon = utm_to_latlon(ox, oy, zone, northern)
        if self.transform_override is not None:
            self.transform = self.transform_override
        else:
            self.transform = enu_to_ecef_transform(lat, lon, self.height)
        self.log('SRS %s zone=%d%s origin=(%.1f, %.1f, %.1f) -> lat=%.6f lon=%.6f height=%.1f'
                 % (meta['srs'], zone, 'N' if northern else 'S', ox, oy, oz,
                    lat, lon, self.height))

        data = os.path.join(osgb_root, 'Data')
        self.data_root = data if os.path.isdir(data) else osgb_root
        roots = find_tile_roots(osgb_root)
        if self.only:
            roots = [r for r in roots if self.only in r]
        self.log('根瓦片: %d 个' % len(roots))

        tiles = []
        for i, rf in enumerate(roots):
            t = self._file_tile(rf, 0)
            if t:
                tiles.append(t)
            if (i + 1) % 8 == 0:
                self.log('  ...%d/%d 根瓦片 (%.0fs, %d b3dm)'
                         % (i + 1, len(roots), time.time() - t0, self.n_b3dm))
        if not tiles:
            raise OsgError('没有成功转换的瓦片')

        box = _union_boxes(t['box'] for t in tiles)
        ge = max(2.0 * _box_radius(box), max(t['ge'] for t in tiles))
        tileset = {
            'asset': {'version': '1.0', 'gltfUpAxis': 'Z'},
            'geometricError': ge,
            'root': {
                'transform': self.transform,
                'boundingVolume': {'box': box},
                'refine': 'ADD',
                'geometricError': ge,
                'children': [self._tile_json(t) for t in tiles],
            },
        }
        os.makedirs(self.out_dir, exist_ok=True)
        with open(os.path.join(self.out_dir, 'tileset.json'), 'w', encoding='utf-8') as f:
            json.dump(tileset, f, separators=(',', ':'))

        self.log('完成: %d 文件 / %d b3dm / %.1f MB, 失败 %d, 用时 %.0fs'
                 % (self.n_files, self.n_b3dm, self.n_bytes / 1048576.0,
                    len(self.failures), time.time() - t0))
        for fp, e in self.failures[:10]:
            self.log('  FAIL %s: %s' % (fp, e))
        return {'files': self.n_files, 'b3dm': self.n_b3dm,
                'bytes': self.n_bytes, 'failures': self.failures}

    def _file_tile(self, path, depth):
        if depth > 60:
            self.failures.append((path, 'depth limit'))
            return None
        key = os.path.normcase(os.path.abspath(path))
        if key in self.visited:
            self.failures.append((path, 'revisited (cycle?)'))
            return None
        self.visited.add(key)
        try:
            with open(path, 'rb') as f:
                node = read_osgb(f.read())
        except Exception as e:
            self.failures.append((path, str(e)))
            return None
        self.n_files += 1
        rel_dir = os.path.relpath(os.path.dirname(path), self.data_root)
        stem = os.path.basename(path)[:-5]
        return self._node_tile(os.path.dirname(path), rel_dir, node, stem, depth, None)

    def _node_tile(self, src_dir, rel_dir, node, stem, depth, matrix):
        if node.cls == 'osg::PagedLOD':
            geoms = []
            _collect_geoms(node.children, matrix, geoms)
            uri = None
            box = None
            if geoms:
                uri, box = self._write_b3dm(rel_dir, stem, geoms)
            children = []
            for fn in node.file_names:
                if fn:
                    c = self._file_tile(os.path.join(src_dir, fn), depth + 1)
                    if c:
                        children.append(c)
            box = _union2(box, _union_boxes([c['box'] for c in children])
                          if children else None)
            if box is None:
                return None
            ge = 0.0
            if children:
                r = node.radius or _box_radius(box)
                ge = 0.0
                if len(node.range_list) > 1:
                    p = min(rg[0] for rg in node.range_list[1:])
                    if p > 0 and r > 0:
                        ge = 32.0 * r / p
                ge = max(ge, max(c['ge'] for c in children))
                ge = min(max(ge, 0.25), 4096.0)
            return {'uri': uri, 'box': box, 'ge': ge,
                    'refine': 'REPLACE' if children else None, 'children': children}

        if node.cls in ('osg::Group', 'osg::MatrixTransform'):
            m = matrix
            if node.cls == 'osg::MatrixTransform' and node.matrix is not None:
                m = _mat_mul(node.matrix, matrix) if matrix is not None else node.matrix
            children = []
            for i, ch in enumerate(node.children):
                t = self._node_tile(src_dir, rel_dir, ch,
                                    '%s_c%d' % (stem, i), depth, m)
                if t:
                    children.append(t)
            if not children:
                return None
            box = _union_boxes([c['box'] for c in children])
            ge = max(c['ge'] for c in children)
            return {'uri': None, 'box': box, 'ge': ge, 'refine': 'ADD',
                    'children': children}

        # Geode / 其它叶子
        geoms = []
        _collect_geoms([node], matrix, geoms)
        if not geoms:
            return None
        uri, box = self._write_b3dm(rel_dir, stem, geoms)
        if uri is None:
            return None
        return {'uri': uri, 'box': box, 'ge': 0.0, 'refine': None, 'children': []}

    def _write_b3dm(self, rel_dir, stem, geoms):
        builder = GlbBuilder(self.flip_v)
        for g, m in geoms:
            builder.add_geometry(g, m)
        if not builder.prims:
            return None, None
        glb = builder.finish()
        data = _b3dm(glb)
        rel_dir = _safe_name(rel_dir.replace('\\', '/'))
        stem = _safe_name(stem)
        out_dir = (os.path.join(self.out_dir, *rel_dir.split('/'))
                   if rel_dir != '.' else self.out_dir)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, stem + '.b3dm')
        with open(out_path, 'wb') as f:
            f.write(data)
        self.n_b3dm += 1
        self.n_bytes += len(data)
        uri = ('%s/%s.b3dm' % (rel_dir, stem)) if rel_dir != '.' else ('%s.b3dm' % stem)
        return uri, _box_from_minmax(builder.pos_min, builder.pos_max)

    @staticmethod
    def _tile_json(t):
        d = {'boundingVolume': {'box': t['box']},
             'geometricError': round(t['ge'], 4)}
        if t['refine']:
            d['refine'] = t['refine']
        if t['uri']:
            d['content'] = {'uri': t['uri']}
        if t['children']:
            d['children'] = [OsgbToTiles._tile_json(c) for c in t['children']]
        return d


def main(argv=None):
    ap = argparse.ArgumentParser(
        description='OSGB (Smart3D) → 3D Tiles (b3dm) 转换器')
    ap.add_argument('input', help='OSGB 根目录（含 metadata.xml 与 Data/）')
    ap.add_argument('--out', required=True, help='输出目录')
    ap.add_argument('--height', type=float, default=0.0,
                    help='ENU 原点椭球高（默认 0，应用为无地形平坦世界）')
    ap.add_argument('--no-flip-v', action='store_true',
                    help='不翻转纹理 V 坐标（默认翻转：OSG 纹理原点在左下，glTF 在左上）')
    ap.add_argument('--transform-from', default=None, metavar='TILESET',
                    help='从参考 tileset.json 复制 root.transform（与既有模型精确重合）')
    ap.add_argument('--only', default=None, help='只转换名称含此子串的根瓦片（调试）')
    args = ap.parse_args(argv)
    transform = None
    if args.transform_from:
        transform = transform_from_tileset(args.transform_from)
    conv = OsgbToTiles(args.out, flip_v=not args.no_flip_v, height=args.height,
                       only=args.only, transform=transform)
    conv.convert(args.input)


if __name__ == '__main__':
    main()
