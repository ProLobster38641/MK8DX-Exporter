"""Collect evaluated geometry, materials and textures from the Blender scene into an export folder."""
import json
import os
import re
import struct

import bpy
import numpy as np


def safe_name(s):
    s = re.sub(r"\.(png|jpg|jpeg|tga|bmp|dds|tif|tiff)$", "", s, flags=re.I)
    return re.sub(r"[^A-Za-z0-9_]", "_", s) or "unnamed"


def mat_name(s):
    """BFRES material name = the Blender material name (printable ASCII kept, incl. dots)."""
    n = "".join(c if 32 < ord(c) < 127 else "_" for c in s)
    return n or "Material"


def base_color_and_alpha(mat):
    """Fallback colour (sRGB 0-255) from Principled Base Color, and whether the material uses transparency."""
    col, alpha = (204, 204, 204, 255), False
    try:
        # Blender 4.2+: surface_render_method (DITHERED default, BLENDED = transparent); older: blend_method
        if hasattr(mat, "surface_render_method"):
            alpha = mat.surface_render_method == "BLENDED"
        elif getattr(mat, "blend_method", "OPAQUE") in ("BLEND", "CLIP"):
            alpha = True
        nt = getattr(mat, "node_tree", None)
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None) if nt else None
        if bsdf:
            a = bsdf.inputs.get("Alpha")
            if a is not None and (a.is_linked or a.default_value < 0.999):
                alpha = True
            c = bsdf.inputs["Base Color"].default_value
        else:
            c = mat.diffuse_color
        def to_srgb(v):
            v = max(0.0, min(1.0, v))
            return int(round(255 * (v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055)))
        col = (to_srgb(c[0]), to_srgb(c[1]), to_srgb(c[2]), 255)
    except Exception:
        pass
    return col, alpha


def save_solid_rgba(col, path, size=8):
    with open(path, "wb") as f:
        f.write(b"RGBA" + struct.pack("<ii", size, size) + bytes(col) * (size * size))


def find_albedo_image(mat):
    """Image feeding Base Color of the Principled BSDF (walks back through mix/math nodes)."""
    if mat is None:
        return None, []
    ov = getattr(mat, "mk8dx", None)
    if ov and ov.texture_override:
        return ov.texture_override, []
    if not getattr(mat, "node_tree", None):
        return None, []
    warnings = []
    nt = mat.node_tree

    def upstream(sock, depth=0):
        if depth > 12 or not sock.is_linked:
            return None
        node = sock.links[0].from_node
        if node.type == "TEX_IMAGE" and node.image:
            vec = node.inputs.get("Vector")
            if vec and vec.is_linked and vec.links[0].from_node.type == "MAPPING":
                warnings.append(f"Material '{mat.name}': a Mapping node scales the texture. That tiling is NOT exported - "
                                f"scale the UVs instead (UV Editor: select all, S, type the repeat count).")
            return node.image
        for inp in node.inputs:
            r = upstream(inp, depth + 1)
            if r:
                return r
        return None

    for node in nt.nodes:
        if node.type == "BSDF_PRINCIPLED":
            img = upstream(node.inputs["Base Color"])
            if img:
                return img, warnings
    for node in nt.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            return node.image, warnings
    return None, warnings


def save_image_rgba(img, path):
    w, h = img.size
    if w == 0 or h == 0:
        raise RuntimeError(f"Image '{img.name}' has no pixels (missing file?)")
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    px = px.reshape(h, w, 4)[::-1]  # Blender stores bottom row first
    data = (np.clip(px, 0, 1) * 255 + 0.5).astype(np.uint8)
    with open(path, "wb") as f:
        f.write(b"RGBA" + struct.pack("<ii", w, h))
        f.write(data.tobytes())


def collect(context, out_dir, use_selection=True, scale=1.0, export_uv1=True):
    """Writes geometry.bin, textures/*.rgba and returns (meshes, materials, textures, warnings)."""
    os.makedirs(os.path.join(out_dir, "textures"), exist_ok=True)
    depsgraph = context.evaluated_depsgraph_get()
    from .collision import is_visual, COLOR_ATTR
    from .placeholder import is_placeholder

    def pick(pool):
        # collision-only objects and the start-grid placeholder never go into the model
        return [o for o in pool if o.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"} and o.visible_get()
                and (o.type != "MESH" or is_visual(o)) and not is_placeholder(o)]

    warnings, meshes, materials, textures = [], [], {}, {}
    if use_selection:
        objs = pick(context.selected_objects)
        if not objs:
            objs = pick(context.scene.objects)
            if objs:
                warnings.append("'Selected only' is on but no exportable object is selected: exported all visible objects instead.")
    else:
        objs = pick(context.scene.objects)
    if not objs:
        raise RuntimeError("Nothing to export: the scene has no visible mesh that is set to Visual or Visual + collision.")

    # Blender Z-up -> MK8 Y-up: (x, y, z) -> (x, z, -y)
    axis = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=np.float64)
    bin_path = os.path.join(out_dir, "geometry.bin")
    with open(bin_path, "wb") as binf:
        def write(arr):
            off = binf.tell()
            binf.write(np.ascontiguousarray(arr, dtype=np.float32 if arr.dtype.kind == "f" else np.uint32).tobytes())
            return off

        for obj in objs:
            ev = obj.evaluated_get(depsgraph)
            me = ev.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
            try:
                if me is None or len(me.polygons) == 0:
                    continue
                me.calc_loop_triangles()
                tris = me.loop_triangles
                nt = len(tris)
                loops = np.empty(nt * 3, dtype=np.int64); tris.foreach_get("loops", loops)
                mat_idx = np.empty(nt, dtype=np.int64); tris.foreach_get("material_index", mat_idx)

                nl = len(me.loops)
                vidx = np.empty(nl, dtype=np.int64); me.loops.foreach_get("vertex_index", vidx)
                co = np.empty(len(me.vertices) * 3, dtype=np.float64); me.vertices.foreach_get("co", co)
                co = co.reshape(-1, 3)
                cn = np.empty(nl * 3, dtype=np.float64)
                if hasattr(me, "corner_normals"):
                    me.corner_normals.foreach_get("vector", cn)
                else:
                    me.loops.foreach_get("normal", cn)
                cn = cn.reshape(-1, 3)

                mw = np.array(obj.matrix_world, dtype=np.float64)
                pos = co[vidx] @ mw[:3, :3].T + mw[:3, 3]
                nm = np.linalg.inv(mw[:3, :3]).T
                nrm = cn @ nm.T
                nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
                pos = (pos @ axis.T) * scale
                nrm = nrm @ axis.T
                if np.linalg.det(mw[:3, :3]) < 0:  # mirrored object: keep winding correct
                    loops = loops.reshape(-1, 3)[:, ::-1].reshape(-1)

                uvs = []
                layers = list(me.uv_layers)
                if layers:
                    active = me.uv_layers.active_index if me.uv_layers.active_index >= 0 else 0
                    order = [active] + [i for i in range(len(layers)) if i != active]
                    for i in order[: (2 if export_uv1 else 1)]:
                        uv = np.empty(nl * 2, dtype=np.float64); layers[i].data.foreach_get("uv", uv)
                        uv = uv.reshape(-1, 2)
                        uv[:, 1] = 1.0 - uv[:, 1]  # flip V (BFRES origin is top-left)
                        uvs.append(uv)
                else:
                    warnings.append(f"'{obj.name}' has no UV map; textures will look like a single colour.")

                col = None
                cas = [c for c in me.color_attributes if c.name != COLOR_ATTR]   # MK8DX_Collision is display only
                if cas:
                    act = me.color_attributes.active_color
                    ca = act if act is not None and act.name != COLOR_ATTR else cas[0]
                    if ca.domain == "CORNER":
                        c = np.empty(nl * 4, dtype=np.float64); ca.data.foreach_get("color", c); col = c.reshape(-1, 4)
                    elif ca.domain == "POINT":
                        c = np.empty(len(me.vertices) * 4, dtype=np.float64); ca.data.foreach_get("color", c); col = c.reshape(-1, 4)[vidx]

                slots = obj.material_slots
                for mi in (int(x) for x in np.unique(mat_idx)):
                    sel = loops.reshape(-1, 3)[mat_idx == mi].reshape(-1)
                    bmat = slots[mi].material if mi < len(slots) else None
                    mname = mat_name(bmat.name) if bmat else "Material"
                    # unique corners -> vertices
                    parts = [pos[sel], nrm[sel]] + [u[sel] for u in uvs] + ([col[sel]] if col is not None else [])
                    key = np.round(np.hstack(parts), 6)
                    uniq, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
                    vsel = sel[first]
                    arrays = {"position": {"offset": write(pos[vsel]), "components": 3},
                              "normal": {"offset": write(nrm[vsel]), "components": 3}}
                    for k, u in enumerate(uvs):
                        arrays[f"uv{k}"] = {"offset": write(u[vsel]), "components": 2}
                    if col is not None:
                        arrays["color0"] = {"offset": write(col[vsel]), "components": 4}
                    idx = inv.reshape(-1).astype(np.uint32)
                    ioff = write(idx)
                    meshes.append({"name": safe_name(f"{obj.name}__{mname}") if len(np.unique(mat_idx)) > 1 else safe_name(obj.name), "material": mname, "bin": "geometry.bin",
                                   "vertex_count": int(len(vsel)), "index_count": int(len(idx)),
                                   "arrays": arrays, "indices_offset": ioff})

                    if mname not in materials:
                        entry = {"name": mname, "template": None, "textures": {}, "alpha": False}
                        if bmat is None:
                            tname = "mk8exp_default_col"
                            if tname not in textures:
                                rel = os.path.join("textures", tname + ".rgba")
                                save_solid_rgba((204, 204, 204, 255), os.path.join(out_dir, rel))
                                textures[tname] = {"name": tname, "file": rel, "format": "BC1_SRGB", "srgb": True, "mips": True}
                            entry["textures"]["albedo"] = tname
                        if bmat:
                            bcol, entry["alpha"] = base_color_and_alpha(bmat)
                            s = bmat.mk8dx
                            if s.template and s.template != "NONE":
                                entry["template"] = s.template
                            img, w = find_albedo_image(bmat)
                            warnings += w
                            keep_orig = False
                            if s.bfmat_path:
                                bp = os.path.normpath(bpy.path.abspath(s.bfmat_path))
                                if os.path.isfile(bp):
                                    entry["bfmat"] = bp
                                    try:
                                        info = json.loads(s.bfmat_info or "{}")
                                    except Exception:
                                        info = {}
                                    entry["texture_sources"] = [p for p in info.get("texture_sources", [])
                                                                if os.path.isfile(p) or os.path.isdir(p[:-3] if p.endswith(("/**", "\\**")) else p)]
                                    alb = next((t for t in info.get("textures", []) if t.get("sampler") == "_a0"), None)
                                    # unchanged imported albedo (or none) + original still available -> keep the original texture
                                    keep_orig = (img is None or (img == s.bfmat_albedo and not img.is_dirty)) and bool(entry["texture_sources"]) and bool(alb and alb.get("found"))
                                else:
                                    warnings.append(f"Material '{bmat.name}': linked .bfmat not found ({bp}); using the normal template choice.")
                            if keep_orig:
                                pass
                            elif img:
                                tname = safe_name(img.name)
                                if tname not in textures:
                                    rel = os.path.join("textures", tname + ".rgba")
                                    save_image_rgba(img, os.path.join(out_dir, rel))
                                    textures[tname] = {"name": tname, "file": rel, "format": s.tex_format,
                                                       "srgb": True, "mips": True}
                                entry["textures"]["albedo"] = tname
                            else:
                                # no image: bake the Base Color into a small solid texture so the material still has its colour
                                tname = safe_name(mname) + "_col"
                                rel = os.path.join("textures", tname + ".rgba")
                                save_solid_rgba(bcol, os.path.join(out_dir, rel))
                                textures[tname] = {"name": tname, "file": rel, "format": "BC1_SRGB", "srgb": True, "mips": True}
                                entry["textures"]["albedo"] = tname
                                warnings.append(f"Material '{bmat.name}' has no image texture; using its Base Color as a solid texture.")
                        materials[mname] = entry
            finally:
                ev.to_mesh_clear()
    if not meshes:
        raise RuntimeError("The selected objects contain no faces.")
    return meshes, list(materials.values()), list(textures.values()), warnings
