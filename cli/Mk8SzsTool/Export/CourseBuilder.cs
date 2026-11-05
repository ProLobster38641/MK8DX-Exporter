using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using BfresLibrary;
using BfresLibrary.GX2;
using BfresLibrary.Helpers;
using Mk8SzsTool.Formats;
using Mk8SzsTool.Materials;
using Syroot.Maths;

namespace Mk8SzsTool.Export
{
    public class CourseBuilder
    {
        readonly Manifest man; readonly string dir; readonly Action<string> log;
        public List<string> Warnings { get; } = new();

        public CourseBuilder(Manifest m, string manifestDir, Action<string> logger) { man = m; dir = manifestDir; log = logger; }

        string Abs(string p) => Path.IsPathRooted(p) ? p : Path.Combine(dir, p);
        void Warn(string s) { Warnings.Add(s); log("WARNING: " + s); }

        public ResFile Build()
        {
            // 1. Base file: the user's original course_model.szs (keeps MK8DX header/version/textures/shader setup).
            ResFile res;
            List<ShaderVariants.Variant>? baseVariants = null;
            var templateSources = new List<ResFile>();
            var bfmats = new List<string>();
            if (!string.IsNullOrEmpty(man.Base))
            {
                log($"Loading base: {man.Base}");
                res = BfresIO.Load(Abs(man.Base));
                if (!res.IsPlatformSwitch) throw new InvalidDataException("Base file is a Wii U BFRES. Use the MK8 Deluxe (Switch) course_model.szs.");
                templateSources.Add(res);
                baseVariants = ShaderVariants.Collect(res);
                // Re-exported destinations only retain their used materials. The untouched sidecar
                // can supply other known-good variations, but only for the exact same archive.
                string original = Abs(man.Base) + ".orig";
                if (File.Exists(original))
                {
                    try
                    {
                        var backup = BfresIO.Load(original);
                        if (ShaderVariants.SameArchive(res, backup))
                            baseVariants.AddRange(ShaderVariants.Collect(backup));
                    }
                    catch (Exception e) { log($"INFO: Could not read optional template backup: {e.Message}"); }
                }
            }
            else
            {
                log("No base file: creating a new Switch BFRES (v5.0.3)");
                res = new ResFile(true) { Name = string.IsNullOrEmpty(man.ModelName) ? "course_model" : man.ModelName, Alignment = 0xC, TargetAddressSize = 0x40 };
            }
            foreach (var t in man.TemplateFiles)
            {
                if (t.EndsWith(".bfmat", StringComparison.OrdinalIgnoreCase)) bfmats.Add(Abs(t));
                else
                {
                    var source = BfresIO.Load(Abs(t));
                    templateSources.Add(source);
                    if (baseVariants != null && ShaderVariants.SameArchive(res, source))
                        baseVariants.AddRange(ShaderVariants.Collect(source));
                }
            }

            // texture alpha (for automatic opaque/alpha template choice)
            var texImages = new Dictionary<string, RgbaImage>();
            foreach (var te in man.Textures) texImages[te.Name] = ImageIO.Load(Abs(te.File));
            var animated = new HashSet<string>(templateSources.SelectMany(MaterialTemplates.AnimatedMaterialNames));

            // 2. Resolve + clone template materials BEFORE models are removed.
            var newMats = new List<Material>();
            var extraTexSources = new HashSet<string>();
            var wantedTextures = new HashSet<string>();
            int adjustedMaterials = 0;
            foreach (var me in man.Materials)
            {
                string? tname = me.Template ?? man.DefaultTemplate;
                Material? mat = null; string source = "";
                if (!string.IsNullOrEmpty(me.Bfmat))
                {
                    if (File.Exists(Abs(me.Bfmat))) { mat = MaterialTemplates.ImportBfmat(Abs(me.Bfmat), res); mat.Name = me.Name; source = "bfmat:" + Path.GetFileName(me.Bfmat); }
                    else Warn($"Material '{me.Name}': linked .bfmat not found ({me.Bfmat}); using the normal template choice.");
                }
                foreach (var ts in me.TextureSources) extraTexSources.Add(ts.EndsWith("/**") || ts.EndsWith("\\**") ? Abs(ts[..^3]) + "/**" : Abs(ts));
                if (mat == null && !string.IsNullOrEmpty(tname))
                {
                    var bf = bfmats.FirstOrDefault(p => Path.GetFileNameWithoutExtension(p) == tname)
                             ?? bfmats.FirstOrDefault(p => MaterialTemplates.ImportBfmat(p, res).Name == tname);
                    if (bf != null) { mat = MaterialTemplates.ImportBfmat(bf, res); mat.Name = me.Name; source = Path.GetFileName(bf); }
                    else
                        foreach (var src in templateSources)
                        {
                            var m = MaterialTemplates.Find(src, tname);
                            if (m != null) { mat = MaterialTemplates.Clone(src, m, me.Name); source = tname; break; }
                        }
                    if (mat == null) Warn($"Template material '{tname}' not found for '{me.Name}'.");
                }
                if (mat == null && bfmats.Count == 0 && templateSources.Count > 0)
                {
                    me.Textures.TryGetValue("albedo", out var albTex);
                    if (albTex == null) me.Textures.TryGetValue("_a0", out albTex);
                    bool alpha = me.Alpha || (albTex != null && texImages.TryGetValue(albTex, out var aimg) && aimg.HasAlpha());
                    foreach (var src in templateSources)
                    {
                        var (_, pick, why) = MaterialTemplates.AutoPick(src, alpha, animated);
                        if (pick != null) { mat = MaterialTemplates.Clone(src, pick, me.Name); source = $"auto:{pick.Name} ({why})"; break; }
                    }
                }
                if (mat == null && bfmats.Count > 0)
                {
                    mat = MaterialTemplates.ImportBfmat(bfmats[0], res); mat.Name = me.Name; source = Path.GetFileName(bfmats[0]);
                }
                if (mat == null)
                {
                    if (!man.AllowSynthetic)
                        throw new InvalidDataException($"No template material for '{me.Name}'. Pick an original MK8DX material (set the original course_model.szs in the exporter) or provide a .bfmat.");
                    Warn($"Using SYNTHETIC test material for '{me.Name}' (will not render in MK8DX).");
                    mat = MaterialTemplates.Synthetic(me.Name); source = "SYNTHETIC";
                }

                var userMap = new Dictionary<string, string>();
                foreach (var kv in me.Textures)
                    userMap[kv.Key == "albedo" ? MaterialTemplates.AlbedoSampler(mat) : kv.Key] = kv.Value;
                var neutralMap = new Dictionary<string, string>();
                if (man.NeutralOtherSamplers)
                    for (int i = 0; i < mat.Samplers.Count; i++)
                    {
                        string s = mat.Samplers.GetKey(i);
                        if (!userMap.ContainsKey(s) && s != MaterialTemplates.AlbedoSampler(mat)) neutralMap[s] = NeutralFor(s);
                    }
                var missing = MaterialTemplates.SetTextures(mat, userMap, man.ForceRepeat);
                MaterialTemplates.SetTextures(mat, neutralMap, false);
                foreach (var s in missing) Warn($"Material '{me.Name}': template has no sampler '{s}'.");
                foreach (var tr in mat.TextureRefs) wantedTextures.Add(tr.Name);
                if (baseVariants != null && mat.ShaderAssign != null)
                {
                    var (from, changed) = ShaderVariants.Snap(mat, baseVariants);
                    if (changed.Count > 0)
                    {
                        adjustedMaterials++;
                        log($"INFO: Material '{me.Name}': adjusted to the course shader variation of base material '{from}'; changed: {string.Join(", ", changed)}");
                    }
                }
                newMats.Add(mat);
                log($"Material {me.Name}: template={source} shader={mat.ShaderAssign?.ShaderArchiveName}/{mat.ShaderAssign?.ShadingModelName} samplers=[{string.Join(", ", Enumerable.Range(0, mat.Samplers.Count).Select(i => mat.Samplers.GetKey(i) + "=" + mat.TextureRefs[i].Name))}]");
            }

            if (adjustedMaterials > 0)
                log($"INFO: Adjusted {adjustedMaterials} material{(adjustedMaterials == 1 ? "" : "s")} to fit the course shaders (see log)");

            // Textures from template sources other than base that our materials still reference.
            foreach (var src in templateSources.Skip(string.IsNullOrEmpty(man.Base) ? 0 : 1))
                foreach (var kv in src.Textures)
                    if (wantedTextures.Contains(kv.Key) && !res.Textures.ContainsKey(kv.Key) && kv.Value is BfresLibrary.Switch.SwitchTexture st)
                        BntxTextures.AddOrReplace(res, st.Texture);

            // Original textures of imported .bfmat materials (kept albedo / other maps) from their source files.
            if (extraTexSources.Count > 0)
            {
                var pool = new TexturePool();
                foreach (var spec in extraTexSources) pool.Add(spec);
                var bntxOut = BntxTextures.GetOrCreate(res);
                foreach (var n in wantedTextures)
                {
                    if (res.Textures.ContainsKey(n) || man.Textures.Any(t => t.Name == n) || NeutralTextures.ContainsKey(n)) continue;
                    var ft = pool.Find(n);
                    if (ft == null) continue;
                    if (ft.Native != null) { ft.Native.Name = n; BntxTextures.AddOrReplace(res, ft.Native); log($"Texture {n}: kept original ({ft.Format}) from {ft.Origin}"); }
                    else if (ft.Image != null)
                    {
                        bool data = System.Text.RegularExpressions.Regex.IsMatch(n, @"_(nrm|nor|norm|spm|spc|spec|ao|msk|mask|bake|emm|emi|rgh)\d*$", System.Text.RegularExpressions.RegexOptions.IgnoreCase);
                        var tex = BntxTextures.Create(n, ft.Image, BntxTextures.ParseFormat("auto", ft.Image, !data), true, bntxOut);
                        BntxTextures.AddOrReplace(res, tex); log($"Texture {n}: encoded {tex.Format} from {ft.Origin}");
                    }
                }
                foreach (var w in pool.Warnings) Warn(w);
            }
            foreach (var n in wantedTextures)
                if (!res.Textures.ContainsKey(n) && !man.Textures.Any(t => t.Name == n) && !NeutralTextures.ContainsKey(n))
                    Warn($"Texture '{n}' is referenced by a material but was not found in any source; the game may show it black/missing.");

            // 3. Models
            string modelName = string.IsNullOrEmpty(man.ModelName) ? "course" : man.ModelName;
            if (man.Mode == "replace")
            {
                if (res.Models.Count > 0 && string.IsNullOrEmpty(man.ModelName)) modelName = res.Models.GetKey(0);
                res.Models.Clear();
                if (!man.KeepAnimations)
                {
                    res.SkeletalAnims.Clear(); res.ShaderParamAnims.Clear(); res.ColorAnims.Clear(); res.TexSrtAnims.Clear();
                    res.TexPatternAnims.Clear(); res.BoneVisibilityAnims.Clear(); res.MatVisibilityAnims.Clear(); res.ShapeAnims.Clear();
                    res.SceneAnims.Clear();
                }
            }
            if (res.Models.ContainsKey(modelName)) modelName += "_custom";
            res.Models.Add(modelName, BuildModel(modelName, newMats));

            // 4. Textures
            var bntx = BntxTextures.GetOrCreate(res);
            foreach (var te in man.Textures)
            {
                var img = texImages[te.Name];
                var fmt = BntxTextures.ParseFormat(te.Format, img, te.Srgb);
                if ((img.Width & (img.Width - 1)) != 0 || (img.Height & (img.Height - 1)) != 0)
                    Warn($"Texture '{te.Name}' is {img.Width}x{img.Height}; power-of-two sizes are recommended.");
                var tex = BntxTextures.Create(te.Name, img, fmt, te.Mips, bntx);
                BntxTextures.AddOrReplace(res, tex);
                log($"Texture {te.Name}: {img.Width}x{img.Height} {fmt} mips={tex.MipCount}");
            }
            foreach (var n in NeutralTextures.Keys)
                if (wantedTextures.Contains(n) && !res.Textures.ContainsKey(n))
                    BntxTextures.AddOrReplace(res, BntxTextures.Create(n, NeutralTextures[n](), Syroot.NintenTools.NSW.Bntx.GFX.SurfaceFormat.BC1_UNORM, true, bntx));

            if (man.PruneTextures && man.Mode == "replace")
            {
                var used = new HashSet<string>(res.Models.Values.SelectMany(m => m.Materials.Values).SelectMany(m => m.TextureRefs).Select(t => t.Name));
                if (man.KeepAnimations) used.UnionWith(MaterialTemplates.AnimTextureNames(res));
                foreach (var name in res.Textures.Keys.ToList())
                    if (!used.Contains(name)) BntxTextures.Remove(res, name);
            }
            if (!res.ExternalFiles.Keys.Any(k => k.EndsWith(".bfsha")) && !man.AllowSynthetic)
                Warn("No Turbo_UBER.bfsha is embedded. Original MK8DX course models embed their shader archive; use an original course .szs as the template file (not only a .bfmat) or the game may not draw the model.");
            foreach (var t in wantedTextures)
                if (!res.Textures.ContainsKey(t)) Warn($"Texture '{t}' is referenced by a material but is not in the file.");
            return res;
        }

        static string NeutralFor(string sampler)
        {
            if (sampler.StartsWith("_n")) return "mk8exp_flat_normal";
            if (sampler.StartsWith("_s") || sampler.StartsWith("_e")) return "mk8exp_black";
            return "mk8exp_white";
        }

        static RgbaImage Solid(byte r, byte g, byte b, byte a)
        {
            var px = new byte[8 * 8 * 4];
            for (int i = 0; i < 64; i++) { px[i * 4] = r; px[i * 4 + 1] = g; px[i * 4 + 2] = b; px[i * 4 + 3] = a; }
            return new RgbaImage { Width = 8, Height = 8, Pixels = px };
        }
        static readonly Dictionary<string, Func<RgbaImage>> NeutralTextures = new()
        {
            ["mk8exp_white"] = () => Solid(255, 255, 255, 255),
            ["mk8exp_black"] = () => Solid(0, 0, 0, 255),
            ["mk8exp_flat_normal"] = () => Solid(128, 128, 255, 255),
        };

        float[] ReadFloats(BinaryReader br, long off, int count)
        {
            br.BaseStream.Position = off;
            var f = new float[count];
            for (int i = 0; i < count; i++) f[i] = br.ReadSingle();
            return f;
        }

        Model BuildModel(string name, List<Material> mats)
        {
            var model = new Model { Name = name, Path = "" };
            model.Skeleton = new Skeleton();
            var bone = new Bone
            {
                Name = name, ParentIndex = -1, SmoothMatrixIndex = -1, RigidMatrixIndex = -1, BillboardIndex = -1,
                Scale = new Vector3F(1, 1, 1), Rotation = new Vector4F(0, 0, 0, 1), Position = new Vector3F(0, 0, 0),
            };
            model.Skeleton.Bones.Add(bone.Name, bone);
            model.Skeleton.InverseModelMatrices = new List<Matrix3x4>();
            model.Skeleton.MatrixToBoneList = new List<ushort>();
            foreach (var m in mats) model.Materials.Add(m.Name, m);

            var readers = new Dictionary<string, BinaryReader>();
            try
            {
                foreach (var me in man.Meshes)
                {
                    int matIndex = model.Materials.IndexOf(me.Material);
                    if (matIndex < 0) throw new InvalidDataException($"Mesh '{me.Name}' uses unknown material '{me.Material}'.");
                    if (!readers.TryGetValue(me.Bin, out var br)) readers[me.Bin] = br = new BinaryReader(File.OpenRead(Abs(me.Bin)));
                    var mat = model.Materials[matIndex];
                    var (shape, vb) = BuildShape(me, br, mat, model.VertexBuffers.Count);
                    shape.MaterialIndex = (ushort)matIndex;
                    model.VertexBuffers.Add(vb);
                    string sname = me.Name; int dup = 1;
                    while (model.Shapes.ContainsKey(sname)) sname = me.Name + "_" + dup++;
                    shape.Name = sname;
                    model.Shapes.Add(sname, shape);
                    log($"Shape {sname}: {me.VertexCount} verts, {me.IndexCount / 3} tris, material {me.Material}");
                }
            }
            finally { foreach (var r in readers.Values) r.Dispose(); }
            return model;
        }

        (Shape, VertexBuffer) BuildShape(MeshEntry me, BinaryReader br, Material mat, int vbIndex)
        {
            int n = me.VertexCount;
            Vector4F[] Get(string key, int comps, Vector4F def)
            {
                var res = new Vector4F[n];
                if (!me.Arrays.TryGetValue(key, out var a)) { Array.Fill(res, def); return res; }
                var f = ReadFloats(br, a.Offset, n * a.Components);
                for (int i = 0; i < n; i++)
                {
                    float x = f[i * a.Components], y = a.Components > 1 ? f[i * a.Components + 1] : def.Y,
                          z = a.Components > 2 ? f[i * a.Components + 2] : def.Z, w = a.Components > 3 ? f[i * a.Components + 3] : def.W;
                    res[i] = new Vector4F(x, y, z, w);
                }
                return res;
            }

            var pos = Get("position", 3, new Vector4F(0, 0, 0, 1));
            // which vertex attributes does the template's shader want?
            var wanted = new List<string>(MaterialTemplates.Map(mat.ShaderAssign?.AttribAssigns).Values.Where(v => !string.IsNullOrEmpty(v)));
            foreach (var a in new[] { "_p0", "_n0", "_u0" }) if (!wanted.Contains(a)) wanted.Insert(0, a);
            wanted = wanted.Distinct().ToList();

            var helper = new VertexBufferHelper { VertexSkinCount = 0, ByteOrder = Syroot.BinaryData.ByteOrder.LittleEndian };
            helper.Attributes = new List<VertexBufferHelperAttrib>();
            void Add(string nm, GX2AttribFormat f, Vector4F[] d) => helper.Attributes.Add(new VertexBufferHelperAttrib { Name = nm, Format = f, Data = d, BufferIndex = (byte)helper.Attributes.Count });
            foreach (var a in wanted.OrderBy(x => x == "_p0" ? 0 : 1))
            {
                if (a.StartsWith("_p")) Add(a, GX2AttribFormat.Format_32_32_32_Single, pos);
                else if (a.StartsWith("_n")) Add(a, GX2AttribFormat.Format_10_10_10_2_SNorm, Get("normal", 3, new Vector4F(0, 1, 0, 0)));
                else if (a.StartsWith("_u") && int.TryParse(a.Substring(2), out int k))
                {
                    string key = me.Arrays.ContainsKey("uv" + k) ? "uv" + k : "uv0";
                    if (key != "uv" + k && k > 0) log($"  {me.Name}: shader wants {a}, no UV map {k} -> reusing uv0");
                    Add(a, GX2AttribFormat.Format_32_32_Single, Get(key, 2, new Vector4F(0, 0, 0, 0)));
                }
                else if (a.StartsWith("_c")) Add(a, GX2AttribFormat.Format_8_8_8_8_UNorm, Get("color0", 4, new Vector4F(1, 1, 1, 1)));
                else if (a.StartsWith("_t")) Add(a, GX2AttribFormat.Format_8_8_8_8_SNorm, Get("tangent", 4, new Vector4F(1, 0, 0, 1)));
                else if (a.StartsWith("_b")) Add(a, GX2AttribFormat.Format_8_8_8_8_SNorm, Get("bitangent", 4, new Vector4F(0, 0, 1, 1)));
                else if (a.StartsWith("_i") || a.StartsWith("_w")) Warn($"Template material '{mat.Name}' expects skinning attribute {a}; static course meshes do not provide it.");
                else { Warn($"Unknown vertex attribute {a} requested by '{mat.Name}', filled with zeros."); Add(a, GX2AttribFormat.Format_32_32_32_32_Single, new Vector4F[n]); }
            }
            var vb = helper.ToVertexBuffer();

            br.BaseStream.Position = me.IndicesOffset;
            var idx = new uint[me.IndexCount];
            for (int i = 0; i < idx.Length; i++) idx[i] = br.ReadUInt32();

            var mesh = new Mesh { PrimitiveType = GX2PrimitiveType.Triangles, FirstVertex = 0 };
            mesh.SetIndices(idx, n > 65535 ? GX2IndexFormat.UInt32LittleEndian : GX2IndexFormat.UInt16LittleEndian);
            mesh.SubMeshes.Add(new SubMesh { Offset = 0, Count = (uint)idx.Length });

            var min = new Vector3F(float.MaxValue, float.MaxValue, float.MaxValue); var max = new Vector3F(float.MinValue, float.MinValue, float.MinValue);
            foreach (var p in pos)
            {
                min = new Vector3F(Math.Min(min.X, p.X), Math.Min(min.Y, p.Y), Math.Min(min.Z, p.Z));
                max = new Vector3F(Math.Max(max.X, p.X), Math.Max(max.Y, p.Y), Math.Max(max.Z, p.Z));
            }
            var center = new Vector3F((min.X + max.X) / 2, (min.Y + max.Y) / 2, (min.Z + max.Z) / 2);
            var extent = new Vector3F((max.X - min.X) / 2, (max.Y - min.Y) / 2, (max.Z - min.Z) / 2);
            float radius = 0;
            foreach (var p in pos)
            {
                float dx = p.X - center.X, dy = p.Y - center.Y, dz = p.Z - center.Z;
                radius = Math.Max(radius, (float)Math.Sqrt(dx * dx + dy * dy + dz * dz));
            }

            var shape = new Shape
            {
                Flags = ShapeFlags.HasVertexBuffer, BoneIndex = 0, VertexBufferIndex = (ushort)vbIndex, VertexSkinCount = 0,
                Meshes = new List<Mesh> { mesh },
            };
            shape.SubMeshBoundings = new List<Bounding> { new Bounding { Center = center, Extent = extent }, new Bounding { Center = center, Extent = extent } };
            shape.SubMeshBoundingIndices = new List<ushort> { 0 };
            shape.SubMeshBoundingNodes = new List<BoundingNode> { new BoundingNode { SubMeshIndex = 0, SubMeshCount = 1 } };
            shape.RadiusArray = new List<float> { radius };
            shape.BoundingRadiusList = new List<Vector4F> { new Vector4F(center.X, center.Y, center.Z, radius) };
            return (shape, vb);
        }
    }
}
