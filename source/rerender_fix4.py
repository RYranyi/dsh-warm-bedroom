# -*- coding: utf-8 -*-
"""Re-render 4 segments with the CORRECT folder mapping.

Bug being fixed: the earlier re-render used dict keys {3: desk, 8: storm}, but the
render table maps  seg_02 = 03_desk_window, seg_03 = 04_tv, seg_07 = 08_storm,
seg_08 = 09_rainy.  So seg_03/seg_08 were overwritten with the wrong shots and the
TV + rainy shots were lost.

This script restores all four:
  seg_02  03_desk_window  NEW framing (morning)
  seg_03  04_tv           ORIGINAL framing (dusk)
  seg_07  08_storm        NEW framing (storm)
  seg_08  09_rainy        ORIGINAL framing (rainy)

Quality unchanged: 1920x1080, 10 samples, adaptive, OptiX denoise.
"""
import bpy, os, sys, time
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

BLEND = paths.blend()
OUT = paths.scratch("video", "frames")
FPS = 24
SEG_FRAMES = 144
RES = (1920, 1080)
SAMPLES = 10

SEGS = {
    2: dict(name="03_desk_window", time="morning", weather="sunny",
            start=(0.10, -0.90, 1.60), end=(0.42, -0.55, 1.62), look=(1.95, 1.12, 0.96)),
    3: dict(name="04_tv", time="dusk", weather="sunny",
            start=(0.45, -0.9, 1.58), end=(0.28, -1.35, 1.62), look=(0.0, -2.442, 1.32)),
    7: dict(name="08_storm", time="dusk", weather="storm",
            start=(-1.10, -0.50, 1.62), end=(-0.80, -0.20, 1.60), look=(2.20, 1.25, 1.15)),
    8: dict(name="09_rainy", time="dusk", weather="rainy",
            start=(0.5, -0.9, 1.55), end=(-0.35, -0.4, 1.6), look=(1.3, 1.3, 1.25)),
}

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
ctrl = bpy.data.texts.get("scene_controller.py")
ns = {"__name__": "fix_four", "bpy": bpy}
exec(compile(ctrl.as_string(), "scene_controller.py", "exec"), ns)

sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_adaptive_sampling = True
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = "OPTIX"
except Exception:
    pass
sc.render.resolution_x = RES[0]
sc.render.resolution_y = RES[1]
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.fps = FPS

cam = bpy.data.objects.new("Fix4_Cam", bpy.data.cameras.new("Fix4_Cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 35.0


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return [a[i] + (b[i] - a[i]) * t for i in range(3)]


def set_cam(pos, look):
    p = Vector(pos)
    d = Vector(look) - p
    if d.length > 1e-6:
        cam.matrix_world = d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
        cam.matrix_world.translation = p


total = len(SEGS) * SEG_FRAMES
done = 0
t_all = time.time()
print("PLAN " + " | ".join("seg_%02d=%s" % (k, SEGS[k]["name"]) for k in sorted(SEGS)))

for si in sorted(SEGS):
    s = SEGS[si]
    ns["set_time_of_day"](s["time"])
    ns["set_weather"](s["weather"])
    d = os.path.join(OUT, "seg_%02d" % si)
    os.makedirs(d, exist_ok=True)
    for f in range(SEG_FRAMES):
        t = f / (SEG_FRAMES - 1)
        set_cam(lerp(s["start"], s["end"], ease(t)), s["look"])
        sc.render.filepath = os.path.join(d, "frame_%04d.png" % f)
        bpy.ops.render.render(scene=sc.name, write_still=True)
        done += 1
        if done % 12 == 0:
            el = time.time() - t_all
            rate = el / done
            print("PROGRESS %d/%d  %.2fs/f  elapsed=%.1fmin  eta=%.1fmin" % (
                done, total, rate, el / 60, (total - done) * rate / 60))
    print("SEG%02d DONE %s" % (si, s["name"]))

print("FIX4_DONE frames=%d elapsed=%.1fmin" % (done, (time.time() - t_all) / 60))
