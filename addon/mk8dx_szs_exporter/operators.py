import json
import os
import shutil
import tempfile
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from . import cli, gather, files


def romfs_template(context):
    """Shortcut: <RomFS>/course/<Course folder>/course_model.szs, or '' (never raises)."""
    try:
        p = cli.addon_prefs(context)
        sc = context.scene.mk8dx
        if p and p.romfs_dir and sc.gu_folder:
            cand = os.path.join(romfs_course_dir(p.romfs_dir), sc.gu_folder, "course_model.szs")
            for c in (cand + ".orig", cand):
                if os.path.isfile(c):
                    return c
    except Exception:
        pass
    return ""


def resolve_template(context):
    """Template source: the picked file if it exists, else the RomFS shortcut, else ''."""
    try:
        f = context.scene.mk8dx.template_file
        if f:
            f = files.norm(f)
            if os.path.isfile(f + ".orig"):   # we replaced it earlier: keep cloning from the untouched original
                return f + ".orig"
            if os.path.isfile(f):
                return f
    except Exception:
        pass
    return romfs_template(context)


# kept name for older callers
resolve_base = resolve_template


def course_name(context):
    """Course folder: taken from the template path when it sits in .../course/Gu_xxx/, else the Course field."""
    sc = context.scene.mk8dx
    tpl = resolve_template(context)
    return files.course_from_path(tpl) or sc.gu_folder


def course_target(context, kind, custom_root="", fname="course_model.szs"):
    """Optional course-folder destination, or '' when it can't be built."""
    sc = context.scene.mk8dx
    gu = course_name(context)
    p = cli.addon_prefs(context)
    if kind == "TEMPLATE":
        tpl = resolve_template(context)
        if tpl and not tpl.lower().endswith(".bfmat"):
            return os.path.join(os.path.dirname(files.norm(tpl)), fname)
        return ""
    if not gu:
        return ""
    if kind == "RYUJINX":
        if not (p and p.ryujinx_dir and sc.mod_name):
            return ""
        return os.path.join(files.norm(p.ryujinx_dir), "mods", "contents", "0100152000022000",
                            sc.mod_name.strip(), "romfs", "course", gu, fname)
    if kind == "ROMFS":
        root = custom_root or (p.romfs_dir if p else "")
        if root:
            return os.path.join(romfs_course_dir(root), gu, fname)
    return ""


def romfs_course_dir(root):
    """Existing 'course' folder of a RomFS. Accepts the romfs folder itself or its parent. Never creates anything."""
    r = files.norm(root)
    for c in (os.path.join(r, "course"), os.path.join(r, "romfs", "course")):
        if os.path.isdir(c):
            return c
    if os.path.basename(r).lower() == "course" and os.path.isdir(r):
        return r
    return os.path.join(r, "course")   # doesn't exist: make_targets reports it


def ryujinx_target(context):
    return course_target(context, "RYUJINX")


class MK8DX_OT_load_materials(bpy.types.Operator):
    """Read the material list from the original course_model.szs so you can pick templates per material"""
    bl_idname = "mk8dx.load_materials"
    bl_label = "Load Original Materials"

    filepath: StringProperty(subtype="FILE_PATH", default="")

    def execute(self, context):
        path = cli.bpy_abspath(self.filepath) if self.filepath else resolve_template(context)
        if not path or not os.path.isfile(path):
            self.report({"WARNING"}, "No template file: pick one in the MK8DX panel (any MK8DX .szs or .bfmat), or set RomFS folder + Course folder.")
            return {"CANCELLED"}
        try:
            mats = cli.list_materials(context, path)
        except Exception as e:
            self.report({"ERROR"}, f"Could not read materials: {e}")
            return {"CANCELLED"}
        context.scene.mk8dx.materials_json = json.dumps(mats)
        context.scene.mk8dx.materials_source = path
        self.report({"INFO"}, f"Loaded {len(mats)} materials from {os.path.basename(path)}")
        return {"FINISHED"}


def default_template_items(self, context):
    from .props import template_items
    items = template_items(self, context)
    return [("NONE", "Automatic (recommended)", "Each Blender material clones a plain opaque material from the template (an alpha one if its texture/material has transparency)")] + items[1:]


MODEL_OPTS = ("use_selection", "scale", "export_uv1", "with_kcl", "course_dest", "course_kind", "course_root", "mode",
              "neutral_other", "force_repeat", "prune", "keep_anims", "template_file")


def _opt_store(context):
    p = cli.addon_prefs(context)
    return [context.scene.mk8dx, p] if p else [context.scene.mk8dx]


def load_opts(op, context, keys):
    """Restore last-used dialog options: this .blend's scene first, else the add-on preferences (other .blend files)."""
    for store in _opt_store(context):
        try:
            d = json.loads(store.export_opts or "{}").get(op.bl_idname, {})
        except Exception:
            d = {}
        if d:
            for k in keys:
                if k in d:
                    try:
                        if k == "template_file":
                            # The panel and dialog share one scene property. Never overwrite a panel edit
                            # (including an explicitly cleared field) with stale last-export settings.
                            if not context.scene.mk8dx.is_property_set(k):
                                context.scene.mk8dx.template_file = d[k]
                        else:
                            setattr(op, k, d[k])
                    except Exception:
                        pass
            return


def save_opts(op, context, keys):
    for store in _opt_store(context):
        try:
            d = json.loads(store.export_opts or "{}")
        except Exception:
            d = {}
        d[op.bl_idname] = {k: getattr(context.scene.mk8dx if k == "template_file" else op, k) for k in keys}
        try:
            store.export_opts = json.dumps(d)
        except Exception:
            pass


def make_targets(op, context, fname):
    """List of absolute output paths (browser file and/or course folder), or an error string."""
    targets = []
    if op.course_dest != "INSTEAD":
        fp = files.norm(op.filepath) if op.filepath else ""
        if not fp or os.path.isdir(fp) or not os.path.basename(fp):
            fp = os.path.join(fp or os.path.expanduser("~"), fname)
        if not os.path.splitext(fp)[1]:
            fp += ".szs"
        targets.append(fp)
    if op.course_dest != "NONE":
        ct = course_target(context, op.course_kind, op.course_root, fname)
        if not ct and op.course_kind == "TEMPLATE" and not context.scene.mk8dx.template_file.strip() and op.filepath:
            # With no explicit template, the file browser supplies the existing course folder.
            ct = os.path.join(os.path.dirname(files.norm(op.filepath)), fname)
        if ct and op.course_kind in ("ROMFS", "TEMPLATE"):
            # edit an existing RomFS only: never create romfs/, course/ or Gu_* folders
            d = os.path.dirname(ct)
            if not os.path.isdir(d):
                return f"Course folder not found: {d}. The RomFS destination only edits an existing RomFS (point it at your romfs folder or its parent; check the Course name). Nothing was exported."
            if not os.path.isfile(ct) and not (fname == "course_model.szs" and os.path.isfile(ct + ".orig")):
                return f"{ct} does not exist, so this is not an existing course folder to replace into. Nothing was exported."
        if ct:
            targets.append(ct)
        elif op.course_dest == "INSTEAD":
            return "Course-folder destination is incomplete (Course folder / Mod name / Ryujinx or RomFS root). Fill it in or choose 'Off'. Nothing was exported."
        else:
            return "Course-folder destination is incomplete (see the dialog). Fill it in or set 'Course folder' to Off. Nothing was exported."
    seen, uniq = set(), []
    for t in (os.path.abspath(t) for t in targets):
        if os.path.normcase(t) not in seen:
            seen.add(os.path.normcase(t)); uniq.append(t)
    targets = uniq
    return targets


def export_template(context, targets, course_dest="NONE"):
    """Select the source before building/writing anything. Blank means the actual output, not RomFS prefs."""
    explicit = context.scene.mk8dx.template_file.strip()
    if explicit:
        path = files.norm(explicit)
        # Preserve the explicit-template shortcut's original-backup behaviour.
        for cand in (path + ".orig", path):
            if os.path.isfile(cand):
                return cand, "explicit template"
        raise ValueError(f"Template file not found: {path}. Pick an existing .szs/.bfmat or clear the field to use the destination.")
    target = targets[-1] if course_dest != "NONE" else targets[0]
    for cand, why in ((target, "destination file"), (target + ".orig", "destination backup")):
        if os.path.isfile(cand):
            return cand, why
    return "", f"No template: neither {target} nor {target}.orig exists. Choose a Template file (.szs/.bfmat) in this export dialog for the first export."


def report_export_notes(op, warns, stdout):
    """Real warnings remain warnings; expected shader adaptation is a single informational report."""
    for w in warns + [ln for ln in stdout.splitlines() if ln.startswith("WARNING")]:
        op.report({"WARNING"}, w)
    for ln in stdout.splitlines():
        if ln.startswith("INFO: Adjusted "):
            op.report({"INFO"}, ln[6:])
            break


def place_outputs(op, built, targets, log_text, backup_all=False):
    """Write built file to every target (safe replace + verify). Returns list of written paths, or None after reporting errors."""
    written, failed = [], []
    for t in targets:
        is_course = op.course_dest != "NONE" and t == targets[-1]
        ok, msg = files.place(built, t, backup_original=is_course or backup_all,
                              create_dirs=not (is_course and op.course_kind in ("ROMFS", "TEMPLATE")))
        (written if ok else failed).append(msg)
    report = [f"written: {w} ({os.path.getsize(w)} bytes)" for w in written] + [f"FAILED: {f}" for f in failed]
    for w in written:
        try:
            with open(os.path.splitext(w)[0] + "_export_log.txt", "w") as f:
                f.write(log_text + "\n" + "\n".join(report) + "\n")
        except OSError:
            pass
    for line in report:
        print("MK8DX", line)
    if failed:
        for f in failed:
            op.report({"ERROR"}, "Export NOT saved: " + f)
        if written:
            op.report({"WARNING"}, "Saved only to: " + " ; ".join(written))
        return None
    return written


class MK8DX_OT_export(bpy.types.Operator, ExportHelper):
    """Export to a Mario Kart 8 Deluxe course_model.szs (Switch BFRES, Yaz0)"""
    bl_idname = "mk8dx.export_szs"
    bl_label = "Export MK8DX course_model.szs"
    bl_options = {"PRESET"}

    filename_ext = ".szs"
    filter_glob: StringProperty(default="*.szs;*.bfres", options={"HIDDEN"})

    filepath: StringProperty(subtype="FILE_PATH", default="course_model.szs")
    course_dest: EnumProperty(name="Course folder", default="NONE", items=[
        ("NONE", "Off (only the file above)", "Just save the file you chose in the browser"),
        ("ALSO", "Also save to course folder", "Save the chosen file AND a copy into the course folder below"),
        ("INSTEAD", "Save only to course folder", "Ignore the browser file name and save into the course folder below")])
    course_kind: EnumProperty(name="Destination", default="TEMPLATE", items=[
        ("TEMPLATE", "Template's course folder (replace)", "Overwrite course_model.szs in the folder of the template file (e.g. your dump's romfs/course/Gu_Expert). The original is backed up once as course_model.szs.orig"),
        ("RYUJINX", "Ryujinx mod folder (creates mod folders)", "<Ryujinx>/mods/contents/0100152000022000/<Mod name>/romfs/course/<Course>/course_model.szs"),
        ("ROMFS", "Existing RomFS (replace)", "Replace course_model.szs in an existing <romfs>/course/<Course>/ folder (defaults to the RomFS folder in preferences). Never creates folders")])
    course_root: StringProperty(name="Existing RomFS folder", subtype="DIR_PATH", default="",
                                description="Folder that contains (or will contain) 'course', e.g. a mod's romfs folder")
    use_selection: BoolProperty(name="Selected only", default=True)
    scale: FloatProperty(name="Scale", default=1.0, min=0.0001, soft_max=1000,
                         description="Blender units -> MK8 units. Compare with an original track to find the right value")
    export_uv1: BoolProperty(name="Export 2nd UV map as _u1", default=True,
                             description="If an object has a 2nd UV map, use it for the shadow/bake UV channel (else UV 1 is reused)")
    mode: EnumProperty(name="Mode", default="replace", items=[
        ("replace", "Replace template models", "Output contains only your meshes (template file models are dropped; its header/textures are reused)"),
        ("append", "Add to template models", "Keep the template file models and add your meshes")])
    default_template: EnumProperty(name="Default template", items=default_template_items,
                                   description="Original material cloned for Blender materials without their own choice")
    neutral_other: BoolProperty(name="Neutral extra maps", default=True,
                                description="Use unshadowed AO, zero added baked light, flat normals and no specular/emission maps; keep normal course lighting. Disable only to keep the template's maps with matching bake UVs")
    force_repeat: BoolProperty(name="Repeat (tile) textures", default=True, description="Set the albedo sampler to wrap/repeat")
    prune: BoolProperty(name="Remove unused original textures", default=True)
    keep_anims: BoolProperty(name="Keep template animations", default=True,
                             description="Keep the template's material animations (scrolling water, dash panels) and the textures they use. Safest default")
    allow_synthetic: BoolProperty(name="Allow test material (no original)", default=False,
                                  description="Developer option: write a placeholder material when no original course is available. Does NOT render in-game")
    keep_temp: BoolProperty(name="Keep export folder (debug)", default=False)
    with_kcl: BoolProperty(name="Also export collision (course_kcl.szs)", default=False,
                           description="Also write course_kcl.szs from your collision objects, next to the model file and to the same course folder")
    extra_template: StringProperty(name="Extra template (.bfmat/.szs)", subtype="FILE_PATH", default="",
                                   description="Optional: a .bfmat exported from Switch Toolbox (or another MK8DX .szs) to clone materials from. "
                                               "A .bfmat named like a material's template is used for it; otherwise the first .bfmat is the default")

    def invoke(self, context, event):
        load_opts(self, context, MODEL_OPTS)
        if not self.filepath or os.path.basename(self.filepath) == "":
            self.filepath = "course_model.szs"
        return super().invoke(context, event)

    def draw(self, context):
        l = self.layout
        sc = context.scene.mk8dx
        box = l.box()
        box.label(text="Template file (.szs/.bfmat)")
        box.prop(sc, "template_file", text="")
        box.label(text="Blank: use the destination file, then its .orig backup", icon="INFO")
        box.prop(self, "extra_template")
        box = l.box()
        box.label(text="Optional course-folder copy")
        box.prop(self, "course_dest", text="")
        if self.course_dest != "NONE":
            box.prop(self, "course_kind")
            if self.course_kind == "ROMFS":
                box.prop(self, "course_root")
            if self.course_kind != "TEMPLATE":
                box.prop(sc, "gu_folder")
                gu = course_name(context)
                if gu != sc.gu_folder:
                    box.label(text=f"Course from template path: {gu}", icon="INFO")
            if self.course_kind == "RYUJINX":
                box.prop(sc, "mod_name")
            tgt = course_target(context, self.course_kind, self.course_root)
            box.label(text=tgt if tgt else "Destination incomplete (it will be skipped)", icon="FILE_FOLDER" if tgt else "ERROR")
        box = l.box()
        box.label(text="Geometry")
        box.prop(self, "use_selection"); box.prop(self, "scale"); box.prop(self, "export_uv1")
        box.prop(self, "with_kcl")
        box = l.box()
        box.label(text="Materials")
        box.prop(self, "mode"); box.prop(self, "default_template")
        box.prop(self, "neutral_other"); box.prop(self, "force_repeat"); box.prop(self, "prune"); box.prop(self, "keep_anims")
        box = l.box()
        box.label(text="Advanced")
        box.prop(self, "allow_synthetic"); box.prop(self, "keep_temp")

    def execute(self, context):
        save_opts(self, context, MODEL_OPTS)
        targets = make_targets(self, context, "course_model.szs")
        if isinstance(targets, str):
            self.report({"ERROR"}, targets)
            return {"CANCELLED"}
        out = targets[0]

        try:
            tpl, template_note = export_template(context, targets, self.course_dest)
        except ValueError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        extra = cli.bpy_abspath(self.extra_template) if self.extra_template else ""
        if extra and not os.path.isfile(extra):
            self.report({"ERROR"}, f"Extra template file not found: {extra}")
            return {"CANCELLED"}
        templates = [t for t in (tpl, extra) if t]
        # an .szs/.bfres template is also the base file (keeps MK8DX header/version); a .bfmat is not
        base = next((t for t in templates if not t.lower().endswith(".bfmat")), "")
        if not base and templates:
            dest = targets[-1] if self.course_dest != "NONE" else targets[0]
            base = next((t for t in (dest, dest + ".orig") if os.path.isfile(t)), "")
        template_log = f"Template used ({template_note}): {tpl or extra or '(synthetic test)'}\n"
        if base and base not in templates:
            template_log += f"Shader archive base (destination): {base}\n"
        if not templates and not self.allow_synthetic:
            self.report({"ERROR"}, template_note)
            return {"CANCELLED"}
        if bpy.context.object and bpy.context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        work = tempfile.mkdtemp(prefix="mk8dx_export_")
        t0 = time.time()
        try:
            meshes, mats, texs, warns = gather.collect(context, work, self.use_selection, self.scale, self.export_uv1)
            man = {
                "version": 1, "model_name": "", "base": base or None, "template_files": [t for t in templates if t != base],
                "mode": self.mode, "keep_animations": self.keep_anims, "prune_textures": self.prune,
                "neutral_other_samplers": self.neutral_other, "force_repeat": self.force_repeat,
                "allow_synthetic": self.allow_synthetic,
                "default_template": None if self.default_template == "NONE" else self.default_template,
                "textures": texs, "materials": mats, "meshes": meshes,
            }
            # default_template None -> the CLI auto-picks a plain opaque (or alpha) material per Blender material
            with open(os.path.join(work, "export.json"), "w") as f:
                json.dump(man, f, indent=1)
            built = os.path.join(work, "course_model.szs")
            code, so, se = cli.run(context, ["export", os.path.join(work, "export.json"), built])
            so = template_log + so
            log_path = os.path.splitext(out)[0] + "_export_log.txt"
            try:
                with open(log_path, "w") as f:
                    f.write("\n".join(warns) + "\n" + so + "\n" + se)
            except OSError:
                pass
            if code != 0:
                msg = next((ln for ln in (se or so).splitlines() if ln.startswith("ERROR")), (se or so).strip()[:300])
                self.report({"ERROR"}, f"Export failed: {msg}  (details: {log_path})")
                return {"CANCELLED"}
            report_export_notes(self, warns, so)
            if not os.path.isfile(built) or os.path.getsize(built) == 0:
                self.report({"ERROR"}, f"Export failed: the tool reported success but wrote no file (details: {log_path})")
                return {"CANCELLED"}
            written = place_outputs(self, built, targets, "\n".join(warns) + "\n" + so + "\n" + se, backup_all=True)
            if written is None:
                return {"CANCELLED"}
            if self.with_kcl:
                from . import collision
                kop = collision.Proxy(self, filepath=os.path.join(os.path.dirname(written[0]), "course_kcl.szs")
                                      if self.course_dest != "INSTEAD" else "")
                kw = collision.export_kcl(kop, context, self.use_selection, self.scale)
                if kw is None:
                    self.report({"ERROR"}, "Model saved to " + " ; ".join(written) + ", but collision export FAILED (see above)")
                    return {"CANCELLED"}
                written += kw
            self.report({"INFO"}, f"Exported {len(meshes)} meshes, {len(mats)} materials, {len(texs)} textures. Saved to: " + " ; ".join(written) + f"  ({time.time()-t0:.1f}s)")
            return {"FINISHED"}
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({"ERROR"}, f"Export failed: {e}")
            return {"CANCELLED"}
        finally:
            if not self.keep_temp:
                shutil.rmtree(work, ignore_errors=True)
            else:
                print("MK8DX export folder kept at", work)


def menu_func(self, context):
    self.layout.operator(MK8DX_OT_export.bl_idname, text="MK8DX course_model (.szs)")


classes = (MK8DX_OT_load_materials, MK8DX_OT_export)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.TOPBAR_MT_file_export.append(menu_func)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
