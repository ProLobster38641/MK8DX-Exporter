using System.IO;
using BfresLibrary;

namespace Mk8SzsTool.Formats
{
    /// <summary>Load/save BFRES from raw .bfres or Yaz0 .szs. Shared by export and import.</summary>
    public static class BfresIO
    {
        public static byte[] ReadMaybeYaz0(string path)
        {
            var d = File.ReadAllBytes(path);
            return Yaz0.IsYaz0(d) ? Yaz0.Decompress(d) : d;
        }

        public static ResFile Load(string path)
        {
            var raw = ReadMaybeYaz0(path);
            if (Sarc.IsSarc(raw))
            {
                foreach (var kv in Sarc.Read(raw))
                    if (kv.Value.Length > 4 && kv.Value[0] == 'F' && kv.Value[1] == 'R' && kv.Value[2] == 'E' && kv.Value[3] == 'S')
                        return new ResFile(new MemoryStream(kv.Value));
                throw new InvalidDataException("SARC contains no BFRES");
            }
            return new ResFile(new MemoryStream(raw));
        }

        public static byte[] ToBytes(ResFile res)
        {
            var ms = new MemoryStream();
            res.Save(ms, true);
            return ms.ToArray();
        }

        public static void Save(ResFile res, string path, bool yaz0)
        {
            var raw = ToBytes(res);
            File.WriteAllBytes(path, yaz0 ? Yaz0.Compress(raw) : raw);
        }
    }
}
