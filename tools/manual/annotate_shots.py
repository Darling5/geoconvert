# -*- coding: utf-8 -*-
"""手册截图标注：序号圈 + 红框 + 黄色高亮 + 箭头。
截图 2586x1871 = CSS 1724x1247 x DPR 1.5，坐标按 CSS 写再乘 1.5。
坐标全部来自浏览器 getBoundingClientRect 实测（viewport 1724x1247 @ DPR 1.5）。
"""
import os
from PIL import Image, ImageDraw, ImageFont

SRC = r"D:\WEB\zicaiduck\geo-convert\tools\manual\shots_raw"
DST = r"D:\WEB\zicaiduck\geo-convert\tools\manual\shots"
S = 1.5
RED = (255, 59, 48, 255)
YEL = (255, 214, 0)

font_path = "C:/Windows/Fonts/arialbd.ttf"


def load(name):
    return Image.open(os.path.join(SRC, name)).convert("RGBA")


def save(img, name):
    os.makedirs(DST, exist_ok=True)
    out = os.path.join(DST, name)
    img.convert("RGB").save(out)
    print("saved", out)


class Pen:
    def __init__(self, img):
        self.img = img
        self.overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.overlay)

    def box(self, css, w=6, pad=8, color=RED):
        """红框：css=(x,y,w,h)"""
        x, y, w2, h = [int(v * S) for v in css]
        self.d.rounded_rectangle(
            [x - pad, y - pad, x + w2 + pad, y + h + pad],
            radius=12, outline=color, width=w)

    def highlight(self, css, alpha=80):
        """黄色半透明高亮 + 红细框"""
        x, y, w, h = [int(v * S) for v in css]
        self.d.rectangle([x, y, x + w, y + h], fill=YEL + (alpha,),
                         outline=RED, width=4)

    def num(self, n, css_xy, r=42, fs=50):
        """红色序号圆圈，css_xy 为圆心（CSS 坐标），r/fs 为物理像素"""
        cx, cy = int(css_xy[0] * S), int(css_xy[1] * S)
        self.d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=RED)
        f = ImageFont.truetype(font_path, fs)
        self.d.text((cx, cy), str(n), font=f, fill=(255, 255, 255, 255),
                    anchor="mm")

    def arrow(self, css_from, css_to, w=7):
        """箭头：从 from 指向 to（CSS 坐标）"""
        x1, y1 = int(css_from[0] * S), int(css_from[1] * S)
        x2, y2 = int(css_to[0] * S), int(css_to[1] * S)
        self.d.line([x1, y1, x2, y2], fill=RED, width=w)
        import math
        ang = math.atan2(y2 - y1, x2 - x1)
        L, Wd = 34, 26
        p1 = (x2, y2)
        p2 = (x2 - L * math.cos(ang) + Wd * math.sin(ang) / 2,
              y2 - L * math.sin(ang) - Wd * math.cos(ang) / 2)
        p3 = (x2 - L * math.cos(ang) - Wd * math.sin(ang) / 2,
              y2 - L * math.sin(ang) + Wd * math.cos(ang) / 2)
        self.d.polygon([p1, p2, p3], fill=RED)

    def done(self):
        self.img.alpha_composite(self.overlay)
        return self.img


# ---------- m0 开始之前：主界面与左侧四个页签（s1） ----------
# 侧栏实测 .side = (278, 91.9, 158, 255.3)，四个页签 y 中心 120.6/185.2/251.2/317.2
img = load("s1-conv-blank.png")
p = Pen(img)
p.box((278, 92, 158, 255))              # 左侧功能栏
p.num(1, (240, 121))                    # 模型转换
p.num(2, (240, 185))                    # 坐标转换
p.num(3, (240, 251))                    # 3D 预览
p.num(4, (240, 317))                    # 注册模型
save(p.done(), "m0-sidebar.png")

# ---------- m1 第1步：选格式 + 选输入（s1） ----------
# 输入行实测 #input(546.7,192.3,797.3,31.3) + #btn-in(1354,190.3,75.3,35.3)
img = load("s1-conv-blank.png")
p = Pen(img)
p.box((473, 111, 957, 68), pad=3)       # 格式三卡片 OBJ/OSGB/TIF
p.num(1, (1462, 145))                   # 右侧，与卡片框同一水平带
p.box((540, 186, 895, 48), pad=3)       # 输入行 + 浏览按钮
p.num(2, (1466, 210))
save(p.done(), "m1-fmt-input.png")

# ---------- m2 第1步续：浏览弹层整夹上传（s2） ----------
# 弹层实测 .modal-box(542,383.7,640,480)；列表 #br-list(542.7,475.4,638.7,331.6)
# 「选择当前目录」#br-pick(978.7,817.7,117.3,35.3)；「＋ 新建文件夹」#br-newdir(877.2,394.3,121.2,35.3)
img = load("s2-browse-multiblock.png")
p = Pen(img)
p.box((543, 475, 639, 332))             # Block 文件夹列表
p.num(1, (518, 462))
p.num(2, (1037, 940))                   # 弹层下方遮罩上
p.arrow((1037, 912), (1037, 860))       # 直上指向「选择当前目录」
p.num(3, (938, 300))                    # 弹层上方遮罩上
p.arrow((938, 328), (938, 389))         # 直下指向「＋ 新建文件夹」
save(p.done(), "m2-browse-dir.png")

# ---------- m3 第2步：坐标转换页（s3） ----------
# 实测 #cc-in(546.7,139.3,811.3,31.3) #cc-go(1368,137.3,61.3,35.3)
#      #cc-out(546.7,190.3,504.5,16) #cc-use-ll(1061.2,180.7,168.7,35.3)
img = load("s3-coord-result.png")
p = Pen(img)
p.box((547, 139, 883, 31), pad=5)       # 链接输入框 + 解析按钮整行
p.num(1, (522, 126))
p.num(2, (1466, 155))                   # 「解析」按钮右侧
p.highlight((543, 188, 511, 22))        # 解析出的 WGS-84 结果文字
p.num(3, (560, 199))                    # 圆圈压在高亮左端
p.box((1061, 181, 169, 35), pad=5)      # 「填入 OBJ/OSGB 定位」按钮
p.num(4, (1036, 198), r=34, fs=40)     # 高亮与按钮之间
save(p.done(), "m3-coord.png")

# ---------- m4 第3步：导出目录 + 定位确认 + 开始转换（s4） ----------
# 实测 #output(546.7,235.6,797.3,31.3)+#btn-out(1354,233.6,75.3,35.3)
#      #loc-ll(472.7,379.8,956.7,31.3) #start(456,624.6,125.3,39.3)
img = load("s4-conv-filled.png")
p = Pen(img)
p.box((540, 230, 895, 48))              # 输出行 + 浏览按钮
p.num(1, (515, 219))
p.highlight((543, 377, 300, 36))        # 纬度/经度（已由第2步自动填入）
p.num(2, (448, 395))
p.num(3, (300, 733))
p.arrow((335, 715), (513, 647))         # 指向「开始转换」
save(p.done(), "m4-output-start.png")

# ---------- m5 第4步：转换完成（s5） ----------
# 状态文字实测约 (1245,640,200,18)（btnbar 行 y 624.6-664，右对齐）
img = load("s5-conv-done.png")
p = Pen(img)
p.highlight((473, 975, 957, 32))        # 日志最后一行「完成：用时…」
p.num(1, (448, 965))
p.box((1240, 628, 196, 32))             # 右上角状态「完成 · 用时 …」
p.num(2, (1208, 606))
save(p.done(), "m5-done.png")

# ---------- m6 第4步续：注册表单（s6） ----------
# 实测 #btn-regfind(1340,137.3,89.3,35.3) #reg-dir(546.7,224,410.3,31.3)
#      #reg-name(546.7,263.3,882.7,31.3) #reg-do(472.7,348,125.3,39.3)
img = load("s6-register-filled.png")
p = Pen(img)
p.num(1, (1525, 65))
p.arrow((1490, 78), (1388, 154))        # 指向「自动探测」
p.box((547, 224, 410, 31), pad=3)       # 目录名
p.num(2, (522, 213))
p.box((547, 263, 883, 31), pad=3)       # 显示名称
p.num(3, (522, 252))
p.num(4, (300, 462))
p.arrow((335, 445), (510, 372))         # 指向「注册模型」
save(p.done(), "m6-register.png")

# ---------- m7 第5步：3D 预览微调 + 保存（s7） ----------
# 实测 #pv-save(838.3,185,201.4,35.3) 透明度组(938.4,284,252.2,37.3)
#      画布 #pv-viewer(472.7,331.3,956.7,480)
img = load("s7-preview.png")
p = Pen(img)
p.box((795, 420, 320, 250), w=5)        # 模型 + 三轴控件区
p.num(1, (770, 408))
p.box((938, 284, 253, 38), pad=5)       # 透明度滑块组
p.num(2, (1230, 302))
p.box((838, 185, 202, 36), pad=5)       # 「保存（烘焙）」按钮
p.num(3, (845, 216), r=34, fs=40)      # 按钮左下角
save(p.done(), "m7-preview.png")

print("ALL DONE")
