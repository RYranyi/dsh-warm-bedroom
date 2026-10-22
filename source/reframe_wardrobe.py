# -*- coding: utf-8 -*-
"""Re-frame the wardrobe shot (seg_04) so it actually moves.

The old move kept a fixed look target on a flat wardrobe face, so the frame was
almost static (mean frame diff 0.3-0.5 vs 0.6-3.0 elsewhere).

Modes (arg after --):
  INFO     : print wardrobe / door bounding boxes, render nothing
  PREVIEW  : render the 3 candidate poses at 960x540
  FULL     : render all 144 frames of the new move into frames/seg_04
"""
import bpy, os, sys, json, time, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

BLEND = paths.blend()
OUT = paths.scratch("video", "frames", "seg_04")
CAND = paths.scratch("qa")
NF = 130
FPS = 24
RES = (1920, 1080)
SAMPLES = 10

mode = "INFO"
if "--" in sys.argv:
    rest = [a for a in sys.argv[sys.argv.index("--") + 1:] if a.strip()]
    if rest:
        mode = rest[0].upper()
print("MODE", mode)

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
ctrl = bpy.data.texts.get("scene_controller.py")
ns = {"__name__": "reframe_wardrobe", "bpy": bpy}
exec(compile(ctrl.as_string(), "scene_controller.py", "exec"), ns)

# candidate track: gentle push-in + slight rise, keeping the boxes on top in frame
A_POS = (1.62, -1.25, 1.48)
A_LOOK = (-1.58, -0.35, 1.44)
B_POS = (1.20, -0.95, 1.54)
B_LOOK = (-1.64, -0.22, 1.42)
C_POS = (0.80, -0.65, 1.62)
C_LOOK = (-1.70, -0.10, 1.50)

if mode == "INFO":
    rows = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        n = o.name.lower()
        if n.startswith("wardrobe") or n.startswith("door") or "closet" in n:
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            mn = [round(min(v[i] for v in bb), 3) for i in range(3)]
            mx = [round(max(v[i] for v in bb), 3) for i in range(3)]
            rows.append([o.name, mn, mx])
    rows.sort()
    print("HEADLESS " + json.dumps({"items": rows[:40]}, ensure_ascii=False))
    sys.exit(0)

W, H = (960, 540) if mode == "PREVIEW" else RES
sc.render.resolution_x = W
sc.render.resolution_y = H
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.fps = FPS
sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"
sc.cycles.samples = SAMPLES
sc.cycles.use_adaptive_sampling = True
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = "OPTIX"
except Exception:
    pass

ns["set_time_of_day"]("dusk")
ns["set_weather"]("sunny")

cam = bpy.data.objects.new("Ward_Cam", bpy.data.cameras.new("Ward_Cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 35.0


def set_cam(pos, look):
    p = Vector(pos)
    d = Vector(look) - p
    if d.length > 1e-6:
        cam.matrix_world = d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
        cam.matrix_world.translation = p


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def cam_at(t):
    e = t * t * (3 - 2 * t)
    # piecewise: A -> B -> C so the path follows the wall
    if e < 0.5:
        k = e / 0.5
        pos = lerp(A_POS, B_POS, k)
        look = lerp(A_LOOK, B_LOOK, k)
    else:
        k = (e - 0.5) / 0.5
        pos = lerp(B_POS, C_POS, k)
        look = lerp(B_LOOK, C_LOOK, k)
    return pos, look


t0 = time.time()
if mode == "PREVIEW":
    os.makedirs(CAND, exist_ok=True)
    out = []
    for tag, (pos, look) in (("A", (A_POS, A_LOOK)), ("B", (B_POS, B_LOOK)), ("C", (C_POS, C_LOOK))):
        set_cam(pos, look)
        p = os.path.join(CAND, "ward_%s.png" % tag)
        sc.render.filepath = p
        bpy.ops.render.render(scene=sc.name, write_still=True)
        out.append([tag, os.path.exists(p)])
    print("HEADLESS " + json.dumps({"preview": out, "sec": round(time.time() - t0, 1)}))
else:
    os.makedirs(OUT, exist_ok=True)
    for f in range(NF):
        pos, look = cam_at(f / (NF - 1))
        set_cam(pos, look)
        sc.render.filepath = os.path.join(OUT, "frame_%04d.png" % f)
        bpy.ops.render.render(scene=sc.name, write_still=True)
        if (f + 1) % 12 == 0:
            el = time.time() - t0
            print("PROGRESS %d/%d %.2fs/f eta=%.1fmin" % (
                f + 1, NF, el / (f + 1), (NF - f - 1) * (el / (f + 1)) / 60))
    print("WARDROBE_DONE frames=%d elapsed=%.1fmin" % (NF, (time.time() - t0) / 60))
