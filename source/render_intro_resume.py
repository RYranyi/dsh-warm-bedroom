# -*- coding: utf-8 -*-
"""Resume the FULL original plan: 10 segments x 144 frames (6 s each) = 1440.

Progress on disk when this runs:
  seg_00..seg_04 : complete (144 each)
  seg_05         : partial  -> resumes at the missing frame
  seg_06..seg_09 : not started

Keeps the original quality: 1920x1080, 10 samples, adaptive, OptiX denoise.
"""
import bpy, os, time
from mathutils import Vector

BLEND = r"E:\dsh\bedroom_scene\warm_bedroom_v2.blend"
OUT = r"E:\dsh\.scratch\video\frames"
FPS = 24
SEG_FRAMES = 144
RES = (1920, 1080)
SAMPLES = 10

# full original segment table (index order matters)
SEGS = [
    dict(name="01_overview", time="dusk", weather="sunny",
         start=(-0.7, 2.28, 1.55), end=(0.45, -1.85, 1.62), look=(0.0, -0.4, 1.2)),
    dict(name="02_bed_art", time="dusk", weather="sunny",
         start=(-0.55, -2.15, 1.5), end=(0.35, -2.25, 1.62), look=(0.0, 2.35, 1.65)),
    dict(name="03_desk_window", time="morning", weather="sunny",
         start=(1.25, 0.45, 1.62), end=(1.65, 0.15, 1.72), look=(2.25, 1.45, 1.6)),
    dict(name="04_tv", time="dusk", weather="sunny",
         start=(0.45, -0.9, 1.58), end=(0.28, -1.35, 1.62), look=(0.0, -2.42, 1.32)),
    dict(name="05_wardrobe_door", time="dusk", weather="sunny",
         start=(0.85, -0.35, 1.6), end=(1.05, 0.15, 1.62), look=(-1.72, -0.05, 1.5)),
    dict(name="06_plants", time="noon", weather="sunny",
         start=(0.55, 0.6, 1.5), end=(0.85, 0.35, 1.6), look=(1.8, 1.35, 1.35)),
    dict(name="07_night", time="night", weather="sunny",
         start=(-0.2, -0.6, 1.55), end=(0.2, -1.4, 1.6), look=(1.13, 2.27, 1.0)),
    dict(name="08_storm", time="dusk", weather="storm",
         start=(1.95, 1.5, 1.55), end=(2.15, 1.4, 1.6), look=(4.4, 1.45, 1.6)),
    dict(name="09_rainy", time="dusk", weather="rainy",
         start=(0.5, -0.9, 1.55), end=(-0.35, -0.4, 1.6), look=(1.3, 1.3, 1.25)),
    dict(name="10_outro", time="dusk", weather="sunny",
         start=(0.0, 2.4, 1.7), end=(0.0, 2.0, 1.7), look=(0.0, -0.9, 1.15)),
]

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
ctrl = bpy.data.texts.get("scene_controller.py")
ns = {"__name__": "resume_full", "bpy": bpy}
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

cam = bpy.data.objects.new("Full_Cam", bpy.data.cameras.new("Full_Cam"))
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


def missing_frames(si):
    d = os.path.join(OUT, "seg_%02d" % si)
    have = set()
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.startswith("frame_") and f.endswith(".png"):
                try:
                    have.add(int(f[6:10]))
                except ValueError:
                    pass
    return [i for i in range(SEG_FRAMES) if i not in have]


t_all = time.time()
total_todo = 0
for si in range(len(SEGS)):
    total_todo += len(missing_frames(si))
print("TODO_FRAMES", total_todo)

done = 0
for si, s in enumerate(SEGS):
    todo = missing_frames(si)
    if not todo:
        print("SEG%02d SKIP (complete)" % si)
        continue
    ns["set_time_of_day"](s["time"])
    ns["set_weather"](s["weather"])
    d = os.path.join(OUT, "seg_%02d" % si)
    os.makedirs(d, exist_ok=True)
    for f in todo:
        t = f / (SEG_FRAMES - 1)
        set_cam(lerp(s["start"], s["end"], ease(t)), s["look"])
        sc.render.filepath = os.path.join(d, "frame_%04d.png" % f)
        bpy.ops.render.render(scene=sc.name, write_still=True)
        done += 1
        if done % 20 == 0:
            el = time.time() - t_all
            rate = el / done
            print("PROGRESS %d/%d  %.2fs/f  elapsed=%.1fmin  eta=%.1fmin" % (
                done, total_todo, rate, el / 60, (total_todo - done) * rate / 60))

print("RESUME_DONE frames=%d elapsed=%.1fmin" % (done, (time.time() - t_all) / 60))