import bpy, sys, addon_utils, numpy as np
addon_utils.enable("bl_ext.user_default.io_scene_bfres", default_set=True)
path = sys.argv[sys.argv.index("--")+1]
ops = [o for o in dir(bpy.ops.import_scene) if "bfres" in o.lower()]
print("ops", ops)
bpy.ops.wm.read_homefile(use_empty=True)
getattr(bpy.ops.import_scene, ops[0])(filepath=path)
for o in bpy.data.objects:
    if o.type == "MESH":
        me = o.data; me.calc_loop_triangles()
        co = np.array([v.co[:] for v in me.vertices])
        print("MESH", o.name, "verts", len(me.vertices), "tris", len(me.loop_triangles), "bbox", co.min(0).round(2).tolist(), co.max(0).round(2).tolist(), "uvs", [l.name for l in me.uv_layers], "mats", [m.name for m in me.materials])
for i in bpy.data.images:
    if i.size[0]:
        px = np.empty(i.size[0]*i.size[1]*4, np.float32); i.pixels.foreach_get(px); px = px.reshape(i.size[1], i.size[0], 4)
        print("IMAGE", i.name, tuple(i.size), "mean rgba", px.reshape(-1,4).mean(0).round(3).tolist(), "alpha min", px[...,3].min())
for m in bpy.data.materials:
    print("MAT", m.name, {k: str(m[k])[:60] for k in m.keys()} if hasattr(m, "keys") else "")
