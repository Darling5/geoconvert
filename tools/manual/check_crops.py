# -*- coding: utf-8 -*-
"""裁剪标注图的关键区域，放大 2 倍检查箭头/框指向是否正确。"""
import sys
from PIL import Image

SHOTS = r"D:\WEB\zicaiduck\geo-convert\tools\manual\shots"
S = 1.5

def crop(src, css, out, zoom=1.6):
    img = Image.open("%s\\%s" % (SHOTS, src))
    x, y, w, h = [int(v * S) for v in css]
    c = img.crop((x, y, x + w, y + h))
    c = c.resize((int(c.width * zoom), int(c.height * zoom)), Image.LANCZOS)
    c.save("%s\\_%s" % (SHOTS, out))
    print("saved _%s" % out)

# m3 右侧：填入按钮 + 坐标系下拉区域
crop("m3-coord.png", (1000, 150, 1724, 360), "chk-m3-buttons.png")
# m7 顶部：按钮行 + 数值面板 + 滑块
crop("m7-preview.png", (600, 160, 1724, 340), "chk-m7-panel.png")
# m5 底部：日志完成行 + 状态
crop("m5-done.png", (400, 600, 1724, 1050), "chk-m5-log.png")
# m2 底部：选择当前目录按钮
crop("m2-browse-dir.png", (700, 350, 1724, 900), "chk-m2-modal.png")
