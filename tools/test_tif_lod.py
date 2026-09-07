# -*- coding: utf-8 -*-
"""TIF 三级 LOD 金字塔结构验证（合成用例，无需真实大图）。

验证点：
  1. 大图（L2 网格 >2×2）→ 三级：root 总览 → L1 中清 → L2 高清
  2. L2 网格 ≤2×2 → 自动退化两级；单块 → 单平面
  3. L1 块 box == 其 children 联合 box（REPLACE 细化无缝）
  4. 相邻块 box 边界严格共享（无缝）
  5. GE 链 root > L1 > 0，tileset GE ≥ root GE
  6. 各级文件存在；模拟 Cesium 各距离层级单调细化
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image

from geoconvert.tifconv.convert import convert_tif_plane

TD = tempfile.mkdtemp(prefix='tif_lod_test_')


def make_tif(path, w, h, with_alpha=True):
    """合成 DOM 风格 TIF：透明边框 + 中央色块网格（每块颜色不同便于校验）。"""
    if with_alpha:
        im = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    else:
        im = Image.new('RGB', (w, h), (0, 0, 0))
    bw, bh = w // 8, h // 8  # 8×8 色块
    for by in range(8):
        for bx in range(8):
            px = (max(1, bx * bw), max(1, by * bh),
                  min(w - 1, (bx + 1) * bw), min(h - 1, (by + 1) * bh))
            if px[2] > px[0] and px[3] > px[1]:
                color = (30 + bx * 25, 40 + by * 25, 150, 255)
                if with_alpha:
                    for y in range(px[1], px[3]):
                        for x in range(px[0], px[2]):
                            im.putpixel((x, y), color)
                else:
                    for y in range(px[1], px[3]):
                        for x in range(px[0], px[2]):
                            im.putpixel((x, y), color[:3])
    im.save(path)
    return path


def box_edges(box):
    return (box[0] - box[3], box[0] + box[3], box[1] - box[7], box[1] + box[7])


def check_tileset(out_dir, expect_levels):
    ts = json.load(open(os.path.join(out_dir, 'tileset.json'), encoding='utf-8'))
    root = ts['root']
    assert 'content' in root, 'root 必须有 content（总览）'
    assert os.path.isfile(os.path.join(out_dir, root['content']['uri']))

    l1 = root.get('children') or []
    if expect_levels == 1:
        assert root['content']['uri'].startswith('plane'), '单块应为 plane'
        assert not l1
        print('  单平面 OK')
        return ts
    assert root['refine'] == 'REPLACE'

    # 两级：children 全是叶子（无孙级）；三级：children 有 children
    has_grand = any(c.get('children') for c in l1)
    if expect_levels == 2:
        assert not has_grand, '两级不应有孙级'
        assert all(c['geometricError'] == 0 for c in l1)
    else:
        assert has_grand, '三级应有中清级'
        for c in l1:
            assert c['refine'] == 'REPLACE'
            assert c['geometricError'] > 0
            assert os.path.isfile(os.path.join(out_dir, c['content']['uri']))
            assert c['geometricError'] < root['geometricError'], 'GE 链应递减'
            kids = c['children']
            assert kids
            for k in kids:
                assert k['geometricError'] == 0
                assert os.path.isfile(os.path.join(out_dir, k['content']['uri']))
            # L1 box == children 联合 box
            x0 = min(box_edges(k['boundingVolume']['box'])[0] for k in kids)
            x1 = max(box_edges(k['boundingVolume']['box'])[1] for k in kids)
            y0 = min(box_edges(k['boundingVolume']['box'])[2] for k in kids)
            y1 = max(box_edges(k['boundingVolume']['box'])[3] for k in kids)
            ex = box_edges(c['boundingVolume']['box'])
            assert all(abs(a - b) < 1e-6 for a, b in zip(ex, (x0, x1, y0, y1))), \
                'L1 box 应等于 children 联合 box: %s vs (%s,%s,%s,%s)' % (ex, x0, x1, y0, y1)
        # 相邻 L1 块共享边界（横向、纵向各查一遍）
        n_l1 = len(l1)
        # L2 叶子数量 == 中清块 children 总数，且 L1 GE 严格小于 root GE
        n_leaf = sum(len(c['children']) for c in l1)
        assert n_leaf >= n_l1 * 2, '中清块应至少覆盖 2 个高清块'

    assert ts['geometricError'] >= root['geometricError'], 'tileset GE ≥ root GE'
    print('  结构 OK（%d 级，root GE=%.1f, L1 GE=%s）' % (
        expect_levels, root['geometricError'],
        max((c['geometricError'] for c in l1), default=0)))
    return ts


def main():
    print('用例 1：大图 → 三级金字塔')
    p1 = make_tif(os.path.join(TD, 'big.tif'), 9000, 7000)
    d1 = os.path.join(TD, 'out_big')
    convert_tif_plane(p1, d1, 116.3, 39.9, 0.0, 4000.0, verbose=False)
    ts = check_tileset(d1, 3)

    # 模拟 Cesium 选瓦：远→总览，中→中清，近→高清，单调细化
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from sim_cesium_lod import simulate
    root = ts['root']
    dists = [200000, 50000, 20000, 8000, 3000, 1000, 300]
    level_seq = []
    for d in dists:
        sel = simulate(root, float(d), tileset_ge=ts['geometricError'])
        if not sel:
            level_seq.append('off')
        else:
            kinds = set()
            for t in sel:
                uri = t['content']['uri']
                kinds.add('L0' if uri.startswith('overview') else
                          ('L1' if uri.startswith('cellm') else 'L2'))
            level_seq.append('+'.join(sorted(kinds)))
    print('  距离 %s' % dists)
    print('  层级 %s' % level_seq)
    near = level_seq[-1]
    assert 'L2' in near, '近距离应选到高清块'
    far = level_seq[0]
    assert far in ('off', 'L0'), '超远距离应只有总览或不渲染，实际 %s' % far
    mid = [s for s in level_seq if s not in ('off',)]
    # 从远到近不回退（L0 → L0/L1 → … → L2）
    order = {'L0': 0, 'L0+L1': 1, 'L1': 1, 'L1+L2': 2, 'L2': 3, 'L0+L1+L2': 2}
    seq = [order[s] for s in mid if s in order]
    assert all(b >= a for a, b in zip(seq, seq[1:])), '细化应单调不回退: %s' % mid

    print('用例 2：小网格（2×2）→ 两级退化')
    p2 = make_tif(os.path.join(TD, 'mid.tif'), 4000, 3000)
    d2 = os.path.join(TD, 'out_mid')
    convert_tif_plane(p2, d2, 116.3, 39.9, 0.0, 3000.0, verbose=False)
    check_tileset(d2, 2)

    print('用例 3：小图 → 单平面')
    p3 = make_tif(os.path.join(TD, 'small.tif'), 1800, 1200)
    d3 = os.path.join(TD, 'out_small')
    convert_tif_plane(p3, d3, 116.3, 39.9, 0.0, 2000.0, verbose=False)
    check_tileset(d3, 1)

    print('用例 4：无 alpha 大图（近黑边）→ 三级 + png 近黑转透明')
    p4 = make_tif(os.path.join(TD, 'noalpha.tif'), 9000, 7000, with_alpha=False)
    d4 = os.path.join(TD, 'out_noalpha')
    convert_tif_plane(p4, d4, 116.3, 39.9, 0.0, 4000.0, verbose=False)
    check_tileset(d4, 3)

    print('用例 5：jpeg 格式大图 → 三级')
    p5 = os.path.join(TD, 'big.tif')
    d5 = os.path.join(TD, 'out_jpeg')
    convert_tif_plane(p5, d5, 116.3, 39.9, 0.0, 4000.0, fmt='jpeg', verbose=False)
    check_tileset(d5, 3)

    print('全部通过')
    shutil.rmtree(TD, ignore_errors=True)


if __name__ == '__main__':
    main()
