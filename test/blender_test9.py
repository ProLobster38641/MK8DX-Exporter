import bpy, os, json, subprocess, addon_utils, shutil, tempfile
TMP = tempfile.gettempdir(); T = os.path.dirname(os.path.abspath(__file__))
O = os.path.join(TMP, "grid test"); shutil.rmtree(O, ignore_errors=True); os.makedirs(O)
CLI = os.path.join(T, "..", "cli", "publish", "linux-x64", "mk8szs")
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
def chk(t, ok, x=""): print(f"CHECK {t}: {'PASS' if ok else 'FAIL'} {x}")
bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene; sc.mk8dx.template_file = T + "/tmpl.szs"
chk("add menu entry", hasattr(bpy.types, "VIEW3D_MT_mk8dx_add"))
bpy.ops.mesh.primitive_plane_add(size=50); road = bpy.context.object; road.name = "Road"
road.mk8dx_col.role = "BOTH"
r = bpy.ops.mk8dx.add_start_grid(scale=10)
root = bpy.data.objects.get("MK8DX_StartGrid_Placeholder")
karts = [o for o in bpy.data.objects if o.name.startswith("MK8DX_Start_")]
chk("12 markers under one empty", r == {"FINISHED"} and root and len(karts) == 12 and all(k.parent == root for k in karts))
dims = karts[0].dimensions
chk("kart size = game units / scale", abs(dims.x - 10.0) < 0.01 and abs(karts[0].data.vertices[2].co.y * 2 - 14.0) < 0.01, str(tuple(dims)))
chk("staggered grid", karts[0].location.x < 0 < karts[1].location.x and karts[1].location.y < karts[0].location.y)
chk("wire, hidden from render, no locks", all(k.display_type == "WIRE" and k.hide_render and not any(k.lock_location) for k in karts))
coll = bpy.data.collections.get("MK8DX_StartGrid_Placeholder"); chk("own collection", coll and len(coll.objects) == 14)
# put a marker in a Collision collection too, select everything, export both
cc = bpy.data.collections.new("Collision"); sc.collection.children.link(cc); cc.objects.link(karts[3])
for o in bpy.data.objects: o.select_set(True)
r = bpy.ops.mk8dx.export_szs(filepath=O + "/course_model.szs", with_kcl=True)
inf = subprocess.run([CLI, "info", O + "/course_model.szs"], capture_output=True, text=True).stdout
kcl = json.loads(subprocess.run([CLI, "kcl-info", O + "/course_kcl.szs"], capture_output=True, text=True).stdout)
chk("model excludes grid", r == {"FINISHED"} and "MK8DX_" not in inf and '"Road"' in inf)
chk("kcl excludes grid", kcl["triangles"] == 2, str(kcl["triangles"]))
# delete one marker with normal delete
bpy.ops.object.select_all(action="DESELECT"); karts[5].select_set(True); bpy.context.view_layer.objects.active = karts[5]
bpy.ops.object.delete(); bpy.context.view_layer.update()
chk("single marker deletes normally", "MK8DX_Start_06" not in bpy.data.objects and len([o for o in bpy.data.objects if o.name.startswith("MK8DX_Start_")]) == 11)
# delete parent empty -> whole grid + collection + mesh gone
root = bpy.data.objects["MK8DX_StartGrid_Placeholder"]
bpy.ops.object.select_all(action="DESELECT"); root.select_set(True); bpy.context.view_layer.objects.active = root
bpy.ops.object.delete(); bpy.context.view_layer.update()
left = [o.name for o in bpy.data.objects if o.name.startswith("MK8DX_")]
chk("deleting empty removes everything", not left and "MK8DX_StartGrid_Placeholder" not in bpy.data.collections and "MK8DX_StartGrid_Kart" not in bpy.data.meshes and "Road" in bpy.data.objects, str(left))
# add again and remove with the button
bpy.ops.mk8dx.add_start_grid(); r = bpy.ops.mk8dx.remove_start_grid()
chk("remove button", r == {"FINISHED"} and not [o for o in bpy.data.objects if o.name.startswith("MK8DX_")] and "MK8DX_StartGrid_Placeholder" not in bpy.data.collections)
