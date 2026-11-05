using System;
using System.IO;

namespace Mk8SzsTool.Formats
{
    /// <summary>Yaz0 (SZS) compression used by Nintendo. Shared by export and (future) import.</summary>
    public static class Yaz0
    {
        public static bool IsYaz0(byte[] d) => d.Length >= 16 && d[0] == 'Y' && d[1] == 'a' && d[2] == 'z' && d[3] == '0';

        public static byte[] Decompress(byte[] src)
        {
            if (!IsYaz0(src)) throw new InvalidDataException("Not a Yaz0 file");
            int size = (src[4] << 24) | (src[5] << 16) | (src[6] << 8) | src[7];
            var dst = new byte[size];
            int s = 16, d = 0;
            while (d < size)
            {
                byte code = src[s++];
                for (int bit = 7; bit >= 0 && d < size; bit--)
                {
                    if ((code & (1 << bit)) != 0) { dst[d++] = src[s++]; continue; }
                    int b1 = src[s++], b2 = src[s++];
                    int dist = ((b1 & 0x0F) << 8 | b2) + 1;
                    int len = b1 >> 4;
                    len = len == 0 ? src[s++] + 0x12 : len + 2;
                    int from = d - dist;
                    for (int i = 0; i < len; i++) dst[d++] = dst[from + i];
                }
            }
            return dst;
        }

        /// <summary>Greedy LZ with hash chains (window 0x1000, max match 0x111).</summary>
        public static byte[] Compress(byte[] src, uint alignment = 0x80)
        {
            const int Window = 0x1000, MaxLen = 0x111, MinLen = 3, HashSize = 1 << 16, MaxChain = 256;
            var ms = new MemoryStream(src.Length / 2 + 64);
            ms.Write(new byte[] { (byte)'Y', (byte)'a', (byte)'z', (byte)'0' });
            ms.WriteByte((byte)(src.Length >> 24)); ms.WriteByte((byte)(src.Length >> 16));
            ms.WriteByte((byte)(src.Length >> 8)); ms.WriteByte((byte)src.Length);
            ms.WriteByte((byte)(alignment >> 24)); ms.WriteByte((byte)(alignment >> 16));
            ms.WriteByte((byte)(alignment >> 8)); ms.WriteByte((byte)alignment);
            ms.Write(new byte[4]);

            var head = new int[HashSize]; Array.Fill(head, -1);
            var prev = new int[src.Length];
            int Hash(int p) => ((src[p] << 8) ^ (src[p + 1] << 4) ^ src[p + 2]) & (HashSize - 1);
            void Insert(int p) { if (p + 2 < src.Length) { int h = Hash(p); prev[p] = head[h]; head[h] = p; } }

            var group = new byte[1 + 8 * 3];
            int pos = 0;
            while (pos < src.Length)
            {
                int gl = 1; byte code = 0;
                for (int bit = 7; bit >= 0 && pos < src.Length; bit--)
                {
                    int bestLen = 0, bestDist = 0;
                    if (pos + MinLen <= src.Length)
                    {
                        int maxl = Math.Min(MaxLen, src.Length - pos);
                        int cand = head[Hash(pos)], chain = 0;
                        while (cand >= 0 && pos - cand <= Window && chain++ < MaxChain)
                        {
                            int l = 0;
                            while (l < maxl && src[cand + l] == src[pos + l]) l++;
                            if (l > bestLen) { bestLen = l; bestDist = pos - cand; if (l == maxl) break; }
                            cand = prev[cand];
                        }
                    }
                    if (bestLen >= MinLen)
                    {
                        int dist = bestDist - 1;
                        if (bestLen >= 0x12)
                        {
                            group[gl++] = (byte)(dist >> 8); group[gl++] = (byte)dist; group[gl++] = (byte)(bestLen - 0x12);
                        }
                        else
                        {
                            group[gl++] = (byte)(((bestLen - 2) << 4) | (dist >> 8)); group[gl++] = (byte)dist;
                        }
                        for (int i = 0; i < bestLen; i++) Insert(pos + i);
                        pos += bestLen;
                    }
                    else
                    {
                        code |= (byte)(1 << bit);
                        group[gl++] = src[pos];
                        Insert(pos); pos++;
                    }
                }
                group[0] = code;
                ms.Write(group, 0, gl);
            }
            return ms.ToArray();
        }
    }
}
