# -*- coding: utf-8 -*-
"""Prologue: 6 s 'production process' beat -> wireframe | clay | final render.

Renders 144 frames (24 fps) into frames/seg_pro/ , camera ends exactly at the
seg_01 start pose so the cut into the film is seamless.

Modes (pass after --):
  PREVIEW  : 3 stills (one per beat) at 960x540  -> E:\\dsh\\.scratch\\video\\cand
  FULL     : all 144 frames at 1920x1080
"""
import bpy, os, sys, json, time, math
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths

BLEND = paths.blend()
OUT = paths.scratch("video", "frames", "seg_pro")
CAND = paths.scratch("video", "cand")
NF = 144
FPS = 24
BEAT = NF // 3  # 48

mode = "PREVIEW"
if "--" in sys.argv:
    rest = [a for a in sys.argv[sys.argv.index("--") + 1:] if a.strip()]
    if rest:
        mode = rest[0].upper()
print("MODE", mode)

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene
ctrl = bpy.data.texts.get("scene_controller.py")
ns = {"__name__": "prologue", "bpy": bpy}
exec(compile(ctrl.as_string(), "scene_controller.py", "exec"), ns)
ns["set_time_of_day"]("dusk")
ns["set_weather"]("sunny")

W, H = (960, 540) if mode == "PREVIEW" else (1920, 1080)
sc.render.resolution_x = W
sc.render.resolution_y = H
sc.render.resolution_percentage = 100
sc.render.image_settings.file_format = "PNG"
sc.render.fps = FPS

cam = bpy.data.objects.new("Pro_Cam", bpy.data.cameras.new("Pro_Cam"))
sc.collection.objects.link(cam)
sc.camera = cam
cam.data.lens = 30.0


def set_cam(pos, look):
    p = Vector(pos)
    d = Vector(look) - p
    if d.length > 1e-6:
        cam.matrix_world = d.to_track_quat("-Z", "Y").to_matrix().to_4x4()
        cam.matrix_world.translation = p


# ---- camera path: sweep across the room, ends on the seg_01 start pose -----
END_POS = (-0.7, 2.28, 1.55)   # seg_01 start
END_LOOK = (0.0, -0.4, 1.2)    # seg_01 look target
P0 = (1.85, -0.55, 1.72)
L0 = (0.0, 0.15, 1.34)         # aim near eye level -> the frame shows the room


def cam_at(t):
    t = max(0.0, min(1.0, t))
    e = t * t * (3 - 2 * t)
    pos = tuple(P0[i] + (END_POS[i] - P0[i]) * e for i in range(3))
    look = tuple(L0[i] + (END_LOOK[i] - L0[i]) * e for i in range(3))
    return pos, look


# ---- clay / wire material --------------------------------------------------
def build_override(wire):
    mat = bpy.data.materials.new("ClayOverride_%s" % ("wire" if wire else "clay"))
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diff.inputs["Color"].default_value = (0.86, 0.85, 0.83, 1.0)
    if not wire:
        nt.links.new(diff.outputs[0], out.inputs["Surface"])
        return mat
    wf = nt.nodes.new("ShaderNodeWireframe")
    wf.use_pixel_size = True
    wf.inputs["Size"].default_value = 1.1
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = (0.06, 0.06, 0.07, 1.0)
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(wf.outputs[0], mix.inputs[0])
    nt.links.new(diff.outputs[0], mix.inputs[1])
    nt.links.new(emi.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


MAT_WIRE = build_override(True)
MAT_CLAY = build_override(False)


def beat_of(f):
    return 0 if f < BEAT else (1 if f < 2 * BEAT else 2)


# ---- studio setup for the clay / wireframe beats ---------------------------
LIGHTS = [o for o in bpy.data.objects if o.type == "LIGHT"]
WORLD_BAK = sc.world
VIEW_BAK = sc.view_settings.view_transform
LOOK_BAK = sc.view_settings.look

studio = bpy.data.worlds.new("StudioWorld")
studio.use_nodes = True
bg = studio.node_tree.nodes.get("Background")
if bg is not None:
    bg.inputs[0].default_value = (0.62, 0.65, 0.70, 1.0)
    bg.inputs[1].default_value = 0.55


def _area(name, loc, look_at, energy, size):
    d = bpy.data.lights.new(name, type="AREA")
    d.energy = energy
    d.size = size
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    v = Vector(look_at) - Vector(loc)
    o.rotation_euler = v.to_track_quat("-Z", "Y").to_euler()
    o.hide_render = True
    return o


# interior key + fill so the flat ambient world still shows form
_STUDIO_LIGHTS = [
    _area("StudioKey", (1.15, 0.95, 2.25), (0.10, 0.05, 0.70), 110.0, 2.2),
    _area("StudioFill", (-1.35, -1.15, 2.10), (0.05, 0.00, 0.85), 35.0, 3.0),
]


def studio_on():
    for o in LIGHTS:
        o.hide_render = True
    for o in _STUDIO_LIGHTS:
        o.hide_render = False
    sc.world = studio
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.look = "None"
    sc.view_settings.exposure = 0.0


def studio_off():
    for o in LIGHTS:
        o.hide_render = False
    for o in _STUDIO_LIGHTS:
        o.hide_render = True
    sc.world = WORLD_BAK
    sc.view_settings.view_transform = VIEW_BAK
    sc.view_settings.look = LOOK_BAK


def apply_engine(beat):
    if beat == 0:
        # wireframe pass: flat grey surfaces + dark mesh lines (EEVEE)
        studio_on()
        sc.render.engine = "BLENDER_EEVEE"
        sc.eevee.taa_render_samples = 24
        bpy.context.view_layer.material_override = MAT_WIRE
    elif beat == 1:
        # clay pass: workbench studio shading -> real form, no scene lights
        studio_off()
        bpy.context.view_layer.material_override = None
        sc.render.engine = "BLENDER_WORKBENCH"
        d = sc.display
        d.render_aa = "16"
        sh = d.shading
        sh.light = "STUDIO"
        sh.color_type = "SINGLE"
        sh.single_color = (0.86, 0.84, 0.80)
        sh.show_shadows = True
        sh.shadow_intensity = 0.42
        sh.show_cavity = True
        sh.cavity_type = "BOTH"
        sh.cavity_ridge_factor = 0.9
        sh.cavity_valley_factor = 1.1
        sh.show_specular_highlight = True
        sh.background_type = "VIEWPORT"
        sh.background_color = (0.60, 0.63, 0.68)
        sc.view_settings.view_transform = "Standard"
        sc.view_settings.look = "None"
    else:
        studio_off()
        bpy.context.view_layer.material_override = None
        sc.render.engine = "CYCLES"
        sc.cycles.device = "GPU"
        sc.cycles.samples = 10
        sc.cycles.use_adaptive_sampling = True
        sc.cycles.use_denoising = True
        try:
            sc.cycles.denoiser = "OPTIX"
        except Exception:
            pass


def render_frame(f, path):
    t = f / (NF - 1)
    pos, look = cam_at(t)
    set_cam(pos, look)
    sc.frame_set(1)
    sc.render.filepath = path
    bpy.ops.render.render(scene=sc.name, write_still=True)


t0 = time.time()
if mode == "PREVIEW":
    os.makedirs(CAND, exist_ok=True)
    info = []
    for f in (BEAT // 2, BEAT + BEAT // 2, 2 * BEAT + BEAT // 2):
        apply_engine(beat_of(f))
        p = os.path.join(CAND, "pro_%03d.png" % f)
        render_frame(f, p)
        info.append([f, beat_of(f), os.path.exists(p)])
    print("HEADLESS " + json.dumps({"preview": info, "sec": round(time.time() - t0, 1)}))
else:
    # FULL  = all 144 frames,  WIRE / CLAY / FINAL = one beat only (re-render helper)
    BEATS = {"FULL": (0, 1, 2), "WIRE": (0,), "CLAY": (1,), "FINAL": (2,)}
    want = BEATS.get(mode, (0, 1, 2))
    todo = [f for f in range(NF) if beat_of(f) in want]
    os.makedirs(OUT, exist_ok=True)
    cur = -1
    for f in todo:
        b = beat_of(f)
        if b != cur:
            apply_engine(b)
            print("BEAT %d from frame %d" % (b, f))
            cur = b
        p = os.path.join(OUT, "frame_%04d.png" % f)
        render_frame(f, p)
        if (len(todo) and (todo.index(f) + 1) % 12 == 0):
            el = time.time() - t0
            i = todo.index(f) + 1
            print("PROGRESS %d/%d %.2fs/f eta=%.1fmin" % (
                i, len(todo), el / i, (len(todo) - i) * (el / i) / 60))
    print("PROLOGUE_DONE mode=%s frames=%d elapsed=%.1fmin" % (
        mode, len(todo), (time.time() - t0) / 60))

