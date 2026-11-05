using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;

namespace Mk8SzsTool.Formats
{
    /// <summary>
    /// Minimal little-endian SARC reader/writer (Switch). MK8DX course_model.szs is Yaz0(BFRES) directly,
    /// but other course files (and future import features) use SARC, so it lives in the shared layer.
    /// </summary>
    public static class Sarc
    {
        public static bool IsSarc(byte[] d) => d.Length >= 0x14 && Encoding.ASCII.GetString(d, 0, 4) == "SARC";

        static uint Hash(string name, uint key = 0x65)
        {
            uint h = 0; foreach (byte b in Encoding.UTF8.GetBytes(name)) h = h * key + b; return h;
        }

        public static Dictionary<string, byte[]> Read(byte[] d)
        {
            if (!IsSarc(d)) throw new InvalidDataException("Not a SARC");
            if (d[6] != 0xFF || d[7] != 0xFE) throw new NotSupportedException("Only little-endian SARC supported");
            uint dataStart = BitConverter.ToUInt32(d, 0x0C);
            int sfat = 0x14;
            int count = BitConverter.ToUInt16(d, sfat + 6);
            int nodes = sfat + 0x0C;
            int sfnt = nodes + count * 0x10;
            int names = sfnt + 8;
            var res = new Dictionary<string, byte[]>();
            for (int i = 0; i < count; i++)
            {
                int n = nodes + i * 0x10;
                uint attr = BitConverter.ToUInt32(d, n + 4);
                uint s = BitConverter.ToUInt32(d, n + 8), e = BitConverter.ToUInt32(d, n + 12);
                string name = $"file_{i}";
                if ((attr & 0x01000000) != 0)
                {
                    int off = names + (int)(attr & 0xFFFF) * 4, end = off;
                    while (d[end] != 0) end++;
                    name = Encoding.UTF8.GetString(d, off, end - off);
                }
                res[name] = d.Skip((int)(dataStart + s)).Take((int)(e - s)).ToArray();
            }
            return res;
        }

        public static byte[] Write(Dictionary<string, byte[]> files, int alignment = 0x2000)
        {
            var entries = files.Select(kv => (kv.Key, kv.Value, H: Hash(kv.Key))).OrderBy(x => x.H).ToList();
            var nameTbl = new MemoryStream(); var nameOffs = new List<int>();
            foreach (var e in entries)
            {
                nameOffs.Add((int)nameTbl.Position / 4);
                var b = Encoding.UTF8.GetBytes(e.Key); nameTbl.Write(b); nameTbl.WriteByte(0);
                while (nameTbl.Position % 4 != 0) nameTbl.WriteByte(0);
            }
            int headerSize = 0x14 + 0x0C + entries.Count * 0x10 + 8 + (int)nameTbl.Length;
            int dataStart = (headerSize + alignment - 1) / alignment * alignment;
            var data = new MemoryStream(); var ranges = new List<(int, int)>();
            foreach (var e in entries)
            {
                while (data.Position % 0x80 != 0) data.WriteByte(0);
                int s = (int)data.Position; data.Write(e.Value); ranges.Add((s, (int)data.Position));
            }
            var o = new MemoryStream(); var w = new BinaryWriter(o);
            w.Write(Encoding.ASCII.GetBytes("SARC")); w.Write((ushort)0x14); w.Write((ushort)0xFEFF);
            w.Write((uint)(dataStart + data.Length)); w.Write((uint)dataStart); w.Write((ushort)0x100); w.Write((ushort)0);
            w.Write(Encoding.ASCII.GetBytes("SFAT")); w.Write((ushort)0x0C); w.Write((ushort)entries.Count); w.Write(0x65u);
            for (int i = 0; i < entries.Count; i++)
            {
                w.Write(entries[i].H); w.Write(0x01000000u | (uint)nameOffs[i]);
                w.Write((uint)ranges[i].Item1); w.Write((uint)ranges[i].Item2);
            }
            w.Write(Encoding.ASCII.GetBytes("SFNT")); w.Write((ushort)8); w.Write((ushort)0);
            w.Write(nameTbl.ToArray());
            while (o.Position < dataStart) w.Write((byte)0);
            w.Write(data.ToArray());
            return o.ToArray();
        }
    }
}
