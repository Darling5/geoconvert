# -*- coding: utf-8 -*-
"""OBJ/MTL 解析：流式读取 v/vt/usemtl/f，按材质分组输出 numpy 结构。

- OBJ 索引 1 起，负数相对末尾；f 支持 v、v/vt、v//vn、v/vt/vn，多边形扇形三角化
- 本模块不做 V 翻转（OBJ 左下原点 → glTF 左上原点），由 convert.py 统一处理
"""
import os

import numpy as np


class ObjError(Exception):
    pass


def parse_mtl(path):
    """MTL → {材质名: 纹理文件名(相对 MTL 目录) or None}。"""
    mats = {}
    cur = None
    try:
        f = open(path, 'r', encoding='utf-8', errors='replace')
    except OSError:
        return mats
    with f:
        for line in f:
            if line.startswith('newmtl'):
                parts = line.split(None, 1)
                cur = parts[1].strip() if len(parts) > 1 else ''
                mats[cur] = None
            elif line.startswith('map_Kd') and cur is not None:
                toks = line.split()
                if len(toks) > 1:
                    # MTL 规范：选项参数在前，文件名总是最后一个 token
                    mats[cur] = toks[-1].strip()
    return mats


class ObjMesh:
    """单个 OBJ 的解析结果（未焊接）。

    positions: (nv,3) float64；uvs: (nt,2) float64 或 None
    groups: [(mtl 名 or None, corners ndarray(nf*3,2) int64 [vi, ti(无=-1)])]
    """

    __slots__ = ('positions', 'uvs', 'groups', 'obj_dir', 'materials')

    def __init__(self):
        self.positions = None
        self.uvs = None
        self.groups = []
        self.obj_dir = ''
        self.materials = {}


def read_obj(path):
    mesh = ObjMesh()
    mesh.obj_dir = os.path.dirname(os.path.abspath(path))

    pos = []  # array('d') 逐行 append 慢，先收 list 再一次性转
    uv = []
    n_v = 0
    n_t = 0
    groups = {}  # mtl_name -> [(vi,ti), ...] 扁平列表
    order = []  # 保持材质出现顺序
    cur_mat = None
    mtllibs = []

    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for line in f:
            c = line[0] if line else ''
            if c == 'v':
                if line[1] == ' ' or line[1] == '\t':
                    t = line.split()
                    if len(t) >= 4:
                        pos.append((float(t[1]), float(t[2]), float(t[3])))
                        n_v += 1
                elif line[1] == 't' and (line[2] == ' ' or line[2] == '\t'):
                    t = line.split()
                    if len(t) >= 3:
                        uv.append((float(t[1]), float(t[2])))
                        n_t += 1
                # vn 忽略（Cesium 自动计算平面法线）
            elif c == 'f' and (line[1] == ' ' or line[1] == '\t'):
                t = line.split()
                if len(t) < 4:
                    continue
                corners = []
                for tok in t[1:]:
                    sp = tok.split('/')
                    vi = int(sp[0])
                    vi = vi - 1 if vi > 0 else n_v + vi
                    ti = -1
                    if len(sp) > 1 and sp[1]:
                        ti = int(sp[1])
                        ti = ti - 1 if ti > 0 else n_t + ti
                    corners.append((vi, ti))
                if len(corners) < 3:
                    continue
                lst = groups.get(cur_mat)
                if lst is None:
                    lst = groups[cur_mat] = []
                    order.append(cur_mat)
                c0 = corners[0]
                for k in range(1, len(corners) - 1):
                    lst.extend((c0[0], c0[1], corners[k][0], corners[k][1],
                                corners[k + 1][0], corners[k + 1][1]))
            elif c == 'u' and line.startswith('usemtl'):
                parts = line.split(None, 1)
                cur_mat = parts[1].strip() if len(parts) > 1 else None
            elif c == 'm' and line.startswith('mtllib'):
                parts = line.split(None, 1)
                if len(parts) > 1:
                    mtllibs.append(parts[1].strip())
            # g/o/s 忽略

    if not pos or not groups:
        raise ObjError('%s 未解析到几何（v=%d faces=%d）' % (path, n_v, len(groups)))

    mesh.positions = np.array(pos, dtype=np.float64)
    mesh.uvs = np.array(uv, dtype=np.float64) if uv else None
    for mtl in order:
        arr = np.array(groups[mtl], dtype=np.int64)
        mesh.groups.append((mtl, arr.reshape(-1, 2)))
    for lib in mtllibs:
        p = os.path.join(mesh.obj_dir, lib)
        if os.path.isfile(p):
            mesh.materials.update(parse_mtl(p))
    return mesh


def weld_group(positions, uvs, corners):
    """角点焊接：corners (n,2) [vi, ti(-1=无)] → 唯一 (vi,ti) 顶点。

    返回 (wpos (m,3), wuv (m,2) 或 None, tri (k,3))。
    """
    n_uv = 0 if uvs is None else uvs.shape[0]
    slot = corners[:, 1].copy()
    slot[slot < 0] = n_uv  # 无 uv 角点占位槽
    base = np.int64(n_uv + 1)
    keys = corners[:, 0] * base + slot
    uniq, inv = np.unique(keys, return_inverse=True)
    vi = uniq // base
    sl = uniq % base
    wpos = positions[vi]
    if uvs is None:
        wuv = None
    else:
        has = sl < n_uv
        if not has.any():
            wuv = None
        else:
            wuv = np.zeros((uniq.shape[0], 2), dtype=np.float64)
            wuv[has] = uvs[sl[has]]
    tri = inv.reshape(-1, 3)
    return wpos, wuv, tri
