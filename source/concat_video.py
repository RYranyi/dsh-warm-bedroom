# -*- coding: utf-8 -*-
"""Encode the ~60 s intro: 6 s prologue (制作过程) + 10 shots x 5.42 s, burn Chinese SRT.

  frames/seg_pro/frame_0000..0143.png   144 fr @24 = 6.000 s
  frames/seg_00..seg_09/frame_0000..0129.png  first 130 fr each = 5.4167 s
  total 1444 fr = 60.167 s
"""
import subprocess, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

FRAMES = paths.scratch("video", "frames")
SRT = paths.scratch("video", "subtitles.srt")
OUT = paths.scratch("video", "warm_bedroom_intro.mp4")
WORK = paths.scratch("video", "concat_work")
FPS = 24
W, H = 1920, 1080
PRO_FRAMES = 144
SEG_FRAMES = 130
NSEG = 10
os.makedirs(WORK, exist_ok=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("FFMPEG FAILED: %s\n%s" % (" ".join(cmd), r.stderr[-2000:]))
    return r


def esc(p):
    return p.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


# ---- verify every frame we need is on disk --------------------------------
missing = []
for f in range(PRO_FRAMES):
    if not os.path.exists(os.path.join(FRAMES, "seg_pro", "frame_%04d.png" % f)):
        missing.append("seg_pro/frame_%04d" % f)
for i in range(NSEG):
    d = os.path.join(FRAMES, "seg_%02d" % i)
    for f in range(SEG_FRAMES):
        if not os.path.exists(os.path.join(d, "frame_%04d.png" % f)):
            missing.append("seg_%02d/frame_%04d" % (i, f))
if missing:
    raise SystemExit("MISSING %d frames, first: %s" % (len(missing), missing[:5]))
total_frames = PRO_FRAMES + NSEG * SEG_FRAMES
print("ALL %d FRAMES PRESENT (%.3f s)" % (total_frames, total_frames / float(FPS)))

# ---- encode every shot ----------------------------------------------------
jobs = [("pro", "seg_pro", PRO_FRAMES)]
jobs += [("seg_%02d" % i, "seg_%02d" % i, SEG_FRAMES) for i in range(NSEG)]

parts = []
for name, folder, nfr in jobs:
    mp4 = os.path.join(WORK, "%s.mp4" % name)
    pat = os.path.join(FRAMES, folder) + "\\frame_%04d.png"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-framerate", str(FPS), "-i", pat,
         "-frames:v", str(nfr),
         "-vf", "scale=%d:%d,format=yuv420p" % (W, H),
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", mp4])
    parts.append(mp4)
    print("ENCODED", name, nfr, "fr")

with open(os.path.join(WORK, "concat.txt"), "w") as f:
    for mp4 in parts:
        f.write("file '%s'\n" % mp4.replace("\\", "/"))

silent = os.path.join(WORK, "silent.mp4")
run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
     "-f", "concat", "-safe", "0",
     "-i", os.path.join(WORK, "concat.txt"), "-c", "copy", silent])
print("SILENT OK")

# ---- burn subtitles -------------------------------------------------------
style = ("FontName=Microsoft YaHei,FontSize=16,PrimaryColour=&H00FFFFFF,"
         "OutlineColour=&H00101010,BorderStyle=1,Outline=2,Shadow=1,"
         "MarginV=44,Alignment=2")
vf = "subtitles='%s':force_style='%s'" % (esc(SRT), style)
run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
     "-i", silent, "-vf", vf,
     "-c:v", "libx264", "-preset", "medium", "-crf", "18",
     "-pix_fmt", "yuv420p", OUT])

print("VIDEO_WRITTEN", OUT, os.path.getsize(OUT))
