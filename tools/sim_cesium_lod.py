# -*- coding: utf-8 -*-
"""模拟 Cesium 1.144 Cesium3DTilesetTraversal 的稳态选瓦逻辑，验证 LOD 结构。

复刻 TVe.selectTiles / mg.canTraverse / meetsScreenSpaceErrorEarly 关键语义：
- 根瓦片 SSE ≤ maxSSE(16) 时整个 tileset 不渲染（selectTiles 早退）
- canTraverse = 有 children 且 SSE > 16（空 content 瓦片无豁免）
- ADD 父级的子级：以父级 GE 算 SSE ≤ 16 时被提前剔除（meetsScreenSpaceErrorEarly）
- REPLACE 父级稳态下（全部子级已加载）refine = canTraverse
用法: python tools/sim_cesium_lod.py <tileset.json>
"""
import json
import math
import sys

MAX_SSE = 16.0


def sphere_of(n):
    b = n['boundingVolume']['box']
    cx, cy, cz = b[0], b[1], b[2]
    r = max(abs(b[3]), abs(b[7]), abs(b[11]))
    return (cx, cy, cz), r


def simulate(root, dist, screen_h=1000.0):
    """相机在模型正上方 dist 米处；返回被选中渲染的瓦片列表。"""
    if root['geometricError'] * screen_h / dist <= MAX_SSE:
        return []  # selectTiles 早退：整个 tileset 不渲染

    selected = []
    parent_refines = {id(root): True}
    parent_of = {}
    stack = [root]
    while stack:
        t = stack.pop()
        ge = t['geometricError']
        has_content = 'content' in t
        p = parent_of.get(id(t))
        # meetsScreenSpaceErrorEarly：ADD 父级 + 父级 GE 视角 SSE ≤ 16 → 剔除
        if p is not None and p.get('refine') == 'ADD':
            if p['geometricError'] * screen_h / dist <= MAX_SSE:
                continue
        (cx, cy, cz), r = sphere_of(t)
        d = max(dist - r, 1.0)  # 近似：相机到瓦片包围球最近距离
        can_traverse = bool(t.get('children')) and ge * screen_h / d > MAX_SSE
        u = parent_refines[id(t)]
        refines = can_traverse and u
        if (not refines) and u and has_content:
            selected.append(t)
        if can_traverse:
            for c in t['children']:
                parent_refines[id(c)] = refines
                parent_of[id(c)] = t
                stack.append(c)
    return selected


def stats(path):
    ts = json.load(open(path, encoding='utf-8'))
    root = ts['root']
    print('== %s ==' % path)
    print('根 GE: %.1f  根有 content: %s  子数: %d'
          % (root['geometricError'], 'content' in root, len(root.get('children', []))))
    for dist in (200, 1000, 3000, 9000, 10800, 20000, 100000, 500000,
                 5000000, 20000000, 31900000):
        sel = simulate(root, float(dist))
        top = [s['content']['uri'].split('/')[0] for s in sel
               if 'content' in s]
        uniq = sorted(set(top))
        print('距离 %9d m: 选中 %4d 瓦片, 顶层块 %d/%d %s'
              % (dist, len(sel), len(uniq), len(root.get('children', [])),
                 '' if len(uniq) == len(root.get('children', [])) else '<- 有块缺失!'))
    # REPLACE 父级的子级应全部有 content（流式加载时粗模兜底的前提）
    bad = []
    def walk(n):
        for c in n.get('children', []):
            if n.get('refine') == 'REPLACE' and 'content' not in c:
                bad.append(c)
            walk(c)
    walk(root)
    print('REPLACE 父级下的无 content 子级: %d%s' % (len(bad), ' <- 流式加载会出空洞!' if bad else ''))
    empty_deep = []
    def walk2(n, is_root):
        if not is_root and 'content' not in n:
            empty_deep.append(n)
        for c in n.get('children', []):
            walk2(c, False)
    walk2(root, True)
    print('根以下无 content 空壳瓦片: %d%s' % (len(empty_deep), ' <- 视距内子树消失!' if empty_deep else ''))


if __name__ == '__main__':
    for p in sys.argv[1:]:
        stats(p)
        print()
