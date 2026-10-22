# -*- coding: utf-8 -*-
"""
Warm Bedroom - scene_controller.py
==================================
Blender 5.x scene controller for the "Warm Bedroom" project.

Usage (Blender Text Editor -> Run Script, or from the Python Console):
    import bpy
    exec(compile(bpy.data.texts["scene_controller.py"].as_string(),
                 "scene_controller.py", "exec"))

    set_time_of_day("dusk")
    set_weather("sunny")

    # combine freely:
    set_time_of_day("night"); set_weather("rainy")

    # replace the artwork with a local image:
    set_frame_artwork(r"D:/pictures/my_painting.jpg")

The two main setters are deliberately orthogonal.  Each setter only writes its
own half of the state (time or weather) and then rebuilds the look from both
halves, so any of the 5 x 4 combinations is valid.
"""

import bpy
import math
import os
from mathutils import Vector, Matrix, Euler

# ---------------------------------------------------------------------------
# Preset data
# ---------------------------------------------------------------------------
# Colours are sRGB hex.  They are converted to scene-linear inside the script.
# sun_azimuth is measured from +X toward +Y.  The window faces +X, so ~45 deg
# is the direction seen through the window and produces light falling into the
# room from the upper right.

TIME_PRESETS = {
    "dawn": {
        "sun_elevation": 8.0,
        "sun_azimuth": -32.0,
        "sun_energy": 3.0,
        "sun_kelvin": 3000,
        "sun_angle_deg": 1.2,
        "exposure": 0.65,
        "world_strength": 0.18,
        "world_top": "#26344F",
        "world_horizon": "#7B625B",
        "sky_top": "#172A50",
        "sky_high": "#52678F",
        "sky_low": "#D79A83",
        "sky_horizon": "#F3B071",
        "cloud_light": "#FFD5B8",
        "cloud_dark": "#73566A",
        "sky_emission": 0.78,
        "lamp_bedside": 22.0,
        "lamp_floor": 12.0,
        "fill": 5.0,
        "fill_kelvin": 3400,
        "window_fill": 16.0,
        "window_fill_kelvin": 4200,
        "art_light": 3.0,
        "shade_glow": 1.2,
        "bulb": 3.5,
        "lamp_desk": 4.0,
        "tv_emission": 0.35,
        "tv_glow": 0.05,
        "moon": False,
        "sun_disc": True,
        "sheer": False,
        "city_lights": False,
    },
    "morning": {
        "sun_elevation": 20.0,
        "sun_azimuth": -24.0,
        "sun_energy": 8.5,
        "sun_kelvin": 4800,
        "sun_angle_deg": 1.0,
        "exposure": 0.10,
        "world_strength": 0.82,
        "world_top": "#8CBAE4",
        "world_horizon": "#F5E7D3",
        "sky_top": "#2C68B0",
        "sky_high": "#5D95CE",
        "sky_low": "#B5D5ED",
        "sky_horizon": "#E7F2FB",
        "cloud_light": "#FFFFFF",
        "cloud_dark": "#AABACB",
        "sky_emission": 1.28,
        "lamp_bedside": 0.0,
        "lamp_floor": 0.0,
        "fill": 10.0,
        "fill_kelvin": 5000,
        "window_fill": 72.0,
        "window_fill_kelvin": 6200,
        "art_light": 0.0,
        "shade_glow": 0.0,
        "bulb": 0.0,
        "lamp_desk": 0.0,
        "tv_emission": 0.06,
        "tv_glow": 0.0,
        "moon": False,
        "sun_disc": False,
        "sheer": False,
        "city_lights": False,
    },
    "noon": {
        "sun_elevation": 62.0,
        "sun_azimuth": -12.0,
        "sun_energy": 8.0,
        "sun_kelvin": 5600,
        "sun_angle_deg": 0.9,
        "exposure": -0.15,
        "world_strength": 0.92,
        "world_top": "#A8D3F0",
        "world_horizon": "#FFF1D9",
        "sky_top": "#2363AE",
        "sky_high": "#4A88C8",
        "sky_low": "#9DCBEA",
        "sky_horizon": "#DCEEFB",
        "cloud_light": "#FFFFFF",
        "cloud_dark": "#B2C1CE",
        "sky_emission": 1.45,
        "lamp_bedside": 0.0,
        "lamp_floor": 0.0,
        "fill": 18.0,
        "fill_kelvin": 5400,
        "window_fill": 155.0,
        "window_fill_kelvin": 6600,
        "art_light": 0.0,
        "shade_glow": 0.0,
        "bulb": 0.0,
        "lamp_desk": 0.0,
        "tv_emission": 0.02,
        "tv_glow": 0.0,
        "moon": False,
        "sun_disc": False,
        "sheer": True,
        "city_lights": False,
    },
    "dusk": {
        "sun_elevation": 11.0,
        "sun_azimuth": -22.0,
        "sun_energy": 10.5,
        "sun_kelvin": 3300,
        "sun_angle_deg": 1.0,
        "exposure": 0.0,
        "world_strength": 0.16,
        "world_top": "#1C274D",
        "world_horizon": "#9C664F",
        "sky_top": "#0B1735",
        "sky_high": "#3E5A88",
        "sky_low": "#DE825F",
        "sky_horizon": "#FF9A4B",
        "cloud_light": "#FFC08B",
        "cloud_dark": "#65465D",
        "sky_emission": 0.98,
        "lamp_bedside": 22.0,
        "lamp_floor": 12.0,
        "fill": 5.0,
        "fill_kelvin": 3900,
        "window_fill": 23.0,
        "window_fill_kelvin": 4300,
        "art_light": 4.0,
        "shade_glow": 0.7,
        "bulb": 3.0,
        "lamp_desk": 6.0,
        "tv_emission": 4.5,
        "tv_glow": 6.0,
        "moon": False,
        "sun_disc": True,
        "sheer": False,
        "city_lights": False,
    },
    "night": {
        "sun_elevation": 36.0,
        "sun_azimuth": 16.0,
        "sun_energy": 0.08,
        "sun_kelvin": 5400,
        "sun_angle_deg": 2.0,
        "exposure": 0.95,
        "world_strength": 0.025,
        "world_top": "#070C18",
        "world_horizon": "#182133",
        "sky_top": "#03050B",
        "sky_high": "#081020",
        "sky_low": "#111C2E",
        "sky_horizon": "#253142",
        "cloud_light": "#263346",
        "cloud_dark": "#070B13",
        "sky_emission": 0.24,
        "lamp_bedside": 30.0,
        "lamp_floor": 22.0,
        "fill": 2.5,
        "fill_kelvin": 2800,
        "window_fill": 0.4,
        "window_fill_kelvin": 4600,
        "art_light": 2.6,
        "shade_glow": 1.8,
        "bulb": 5.5,
        "lamp_desk": 8.0,
        "tv_emission": 6.0,
        "tv_glow": 9.0,
        "moon": True,
        "sun_disc": False,
        "sheer": False,
        "city_lights": True,
    },
}

WEATHER_PRESETS = {
    "sunny": {
        "label": "晴天 / clear",
        "sky_material": "Sky_Sunny",
        "sun_factor": 1.0,
        "sun_softness": 1.0,
        "sun_kelvin_override": None,
        "exposure_add": 0.0,
        "world_mult": 1.0,
        "sky_emission_mult": 1.0,
        "lamp_mult": 1.0,
        "fill_mult": 1.0,
        "window_fill_mult": 1.0,
        "window_fill_kelvin_override": None,
        "sky_tint": None,
        "sky_tint_mix": 0.0,
        "cloud_tint": None,
        "cloud_tint_mix": 0.0,
        "rain_count": 0,
        "rain_glass": False,
        "rain_material": None,
        "haze": 0.055,
        "show_sun_disc": True,
        "show_moon": True,
        "sheer": False,
        "lightning": False,
    },
    "cloudy": {
        "label": "多云 / cloudy",
        "sky_material": "Sky_Cloudy",
        "sun_factor": 0.24,
        "sun_softness": 4.5,
        "sun_kelvin_override": 5200,
        "exposure_add": 0.18,
        "world_mult": 0.70,
        "sky_emission_mult": 0.82,
        "lamp_mult": 1.08,
        "fill_mult": 1.25,
        "window_fill_mult": 0.65,
        "window_fill_kelvin_override": 5800,
        "sky_tint": "#B7BCC1",
        "sky_tint_mix": 0.55,
        "cloud_tint": "#D2D3D1",
        "cloud_tint_mix": 0.65,
        "rain_count": 0,
        "rain_glass": False,
        "rain_material": None,
        "haze": 0.12,
        "show_sun_disc": False,
        "show_moon": True,
        "sheer": False,
        "lightning": False,
    },
    "rainy": {
        "label": "雨天 / rainy",
        "sky_material": "Sky_Rainy",
        "sun_factor": 0.075,
        "sun_softness": 7.0,
        "sun_kelvin_override": 6500,
        "exposure_add": 0.36,
        "world_mult": 0.42,
        "sky_emission_mult": 0.58,
        "lamp_mult": 1.18,
        "fill_mult": 1.38,
        "window_fill_mult": 0.40,
        "window_fill_kelvin_override": 6500,
        "sky_tint": "#697C82",
        "sky_tint_mix": 0.74,
        "cloud_tint": "#7A898E",
        "cloud_tint_mix": 0.86,
        "rain_count": 2,
        "rain_glass": True,
        "rain_material": "Rain_Curtain_Moderate",
        "haze": 0.24,
        "show_sun_disc": False,
        "show_moon": False,
        "sheer": False,
        "lightning": False,
    },
    "storm": {
        "label": "暴雨 / storm",
        "sky_material": "Sky_Storm",
        "sun_factor": 0.018,
        "sun_softness": 9.0,
        "sun_kelvin_override": 7200,
        "exposure_add": 0.55,
        "world_mult": 0.20,
        "sky_emission_mult": 0.24,
        "lamp_mult": 1.28,
        "fill_mult": 1.52,
        "window_fill_mult": 0.15,
        "window_fill_kelvin_override": 7200,
        "sky_tint": "#141A20",
        "sky_tint_mix": 0.88,
        "cloud_tint": "#242C32",
        "cloud_tint_mix": 0.92,
        "rain_count": 3,
        "rain_glass": True,
        "rain_material": "Rain_Curtain_Storm",
        "haze": 0.34,
        "show_sun_disc": False,
        "show_moon": False,
        "sheer": False,
        "lightning": True,
    },
}

_STATE = {"time": "dusk", "weather": "sunny"}


# ---------------------------------------------------------------------------
# Small colour / material utilities
# ---------------------------------------------------------------------------
def _srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _hex(h):
    h = h.lstrip("#")
    return tuple(_srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def _mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def _kelvin_rgb(kelvin, linear=True):
    """Tanner Helland's black-body approximation, returned scene-linear."""
    t = max(1000.0, min(40000.0, float(kelvin))) / 100.0
    if t <= 66.0:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19.0 else 138.5177312231 * math.log(t - 10.0) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60.0) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60.0) ** -0.0755148492)
        b = 255.0
    rgb = tuple(max(0.0, min(255.0, v)) / 255.0 for v in (r, g, b))
    if linear:
        rgb = tuple(_srgb_to_linear(v) for v in rgb)
    # normalise so a light's colour does not change its wattage dramatically
    mx = max(rgb) or 1.0
    return tuple(v / mx for v in rgb)


def _node(mat, name, node_type=None):
    if mat is None or mat.node_tree is None:
        return None
    n = mat.node_tree.nodes.get(name)
    if n is None and node_type is not None:
        n = mat.node_tree.nodes.new(node_type)
        n.name = name
    return n


def _set_input(node, name, value):
    if node is None:
        return False
    sock = node.inputs.get(name)
    if sock is None:
        return False
    try:
        sock.default_value = value
        return True
    except Exception:
        return False


def _show(obj, visible):
    if obj is None:
        return
    obj.hide_render = not visible
    obj.hide_viewport = not visible
    try:
        obj.hide_set(not visible)
    except Exception:
        pass


def _set_obj_visible(obj_name, visible):
    _show(bpy.data.objects.get(obj_name), visible)


def _set_sky_color_ramp(ramp_node, top, high, low, horizon):
    if ramp_node is None or ramp_node.type != "VALTORGB":
        return
    els = ramp_node.color_ramp.elements
    # 4 stops built by the modelling script.  Guard for unexpected trees.
    colors = (horizon, low, high, top)
    for i, col in enumerate(colors[: len(els)]):
        els[i].color = (*col, 1.0)


def _set_rgb_node(mat, node_name, color):
    n = _node(mat, node_name)
    if n is not None and getattr(n, "outputs", None) and len(n.outputs):
        try:
            n.outputs[0].default_value = (*color, 1.0)
        except Exception:
            pass


def _sun_direction(elevation_deg, azimuth_deg):
    """Unit vector pointing from the room toward the sun."""
    el = math.radians(float(elevation_deg))
    az = math.radians(float(azimuth_deg))
    return Vector((math.cos(el) * math.cos(az),
                   math.cos(el) * math.sin(az),
                   math.sin(el)))


def _aim_light_at(obj, target):
    direction = Vector(target) - obj.location
    if direction.length > 1e-6:
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


# ---------------------------------------------------------------------------
# Unified application of the current (time, weather) pair
# ---------------------------------------------------------------------------
def _resolve_palette(time_data, weather_data):
    """Merge time-of-day palette with weather tint; returns linear colours."""
    top = _hex(time_data["sky_top"])
    high = _hex(time_data["sky_high"])
    low = _hex(time_data["sky_low"])
    horizon = _hex(time_data["sky_horizon"])
    cloud_light = _hex(time_data["cloud_light"])
    cloud_dark = _hex(time_data["cloud_dark"])

    tint_mix = weather_data.get("sky_tint_mix", 0.0)
    if weather_data.get("sky_tint"):
        tint = _hex(weather_data["sky_tint"])
        top = _mix(top, tint, tint_mix)
        high = _mix(high, tint, tint_mix)
        low = _mix(low, tint, tint_mix * 0.82)
        horizon = _mix(horizon, tint, tint_mix * 0.70)

    cmix = weather_data.get("cloud_tint_mix", 0.0)
    if weather_data.get("cloud_tint"):
        ctint = _hex(weather_data["cloud_tint"])
        cloud_light = _mix(cloud_light, ctint, cmix)
        cloud_dark = _mix(cloud_dark, ctint, cmix * 0.85)

    # At night clouds are barely visible; keep them from glowing grey.
    if _STATE["time"] == "night":
        night_cloud = _hex("#1A2433")
        cloud_light = _mix(cloud_light, night_cloud, 0.55)
        cloud_dark = _mix(cloud_dark, _hex("#05070C"), 0.55)

    return {
        "top": top, "high": high, "low": low, "horizon": horizon,
        "cloud_light": cloud_light, "cloud_dark": cloud_dark,
    }


def _apply():
    scene = bpy.context.scene
    time_name = _STATE["time"]
    weather_name = _STATE["weather"]
    t = TIME_PRESETS[time_name]
    w = WEATHER_PRESETS[weather_name]

    # --- sun / moon key light ------------------------------------------------
    sun = bpy.data.objects.get("Sun")
    sun_dir = _sun_direction(t["sun_elevation"], t["sun_azimuth"])
    if sun is not None:
        sun.rotation_euler = (-sun_dir).to_track_quat("-Z", "Y").to_euler()
        kelvin = w.get("sun_kelvin_override") or t["sun_kelvin"]
        sun.data.energy = float(t["sun_energy"]) * float(w["sun_factor"])
        sun.data.color = _kelvin_rgb(kelvin)
        sun.data.angle = math.radians(max(0.15, float(t["sun_angle_deg"]) * float(w["sun_softness"])))

    # Optional visible solar disc.  A little visual cheat: it sits slightly
    # above the light's true elevation, but reads better through the window.
    disc = bpy.data.objects.get("Sun_Disc")
    if disc is not None:
        ddir = _sun_direction(max(7.5, t["sun_elevation"]), t["sun_azimuth"])
        disc.location = Vector((0.0, 0.0, 1.2)) + ddir * 56.0
        disc.rotation_euler = (-ddir).to_track_quat("-Z", "Y").to_euler()
        disc_visible = bool(t.get("sun_disc")) and bool(w.get("show_sun_disc"))
        _show(disc, disc_visible)
        dmat = disc.data.materials[0] if disc.data.materials else None
        if dmat is not None:
            em = _node(dmat, "Sun_Disc_Emission")
            if em is not None:
                em.inputs["Color"].default_value = (*_kelvin_rgb(max(2200, t["sun_kelvin"] - 300)), 1.0)
                em.inputs["Strength"].default_value = 6.5 if time_name != "dawn" else 4.0

    # --- moon ----------------------------------------------------------------
    moon = bpy.data.objects.get("Moon")
    if moon is not None:
        visible = bool(t.get("moon")) and bool(w.get("show_moon"))
        _show(moon, visible)
        moon_mat = moon.data.materials[0] if moon.data.materials else None
        if moon_mat is not None:
            em = _node(moon_mat, "Moon_Emission")
            if em is not None:
                em.inputs["Strength"].default_value = 7.0 if visible else 0.0

    # --- sky dome material ---------------------------------------------------
    dome = bpy.data.objects.get("Sky_Dome")
    sky_mat = bpy.data.materials.get(w["sky_material"])
    palette = _resolve_palette(t, w)
    if dome is not None and sky_mat is not None:
        dome.data.materials.clear()
        dome.data.materials.append(sky_mat)
        _set_sky_color_ramp(_node(sky_mat, "Sky_Gradient"),
                            palette["top"], palette["high"],
                            palette["low"], palette["horizon"])
        _set_rgb_node(sky_mat, "Cloud_Color_Light", palette["cloud_light"])
        _set_rgb_node(sky_mat, "Cloud_Color_Dark", palette["cloud_dark"])
        em = _node(sky_mat, "Sky_Emission")
        if em is not None:
            em.inputs["Strength"].default_value = (
                float(t["sky_emission"]) * float(w["sky_emission_mult"])
            )

    # Keep every sky variant up to date, so switching weather later is seamless.
    for other_name in ("Sky_Sunny", "Sky_Cloudy", "Sky_Rainy", "Sky_Storm"):
        other = bpy.data.materials.get(other_name)
        if other is None:
            continue
        _set_sky_color_ramp(_node(other, "Sky_Gradient"),
                            palette["top"], palette["high"],
                            palette["low"], palette["horizon"])
        _set_rgb_node(other, "Cloud_Color_Light", palette["cloud_light"])
        _set_rgb_node(other, "Cloud_Color_Dark", palette["cloud_dark"])
        oe = _node(other, "Sky_Emission")
        if oe is not None:
            oe.inputs["Strength"].default_value = float(t["sky_emission"]) * float(w["sky_emission_mult"])

    # --- world ---------------------------------------------------------------
    world = bpy.data.worlds.get("Sky") or scene.world
    if world is not None and world.node_tree is not None:
        wtop = _hex(t["world_top"])
        whor = _hex(t["world_horizon"])
        if w.get("sky_tint"):
            wt = _hex(w["sky_tint"])
            wtop = _mix(wtop, wt, w.get("sky_tint_mix", 0.0) * 0.55)
            whor = _mix(whor, wt, w.get("sky_tint_mix", 0.0) * 0.35)
        ramp = world.node_tree.nodes.get("World_Gradient")
        if ramp is not None:
            els = ramp.color_ramp.elements
            if len(els) >= 2:
                els[0].color = (*whor, 1.0)
                els[1].color = (*wtop, 1.0)
        bg = world.node_tree.nodes.get("World_Background")
        if bg is not None:
            bg.inputs["Strength"].default_value = float(t["world_strength"]) * float(w["world_mult"])

    # --- practical lights ----------------------------------------------------
    warm = _kelvin_rgb(2750)
    bedside = bpy.data.objects.get("Lamp_Bedside")
    if bedside is not None:
        bedside.data.energy = float(t["lamp_bedside"]) * float(w["lamp_mult"])
        bedside.data.color = warm
    floor_lamp = bpy.data.objects.get("Lamp_Floor")
    if floor_lamp is not None:
        floor_lamp.data.energy = float(t["lamp_floor"]) * float(w["lamp_mult"])
        floor_lamp.data.color = _kelvin_rgb(2600)
    desk_lamp = bpy.data.objects.get("Lamp_Desk")
    if desk_lamp is not None:
        desk_lamp.data.energy = float(t.get("lamp_desk", 0.0)) * float(w["lamp_mult"])
        desk_lamp.data.color = _kelvin_rgb(3000)

    fill = bpy.data.objects.get("Fill_Soft")
    if fill is not None:
        fill.data.energy = float(t["fill"]) * float(w["fill_mult"])
        fill.data.color = _kelvin_rgb(t["fill_kelvin"])

    window_fill = bpy.data.objects.get("Fill_Window")
    if window_fill is not None:
        window_fill.data.energy = float(t["window_fill"]) * float(w["window_fill_mult"])
        wf_kelvin = w.get("window_fill_kelvin_override") or t["window_fill_kelvin"]
        window_fill.data.color = _kelvin_rgb(wf_kelvin)

    art_light = bpy.data.objects.get("Art_Light")
    if art_light is not None:
        art_light.data.energy = float(t.get("art_light", 0.0)) * float(w["lamp_mult"])
        art_light.data.color = _kelvin_rgb(2850)

    # television screen: its own named material and a soft screen glow
    tv_screen = bpy.data.materials.get("TV_Screen")
    if tv_screen is not None and tv_screen.node_tree is not None:
        em = _node(tv_screen, "TV_Emission")
        if em is not None:
            em.inputs["Strength"].default_value = float(t.get("tv_emission", 0.0))
    tv_glow = bpy.data.objects.get("TV_Glow")
    if tv_glow is not None:
        tv_glow.data.energy = float(t.get("tv_glow", 0.0)) * float(w["lamp_mult"])
        tv_glow.data.color = _kelvin_rgb(2500)

    # lamp shade / bulb glow
    for mat_name in ("Lamp_Shade_Bedside", "Lamp_Shade_Floor", "Lamp_Shade_Desk"):
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            continue
        bsdf = _node(mat, "Shade_Principled")
        if bsdf is not None:
            _set_input(bsdf, "Emission Strength", float(t["shade_glow"]))
            _set_input(bsdf, "Emission Color", (*warm, 1.0))
    for mat_name, node_name in (("Bulb_Bedside_Mat", "Bulb_Emission"),
                                ("Bulb_Floor_Mat", "Bulb_Emission"),
                                ("Bulb_Desk_Mat", "Desk_Bulb_Emission"),
                                ("TV_UI_Mat", "TV_UI_Emission")):
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            continue
        em = _node(mat, node_name)
        if em is not None:
            if mat_name == "TV_UI_Mat":
                em.inputs["Strength"].default_value = 0.9 if float(t.get("tv_emission", 0.0)) > 1.0 else 0.25
            else:
                em.inputs["Strength"].default_value = float(t["bulb"])

    # --- weather geometry ----------------------------------------------------
    _set_obj_visible("Rain_Glass_Overlay", bool(w["rain_glass"]))
    if w["rain_glass"]:
        overlay = bpy.data.objects.get("Rain_Glass_Overlay")
        rmat = bpy.data.materials.get(
            "Window_Rain_Storm" if weather_name == "storm" else "Window_Rain_Moderate"
        )
        if overlay is not None and rmat is not None:
            overlay.data.materials.clear()
            overlay.data.materials.append(rmat)

    for i in range(1, 4):
        rain = bpy.data.objects.get("Rain_Curtain_%d" % i)
        vis = i <= int(w["rain_count"])
        _show(rain, vis)
        if vis:
            rmat = bpy.data.materials.get(w["rain_material"])
            if rain is not None and rmat is not None:
                rain.data.materials.clear()
                rain.data.materials.append(rmat)

    haze = bpy.data.objects.get("Rain_Haze")
    haze_visible = float(w["haze"]) > 0.001
    _show(haze, haze_visible)
    if haze_visible and haze is not None:
        hmat = haze.data.materials[0] if haze.data.materials else None
        if hmat is not None:
            op = _node(hmat, "Haze_Opacity")
            if op is not None:
                _set_input(op, "Value", float(w["haze"]))
            em = _node(hmat, "Haze_Emission")
            if em is not None:
                # The haze catches a little of the sky's light.
                em.inputs["Color"].default_value = (*palette["low"], 1.0)
                em.inputs["Strength"].default_value = 0.28 if weather_name != "storm" else 0.12

    # --- sheer curtain -------------------------------------------------------
    sheer_visible = bool(t.get("sheer")) or bool(w.get("sheer"))
    _set_obj_visible("Curtain_Sheer", sheer_visible)

    # --- city lights and stars ----------------------------------------------
    city_on = bool(t.get("city_lights"))
    _set_obj_visible("City_Lights", city_on)
    _set_obj_visible("Stars", bool(t.get("moon")))
    city_mat = bpy.data.materials.get("City_Lights_Mat")
    if city_mat is not None:
        em = _node(city_mat, "City_Emission")
        if em is not None:
            em.inputs["Strength"].default_value = 2.6 if city_on else 0.0

    # --- lightning (independent switch, only active during a storm) ----------
    bolt = bpy.data.objects.get("Lightning")
    if bolt is not None:
        if weather_name == "storm":
            bolt.hide_render = False
            bolt.hide_viewport = True  # keep the viewport clean
            bolt.data.energy = float(scene.get("lightning_energy", 0.0))
        else:
            bolt.hide_render = True
            bolt.hide_viewport = True
            bolt.data.energy = 0.0

    # --- exposure / colour management ---------------------------------------
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    scene.view_settings.exposure = float(t["exposure"]) + float(w["exposure_add"])

    scene["time_of_day"] = time_name
    scene["weather"] = weather_name
    scene["lighting_label"] = "%s / %s" % (time_name, weather_name)
    print("[WarmBedroom] time=%s  weather=%s  sun=%.2fW/m2  exposure=%+.2f"
          % (time_name, weather_name, sun.data.energy if sun else -1,
             scene.view_settings.exposure))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def set_time_of_day(mode):
    """Select the time of day: dawn | morning | noon | dusk | night."""
    if mode not in TIME_PRESETS:
        raise ValueError("Unknown time_of_day %r. Use one of: %s"
                         % (mode, ", ".join(sorted(TIME_PRESETS))))
    _STATE["time"] = mode
    _apply()


def set_weather(mode):
    """Select the weather: sunny | cloudy | rainy | storm."""
    if mode not in WEATHER_PRESETS:
        raise ValueError("Unknown weather %r. Use one of: %s"
                         % (mode, ", ".join(sorted(WEATHER_PRESETS))))
    _STATE["weather"] = mode
    _apply()


def set_frame_artwork(image_path):
    """Load a local image and use it as the framed artwork.

    The frame object is UV-unwrapped and its artwork material is the independent
    material slot named "Frame_Artwork".  The image is packed into the .blend so
    the saved scene stays portable.
    """
    path = os.path.abspath(os.path.expanduser(image_path))
    if not os.path.exists(path):
        raise FileNotFoundError("Artwork not found: %s" % path)
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "sRGB"
    try:
        img.pack()
    except Exception:
        pass
    mat = bpy.data.materials.get("Frame_Artwork")
    if mat is None or mat.node_tree is None:
        raise RuntimeError('Material "Frame_Artwork" is missing.')
    node = mat.node_tree.nodes.get("Artwork_Image")
    if node is None:
        raise RuntimeError('Image Texture node "Artwork_Image" is missing.')
    node.image = img
    node.image.colorspace_settings.name = "sRGB"
    # Make sure the material is actually assigned to the art plane.
    plane = bpy.data.objects.get("Frame_Artwork")
    if plane is not None and mat.name not in [m.name for m in plane.data.materials if m]:
        plane.data.materials.append(mat)
    print("[WarmBedroom] artwork -> %s (%dx%d)" % (path, img.size[0], img.size[1]))
    return img


def set_lightning(enabled=True, energy=6500.0):
    """Independent storm-lightning switch.

    Lightning is only allowed to render in the storm weather mode.
    `energy` is the Area light power in watts (roughly 2500-12000 is plausible
    for a stylised single-frame flash).
    """
    scene = bpy.context.scene
    scene["lightning_energy"] = float(energy) if enabled else 0.0
    bolt = bpy.data.objects.get("Lightning")
    if bolt is not None and _STATE["weather"] == "storm":
        bolt.hide_render = not enabled
        bolt.hide_viewport = True
        bolt.data.energy = float(energy) if enabled else 0.0
    print("[WarmBedroom] lightning=%s  energy=%.0fW" % (enabled, energy))


def flash_lightning(energy=6500.0):
    """Alias for a single dramatic flash (useful in stills)."""
    set_lightning(True, energy)


def get_lighting_state():
    """Return a small dict describing the active combination."""
    t = TIME_PRESETS[_STATE["time"]]
    w = WEATHER_PRESETS[_STATE["weather"]]
    return {
        "time": _STATE["time"],
        "weather": _STATE["weather"],
        "label": "%s / %s" % (_STATE["time"], _STATE["weather"]),
        "sun_energy": t["sun_energy"] * w["sun_factor"],
        "lamp_bedside_w": t["lamp_bedside"] * w["lamp_mult"],
        "lamp_floor_w": t["lamp_floor"] * w["lamp_mult"],
        "lamp_desk_w": t.get("lamp_desk", 0.0) * w["lamp_mult"],
        "tv_emission": t.get("tv_emission", 0.0),
        "tv_glow_w": t.get("tv_glow", 0.0) * w["lamp_mult"],
        "exposure": t["exposure"] + w["exposure_add"],
    }


# ---------------------------------------------------------------------------
# Chibi maid integration (pure meshes, no armature in the supplied file)
# ---------------------------------------------------------------------------
MAID_SOURCE_CANDIDATES = [
    # 1) 与当前 .blend 同级的 assets/（最通用）
    os.path.join(os.path.dirname(bpy.data.filepath), "assets", "chibi_maid_USER.blend")
    if bpy.data.filepath else "",
    # 2) 与 scene_controller.py 同级的 assets/
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "chibi_maid_USER.blend")
    if "__file__" in globals() else "",
    # 3) 环境变量覆盖，便于把模型放在项目外
    os.environ.get("WARM_BEDROOM_MAID_BLEND", ""),
]
MAID_SOURCE = next((p for p in MAID_SOURCE_CANDIDATES if p and os.path.exists(p)),
                   MAID_SOURCE_CANDIDATES[0])
MAID_COLLECTION = "Maid"
MAID_SCALE = 0.48          # uniform XYZ scale, root empty only (~49 cm tall)
MAID_YAW_DEG = 25.0        # turned slightly toward the main camera
MAID_LOCATION = (0.46, 1.99)
MAID_BED_TOP = 0.755       # duvet/sheet surface where she sits (no cushion)
MAID_LEG_ANGLE = -65.0     # hip swing; tuned so soles and skirt hem meet the bed

_MAID_LEGS = {
    "plus": ["Leg", "Sock", "SockFoot", "SockRim", "LoaferL", "LoaferL_sole", "Foot"],
    "minus": ["Leg.001", "Sock.001", "SockFoot.001", "SockRim.001",
              "LoaferR", "LoaferR_sole", "Foot.001"],
}
_MAID_ARMS = {
    "plus": ["Arm", "Hand", "Sleeve", "Cuff"],
    "minus": ["Arm.001", "Hand.001", "Sleeve.001", "Cuff.001"],
}


def _maid_rotate(obj, pivot, angle_deg, axis="X"):
    T = (Matrix.Translation(Vector(pivot)) @
         Matrix.Rotation(math.radians(angle_deg), 4, axis) @
         Matrix.Translation(-Vector(pivot)))
    obj.matrix_world = T @ obj.matrix_world


def _maid_world_bounds(objects):
    pts = []
    for o in objects:
        if o.type != "MESH":
            continue
        for c in o.bound_box:
            pts.append(o.matrix_world @ Vector(c))
    return pts


def place_maid_on_bed(scale=None, location=None, yaw_deg=None, sink=0.0):
    """Import the chibi maid, sit her directly on the duvet and return the root.

    The supplied character is a set of unparented meshes (no armature).  The
    function uses a rigid seated pose: legs swung forward at the hip and arms
    brought forward over the lap.  A single root empty carries the uniform XYZ
    scale, yaw and placement; no individual mesh is stretched.

    There is no seat cushion: the skirt hem and the soles are tuned to meet the
    duvet plane so she reads as sitting on the bed, not hovering above it.

    Calling the function again rebuilds the Maid collection from MAID_SOURCE,
    so it is safe to use as a one-click reset/placement utility.
    """
    if not os.path.exists(MAID_SOURCE):
        raise FileNotFoundError("Maid source not found: %s" % MAID_SOURCE)
    scale = float(MAID_SCALE if scale is None else scale)
    location = MAID_LOCATION if location is None else location
    yaw = math.radians(MAID_YAW_DEG if yaw_deg is None else yaw_deg)

    old = bpy.data.collections.get(MAID_COLLECTION)
    if old is not None:
        for o in list(old.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(old)
    coll = bpy.data.collections.new(MAID_COLLECTION)
    bpy.context.scene.collection.children.link(coll)

    # Import the character meshes only.  The source file also contains four
    # lights and eleven cameras; those are deliberately discarded.
    with bpy.data.libraries.load(MAID_SOURCE, link=False) as (data_from, data_to):
        data_to.objects = list(data_from.objects)
    imported = [o for o in data_to.objects if o is not None]
    meshes = []
    for o in imported:
        if o.type == "MESH":
            o.name = "Maid_" + o.name
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
            meshes.append(o)
        else:
            bpy.data.objects.remove(o, do_unlink=True)
    if not meshes:
        raise RuntimeError("No meshes were imported from %s" % MAID_SOURCE)

    # The little back bow hangs far below the seat and would be buried in the
    # duvet.  It is not visible in any delivered view, so drop it from the
    # posed copy instead of leaving hidden geometry inside the mattress.
    backbow = bpy.data.objects.get("Maid_BackBow")
    if backbow is not None:
        if backbow in meshes:
            meshes.remove(backbow)
        bpy.data.objects.remove(backbow, do_unlink=True)

    # Seated pose.  The hips are at z=0.40 in the source model.
    for side, names in _MAID_LEGS.items():
        x = 0.047 if side == "plus" else -0.047
        for base in names:
            o = bpy.data.objects.get("Maid_" + base)
            if o is not None:
                # 65 deg puts the soles and the skirt hem on the same duvet
                # plane; more angle pushes the hem through the mattress.
                _maid_rotate(o, (x, 0.0, 0.40), MAID_LEG_ANGLE)
    for side, names in _MAID_ARMS.items():
        x = 0.10 if side == "plus" else -0.10
        for base in names:
            o = bpy.data.objects.get("Maid_" + base)
            if o is not None:
                _maid_rotate(o, (x, 0.0, 0.57), -45.0)

    # One root carries every transform.  matrix_parent_inverse = identity keeps
    # the existing character-space matrices while the root is still at origin.
    root = bpy.data.objects.new("Maid_Root", None)
    coll.objects.link(root)
    root.empty_display_type = "PLAIN_AXES"
    root.empty_display_size = 0.12
    root.scale = (scale, scale, scale)
    root.rotation_euler = (0.0, 0.0, yaw)
    for o in meshes:
        mw = o.matrix_world.copy()
        o.parent = root
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_world = mw

    bpy.context.view_layer.update()
    # Use the leg/shoe bounds for mattress contact; at MAID_LEG_ANGLE = -65 the
    # skirt hem lands ~4 mm above the same plane, so nothing visibly clips.
    leg_objects = []
    for names in _MAID_LEGS.values():
        for base in names:
            o = bpy.data.objects.get("Maid_" + base)
            if o is not None:
                leg_objects.append(o)
    leg_pts = _maid_world_bounds(leg_objects)
    all_pts = _maid_world_bounds(meshes)
    body_min = min(p.z for p in all_pts)
    leg_min = min(p.z for p in leg_pts) if leg_pts else body_min
    # Contact is set by the soles; the back-bow mesh has already been removed.
    root.location = (location[0], location[1],
                     MAID_BED_TOP + float(sink) - leg_min)
    bpy.context.view_layer.update()

    all_pts = _maid_world_bounds(meshes)
    zmin = min(p.z for p in all_pts)
    zmax = max(p.z for p in all_pts)
    root["maid_source"] = MAID_SOURCE
    root["uniform_scale"] = scale
    root["seated_height_m"] = round(zmax - MAID_BED_TOP, 3)
    root["pose"] = "seated on bed, legs forward %.0fdeg, arms -45deg" % MAID_LEG_ANGLE
    print("[WarmBedroom] maid placed: scale=%.2f seated height=%.2fm z=[%.3f, %.3f] body_min=%.3f leg_min=%.3f"
          % (scale, zmax - MAID_BED_TOP, zmin, zmax, body_min, leg_min))
    return root


def render_maid_check(path=None):
    """Render a quick close-up of the seated maid for pose validation."""
    scene = bpy.context.scene
    cam = bpy.data.objects.get("Camera_Maid")
    if cam is None:
        raise RuntimeError("Camera_Maid is missing")
    old_cam = scene.camera
    old_res = (scene.render.resolution_x, scene.render.resolution_y)
    old_samples = scene.cycles.samples
    old_path = scene.render.filepath
    try:
        scene.camera = cam
        scene.render.resolution_x = 1200
        scene.render.resolution_y = 900
        scene.render.resolution_percentage = 100
        scene.cycles.samples = 64
        scene.cycles.use_denoising = True
        scene.render.image_settings.file_format = "PNG"
        if path is None:
            path = os.path.join(os.path.dirname(bpy.data.filepath),
                                "renders_v2", "maid_selfcheck.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print("[WarmBedroom] maid check ->", path)
        return path
    finally:
        scene.camera = old_cam
        scene.render.resolution_x, scene.render.resolution_y = old_res
        scene.cycles.samples = old_samples
        scene.render.filepath = old_path


# ---------------------------------------------------------------------------
# Example combinations (uncomment to run on demand)
# ---------------------------------------------------------------------------
# 示例 1：黄昏晴天，暖阳斜照、台灯亮起，最温馨的房间氛围。
# set_time_of_day("dusk"); set_weather("sunny")
#
# 示例 2：清晨雨天，冷调天光 + 室内暖灯，形成冷暖对比。
# set_time_of_day("dawn"); set_weather("rainy")
#
# 示例 3：夜晚暴雨，仅靠床头灯与落地灯，窗外城市微光和雨幕。
# set_time_of_day("night"); set_weather("storm")
# set_lightning(True)          # 可选：一道闪电定格
#
# 画芯替换：
# set_frame_artwork(r"E:/pictures/artwork.jpg")
