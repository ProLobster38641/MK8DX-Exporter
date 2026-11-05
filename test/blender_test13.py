"""Collision preview is flat/untextured, nondestructive and restores exact viewport shading."""
import bpy, os, addon_utils, numpy as np
pkg = "bl_ext.user_default.mk8dx_szs_exporter"; addon_utils.enable(pkg, default_set=True)
col = __import__(pkg + ".collision", fromlist=["x"])
preview = __import__(pkg + ".collision_preview", fromlist=["x"])
from mathutils import Matrix
bpy.ops.wm.read_homefile(use_empty=True)
mesh = bpy.data.meshes.new("PreviewTest")
mesh.from_pydata([(0,0,0), (1,0,0), (1,1,0), (0,1,0)], [], [(0,1,2), (0,2,3)])
obj = bpy.data.objects.new("Road", mesh); bpy.context.scene.collection.objects.link(obj)
linked = bpy.data.objects.new("Linked", mesh); bpy.context.scene.collection.objects.link(linked)
linked.mk8dx_col.attr = 0x15
visual = bpy.data.objects.new("VisualOnly", mesh.copy()); bpy.context.scene.collection.objects.link(visual)
visual.mk8dx_col.role = "VISUAL"
mat = bpy.data.materials.new("Textured"); tex = bpy.data.images.new("Albedo", 8, 8)
node = mat.node_tree.nodes.new("ShaderNodeTexImage"); node.image = tex
mat.node_tree.links.new(node.outputs["Color"],mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
mesh.materials.append(mat)
ca = mesh.color_attributes.new("ArtistColour", "BYTE_COLOR", "CORNER")
ca.data.foreach_set("color", np.tile([0.8,0.2,0.3,1],len(mesh.loops)).astype(np.float32))
mesh.color_attributes.active_color_name = "ArtistColour"
fa = mesh.attributes.new(col.FACE_ATTR, "INT", "FACE"); fa.data.foreach_set("value", [-1,4])
bpy.context.view_layer.update()
def chk(tag, ok):
    print(f"CHECK {tag}: {'PASS' if ok else 'FAIL'}"); assert ok, tag

def shading_snapshot(sh):
    out = {}
    for p in sh.bl_rna.properties:
        if p.is_readonly or p.type in {"POINTER","COLLECTION"}: continue
        v = getattr(sh,p.identifier)
        out[p.identifier] = tuple(v) if getattr(p, "is_array", False) else v
    return out

def data_snapshot():
    return (tuple(mesh.color_attributes.keys()), mesh.color_attributes.active_color_name,
            mesh.color_attributes.active_color_index, mesh.color_attributes.render_color_index,
            tuple(v for d in ca.data for v in d.color), tuple(obj.color), tuple(linked.color),
            tuple(mesh.materials), node.image, tuple(f.material_index for f in mesh.polygons))
base_data = data_snapshot()
area = next(a for a in bpy.context.screen.areas if a.type == "VIEW_3D")
region = next(r for r in area.regions if r.type == "WINDOW")
with bpy.context.temp_override(area=area, region=region):
    sh = area.spaces.active.shading
    for mode, light, colour in [("MATERIAL","STUDIO","MATERIAL"),("RENDERED","MATCAP","TEXTURE"),("WIREFRAME","STUDIO","OBJECT"),("SOLID","MATCAP","VERTEX")]:
        sh.type=mode; sh.light=light; sh.color_type=colour
        sh.single_color=(0.7,0.3,0.1); sh.show_shadows=True; sh.show_cavity=True
        sh.show_specular_highlight=True; sh.show_xray=True; sh.show_xray_wireframe=True
        before = shading_snapshot(sh)
        r = bpy.ops.mk8dx.col_show()
        chk("flat preview from " + mode, r == {"FINISHED"} and preview.enabled(bpy.context) and sh.type=="SOLID" and sh.color_type=="SINGLE" and sh.light=="FLAT" and not sh.show_shadows and not sh.show_cavity and not sh.show_specular_highlight)
        chk("materials, images and colour attributes untouched from " + mode, data_snapshot()==base_data)
        bpy.ops.mk8dx.col_show()
        chk("exact shading restored to " + mode, shading_snapshot(sh)==before and not preview.enabled(bpy.context))
    # Per-face overrides and linked objects keep their own object-level defaults.
    dep=bpy.context.evaluated_depsgraph_get()
    pos, rgb=preview.mesh_colours(obj,dep)
    pos2, rgb2=preview.mesh_colours(linked,dep)
    chk("face types have flat constant colours", pos.shape==(6,3) and np.allclose(rgb[:3],col.coltypes.color(0)+(1.0,)) and np.allclose(rgb[3:],col.coltypes.color(4)+(1.0,)))
    chk("linked meshes respect each object's collision type", np.allclose(rgb2[:3],col.coltypes.color(0x15)+(1.0,)) and np.allclose(rgb2[3:],rgb[3:]))
    vp, vc=preview.mesh_colours(visual,dep)
    chk("non-collision meshes get only neutral Workbench base", len(vp)==0 and len(vc)==0 and preview.PREVIEW_SHADING["single_color"]==preview.NEUTRAL)
    before=shading_snapshot(sh); bpy.ops.mk8dx.col_show(); preview.unregister()
    chk("disabling add-on restores shading and removes handlers", shading_snapshot(sh)==before and not preview._states and preview._handler is None and preview.invalidate not in bpy.app.handlers.depsgraph_update_post)
chk("preview does not modify mesh data or artist materials", data_snapshot()==base_data)
print("RESULT: ALL PASS")
