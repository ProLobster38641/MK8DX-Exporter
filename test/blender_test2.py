import bpy, os, json, numpy as np, addon_utils
T = os.path.dirname(os.path.abspath(__file__))
pkg = "bl_ext.user_default.mk8dx_szs_exporter"
addon_utils.enable(pkg, default_set=True)
p = bpy.context.preferences.addons[pkg].preferences
p.romfs_dir = T + "/romfs"; p.ryujinx_dir = T + "/ryujinx"
bpy.ops.wm.read_homefile(use_empty=True)
sc = bpy.context.scene; sc.mk8dx.template_file = T + "/tmpl.szs"; sc.mk8dx.mod_name = "Stress"
bpy.ops.mk8dx.load_materials()
# big grid (>65535 verts), 1024 texture, 2 UV maps, mirrored copy, vertex colours
bpy.ops.mesh.primitive_grid_add(x_subdivisions=300, y_subdivisions=300, size=200)
g = bpy.context.object; g.name = "BigTerrain"
g.data.uv_layers.new(name="Shadow")
ca = g.data.color_attributes.new("Col", "BYTE_COLOR", "CORNER")
img = bpy.data.images.new("terrain_1k", 1024, 1024)
yy, xx = np.mgrid[0:1024, 0:1024]; px = np.stack([xx/1024, yy/1024, ((xx//64+yy//64)%2)*0.8, np.ones_like(xx)], -1).astype(np.float32); img.pixels.foreach_set(px.ravel())
m = bpy.data.materials.new("Terrain"); nt = m.node_tree
t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; nt.links.new(t.outputs[0], nt.nodes["Principled BSDF"].inputs["Base Color"])
m.mk8dx.template = "mt_grass_template"
g.data.materials.append(m)
bpy.ops.mesh.primitive_monkey_add(location=(0, 0, 5)); mk = bpy.context.object; mk.scale = (-1, 1, 1)  # mirrored
npot = bpy.data.images.new("npot", 100, 60); m2 = bpy.data.materials.new("NoImage"); mk.data.materials.append(m2)
for o in bpy.data.objects: o.select_set(True)
r = bpy.ops.mk8dx.export_szs(course_dest="INSTEAD", course_kind="RYUJINX", mode="append", keep_temp=True)
print("export:", r)
