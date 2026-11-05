using System;

namespace Mk8SzsTool.Formats
{
    /// <summary>Simple BC1/BC3 encoder + decoder (RGBA8 in/out, rows top-down).</summary>
    public static class BcCodec
    {
        static ushort To565(int r, int g, int b) => (ushort)(((r * 31 + 127) / 255) << 11 | ((g * 63 + 127) / 255) << 5 | ((b * 31 + 127) / 255));
        static void From565(ushort c, out int r, out int g, out int b)
        {
            r = (c >> 11) & 31; g = (c >> 5) & 63; b = c & 31;
            r = (r << 3) | (r >> 2); g = (g << 2) | (g >> 4); b = (b << 3) | (b >> 2);
        }

        static void FetchBlock(byte[] rgba, int w, int h, int bx, int by, byte[] blk)
        {
            for (int y = 0; y < 4; y++)
                for (int x = 0; x < 4; x++)
                {
                    int sx = Math.Min(bx * 4 + x, w - 1), sy = Math.Min(by * 4 + y, h - 1);
                    Buffer.BlockCopy(rgba, (sy * w + sx) * 4, blk, (y * 4 + x) * 4, 4);
                }
        }

        static void EncodeColor(byte[] blk, byte[] dst, int o)
        {
            // principal axis via bounding box diagonal, refined by projecting onto it
            double mr = 0, mg = 0, mb = 0;
            for (int i = 0; i < 16; i++) { mr += blk[i * 4]; mg += blk[i * 4 + 1]; mb += blk[i * 4 + 2]; }
            mr /= 16; mg /= 16; mb /= 16;
            double cxx = 0, cxy = 0, cxz = 0, cyy = 0, cyz = 0, czz = 0;
            for (int i = 0; i < 16; i++)
            {
                double r = blk[i * 4] - mr, g = blk[i * 4 + 1] - mg, b = blk[i * 4 + 2] - mb;
                cxx += r * r; cxy += r * g; cxz += r * b; cyy += g * g; cyz += g * b; czz += b * b;
            }
            double ax = 1, ay = 1, az = 1;
            for (int it = 0; it < 8; it++)
            {
                double nx = cxx * ax + cxy * ay + cxz * az, ny = cxy * ax + cyy * ay + cyz * az, nz = cxz * ax + cyz * ay + czz * az;
                double len = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                if (len < 1e-9) { ax = ay = az = 0; break; }
                ax = nx / len; ay = ny / len; az = nz / len;
            }
            double minp = double.MaxValue, maxp = double.MinValue;
            for (int i = 0; i < 16; i++)
            {
                double p = (blk[i * 4] - mr) * ax + (blk[i * 4 + 1] - mg) * ay + (blk[i * 4 + 2] - mb) * az;
                minp = Math.Min(minp, p); maxp = Math.Max(maxp, p);
            }
            int C(double v) => (int)Math.Clamp(Math.Round(v), 0, 255);
            ushort c0 = To565(C(mr + ax * maxp), C(mg + ay * maxp), C(mb + az * maxp));
            ushort c1 = To565(C(mr + ax * minp), C(mg + ay * minp), C(mb + az * minp));
            if (c0 < c1) (c0, c1) = (c1, c0);
            uint idx = 0;
            if (c0 != c1)
            {
                var pal = new int[4, 3];
                From565(c0, out pal[0, 0], out pal[0, 1], out pal[0, 2]);
                From565(c1, out pal[1, 0], out pal[1, 1], out pal[1, 2]);
                for (int k = 0; k < 3; k++) { pal[2, k] = (2 * pal[0, k] + pal[1, k]) / 3; pal[3, k] = (pal[0, k] + 2 * pal[1, k]) / 3; }
                for (int i = 0; i < 16; i++)
                {
                    int best = 0, bd = int.MaxValue;
                    for (int p = 0; p < 4; p++)
                    {
                        int dr = blk[i * 4] - pal[p, 0], dg = blk[i * 4 + 1] - pal[p, 1], db = blk[i * 4 + 2] - pal[p, 2];
                        int dd = dr * dr + dg * dg + db * db;
                        if (dd < bd) { bd = dd; best = p; }
                    }
                    idx |= (uint)best << (i * 2);
                }
            }
            dst[o] = (byte)c0; dst[o + 1] = (byte)(c0 >> 8); dst[o + 2] = (byte)c1; dst[o + 3] = (byte)(c1 >> 8);
            dst[o + 4] = (byte)idx; dst[o + 5] = (byte)(idx >> 8); dst[o + 6] = (byte)(idx >> 16); dst[o + 7] = (byte)(idx >> 24);
        }

        static void EncodeAlpha(byte[] blk, byte[] dst, int o)
        {
            int a0 = 0, a1 = 255;
            for (int i = 0; i < 16; i++) { a0 = Math.Max(a0, blk[i * 4 + 3]); a1 = Math.Min(a1, blk[i * 4 + 3]); }
            dst[o] = (byte)a0; dst[o + 1] = (byte)a1;
            ulong bits = 0;
            if (a0 != a1)
            {
                var pal = new int[8]; pal[0] = a0; pal[1] = a1;
                for (int k = 1; k < 7; k++) pal[k + 1] = ((7 - k) * a0 + k * a1) / 7;
                for (int i = 0; i < 16; i++)
                {
                    int a = blk[i * 4 + 3], best = 0, bd = int.MaxValue;
                    for (int p = 0; p < 8; p++) { int dd = Math.Abs(a - pal[p]); if (dd < bd) { bd = dd; best = p; } }
                    bits |= (ulong)best << (i * 3);
                }
            }
            for (int k = 0; k < 6; k++) dst[o + 2 + k] = (byte)(bits >> (8 * k));
        }

        public static byte[] Encode(byte[] rgba, int w, int h, bool bc3)
        {
            int bw = (w + 3) / 4, bh = (h + 3) / 4, bs = bc3 ? 16 : 8;
            var outp = new byte[bw * bh * bs];
            var blk = new byte[64];
            for (int by = 0; by < bh; by++)
                for (int bx = 0; bx < bw; bx++)
                {
                    FetchBlock(rgba, w, h, bx, by, blk);
                    int o = (by * bw + bx) * bs;
                    if (bc3) { EncodeAlpha(blk, outp, o); EncodeColor(blk, outp, o + 8); }
                    else EncodeColor(blk, outp, o);
                }
            return outp;
        }

        public static byte[] Decode(byte[] data, int w, int h, bool bc3)
        {
            int bw = (w + 3) / 4, bh = (h + 3) / 4, bs = bc3 ? 16 : 8;
            var outp = new byte[w * h * 4];
            for (int by = 0; by < bh; by++)
                for (int bx = 0; bx < bw; bx++)
                {
                    int o = (by * bw + bx) * bs;
                    var alpha = new int[16]; for (int i = 0; i < 16; i++) alpha[i] = 255;
                    if (bc3)
                    {
                        int a0 = data[o], a1 = data[o + 1]; var pal = new int[8]; pal[0] = a0; pal[1] = a1;
                        if (a0 > a1) for (int k = 1; k < 7; k++) pal[k + 1] = ((7 - k) * a0 + k * a1) / 7;
                        else { for (int k = 1; k < 5; k++) pal[k + 1] = ((5 - k) * a0 + k * a1) / 5; pal[6] = 0; pal[7] = 255; }
                        ulong bits = 0; for (int k = 0; k < 6; k++) bits |= (ulong)data[o + 2 + k] << (8 * k);
                        for (int i = 0; i < 16; i++) alpha[i] = pal[(bits >> (3 * i)) & 7];
                        o += 8;
                    }
                    ushort c0 = (ushort)(data[o] | data[o + 1] << 8), c1 = (ushort)(data[o + 2] | data[o + 3] << 8);
                    uint idx = BitConverter.ToUInt32(data, o + 4);
                    var p = new int[4, 4];
                    From565(c0, out p[0, 0], out p[0, 1], out p[0, 2]); From565(c1, out p[1, 0], out p[1, 1], out p[1, 2]);
                    for (int k = 0; k < 4; k++) { p[0, 3] = 255; p[1, 3] = 255; }
                    if (c0 > c1 || bc3)
                        for (int k = 0; k < 3; k++) { p[2, k] = (2 * p[0, k] + p[1, k]) / 3; p[3, k] = (p[0, k] + 2 * p[1, k]) / 3; }
                    else
                        for (int k = 0; k < 3; k++) { p[2, k] = (p[0, k] + p[1, k]) / 2; p[3, k] = 0; }
                    p[2, 3] = 255; p[3, 3] = (c0 > c1 || bc3) ? 255 : 0;
                    for (int i = 0; i < 16; i++)
                    {
                        int x = bx * 4 + i % 4, y = by * 4 + i / 4; if (x >= w || y >= h) continue;
                        int s = (int)((idx >> (2 * i)) & 3), d = (y * w + x) * 4;
                        outp[d] = (byte)p[s, 0]; outp[d + 1] = (byte)p[s, 1]; outp[d + 2] = (byte)p[s, 2];
                        outp[d + 3] = (byte)(bc3 ? alpha[i] : p[s, 3]);
                    }
                }
            return outp;
        }

        static void Bc4Block(byte[] d, int o, bool signed, int[] outv)
        {
            int a0 = signed ? (sbyte)d[o] + 128 : d[o], a1 = signed ? (sbyte)d[o + 1] + 128 : d[o + 1];
            var pal = new int[8]; pal[0] = a0; pal[1] = a1;
            bool gt = signed ? (sbyte)d[o] > (sbyte)d[o + 1] : a0 > a1;
            if (gt) for (int k = 1; k < 7; k++) pal[k + 1] = ((7 - k) * a0 + k * a1) / 7;
            else { for (int k = 1; k < 5; k++) pal[k + 1] = ((5 - k) * a0 + k * a1) / 5; pal[6] = signed ? 1 : 0; pal[7] = 255; }
            ulong bits = 0; for (int k = 0; k < 6; k++) bits |= (ulong)d[o + 2 + k] << (8 * k);
            for (int i = 0; i < 16; i++) outv[i] = Math.Clamp(pal[(bits >> (3 * i)) & 7], 0, 255);
        }

        /// <summary>BC4 (grey) / BC5 (RG normal map; B reconstructed) to RGBA8.</summary>
        public static byte[] DecodeBc45(byte[] data, int w, int h, bool bc5, bool signed)
        {
            int bw = (w + 3) / 4, bh = (h + 3) / 4, bs = bc5 ? 16 : 8;
            var outp = new byte[w * h * 4]; var r = new int[16]; var g = new int[16];
            for (int by = 0; by < bh; by++)
                for (int bx = 0; bx < bw; bx++)
                {
                    int o = (by * bw + bx) * bs;
                    Bc4Block(data, o, signed, r);
                    if (bc5) Bc4Block(data, o + 8, signed, g);
                    for (int i = 0; i < 16; i++)
                    {
                        int x = bx * 4 + i % 4, y = by * 4 + i / 4; if (x >= w || y >= h) continue;
                        int d = (y * w + x) * 4;
                        if (bc5)
                        {
                            double nx = r[i] / 127.5 - 1, ny = g[i] / 127.5 - 1, nz = Math.Sqrt(Math.Max(0, 1 - nx * nx - ny * ny));
                            outp[d] = (byte)r[i]; outp[d + 1] = (byte)g[i]; outp[d + 2] = (byte)Math.Round((nz + 1) * 127.5);
                        }
                        else { outp[d] = outp[d + 1] = outp[d + 2] = (byte)r[i]; }
                        outp[d + 3] = 255;
                    }
                }
            return outp;
        }
    }
}