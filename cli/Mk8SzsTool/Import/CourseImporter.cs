using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using BfresLibrary;
using BfresLibrary.Helpers;
using BfresLibrary.Switch;
using Mk8SzsTool.Export;
using Mk8SzsTool.Formats;
using Mk8SzsTool.Materials;

namespace Mk8SzsTool.Import
{
    /// <summary>
    /// Reverse of the exporter: .szs/.bfres -> manifest (export.json-compatible) + geometry.bin + textures (.rgba)
    /// + materials.json. The Blender side of import is the planned follow-up (see README "Import roadmap").
    /// </summary>
    public static class CourseImporter
    {
        public static Manifest Run(string input, string outDir, Action<string> log)
        {
            Directory.CreateDirectory(outDir);
            var res = BfresIO.Load(input);
            var man = new Manifest { Base = Path.GetFullPath(input), Mode = "replace" };
            var bin = new BinaryWriter(File.Create(Path.Combine(outDir, "geometry.bin")));
            try
            {
                foreach (var model in res.Models.Values)
                {
                    man.ModelName = model.Name;
                    foreach (var mat in model.Materials.Values)
                    {
                        var info = MaterialTemplates.Describe(model, mat);
                        man.Materials.Add(new MaterialEntry { Name = mat.Name, Template = mat.Name, Textures = info.Samplers });
                    }
                    foreach (var shape in model.Shapes.Values)
                    {
                        var vb = model.VertexBuffers[shape.VertexBufferIndex];
                        var h = new VertexBufferHelper(vb, res.ByteOrder);
                        var me = new MeshEntry { Name = shape.Name, Material = model.Materials[shape.MaterialIndex].Name, Bin = "geometry.bin", VertexCount = (int)vb.VertexCount };
                        void Put(string attr, string key, int comps)
                        {
                            if (!h.Contains(attr)) return;
                            me.Arrays[key] = new ArrayRef { Offset = bin.BaseStream.Position, Components = comps };
                            foreach (var v in h[attr].Data)
                            {
                                bin.Write(v.X); if (comps > 1) bin.Write(v.Y); if (comps > 2) bin.Write(v.Z); if (comps > 3) bin.Write(v.W);
                            }
                        }
                        Put("_p0", "position", 3); Put("_n0", "normal", 3); Put("_t0", "tangent", 4); Put("_c0", "color0", 4);
                        for (int k = 0; k < 4; k++) Put("_u" + k, "uv" + k, 2);
                        var lod0 = shape.Meshes[0];
                        var idx = lod0.GetIndices().Select(i => i + lod0.FirstVertex).ToArray();
                        me.IndicesOffset = bin.BaseStream.Position; me.IndexCount = idx.Length;
                        foreach (var i in idx) bin.Write(i);
                        man.Meshes.Add(me);
                    }
                }
            }
            finally { bin.Dispose(); }

            Directory.CreateDirectory(Path.Combine(outDir, "textures"));
            foreach (var kv in res.Textures)
            {
                if (kv.Value is not SwitchTexture st) continue;
                var img = BntxTextures.DecodeToRgba(st);
                if (img == null) { log($"Texture {kv.Key}: format {st.Texture.Format} not decodable yet (skipped)"); continue; }
                string f = Path.Combine("textures", kv.Key + ".rgba");
                ImageIO.SaveRaw(Path.Combine(outDir, f), img);
                man.Textures.Add(new TextureEntry { Name = kv.Key, File = f, Format = st.Texture.Format.ToString() });
            }
            File.WriteAllText(Path.Combine(outDir, "import.json"), JsonSerializer.Serialize(man, new JsonSerializerOptions { WriteIndented = true }));
            File.WriteAllText(Path.Combine(outDir, "materials.json"), JsonSerializer.Serialize(MaterialTemplates.List(res), new JsonSerializerOptions { WriteIndented = true }));
            log($"Imported {man.Meshes.Count} shapes, {man.Materials.Count} materials, {man.Textures.Count} textures -> {outDir}");
            return man;
        }
    }
}
