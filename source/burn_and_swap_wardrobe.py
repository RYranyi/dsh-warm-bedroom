# -*- coding: utf-8 -*-
"""Burn subtitle #6 onto the new wardrobe frames, swap them into the decoded film,
then re-encode once.

Why: the new block was rendered raw (no burned subtitles), while every other frame
in the delivered film already has libass-burned Chinese text. Without this step the
wardrobe block would be the only shot without a subtitle.

Steps
  1. write a block-local SRT (same text, same style, 0 -> 5.458 s)
  2. burn it onto frames/seg_04/frame_0000..0129 with FFV1 (lossless) round-trip
  3. copy the burned PNGs over decoded f_0665..f_0794
  4. re-encode the 1444-frame sequence
"""
import subprocess, os, shutil, codecs, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

QA = paths.scratch("qa")
FRAMES = os.path.join(QA, "frames")
NEW = paths.scratch("video", "frames", "seg_04")
SRT = os.path.join(QA, "block6.srt")
BURNED_MKV = os.path.join(QA, "block6_burned.mkv")
BURNED_DIR = os.path.join(QA, "block6_burned")
OUT = os.path.join(QA, "warm_bedroom_intro_v3.mp4")
BLOCK_START_0 = 664
BLOCK_N = 130
TOTAL = 1444

TEXT = "胡桃木门与双开衣柜对称而立，细长拉手与竖向分格，收纳与秩序感并存。"
STYLE = ("FontName=Microsoft YaHei,FontSize=16,PrimaryColour=&H00FFFFFF,"
         "OutlineColour=&H00101010,BorderStyle=1,Outline=2,Shadow=1,"
         "MarginV=44,Alignment=2")


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("FAILED: %s\n%s" % (" ".join(cmd), r.stderr[-3000:]))
    return r


def esc(p):
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


# 1. block-local SRT -------------------------------------------------------
end = (BLOCK_N + 1) / 24.0          # cover the last frame fully
with codecs.open(SRT, "w", "utf-8-sig") as f:
    f.write("1\n00:00:00,000 --> %s\n%s\n" % (
        ("00:00:%06.3f" % end).replace(".", ","), TEXT))
print("srt:", open(SRT, encoding="utf-8-sig").read().replace("\n", " | "))

# 2. burn (lossless) -------------------------------------------------------
os.makedirs(BURNED_DIR, exist_ok=True)
vf = "subtitles='%s':force_style='%s'" % (esc(SRT), STYLE)
run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
     "-framerate", "24", "-i", os.path.join(NEW, "frame_%04d.png"),
     "-frames:v", str(BLOCK_N), "-vf", vf,
     "-c:v", "ffv1", "-pix_fmt", "bgr0", BURNED_MKV])
run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
     "-i", BURNED_MKV, "-vsync", "0", os.path.join(BURNED_DIR, "b_%04d.png")])
burned = sorted(f for f in os.listdir(BURNED_DIR) if f.endswith(".png"))
print("burned frames:", len(burned))

# 3. swap into the decoded pool -------------------------------------------
have = sorted(f for f in os.listdir(FRAMES) if f.startswith("f_") and f.endswith(".png"))
if len(have) != TOTAL:
    raise SystemExit("decoded pool has %d frames, expected %d" % (len(have), TOTAL))
if len(burned) < BLOCK_N:
    raise SystemExit("only %d burned frames" % len(burned))
for i in range(BLOCK_N):
    shutil.copyfile(os.path.join(BURNED_DIR, "b_%04d.png" % (i + 1)),
                    os.path.join(FRAMES, "f_%04d.png" % (BLOCK_START_0 + i + 1)))
print("swapped f_%04d..f_%04d" % (BLOCK_START_0 + 1, BLOCK_START_0 + BLOCK_N))

# 4. encode ---------------------------------------------------------------
run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
     "-framerate", "24", "-i", os.path.join(FRAMES, "f_%04d.png"),
     "-frames:v", str(TOTAL),
     "-c:v", "libx264", "-preset", "medium", "-crf", "16",
     "-profile:v", "high", "-pix_fmt", "yuv420p",
     "-movflags", "+faststart", OUT])

pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height,nb_frames,r_frame_rate,pix_fmt",
                     "-show_entries", "format=duration,size", "-of", "default=noprint_wrappers=1", OUT],
                    capture_output=True, text=True)
print(pr.stdout.strip())
print("WROTE", OUT, os.path.getsize(OUT))
