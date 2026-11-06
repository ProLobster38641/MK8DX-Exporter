# Architecture

```
Blender add-on (Python, addon/mk8dx_szs_exporter)
  gather.py     evaluated meshes (modifiers applied) -> per (object, material) shapes; Z-up -> Y-up; V flip;
                images -> raw RGBA (.rgba); writes export folder: export.json + geometry.bin + textures/
  operators.py  export dialog, Ryujinx path logic, "Load Original Materials" (runs `mk8szs materials --json`)
  props/panels  per-material template choice, texture format; N-panel
  cli.py        runs bin/mk8szs(.exe)

mk8szs CLI (C# .NET 8, single-file self-contained, cli/Mk8SzsTool)
  Formats/      SHARED read+write layer (used by both export and import)
    Yaz0.cs        decompress + compress
    Sarc.cs        read + write (not needed for course_model.szs; ready for other course files)
    BfresIO.cs     load .szs/.bfres (Yaz0/SARC-aware), save (+Yaz0)
    BntxTextures.cs create BNTX textures (BC1/BC3/RGBA8, mips, Tegra X1 block-linear swizzle), decode back
    BcCodec.cs     BC1/BC3 encode + decode
    ImageIO.cs     PNG/JPG/TGA (StbImageSharp) + raw .rgba; gamma-correct mip downsampling
  Materials/MaterialTemplates.cs  READ (list/describe/extract .bfmat) + WRITE (clone, retarget samplers)
  Export/       Manifest (interchange schema) + CourseBuilder (base file -> cloned materials -> model -> BNTX)
  Import/       CourseImporter: .szs -> same manifest schema + geometry.bin + .rgba + materials.json
  Commands/     info, test template
  Program.cs    command dispatch: export | import | materials | extract-bfmat | info | decode-texture | yaz0-d/-c
```

## Import roadmap (planned follow-up)
`mk8szs import` already writes an `import.json` in the same schema the exporter reads, plus decoded textures and full material descriptions. The Blender side still to do:
1. `File > Import > MK8DX course_model (.szs)`: run `mk8szs import` into a temp folder.
2. Build meshes from geometry.bin (Y-up -> Z-up, flip V back), and images from .rgba.
3. Create Blender materials with Image Texture -> Base Color, and set `material.mk8dx.template` to the original material name, so re-export clones the exact same shader setup (a lossless round trip of materials).
4. Optional: BC4/BC5/BC7/ASTC decode for the remaining texture formats (only BC1/BC3/RGBA8 decode today).


## Collision (v1.2)
- `addon/collision.py`: object role (visual / collision / both), per-face INT attribute `mk8dx_col` (-1 = object type), toolbar WorkSpaceTool + N-panel, KCL gather (Z-up -> Y-up, same scale as the model).
- `addon/coltypes.py`: flag table (type + variant*0x20 + special flags).
- `cli/Collision/KclIO.cs`: KclLibrary -> KCL Version2 little endian, Yaz0 (`kcl-export`, `kcl-info --hit-test`, `kcl-dump`; dump is groundwork for a KCL importer).
- Model export skips collision-only objects and ignores the `MK8DX_Collision` display colour attribute.

## Material import + placeholder
- `cli/Import/MaterialImport.cs` (`mat-import`): .bfmat / .szs materials -> .bfmat copies + decoded textures (`Formats/TextureSource.cs` reads .szs/.bfres/.bntx). Groundwork for the full importer.
- `addon/importer.py`: builds Principled BSDF materials, links `mk8dx.bfmat_path`; export clones that .bfmat (`MaterialEntry.bfmat`) and copies original textures from `texture_sources`.
- `addon/placeholder.py`: start grid markers flagged `mk8dx_placeholder`; skipped by both exporters; deleting the empty removes the grid.

## Release 1.0.0 template and shader handling
The model export dialog binds directly to SceneSettings.template_file (the same property as the N-panel).
Its value is saved with the dialog options; an explicitly cleared or edited field is never overwritten by
stale saved settings. A blank field resolves after destinations are validated: the current course output,
then its .orig sidecar. Building completes in a temporary directory before any model output is replaced.
Existing model destinations are backed up once, including browser-only overwrites.

Shader adaptation logs INFO detail plus one summary, not a Blender WARNING. The base's original materials
remain authoritative; a matching known option set is preserved. A byte-identical Turbo_UBER.bfsha permits
adding known variants from an original sidecar or another template .szs, without trusting unrelated courses.

## Collision preview
`collision_preview.py` draws evaluated per-face collision colours through a cached, depth-tested viewport
GPU overlay on a neutral, flat Solid background. Materials/textures are not used. It does not change
active vertex-colour layers, material slots, object display colours or mesh data. Linked mesh objects
are evaluated separately for their object collision defaults. Each viewport saves/restores its own
changed shading properties; disabling the add-on or loading another file cleans up the draw handler.

## Release 1.1.0 lighting defaults
Neutral extra maps are selected after shader-variation adaptation, using shader sampler assignments
rather than physical slot names. `_b0` is white (unoccluded AO/shadows); `_b1` is black
(zero additive baked light). Normal defaults use exact RGBA8 UNORM data: unsigned mid-grey
when `gsys_normalmap_BC1=1`, zero XY when the shader expects signed-style normal samples.
Reserved defaults are regenerated on re-export. Course lighting options and environment bindings stay intact.
Automatic template scoring penalizes emissive, unlit, multi-texture and reflection/shadow-only helpers.

Imported materials store their source name separately from the visible missing-texture suffix.
Missing texture slots remain empty and do not prevent other slots or materials importing.
Re-import updates the same datablock and clears the marker when the missing textures are supplied.
