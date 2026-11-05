"""Start-grid placeholder: 12 kart-sized markers for sizing a course. Never exported (model or collision).

Assumed MK8DX sizes in game units (not official; adjustable in the operator's redo panel):
  kart about 140 long x 100 wide x 70 high; staggered grid, racers alternate left/right of the centre line
  250 units apart sideways and 230 units further back each, i.e. 6 rows of 2; typical road about 2400 wide.
Blender size = game units / export Scale (the exporter multiplies by Scale).
"""
import bpy
from bpy.props import FloatProperty, BoolProperty

FLAG = "mk8dx_placeholder"
ROOT = "MK8DX_StartGrid_Placeholder"
COLL = "MK8DX_StartGrid_Placeholder"
MESH = "MK8DX_StartGrid_Kart"
ROADMESH = "MK8DX_StartGrid_RoadRef"


def is_placeholder(obj):
    o = obj
    while o is not None:
        if o.get(FLAG):
            return True
        o = o.parent
    return any(c.get(FLAG) for c in obj.users_collection)


def export_scale(context):
    try:
        return context.window_manager.operator_properties_last("mk8dx.export_szs").scale or 1.0
    except Exception:
        return 1.0


def kart_mesh(name, L, W, H):
    """Low-poly box with a wedge arrow on top pointing forward (+Y in Blender = driving direction)."""
    l, w, h = L / 2, W / 2, H
    v = [(-w, -l, 0), (w, -l, 0), (w, l, 0), (-w, l, 0), (-w, -l, h), (w, -l, h), (w, l, h), (-w, l, h),
         (-w * 0.6, 0, h * 1.01), (w * 0.6, 0, h * 1.01), (0, l * 1.35, h * 1.01)]
    f = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (8, 9, 10)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(v, [], f)
    me.update()
    return me


def remove_grid(scene=None):
    """Delete the whole placeholder: objects, its collection, and orphan meshes."""
    for o in [o for o in bpy.data.objects if o.get(FLAG) or (o.parent and o.parent.get(FLAG))]:
        bpy.data.objects.remove(o, do_unlink=True)
    c = bpy.data.collections.get(COLL)
    if c and c.get(FLAG):
        for o in list(c.objects):
            bpy.data.objects.remove(o, do_unlink=True)
        bpy.data.collections.remove(c)
    for n in (MESH, ROADMESH):
        me = bpy.data.meshes.get(n)
        if me and me.users == 0:
            bpy.data.meshes.remove(me)


_busy = False


@bpy.app.handlers.persistent
def _cleanup(scene, depsgraph=None):
    """Deleting the parent empty with X/Delete removes the rest of the grid too."""
    global _busy
    if _busy:
        return
    c = bpy.data.collections.get(COLL)
    if not c or not c.get(FLAG):
        return
    root_alive = any(o.get(FLAG) and o.type == "EMPTY" for o in c.objects)
    if root_alive and len(c.objects):
        return
    _busy = True
    try:
        remove_grid()
    finally:
        _busy = False


class MK8DX_OT_add_start_grid(bpy.types.Operator):
    """Add 12 kart-sized start-grid markers at the 3D cursor to size your course. Never exported"""
    bl_idname = "mk8dx.add_start_grid"
    bl_label = "Add Start Grid Placeholder"
    bl_options = {"REGISTER", "UNDO"}

    kart_length: FloatProperty(name="Kart length (game units)", default=140, min=1)
    kart_width: FloatProperty(name="Kart width (game units)", default=100, min=1)
    kart_height: FloatProperty(name="Kart height (game units)", default=70, min=1)
    side: FloatProperty(name="Left/right offset", default=250, min=0, description="Distance of each column from the centre line")
    step: FloatProperty(name="Spacing per racer", default=230, min=1, description="Each next racer is this much further back")
    road_ref: BoolProperty(name="Road width reference", default=True)
    road_width: FloatProperty(name="Road width (game units)", default=2400, min=1)
    scale: FloatProperty(name="Export scale", default=0, min=0,
                         description="0 = use the Scale from the last model export (Blender size = game units / scale)")

    def execute(self, context):
        remove_grid()
        s = self.scale or export_scale(context)
        k = 1.0 / s
        coll = bpy.data.collections.new(COLL); coll[FLAG] = True
        context.scene.collection.children.link(coll)
        root = bpy.data.objects.new(ROOT, None); root[FLAG] = True
        root.empty_display_type = "SINGLE_ARROW"; root.empty_display_size = self.step * 2 * k
        root.location = context.scene.cursor.location; root.hide_render = True
        coll.objects.link(root)
        me = kart_mesh(MESH, self.kart_length * k, self.kart_width * k, self.kart_height * k)
        for i in range(12):
            o = bpy.data.objects.new(f"MK8DX_Start_{i + 1:02d}", me); o[FLAG] = True
            o.location = ((-1 if i % 2 == 0 else 1) * self.side * k, -i * self.step * k - self.kart_length * k, 0)
            o.parent = root; o.display_type = "WIRE"; o.show_in_front = True
            o.color = (1.0, 0.2, 0.9, 1.0) if i else (1.0, 0.85, 0.1, 1.0); o.hide_render = True
            coll.objects.link(o)
        if self.road_ref:
            rw, rl = self.road_width * k / 2, (12 * self.step + 400) * k
            rm = bpy.data.meshes.new(ROADMESH)
            rm.from_pydata([(-rw, 200 * k, 0), (rw, 200 * k, 0), (rw, -rl, 0), (-rw, -rl, 0)], [(0, 1), (1, 2), (2, 3), (3, 0)], [])
            ro = bpy.data.objects.new("MK8DX_RoadWidth_Ref", rm); ro[FLAG] = True; ro.parent = root
            ro.hide_render = True; ro.color = (0.2, 0.9, 1.0, 1.0); coll.objects.link(ro)
        self.report({"INFO"}, f"Start grid added (scale {s:g}: 1 Blender unit = {s:g} game units). Never exported; delete the empty to remove it")
        return {"FINISHED"}


class MK8DX_OT_remove_start_grid(bpy.types.Operator):
    """Remove the start-grid placeholder (markers, collection and mesh data)"""
    bl_idname = "mk8dx.remove_start_grid"
    bl_label = "Remove Start Grid Placeholder"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        remove_grid()
        return {"FINISHED"}


class VIEW3D_MT_mk8dx_add(bpy.types.Menu):
    bl_idname = "VIEW3D_MT_mk8dx_add"
    bl_label = "MK8DX"

    def draw(self, context):
        self.layout.operator(MK8DX_OT_add_start_grid.bl_idname, icon="AUTO")
        self.layout.operator(MK8DX_OT_remove_start_grid.bl_idname, icon="X")


def draw_panel(layout):
    r = layout.row(align=True)
    r.operator(MK8DX_OT_add_start_grid.bl_idname, text="Add Start Grid", icon="AUTO")
    r.operator(MK8DX_OT_remove_start_grid.bl_idname, text="Remove", icon="X")


def menu_func(self, context):
    self.layout.menu(VIEW3D_MT_mk8dx_add.bl_idname)


classes = (MK8DX_OT_add_start_grid, MK8DX_OT_remove_start_grid, VIEW3D_MT_mk8dx_add)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_add.append(menu_func)
    bpy.app.handlers.depsgraph_update_post.append(_cleanup)


def unregister():
    if _cleanup in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_cleanup)
    bpy.types.VIEW3D_MT_add.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
