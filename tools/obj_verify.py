# -*- coding: utf-8 -*-
"""校验 OBJ 解析器输出与 obj2gltf 参考产物（同目录 .gltf+.bin）的一致性。

对比项：顶点集合、V 翻转后的 UV 集合、三角形数量、包围盒。
obj2gltf 会按 (v,vt) 焊接顶点（与我们相同），索引顺序可能不同 → 按集合比较。
"""
import json
import os
import struct
import sys

import numpy as np

sys.path.insert(0, r'D:\WEB\zicaiduck\geo-convert')
from geoconvert.objconv.reader import read_obj, weld_group

# 路径含 '+' 字符，硬编码字面量经工具写入易丢失，一律动态推导
_DIR = r'D:\WEB\zicaiduck\www\public\malanyouzhan\Tile_005_006'
GLTF = os.path.join(_DIR, 'Tile_005_006.gltf')
_g = json.load(open(GLTF, encoding='utf-8'))
BIN = os.path.join(_DIR, _g['buffers'][0]['uri'])
_objs = [f for f in os.listdir(_DIR) if f.lower().endswith('.obj')]
OBJ = os.path.join(_DIR, _objs[0])


def read_accessor(gltf, bin_data, idx):
    acc = gltf['accessors'][idx]
    bv = gltf['bufferViews'][acc['bufferView']]
    base = (bv.get('byteOffset', 0)) + (acc.get('byteOffset', 0))
    comp = {5126: ('f', 4), 5125: ('I', 4), 5123: ('H', 2)}[acc['componentType']]
    n = {'VEC3': 3, 'VEC2': 2, 'SCALAR': 1}[acc['type']]
    stride = bv.get('byteStride', n * comp[1])
    count = acc['count']
    out = np.zeros((count, n), dtype=np.float64)
    for i in range(count):
        off = base + i * stride
        for c in range(n):
            out[i, c] = struct.unpack_from('<' + comp[0], bin_data, off + c * comp[1])[0]
    return out


def keyset(arr, nd=3):
    """顶点集合指纹：按行排序后取唯一（容忍顺序差异与重复）。"""
    a = np.unique(np.round(arr, 5), axis=0)
    return a


def main():
    print('BIN:', os.path.basename(BIN), 'len:', len(BIN), 'exists:', os.path.exists(BIN))
    gltf = json.load(open(GLTF, encoding='utf-8'))
    bin_data = open(BIN, 'rb').read()
    prim = gltf['meshes'][0]['primitives'][0]
    ref_pos = read_accessor(gltf, bin_data, prim['attributes']['POSITION'])
    ref_uv = read_accessor(gltf, bin_data, prim['attributes']['TEXCOORD_0'])
    ref_idx = read_accessor(gltf, bin_data, prim['indices']).astype(np.int64)

    mesh = read_obj(OBJ)
    mtl, corners = mesh.groups[0]
    wpos, wuv, tri = weld_group(mesh.positions, mesh.uvs, corners)
    wuv = wuv.copy()
    wuv[:, 1] = 1.0 - wuv[:, 1]

    print('参考: 顶点 %d 三角形 %d UV %d' %
          (ref_pos.shape[0], ref_idx.shape[0] // 3, ref_uv.shape[0]))
    print('我的: 顶点 %d 三角形 %d UV %d' % (wpos.shape[0], tri.shape[0], wuv.shape[0]))

    ok = True
    if ref_pos.shape[0] != wpos.shape[0] or tri.shape[0] != ref_idx.shape[0] // 3:
        print('!! 数量不一致')
        ok = False

    ps_ref, ps_my = keyset(ref_pos), keyset(wpos)
    d_pos = '一致' if ps_ref.shape == ps_my.shape and np.allclose(
        ps_ref, ps_my, atol=1e-4) else '不一致'
    print('顶点集合(float32 精度): %s (%d vs %d)' % (d_pos, ps_ref.shape[0], ps_my.shape[0]))
    ok &= d_pos == '一致'

    # 参考是 float32 精度：比较时把我的也降为 float32 再取集合
    uv_ref = keyset(ref_uv, 2)
    uv_my = keyset(wuv.astype(np.float32).astype(np.float64), 2)
    d_uv = '一致' if uv_ref.shape == uv_my.shape and np.allclose(
        uv_ref, uv_my, atol=1e-4) else '不一致'
    print('UV 集合(V 翻转后): %s (%d vs %d)' % (d_uv, uv_ref.shape[0], uv_my.shape[0]))
    ok &= d_uv == '一致'

    print('包围盒 ref: %s' % [round(v, 3) for v in
                              np.concatenate([ref_pos.min(0), ref_pos.max(0)])])
    print('包围盒 my : %s' % [round(v, 3) for v in
                              np.concatenate([wpos.min(0), wpos.max(0)])])
    print('\n结论: %s' % ('全部通过' if ok else '存在差异'))


if __name__ == '__main__':
    main()
