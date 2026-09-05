# -*- coding: utf-8 -*-
"""统计所有 OSGB 文件的节点类型、图元模式、索引类型、法线/纹理情况。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from geoconvert.osgb.reader import read_osgb

ROOT = r'D:\BaiduNetdiskDownload\库米什压气站模型\OSGB\Data'


def walk(node, st):
    st['class:%s' % node.cls] = st.get('class:%s' % node.cls, 0) + 1
    if node.cls == 'osg::PagedLOD':
        st['paged_children_files'] += len([f for f in node.file_names if f])
        if len(node.file_names) != 2:
            st['file_names_len_%d' % len(node.file_names)] = \
                st.get('file_names_len_%d' % len(node.file_names), 0) + 1
        if len(node.range_list) != 2:
            st['range_len_%d' % len(node.range_list)] = \
                st.get('range_len_%d' % len(node.range_list), 0) + 1
        if node.range_mode != 1:
            st['range_mode_%d' % node.range_mode] = st.get('range_mode_%d' % node.range_mode, 0) + 1
    for d in getattr(node, 'drawables', []):
        st['geoms'] += 1
        if d.normals:
            st['has_normals'] += 1
        if len(d.texcoords) > 1:
            st['multi_texcoord'] += 1
        if not d.texcoords:
            st['no_texcoord'] += 1
        for p in d.primitives:
            st['prim_type_%d' % p['type']] = st.get('prim_type_%d' % p['type'], 0) + 1
            st['prim_mode_%d' % p['mode']] = st.get('prim_mode_%d' % p['mode'], 0) + 1
            if 'first' in p:
                st['drawarrays'] += 1
        if d.state_set:
            units = d.state_set.texture_attributes
            st['tex_units_%d' % len(units)] = st.get('tex_units_%d' % len(units), 0) + 1
            for unit in units:
                ntex = sum(1 for o in unit if o is not None)
                if ntex != 1:
                    st['unit_attrs_%d' % ntex] = st.get('unit_attrs_%d' % ntex, 0) + 1
    for c in getattr(node, 'children', []):
        walk(c, st)


def main():
    files = []
    for dp, _, fns in os.walk(ROOT):
        for f in fns:
            if f.lower().endswith('.osgb'):
                files.append(os.path.join(dp, f))
    st = {'paged_children_files': 0, 'geoms': 0, 'has_normals': 0,
          'multi_texcoord': 0, 'no_texcoord': 0, 'drawarrays': 0}
    for fp in files:
        root = read_osgb(open(fp, 'rb').read())
        walk(root, st)
    for k in sorted(st):
        print('%-28s %d' % (k, st[k]))


if __name__ == '__main__':
    main()
