# -*- coding: utf-8 -*-
"""Build the Chinese SRT for the ~60 s intro.

Timeline (24 fps):
  prologue        144 fr = 6.000 s   (制作过程: 线框 -> 白模 -> 成品)
  10 x segments   130 fr = 5.4167 s  each
  total          1444 fr = 60.1667 s
"""
import codecs, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

PRO_SEC = 144 / 24.0
SEG_FRAMES = 130
SEG_SEC = SEG_FRAMES / 24.0

LINES = [
    # prologue
    "制作过程：从线框、白模到材质与灯光，898 个对象逐件搭建。",
    # 10 showcase segments
    "开场：夕阳斜照，暖色木纹与现代家具交响，一间属于你的卧室。",
    "焦点落在床头：画芯居中、白卡纸与玻璃装裱，床头灯把暖意留在墙上。",
    "晨光涌上窗台：1.2 米书桌、笔记本与咖啡，光从半透窗纱漫进来。",
    "黄昏点亮电视屏：冷光自屏幕漫出，与满室暖木色相撞。",
    "胡桃木门与双开衣柜对称而立，细长拉手与竖向分格，收纳与秩序感并存。",
    "正午日光最盛：窗台绿植与半透窗纱，把整面墙都照得发亮。",
    "入夜只留床头灯与屏幕微光：暖黄光晕把床团成最柔软的一角。",
    "风暴卷过屋外：城市剪影与雨线划过窗面，室内灯自动亮起，守住一方安稳。",
    "雨天自动点亮全屋：窗外阴沉，屋内依旧温暖明亮、干爽可居。",
    "从晨光到深夜、从晴天到暴雨，每个时刻这间屋子都在回应生活。暖居，静候归家。",
]

# beat boundaries in seconds
bounds = [0.0, PRO_SEC]
for i in range(len(LINES) - 1):
    bounds.append(PRO_SEC + (i + 1) * SEG_SEC)


def ts(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec % 60
    return ("%02d:%02d:%06.3f" % (h, m, s)).replace(".", ",")


blocks = []
for i, text in enumerate(LINES):
    start = bounds[i]
    end = bounds[i + 1] if i + 1 < len(bounds) else PRO_SEC + (len(LINES) - 1) * SEG_SEC
    blocks.append("%d\n%s --> %s\n%s\n" % (i + 1, ts(start), ts(end), text))

out = paths.scratch("video", "subtitles.srt")
os.makedirs(os.path.dirname(out), exist_ok=True)
with codecs.open(out, "w", "utf-8-sig") as f:
    f.write("\n".join(blocks))

total = PRO_SEC + (len(LINES) - 1) * SEG_SEC
print("SRT_WRITTEN", out, "entries", len(LINES), "duration %.3fs" % total)
for i, s in enumerate(LINES):
    w = sum(1.0 if ord(c) > 0x2E80 else 0.5 for c in s)
    flag = "  <-- TOO WIDE" if w > 34 else ""
    print("  %2d  width=%4.1f  %s%s" % (i + 1, w, s[:14], flag))
