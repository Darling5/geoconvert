# -*- coding: utf-8 -*-
import sys, os

d = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.environ.get('TEMP', '.'), 'gc_alpha_test')
needle = b'"alphaMode":"BLEND"'
for f in sorted(os.listdir(d)):
    if f.endswith('.b3dm'):
        raw = open(os.path.join(d, f), 'rb').read()
        print(f, '-> alphaMode BLEND:', needle in raw)
