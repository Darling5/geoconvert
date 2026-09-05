# -*- coding: utf-8 -*-
"""3D Tiles 1.1 (glb) 输出冒烟测试：与 1.0 对比结构、朝向节点、参数链路。"""
import json
import os
import struct
import subprocess
import sys
import tempfile

ROOT = r"D:\WEB\zicaiduck\geo-convert"
sys.path.insert(0, ROOT)

SMOKE_OBJ = os.path.join(ROOT, "tools", "smoke", "obj", "smoke.obj")


def glb_json(data):
    """解 GLB 头取 JSON chunk。"""
    magic, ver, total = struct.unpack_from("<4sII", data, 0)
    assert magic == b"glTF" and ver == 2, "不是 GLB"
    jlen, jmagic = struct.unpack_from("<I4s", data, 12)
    assert jmagic == b"JSON"
    return json.loads(data[20:20 + jlen].decode("utf-8"))


def check(out_dir, expect_ver, expect_ext):
    ts_path = os.path.join(out_dir, "tileset.json")
    with open(ts_path, encoding="utf-8") as f:
        ts = json.load(f)
    assert ts["asset"]["version"] == expect_ver, \
        "asset.version=%s 期望 %s" % (ts["asset"].get("version"), expect_ver)
    if expect_ver == "1.1":
        assert "gltfUpAxis" not in ts["asset"], "1.1 不应带 gltfUpAxis"
    else:
        assert ts["asset"].get("gltfUpAxis") == "Z", "1.0 应带 gltfUpAxis Z"

    # 找到第一个有 content 的 tile，检查扩展名与 glb 结构
    def walk(node):
        if "content" in node:
            yield node
        for c in node.get("children", []):
            yield from walk(c)

    tiles = list(walk(ts["root"]))
    assert tiles, "无 content tile"
    for t in tiles:
        uri = t["content"]["uri"]
        assert uri.endswith("." + expect_ext), "uri=%s 期望 .%s" % (uri, expect_ext)
        p = os.path.join(out_dir, uri)
        assert os.path.isfile(p), "缺文件 %s" % p
        if expect_ext == "glb":
            with open(p, "rb") as f:
                g = glb_json(f.read())
            nodes = g["nodes"]
            rot_node = next((n for n in nodes if "rotation" in n), None)
            assert rot_node is not None, "glb 缺 Y-up 旋转根节点"
            assert rot_node["rotation"][0] < 0 and abs(abs(rot_node["rotation"][0]) - 0.70710678) < 1e-6
            assert rot_node["rotation"][3] > 0
        else:
            with open(p, "rb") as f:
                head = f.read(4)
            assert head == b"b3dm", "不是 b3dm"
    return len(tiles)


def main():
    tmp = tempfile.mkdtemp(prefix="gc_tiles11_")
    out10 = os.path.join(tmp, "v10")
    out11 = os.path.join(tmp, "v11")
    for out, ver in ((out10, "1.0"), (out11, "1.1")):
        r = subprocess.run(
            [sys.executable, "-m", "geoconvert", "obj", SMOKE_OBJ, out,
             "--lat", "42.19", "--lon", "88.46", "--tiles-version", ver, "-q"],
            cwd=ROOT, capture_output=True, text=True)
        assert r.returncode == 0, "%s 转换失败:\n%s" % (ver, r.stderr)
    n10 = check(out10, "1.0", "b3dm")
    n11 = check(out11, "1.1", "glb")
    print("OK: 1.0=%d tiles (b3dm), 1.1=%d tiles (glb)" % (n10, n11))

    # 默认值不传参 = 1.0
    outd = os.path.join(tmp, "def")
    r = subprocess.run([sys.executable, "-m", "geoconvert", "obj", SMOKE_OBJ,
                        outd, "-q"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    check(outd, "1.0", "b3dm")
    print("OK: 默认（不传参）= 1.0 b3dm")

    # 参数链路：validate → build_argv
    from geoconvert.params import validate, build_argv
    vals, err = validate("OBJ", SMOKE_OBJ, out11, lat="42.19", lon="88.46",
                         tiles="1.1")
    assert not err, err
    argv = build_argv(vals)
    assert "--tiles-version" in argv and argv[argv.index("--tiles-version") + 1] == "1.1"
    vals, _ = validate("OBJ", SMOKE_OBJ, out11, tiles="1.0")
    assert "--tiles-version" not in build_argv(vals)
    vals, _ = validate("OBJ", SMOKE_OBJ, out11)  # 空值 → 默认 1.0
    assert "--tiles-version" not in build_argv(vals)
    print("OK: 参数链路 validate/build_argv")

    # 两个版本 root.transform 应完全一致（位置不变）
    with open(os.path.join(out10, "tileset.json"), encoding="utf-8") as f:
        t10 = json.load(f)
    with open(os.path.join(out11, "tileset.json"), encoding="utf-8") as f:
        t11 = json.load(f)
    assert t10["root"]["transform"] == t11["root"]["transform"], "transform 漂移"
    print("OK: 两版本 root.transform 一致")
    print("\n全部通过")


if __name__ == "__main__":
    main()
