using BfresLibrary;
using BfresLibrary.Switch;
using Mk8SzsTool.Formats;
using Mk8SzsTool.Materials;

namespace Mk8SzsTool.Import
{
    /// <summary>bfmat / .szs materials -> .bfmat copies + decoded textures (.rgba) + JSON description for the Blender importer.</summary>
    public static class MaterialImport
    {
        public static List<object> Run(List<string> bfmats, string? szs, HashSet<string>? only, List<string> texSources, string outDir, List<string> warns)
        {
            Directory.CreateDirectory(outDir);
            Directory.CreateDirectory(Path.Combine(outDir, "textures"));
            var mats = new List<(Material m, string bfmat, string? model)>();
            var pool = new TexturePool();
            if (szs != null)
            {
                var res = BfresIO.Load(szs);
                foreach (var model in res.Models.Values)
                    foreach (var m in model.Materials.Values)
                    {
                        if (only != null && !only.Contains(m.Name)) continue;
                        if (mats.Any(x => x.m.Name == m.Name)) continue;
                        string p = Path.Combine(outDir, Safe(m.Name) + ".bfmat");
                        m.Export(p, res);
                        mats.Add((m, p, model.Name));
                    }
            }
            foreach (var bf in bfmats)
            {
                var m = MaterialTemplates.ImportBfmat(bf, new ResFile(true));
                string name = Path.GetFileNameWithoutExtension(bf);
                string p = Path.Combine(outDir, Safe(name) + ".bfmat");
                if (Path.GetFullPath(p) != Path.GetFullPath(bf)) File.Copy(bf, p, true);
                m.Name = name;
                mats.Add((m, p, null));
            }
            foreach (var s in texSources) pool.Add(s);      // dialog folder/file first, then template
            if (szs != null) pool.Add(szs);
            string where = pool.Labels.Any() ? string.Join("; ", pool.Labels) : "(no texture source set)";

            var result = new List<object>();
            foreach (var (m, bfmat, model) in mats)
            {
                var info = MaterialTemplates.Describe(null, m);
                string albedo = MaterialTemplates.AlbedoSampler(m);
                var texs = new List<object>();
                var srcs = new HashSet<string>();
                for (int i = 0; i < m.Samplers.Count; i++)
                {
                    string samp = m.Samplers.GetKey(i), tn = i < m.TextureRefs.Count ? m.TextureRefs[i].Name : "";
                    string? file = null, fmt = null, note = null;
                    var ft = pool.Find(tn);
                    if (ft != null)
                    {
                        fmt = ft.Format;
                        srcs.Add(ft.Native != null && !ft.Origin.EndsWith(".bftex", StringComparison.OrdinalIgnoreCase) && File.Exists(ft.Origin) ? ft.Origin : SourceSpecFor(ft.Origin, texSources));
                        if (samp == albedo || samp.StartsWith("_n"))
                        {
                            var img = TexturePool.Decode(ft);
                            if (img != null) { file = Path.Combine(outDir, "textures", Safe(tn) + ".rgba"); ImageIO.SaveRaw(file, img); }
                            else note = $"format {fmt} not decodable (kept as reference; exported unchanged)";
                        }
                        note ??= "from " + ft.Origin;
                    }
                    else if (!string.IsNullOrEmpty(tn))
                        note = pool.Duplicates.Contains(tn) ? "skipped: duplicate files with this name in the texture source" : $"not found; looked in: {where}";
                    texs.Add(new { sampler = samp, texture = tn, file, format = fmt, found = fmt != null, duplicate = pool.Duplicates.Contains(tn), note, albedo = samp == albedo });
                }
                result.Add(new { name = m.Name, model, bfmat = Path.GetFullPath(bfmat), shading_model = info.ShadingModel, has_alpha = info.HasAlpha,
                                 render_info = info.RenderInfo, textures = texs, texture_sources = srcs.ToList() });
            }
            warns.AddRange(pool.Warnings.Select(w => "WARNING: " + w));
            return result;
        }

        /// <summary>The source spec (folder, maybe "/**") a folder-found file came from, so export can find it again.</summary>
        static string SourceSpecFor(string file, List<string> specs)
        {
            foreach (var sp in specs)
            {
                string d = sp.EndsWith("/**") || sp.EndsWith("\\**") ? sp[..^3] : sp;
                if (Directory.Exists(d) && Path.GetFullPath(file).StartsWith(Path.GetFullPath(d), StringComparison.OrdinalIgnoreCase)) return sp;
            }
            return file;
        }

        static string Safe(string s) => string.Concat(s.Select(c => Path.GetInvalidFileNameChars().Contains(c) || c == '/' || c == '\\' ? '_' : c));
    }
}
