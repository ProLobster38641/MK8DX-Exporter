import bpy, os, json, subprocess, addon_utils, numpy as np, shutil, tempfile
TMP = tempfile.gettempdir()
T = os.path.dirname(os.path.abspath(__file__)); O = os.path.join(TMP, "bfmat import"); shutil.rmtree(O, ignore_errors=True); os.makedirs(O)
CLI = os.path.join(T, "..", "cli", "publish", "linux-x64", "mk8szs")
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
p = bpy.context.preferences.addons[pkg].preferences; p.ryujinx_dir = ""; p.romfs_dir = ""
def chk(t, ok, x=""): print(f"CHECK {t}: {'PASS' if ok else 'FAIL'} {x}")
def cli(*a): return subprocess.run([CLI, *a], capture_output=True, text=True).stdout
def info(path): return json.loads(cli("info", path))
def run(op, **kw):
    try: return op(**kw)
    except RuntimeError as e: return "ERR " + str(e)[:200]
# --- 1. make a texture-source course: export a material 'Brick' with a 32x32 image
bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene; sc.mk8dx.template_file = T + "/tmpl.szs"
img = bpy.data.images.new("brick", 32, 32); y, x = np.mgrid[0:32, 0:32]
px = np.zeros((32, 32, 4), np.float32); px[..., 0] = x / 31; px[..., 1] = y / 31; px[..., 2] = 0.3; px[..., 3] = 1; img.pixels.foreach_set(px.ravel())
m = bpy.data.materials.new("Brick"); n = m.node_tree.nodes.new("ShaderNodeTexImage"); n.image = img
m.node_tree.links.new(n.outputs[0], m.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
bpy.ops.mesh.primitive_plane_add(size=4); bpy.context.object.data.materials.append(m)
SRC = O + "/source course/course_model.szs"
chk("make source course", run(bpy.ops.mk8dx.export_szs, filepath=SRC) == {"FINISHED"})
cli("extract-bfmat", SRC, "Brick", O + "/Brick.bfmat"); chk("bfmat extracted", os.path.isfile(O + "/Brick.bfmat"))
# --- 2. fresh scene, save blend, import bfmat (texture source picked in dialog), template = tmpl.szs (has no 'brick')
bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene; sc.mk8dx.template_file = T + "/tmpl.szs"
bpy.ops.wm.save_as_mainfile(filepath=O + "/scene.blend")
r = run(bpy.ops.mk8dx.import_bfmat, filepath=O + "/Brick.bfmat", files=[{"name": "Brick.bfmat"}], directory=O, tex_source=SRC)
mat = bpy.data.materials.get("Brick")
from importlib import import_module; g = import_module(pkg + ".gather")
im, _ = g.find_albedo_image(mat) if mat else (None, None)
chk("bfmat import -> material with albedo image", r == {"FINISHED"} and mat and im and tuple(im.size) == (32, 32), str(r))
chk("linked .bfmat next to .blend", mat.mk8dx.bfmat_path.startswith(O + "/scene_mk8dx") and os.path.isfile(mat.mk8dx.bfmat_path), mat.mk8dx.bfmat_path)
chk("PNG saved + packed", os.path.isfile(O + "/scene_mk8dx/textures/brick.png") and im.packed_file is not None)
px2 = np.empty(32 * 32 * 4, np.float32); im.pixels.foreach_get(px2)
chk("decoded pixels ~ original", np.abs(px2.reshape(32, 32, 4)[..., :3] - px[..., :3]).max() < 0.08, str(np.abs(px2.reshape(32,32,4)[...,:3]-px[...,:3]).max()))
run(bpy.ops.mk8dx.import_bfmat, filepath=O + "/Brick.bfmat", files=[{"name": "Brick.bfmat"}], directory=O, tex_source=SRC)
chk("re-import reuses material (no .001)", "Brick.001" not in bpy.data.materials and len([x for x in bpy.data.materials if x.name.startswith("Brick")]) == 1)
# --- 3. export unchanged -> clones the bfmat, keeps original texture bytes from source
bpy.ops.mesh.primitive_plane_add(size=10); ob = bpy.context.object; ob.data.materials.append(mat)
OUT = O + "/out/course_model.szs"
r = run(bpy.ops.mk8dx.export_szs, filepath=OUT)
d = info(OUT); mats = [mm for md in d["models"] for mm in md["materials"]]
bm = next((mm for mm in mats if mm["Name"] == "Brick"), None)
chk("export ok, material Brick present", r == {"FINISHED"} and bm is not None, str(r))
log = open(O + "/out/course_model_export_log.txt").read()
chk("cloned from bfmat", "template=bfmat:" in log)
smp = json.dumps(bm)
chk("albedo keeps original texture name", '"brick"' in smp.lower() or "brick" in smp, smp[:300])
cli("decode-texture", SRC, "brick", O + "/a.rgba"); cli("decode-texture", OUT, "brick", O + "/b.rgba")
chk("original texture embedded unchanged", os.path.isfile(O + "/b.rgba") and open(O + "/a.rgba", "rb").read() == open(O + "/b.rgba", "rb").read())
# --- 4. change Base Color image -> albedo swapped
new = bpy.data.images.new("my_new_alb", 16, 16); new.pixels.foreach_set(np.ones(16 * 16 * 4, np.float32))
for nd in mat.node_tree.nodes:
    if nd.type == "TEX_IMAGE" and nd.image == im: nd.image = new
r = run(bpy.ops.mk8dx.export_szs, filepath=O + "/out2.szs")
d2 = json.dumps(info(O + "/out2.szs"))
chk("changed image -> albedo swapped, still bfmat clone", r == {"FINISHED"} and "my_new_alb" in d2 and "template=bfmat:" in open(O + "/out2_export_log.txt").read())
# --- 5. missing textures: no source, template without them
bpy.ops.wm.read_homefile(use_empty=True); sc = bpy.context.scene; sc.mk8dx.template_file = ""
r = run(bpy.ops.mk8dx.import_bfmat, filepath=O + "/Brick.bfmat", files=[{"name": "Brick.bfmat"}], directory=O)
m3 = bpy.data.materials.get("Brick (missing textures)")
chk("missing textures -> material still created, no error", r == {"FINISHED"} and m3 is not None and m3.mk8dx.bfmat_path, str(r))
chk("missing noted", "not found" in m3.mk8dx.bfmat_info)
# --- 6. import all materials from a .szs
r = run(bpy.ops.mk8dx.import_szs_materials, filepath=T + "/tmpl.szs")
names = sorted(x.name for x in bpy.data.materials)
chk("import all from .szs", r == {"FINISHED"} and all(n in names for n in ("mt_road_template", "mt_grass_template", "ef_water01", "mt_fence_mask")), str(names))
mr = bpy.data.materials["mt_road_template"]; ia, _ = g.find_albedo_image(mr)
chk("szs material has its albedo", ia is not None and ia.name == "orig_road_alb")
r = run(bpy.ops.mk8dx.import_szs_materials, filepath=T + "/tmpl.szs", only="ef_water01")
chk("only filter + no duplicates", r == {"FINISHED"} and "ef_water01.001" not in bpy.data.materials)
