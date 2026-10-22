# Adds a real Blender particle rain system to a COPY of the user's final scene.
# Saves warm_bedroom_rain.blend and renders a preview / final rainy still.
import bpy, os, math
from mathutils import Vector

USER = r"E:\dsh\bedroom_scene\user_edit_20261020_1421.blend"
OUT_BLEND = r"E:\dsh\bedroom_scene\warm_bedroom_rain.blend"
OUT_IMG = r"E:\dsh\bedroom_scene\renders_v2\hero_rain_2560.png"
PREVIEW = r"E:\dsh\.scratch\web3d\rain_preview.png"
bpy.ops.wm.open_mainfile(filepath=USER)
sc = bpy.context.scene

# Use the embedded time / weather controller (same one used by the project).
ctrl = bpy.data.texts.get("scene_controller.py")
if ctrl:
    ns = {"__name__": "rain_render"}
    exec(compile(ctrl.as_string(), "scene_controller.py", "exec"), ns)
    ns["set_time_of_day"]("dusk")
    ns["set_weather"]("rainy")
else:
    print("WARN: no scene_controller.py text; keeping file settings")

# Hide the old flat rain cards; we are replacing them with particles.
for o in bpy.data.objects:
    if o.name.startswith("Rain_"):
        o.hide_render = True

# Emitter: horizontal sheet above/outside the window, normal down.
bpy.ops.mesh.primitive_plane_add(size=1, location=(3.8, 0.0, 3.35))
em = bpy.context.object
em.name = "Rain_Particle_Emitter"
em.scale = (3.2, 5.8, 1.0)  # x 2.2..5.4, y -2.9..2.9
em.rotation_euler = (math.pi, 0, 0)  # face normal down
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

mat = bpy.data.materials.new("Rain_Emitter_Invisible")
mat.use_nodes = True
bsdf = mat.node_tree.nodes.get("Principled BSDF")
bsdf.inputs["Base Color"].default_value = (0.05, 0.06, 0.08, 1)
bsdf.inputs["Roughness"].default_value = .8
em.data.materials.append(mat)
em.show_instancer_for_render = False
em.show_instancer_for_viewport = False
em.hide_render = False

# Drop instance object: a tiny vertical glass/white streak.
bpy.ops.mesh.primitive_cube_add(size=1, location=(3.0, 0, 1.8))
drop = bpy.context.object
drop.name = "Rain_Particle_Drop"
drop.scale = (0.006, 0.006, 0.105)
bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
dmat = bpy.data.materials.new("Rain_Particle_Water")
dmat.use_nodes = True
dbsdf = dmat.node_tree.nodes.get("Principled BSDF")
dbsdf.inputs["Base Color"].default_value = (0.72, 0.83, 0.95, 1)
dbsdf.inputs["Roughness"].default_value = .08
dbsdf.inputs["Metallic"].default_value = 0
if "Transmission Weight" in dbsdf.inputs:
    dbsdf.inputs["Transmission Weight"].default_value = .55
if "Emission Color" in dbsdf.inputs:
    dbsdf.inputs["Emission Color"].default_value = (0.55, 0.68, 0.85, 1)
if "Emission Strength" in dbsdf.inputs:
    dbsdf.inputs["Emission Strength"].default_value = .35
drop.data.materials.append(dmat)
drop.hide_render = False

mod = em.modifiers.new("Rain_Particles", "PARTICLE_SYSTEM")
psys = mod.particle_system
ps = psys.settings
ps.name = "Rain_Particles"
ps.count = 2600
ps.frame_start = 1
ps.frame_end = 80
ps.lifetime = 55
ps.lifetime_random = .35
ps.emit_from = "FACE"
ps.distribution = "RAND"
ps.normal_factor = 2.2
ps.object_align_factor = (0, 0, -0.8)
ps.physics_type = "NEWTON"
ps.mass = .001
ps.use_rotations = True
ps.rotation_mode = "VEL"
ps.use_rotation_instance = True
ps.render_type = "OBJECT"
ps.instance_object = drop
ps.particle_size = 1.0
ps.size_random = .65
ps.display_method = "DOT"
ps.display_percentage = 15
psys.seed = 7

# Evaluate the particle cache to a steady downpour.
sc.frame_start = 1
sc.frame_end = 80
sc.frame_set(60)

# Camera: inside, looking toward the rain / desk window.
cd = bpy.data.cameras.new("Rain_Hero_Camera")
cd.lens = 38
co = bpy.data.objects.new("Rain_Hero_Camera", cd)
sc.collection.objects.link(co)
co.location = (0.55, -0.15, 1.55)
target = Vector((2.25, 1.30, 1.25))
co.rotation_euler = (target - Vector(co.location)).to_track_quat("-Z", "Y").to_euler()
sc.camera = co

sc.render.engine = "CYCLES"
sc.cycles.device = "GPU"
sc.cycles.samples = 96
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = "OPTIX"
except Exception:
    pass
sc.render.image_settings.file_format = "PNG"
sc.render.film_transparent = False
sc.render.use_motion_blur = True
sc.render.motion_blur_shutter = 0.28

# Preview first (fast), then the final still.
sc.render.resolution_x = 640
sc.render.resolution_y = 360
sc.render.resolution_percentage = 100
sc.render.filepath = PREVIEW
bpy.ops.render.render(write_still=True)

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)

sc.render.resolution_x = 2560
sc.render.resolution_y = 1440
sc.cycles.samples = 128
sc.render.filepath = OUT_IMG
bpy.ops.render.render(write_still=True)
print("RAIN_RENDER_DONE")
