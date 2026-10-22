/* Warm Bedroom — live 3D viewer (v2).

   Camera: true 6-DOF free flight.  Position (x/y/z, including lift) and
   orientation (yaw/pitch/roll) are independent, so you can fly anywhere in the
   room and look any direction instead of sliding along a fixed eye plane.

   Lighting numbers come from the user's scene_controller.py presets, so the site
   reproduces Blender's 5 times x 4 weathers -- including turning the room lights
   UP when it rains and keeping the TV readable in daylight.

   Coordinates: the .blend is Z-up; the GLB is exported Y-up, so a Blender point
   (x, y, z) becomes (x, z, -y) here.  bl() does that conversion so every number
   stays traceable to the measured model.
*/
(() => {
  "use strict";

  const $ = (s) => document.querySelector(s);
  const canvas = $("#viewer");
  const qs = new URLSearchParams(location.search);
  const isTouch = matchMedia("(pointer: coarse)").matches || navigator.maxTouchPoints > 0 || qs.get("touch") === "1";
  if (isTouch) document.body.classList.add("touch");

  const bl = (x, y, z) => [x, z, -y];

  /* View boundaries (Y-up). -Z is the art wall, +Z the TV wall, +X the window. */
  const ROOM = { minX: -2.26, maxX: 2.26, minZ: -2.46, maxZ: 2.46, minY: 0.08, maxY: 2.72, eye: 1.58 };

  /* Blender: window glass x=2.365, y 0.605..2.295, z 0.905..2.295 */
  const WINDOW = bl(2.365, 1.45, 1.60);
  const WINDOW_BOX = { x: 2.365, y: [0.905, 2.295], z: [-2.295, -0.605] };

  /* Light fixture anchors, measured in Blender and converted.
     The practical lamps light from the OPEN BOTTOM of the shade, not from the
     bulb centre: the shade is a solid mesh, so a light at the bulb sits inside it
     and the shade blocks every ray.  These y values are just below each shade's
     lower rim (bedside 0.939, desk 1.054, floor 1.349 in Blender Z). */
  const FIX = {
    bedside: bl(1.13, 2.27, 1.02),
    desk: bl(1.948, 1.7181, 1.09),
    floorLamp: bl(-2.02, -2.31, 1.45),
    tv: bl(0.0, -2.392, 1.30),
    art: bl(0.0, 2.3825, 2.2125),
    // light origins, at the shade opening
    bedsideLight: bl(1.13, 2.27, 0.94),
    deskLight: bl(1.948, 1.7181, 1.05),
    floorLight: bl(-2.02, -2.31, 1.34)
  };

  /* Time presets — mirror TIME_PRESETS in scene_controller.py.
     `fill` / `windowFill` are Blender watts; they are normalised where used so
     the relative brightness of the five times survives. */
  const TIMES = {
    dawn: {
      label: "黎明", clock: "05:40", icon: "dawn",
      desc: "低角度的晨光，窗外的空气还有些凉。",
      exposure: 0.65, sun: 3.0, sunColor: 0xffb27a, fill: 5.0,
      room: { bedside: 22, floor: 12, desk: 4, art: 3 },
      tvGlow: 0.05, windowFill: 16, windowFillColor: 0xffd9b8,
      bg: 0x2a2f42, ambient: 0.18, sheer: false, city: false, moon: false, sunDisc: true
    },
    morning: {
      label: "晨光", clock: "08:20", icon: "morning",
      desc: "清透的晨光从窗边进来，房间刚开始亮。",
      exposure: 0.10, sun: 8.5, sunColor: 0xffe7c8, fill: 10.0,
      room: { bedside: 0, floor: 0, desk: 0, art: 0 },
      tvGlow: 0.0, windowFill: 72, windowFillColor: 0xdcecff,
      bg: 0xa8c6e2, ambient: 0.82, sheer: false, city: false, moon: false, sunDisc: false
    },
    noon: {
      label: "正午", clock: "12:30", icon: "noon",
      desc: "高角度日光穿过半透窗纱，干净而明亮。",
      exposure: -0.15, sun: 8.0, sunColor: 0xfff4de, fill: 18.0,
      room: { bedside: 0, floor: 0, desk: 0, art: 0 },
      tvGlow: 0.0, windowFill: 155, windowFillColor: 0xe8f4ff,
      bg: 0xc2d9ec, ambient: 0.92, sheer: true, city: false, moon: false, sunDisc: false
    },
    dusk: {
      label: "黄昏", clock: "18:40", icon: "dusk",
      desc: "夕阳斜照，床头灯和电视的光把房间包住。",
      exposure: 0.0, sun: 10.5, sunColor: 0xffa35c, fill: 5.0,
      room: { bedside: 22, floor: 12, desk: 6, art: 4 },
      tvGlow: 6.0, windowFill: 23, windowFillColor: 0xffc79a,
      bg: 0x33283a, ambient: 0.16, sheer: false, city: false, moon: false, sunDisc: true
    },
    night: {
      label: "夜晚", clock: "22:15", icon: "night",
      desc: "只留床头灯、书桌灯和屏幕微光，城市在窗外。",
      exposure: 0.95, sun: 0.08, sunColor: 0xcfd8f0, fill: 2.5,
      room: { bedside: 30, floor: 22, desk: 8, art: 2.6 },
      tvGlow: 9.0, windowFill: 0.4, windowFillColor: 0x8fa4c4,
      bg: 0x070a11, ambient: 0.025, sheer: false, city: true, moon: true, sunDisc: false,
      // night reads best with a low exposure so the lamps stay pools of light
      exposureTrim: -1.15
    }
  };

  /* Weather presets.  roomMult multiplies the room lights so rain LIGHTS the
     room instead of leaving it dark. */
  const WEATHERS = {
    sunny: { label: "晴天", sunFactor: 1.0, exposureAdd: 0.0, worldMult: 1.0,
             roomMult: 1.0, fillMult: 1.0, rain: 0, haze: 0.055, windowTint: 1.0, lightning: false, skyTint: null },
    cloudy: { label: "多云", sunFactor: 0.24, exposureAdd: 0.18, worldMult: 0.70,
              roomMult: 1.08, fillMult: 1.25, rain: 0, haze: 0.12, windowTint: 0.72, lightning: false, skyTint: 0x9aa3ab },
    rainy: { label: "雨天", sunFactor: 0.075, exposureAdd: 0.42, worldMult: 0.42,
             roomMult: 1.62, fillMult: 1.38, rain: 0.62, haze: 0.24, windowTint: 0.5, lightning: false, skyTint: 0x6d7c82 },
    storm: { label: "暴雨", sunFactor: 0.018, exposureAdd: 0.62, worldMult: 0.20,
             roomMult: 1.80, fillMult: 1.52, rain: 1.0, haze: 0.34, windowTint: 0.36, lightning: true, skyTint: 0x2b343b }
  };

  /* Camera presets, in the viewer's Y-up frame. */
  const VIEWS = [
    { id: "bed", label: "床与画框", short: "床", pos: [0, 1.58, 0.95], look: [0, 1.05, -1.75] },
    { id: "desk", label: "书桌窗景", short: "书桌", pos: [0.55, 1.50, 0.05], look: [2.05, 1.05, -1.45] },
    { id: "tv", label: "电视游戏区", short: "电视", pos: [0, 1.55, 0.62], look: [0, 1.15, 2.42] },
    { id: "door", label: "衣柜与门", short: "门柜", pos: [0.5, 1.55, 0.18], look: [-2.2, 1.2, -1.45] },
    { id: "maid", label: "小女仆", short: "女仆", pos: [0.10, 1.42, -0.92], look: [0.46, 1.02, -1.99] },
    { id: "plants", label: "绿植角落", short: "绿植", pos: [0.35, 1.45, -0.60], look: [1.85, 1.02, -1.95] },
    { id: "window", label: "窗外景色", short: "窗外", pos: [1.30, 1.45, -1.45], look: [7.0, 1.25, -1.45] },
    { id: "overview", label: "全屋", short: "全景", pos: [0, 1.65, 2.08], look: [0, 1.05, -1.05] }
  ];

  const GROUPS = {
    Baked_Architecture: { file: "architecture.jpg", rough: 0.80 },
    Baked_Bedding: { file: "bedding.jpg", rough: 0.90 },
    Baked_Decor: { file: "decor.jpg", rough: 0.62 },
    Baked_Furniture: { file: "furniture.jpg", rough: 0.55 },
    Baked_Maid: { file: "maid.jpg", rough: 0.58 },
    Baked_Plants: { file: "plants.jpg", rough: 0.70 },
    Baked_Window: { file: "window.jpg", rough: 0.75 },
    Baked_OutdoorNear: { file: "outdoornear.jpg", rough: 0.78 }
  };

  let scene, camera, renderer, controls;
  let hemi, sun, fillSoft, fillWindow, spotWindow;
  const lampLights = {};
  const lampGlows = [];
  let tvLight, artLight, flashLight;
  let skyMat, sunSprite, moonSprite, groundMesh, stars;
  let rain, rainGeo, rainMat, glassRain, glassRainGeo, glassRainMat;
  const rainState = [];
  const glassRainState = [];
  let fogOn = false;
  let tvMaterial = null, artMaterial = null;
  let mode = "fly";
  let activeTime = "dusk", activeWeather = "sunny";
  let currentView = "bed";
  let targetFov = 58, smoothFov = 58;
  const fly = {
    pos: new THREE.Vector3(0, ROOM.eye, 0.95),
    yaw: 0, pitch: -0.10, roll: 0,
    vel: new THREE.Vector3()
  };
  let dragging = false, lastPointer = null, activeButton = 0;
  const keys = Object.create(null);
  const joy = { x: 0, y: 0, active: false, lift: 0, liftActive: false };
  let clock, flashNext = 5, flash = 0, ready = false;

  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;

  /* ------------------------------------------------------------- helpers */
  function progress(p, msg) {
    const el = $("#load-fill"), pc = $("#load-pct");
    if (el) el.style.width = p + "%";
    if (pc) pc.textContent = Math.round(p) + "%";
    const h = $(".loading h2");
    if (h && msg) h.textContent = msg;
  }
  function fail(err) {
    console.error(err);
    const l = $("#loading");
    if (l) l.classList.add("error");
    const e = $("#load-err");
    if (e) e.innerHTML = "加载失败：" + String(err).replace(/[<>&]/g, "") + "<br>请确认整个 website 文件夹完整。";
  }

  /* THREE's camera looks down -Z, so with Euler order "YXZ" the forward vector
     is (-sin(yaw)cos(pitch), sin(pitch), -cos(yaw)cos(pitch)) and the horizontal
     right vector is (cos(yaw), 0, -sin(yaw)).  Sole source of truth for both the
     look direction and movement, so they cannot drift apart. */
  function dirFrom(yaw, pitch) {
    const cp = Math.cos(pitch);
    return new THREE.Vector3(-Math.sin(yaw) * cp, Math.sin(pitch), -Math.cos(yaw) * cp);
  }
  function rightFrom(yaw) {
    return new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
  }
  function yawPitchTo(from, look) {
    const lx = Array.isArray(look) ? look[0] : look.x;
    const ly = Array.isArray(look) ? look[1] : look.y;
    const lz = Array.isArray(look) ? look[2] : look.z;
    const d = new THREE.Vector3(lx - from.x, ly - from.y, lz - from.z).normalize();
    return { yaw: Math.atan2(-d.x, -d.z), pitch: Math.asin(clamp(d.y, -1, 1)) };
  }

  /* ---------------------------------------------------------- scene setup */
  function setupScene() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x120d09);

    camera = new THREE.PerspectiveCamera(58, innerWidth / innerHeight, 0.02, 600);
    camera.rotation.order = "YXZ";

    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: "high-performance" });
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    renderer.setSize(innerWidth, innerHeight);
    renderer.outputEncoding = THREE.sRGBEncoding;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;

    hemi = new THREE.HemisphereLight(0xffe9d2, 0x241a12, 0.5);
    scene.add(hemi);

    /* key light: the sun through the window (+X) */
    sun = new THREE.DirectionalLight(0xffd2a0, 3.0);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.camera.left = -3.6;
    sun.shadow.camera.right = 3.6;
    sun.shadow.camera.top = 3.0;
    sun.shadow.camera.bottom = -2.6;
    sun.shadow.camera.near = 0.1;
    sun.shadow.camera.far = 30;
    sun.shadow.bias = -0.0007;
    scene.add(sun);
    scene.add(sun.target);

    /* soft fills mirroring Fill_Soft / Fill_Window in the .blend */
    fillSoft = new THREE.DirectionalLight(0xffd9b5, 0.3);
    fillSoft.position.set(0, 2.4, 1.6);
    scene.add(fillSoft);
    fillWindow = new THREE.DirectionalLight(0xffe6cf, 0.5);
    fillWindow.position.set(2.8, 1.45, -1.5);
    fillWindow.target.position.set(0, 1.2, -0.4);
    scene.add(fillWindow);
    scene.add(fillWindow.target);

    /* window spot: the pool of daylight on the desk and floor */
    spotWindow = new THREE.SpotLight(0xffe0bb, 2.0, 10, Math.PI / 3.2, 0.85, 1.4);
    spotWindow.position.set(WINDOW[0] + 0.2, WINDOW[1] + 0.1, WINDOW[2] + 0.25);
    spotWindow.target.position.set(0.5, 0.85, WINDOW[2] - 0.15);
    spotWindow.castShadow = true;
    spotWindow.shadow.mapSize.set(2048, 2048);
    spotWindow.shadow.bias = -0.0006;
    spotWindow.shadow.camera.near = 0.05;
    spotWindow.shadow.camera.far = 14;
    scene.add(spotWindow);
    scene.add(spotWindow.target);

    /* practical lights at the real bulb positions */
    const mkLamp = (key, pos, dist) => {
      /* decay 1 (linear) instead of the physical 2: the shades sit only ~20 cm
         from a wall, and inverse-square blows that wall out completely. */
      const l = new THREE.PointLight(0xffb56a, 0, dist, 1.0);
      l.position.set(pos[0], pos[1], pos[2]);
      scene.add(l);
      lampLights[key] = l;
    };
    mkLamp("bedside", FIX.bedsideLight, 5.2);
    mkLamp("desk", FIX.deskLight, 3.8);
    mkLamp("floor", FIX.floorLight, 6.2);

    const glowTex = makeGlowTexture();
    [["bedside", FIX.bedside, 0.40], ["desk", FIX.desk, 0.26], ["floor", FIX.floorLamp, 0.36]]      .forEach(([key, p, s]) => {
        const m = new THREE.SpriteMaterial({ map: glowTex, color: 0xffb36a, transparent: true,
          opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending });
        const sp = new THREE.Sprite(m);
        sp.position.set(p[0], p[1], p[2]);
        sp.scale.set(s, s, 1);
        scene.add(sp);
        lampGlows.push({ key: key, sprite: sp });
      });

    /* TV glow 5 cm in front of the screen (screen faces +Z in this frame) */
    tvLight = new THREE.PointLight(0xff9a72, 0, 4.6, 1.7);
    tvLight.position.set(FIX.tv[0], FIX.tv[1] + 0.06, FIX.tv[2] - 0.05);
    scene.add(tvLight);

    /* picture light above the frame, aimed at the art */
    artLight = new THREE.SpotLight(0xffcf9c, 0, 3.4, Math.PI / 5, 0.7, 1.5);
    artLight.position.set(FIX.art[0], FIX.art[1], FIX.art[2]);
    artLight.target.position.set(0, 1.86, -2.44);
    scene.add(artLight);
    scene.add(artLight.target);

    flashLight = new THREE.PointLight(0xcfe0ff, 0, 14, 1.4);
    flashLight.position.set(2.4, 2.6, -2.0);
    scene.add(flashLight);

    /* sky sphere, large enough that any camera position stays inside */
    skyMat = new THREE.MeshBasicMaterial({ side: THREE.BackSide, toneMapped: false, depthWrite: false });
    const sky = new THREE.Mesh(new THREE.SphereGeometry(300, 48, 32), skyMat);
    scene.add(sky);

    /* ground outside so the garden is not floating */
    groundMesh = new THREE.Mesh(
      new THREE.PlaneGeometry(600, 600),
      new THREE.MeshStandardMaterial({ color: 0x5d6b4d, roughness: 0.95, metalness: 0 })
    );
    groundMesh.rotation.x = -Math.PI / 2;
    groundMesh.position.y = -0.03;
    groundMesh.receiveShadow = true;
    scene.add(groundMesh);

    sunSprite = makeDiscSprite(0xfff0cf);
    sunSprite.scale.set(34, 34, 1);
    scene.add(sunSprite);
    moonSprite = makeDiscSprite(0xdfe8ff);
    moonSprite.scale.set(16, 16, 1);
    scene.add(moonSprite);
    stars = makeStars();
    scene.add(stars);

    controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.075;
    controls.minDistance = 0.35;
    controls.maxDistance = 7.0;
    controls.maxPolarAngle = Math.PI * 0.96;
    controls.target.set(0, 1.08, 0.45);
    controls.enabled = false;

    if (isTouch) targetFov = 68;
    createRain();
    bindUI();
    setMode("fly");
    goView(isTouch ? "overview" : "bed");
    applyEnvironment();
    clock = new THREE.Clock();
    resize();
    addEventListener("resize", resize);
    requestAnimationFrame(loop);
  }

  function resize() {
    if (!renderer || !camera) return;
    const w = Math.max(320, innerWidth), h = Math.max(240, innerHeight);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2));
    renderer.setSize(w, h);
  }

  function makeGlowTexture() {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const x = c.getContext("2d");
    const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(255,240,205,.95)");
    g.addColorStop(0.18, "rgba(255,196,128,.62)");
    g.addColorStop(1, "rgba(255,150,70,0)");
    x.fillStyle = g;
    x.fillRect(0, 0, 128, 128);
    const t = new THREE.CanvasTexture(c);
    t.encoding = THREE.sRGBEncoding;
    return t;
  }

  function makeDiscSprite(color) {
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const x = c.getContext("2d");
    const g = x.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.4, "rgba(255,255,255,.85)");
    g.addColorStop(0.56, "rgba(255,255,255,.22)");
    g.addColorStop(1, "rgba(255,255,255,0)");
    x.fillStyle = g;
    x.fillRect(0, 0, 128, 128);
    const t = new THREE.CanvasTexture(c);
    t.encoding = THREE.sRGBEncoding;
    return new THREE.Sprite(new THREE.SpriteMaterial({
      map: t, color: color, transparent: true, opacity: 0.9,
      depthWrite: false, blending: THREE.AdditiveBlending, toneMapped: false
    }));
  }

  function makeStars() {
    const N = 500;
    const g = new THREE.BufferGeometry();
    const p = new Float32Array(N * 3);
    for (let i = 0; i < N; i++) {
      const v = new THREE.Vector3().setFromSphericalCoords(
        220, Math.acos(Math.random() * 0.6), Math.random() * Math.PI * 2);
      p[i * 3] = v.x;
      p[i * 3 + 1] = Math.max(v.y, 8);
      p[i * 3 + 2] = v.z;
    }
    g.setAttribute("position", new THREE.BufferAttribute(p, 3));
    const m = new THREE.PointsMaterial({ color: 0xdfe8ff, size: 1.6, sizeAttenuation: false,
      transparent: true, opacity: 0, depthWrite: false });
    return new THREE.Points(g, m);
  }

  /* ------------------------------------------------------------ sky plate */
  function skyPalette(timeId, weatherId) {
    const w = WEATHERS[weatherId] || WEATHERS.sunny;
    const rainy = weatherId === "rainy" || weatherId === "storm";
    let top, mid, low, horizon, sunCol;
    switch (timeId) {
      case "night":
        top = "#03050b"; mid = "#081020"; low = "#111c2e"; horizon = "#253142"; sunCol = "#e5edff"; break;
      case "dawn":
        top = "#172a50"; mid = "#52678f"; low = "#d79a83"; horizon = "#f3b071"; sunCol = "#ffd5b8"; break;
      case "noon":
        top = "#2363ae"; mid = "#4a88c8"; low = "#9dcbea"; horizon = "#dceefb"; sunCol = "#fff9db"; break;
      case "morning":
        top = "#2c68b0"; mid = "#5d95ce"; low = "#b5d5ed"; horizon = "#e7f2fb"; sunCol = "#fff7d8"; break;
      default:
        top = "#0b1735"; mid = "#3e5a88"; low = "#de825f"; horizon = "#ff9a4b"; sunCol = "#ffc08b";
    }
    if (rainy) {
      const dark = timeId === "night";
      top = dark ? "#0a1017" : "#33404a";
      mid = dark ? "#131c26" : "#4d5a62";
      low = dark ? "#1b1f23" : "#72787a";
      horizon = dark ? "#20262b" : "#8b9091";
      sunCol = "#b7c2ca";
    }
    if (w.skyTint) {
      const mix = (hex, t) => {
        const a = new THREE.Color(hex), b = new THREE.Color(w.skyTint);
        return "#" + a.lerp(b, t).getHexString();
      };
      const k = rainy ? 0.7 : 0.45;
      top = mix(top, k);
      mid = mix(mid, k * 0.9);
      low = mix(low, k * 0.7);
    }
    return { top: top, mid: mid, low: low, horizon: horizon, sunCol: sunCol };
  }

  function makeSkyTexture(timeId, weatherId) {
    const c = document.createElement("canvas");
    c.width = 2048;
    c.height = 1024;
    const x = c.getContext("2d");
    const pal = skyPalette(timeId, weatherId);
    const rainy = weatherId === "rainy" || weatherId === "storm";

    const g = x.createLinearGradient(0, 0, 0, 1024);
    g.addColorStop(0, pal.top);
    g.addColorStop(0.42, pal.mid);
    g.addColorStop(0.68, pal.low);
    g.addColorStop(0.8, pal.horizon);
    g.addColorStop(1, pal.horizon);
    x.fillStyle = g;
    x.fillRect(0, 0, 2048, 1024);

    x.save();
    x.filter = "blur(16px)";
    for (let i = 0; i < 15; i++) {
      const cx = (i * 271) % 2048;
      const cy = 120 + ((i * 113) % 300);
      const rx = 200 + ((i * 71) % 210);
      const ry = 32 + ((i * 29) % 44);
      x.fillStyle = rainy ? "rgba(190,200,206,.14)"
        : (timeId === "night" ? "rgba(150,175,205,.05)" : "rgba(255,240,220,.17)");
      x.beginPath();
      x.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
      x.fill();
    }
    x.restore();

    x.save();
    x.filter = "blur(30px)";
    x.globalAlpha = 0.8;
    x.fillStyle = pal.sunCol;
    x.beginPath();
    x.arc(timeId === "dusk" || timeId === "dawn" ? 1520 : 1160, 460, 155, 0, Math.PI * 2);
    x.fill();
    x.restore();

    if (rainy) {
      x.fillStyle = "rgba(16,24,30,.22)";
      x.fillRect(0, 0, 2048, 1024);
    }
    const t = new THREE.CanvasTexture(c);
    t.encoding = THREE.sRGBEncoding;
    t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
    t.needsUpdate = true;
    return t;
  }

  function refreshSky() {
    if (!skyMat) return;
    const old = skyMat.map;
    skyMat.map = makeSkyTexture(activeTime, activeWeather);
    skyMat.needsUpdate = true;
    if (old) old.dispose();
  }

  /* ------------------------------------------------------------------ rain */
  function createRain() {
    const N = 2400;
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(N * 6), 3));
    geo.setDrawRange(0, 0);
    rainMat = new THREE.LineBasicMaterial({ color: 0xc4dbe8, transparent: true, opacity: 0.4, depthWrite: false });
    rain = new THREE.LineSegments(geo, rainMat);
    rain.frustumCulled = false;
    rain.visible = false;
    scene.add(rain);
    rainGeo = geo;
    for (let i = 0; i < N; i++) {
      rainState.push({
        x: 2.42 + Math.random() * 7.2,
        y: Math.random() * 8.0,
        z: -3.6 + Math.random() * 7.4,
        len: 0.14 + Math.random() * 0.38,
        sp: 2.6 + Math.random() * 3.4
      });
    }

    const G = 320;
    const gg = new THREE.BufferGeometry();
    gg.setAttribute("position", new THREE.BufferAttribute(new Float32Array(G * 6), 3));
    gg.setDrawRange(0, 0);
    glassRainMat = new THREE.LineBasicMaterial({ color: 0xd8e8f2, transparent: true, opacity: 0.34, depthWrite: false });
    glassRain = new THREE.LineSegments(gg, glassRainMat);
    glassRain.frustumCulled = false;
    glassRain.visible = false;
    scene.add(glassRain);
    glassRainGeo = gg;
    for (let i = 0; i < G; i++) {
      glassRainState.push({
        y: WINDOW_BOX.y[0] + Math.random() * (WINDOW_BOX.y[1] - WINDOW_BOX.y[0]),
        z: WINDOW_BOX.z[0] + Math.random() * (WINDOW_BOX.z[1] - WINDOW_BOX.z[0]),
        len: 0.07 + Math.random() * 0.22,
        sp: 0.9 + Math.random() * 1.6
      });
    }
  }

  function setRain(intensity) {
    const on = intensity > 0;
    rain.visible = on;
    glassRain.visible = on;
    const n = on ? Math.floor(rainState.length * intensity) : 0;
    const g = on ? Math.floor(glassRainState.length * intensity) : 0;
    rain._n = n;
    glassRain._n = g;
    rainGeo.setDrawRange(0, n * 2);
    glassRainGeo.setDrawRange(0, g * 2);
    rainMat.opacity = 0.26 + 0.26 * intensity;
    glassRainMat.opacity = 0.16 + 0.24 * intensity;
  }

  function updateRain(dt) {
    if (!rain.visible) return;
    const heavy = activeWeather === "storm";
    const rp = rainGeo.attributes.position.array;
    const n = rain._n || 0;
    for (let i = 0; i < n; i++) {
      const d = rainState[i];
      d.y -= d.sp * dt * (heavy ? 1.5 : 1.0);
      if (d.y < 0.25) {
        d.y = 8.0 + Math.random();
        d.x = 2.42 + Math.random() * 7.2;
        d.z = -3.6 + Math.random() * 7.4;
      }
      rp[i * 6] = d.x; rp[i * 6 + 1] = d.y; rp[i * 6 + 2] = d.z;
      rp[i * 6 + 3] = d.x; rp[i * 6 + 4] = d.y - d.len; rp[i * 6 + 5] = d.z;
    }
    rainGeo.attributes.position.needsUpdate = true;
    rainGeo.setDrawRange(0, n * 2);

    const gp = glassRainGeo.attributes.position.array;
    const g = glassRain._n || 0;
    for (let i = 0; i < g; i++) {
      const d = glassRainState[i];
      d.y -= d.sp * dt * (heavy ? 1.4 : 1.0);
      if (d.y < WINDOW_BOX.y[0]) d.y = WINDOW_BOX.y[1];
      gp[i * 6] = WINDOW_BOX.x - 0.03; gp[i * 6 + 1] = d.y; gp[i * 6 + 2] = d.z;
      gp[i * 6 + 3] = WINDOW_BOX.x - 0.03; gp[i * 6 + 4] = d.y - d.len; gp[i * 6 + 5] = d.z;
    }
    glassRainGeo.attributes.position.needsUpdate = true;
    glassRainGeo.setDrawRange(0, g * 2);
  }

  /* ----------------------------------------------------------- environment */
  function applyEnvironment() {
    if (!scene) return;
    const t = TIMES[activeTime] || TIMES.dusk;
    const w = WEATHERS[activeWeather] || WEATHERS.sunny;
    const rainy = activeWeather === "rainy" || activeWeather === "storm";

    renderer.toneMappingExposure = Math.pow(2, t.exposure + w.exposureAdd + (t.exposureTrim || 0));
    scene.background.setHex(t.bg);

    refreshSky();
    skyMat.color.setScalar(clamp(t.ambient * w.worldMult + (rainy ? 0.05 : 0.03), 0.03, 1));

    /* the sun comes in through the window (+X), so aim it from there */
    const elev = activeTime === "noon" ? 0.95 : (activeTime === "dusk" || activeTime === "dawn") ? 0.22 : 0.55;
    const azim = 0.42;
    const sDir = new THREE.Vector3(
      Math.cos(elev) * Math.cos(azim), Math.sin(elev), -Math.cos(elev) * Math.sin(azim)).normalize();
    sun.position.copy(sDir).multiplyScalar(20);
    sun.target.position.set(0, 1.0, 0.2);
    sun.intensity = t.sun * w.sunFactor * 0.5;
    sun.color.setHex(t.sunColor);
    sun.visible = sun.intensity > 0.02;

    const showSun = t.sunDisc && !rainy && activeWeather !== "cloudy";
    const showMoon = t.moon && !rainy;
    sunSprite.position.copy(sDir).multiplyScalar(170);
    sunSprite.position.y = Math.max(sunSprite.position.y, 26);
    sunSprite.material.color.setHex(t.sunColor);
    sunSprite.material.opacity = showSun ? 0.95 : 0;
    moonSprite.position.set(100, 130, -80);
    moonSprite.material.opacity = showMoon ? 0.9 : 0;
    if (stars) stars.material.opacity = (activeTime === "night" && !rainy) ? 0.85 : 0;

    hemi.intensity = lerp(0.02, 0.42, clamp(t.ambient * w.worldMult, 0, 1));
    hemi.color.setHex(t.windowFillColor);
    /* Room lights.  Blender's presets are watts (30 W at night, 0 W by day), a
       range too wide to hand straight to three.js, so each fixture is normalised
       against its own night value and then given a usable intensity.  Weather
       multiplies them UP, which is why rain does not leave the room black. */
    const rm = w.roomMult * w.fillMult;
    fillSoft.intensity = (t.fill / 18.0) * 0.85 * rm;
    fillWindow.intensity = (t.windowFill / 155.0) * 0.9 * w.windowTint;
    fillWindow.color.setHex(t.windowFillColor);
    spotWindow.intensity = (t.windowFill / 155.0) * 2.2 * w.windowTint;
    spotWindow.color.setHex(t.windowFillColor);
    spotWindow.visible = spotWindow.intensity > 0.05;

    /* A point light this close to the shade needs a large intensity to read, so
       the night values are much higher than the linear watt ratio.  Distance
       falloff keeps each lamp a warm pool instead of lighting the room evenly.
       Note: PointLight.distance = 0 means "no cutoff" in three.js, so it must
       never be given 0 or the intensity maths below collapses. */
    const lit = (watts, maxWatts, peak) => (maxWatts > 0 ? (watts / maxWatts) * peak * rm : 0);
    lampLights.bedside.intensity = lit(t.room.bedside, 30.0, 1.5);
    lampLights.desk.intensity = lit(t.room.desk, 8.0, 0.6);
    lampLights.floor.intensity = lit(t.room.floor, 22.0, 1.2);
    lampGlows.forEach((g) => {
      const l = lampLights[g.key];
      g.sprite.material.opacity = l.intensity > 0.03 ? Math.min(0.85, l.intensity * 0.45 + 0.12) : 0;
    });

    /* The screen must stay readable in daylight: keep its base colour high and
       let the emissive glow only add on top of it. */
    if (tvMaterial) tvMaterial.color.setScalar(t.tvGlow > 1 ? 1.0 : 0.92);
    tvLight.intensity = Math.min(4.5, t.tvGlow * rm * 0.28);

    artLight.intensity = (t.room.art / 4.0) * 0.9 * rm;
    artLight.visible = artLight.intensity > 0.03;

    setRain(w.rain);
    if (w.haze > 0.001 && rainy) {
      scene.fog = new THREE.FogExp2(t.bg, 0.012 + w.haze * 0.05);
      fogOn = true;
    } else if (fogOn) {
      scene.fog = null;
      fogOn = false;
    }

    if (groundMesh) {
      const gcol = new THREE.Color(0x5d6b4d).lerp(new THREE.Color(t.bg), rainy ? 0.6 : 0.35);
      gcol.multiplyScalar(clamp(0.35 + t.ambient * 1.1, 0.2, 1.2));
      if (activeTime === "night") gcol.multiplyScalar(0.35);
      groundMesh.material.color.copy(gcol);
    }

    $("#story-title").innerHTML = t.label + " <em>" + t.clock + "</em>";
    $("#story-desc").textContent = t.desc + (w.label !== "晴天" ? " · " + w.label : "");
    document.querySelectorAll(".time-btn").forEach(b => b.classList.toggle("active", b.dataset.time === activeTime));
    document.querySelectorAll(".weather button").forEach(b => b.classList.toggle("active", b.dataset.weather === activeWeather));
  }

  /* --------------------------------------------------------------- camera */
  function applyFlyCamera() {
    if (!camera) return;
    camera.position.copy(fly.pos);
    smoothFov += (targetFov - smoothFov) * 0.15;
    if (Math.abs(camera.fov - smoothFov) > 0.01) {
      camera.fov = smoothFov;
      camera.updateProjectionMatrix();
    }
    camera.quaternion.setFromEuler(new THREE.Euler(fly.pitch, fly.yaw, fly.roll, "YXZ"));
  }

  function clampPos(p) {
    p.x = clamp(p.x, ROOM.minX, ROOM.maxX);
    p.y = clamp(p.y, ROOM.minY, ROOM.maxY);
    p.z = clamp(p.z, ROOM.minZ, ROOM.maxZ);
    return p;
  }

  function updateFly(dt) {
    const rotSpeed = keys["shift"] ? 2.2 : 1.35;
    if (keys["q"]) fly.roll = clamp(fly.roll + rotSpeed * dt, -1.1, 1.1);
    if (keys["e"]) fly.roll = clamp(fly.roll - rotSpeed * dt, -1.1, 1.1);

    let f = 0, r = 0, u = 0;
    if (keys["w"] || keys["arrowup"]) f += 1;
    if (keys["s"] || keys["arrowdown"]) f -= 1;
    if (keys["d"] || keys["arrowright"]) r += 1;
    if (keys["a"] || keys["arrowleft"]) r -= 1;
    if (keys[" "] || keys["r"]) u += 1;
    if (keys["c"]) u -= 1;
    f += -joy.y * 0.9;
    r += joy.x * 0.9;
    u += joy.lift * 0.9;

    const len = Math.hypot(f, r, u);
    if (len > 0.001) {
      f /= Math.max(1, len);
      r /= Math.max(1, len);
      u /= Math.max(1, len);
      const speed = (keys["shift"] ? 1.9 : 0.95) * dt * 1.7;
      const move = new THREE.Vector3()
        .addScaledVector(dirFrom(fly.yaw, fly.pitch), f * speed)
        .addScaledVector(rightFrom(fly.yaw), r * speed)
        .addScaledVector(new THREE.Vector3(0, 1, 0), u * speed);
      fly.vel.lerp(move, 0.5);
    } else {
      fly.vel.multiplyScalar(0.85);
      if (fly.vel.lengthSq() < 1e-7) fly.vel.set(0, 0, 0);
    }
    fly.pos.add(fly.vel);
    clampPos(fly.pos);
    applyFlyCamera();
  }

  function setMode(next) {
    mode = next;
    document.body.classList.toggle("fly", mode === "fly");
    document.body.classList.toggle("orbit", mode === "orbit");
    if (mode === "orbit") {
      controls.enabled = true;
      controls.target.set(0, 1.08, 0.45);
      camera.position.copy(fly.pos);
      controls.update();
    } else {
      controls.enabled = false;
      const d = new THREE.Vector3();
      camera.getWorldDirection(d);
      fly.yaw = Math.atan2(-d.x, -d.z);
      fly.pitch = Math.asin(clamp(d.y, -1, 1));
      const up = new THREE.Vector3(0, 1, 0).applyQuaternion(camera.quaternion);
      fly.roll = -Math.atan2(up.x, up.y);
      fly.pos.copy(camera.position);
      clampPos(fly.pos);
      applyFlyCamera();
    }
    $("#mode-label").textContent = mode === "fly" ? "自由飞行" : "环绕";
    $("#mode2-label").textContent = mode === "fly" ? "自由飞行" : "环绕观察";
    $("#mode2-sub").textContent = mode === "fly" ? "6-DOF" : "ORBIT";
    document.querySelectorAll("#btn-mode,#btn-mode2").forEach(b => b.classList.toggle("active", mode === "orbit"));
    const hint = $("#hint .desk");
    if (hint) {
      hint.innerHTML = mode === "fly"
        ? '拖动看 · <kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> 前后左右 · <kbd>空格</kbd><kbd>C</kbd> 升降 · <kbd>Q</kbd><kbd>E</kbd> 侧倾 · <kbd>Shift</kbd> 加速'
        : '拖动环绕 · 滚轮缩放 · 右键平移';
    }
    applyFlyCamera();
  }

  function goView(id) {
    const v = VIEWS.find(x => x.id === id) || VIEWS[0];
    const p = new THREE.Vector3(v.pos[0], v.pos[1], v.pos[2]);
    const t = new THREE.Vector3(v.look[0], v.look[1], v.look[2]);
    currentView = id;
    document.querySelectorAll(".view-btn").forEach(b => b.classList.toggle("active", b.dataset.view === id));
    if (mode === "fly") {
      fly.pos.copy(clampPos(p));
      const yp = yawPitchTo(fly.pos, t);
      fly.yaw = yp.yaw;
      fly.pitch = yp.pitch;
      fly.roll = 0;
      fly.vel.set(0, 0, 0);
      targetFov = isTouch ? 68 : 58;
      applyFlyCamera();
    } else {
      camera.position.copy(p);
      controls.target.copy(t);
      controls.update();
    }
  }

  /* ------------------------------------------------------------------- UI */
  function bindUI() {
    const tn = $("#times");
    tn.innerHTML = Object.keys(TIMES).map(id =>
      '<button class="time-btn" data-time="' + id + '" aria-label="' + TIMES[id].label + '">' +
      "<span>" + timeIcon(TIMES[id].icon) + "</span><span>" + TIMES[id].label + "</span></button>").join("");
    tn.querySelectorAll(".time-btn").forEach(b =>
      b.addEventListener("click", () => { activeTime = b.dataset.time; applyEnvironment(); }));

    const wn = $("#weather");
    wn.innerHTML = Object.keys(WEATHERS).map(id =>
      '<button data-weather="' + id + '" aria-label="' + WEATHERS[id].label + '">' + WEATHERS[id].label + "</button>").join("");
    wn.querySelectorAll("button").forEach(b =>
      b.addEventListener("click", () => { activeWeather = b.dataset.weather; applyEnvironment(); }));

    const vn = $("#views");
    vn.innerHTML = '<div class="eyebrow">CAMERA / 机位</div>' + VIEWS.map((v, i) =>
      '<button class="view-btn" data-view="' + v.id + '" data-short="' + v.short + '" aria-label="' + v.label + '">' +
      '<span class="num">0' + (i + 1) + '</span><span class="lbl">' + v.label + '</span><span class="ln"></span></button>').join("");
    vn.querySelectorAll(".view-btn").forEach(b => b.addEventListener("click", () => goView(b.dataset.view)));

    $("#btn-mode").addEventListener("click", () => setMode(mode === "fly" ? "orbit" : "fly"));
    $("#btn-mode2").addEventListener("click", () => setMode(mode === "fly" ? "orbit" : "fly"));
    $("#btn-full").addEventListener("click", () => {
      if (!document.fullscreenElement) document.documentElement.requestFullscreen?.().catch(() => {});
      else document.exitFullscreen?.();
    });
    $("#btn-info").addEventListener("click", () => {
      const m = $("#info-modal");
      m.classList.add("open");
      m.setAttribute("aria-hidden", "false");
    });
    document.querySelectorAll("[data-close]").forEach(b => b.addEventListener("click", () => {
      const m = $("#info-modal");
      m.classList.remove("open");
      m.setAttribute("aria-hidden", "true");
    }));
    $("#info-modal").addEventListener("click", e => {
      if (e.target.id === "info-modal") {
        e.currentTarget.classList.remove("open");
        e.currentTarget.setAttribute("aria-hidden", "true");
      }
    });
    document.querySelectorAll(".view-btn").forEach(b => b.classList.toggle("active", b.dataset.view === currentView));
    if (isTouch) document.querySelectorAll(".touch-only").forEach(e => { e.style.display = "inline"; });
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", e => { keys[e.key.toLowerCase()] = false; });
    initJoystick();
    initPointer();
  }

  function onKeyDown(e) {
    const k = e.key.toLowerCase();
    if (["w", "a", "s", "d", "arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(k)) e.preventDefault();
    keys[k] = true;
    if (k === "v") setMode(mode === "fly" ? "orbit" : "fly");
    if (k === "home") goView("bed");
    if (k === "x") $("#btn-full").click();
    if (k === "z") {
      fly.pos.set(0, ROOM.eye, 0.95);
      const yp = yawPitchTo(fly.pos, new THREE.Vector3(0, 1.05, -1.75));
      fly.yaw = yp.yaw;
      fly.pitch = yp.pitch;
      fly.roll = 0;
      applyFlyCamera();
    }
    if (k === "escape") {
      const m = $("#info-modal");
      m.classList.remove("open");
      m.setAttribute("aria-hidden", "true");
    }
    const tk = Object.keys(TIMES);
    const ti = ["1", "2", "3", "4", "5"].indexOf(k);
    if (ti >= 0 && tk[ti]) { activeTime = tk[ti]; applyEnvironment(); }
    const wk = Object.keys(WEATHERS);
    const wi = ["6", "7", "8", "9"].indexOf(k);
    if (wi >= 0 && wk[wi]) { activeWeather = wk[wi]; applyEnvironment(); }
  }

  function initPointer() {
    canvas.addEventListener("pointerdown", e => {
      if (mode !== "fly") return;
      if (e.target.closest && e.target.closest(".joy")) return;
      dragging = true;
      activeButton = e.button;
      lastPointer = { x: e.clientX, y: e.clientY };
      canvas.setPointerCapture(e.pointerId);
      canvas.classList.add("dragging");
    });
    canvas.addEventListener("pointermove", e => {
      if (!dragging || mode !== "fly" || !lastPointer) return;
      const dx = e.clientX - lastPointer.x;
      const dy = e.clientY - lastPointer.y;
      lastPointer = { x: e.clientX, y: e.clientY };
      if (activeButton === 2 || e.shiftKey) {
        /* slide the camera sideways / vertically (translation, not rotation) */
        fly.pos.addScaledVector(rightFrom(fly.yaw), -dx * 0.0042);
        fly.pos.y = clamp(fly.pos.y + dy * 0.0042, ROOM.minY, ROOM.maxY);
        clampPos(fly.pos);
        fly.vel.set(0, 0, 0);
        applyFlyCamera();
        return;
      }
      fly.yaw -= dx * 0.0032;
      fly.pitch = clamp(fly.pitch - dy * 0.0030, -1.45, 1.45);
      applyFlyCamera();
    });
    const up = () => { dragging = false; lastPointer = null; canvas.classList.remove("dragging"); };
    canvas.addEventListener("pointerup", up);
    canvas.addEventListener("pointercancel", up);
    canvas.addEventListener("contextmenu", e => e.preventDefault());
    canvas.addEventListener("wheel", e => {
      if (mode !== "fly") return;
      e.preventDefault();
      targetFov = clamp(targetFov + e.deltaY * 0.025, 30, 80);
    }, { passive: false });
  }

  function initJoystick() {
    const base = $("#joy"), stick = $("#stick");
    if (!base) return;
    const R = 34;
    const set = (dx, dy) => {
      const d = Math.min(R, Math.hypot(dx, dy)), a = Math.atan2(dy, dx);
      const x = Math.cos(a) * d, y = Math.sin(a) * d;
      stick.style.transform = "translate(" + x + "px," + y + "px)";
      joy.x = x / R;
      joy.y = y / R;
      joy.active = true;
    };
    const reset = () => {
      stick.style.transform = "translate(0,0)";
      joy.x = 0;
      joy.y = 0;
      joy.active = false;
    };
    base.addEventListener("pointerdown", e => {
      e.preventDefault();
      e.stopPropagation();
      base.setPointerCapture(e.pointerId);
      const r = base.getBoundingClientRect();
      set(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
    });
    base.addEventListener("pointermove", e => {
      if (!joy.active) return;
      e.preventDefault();
      e.stopPropagation();
      const r = base.getBoundingClientRect();
      set(e.clientX - (r.left + r.width / 2), e.clientY - (r.top + r.height / 2));
    });
    base.addEventListener("pointerup", e => { e.preventDefault(); e.stopPropagation(); reset(); });
    base.addEventListener("pointercancel", reset);

    const lift = $("#lift");
    if (lift) {
      const knob = $("#lift-knob");
      const setLift = v => {
        joy.lift = clamp(v, -1, 1);
        knob.style.transform = "translate(0," + (-joy.lift * 30) + "px)";
      };
      const from = e => {
        const r = lift.getBoundingClientRect();
        setLift(-((e.clientY - (r.top + r.height / 2)) / (r.height / 2)));
      };
      lift.addEventListener("pointerdown", e => {
        e.preventDefault();
        e.stopPropagation();
        lift.setPointerCapture(e.pointerId);
        from(e);
        joy.liftActive = true;
      });
      lift.addEventListener("pointermove", e => {
        if (!joy.liftActive) return;
        e.preventDefault();
        e.stopPropagation();
        from(e);
      });
      const end = e => {
        e.preventDefault();
        e.stopPropagation();
        joy.liftActive = false;
        setLift(0);
      };
      lift.addEventListener("pointerup", end);
      lift.addEventListener("pointercancel", end);
    }
  }

  function timeIcon(id) {
    const s = 'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.35" stroke-linecap="round"';
    if (id === "dawn") return "<svg " + s + '><path d="M3 17h18M7 17a5 5 0 0 1 10 0M12 5v3M5.2 8.2l2.1 2.1M18.8 8.2l-2.1 2.1M2.5 21h19"/></svg>';
    if (id === "morning") return "<svg " + s + '><circle cx="12" cy="12" r="4"/><path d="M12 2.8v2.4M12 18.8v2.4M2.8 12h2.4M18.8 12h2.4M5.4 5.4l1.7 1.7M16.9 16.9l1.7 1.7M18.6 5.4l-1.7 1.7M7.1 16.9l-1.7 1.7"/></svg>';
    if (id === "noon") return "<svg " + s + '><circle cx="12" cy="12" r="3.5"/><path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6L7 7M17 17l1.4 1.4M18.4 5.6L17 7M7 17l-1.4 1.4"/></svg>';
    if (id === "dusk") return "<svg " + s + '><path d="M3 18h18M8 18a4 4 0 0 1 8 0M12 7v3M4.8 10.8l2 2M19.2 10.8l-2 2"/></svg>';
    return "<svg " + s + '><path d="M19.2 14.5A7.8 7.8 0 0 1 9.5 4.8 8 8 0 1 0 19.2 14.5z"/></svg>';
  }

  /* --------------------------------------------------------------- assets */
  function b64ToBuffer(b64) {
    const bin = atob(b64), n = bin.length;
    const arr = new Uint8Array(n);
    for (let i = 0; i < n; i++) arr[i] = bin.charCodeAt(i);
    return arr.buffer;
  }
  function loadTexture(src, srgb) {
    return new Promise((res, rej) => {
      new THREE.TextureLoader().load(src, t => {
        if (srgb !== false) t.encoding = THREE.sRGBEncoding;
        t.flipY = false;
        t.anisotropy = Math.min(8, renderer.capabilities.getMaxAnisotropy());
        res(t);
      }, undefined, rej);
    });
  }

  async function start() {
    try {
      setupScene();
      const A = (typeof window.SITE_ASSETS !== "undefined" && window.SITE_ASSETS) ? window.SITE_ASSETS : null;
      const tex = {};
      const keys = Object.keys(GROUPS);
      let done = 0;
      for (const key of keys) {
        const src = (A && A.textures && A.textures[key]) ? A.textures[key] : "assets/textures/" + GROUPS[key].file;
        try { tex[key] = await loadTexture(src); } catch (e) { console.warn("texture", key, e); }
        done++;
        progress(6 + (done / keys.length) * 62, "正在加载烘焙贴图");
      }
      let artTex = null, tvTex = null;
      try { artTex = await loadTexture(A && A.art ? A.art : "assets/art.png"); } catch (e) { console.warn(e); }
      try {
        tvTex = await loadTexture(A && A.tv ? A.tv : "assets/tv.png");
        tvTex.wrapS = THREE.RepeatWrapping;
        tvTex.repeat.x = -1;
        tvTex.offset.x = 1;
        tvTex.needsUpdate = true;
      } catch (e) { console.warn(e); }

      progress(74, "正在组装房间");
      const loader = new THREE.GLTFLoader();
      const onLoad = g => {
        try {
          buildModel(g.scene, tex, artTex, tvTex);
          if (qs.get("view") && VIEWS.some(v => v.id === qs.get("view"))) goView(qs.get("view"));
          if (qs.get("mode") === "orbit") setMode("orbit");
          progress(100, "进入房间");
          ready = true;
          $("#loading").classList.add("hide");
          requestAnimationFrame(() => { renderer.shadowMap.needsUpdate = true; });
        } catch (e) { fail(e); }
      };
      const onErr = e => fail(e);
      if (A && A.glb) {
        progress(84, "正在解析 3D 网格");
        loader.parse(b64ToBuffer(A.glb), "", onLoad, onErr);
      } else {
        loader.load("assets/scene.glb", onLoad, undefined, onErr);
      }
    } catch (e) { fail(e); }
  }

  function buildModel(root, tex, artTex, tvTex) {
    root.traverse(o => {
      if (!o.isMesh) return;
      o.castShadow = true;
      o.receiveShadow = true;
      const n = o.name.split(".")[0];
      const parent = (o.parent && o.parent.name) || "";
      const hit = Object.keys(tex).find(k => n.startsWith(k) || parent.startsWith(k));
      if (hit) {
        o.material = new THREE.MeshStandardMaterial({
          map: tex[hit],
          roughness: GROUPS[hit] ? GROUPS[hit].rough : 0.7,
          metalness: 0,
          side: THREE.DoubleSide
        });
      }
      if (n.startsWith("City_Far") || parent.startsWith("City_Far")) {
        o.material = new THREE.MeshStandardMaterial({ color: 0x2a3038, roughness: 0.95, metalness: 0, side: THREE.DoubleSide });
        o.castShadow = false;
      }
      if (n.startsWith("Frame_Artwork") || parent.startsWith("Frame_Artwork")) {
        if (artTex) {
          artMaterial = new THREE.MeshStandardMaterial({ map: artTex, roughness: 0.38, metalness: 0, side: THREE.DoubleSide });
          o.material = artMaterial;
        }
      }
      if (n.startsWith("TV_Screen") || parent.startsWith("TV_Screen")) {
        if (tvTex) {
          tvMaterial = new THREE.MeshBasicMaterial({ map: tvTex, toneMapped: false, side: THREE.DoubleSide });
          o.material = tvMaterial;
        }
      }
    });
    scene.add(root);
    applyEnvironment();
    setMode("fly");
    renderer.shadowMap.needsUpdate = true;
    setTimeout(() => { renderer.shadowMap.autoUpdate = false; }, 500);
  }

  /* ----------------------------------------------------------------- loop */
  function loop() {
    requestAnimationFrame(loop);
    if (!renderer || !scene || !camera) return;
    const dt = Math.min(0.05, clock.getDelta());
    if (mode === "fly") updateFly(dt);
    else controls.update();

    if (activeWeather === "storm") {
      flashNext -= dt;
      if (flashNext <= 0) { flash = 9.0; flashNext = 3.0 + Math.random() * 6.0; }
      flash *= 0.82;
      flashLight.intensity = flash;
    } else if (flashLight) {
      flashLight.intensity = 0;
    }
    updateRain(dt);
    renderer.render(scene, camera);
  }

  function readQuery() {
    const t = Object.keys(TIMES).find(k => k === qs.get("time"));
    if (t) activeTime = t;
    const w = Object.keys(WEATHERS).find(k => k === qs.get("weather"));
    if (w) activeWeather = w;
  }

  readQuery();
  start().catch(e => console.error(e));
})();
