# -*- coding: utf-8 -*-
"""geoconvert 统一 CLI：OBJ / OSGB / TIF → 3D Tiles。

用法:
  geoconvert / python -m geoconvert   (无参数) 启动图形界面（内嵌单窗口，需 WebView2）
  geoconvert gui                       同上
  geoconvert web [--port 端口]         图形界面走系统浏览器（WebView2 不可用时的后门）
  geoconvert obj  <input> <output> [options]    # OBJ 分块 → 三级 LOD b3dm
  geoconvert osgb <input> --out DIR [options]   # OSGB (Smart3D) → b3dm LOD 树
  geoconvert tif  <tif> <output> [options]      # 正射影像 → 贴图 3D 平面

定位方式（obj/osgb 通用）:
  --transform-from TILESET  复制参考 tileset.json 的 root.transform（与既有模型重合）
  --lat X --lon Y           ENU 原点经纬度
  （都不给时 obj 默认赤道 ENU 经应用内模型调整定位；osgb 读 metadata.xml）
"""
import sys

USAGE = __doc__


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] == 'gui':
        from .webui import run_gui
        return run_gui([])
    if argv[0] == 'web':
        from .webui import run_gui
        return run_gui(argv[1:], force_browser=True)
    if argv[0].startswith('--port') or argv[0] == '-p':
        from .webui import run_gui
        return run_gui(argv)
    if argv[0] in ('-h', '--help', 'help'):
        print(USAGE)
        return 0
    cmd = argv[0]
    if cmd == 'obj':
        from .objconv.convert import main as m
    elif cmd == 'osgb':
        from .osgb.convert import main as m
    elif cmd == 'tif':
        from .tifconv.convert import main as m
    else:
        print('未知命令: %s\n' % cmd, file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    return m(argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())
