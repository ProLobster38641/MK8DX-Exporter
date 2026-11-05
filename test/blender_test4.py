import bpy, os, addon_utils, numpy as np
import tempfile; TMP = tempfile.gettempdir()
T = os.path.dirname(os.path.abspath(__file__)); out = TMP + "/anywhere/zero_setup.szs"
pkg = "bl_ext.user_default.mk8dx_szs_exporter"
addon_utils.enable(pkg, default_set=True)
p = bpy.context.preferences.addons[pkg].preferences; p.romfs_dir = ""; p.ryujinx_dir = ""
bpy.ops.wm.read_homefile(use_empty=True)
bpy.context.scene.mk8dx.template_file = T + "/tmpl.szs"   # only setup step
def img(name, alpha):
    i = bpy.data.images.new(name, 64, 64, alpha=alpha); px = np.full((64, 64, 4), 0.6, np.float32)
    px[..., 3] = 1.0
    if alpha: px[::2, :, 3] = 0.0
    i.pixels.foreach_set(px.ravel()); return i
def mat(name, image=None, color=None):
    m = bpy.data.materials.new(name); b = m.node_tree.nodes["Principled BSDF"]
    if image:
        t = m.node_tree.nodes.new("ShaderNodeTexImage"); t.image = image; m.node_tree.links.new(t.outputs[0], b.inputs["Base Color"])
    if color: b.inputs["Base Color"].default_value = color
    return m
bpy.ops.mesh.primitive_plane_add(size=20); plane = bpy.context.object; plane.name = "Plane"
plane.data.materials.append(mat("Material.001", img("asphalt.png", False)))
plane.data.materials.append(mat("Glass Fence", img("fence_alpha.png", True)))
plane.data.materials.append(mat("Painted", color=(1, 0, 0, 1)))
for i, poly in enumerate(plane.data.polygons): poly.material_index = 0
bpy.ops.object.mode_set(mode="EDIT"); bpy.ops.mesh.subdivide(number_cuts=2); bpy.ops.object.mode_set(mode="OBJECT")
for i, poly in enumerate(plane.data.polygons): poly.material_index = i % 3
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 3)); bpy.context.object.name = "NoMatCube"
for o in bpy.data.objects: o.select_set(True)
r = bpy.ops.mk8dx.export_szs(filepath=out, keep_temp=True)
print("RESULT export:", r, os.path.exists(out))
