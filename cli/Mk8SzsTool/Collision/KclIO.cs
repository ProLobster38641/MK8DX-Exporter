using System.Numerics;
using KclLibrary;
using Mk8SzsTool.Formats;

namespace Mk8SzsTool.Collision
{
    /// <summary>MK8DX (Switch) collision: KCL version 2, little endian, Yaz0 wrapped as course_kcl.szs.
    /// Attribute = type (bits 0-4) | variant (bits 5-7) | special flags (bits 12-15).</summary>
    public static class KclIO
    {
        // MK8 Deluxe preset values used by Switch Toolbox / KclLibrary (KclImporter/CollisionPresets)
        public static CollisionImportSettings Mk8dxSettings() => new CollisionImportSettings
        {
            PrismThickness = 30, SphereRadius = 25,
        };

        /// <param name="pos">float32 x,y,z * 3 per triangle (already in MK8 space)</param>
        public static byte[] Build(float[] pos, ushort[] attrs, bool yaz0, out int written, List<string> warns)
        {
            var tris = new List<Triangle>();
            for (int i = 0; i < attrs.Length; i++)
            {
                int o = i * 9;
                var t = new Triangle(new Vector3(pos[o], pos[o + 1], pos[o + 2]), new Vector3(pos[o + 3], pos[o + 4], pos[o + 5]), new Vector3(pos[o + 6], pos[o + 7], pos[o + 8]));
                var n = Vector3.Cross(t.Vertices[1] - t.Vertices[0], t.Vertices[2] - t.Vertices[0]);
                if (n.LengthSquared() < 1e-10f || t.HasNan()) continue;   // degenerate: KCL can't store it
                t.Attribute = attrs[i];
                tris.Add(t);
            }
            if (tris.Count < attrs.Length) warns.Add($"WARNING: skipped {attrs.Length - tris.Count} degenerate (zero-area) collision triangles");
            if (tris.Count == 0) throw new Exception("no valid collision triangles");
            written = tris.Count;
            var kcl = new KCLFile(tris, FileVersion.Version2, false, Mk8dxSettings());
            var ms = new MemoryStream();
            kcl.Save(ms);
            var raw = ms.ToArray();
            return yaz0 ? Yaz0.Compress(raw, 0) : raw;
        }

        public static KCLFile Load(string path)
        {
            var d = File.ReadAllBytes(path);
            if (Yaz0.IsYaz0(d)) d = Yaz0.Decompress(d);
            return new KCLFile(new MemoryStream(d));
        }

        /// <summary>Summary + self-check: every triangle's centre (nudged along its normal) must be found by the octree.</summary>
        public static object Describe(string path, bool hitTest)
        {
            var d = File.ReadAllBytes(path);
            bool isYaz0 = Yaz0.IsYaz0(d);
            var kcl = Load(path);
            var hist = new SortedDictionary<string, int>();
            int tris = 0, hits = 0, tested = 0;
            var all = new List<object>();
            foreach (var m in kcl.Models)
                foreach (var p in m.Prisms)
                {
                    tris++;
                    string k = $"COL_{p.CollisionFlags:X}";
                    hist[k] = hist.TryGetValue(k, out var c) ? c + 1 : 1;
                    if (hitTest)
                    {
                        var t = m.GetTriangle(p);
                        var ctr = (t.Vertices[0] + t.Vertices[1] + t.Vertices[2]) / 3f;
                        tested++;
                        if (kcl.CheckHit(ctr) != null) hits++;
                    }
                }
            return new
            {
                yaz0 = isYaz0, version = kcl.Version.ToString(), byte_order = kcl.ByteOrder.ToString(),
                models = kcl.Models.Count, triangles = tris, attributes = hist,
                min = new[] { kcl.MinCoordinate.X, kcl.MinCoordinate.Y, kcl.MinCoordinate.Z },
                max = new[] { kcl.MaxCoordinate.X, kcl.MaxCoordinate.Y, kcl.MaxCoordinate.Z },
                octree_hit_test = hitTest ? $"{hits}/{tested}" : null,
            };
        }

        /// <summary>Dump triangles back as float32 positions + uint16 attributes (for tests and a future importer).</summary>
        public static void Dump(string path, string posOut, string attrOut)
        {
            var kcl = Load(path);
            using var pw = new BinaryWriter(File.Create(posOut));
            using var aw = new BinaryWriter(File.Create(attrOut));
            foreach (var m in kcl.Models)
                foreach (var p in m.Prisms)
                {
                    var t = m.GetTriangle(p);
                    foreach (var v in t.Vertices) { pw.Write(v.X); pw.Write(v.Y); pw.Write(v.Z); }
                    aw.Write((ushort)p.CollisionFlags);
                }
        }
    }
}
