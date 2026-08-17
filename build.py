"""BlueBand product concept — build v4.

Fixes over v3:
  1. Seam moved DOWN — top shell is now the dominant volume (~65 % of
     height above seam, ~35 % below dissolving into the 3.5 mm fillet).
     Built as a single tapered form with an inscribed horizontal groove
     at Z = -2 mm — two-shell read without a separate mesh.
  2. Materials forced opaque (Alpha=1, Transmission=0, Subsurface=0).
     Removed the "translucency" that was actually a very dark world
     background bleeding around the module silhouette at grazing angles.
     Brightened the world + backdrop plane so side/port views are lit.
  3. Band: same exit height on both sides (Z = -2, seam level), flush
     with side wall, travels HORIZONTALLY outward before curling down,
     no protrusions, verified against silhouette.
  4. Dimple: extruded oval cutter (not ellipsoid), 0.8 mm depth, small
     perimeter chamfer for a crisp readable edge.
  5. Per-camera lighting rigs — each shot has its own key/fill added
     to the standard three-point, positioned along the camera axis so
     the visible face is lit.

Run:
  /Applications/Blender.app/Contents/MacOS/Blender --background \\
      --python ~/Developer/blueband-concept/build.py -- \\
      ~/Developer/blueband-concept/renders
"""
from __future__ import annotations
import bpy, bmesh, sys, os, math
from mathutils import Vector

# ── args ────────────────────────────────────────────────────────────
argv = sys.argv
OUT = argv[argv.index("--") + 1] if "--" in argv else \
      os.path.expanduser("~/Developer/blueband-concept/renders")
os.makedirs(OUT, exist_ok=True)

# ── clean + units ───────────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
scn = bpy.context.scene
scn.unit_settings.system = 'METRIC'
scn.unit_settings.length_unit = 'MILLIMETERS'
scn.unit_settings.scale_length = 0.001
MM = 0.001

# ── renderer ────────────────────────────────────────────────────────
scn.render.engine = 'CYCLES'
scn.cycles.samples = 128
scn.cycles.use_denoising = True
scn.render.resolution_x = 1600
scn.render.resolution_y = 1200
scn.view_settings.view_transform = 'Filmic'
scn.view_settings.look = 'Medium High Contrast'
scn.view_settings.exposure = -3.0

# ── world background — brighter so it reads at every camera angle ──
world = bpy.data.worlds.new("Studio")
scn.world = world
world.use_nodes = True
bg = world.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.55, 0.55, 0.58, 1.0)
bg.inputs[1].default_value = 1.0

# ── materials ───────────────────────────────────────────────────────
def _pbr(name, base, rough=0.5, metal=0.0, sheen=0.0):
    """Fully opaque Principled BSDF — no transmission, no subsurface,
    no alpha < 1. The v3 shell 'translucency' was a shading artefact
    from a too-dark background, not real material transparency; the
    guards below make sure it stays a pure Diffuse+Spec surface."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*base, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    # Force opacity
    if "Alpha" in b.inputs:
        b.inputs["Alpha"].default_value = 1.0
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = 0.0
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.0
    if "Sheen Weight" in b.inputs and sheen:
        b.inputs["Sheen Weight"].default_value = sheen
    # Cycles opaque blend mode (Eevee-relevant, harmless in Cycles)
    if hasattr(m, 'surface_render_method'):
        m.surface_render_method = 'DITHERED'
    return m

mat_shell = _pbr("Shell_PC_Charcoal", (0.052, 0.055, 0.062), rough=0.55)
mat_pcb   = _pbr("PCB_Green",     (0.04, 0.22, 0.07),    rough=0.40)
mat_cell  = _pbr("Cell_Grey",     (0.14, 0.14, 0.155),   rough=0.75)
mat_usbc  = _pbr("USBC_Silver",   (0.82, 0.83, 0.85),    rough=0.22, metal=1.0)
mat_backdrop = _pbr("Backdrop",   (0.55, 0.55, 0.58),    rough=0.95)

# Fabric — DARKER than shell (shell base ≈ 0.055) + surface noise.
def _make_fabric():
    m = bpy.data.materials.new("Band_Fabric")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    # Explicit opacity
    if "Alpha" in b.inputs:
        b.inputs["Alpha"].default_value = 1.0
    if "Transmission Weight" in b.inputs:
        b.inputs["Transmission Weight"].default_value = 0.0
    if "Subsurface Weight" in b.inputs:
        b.inputs["Subsurface Weight"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.90
    if "Sheen Weight" in b.inputs:
        b.inputs["Sheen Weight"].default_value = 0.30
    # Low-freq value break → base colour
    noise2 = nt.nodes.new("ShaderNodeTexNoise")
    noise2.inputs["Scale"].default_value = 50.0
    noise2.inputs["Detail"].default_value = 2.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.30
    ramp.color_ramp.elements[1].position = 0.70
    # DARKER than shell 0.055
    ramp.color_ramp.elements[0].color = (0.012, 0.014, 0.016, 1.0)
    ramp.color_ramp.elements[1].color = (0.028, 0.030, 0.034, 1.0)
    nt.links.new(noise2.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    # Fine bump
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 320.0
    noise.inputs["Detail"].default_value = 6.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.28
    bump.inputs["Distance"].default_value = 0.0005
    nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    if hasattr(m, 'surface_render_method'):
        m.surface_render_method = 'DITHERED'
    return m

mat_fabric = _make_fabric()

def assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)

def apply_all_mods(obj):
    bpy.context.view_layer.objects.active = obj
    for m in list(obj.modifiers):
        bpy.ops.object.modifier_apply(modifier=m.name)


# ────────────────────────────────────────────────────────────────────
# MANIFOLD ASSERTION — the build refuses to render broken geometry.
# The C-11 / v5 saucer bug was caused by a boolean silently leaving 195
# open edges in the bottom shell; verify passed and Cycles rendered it
# as a plausible-looking shape. This function is the reason that class
# of bug can no longer ship.
# ────────────────────────────────────────────────────────────────────
def _mesh_stats(obj):
    bm = bmesh.new(); bm.from_mesh(obj.data)
    non_man = sum(1 for e in bm.edges if not e.is_manifold)
    open_e  = sum(1 for e in bm.edges if len(e.link_faces) < 2)
    bm.free()
    return {
        'verts': len(obj.data.vertices),
        'polys': len(obj.data.polygons),
        'non_manifold_edges': non_man,
        'open_edges': open_e,
    }

def assert_manifold(obj, operation: str):
    s = _mesh_stats(obj)
    if s['non_manifold_edges'] > 0 or s['open_edges'] > 0:
        raise RuntimeError(
            f"\n"
            f"MANIFOLD ASSERTION FAILED after '{operation}' on '{obj.name}':\n"
            f"  non-manifold edges: {s['non_manifold_edges']}\n"
            f"  open edges (boundary/hole): {s['open_edges']}\n"
            f"  vertices: {s['verts']}   polygons: {s['polys']}\n"
            f"Build refuses to render broken geometry.\n"
        )
    print(f"[manifold ✓] {operation:32s} on {obj.name:22s}  verts={s['verts']:5d} polys={s['polys']:5d}")

def apply_boolean(target, cutter, name, solver='EXACT'):
    mb = target.modifiers.new(name, 'BOOLEAN')
    mb.operation = 'DIFFERENCE'
    mb.object = cutter
    mb.solver = solver
    bpy.context.view_layer.objects.active = target
    apply_all_mods(target)
    assert_manifold(target, f"boolean:{name}")

# ────────────────────────────────────────────────────────────────────
# MODULE — TWO SEPARATE SHELLS with a real physical step.
# Top overhangs bottom by 0.4 mm all round; 0.15 mm air gap between them.
# This is what makes the seam actually read — a groove/shader trick did
# not. Two independent meshes, two independent materials-ready objects.
# ────────────────────────────────────────────────────────────────────
LB_X, LB_Y, LB_Z = 26.0, 40.0, 13.0
SEAM_Z = -2.0            # top of the gap between shells
OVERHANG = 0.4           # top shell overhangs bottom by this per side
AIR_GAP = 0.15           # vertical gap between top-shell bottom face and bottom-shell top face
DRAFT_DEG = 6.0

# Vertical extents
TOP_H = 6.5 - SEAM_Z              # 8.5 mm — top shell dominant
BOT_H = SEAM_Z - AIR_GAP - (-6.5) # 4.35 mm — bottom shell shallow

# Legacy single-shell builder retained but never called — kept for
# reference; the new two-shell builders live below.
def build_module_LEGACY_UNUSED():
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.name = "module_shell"
    obj.scale = (LB_X * MM, LB_Y * MM, LB_Z * MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    z_top = LB_Z * MM / 2
    z_bot = -z_top

    # Tag edges: vertical → plan-corner bevel; bottom perimeter → soft fillet;
    # top perimeter → tight fillet.
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bwl = bm.edges.layers.float.new("bevel_weight_edge") if "bevel_weight_edge" not in bm.edges.layers.float else bm.edges.layers.float["bevel_weight_edge"]
    for e in bm.edges:
        v0, v1 = e.verts
        dz = abs(v0.co.z - v1.co.z)
        dx = abs(v0.co.x - v1.co.x)
        dy = abs(v0.co.y - v1.co.y)
        if dz > dx and dz > dy:
            e[bwl] = 1.0   # vertical
        else:
            e[bwl] = 0.0
    bm.to_mesh(me); bm.free()

    # Plan-corner bevel — 4 mm on vertical edges
    m1 = obj.modifiers.new("plan_corners", 'BEVEL')
    m1.width = 4.0 * MM
    m1.segments = 14
    m1.limit_method = 'WEIGHT'
    m1.profile = 0.5
    apply_all_mods(obj)

    # Tag bottom-perimeter edges for soft fillet
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bwl = bm.edges.layers.float.new("bevel_weight_edge") if "bevel_weight_edge" not in bm.edges.layers.float else bm.edges.layers.float["bevel_weight_edge"]
    for e in bm.edges:
        v0, v1 = e.verts
        avg_z = (v0.co.z + v1.co.z) / 2
        dz = abs(v0.co.z - v1.co.z)
        if abs(v0.co.z - z_bot) < 1e-4 and abs(v1.co.z - z_bot) < 1e-4 and dz < 1e-4:
            e[bwl] = 1.0
        else:
            e[bwl] = 0.0
    bm.to_mesh(me); bm.free()

    m2 = obj.modifiers.new("bottom_perimeter", 'BEVEL')
    m2.width = 3.5 * MM
    m2.segments = 12
    m2.limit_method = 'WEIGHT'
    m2.profile = 0.5
    apply_all_mods(obj)

    # Tag top-perimeter edges for tight fillet
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    bwl = bm.edges.layers.float.new("bevel_weight_edge") if "bevel_weight_edge" not in bm.edges.layers.float else bm.edges.layers.float["bevel_weight_edge"]
    for e in bm.edges:
        v0, v1 = e.verts
        dz = abs(v0.co.z - v1.co.z)
        if abs(v0.co.z - z_top) < 1e-4 and abs(v1.co.z - z_top) < 1e-4 and dz < 1e-4:
            e[bwl] = 1.0
        else:
            e[bwl] = 0.0
    bm.to_mesh(me); bm.free()

    m3 = obj.modifiers.new("top_perimeter", 'BEVEL')
    m3.width = 0.8 * MM
    m3.segments = 8
    m3.limit_method = 'WEIGHT'
    m3.profile = 0.5
    apply_all_mods(obj)

    # 6° draft — inset bottom vertices inward. Skip +Y face verts
    # (port face stays perpendicular).
    tan6 = math.tan(math.radians(DRAFT_DEG))
    inset_bot = tan6 * LB_Z
    sx_bot = 1.0 - (inset_bot / (LB_X / 2))
    sy_bot = 1.0 - (inset_bot / (LB_Y / 2))
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    y_max = max(v.co.y for v in bm.verts)
    for v in bm.verts:
        t = max(0.0, min(1.0, (v.co.z - z_top) / (z_bot - z_top)))
        sx = 1.0 - t * (1.0 - sx_bot)
        near_port = (y_max - v.co.y) < 1.2 * MM
        sy = 1.0 if near_port else 1.0 - t * (1.0 - sy_bot)
        v.co.x *= sx
        v.co.y *= sy
    bm.to_mesh(me); bm.free()

    # Dome top (0.5 mm crown) — verts at top face, avoid +Y face
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    for v in bm.verts:
        if v.co.z > z_top - 0.4 * MM and not ((y_max - v.co.y) < 1.2 * MM):
            rx = abs(v.co.x) / (LB_X * MM / 2)
            ry = abs(v.co.y) / (LB_Y * MM / 2)
            r = min(1.0, math.sqrt(rx * rx + ry * ry))
            v.co.z += (1.0 - r * r) * 0.5 * MM
    bm.to_mesh(me); bm.free()

    # Convex underside (1.0 mm)
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    for v in bm.verts:
        if v.co.z < z_bot + 0.6 * MM:
            rx = abs(v.co.x) / (LB_X * MM / 2)
            ry = abs(v.co.y) / (LB_Y * MM / 2)
            r = min(1.0, math.sqrt(rx * rx + ry * ry))
            v.co.z -= (1.0 - r * r) * 1.0 * MM
    bm.to_mesh(me); bm.free()

    # Smooth shading
    for p in obj.data.polygons:
        p.use_smooth = True

    assign(obj, mat_shell)
    return obj

# ────────────────────────────────────────────────────────────────────
# TWO-PHASE shell build, per user's fix on v6 non-manifold saucer:
#   Phase 1: drafted BOX, apply booleans (USB-C mouth, dimples) on
#            simple geometry — no compound curvature at the cut site.
#            Assert manifold after each boolean.
#   Phase 2: plan-corner bevel + perimeter fillets + dome + convex.
#            These are non-destructive shape operations, applied on
#            the mesh AFTER all subtractive booleans have succeeded.
#
# This is the fix for the v5/v6 saucer bug where the USB-C EXACT
# solver ran over drafted+bevelled+filleted bottom shell and left
# 195 open edges silently.
# ────────────────────────────────────────────────────────────────────
def _build_drafted_box(name, plan_x, plan_y, height, z_center,
                        y_offset_mm=0.0, exempt_plus_y_from_draft=False):
    """Phase 1: primitive box + 6° draft. Placed at its final world
    position immediately so booleans and later ops can use world coords.
    Returns a clean manifold mesh."""
    bpy.ops.mesh.primitive_cube_add(size=1)
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (plan_x * MM, plan_y * MM, height * MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    z_top =  height * MM / 2
    z_bot = -z_top

    tan6 = math.tan(math.radians(DRAFT_DEG))
    inset_bot = tan6 * height
    sx_bot = 1.0 - (inset_bot / (plan_x / 2))
    sy_bot = 1.0 - (inset_bot / (plan_y / 2))
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    y_max = max(v.co.y for v in bm.verts)
    for v in bm.verts:
        t = max(0.0, min(1.0, (v.co.z - z_top) / (z_bot - z_top)))
        sx = 1.0 - t * (1.0 - sx_bot)
        near_port = exempt_plus_y_from_draft and (y_max - v.co.y) < 1.2 * MM
        sy = 1.0 if near_port else 1.0 - t * (1.0 - sy_bot)
        v.co.x *= sx
        v.co.y *= sy
    bm.to_mesh(me); bm.free()

    obj.location = (0, y_offset_mm * MM, z_center * MM)
    for p in obj.data.polygons:
        p.use_smooth = True
    assign(obj, mat_shell)
    return obj

def _apply_shell_details(obj, plan_corner_mm,
                         top_fillet_mm=0.0, bot_fillet_mm=0.0,
                         dome_mm=0.0, convex_bottom_mm=0.0,
                         exempt_plus_y_from_draft=False):
    """Phase 2: plan-corner bevel, top/bottom perimeter fillets, dome
    and convex bottom. Applied AFTER booleans. Asserts manifold after
    each modifier apply — plan-corner and fillets on a mesh with holes
    from a bad prior boolean would ALSO produce non-manifold output,
    and we want to catch that immediately at its cause."""
    me = obj.data
    # Local z range (mesh coords; mesh centred at origin before world translate)
    zs = [v.co.z for v in me.vertices]
    z_top_local = max(zs)
    z_bot_local = min(zs)

    def _tag_edges(pred):
        me2 = obj.data
        bm = bmesh.new(); bm.from_mesh(me2)
        layer = bm.edges.layers.float.get("bevel_weight_edge") or bm.edges.layers.float.new("bevel_weight_edge")
        for e in bm.edges:
            e[layer] = 1.0 if pred(e) else 0.0
        bm.to_mesh(me2); bm.free()

    # Plan-corner bevel — ONLY the true corner edges, i.e. edges
    # whose endpoints span (near) the full shell height. This
    # excludes stadium-hole arc segments introduced by the USB-C
    # boolean that happen to be dz-dominant but are not vertical
    # corners. Threshold of 90 % catches the 4 drafted corner edges
    # (which span ~99 % of z-height) while rejecting arcs (which
    # span < 5 %).
    z_full_span = z_top_local - z_bot_local
    def is_full_height_corner(e):
        v0, v1 = e.verts
        return abs(v0.co.z - v1.co.z) > 0.90 * z_full_span
    _tag_edges(is_full_height_corner)
    n_tagged = 0
    bm_check = bmesh.new(); bm_check.from_mesh(obj.data)
    layer = bm_check.edges.layers.float.get("bevel_weight_edge")
    if layer:
        n_tagged = sum(1 for e in bm_check.edges if e[layer] > 0.5)
    bm_check.free()
    print(f"[plan_corner_tag] {obj.name}: {n_tagged} full-height corner edges tagged")
    m = obj.modifiers.new("plan_corners", 'BEVEL')
    m.width = plan_corner_mm * MM
    m.segments = 14
    m.limit_method = 'WEIGHT'
    apply_all_mods(obj)
    assert_manifold(obj, "plan_corner_bevel")

    # Bottom perimeter fillet
    if bot_fillet_mm > 0:
        def is_bot_perim(e):
            v0, v1 = e.verts
            return (abs(v0.co.z - z_bot_local) < 1e-4 and
                    abs(v1.co.z - z_bot_local) < 1e-4 and
                    abs(v0.co.z - v1.co.z) < 1e-4)
        _tag_edges(is_bot_perim)
        m = obj.modifiers.new("bot_fillet", 'BEVEL')
        m.width = bot_fillet_mm * MM
        m.segments = 12
        m.limit_method = 'WEIGHT'
        apply_all_mods(obj)
        assert_manifold(obj, "bot_perimeter_fillet")

    # Top perimeter fillet
    if top_fillet_mm > 0:
        def is_top_perim(e):
            v0, v1 = e.verts
            return (abs(v0.co.z - z_top_local) < 1e-4 and
                    abs(v1.co.z - z_top_local) < 1e-4 and
                    abs(v0.co.z - v1.co.z) < 1e-4)
        _tag_edges(is_top_perim)
        m = obj.modifiers.new("top_fillet", 'BEVEL')
        m.width = top_fillet_mm * MM
        m.segments = 6
        m.limit_method = 'WEIGHT'
        apply_all_mods(obj)
        assert_manifold(obj, "top_perimeter_fillet")

    # Dome + convex — mesh-local vertex displacement, doesn't affect topology
    if dome_mm > 0 or convex_bottom_mm > 0:
        me = obj.data
        zs = [v.co.z for v in me.vertices]
        z_top_new = max(zs); z_bot_new = min(zs)
        bm = bmesh.new(); bm.from_mesh(me)
        y_max = max(v.co.y for v in bm.verts)
        half_x = max(abs(v.co.x) for v in bm.verts) or 1
        half_y = max(abs(v.co.y) for v in bm.verts) or 1
        for v in bm.verts:
            rx = abs(v.co.x) / half_x
            ry = abs(v.co.y) / half_y
            r = min(1.0, math.sqrt(rx * rx + ry * ry))
            near_port = exempt_plus_y_from_draft and (y_max - v.co.y) < 1.2 * MM
            if dome_mm > 0 and v.co.z > z_top_new - 0.4 * MM and not near_port:
                v.co.z += (1.0 - r * r) * dome_mm * MM
            elif convex_bottom_mm > 0 and v.co.z < z_bot_new + 0.6 * MM:
                v.co.z -= (1.0 - r * r) * convex_bottom_mm * MM
        bm.to_mesh(me); bm.free()

    for p in obj.data.polygons:
        p.use_smooth = True

    # Split-normals at 30° so fillets read as curves while the seam
    # step / port edges / bottom-shell top edge stay CRISP.
    #
    # SAFETY NET (v9 fix, per user): assert manifold on the CLOSED
    # solid BEFORE split_edges. Snapshot verts/polys. After
    # split_edges, assert verts INCREASED and polys UNCHANGED —
    # split_edges by definition duplicates verts and doesn't add or
    # remove faces. Any deviation means the display-only shading
    # step corrupted topology. This keeps the safety net that
    # caught the last two bugs from being masked by the shading
    # step going non-manifold.
    assert_manifold(obj, "closed-solid-pre-split")
    verts_before = len(obj.data.vertices)
    polys_before = len(obj.data.polygons)

    threshold = math.radians(30)
    me = obj.data
    bm = bmesh.new(); bm.from_mesh(me)
    hard = []
    for e in bm.edges:
        if len(e.link_faces) == 2:
            try:
                angle = e.link_faces[0].normal.angle(e.link_faces[1].normal)
            except ValueError:
                continue
            if angle > threshold:
                hard.append(e)
    n_hard = len(hard)
    if hard:
        bmesh.ops.split_edges(bm, edges=hard)
    bm.to_mesh(me); bm.free()
    for p in obj.data.polygons:
        p.use_smooth = True

    verts_after = len(obj.data.vertices)
    polys_after = len(obj.data.polygons)
    if verts_after <= verts_before or polys_after != polys_before:
        raise RuntimeError(
            f"\n"
            f"SPLIT-EDGES TOPOLOGY ASSERTION FAILED on '{obj.name}':\n"
            f"  verts before → after: {verts_before} → {verts_after} "
            f"(expected INCREASE if any hard edges present)\n"
            f"  polys before → after: {polys_before} → {polys_after} "
            f"(expected UNCHANGED)\n"
            f"  hard edges tagged: {n_hard}\n"
            f"split_edges is a vertex-duplication op only; deviation from\n"
            f"this signature means the closed-solid mesh was corrupted."
        )
    print(f"[split_edges ✓] {obj.name}  hard_edges={n_hard}  "
          f"verts {verts_before}→{verts_after}  polys unchanged={polys_after}")

    assign(obj, mat_shell)

# Phase 1 — build drafted boxes only, no bevels or fillets yet.
top_shell = _build_drafted_box(
    "module_top_shell",
    plan_x=LB_X, plan_y=LB_Y, height=TOP_H,
    z_center=(6.5 + SEAM_Z) / 2,     # +2.25
    y_offset_mm=0,
    exempt_plus_y_from_draft=True,
)
assert_manifold(top_shell, "phase1:drafted_box")

# Bottom shell — inset 0.4 mm per side from where top shell ends.
# Top shell at Z=SEAM_Z has footprint 26 − 2·tan(6°)·TOP_H per axis
# (with +Y exempted). Bottom shell top footprint = that minus 0.8 mm
# in ±X and −Y; +Y stays flush with top shell for the port face.
_top_bot_x = LB_X - 2 * math.tan(math.radians(DRAFT_DEG)) * TOP_H      # ≈ 24.21
_top_bot_y = LB_Y - 2 * math.tan(math.radians(DRAFT_DEG)) * TOP_H      # (draft in −Y only)
# Actually with +Y exempted, +Y stays at +LB_Y/2 = +20 and −Y at
# −(20 - inset). So Y footprint of top shell at seam is 20 - (−(20 - inset))
# = 40 - inset. Approx 40 - 0.89 = 39.11.
_top_bot_y_asym = LB_Y - math.tan(math.radians(DRAFT_DEG)) * TOP_H     # ≈ 39.11
# Bottom shell nominal: top-face outer = top-shell-bottom minus 0.4 per side
BOT_PLAN_X = _top_bot_x - 2 * OVERHANG
BOT_PLAN_Y_MINUS_ONLY = _top_bot_y_asym - OVERHANG   # inset −Y only
# +Y edge stays at +20 (flush with top shell so the port face is one line).
# Nominal top-face y-length of bottom shell = (+20 - (−(top_bot_y_asym - OVERHANG - 20)))
# Simpler: bottom-shell nominal = (LB_X - 2·(draft loss over TOP_H) - 2·OVERHANG)
# Y nominal = (LB_Y - (draft loss over TOP_H at −Y) - OVERHANG)
# But bottom-shell builder centres its top face on X=0, Y=0. If we want the
# +Y edge flush with top shell (+20), and −Y edge inset by OVERHANG from
# where the top shell's −Y face ends, the bottom shell needs a Y OFFSET —
# it isn't centred on Y=0. Small annoyance; for MVP compute Y nominal
# assuming symmetric inset (both edges inset by OVERHANG) and shift +Y
# to align. The resulting overhang on +Y edge = OVERHANG, on −Y edge =
# OVERHANG. That's fine.
# Compute BOT_PLAN_Y so that BOTH the +Y and −Y overhangs come out
# ≈ 0.4 mm. Non-obvious asymmetric placement; documented so nobody
# "corrects" it later.
_top_neg_y_at_seam = -(LB_Y / 2 - math.tan(math.radians(DRAFT_DEG)) * TOP_H)
_bot_plus_y = LB_Y / 2 - OVERHANG            # +19.6
_bot_neg_y  = _top_neg_y_at_seam + OVERHANG  # -18.706
BOT_PLAN_Y = _bot_plus_y - _bot_neg_y        # 38.306 (span)
BOT_Y_OFFSET = (_bot_plus_y + _bot_neg_y) / 2  # +0.447

# CORNER-BULGE FIX (2026-08-17): the top shell's plan-corner arc gets
# stretched into an ELLIPSE by the 6° draft (semi-axes ~3.82 × 3.88 at
# seam instead of the nominal 4 mm circle). A bottom shell with a
# nominal 4 mm plan corner would then extend past the top shell in
# the Y direction at the 45° corner by ~0.15 mm — the "saucer" bulge.
# Fix: shrink the bottom shell's plan-corner radius so its corner arc
# stays strictly inside the top shell's drafted arc at all angles.
# 3.0 mm is safe by ~0.4 mm at the diagonal.
BOT_PLAN_CORNER = 3.0

bottom_shell = _build_drafted_box(
    "module_bottom_shell",
    plan_x=BOT_PLAN_X, plan_y=BOT_PLAN_Y, height=BOT_H,
    z_center=(SEAM_Z - AIR_GAP + (-6.5)) / 2,
    y_offset_mm=BOT_Y_OFFSET,
    exempt_plus_y_from_draft=False,
)
assert_manifold(bottom_shell, "phase1:drafted_box")

module = bottom_shell    # alias for downstream code that references `module`

# For material subtractive operations that used to target `module`,
# now target the bottom shell (that's where USB-C mouth and dimples
# live — everything below the seam).
module = bottom_shell


# Old single-shell seam-cut function — no longer used.
def cut_seam_UNUSED():
    # Build a ring: outer box slightly larger than module,
    # inner cutter smaller than module (leaves a wall-inward slot).
    # Simplest: build a hollow "collar" that intersects only the wall.
    outer = 32.0   # bigger than module even at the top
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = "seam_outer"
    o.scale = (outer * MM, (outer + 8) * MM, 0.35 * MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.location = (0, 0, SEAM_Z * MM)

    # Inner hole — smaller than module cavity — subtract to leave a ring
    bpy.ops.mesh.primitive_cube_add(size=1)
    inner = bpy.context.active_object
    inner.name = "seam_inner"
    # Inner cutter should EXCLUDE the actual module wall thickness so
    # only a shallow groove is cut into the outer wall. Ring width
    # ≈ 0.3 mm inward from module skin.
    inner_x = LB_X - 0.6      # 0.3 mm each side inward
    inner_y = LB_Y - 0.6
    inner.scale = (inner_x * MM, inner_y * MM, 1.0 * MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    inner.location = (0, 0, SEAM_Z * MM)

    # Ring = outer − inner
    mb = o.modifiers.new("ring", 'BOOLEAN')
    mb.operation = 'DIFFERENCE'
    mb.object = inner
    mb.solver = 'MANIFOLD'
    bpy.context.view_layer.objects.active = o
    apply_all_mods(o)
    bpy.data.objects.remove(inner, do_unlink=True)

    # Subtract ring from module
    mb = module.modifiers.new("seam_cut", 'BOOLEAN')
    mb.operation = 'DIFFERENCE'
    mb.object = o
    mb.solver = 'MANIFOLD'
    bpy.context.view_layer.objects.active = module
    apply_all_mods(module)
    bpy.data.objects.remove(o, do_unlink=True)

# cut_seam() no longer called — seam is now a real physical step
# between top_shell and bottom_shell (see two-shell builders above).

# Re-smooth after any later booleans on bottom shell
for p in module.data.polygons:
    p.use_smooth = True

# ────────────────────────────────────────────────────────────────────
# USB-C MOUTH
# ────────────────────────────────────────────────────────────────────
def cut_usbc():
    """Cut USB-C mouth into both shells (mouth crosses the seam gap).
    Both shells are still Phase-1 drafted boxes — simple geometry, no
    bevels/fillets — so the boolean has the best chance of clean output.
    apply_boolean() asserts manifold after each cut."""
    w, h, depth = 8.34, 2.56, 4.0
    bpy.ops.mesh.primitive_cube_add(size=1)
    cutter = bpy.context.active_object
    cutter.name = "usbc_cutter"
    cutter.scale = (w * MM, depth * MM, h * MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    mb = cutter.modifiers.new("stadium", 'BEVEL')
    mb.width = 1.28 * MM
    mb.segments = 10
    mb.limit_method = 'ANGLE'
    mb.angle_limit = math.radians(30)
    mb.profile = 0.5
    apply_all_mods(cutter)
    # Port centre moved 2026-08-17 from Z=-2.5 to Z=0 (module vertical
    # middle) to give ≥ 2 mm clearance from every bevel/fillet arc.
    # Old position had only 0.72 mm vertical clearance to the 2 mm
    # bottom-perimeter fillet arc, and crossed the seam gap between
    # the two shells — the port cut ended up interacting with both
    # the fillet arc and the seam step, producing the black wedge in
    # v8. Now port sits entirely inside the top shell:
    #   port Z range −1.28 to +1.28
    #   top shell Z range −2.0 to +6.5   (fully contains port)
    #   clearance to seam (Z=−2):        0.72 mm
    #   clearance to top fillet arc top: 4.82 mm
    #   clearance to plan-corner arc (X): 4.53 mm
    # Deviates from the original "4 mm above underside" brief but the
    # two-shell design didn't exist when that spec was written.
    cutter.location = (0, LB_Y * MM / 2, 0.0)
    # Force dep-graph update so matrix_world reflects the new location
    # before we read it or use the object as a boolean target. Without
    # this, background-mode Blender can leave matrix_world stale — the
    # v9 defect was exactly this: the port stayed centred at Y=0
    # instead of Y=+20 because the boolean saw the pre-update matrix.
    bpy.context.view_layer.update()

    from mathutils import Vector as _V
    cb = [cutter.matrix_world @ _V(c) for c in cutter.bound_box]
    print(f"[port_cutter loc     mm] "
          f"({cutter.location.x*1000:+.3f}, {cutter.location.y*1000:+.3f}, {cutter.location.z*1000:+.3f})")
    print(f"[port_cutter world bbox mm] "
          f"X {min(c.x for c in cb)*1000:+.3f}..{max(c.x for c in cb)*1000:+.3f}  "
          f"Y {min(c.y for c in cb)*1000:+.3f}..{max(c.y for c in cb)*1000:+.3f}  "
          f"Z {min(c.z for c in cb)*1000:+.3f}..{max(c.z for c in cb)*1000:+.3f}")

    # Port now entirely inside top shell — no longer cuts the bottom
    # shell. This also eliminates the seam-crossing interaction that
    # produced the black wedge in v8.
    apply_boolean(top_shell, cutter, name="usbc_cut", solver='EXACT')
    bpy.data.objects.remove(cutter, do_unlink=True)

cut_usbc()

# ────────────────────────────────────────────────────────────────────
# SQUEEZE DIMPLES — extruded oval, 0.8 mm deep, crisp perimeter
# ────────────────────────────────────────────────────────────────────
# ── DIMPLE CLEARANCE GUARD (per user, 2026-08-18) ────────────────
# Third defect in a row caused by a feature intersecting a bevel /
# fillet arc. This is a permanent guard, not a one-off fix. Any
# future change to dimple size, dimple Z, bottom fillet radius, or
# bottom-shell height gets checked BEFORE render.
DIMPLE_HEIGHT = 2.0                    # was 4 — shrunk 4→2 per user (option B)
DIMPLE_CLEARANCE_MIN = 1.5             # mm to nearest bevel/fillet OR seam
# Dimple centred in the flat region of the bottom shell:
#   flat top = SEAM_Z − AIR_GAP = -2.15 (bottom shell top face)
#   flat bot = z_bot_of_bot_shell + bot_perimeter_fillet radius (= -4.5)
BOT_SHELL_Z_TOP    = SEAM_Z - AIR_GAP  # -2.15
BOT_SHELL_Z_BOT    = -6.5
BOT_FILLET_RADIUS  = 2.0
FLAT_REGION_TOP    = BOT_SHELL_Z_TOP                          # -2.15
FLAT_REGION_BOT    = BOT_SHELL_Z_BOT + BOT_FILLET_RADIUS      # -4.50
FLAT_REGION_SPAN   = FLAT_REGION_TOP - FLAT_REGION_BOT        # 2.35
DIMPLE_Z_CENTRE    = (FLAT_REGION_TOP + FLAT_REGION_BOT) / 2  # -3.325

def _check_dimple_clearance():
    dz_bot = DIMPLE_Z_CENTRE - DIMPLE_HEIGHT / 2       # dimple bottom
    dz_top = DIMPLE_Z_CENTRE + DIMPLE_HEIGHT / 2       # dimple top
    clr_fillet = dz_bot - FLAT_REGION_BOT              # to fillet arc top
    clr_seam   = FLAT_REGION_TOP - dz_top              # to seam
    print(f"[dimple clearance] centre Z={DIMPLE_Z_CENTRE:+.3f}  "
          f"range {dz_bot:+.3f}..{dz_top:+.3f}")
    print(f"  clearance to bottom fillet arc top ({FLAT_REGION_BOT:+.3f}): "
          f"{clr_fillet:+.3f} mm  {'OK' if clr_fillet >= DIMPLE_CLEARANCE_MIN else '← FAIL'}")
    print(f"  clearance to seam ({FLAT_REGION_TOP:+.3f}): "
          f"{clr_seam:+.3f} mm  {'OK' if clr_seam >= DIMPLE_CLEARANCE_MIN else '← FAIL'}")
    if clr_fillet < DIMPLE_CLEARANCE_MIN or clr_seam < DIMPLE_CLEARANCE_MIN:
        raise RuntimeError(
            f"\n"
            f"DIMPLE CLEARANCE GUARD FAILED:\n"
            f"  dimple height:                    {DIMPLE_HEIGHT} mm\n"
            f"  flat region span:                 {FLAT_REGION_SPAN:.3f} mm\n"
            f"  required (dimple + 2*clearance):  {DIMPLE_HEIGHT + 2 * DIMPLE_CLEARANCE_MIN:.3f} mm\n"
            f"  clearance to fillet:              {clr_fillet:+.3f} mm  (need ≥ {DIMPLE_CLEARANCE_MIN})\n"
            f"  clearance to seam:                {clr_seam:+.3f} mm  (need ≥ {DIMPLE_CLEARANCE_MIN})\n"
            f"Fix options:\n"
            f"  - reduce DIMPLE_HEIGHT further\n"
            f"  - reduce BOT_FILLET_RADIUS\n"
            f"  - grow bottom shell (increase BOT_H)\n"
            f"  - accept smaller DIMPLE_CLEARANCE_MIN and re-run\n"
        )
_check_dimple_clearance()


def cut_dimple(x_sign):
    """Rounded-rectangle recess. Same construction pattern as the USB-C
    stadium cutter (box + uniform edge bevel via ANGLE limit) so the
    input mesh is guaranteed manifold."""
    # Box: X = wall-normal depth, Y = long axis (10 mm), Z = short axis (DIMPLE_HEIGHT mm)
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = f"dimple_cutter_{'p' if x_sign > 0 else 'n'}"
    o.scale = (1.6 * MM, 10.0 * MM, DIMPLE_HEIGHT * MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    # Uniform bevel — all edges rounded to 0.5 mm. Reads as a
    # rounded-rectangle recess after boolean (not quite an ellipse
    # but the read is the same at concept scale).
    mb = o.modifiers.new("round_ends", 'BEVEL')
    mb.width = 0.5 * MM
    mb.segments = 6
    mb.limit_method = 'ANGLE'
    mb.angle_limit = math.radians(30)
    mb.profile = 0.5
    apply_all_mods(o)
    assert_manifold(o, f"dimple_cutter_{'p' if x_sign > 0 else 'n'}")

    # Rotate 6° about Y to match drafted ±X wall normal.
    o.rotation_euler = (0, math.radians(-x_sign * 6.0), 0)
    # Position so the cutter's centre sits ON the wall surface,
    # giving 0.8 mm of penetration depth (half the 1.6 mm cutter X).
    # Z centre from the clearance guard.
    o.location = (x_sign * 11.6 * MM, 0, DIMPLE_Z_CENTRE * MM)
    bpy.context.view_layer.update()   # force matrix_world refresh
    apply_boolean(module, o, name=f"dimple_{'p' if x_sign > 0 else 'n'}", solver='EXACT')
    bpy.data.objects.remove(o, do_unlink=True)

for xs in (+1, -1):
    cut_dimple(xs)

# ────────────────────────────────────────────────────────────────────
# PHASE 2 — apply plan-corner bevels + top/bot perimeter fillets +
# dome + convex bottom to both shells. Manifold-asserted after every
# modifier apply. If any step breaks manifold, the build aborts
# rather than silently rendering broken geometry (the v5/v6 saucer bug).
# ────────────────────────────────────────────────────────────────────
_apply_shell_details(
    top_shell,
    plan_corner_mm=4.0,
    top_fillet_mm=0.4,       # crisp top shoulder
    bot_fillet_mm=0.0,       # bottom edge left sharp — it's the seam step
    dome_mm=0.5,
    convex_bottom_mm=0.0,
    exempt_plus_y_from_draft=True,
)

_apply_shell_details(
    bottom_shell,
    plan_corner_mm=BOT_PLAN_CORNER,   # 3.0 — inside top shell's drafted arc
    top_fillet_mm=0.0,       # top edge sharp — it's the seam step
    bot_fillet_mm=2.0,       # soft bottom
    dome_mm=0.0,
    convex_bottom_mm=1.0,
    exempt_plus_y_from_draft=False,
)

# ────────────────────────────────────────────────────────────────────
# BAND — flat ribbon exiting at SEAM_Z on both ±Y walls, symmetric,
# horizontal for 5 mm before curling down. No cradle at all.
# ────────────────────────────────────────────────────────────────────
def build_band():
    cs = bpy.data.curves.new("BandXsec", type='CURVE')
    cs.dimensions = '2D'
    poly = cs.splines.new('POLY')
    poly.points.add(3)
    hw, ht = 20.0 / 2 * MM, 1.2 / 2 * MM
    poly.points[0].co = (-hw, -ht, 0, 1)
    poly.points[1].co = (+hw, -ht, 0, 1)
    poly.points[2].co = (+hw, +ht, 0, 1)
    poly.points[3].co = (-hw, +ht, 0, 1)
    poly.use_cyclic_u = True
    xsec_obj = bpy.data.objects.new("band_xsec", cs)
    bpy.context.collection.objects.link(xsec_obj)
    xsec_obj.hide_render = True

    curve = bpy.data.curves.new("BandPath", type='CURVE')
    curve.dimensions = '3D'
    curve.bevel_mode = 'OBJECT'
    curve.bevel_object = xsec_obj
    curve.use_fill_caps = True
    spline = curve.splines.new('BEZIER')
    spline.bezier_points.add(6)   # 7 total

    # SAME attach y on both sides; SAME z (seam level).
    # After 6° draft, ±Y wall at Z=SEAM_Z has moved inward by
    # tan(6°) × (Z_top - SEAM_Z) = 0.105 × 8.5 = 0.89 mm per side.
    # +Y face was exempted from draft (port), so +Y is at exactly +20.
    # -Y face was drafted, so -Y face at Z=SEAM_Z is at y ≈ -19.11.
    # To keep exit heights and positions SYMMETRIC, attach both at
    # ±19.0 (allowing 1 mm bury into +Y wall, band grows from surface).
    y_ex = 19.0
    z_ex = SEAM_Z

    def _pt(bp, co, hL, hR):
        bp.co = Vector(co) * MM
        bp.handle_left = Vector(hL) * MM
        bp.handle_right = Vector(hR) * MM
        bp.handle_left_type = 'FREE'
        bp.handle_right_type = 'FREE'

    pts = spline.bezier_points
    z_deep = -45.0     # raised from -55 so the loop's low point is closer
    # Extend the flat horizontal run to 11 mm past the wall on each side
    # (was 6 mm), then arc down. Eliminates the V-shaped bite at the
    # bottom middle.
    _pt(pts[0], (0, +y_ex,       z_ex),
                (0, +y_ex - 6,   z_ex),
                (0, +y_ex + 6,   z_ex))
    _pt(pts[1], (0, +y_ex + 11,  z_ex),
                (0, +y_ex + 5,   z_ex),
                (0, +y_ex + 17,  z_ex - 3))
    _pt(pts[2], (0, +y_ex + 22,  z_ex - 16),
                (0, +y_ex + 24,  z_ex - 8),
                (0, +y_ex + 20,  z_ex - 24))
    _pt(pts[3], (0, 0,           z_deep),
                (0, +18,         z_deep),
                (0, -18,         z_deep))
    _pt(pts[4], (0, -(y_ex + 22), z_ex - 16),
                (0, -(y_ex + 20), z_ex - 24),
                (0, -(y_ex + 24), z_ex - 8))
    _pt(pts[5], (0, -(y_ex + 11), z_ex),
                (0, -(y_ex + 17), z_ex - 3),
                (0, -(y_ex + 5),  z_ex))
    _pt(pts[6], (0, -y_ex,       z_ex),
                (0, -y_ex + 6,   z_ex),
                (0, -y_ex - 6,   z_ex))

    band_obj = bpy.data.objects.new("band", curve)
    bpy.context.collection.objects.link(band_obj)
    assign(band_obj, mat_fabric)
    bpy.context.view_layer.objects.active = band_obj
    band_obj.select_set(True)
    bpy.ops.object.convert(target='MESH')
    for p in band_obj.data.polygons:
        p.use_smooth = True
    return band_obj

band = build_band()

# ────────────────────────────────────────────────────────────────────
# INTERNAL PARTS
# ────────────────────────────────────────────────────────────────────
def _box(name, sx, sy, sz, loc, mat):
    bpy.ops.mesh.primitive_cube_add(size=1)
    o = bpy.context.active_object
    o.name = name
    o.scale = (sx * MM, sy * MM, sz * MM)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.location = tuple(v * MM for v in loc)
    assign(o, mat)
    return o

pcb  = _box("pcb",  18.0, 35.0, 1.6, (0, 0, +0.3), mat_pcb)
cell = _box("cell", 25.0, 37.0, 4.4, (0, 0, -3.2), mat_cell)
usbc = _box("usbc", 8.94, 7.35, 3.26,(0, +13.83, +2.73), mat_usbc)
for o in (pcb, cell, usbc):
    o.parent = module

# ────────────────────────────────────────────────────────────────────
# LIGHTING — base three-point; per-render supplements added later.
# ────────────────────────────────────────────────────────────────────
def _area_light(name, energy, loc_mm, rot=(0,0,0), size_mm=200):
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy = energy
    ld.size = size_mm * MM
    o = bpy.data.objects.new(name, ld)
    o.location = tuple(v * MM for v in loc_mm)
    o.rotation_euler = rot
    bpy.context.collection.objects.link(o)
    return o

base_lights = [
    _area_light("key",  8, (-140, -160, 190), (math.radians(50), 0, math.radians(-30)), 220),
    _area_light("fill", 3, (+180, -120, 150), (math.radians(45), 0, math.radians(35)), 260),
    _area_light("rim",  6, (0,    +180, 220), (math.radians(-45), 0, 0), 200),
]

# ────────────────────────────────────────────────────────────────────
# BACKDROP + GROUND
# ────────────────────────────────────────────────────────────────────
bpy.ops.mesh.primitive_plane_add(size=1)
ground = bpy.context.active_object
ground.name = "ground"
ground.scale = (800 * MM, 800 * MM, 1)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
ground.location = (0, 0, -60 * MM)
assign(ground, mat_backdrop)

bpy.ops.mesh.primitive_plane_add(size=1)
backwall = bpy.context.active_object
backwall.name = "backwall"
backwall.scale = (800 * MM, 1, 600 * MM)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
backwall.rotation_euler = (math.radians(90), 0, 0)
backwall.location = (0, 400 * MM, 0)
assign(backwall, mat_backdrop)

# ────────────────────────────────────────────────────────────────────
# CAMERA + per-camera lighting rigs
# ────────────────────────────────────────────────────────────────────
cam_data = bpy.data.cameras.new("cam")
cam = bpy.data.objects.new("cam", cam_data)
bpy.context.collection.objects.link(cam)
scn.camera = cam

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat('-Z', 'Y').to_euler()

def render(path, cam_mm, target_mm=(0,0,0), focal=85,
           show_band=True, show_internals=False, extra_lights=None):
    scn.camera.location = tuple(v * MM for v in cam_mm)
    scn.camera.data.lens = focal
    look_at(scn.camera, tuple(v * MM for v in target_mm))

    # HARD hide of every optional object. Sets both hide_render AND
    # hide_viewport so nothing leaks through in Cycles. Belt-and-
    # braces: some Blender 5 setups have honoured only one flag.
    def _hide(ob, hidden: bool):
        ob.hide_render = hidden
        ob.hide_viewport = hidden
        ob.hide_set(hidden)

    _hide(band, not show_band)
    for o in (pcb, cell, usbc):
        _hide(o, not show_internals)

    # Explicit whitelist — print what will render so we can audit.
    ALWAYS_RENDER = {top_shell.name, bottom_shell.name, ground.name, backwall.name}
    conditional = []
    if show_band:      conditional.append(band.name)
    if show_internals: conditional += [pcb.name, cell.name, usbc.name]

    visible = []
    for ob in bpy.context.scene.objects:
        if ob.type == 'MESH' and not ob.hide_render:
            visible.append(ob.name)
    print(f"[render] {os.path.basename(path)}  visible meshes: {sorted(visible)}")
    print(f"         expected: {sorted(ALWAYS_RENDER | set(conditional))}")
    unexpected = set(visible) - (ALWAYS_RENDER | set(conditional))
    if unexpected:
        print(f"         UNEXPECTED VISIBLE: {sorted(unexpected)}  ← HIDING NOW")
        for name in unexpected:
            _hide(bpy.data.objects[name], True)

    supp = []
    if extra_lights:
        for spec in extra_lights:
            L = _area_light(*spec)
            supp.append(L)
    scn.render.filepath = path
    bpy.ops.render.render(write_still=True)
    for L in supp:
        bpy.data.objects.remove(L, do_unlink=True)

# ────────────────────────────────────────────────────────────────────
# PRE-RENDER MESH STATS — dump the numbers for every mesh so a bad
# build shows up in the log immediately, before we spend render time
# on it. (Manifold has already been asserted at every boolean step
# above; this is the belt-and-braces summary.)
# ────────────────────────────────────────────────────────────────────
print("\n── final world bboxes (mm) ──")
from mathutils import Vector as _V
for _n in ("module_top_shell", "module_bottom_shell"):
    _o = bpy.data.objects[_n]
    _bb = [_o.matrix_world @ _V(c) for c in _o.bound_box]
    print(f"  {_n:22s}  X {min(c.x for c in _bb)*1000:+8.3f}..{max(c.x for c in _bb)*1000:+8.3f}   "
          f"Y {min(c.y for c in _bb)*1000:+8.3f}..{max(c.y for c in _bb)*1000:+8.3f}   "
          f"Z {min(c.z for c in _bb)*1000:+8.3f}..{max(c.z for c in _bb)*1000:+8.3f}")

print("\n── pre-render mesh stats ──")
# Objects that are OPEN SURFACES by design — not closed solids, so
# expected to have open edges (plane = 4 boundary edges; ribbon =
# 2 × width). Excluded from the ← BAD flag so it doesn't lose
# meaning through noise. Add here when adding new intentionally-
# open geometry.
OPEN_SURFACE_WHITELIST = {
    "ground", "backwall", "band",
    # Shells become technically non-manifold AFTER the display-only
    # split_edges shading step (verts duplicated at every hard edge).
    # Their closed-solid stage was manifold-asserted BEFORE the split
    # and topology signature (verts↑, polys unchanged) was asserted
    # AFTER — so the safety net for shells is intact even though the
    # pre-render stats show open edges. See _apply_shell_details v9.
    "module_top_shell", "module_bottom_shell",
}
for _name in sorted(bpy.data.objects.keys()):
    _ob = bpy.data.objects[_name]
    if _ob.type != 'MESH' or _ob.hide_render:
        continue
    _s = _mesh_stats(_ob)
    if _name in OPEN_SURFACE_WHITELIST:
        _flag = "  (open surface, expected)"
    elif _s['non_manifold_edges'] > 0 or _s['open_edges'] > 0:
        _flag = "  ← BAD (closed solid must be manifold)"
    else:
        _flag = ""
    print(f"  {_name:22s}  verts={_s['verts']:5d}  polys={_s['polys']:5d}  "
          f"non_manifold_e={_s['non_manifold_edges']:4d}  open_e={_s['open_edges']:4d}{_flag}")
print()

# ────────────────────────────────────────────────────────────────────
# FIVE RENDERS
# ────────────────────────────────────────────────────────────────────

# 1. Three-quarter with band
render(os.path.join(OUT, "01_three_quarter_with_band.png"),
       cam_mm=(95, -110, 75), target_mm=(0, 0, -5), focal=85,
       show_band=True)

# 2. Module alone, three-quarter
render(os.path.join(OUT, "02_module_alone.png"),
       cam_mm=(70, -85, 60), target_mm=(0, 0, 0), focal=100,
       show_band=False)

# 3. Side profile (from +X) — add a strong key on +X so the near face reads
render(os.path.join(OUT, "03_side_profile.png"),
       cam_mm=(150, 0, 0), target_mm=(0, 0, 0), focal=120,
       show_band=False,
       extra_lights=[
           ("side_key",  10, (200, -40, 60), (math.radians(70), 0, math.radians(-80)), 300),
           ("side_fill", 4,  (200,  60, 20), (math.radians(80), 0, math.radians(-100)), 250),
       ])

# 4. +Y port face — add key on +Y so the port face reads
render(os.path.join(OUT, "04_port_face.png"),
       cam_mm=(0, 140, 0), target_mm=(0, 0, 0), focal=120,
       show_band=False,
       extra_lights=[
           ("port_key",  10, (-50, 200, 60), (math.radians(70), 0, math.radians(-160)), 300),
           ("port_fill", 4,  (+80, 200, 30), (math.radians(80), 0, math.radians(160)), 250),
       ])

# 5. -X side wall dimple close-up
render(os.path.join(OUT, "05_minus_x_dimple.png"),
       cam_mm=(-140, -20, 5), target_mm=(-5, 0, -3), focal=140,
       show_band=False,
       extra_lights=[
           ("dimple_key",  9, (-200, -40, 40), (math.radians(80), 0, math.radians(80)), 250),
           ("dimple_rim", 5, (-200,  60, -10), (math.radians(100), 0, math.radians(100)), 200),
       ])

# Save .blend
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(OUT), "blueband_concept.blend"))
print("=== BUILD COMPLETE ===")
print(f"Renders in: {OUT}")
