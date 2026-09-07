# -*- coding: utf-8 -*-
"""修复既有 3D Tiles 产物的 LOD 结构（瓦片跳变/缩放远不显示）。

问题根源（Cesium 遍历无空瓦片 SSE 豁免）：
1. 无 content 的空壳瓦片（根 / OSGB Group 分组壳）在自身 SSE ≤ 16 的视距内
   既不渲染也不下钻 → 子树整体消失（缩放远模型不显示、缩放中瓦片跳变）；
2. 空壳作为 REPLACE 父级的子级时，父级不等子级就绪即隐藏粗模 → 流式加载期间空洞。

修复：
- 空壳瓦片（无 content）剔除，子级上提到父级 children（tileset 根除外）；
- 根瓦片 geometricError 设 1e7，任何视距（含地球全览）都保证继续下钻。

用法: python tools/fix_tileset_lod.py <tileset.json 路径> [更多路径...]
就地改写（原文件备份为 tileset.json.bak-lodfix），transform/box/content 不变。
"""
import json
import os
import shutil
import sys

EMPTY_GE = 1.0e7


def collapse(node):
    """返回替代 node 的节点列表：无 content 的空壳节点被其子级上提替代。"""
    kids = []
    for c in node.get('children', []):
        kids.extend(collapse(c))
    node['children'] = kids
    if 'content' not in node:
        return kids
    return [node]


def fix(path):
    with open(path, encoding='utf-8') as f:
        ts = json.load(f)
    root = ts['root']
    before = count_nodes(root)
    empty_before = count_empty(root)

    kids = []
    for c in root.get('children', []):
        kids.extend(collapse(c))
    root['children'] = kids
    root['geometricError'] = EMPTY_GE
    ts['geometricError'] = EMPTY_GE

    missing = missing_contents(path, root)

    bak = path + '.bak-lodfix'
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(ts, f, separators=(',', ':'))

    after = count_nodes(root)
    print('%s: 节点 %d -> %d, 空壳 %d -> %d, 根 GE -> 1e7%s'
          % (path, before, after, empty_before, count_empty(root),
             ', 缺失文件 %d!' % len(missing) if missing else ''))
    for m in missing[:10]:
        print('  缺失: %s' % m)
    return len(missing) == 0


def count_nodes(n):
    return 1 + sum(count_nodes(c) for c in n.get('children', []))


def count_empty(n):
    return (0 if 'content' in n else 1) + sum(count_empty(c) for c in n.get('children', []))


def missing_contents(path, root):
    base = os.path.dirname(os.path.abspath(path))
    out = []
    def walk(n):
        c = n.get('content')
        if c and not os.path.exists(os.path.join(base, c['uri'])):
            out.append(c['uri'])
        for k in n.get('children', []):
            walk(k)
    walk(root)
    return out


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    ok = all(fix(p) for p in sys.argv[1:])
    raise SystemExit(0 if ok else 1)
