# -*- coding: utf-8 -*-
"""OBJ → 3D Tiles（b3dm）转换器：三级 LOD + 空间切块（UV 岛纹理重打包）+ 多分块合并。

- 输入：单个 OBJ 文件，或含分块目录（每目录一个 OBJ）的根目录
- 切块：单体 OBJ 超过 --max-tris（默认 25 万三角形）时按 UV 岛做空间二分，
  每块只重打包自己用到的纹理像素（图集不跨块、不重复），拉近镜头只加载所在块
- LOD：pyfqmr 按几何误差折叠，UV 岛分组件简化 + cKDTree 最近邻继承 UV
  （pyfqmr 不携带顶点属性，缝顶点经 preserve_border 锁定保精确，内部折叠点近似）
- 纹理：full 用原始字节；lod0/lod1 用 PIL 降采样（512/1024, q65/q75）
- 定位：--lat/--lon 或 --transform-from 优先；metadata.xml 为 UTM 时用 SRSOrigin；
  否则赤道 ENU（与既有排土场 tileset 同配方，经应用内模型调整功能重新定位）
"""
import argparse
import io
import json
import math
import os
import time

import numpy as np

try:
    import pyfqmr
except ImportError:
    pyfqmr = None
try:
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree
except ImportError:
    coo_matrix = connected_components = cKDTree = None

from PIL import Image

from ..coords import enu_to_ecef_transform, utm_to_latlon
from ..gltf import GlbBuilder, box_from_minmax, box_radius, to_b3dm
from ..osgb.convert import parse_srs, read_metadata, transform_from_tileset
from .reader import ObjError, read_obj, weld_group

EQUATOR_TRANSFORM = [0, 1, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 6378137, 0, 0, 1]

DEFAULT_LODS = [
    {'name': 'lod0', 'ratio': 0.08, 'tex': 512, 'q': 65},
    {'name': 'lod1', 'ratio': 0.35, 'tex': 1024, 'q': 75},
]

MIN_ISLAND_TRIS = 32


def _split_islands(tri, n_verts):
    """按共享焊接顶点划分 UV 岛（位置同但 UV 不同的缝顶点天然分隔）。"""
    e = np.concatenate([tri[:, [0, 1]], tri[:, [1, 2]], tri[:, [2, 0]]])
    g = coo_matrix((np.ones(len(e), dtype=np.int8), (e[:, 0], e[:, 1])),
                   shape=(n_verts, n_verts))
    _, labels = connected_components(g, directed=False)
    return labels


def _pyfqmr(pos, tri, target):
    s = pyfqmr.Simplify()
    s.setMesh(np.ascontiguousarray(pos, dtype=np.float64),
              np.ascontiguousarray(tri, dtype=np.int32))
    s.simplify_mesh(target_count=target, verbose=False, preserve_border=True)
    v2, f2, _ = s.getMesh()
    v2 = np.asarray(v2, dtype=np.float64)
    f2 = np.asarray(f2, dtype=np.int64)
    if v2.ndim != 2 or f2.ndim != 2 or f2.shape[0] == 0:
        return None, None
    return v2, f2


def simplify_group(pos, uv, tri, ratio):
    """按 UV 岛分组件简化一个材质子网格，最近邻继承 UV。"""
    if pyfqmr is None or coo_matrix is None:
        return pos, uv, tri
    if ratio >= 1.0 or tri.shape[0] < MIN_ISLAND_TRIS:
        return pos, uv, tri
    labels = _split_islands(tri, pos.shape[0])
    tl = labels[tri[:, 0]]
    order = np.argsort(tl, kind='stable')
    tl_sorted = tl[order]
    uniq = np.unique(tl_sorted)
    starts = list(np.searchsorted(tl_sorted, uniq)) + [tl_sorted.shape[0]]

    out_p, out_u, out_t = [], [], []
    offset = 0
    for i in range(len(uniq)):
        sub = tri[order[starts[i]:starts[i + 1]]]
        if sub.shape[0] < MIN_ISLAND_TRIS:
            verts = np.unique(sub)
            local = np.searchsorted(verts, sub)
            out_p.append(pos[verts])
            if uv is not None:
                out_u.append(uv[verts])
            out_t.append(local + offset)
            offset += verts.shape[0]
            continue
        target = max(4, int(round(sub.shape[0] * ratio)))
        if target >= sub.shape[0]:
            verts = np.unique(sub)
            local = np.searchsorted(verts, sub)
            out_p.append(pos[verts])
            if uv is not None:
                out_u.append(uv[verts])
            out_t.append(local + offset)
            offset += verts.shape[0]
            continue
        verts = np.unique(sub)
        local = np.searchsorted(verts, sub)
        lpos = pos[verts]
        try:
            v2, f2 = _pyfqmr(lpos, local, target)
        except Exception:
            v2, f2 = None, None
        if v2 is None:
            out_p.append(lpos)
            if uv is not None:
                out_u.append(uv[verts])
            out_t.append(local + offset)
            offset += verts.shape[0]
            continue
        out_p.append(v2)
        if uv is not None:
            luv = uv[verts]
            _, nn = cKDTree(lpos).query(v2, k=1)
            out_u.append(luv[nn])
        out_t.append(f2 + offset)
        offset += v2.shape[0]

    pos2 = np.concatenate(out_p, axis=0)
    uv2 = np.concatenate(out_u, axis=0) if (uv is not None and out_u) else None
    tri2 = np.concatenate(out_t, axis=0)
    return pos2, uv2, tri2


def build_islands(subs):
    """把焊接后的材质子网格拆成 UV 岛池（岛 = 纹理图集中互不相连的贴片）。

    岛是空间切块的最小单元：整岛归属唯一块，纹理像素不跨块、不重复。
    """
    islands = []
    for si, s in enumerate(subs):
        tri = s['tri']
        if tri.shape[0] == 0:
            continue
        labels = _split_islands(tri, s['pos'].shape[0])
        tl = labels[tri[:, 0]]
        order = np.argsort(tl, kind='stable')
        tl_s = tl[order]
        uniq = np.unique(tl_s)
        starts = np.searchsorted(tl_s, uniq)
        ends = np.searchsorted(tl_s, uniq, side='right')
        for i in range(uniq.shape[0]):
            t = tri[order[starts[i]:ends[i]]]
            verts = np.unique(t)
            isl = {'sub': si, 'tri_rows': t, 'verts': verts,
                   'cent': s['pos'][t].mean(axis=(0, 1)), 'n': int(t.shape[0])}
            if s['uv'] is not None:
                u = s['uv'][verts]
                isl['uvb'] = (u.min(axis=0), u.max(axis=0))
            else:
                isl['uvb'] = None
            islands.append(isl)
    return islands


def split_islands(islands, max_tris, max_depth=5):
    """按岛质心做最长水平轴中位数递归二分，直到每块三角形数 ≤ max_tris。"""
    total = sum(i['n'] for i in islands)
    if total <= max_tris or max_depth <= 0 or len(islands) <= 1:
        return [islands]
    cents = np.array([i['cent'] for i in islands])
    extent = cents.max(axis=0) - cents.min(axis=0)
    axis = int(np.argmax(extent[:2]))
    mid = float(np.median(cents[:, axis]))
    left = [i for i in islands if i['cent'][axis] <= mid]
    right = [i for i in islands if i['cent'][axis] > mid]
    if not left or not right:  # 退化（质心全部同侧）→ 停止切分
        return [islands]
    return (split_islands(left, max_tris, max_depth - 1) +
            split_islands(right, max_tris, max_depth - 1))


def _shelf_pack(boxes, W, H):
    """搁架装箱（boxes 按高度降序）。返回 (placed, leftover)，
    placed=[(i,(x,y)), ...]，leftover=未放下的索引列表。"""
    placed, leftover = [], []
    x = y = row_h = 0
    for i, (w, h) in enumerate(boxes):
        if w > W or h > H:
            leftover.append(i)
            continue
        if x + w > W:
            x = 0
            y += row_h
            row_h = 0
        if y + h > H:
            leftover.append(i)
            continue
        placed.append((i, (x, y)))
        x += w
        row_h = max(row_h, h)
    return placed, leftover


def _encode_jpeg(img, max_dim, quality):
    if max_dim:
        w, h = img.size
        scale = min(max_dim / w, max_dim / h, 1.0)
        if scale < 1.0:
            img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                             Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return buf.getvalue()


def find_obj_blocks(root):
    root = os.path.abspath(root)
    if os.path.isfile(root):
        return [(os.path.splitext(os.path.basename(root))[0], root)]
    blocks = []
    for name in sorted(os.listdir(root)):
        p = os.path.join(root, name)
        if os.path.isfile(p) and name.lower().endswith('.obj'):
            blocks.append((os.path.splitext(name)[0], p))
    if not blocks:
        for name in sorted(os.listdir(root)):
            d = os.path.join(root, name)
            if not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.lower().endswith('.obj'):
                    blocks.append((os.path.splitext(fn)[0], os.path.join(d, fn)))
    if not blocks:
        raise ObjError('%s 下未找到 OBJ 文件' % root)
    return blocks


def resolve_transform(obj_root, lat=None, lon=None, height=0.0, override=None):
    if override:
        return list(override)
    if lat is not None and lon is not None:
        return enu_to_ecef_transform(lat, lon, height)
    for cand in (os.path.abspath(obj_root),
                 os.path.dirname(os.path.abspath(obj_root))):
        p = os.path.join(cand, 'metadata.xml')
        if os.path.isfile(p):
            try:
                meta = read_metadata(cand)
                zone, northern = parse_srs(meta['srs'])
                ox, oy, _ = meta['origin']
                mlat, mlon = utm_to_latlon(ox, oy, zone, northern)
                return enu_to_ecef_transform(mlat, mlon, height)
            except Exception:
                pass
    return list(EQUATOR_TRANSFORM)


def _resized_jpeg(path, max_dim, quality):
    img = Image.open(path)
    if img.mode not in ('RGB', 'L'):
        img = img.convert('RGB')
    w, h = img.size
    scale = min(max_dim / w, max_dim / h, 1.0)
    if scale < 1.0:
        img = img.resize((max(1, round(w * scale)), max(1, round(h * scale))),
                         Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=quality)
    return buf.getvalue()


class ObjToTiles:
    def __init__(self, out_dir, lat=None, lon=None, height=0.0, transform=None,
                 lods=None, max_tris=250000, verbose=True):
        self.out_dir = os.path.abspath(out_dir)
        self.lat = lat
        self.lon = lon
        self.height = height
        self.transform_override = list(transform) if transform else None
        self.lods = lods if lods is not None else DEFAULT_LODS
        self.max_tris = max_tris
        self.verbose = verbose
        self.transform = None
        self.blocks = []
        self._tex_cache = {}
        self._tex_lo_cache = {}
        self._tex_img_cache = {}

    def _log(self, msg):
        if self.verbose:
            print(msg, flush=True)

    def _texture_path(self, obj_dir, tex):
        if not tex:
            return None
        p = os.path.join(obj_dir, tex)
        if os.path.isfile(p):
            return p
        p2 = os.path.join(obj_dir, os.path.basename(tex))
        return p2 if os.path.isfile(p2) else None

    def _tex_bytes(self, path):
        if path is None:
            return None
        if path not in self._tex_cache:
            with open(path, 'rb') as f:
                self._tex_cache[path] = f.read()
        return self._tex_cache[path]

    def _tex_lod(self, path, max_dim, quality):
        if path is None:
            return None
        key = (path, max_dim, quality)
        if key not in self._tex_lo_cache:
            try:
                self._tex_lo_cache[key] = _resized_jpeg(path, max_dim, quality)
            except Exception:
                self._tex_lo_cache[key] = self._tex_bytes(path)
        return self._tex_lo_cache[key]

    def _tex_image(self, path):
        """源纹理的 PIL RGB 图（缓存；失败返回 None）。"""
        if path is None:
            return None
        if path not in self._tex_img_cache:
            try:
                im = Image.open(path)
                if im.mode != 'RGB':
                    im = im.convert('RGB')
                self._tex_img_cache[path] = im
            except Exception:
                self._tex_img_cache[path] = None
        return self._tex_img_cache[path]

    def _tex_for(self, s, lod):
        """取子网格在指定 LOD 级（None=full）的纹理字节：打包块用 tex_blobs，否则用源文件。"""
        blobs = s.get('tex_blobs')
        key = lod['name'] if lod else None
        if blobs is not None and key in blobs:
            return blobs[key]
        path = s.get('tex')
        if lod is None:
            return self._tex_bytes(path)
        return self._tex_lod(path, lod['tex'], lod['q'])

    def _plain_sub(self, s, isls):
        """不重打包（无纹理/无 UV/兜底）：直接拼岛的几何，保留原 UV 与纹理。"""
        pos_l, uv_l, tri_l, off = [], [], [], 0
        for isl in isls:
            verts = isl['verts']
            pos_l.append(s['pos'][verts])
            if s['uv'] is not None:
                uv_l.append(s['uv'][verts])
            tri_l.append(np.searchsorted(verts, isl['tri_rows']) + off)
            off += verts.shape[0]
        return {'pos': np.concatenate(pos_l),
                'uv': np.concatenate(uv_l) if (s['uv'] is not None and uv_l) else None,
                'tri': np.concatenate(tri_l), 'tex': s['tex']}

    def _pack_chunk_material(self, s, isls):
        """把一个材质在当前块的岛打包成新图集（搁架装箱 + 像素搬运 + UV 平移）。

        图集按本块岛像素总量自动选边长；放不下自动开第二张。返回子网格列表。
        """
        img = self._tex_image(s['tex'])
        if img is None or s['uv'] is None or not isls:
            return [self._plain_sub(s, isls)]
        W, H = img.size
        g = 4  # 缝隙像素：防降采样/插值时边缘渗色
        entries = []
        for isl in isls:
            (u0, v0), (u1, v1) = isl['uvb']
            x0 = max(0, int(math.floor(u0 * W)) - g)
            y0 = max(0, int(math.floor(v0 * H)) - g)
            x1 = min(W, max(x0 + 1, int(math.ceil(u1 * W)) + g))
            y1 = min(H, max(y0 + 1, int(math.ceil(v1 * H)) + g))
            entries.append({'isl': isl, 'box': (x0, y0, x1, y1)})
        area = sum((e['box'][2] - e['box'][0]) * (e['box'][3] - e['box'][1])
                   for e in entries)
        max_w = max(e['box'][2] - e['box'][0] for e in entries)
        max_h = max(e['box'][3] - e['box'][1] for e in entries)
        side = 256
        while side * side < area * 1.8 or side < max_w or side < max_h:
            side *= 2

        results = []
        remaining = entries
        while remaining:
            order = sorted(range(len(remaining)),
                           key=lambda i: remaining[i]['box'][3] - remaining[i]['box'][1],
                           reverse=True)
            boxes = [(remaining[i]['box'][2] - remaining[i]['box'][0],
                      remaining[i]['box'][3] - remaining[i]['box'][1])
                     for i in order]
            placed, leftover = _shelf_pack(boxes, side, side)
            if not placed:  # 异常兜底：这些岛保留原纹理原 UV（少量重复，保正确性）
                results.append(self._plain_sub(s, [e['isl'] for e in remaining]))
                break
            atlas = Image.new('RGB', (side, side))
            pos_l, uv_l, tri_l, off = [], [], [], 0
            for k, (dx, dy) in placed:
                e = remaining[order[k]]
                isl = e['isl']
                x0, y0, x1, y1 = e['box']
                atlas.paste(img.crop((x0, y0, x1, y1)), (dx, dy))
                verts = isl['verts']
                uv = s['uv'][verts].astype(np.float64).copy()
                # 源像素 → 图集像素 → 图集 UV（图集边长可与源纹理不同）
                uv[:, 0] = (uv[:, 0] * W + dx - x0) / side
                uv[:, 1] = (uv[:, 1] * H + dy - y0) / side
                pos_l.append(s['pos'][verts])
                uv_l.append(uv)
                tri_l.append(np.searchsorted(verts, isl['tri_rows']) + off)
                off += verts.shape[0]
            blobs = {None: _encode_jpeg(atlas, None, 90)}
            for lod in self.lods:
                blobs[lod['name']] = _encode_jpeg(atlas, lod['tex'], lod['q'])
            results.append({'pos': np.concatenate(pos_l),
                            'uv': np.concatenate(uv_l),
                            'tri': np.concatenate(tri_l), 'tex_blobs': blobs})
            remaining = [remaining[order[k]] for k in leftover]
        return results

    def _chunk_subs(self, subs, chunk_islands):
        """一个空间块的岛集合 → 打包后的材质子网格列表。"""
        by_mat = {}
        for isl in chunk_islands:
            by_mat.setdefault(isl['sub'], []).append(isl)
        out = []
        for si in sorted(by_mat):
            out.extend(self._pack_chunk_material(subs[si], by_mat[si]))
        return out

    def convert(self, obj_root):
        t0 = time.time()
        blocks = find_obj_blocks(obj_root)
        self.transform = resolve_transform(obj_root, self.lat, self.lon,
                                           self.height, self.transform_override)
        self._log('输入 %d 个 OBJ 分块，transform=%s' %
                  (len(blocks), 'override' if self.transform_override else
                   ('lat/lon' if self.lat is not None else 'metadata/默认')))
        os.makedirs(self.out_dir, exist_ok=True)
        for name, path in blocks:
            self._convert_block(name, path)
        out_root = self._merge()
        self._log('完成：%.1fs -> %s' % (time.time() - t0, out_root))
        return out_root

    def _convert_block(self, name, obj_path):
        t0 = time.time()
        self._log('\n=== %s ===' % name)
        mesh = read_obj(obj_path)
        subs = []
        n_tri = 0
        for mtl, corners in mesh.groups:
            wpos, wuv, tri = weld_group(mesh.positions, mesh.uvs, corners)
            if wuv is not None:
                wuv = wuv.copy()
                wuv[:, 1] = 1.0 - wuv[:, 1]  # OBJ 左下原点 → glTF 左上原点
            tex_path = self._texture_path(mesh.obj_dir, mesh.materials.get(mtl))
            subs.append({'pos': wpos, 'uv': wuv, 'tri': tri, 'tex': tex_path})
            n_tri += tri.shape[0]
        self._log('  顶点 %d / 三角形 %d / 材质 %d' %
                  (sum(s['pos'].shape[0] for s in subs), n_tri, len(subs)))

        chunks = None
        if self.max_tris and n_tri > self.max_tris and coo_matrix is not None:
            islands = build_islands(subs)
            parts = split_islands(islands, self.max_tris)
            if len(parts) > 1:
                self._log('  空间切块: %d 块（阈值 %d 三角形/块，%d 个 UV 岛，纹理按岛重打包）'
                          % (len(parts), self.max_tris, len(islands)))
                chunks = parts
        if chunks is None:
            self._emit_block(name, subs, time.time())
        else:
            for i, chunk in enumerate(chunks):
                self._emit_block('%s_c%02d' % (name, i),
                                 self._chunk_subs(subs, chunk), time.time())
        # 纹理缓存按块清理：贴图从不跨块复用（每块目录自带贴图），
        # 不清会把前面所有块的解码图集累计在内存里（大模型必炸 MemoryError）
        self._tex_cache.clear()
        self._tex_lo_cache.clear()
        self._tex_img_cache.clear()

    def _emit_block(self, name, subs, t0):
        mn = np.min([s['pos'].min(axis=0) for s in subs], axis=0)
        mx = np.max([s['pos'].max(axis=0) for s in subs], axis=0)
        box = box_from_minmax(mn.tolist(), mx.tolist())
        radius = box_radius(box)

        block_dir = os.path.join(self.out_dir, name)
        os.makedirs(block_dir, exist_ok=True)

        b = GlbBuilder()
        for s in subs:
            b.add_primitive(s['pos'], s['uv'], s['tri'],
                            texture=self._tex_for(s, None))
        data = to_b3dm(b.finish())
        with open(os.path.join(block_dir, 'full.b3dm'), 'wb') as f:
            f.write(data)
        self._log('  %s full.b3dm: %.1f MB %.1fs' %
                  (name, len(data) / 1048576, time.time() - t0))

        for lod in self.lods:
            t1 = time.time()
            b = GlbBuilder()
            for s in subs:
                p2, uv2, t2 = simplify_group(s['pos'], s['uv'], s['tri'],
                                             lod['ratio'])
                b.add_primitive(p2, uv2, t2,
                                texture=self._tex_for(s, lod))
            data = to_b3dm(b.finish())
            with open(os.path.join(block_dir, lod['name'] + '.b3dm'), 'wb') as f:
                f.write(data)
            self._log('  %s %s.b3dm: %.1f MB (%.0f%% tris) %.1fs' %
                      (name, lod['name'], len(data) / 1048576, lod['ratio'] * 100,
                       time.time() - t1))

        ts = self._block_tileset(box, radius)
        with open(os.path.join(block_dir, 'tileset.json'), 'w', encoding='utf-8') as f:
            json.dump(ts, f, separators=(',', ':'))
        self.blocks.append((name, box, radius))

    def _block_tileset(self, box, radius):
        # Cesium SSE=16 下细化距离≈GE×58m；root GE≈radius×0.045、lod1 GE≈radius×0.005
        ge_root = max(40, round(radius * 0.045))
        ge_lod1 = max(4, round(radius * 0.005))
        return {
            'asset': {'gltfUpAxis': 'Z', 'version': '1.0'},
            'geometricError': max(100, int(radius * 2) + 1),
            'root': {
                'transform': self.transform,
                'boundingVolume': {'box': box},
                'refine': 'REPLACE',
                'geometricError': ge_root,
                'content': {'uri': 'lod0.b3dm'},
                'children': [{
                    'boundingVolume': {'box': box},
                    'geometricError': ge_lod1,
                    'content': {'uri': 'lod1.b3dm'},
                    'children': [{
                        'boundingVolume': {'box': box},
                        'geometricError': 0,
                        'content': {'uri': 'full.b3dm'},
                    }],
                }],
            },
        }

    def _merge(self):
        def rewrite(node, block):
            out = {'boundingVolume': node['boundingVolume'],
                   'geometricError': node['geometricError']}
            if 'refine' in node:
                out['refine'] = node['refine']
            if 'content' in node:
                out['content'] = {'uri': '%s/%s' % (block, node['content']['uri'])}
            if 'children' in node:
                out['children'] = [rewrite(c, block) for c in node['children']]
            return out

        children = []
        all_min = [1e30] * 3
        all_max = [-1e30] * 3
        for name, box, _ in self.blocks:
            with open(os.path.join(self.out_dir, name, 'tileset.json'),
                      encoding='utf-8') as f:
                ts = json.load(f)
            node = ts['root']
            node.pop('transform', None)
            children.append(rewrite(node, name))
            for i, h in enumerate((3, 7, 11)):
                all_min[i] = min(all_min[i], box[i] - box[h])
                all_max[i] = max(all_max[i], box[i] + box[h])

        union = box_from_minmax(all_min, all_max)
        radius = box_radius(union)
        tileset = {
            'asset': {'gltfUpAxis': 'Z', 'version': '1.0'},
            'geometricError': max(100, int(radius * 2) + 1),
            'root': {
                'transform': self.transform,
                'boundingVolume': {'box': union},
                'refine': 'ADD',
                'geometricError': int(radius) + 1,
                'children': children,
            },
        }
        out = os.path.join(self.out_dir, 'tileset.json')
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(tileset, f, separators=(',', ':'))
        self._log('\n合并 %d 个分块 -> tileset.json（联合半径 %dm）' %
                  (len(self.blocks), round(radius)))
        return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog='geoconvert obj',
        description='OBJ → 3D Tiles（b3dm，三级 LOD，多分块自动合并）')
    ap.add_argument('input', help='OBJ 文件或含分块目录的根目录')
    ap.add_argument('output', help='输出目录')
    ap.add_argument('--lat', type=float, help='ENU 原点纬度（WGS84）')
    ap.add_argument('--lon', type=float, help='ENU 原点经度（WGS84）')
    ap.add_argument('--height', type=float, default=0.0,
                    help='ENU 原点高度（米，默认 0；系统为平地球，勿用真实海拔）')
    ap.add_argument('--transform-from',
                    help='参考 tileset.json，复制其 root.transform（优先于 --lat/--lon）')
    ap.add_argument('--max-tris', type=int, default=250000,
                    help='单块三角形数上限，超过则空间切块（0=禁用切块，默认 25 万）')
    ap.add_argument('-q', '--quiet', action='store_true')
    args = ap.parse_args(argv)

    override = None
    if args.transform_from:
        override = transform_from_tileset(args.transform_from)
    c = ObjToTiles(args.output, lat=args.lat, lon=args.lon, height=args.height,
                   transform=override, max_tris=args.max_tris,
                   verbose=not args.quiet)
    c.convert(args.input)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
