# -*- coding: utf-8 -*-
"""共享 glTF/GLB/b3dm 构建工具（obj/osgb/tif 转换器共用）。

GlbBuilder 聚合多个图元（positions/uvs/indices/可选纹理）为一个 GLB 字节串；
to_b3dm 按 3D Tiles 1.0 打包。纹理按 bytes 对象身份去重（调用方复用同一对象）。
"""
import array
import json
import struct

try:
    import numpy as _np
except ImportError:  # 纯列表路径不依赖 numpy
    _np = None

_EXT_CACHE = {}

# -90° 绕 X 轴四元数 [x,y,z,w]：Z-up → glTF 标准 Y-up
YUP_ROTATION = [-0.7071067811865476, 0.0, 0.0, 0.7071067811865476]


def image_mime(data):
    if data[:3] == b'\xff\xd8\xff':
        return 'image/jpeg'
    if data[:4] == b'\x89PNG':
        return 'image/png'
    return None


class GlbBuilder:
    def __init__(self, unlit=False, alpha=False):
        self.unlit = unlit  # True=KHR_materials_unlit（正射影像等无需光照）
        self.alpha = alpha  # True=alphaMode BLEND（纹理带透明通道时必须，否则 alpha 被忽略）
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

    def _material_for(self, texture):
        """texture: 纹理文件 bytes（按 id 去重）或 None（无纹理纯色材质）。"""
        def plain():
            m = {
                'pbrMetallicRoughness': {
                    'baseColorFactor': [0.85, 0.85, 0.85, 1.0],
                    'metallicFactor': 0.0, 'roughnessFactor': 1.0},
                'doubleSided': True}
            if self.alpha:
                m['alphaMode'] = 'BLEND'
            return m

        if texture is None:
            if self._plain_mat is None:
                self._plain_mat = len(self.materials)
                m = plain()
                if self.unlit:
                    m['extensions'] = {'KHR_materials_unlit': {}}
                self.materials.append(m)
            return self._plain_mat

        key = id(texture)
        if key in self._tex_by_img:
            return self._tex_by_img[key]
        mime = image_mime(texture)
        if mime is None:
            if self._plain_mat is None:
                self._plain_mat = len(self.materials)
                m = plain()
                if self.unlit:
                    m['extensions'] = {'KHR_materials_unlit': {}}
                self.materials.append(m)
            return self._plain_mat
        start = self._push(texture)
        self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                  'byteLength': len(texture)})
        img_idx = len(self.images)
        self.images.append({'mimeType': mime, 'bufferView': len(self.buffer_views) - 1})
        tex_idx = len(self.textures)
        self.textures.append({'sampler': 0, 'source': img_idx})
        mat_idx = len(self.materials)
        m = {
            'pbrMetallicRoughness': {
                'baseColorTexture': {'index': tex_idx},
                'metallicFactor': 0.0, 'roughnessFactor': 1.0},
            'doubleSided': True}
        if self.alpha:
            m['alphaMode'] = 'BLEND'
        if self.unlit:
            m['extensions'] = {'KHR_materials_unlit': {}}
        self.materials.append(m)
        self._tex_by_img[key] = mat_idx
        return mat_idx

    def add_primitive(self, positions, uvs, indices, texture=None):
        """positions: [(x,y,z)] 或 ndarray(n,3)；uvs: [(u,v)]/ndarray(n,2) 或 None；
        indices: [i...] 或 ndarray(k,)（k%3==0）。ndarray 走向量化快速路径。"""
        if _np is not None and isinstance(positions, _np.ndarray):
            self._add_primitive_nd(positions, uvs, indices, texture)
            return
        if not positions or not indices:
            return
        pos = array.array('f')
        mn = [1e30] * 3
        mx = [-1e30] * 3
        for v in positions:
            pos.extend(v)
            for i in range(3):
                if v[i] < mn[i]:
                    mn[i] = v[i]
                if v[i] > mx[i]:
                    mx[i] = v[i]
        start = self._push(pos.tobytes())
        self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                  'byteLength': len(pos) * 4, 'target': 34962})
        self.accessors.append({'componentType': 5126, 'count': len(positions),
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
        if uvs and len(uvs) == len(positions):
            uv = array.array('f')
            for t in uvs:
                uv.extend(t)
            start = self._push(uv.tobytes())
            self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                      'byteLength': len(uv) * 4, 'target': 34962})
            self.accessors.append({'componentType': 5126, 'count': len(uvs),
                                   'type': 'VEC2',
                                   'bufferView': len(self.buffer_views) - 1})
            attributes['TEXCOORD_0'] = len(self.accessors) - 1

        comp, fmt = (5123, 'H') if len(positions) < 65536 else (5125, 'I')
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
                           'material': self._material_for(texture), 'mode': 4})

    def _add_primitive_nd(self, positions, uvs, indices, texture):
        pos = _np.ascontiguousarray(positions, dtype=_np.float64)
        if pos.ndim != 2 or pos.shape[1] != 3 or pos.shape[0] == 0:
            return
        idx = _np.asarray(indices).reshape(-1)
        if idx.size == 0 or idx.size % 3:
            return
        idx = idx.astype(_np.int64)
        n = pos.shape[0]
        if idx.size and (idx.min() < 0 or idx.max() >= n):
            return
        mn = pos.min(axis=0)
        mx = pos.max(axis=0)

        pos32 = pos.astype('<f4')
        start = self._push(pos32.tobytes())
        self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                  'byteLength': pos32.nbytes, 'target': 34962})
        self.accessors.append({'componentType': 5126, 'count': n,
                               'type': 'VEC3', 'min': mn.tolist(), 'max': mx.tolist(),
                               'bufferView': len(self.buffer_views) - 1})
        pos_acc = len(self.accessors) - 1
        if self.pos_min is None:
            self.pos_min, self.pos_max = mn.tolist(), mx.tolist()
        else:
            for i in range(3):
                self.pos_min[i] = min(self.pos_min[i], mn[i])
                self.pos_max[i] = max(self.pos_max[i], mx[i])

        attributes = {'POSITION': pos_acc}
        if uvs is not None:
            uv = _np.ascontiguousarray(uvs, dtype=_np.float64)
            if uv.ndim == 2 and uv.shape[0] == n and uv.shape[1] == 2:
                uv32 = uv.astype('<f4')
                start = self._push(uv32.tobytes())
                self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                          'byteLength': uv32.nbytes, 'target': 34962})
                self.accessors.append({'componentType': 5126, 'count': n,
                                       'type': 'VEC2',
                                       'bufferView': len(self.buffer_views) - 1})
                attributes['TEXCOORD_0'] = len(self.accessors) - 1

        comp, fmt = (5123, 'H') if n < 65536 else (5125, 'I')
        arr = idx.astype('<%s' % fmt)
        start = self._push(arr.tobytes())
        self.buffer_views.append({'buffer': 0, 'byteOffset': start,
                                  'byteLength': arr.nbytes, 'target': 34963})
        self.accessors.append({'componentType': comp, 'count': idx.size,
                               'type': 'SCALAR', 'min': [int(idx.min())],
                               'max': [int(idx.max())],
                               'bufferView': len(self.buffer_views) - 1})

        self.prims.append({'attributes': attributes,
                           'indices': len(self.accessors) - 1,
                           'material': self._material_for(texture), 'mode': 4})

    def finish(self, yup=False):
        """yup=True：包一层 -90° 绕 X 旋转的根节点，把 Z-up 几何转成标准 glTF Y-up
        （3D Tiles 1.1 的 glb 内容按标准 glTF Y-up 渲染，客户端自动转回 Z-up；
        1.0 b3dm 内嵌 glTF 本身就是 Z-up，不能加，加了会被转两次）"""
        bin_data = b''.join(self.bin_parts)
        nodes = [{'mesh': 0}]
        scene_nodes = [0]
        if yup:
            nodes = [{'rotation': YUP_ROTATION, 'children': [1]}, {'mesh': 0}]
        gltf = {
            'asset': {'generator': 'geoconvert', 'version': '2.0'},
            'scene': 0,
            'scenes': [{'nodes': scene_nodes}],
            'nodes': nodes,
            'meshes': [{'primitives': self.prims}],
            'accessors': self.accessors,
            'bufferViews': self.buffer_views,
            'buffers': [{'byteLength': self.bin_len}],
        }
        if self.materials:
            gltf['materials'] = self.materials
            if self.unlit:
                gltf['extensionsUsed'] = ['KHR_materials_unlit']
        if self.textures:
            gltf['textures'] = self.textures
            gltf['samplers'] = self.samplers
        if self.images:
            gltf['images'] = self.images
        return to_glb(gltf, bin_data)


def to_glb(gltf, bin_data):
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


def to_b3dm(glb):
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


def box_from_minmax(mn, mx):
    cx = [(mn[i] + mx[i]) / 2 for i in range(3)]
    return [cx[0], cx[1], cx[2],
            (mx[0] - mn[0]) / 2, 0, 0,
            0, (mx[1] - mn[1]) / 2, 0,
            0, 0, (mx[2] - mn[2]) / 2]


def box_radius(box):
    return (box[3] ** 2 + box[7] ** 2 + box[11] ** 2) ** 0.5


def union_boxes(boxes):
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
    return box_from_minmax(mn, mx)
