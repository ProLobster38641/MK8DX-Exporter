# MK8DX course_model.szs exporter for Blender 4.2+ / 5.0
# Blender side: collects evaluated meshes (modifiers applied), UVs, materials, textures -> export folder.
# Backend: bundled mk8szs CLI (C#, BfresLibrary) builds the Switch BFRES + BNTX and Yaz0-compresses it.

bl_info = {
    "name": "MK8DX SZS Exporter",
    "author": "MK8DX SZS Exporter contributors",
    "version": (1, 1, 0),
    "blender": (4, 2, 0),
    "location": "File > Export > MK8DX course_model / collision; File > Import > MK8DX material; 3D View toolbar > MK8DX Collision; N-panel > MK8DX",
    "description": "Export meshes to Mario Kart 8 Deluxe (Switch) course_model.szs and course_kcl.szs",
    "category": "Import-Export",
}

from . import prefs, props, cli, operators, panels, collision, importer, placeholder

modules = (prefs, props, collision, operators, importer, placeholder, panels)


def register():
    for m in modules:
        m.register()


def unregister():
    for m in reversed(modules):
        m.unregister()
