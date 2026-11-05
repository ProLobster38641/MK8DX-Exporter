"""Viewport-only collision colours. No materials, mesh attributes or object display colours are changed."""
import bpy
import numpy as np
from bpy.app.handlers import persistent

NEUTRAL = (0.16, 0.16, 0.16)
# Only these shading values are changed; restore them verbatim when the preview closes.
PREVIEW_SHADING = {
    "type": "SOLID", "color_type": "SINGLE", "single_color": NEUTRAL,
    "light": "FLAT", "show_shadows": False, "show_cavity": False,
    "show_specular_highlight": False, "show_xray": False,
    "show_xray_wireframe": False, "show_backface_culling": False,
}
_states = {}
_handler = None
_shader = None
_revision = 0


def enabled(context):
    space = context.space_data
    return bool(space and space.type == "VIEW_3D" and space.as_pointer() in _states)


def _snapshot(shading):
    return {k: tuple(getattr(shading, k)) if k == "single_color" else getattr(shading, k)
            for k in PREVIEW_SHADING}


def _restore(state):
    try:
        sh = state["space"].shading
        # Restore the original engine/shading mode last (Material Preview, Rendered, Wireframe, etc.).
        for k, v in state["shading"].items():
            if k != "type":
                setattr(sh, k, v)
        sh.type = state["shading"]["type"]
    except (ReferenceError, RuntimeError):
        pass  # The viewport may have been closed while the preview was active.


def invalidate(*_args):
    global _revision
    _revision += 1
    for wm in bpy.data.window_managers:
        for window in wm.windows:
            for area in window.screen.areas:
                if area.type == "VIEW_3D":
                    area.tag_redraw()


def property_changed(self, context):
    invalidate()


@persistent
def _load_pre(*_args):
    unregister()


def mesh_colours(obj, depsgraph):
    """Evaluated local-space triangle corners + a constant RGBA colour for each triangle.
    Called separately per object: linked meshes may have different object collision types.
    """
    from . import collision, coltypes
    if obj.type != "MESH" or not collision.is_collision(obj):
        return np.empty((0, 3), np.float32), np.empty((0, 4), np.float32)
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        n = len(mesh.loop_triangles)
        positions = np.empty(len(mesh.vertices) * 3, np.float32)
        mesh.vertices.foreach_get("co", positions)
        indices = np.empty(n * 3, np.int32)
        mesh.loop_triangles.foreach_get("vertices", indices)
        polygon = np.empty(n, np.int32)
        mesh.loop_triangles.foreach_get("polygon_index", polygon)
        flags = np.full(len(mesh.polygons), obj.mk8dx_col.attr, np.int32)
        attr = mesh.attributes.get(collision.FACE_ATTR)
        if attr and attr.domain == "FACE" and attr.data_type == "INT":
            face_flags = np.empty(len(mesh.polygons), np.int32)
            attr.data.foreach_get("value", face_flags)
            flags = np.where(face_flags >= 0, face_flags, flags)
        lut = {int(v): coltypes.color(int(v)) + (1.0,) for v in np.unique(flags)}
        face_colours = np.array([lut[int(v)] for v in flags], np.float32).reshape(-1, 4)
        colours = np.repeat(face_colours[polygon], 3, axis=0)
        return positions.reshape(-1, 3)[indices], colours
    finally:
        evaluated.to_mesh_clear()


def _draw():
    global _shader
    context = bpy.context
    if not enabled(context):
        return
    import gpu
    from gpu_extras.batch import batch_for_shader
    from mathutils import Matrix
    state = _states[context.space_data.as_pointer()]
    if _shader is None:
        _shader = gpu.shader.from_builtin("SMOOTH_COLOR")
    visible = [obj for obj in context.scene.objects if obj.type == "MESH"
               and obj.visible_get(view_layer=context.view_layer, viewport=context.space_data)]
    # Visibility can change without a geometry update (e.g. Local View in this viewport).
    cache_key = (_revision, context.scene.as_pointer(), context.view_layer.as_pointer(), context.mode,
                 tuple(obj.as_pointer() for obj in visible))
    if state.get("cache_key") != cache_key:
        batches = []
        for obj in visible:
            pos, colours = mesh_colours(obj, context.evaluated_depsgraph_get())
            if len(pos):
                batch = batch_for_shader(_shader, "TRIS", {"pos": pos, "color": colours})
                batches.append((obj.evaluated_get(context.evaluated_depsgraph_get()).matrix_world.copy(), batch))
        state["batches"] = batches
        state["cache_key"] = cache_key
    old = (gpu.state.blend_get(), gpu.state.depth_test_get(), gpu.state.depth_mask_get())
    try:
        gpu.state.blend_set("NONE")
        gpu.state.depth_test_set("LESS_EQUAL")
        gpu.state.depth_mask_set(False)
        # A tiny clip-space offset prevents z-fighting with the neutral Workbench surface.
        # Depth testing still hides collision surfaces occluded by other meshes.
        with gpu.matrix.push_pop_projection():
            bias = Matrix.Identity(4); bias[2][3] = -0.00001
            gpu.matrix.load_projection_matrix(bias @ gpu.matrix.get_projection_matrix())
            _shader.bind()
            for matrix, batch in state["batches"]:
                with gpu.matrix.push_pop():
                    gpu.matrix.multiply_matrix(matrix)
                    batch.draw(_shader)
    finally:
        gpu.state.blend_set(old[0]); gpu.state.depth_test_set(old[1]); gpu.state.depth_mask_set(old[2])


def toggle(context):
    global _handler
    space = context.space_data
    if not space or space.type != "VIEW_3D":
        return False
    key = space.as_pointer()
    if key in _states:
        _restore(_states.pop(key))
        if not _states:
            _remove_handlers()
    else:
        _states[key] = {"space": space, "shading": _snapshot(space.shading)}
        for k, v in PREVIEW_SHADING.items():
            setattr(space.shading, k, v)
        if _handler is None:
            _handler = bpy.types.SpaceView3D.draw_handler_add(_draw, (), "WINDOW", "POST_VIEW")
        if invalidate not in bpy.app.handlers.depsgraph_update_post:
            bpy.app.handlers.depsgraph_update_post.append(invalidate)
        if _load_pre not in bpy.app.handlers.load_pre:
            bpy.app.handlers.load_pre.append(_load_pre)
    invalidate()
    return True


def _remove_handlers():
    global _handler, _shader
    if _handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_handler, "WINDOW")
        _handler = None
    for handlers, fn in ((bpy.app.handlers.depsgraph_update_post, invalidate), (bpy.app.handlers.load_pre, _load_pre)):
        if fn in handlers:
            handlers.remove(fn)
    _shader = None


def unregister():
    for state in list(_states.values()):
        _restore(state)
    _states.clear()
    _remove_handlers()
