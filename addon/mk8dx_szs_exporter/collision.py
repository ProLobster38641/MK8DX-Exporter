"""Collision (KCL) side: per-object/per-face collision types, viewport tool, course_kcl.szs export."""
import os
import shutil
import tempfile
import time

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from . import cli, coltypes, files, collision_preview

FACE_ATTR = "mk8dx_col"          # INT, FACE domain; -1 = use the object's type
COLOR_ATTR = "MK8DX_Collision"   # BYTE_COLOR, FACE domain; display only, never exported to the model


# ---------------------------------------------------------------- properties
def _type_items(self, context):
    return [(str(t[0]), f"{t[0]:02X}  {t[1]}", t[2]) for t in coltypes.TYPES]


def _variant_items(self, context):
    t = coltypes.TYPE_BY_ID.get(int(self.col_type or 0))
    names = t[3] if t and t[3] else []
    return [(str(i), f"{i}  {names[i]}" if i < len(names) else str(i), "") for i in range(8)]


def _preset_update(self, context):
    if self.preset == "CUSTOM":
        return
    v = next(h for k, _, h in coltypes.PRESETS if k == self.preset)
    self.use_custom = False
    self.col_type = str(v & 0x1F)
    self.col_variant = str((v >> 5) & 7)
    self.flag_trick, self.flag_trick2, self.flag_grav, self.flag_grav2 = [bool(v & b) for b, _ in coltypes.FLAGS]


class MK8DX_CollisionToolSettings(bpy.types.PropertyGroup):
    preset: EnumProperty(name="Collision type", update=_preset_update,
                         items=[("CUSTOM", "Custom collision (set type + flags)", "Use the type/variant/flags fields")] +
                               [(k, f"{l}  [{h:04X}]", coltypes.describe(h)) for k, l, h in coltypes.PRESETS], default="ROAD")
    col_type: EnumProperty(name="Type", items=_type_items)
    col_variant: EnumProperty(name="Variant (sound/effects)", items=_variant_items)
    flag_trick: BoolProperty(name="Trickable")
    flag_trick2: BoolProperty(name="Trickable (extra)")
    flag_grav: BoolProperty(name="High gravity")
    flag_grav2: BoolProperty(name="High gravity 2")
    use_custom: BoolProperty(name="Custom hex", description="Type the 16-bit KCL flag directly (e.g. 8086)")
    custom_hex: StringProperty(name="Hex", default="0000")
    role: EnumProperty(name="Object becomes", default="COLLISION", items=[
        ("COLLISION", "Collision only", "Not exported to course_model.szs, only to course_kcl.szs"),
        ("BOTH", "Visual + collision", "Exported to both files")])

    def value(self):
        if self.use_custom:
            try:
                return int(self.custom_hex.strip().lower().replace("0x", "").replace("col_", "") or "0", 16) & 0xFFFF
            except ValueError:
                return None
        v = int(self.col_type or 0) | (int(self.col_variant or 0) << 5)
        for (b, _), on in zip(coltypes.FLAGS, (self.flag_trick, self.flag_trick2, self.flag_grav, self.flag_grav2)):
            if on:
                v |= b
        return v


class MK8DX_ObjectCollision(bpy.types.PropertyGroup):
    role: EnumProperty(name="MK8DX role", default="BOTH", update=collision_preview.property_changed, items=[
        ("VISUAL", "Visual only", "Model only, no collision"),
        ("COLLISION", "Collision only", "Only in course_kcl.szs, never in course_model.szs"),
        ("BOTH", "Visual + collision", "In both files (default; collision type Road 1 / Asphalt unless you assign one)")])
    attr: IntProperty(name="Collision flag", default=0, min=0, max=0xFFFF, update=collision_preview.property_changed,
                      description="KCL flag for faces without their own type")


def in_col_collection(obj):
    return any(c.name.lower().startswith("collision") for c in obj.users_collection)


def role_of(obj):
    """Effective role. Never-assigned objects are Visual + collision (Road 1 / Asphalt, 0x0000);
    unassigned objects in a 'Collision...' collection are collision only."""
    c = obj.mk8dx_col
    if c.is_property_set("role"):
        return c.role
    return "COLLISION" if in_col_collection(obj) else "BOTH"


def is_collision(obj):
    from .placeholder import is_placeholder
    if is_placeholder(obj):
        return False
    return role_of(obj) in ("COLLISION", "BOTH")


def is_visual(obj):
    from .placeholder import is_placeholder
    if is_placeholder(obj):
        return False
    return role_of(obj) in ("VISUAL", "BOTH")


# ---------------------------------------------------------------- colours
def refresh_colors(obj):
    """Write the display colour attribute from object + face types (cheap, display only)."""
    me = obj.data
    n = len(me.polygons)
    vals = np.full(n, obj.mk8dx_col.attr, dtype=np.int64)
    fa = me.attributes.get(FACE_ATTR)
    if fa is not None and fa.domain == "FACE" and n:
        a = np.empty(n, dtype=np.int64); fa.data.foreach_get("value", a)
        vals = np.where(a >= 0, a, vals)
    ca = me.color_attributes.get(COLOR_ATTR)
    if ca is None:
        prev = me.color_attributes.active_color_name if hasattr(me.color_attributes, "active_color_name") else None
        ca = me.color_attributes.new(COLOR_ATTR, "BYTE_COLOR", "CORNER")
        if prev:   # don't steal the active (exported) vertex colours
            try:
                me.color_attributes.active_color_name = prev
            except Exception:
                pass
    lut = {int(v): coltypes.color(int(v)) for v in np.unique(vals)}
    face_rgb = np.array([lut[int(v)] + (1.0,) for v in vals], dtype=np.float32).reshape(-1, 4)
    tot = np.empty(n, dtype=np.int64); me.polygons.foreach_get("loop_total", tot)
    loop_face = np.repeat(np.arange(n), tot)   # corners are stored face by face
    ca.data.foreach_set("color", face_rgb[loop_face].ravel() if n else np.zeros(0, np.float32))
    obj.color = lut.get(int(obj.mk8dx_col.attr), coltypes.color(obj.mk8dx_col.attr)) + (1.0,)
    me.update()


# ---------------------------------------------------------------- operators
class MK8DX_OT_col_apply(bpy.types.Operator):
    """Apply the chosen MK8DX collision type to the selected objects (Object mode) or selected faces (Edit mode)"""
    bl_idname = "mk8dx.col_apply"
    bl_label = "Apply collision type"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        ts = context.scene.mk8dx_coltool
        v = ts.value()
        if v is None:
            self.report({"ERROR"}, f"Invalid hex '{ts.custom_hex}'")
            return {"CANCELLED"}
        if context.mode == "EDIT_MESH":
            nf = 0
            for obj in {o for o in context.objects_in_mode if o.type == "MESH"}:
                bm = bmesh.from_edit_mesh(obj.data)
                lay = bm.faces.layers.int.get(FACE_ATTR)
                fresh = lay is None
                if fresh:
                    lay = bm.faces.layers.int.new(FACE_ATTR)
                for f in bm.faces:
                    if fresh:
                        f[lay] = -1
                    if f.select:
                        f[lay] = v; nf += 1
                bmesh.update_edit_mesh(obj.data)
                obj.mk8dx_col.role = ts.role
            # colours need object-mode data
            objs = list(context.objects_in_mode)
            bpy.ops.object.mode_set(mode="OBJECT")
            for o in objs:
                refresh_colors(o)
            bpy.ops.object.mode_set(mode="EDIT")
            self.report({"INFO"}, f"{coltypes.describe(v)} -> {nf} faces")
        else:
            objs = [o for o in context.selected_objects if o.type == "MESH"]
            if not objs:
                self.report({"ERROR"}, "Select mesh objects first")
                return {"CANCELLED"}
            for o in objs:
                o.mk8dx_col.attr = v
                o.mk8dx_col.role = ts.role
                refresh_colors(o)
            self.report({"INFO"}, f"{coltypes.describe(v)} -> {len(objs)} objects")
        return {"FINISHED"}


class MK8DX_OT_col_clear(bpy.types.Operator):
    """Remove MK8DX collision from the selected objects (they become visual only), or reset selected faces to the object's type"""
    bl_idname = "mk8dx.col_clear"
    bl_label = "Clear collision"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        if context.mode == "EDIT_MESH":
            for obj in context.objects_in_mode:
                bm = bmesh.from_edit_mesh(obj.data)
                lay = bm.faces.layers.int.get(FACE_ATTR)
                if lay:
                    for f in bm.faces:
                        if f.select:
                            f[lay] = -1
                    bmesh.update_edit_mesh(obj.data)
            return {"FINISHED"}
        for o in context.selected_objects:
            if o.type != "MESH":
                continue
            o.mk8dx_col.role = "VISUAL"
            for name in (FACE_ATTR, COLOR_ATTR):
                a = o.data.attributes.get(name)
                if a:
                    o.data.attributes.remove(a)
        return {"FINISHED"}


class MK8DX_OT_col_show(bpy.types.Operator):
    """Show only flat collision-type colours (no materials/textures); toggle off to restore your previous shading"""
    bl_idname = "mk8dx.col_show"
    bl_label = "Collision preview"

    @classmethod
    def poll(cls, context):
        return bool(context.space_data and context.space_data.type == "VIEW_3D")

    def execute(self, context):
        collision_preview.toggle(context)
        return {"FINISHED"}


def draw_tool_ui(layout, context):
    ts = context.scene.mk8dx_coltool
    col = layout.column()
    col.prop(ts, "preset", text="")
    if ts.preset == "CUSTOM":
        col.prop(ts, "use_custom")
        if ts.use_custom:
            col.prop(ts, "custom_hex")
        else:
            col.prop(ts, "col_type"); col.prop(ts, "col_variant")
            r = col.row(align=True); r.prop(ts, "flag_trick", toggle=True); r.prop(ts, "flag_trick2", toggle=True)
            r = col.row(align=True); r.prop(ts, "flag_grav", toggle=True); r.prop(ts, "flag_grav2", toggle=True)
    v = ts.value()
    col.label(text=coltypes.describe(v) if v is not None else "Invalid hex", icon="INFO")
    col.prop(ts, "role")
    r = col.row(align=True)
    r.operator("mk8dx.col_apply", icon="CHECKMARK", text="Apply to faces" if context.mode == "EDIT_MESH" else "Apply to objects")
    r.operator("mk8dx.col_clear", icon="X", text="")
    col.operator("mk8dx.col_show", icon="COLOR", text="Hide collision preview" if collision_preview.enabled(context) else "Collision preview", depress=collision_preview.enabled(context))


def draw_tool_header(layout, context):
    ts = context.scene.mk8dx_coltool
    layout.prop(ts, "preset", text="")
    layout.operator("mk8dx.col_apply", text="Apply", icon="CHECKMARK")
    layout.operator("mk8dx.col_show", text="", icon="COLOR", depress=collision_preview.enabled(context))


class _ColToolBase:
    bl_space_type = "VIEW_3D"
    bl_label = "MK8DX Collision"
    bl_description = "Pick an MK8DX collision type and apply it to selected objects or faces"
    bl_icon = "ops.generic.select_box"
    bl_widget = None
    bl_keymap = (
        ("view3d.select", {"type": "LEFTMOUSE", "value": "CLICK"}, None),
        ("view3d.select", {"type": "LEFTMOUSE", "value": "CLICK", "shift": True}, {"properties": [("toggle", True)]}),
        ("view3d.select_box", {"type": "LEFTMOUSE", "value": "CLICK_DRAG"}, None),
        ("view3d.select_box", {"type": "LEFTMOUSE", "value": "CLICK_DRAG", "shift": True}, {"properties": [("mode", "ADD")]}),
    )

    def draw_settings(context, layout, tool):
        draw_tool_header(layout, context)


class MK8DX_TL_collision_object(_ColToolBase, bpy.types.WorkSpaceTool):
    bl_idname = "mk8dx.collision_tool_object"
    bl_context_mode = "OBJECT"


class MK8DX_TL_collision_edit(_ColToolBase, bpy.types.WorkSpaceTool):
    bl_idname = "mk8dx.collision_tool_edit"
    bl_context_mode = "EDIT_MESH"


class MK8DX_PT_collision(bpy.types.Panel):
    bl_label = "MK8DX Collision"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MK8DX"

    def draw(self, context):
        l = self.layout
        draw_tool_ui(l, context)
        o = context.active_object
        if o and o.type == "MESH":
            b = l.box()
            b.label(text=f"Active: {o.name}")
            b.prop(o.mk8dx_col, "role", text="")
            if is_collision(o):
                b.label(text="Object type: " + coltypes.describe(o.mk8dx_col.attr))
                if in_col_collection(o) and not o.mk8dx_col.is_property_set("role"):
                    b.label(text="In a 'Collision' collection -> collision only", icon="INFO")
        l.operator("mk8dx.export_kcl", icon="EXPORT")


# ---------------------------------------------------------------- gather + export
AXIS = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)   # Blender Z-up -> MK8 Y-up


def gather(context, use_selection, scale):
    """Returns (positions float32 [n*9], attrs uint16 [n], object names, warnings)."""
    pool = context.selected_objects if use_selection else context.scene.objects
    objs = [o for o in pool if o.type == "MESH" and is_collision(o) and o.visible_get()]
    warns = []
    if use_selection and not objs:
        objs = [o for o in context.scene.objects if o.type == "MESH" and is_collision(o) and o.visible_get()]
        if objs:
            warns.append("No collision objects selected: exported all visible collision objects instead")
    if not objs:
        raise RuntimeError("No collision objects. Use the MK8DX Collision tool (left toolbar) or the N-panel > MK8DX "
                           "to give meshes a collision type, or put them in a collection named 'Collision'.")
    dg = context.evaluated_depsgraph_get()
    P, A = [], []
    for obj in objs:
        ev = obj.evaluated_get(dg)
        me = ev.to_mesh(preserve_all_data_layers=True, depsgraph=dg)
        try:
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            if not nt:
                continue
            vi = np.empty(nt * 3, np.int64); me.loop_triangles.foreach_get("vertices", vi)
            pi = np.empty(nt, np.int64); me.loop_triangles.foreach_get("polygon_index", pi)
            co = np.empty(len(me.vertices) * 3, np.float64); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
            mw = np.array(obj.matrix_world, np.float64)
            pos = (co[vi] @ mw[:3, :3].T + mw[:3, 3]) @ AXIS.T * scale
            if np.linalg.det(mw[:3, :3]) < 0:     # mirrored: keep winding (normals) pointing the right way
                pos = pos.reshape(-1, 3, 3)[:, [0, 2, 1]].reshape(-1, 3)
            at = np.full(nt, obj.mk8dx_col.attr, np.int64)
            fa = me.attributes.get(FACE_ATTR)
            if fa is not None and fa.domain == "FACE":
                fv = np.empty(len(me.polygons), np.int64); fa.data.foreach_get("value", fv)
                at = np.where(fv[pi] >= 0, fv[pi], at)
            P.append(pos.astype(np.float32).ravel()); A.append((at & 0xFFFF).astype(np.uint16))
        finally:
            ev.to_mesh_clear()
    if not P:
        raise RuntimeError("Collision objects have no faces")
    return np.concatenate(P), np.concatenate(A), [o.name for o in objs], warns


class Proxy:
    """Lets the model exporter reuse the destination settings for course_kcl.szs."""
    def __init__(self, op, filepath):
        self.course_dest, self.course_kind, self.course_root = op.course_dest, op.course_kind, op.course_root
        self.filepath = filepath
        self.report = op.report


def export_kcl(op, context, use_selection, scale):
    """Build + place course_kcl.szs. Returns written paths or None (errors reported)."""
    from . import operators
    targets = operators.make_targets(op, context, "course_kcl.szs")
    if isinstance(targets, str):
        op.report({"ERROR"}, targets)
        return None
    if context.object and context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    work = tempfile.mkdtemp(prefix="mk8dx_kcl_")
    try:
        try:
            pos, att, names, warns = gather(context, use_selection, scale)
        except RuntimeError as e:
            op.report({"ERROR"}, str(e))
            return None
        pos.tofile(os.path.join(work, "pos.bin")); att.tofile(os.path.join(work, "attr.bin"))
        built = os.path.join(work, "course_kcl.szs")
        code, so, se = cli.run(context, ["kcl-export", os.path.join(work, "pos.bin"), os.path.join(work, "attr.bin"), built])
        if code != 0 or not os.path.isfile(built) or os.path.getsize(built) == 0:
            msg = next((ln for ln in (se or so).splitlines() if ln.startswith("ERROR")), (se or so).strip()[-300:])
            op.report({"ERROR"}, f"Collision export failed: {msg}")
            return None
        for w in warns + [ln for ln in so.splitlines() if ln.startswith("WARNING")]:
            op.report({"WARNING"}, w)
        uniq = sorted({int(a) for a in att})
        log = f"objects: {', '.join(names)}\ntriangles: {len(att)}\nflags: {', '.join(f'COL_{a:X}' for a in uniq)}\n" + so + "\n" + se
        return operators.place_outputs(op, built, targets, log)
    finally:
        shutil.rmtree(work, ignore_errors=True)


KCL_OPTS = ("use_selection", "scale", "course_dest", "course_kind", "course_root")


class MK8DX_OT_export_kcl(bpy.types.Operator, ExportHelper):
    """Export collision objects to an MK8DX course_kcl.szs (Switch KCL v2, Yaz0)"""
    bl_idname = "mk8dx.export_kcl"
    bl_label = "Export MK8DX course_kcl.szs"
    filename_ext = ".szs"
    filter_glob: StringProperty(default="*.szs;*.kcl", options={"HIDDEN"})
    filepath: StringProperty(subtype="FILE_PATH", default="course_kcl.szs")
    course_dest: EnumProperty(name="Course folder", default="NONE", items=[
        ("NONE", "Off (only the file above)", ""), ("ALSO", "Also save to course folder", ""), ("INSTEAD", "Save only to course folder", "")])
    course_kind: EnumProperty(name="Destination", default="TEMPLATE", items=[
        ("TEMPLATE", "Template's course folder (replace)", "Next to the template course_model.szs; original kept as course_kcl.szs.orig"),
        ("RYUJINX", "Ryujinx mod folder (creates mod folders)", "<Ryujinx>/mods/contents/0100152000022000/<Mod name>/romfs/course/<Course>/course_kcl.szs"),
        ("ROMFS", "Existing RomFS (replace)", "Replace course_kcl.szs in an existing <romfs>/course/<Course>/ folder. Never creates folders")])
    course_root: StringProperty(name="Existing RomFS folder", subtype="DIR_PATH", default="")
    use_selection: BoolProperty(name="Selected only", default=False,
                                description="Only selected collision objects (falls back to all if none are selected)")
    scale: FloatProperty(name="Scale", default=1.0, min=0.0001, soft_max=1000, description="Must match the model export scale")

    def invoke(self, context, event):
        from . import operators
        operators.load_opts(self, context, KCL_OPTS)
        if not self.filepath or not os.path.basename(self.filepath):
            self.filepath = "course_kcl.szs"
        return super().invoke(context, event)

    def draw(self, context):
        from . import operators
        l = self.layout
        l.prop(self, "use_selection"); l.prop(self, "scale")
        b = l.box(); b.label(text="Optional course-folder copy"); b.prop(self, "course_dest", text="")
        if self.course_dest != "NONE":
            b.prop(self, "course_kind")
            if self.course_kind == "ROMFS":
                b.prop(self, "course_root")
            sc = context.scene.mk8dx
            if self.course_kind != "TEMPLATE":
                b.prop(sc, "gu_folder")
            if self.course_kind == "RYUJINX":
                b.prop(sc, "mod_name")
            t = operators.course_target(context, self.course_kind, self.course_root, "course_kcl.szs")
            b.label(text=t or "Destination incomplete", icon="FILE_FOLDER" if t else "ERROR")

    def execute(self, context):
        from . import operators
        operators.save_opts(self, context, KCL_OPTS)
        t0 = time.time()
        w = export_kcl(self, context, self.use_selection, self.scale)
        if w is None:
            return {"CANCELLED"}
        self.report({"INFO"}, "Collision saved to: " + " ; ".join(w) + f"  ({time.time()-t0:.1f}s)")
        return {"FINISHED"}


class MK8DX_PT_object_col(bpy.types.Panel):
    bl_label = "MK8DX Collision"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"

    @classmethod
    def poll(cls, context):
        return context.object and context.object.type == "MESH"

    def draw(self, context):
        o = context.object
        self.layout.prop(o.mk8dx_col, "role")
        self.layout.prop(o.mk8dx_col, "attr")
        self.layout.label(text=coltypes.describe(o.mk8dx_col.attr))


def menu_func(self, context):
    self.layout.operator(MK8DX_OT_export_kcl.bl_idname, text="MK8DX collision (course_kcl.szs)")


classes = (MK8DX_CollisionToolSettings, MK8DX_ObjectCollision, MK8DX_OT_col_apply, MK8DX_OT_col_clear,
           MK8DX_OT_col_show, MK8DX_OT_export_kcl, MK8DX_PT_collision, MK8DX_PT_object_col)
tools = (MK8DX_TL_collision_object, MK8DX_TL_collision_edit)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.mk8dx_coltool = PointerProperty(type=MK8DX_CollisionToolSettings)
    bpy.types.Object.mk8dx_col = PointerProperty(type=MK8DX_ObjectCollision)
    for t in tools:
        try:
            bpy.utils.register_tool(t, after={"builtin.measure"}, separator=True)
        except Exception as e:   # never block the add-on if the toolbar API changes
            print("MK8DX: could not register toolbar tool:", e)
    bpy.types.TOPBAR_MT_file_export.append(menu_func)


def unregister():
    collision_preview.unregister()
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)
    for t in tools:
        try:
            bpy.utils.unregister_tool(t)
        except Exception:
            pass
    del bpy.types.Object.mk8dx_col
    del bpy.types.Scene.mk8dx_coltool
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
