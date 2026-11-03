// Treasure Radar companion: the map-circle detector. A port of dev/companion/detect.py, which stays the reference.
//
// Pixels only. The input is the RGB square [cx - rim, cy - rim, cx + rim, cy + rim] of the game's client area plus the
// geometry the mod sends in its line (dev/docs/COMPANION_INTERFACE.md). The Pil class below reproduces, to the byte, the
// few PIL operations detect.py is built on (parity_probe.cs checks them against PIL itself).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.Numerics;
using System.Text;

namespace TreasureRadar
{
    // printf's %.Nf: the exact binary value, rounded half to even. .NET Framework's ToString("F1") goes through 15
    // significant digits first and so differs from Python on a few values.
    internal static class Fmt
    {
        public static string F(double v, int nd)
        {
            if (double.IsNaN(v)) return "nan";
            if (double.IsInfinity(v)) return v > 0 ? "inf" : "-inf";
            long bits = BitConverter.DoubleToInt64Bits(v);
            bool neg = bits < 0;
            int e = (int)((bits >> 52) & 0x7FF);
            long m = bits & ((1L << 52) - 1);
            if (e == 0) e = 1; else m |= 1L << 52;
            e -= 1075;
            BigInteger num = new BigInteger(m) * BigInteger.Pow(10, nd);
            BigInteger q;
            if (e >= 0)
            {
                q = num << e;
            }
            else
            {
                BigInteger den = BigInteger.One << -e;
                BigInteger r;
                q = BigInteger.DivRem(num, den, out r);
                int c = (r * 2).CompareTo(den);
                if (c > 0 || (c == 0 && !q.IsEven)) q += 1;
            }
            string s = q.ToString(CultureInfo.InvariantCulture);
            if (nd > 0)
            {
                if (s.Length <= nd) s = new string('0', nd + 1 - s.Length) + s;
                s = s.Substring(0, s.Length - nd) + "." + s.Substring(s.Length - nd);
            }
            return neg ? "-" + s : s;
        }

        public static string Plus(double v, int nd)
        {
            string s = F(v, nd);
            return s[0] == '-' ? s : "+" + s;
        }
    }

    internal static class Pil
    {
        // Image.convert('HSV') on RGB (libImaging/Convert.c rgb2hsv), one pixel at a time, with its float and double steps
        public static void RgbToHsv(byte[] rgb, int count, byte[] H, byte[] S, byte[] V)
        {
            for (int i = 0, p = 0; i < count; i++, p += 3)
            {
                int r = rgb[p], g = rgb[p + 1], b = rgb[p + 2];
                int maxc = r > g ? (r > b ? r : b) : (g > b ? g : b);
                int minc = r < g ? (r < b ? r : b) : (g < b ? g : b);
                V[i] = (byte)maxc;
                if (minc == maxc)
                {
                    H[i] = 0;
                    S[i] = 0;
                    continue;
                }
                float cr = maxc - minc;
                float s = cr / maxc;
                float rc = (maxc - r) / cr;
                float gc = (maxc - g) / cr;
                float bc = (maxc - b) / cr;
                float h;
                if (r == maxc) h = bc - gc;
                else if (g == maxc) h = (float)(2.0 + rc - bc);
                else h = (float)(4.0 + gc - rc);
                h = (float)((h / 6.0 + 1.0) % 1.0);
                int uh = (int)(h * 255.0);
                int us = (int)(s * 255.0);
                H[i] = (byte)(uh <= 0 ? 0 : uh >= 255 ? 255 : uh);
                S[i] = (byte)(us <= 0 ? 0 : us >= 255 ? 255 : us);
            }
        }

        // Image.convert('L') on RGB. Returns the highest value (getextrema's hi)
        public static int RgbToL(byte[] rgb, int count, byte[] L)
        {
            int hi = 0;
            for (int i = 0, p = 0; i < count; i++, p += 3)
            {
                int v = (rgb[p] * 19595 + rgb[p + 1] * 38470 + rgb[p + 2] * 7471 + 0x8000) >> 16;
                L[i] = (byte)v;
                if (v > hi) hi = v;
            }
            return hi;
        }

        // ImageFilter.BoxBlur(radius) on a square L image, integer radius: columns of rows first, then the other axis
        // (libImaging/BoxBlur.c). tmp, inp and outp all hold n * n bytes; inp and outp may be the same array.
        public static void BoxBlur(byte[] inp, byte[] outp, byte[] tmp, int n, int radius)
        {
            uint ww = (uint)((float)(1 << 24) / (radius * 2 + 1));
            uint fw = (uint)(((1u << 24) - (uint)(radius * 2 + 1) * ww) / 2);
            int edgeA = Math.Min(radius + 1, n);
            int edgeB = Math.Max(n - radius - 1, 0);
            for (int y = 0; y < n; y++) Line(inp, y * n, 1, tmp, y * n, 1, n - 1, radius, edgeA, edgeB, ww, fw);
            for (int x = 0; x < n; x++) Line(tmp, x, n, outp, x, n, n - 1, radius, edgeA, edgeB, ww, fw);
        }

        private static void Line(byte[] a, int o, int st, byte[] b, int bo, int bst, int lastx, int radius, int edgeA,
                                 int edgeB, uint ww, uint fw)
        {
            uint acc = (uint)(a[o] * (radius + 1));
            for (int x = 0; x < edgeA - 1; x++) acc += a[o + x * st];
            acc += (uint)(a[o + lastx * st] * (radius - edgeA + 1));
            int first = a[o], last = a[o + lastx * st];
            uint bulk;
            if (edgeA <= edgeB)
            {
                for (int x = 0; x < edgeA; x++)
                {
                    acc += (uint)(a[o + (x + radius) * st] - first);
                    bulk = acc * ww + (uint)(first + a[o + (x + radius + 1) * st]) * fw;
                    b[bo + x * bst] = (byte)((bulk + (1u << 23)) >> 24);
                }
                for (int x = edgeA; x < edgeB; x++)
                {
                    int sub = a[o + (x - radius - 1) * st];
                    acc += (uint)(a[o + (x + radius) * st] - sub);
                    bulk = acc * ww + (uint)(sub + a[o + (x + radius + 1) * st]) * fw;
                    b[bo + x * bst] = (byte)((bulk + (1u << 23)) >> 24);
                }
                for (int x = edgeB; x <= lastx; x++)
                {
                    int sub = a[o + (x - radius - 1) * st];
                    acc += (uint)(last - sub);
                    bulk = acc * ww + (uint)(sub + last) * fw;
                    b[bo + x * bst] = (byte)((bulk + (1u << 23)) >> 24);
                }
            }
            else
            {
                for (int x = 0; x < edgeB; x++)
                {
                    acc += (uint)(a[o + (x + radius) * st] - first);
                    bulk = acc * ww + (uint)(first + a[o + (x + radius + 1) * st]) * fw;
                    b[bo + x * bst] = (byte)((bulk + (1u << 23)) >> 24);
                }
                for (int x = edgeB; x < edgeA; x++)
                {
                    acc += (uint)(last - first);
                    bulk = acc * ww + (uint)(first + last) * fw;
                    b[bo + x * bst] = (byte)((bulk + (1u << 23)) >> 24);
                }
                for (int x = edgeA; x <= lastx; x++)
                {
                    int sub = a[o + (x - radius - 1) * st];
                    acc += (uint)(last - sub);
                    bulk = acc * ww + (uint)(sub + last) * fw;
                    b[bo + x * bst] = (byte)((bulk + (1u << 23)) >> 24);
                }
            }
        }

        // ImageDraw.ellipse(box, fill=255) on a new square L image (libImaging/Draw.c: the box truncated to ints, the
        // doubled-coordinate walk of one quarter, mirrored)
        public static byte[] FilledEllipse(int n, double x0d, double y0d, double x1d, double y1d)
        {
            byte[] m = new byte[n * n];
            int x0 = (int)x0d, y0 = (int)y0d, x1 = (int)x1d, y1 = (int)y1d;
            int a = x1 - x0, b = y1 - y0;
            if (a < 0 || b < 0) return m;
            long a2 = (long)a * a, b2 = (long)b * b, a2b2 = a2 * b2;
            int cx = a, cy = b % 2, ex = a % 2, ey = b;
            while (true)
            {
                int ya = y0 + (cy + b) / 2, yb = y0 + (b - cy) / 2;
                int xa = x0 + (a - cx) / 2, xb = x0 + (a + cx) / 2;
                if (xa < 0) xa = 0;
                if (xb > n - 1) xb = n - 1;
                if (ya >= 0 && ya < n) for (int x = xa; x <= xb; x++) m[ya * n + x] = 255;
                if (yb >= 0 && yb < n) for (int x = xa; x <= xb; x++) m[yb * n + x] = 255;
                if (cx == ex && cy == ey) break;
                int nx = cx, ny = cy + 2;
                long nd = Delta(a2, b2, a2b2, nx, ny);
                if (nx > 1)
                {
                    long d2 = Delta(a2, b2, a2b2, cx - 2, cy + 2);
                    if (nd > d2)
                    {
                        nx = cx - 2;
                        ny = cy + 2;
                        nd = d2;
                    }
                    d2 = Delta(a2, b2, a2b2, cx - 2, cy);
                    if (nd > d2)
                    {
                        nx = cx - 2;
                        ny = cy;
                    }
                }
                cx = nx;
                cy = ny;
            }
            return m;
        }

        private static long Delta(long a2, long b2, long a2b2, long x, long y)
        {
            return Math.Abs(a2 * y * y + b2 * x * x - a2b2);
        }

        // Image.resize((outW, outH), BILINEAR) on RGB (libImaging/Resample.c): horizontal pass, then vertical, 22-bit
        // fixed-point coefficients
        public static byte[] ResizeBilinear(byte[] rgb, int w, int h, int outW, int outH)
        {
            if (w == outW && h == outH) return rgb;
            int[] xb, xk, yb, yk;
            int xs, ys;
            Coeffs(w, outW, out xb, out xk, out xs);
            Coeffs(h, outH, out yb, out yk, out ys);
            byte[] t = rgb;
            int tw = w;
            if (w != outW)
            {
                t = new byte[outW * h * 3];
                for (int y = 0; y < h; y++)
                {
                    for (int x = 0; x < outW; x++)
                    {
                        int xmin = xb[2 * x], cnt = xb[2 * x + 1], ko = x * xs;
                        for (int c = 0; c < 3; c++)
                        {
                            int ss = 1 << 21;
                            for (int i = 0; i < cnt; i++) ss += rgb[(y * w + xmin + i) * 3 + c] * xk[ko + i];
                            t[(y * outW + x) * 3 + c] = Clip(ss);
                        }
                    }
                }
                tw = outW;
            }
            if (h == outH) return t;
            byte[] o = new byte[outW * outH * 3];
            for (int y = 0; y < outH; y++)
            {
                int ymin = yb[2 * y], cnt = yb[2 * y + 1], ko = y * ys;
                for (int x = 0; x < outW; x++)
                {
                    for (int c = 0; c < 3; c++)
                    {
                        int ss = 1 << 21;
                        for (int i = 0; i < cnt; i++) ss += t[((ymin + i) * tw + x) * 3 + c] * yk[ko + i];
                        o[(y * outW + x) * 3 + c] = Clip(ss);
                    }
                }
            }
            return o;
        }

        private static byte Clip(int ss)
        {
            int v = ss >> 22;
            return (byte)(v < 0 ? 0 : v > 255 ? 255 : v);
        }

        private static void Coeffs(int inSize, int outSize, out int[] bounds, out int[] kk, out int ksize)
        {
            double scale = (double)inSize / outSize;
            double fs = scale < 1.0 ? 1.0 : scale;
            double support = 1.0 * fs;
            ksize = (int)Math.Ceiling(support) * 2 + 1;
            bounds = new int[outSize * 2];
            kk = new int[outSize * ksize];
            double[] k = new double[ksize];
            double ss = 1.0 / fs;
            for (int xx = 0; xx < outSize; xx++)
            {
                double center = (xx + 0.5) * scale;
                double ww = 0.0;
                int xmin = (int)(center - support + 0.5);
                if (xmin < 0) xmin = 0;
                int xmax = (int)(center + support + 0.5);
                if (xmax > inSize) xmax = inSize;
                xmax -= xmin;
                for (int x = 0; x < xmax; x++)
                {
                    double u = Math.Abs((x + xmin - center + 0.5) * ss);
                    double w = u < 1.0 ? 1.0 - u : 0.0;
                    k[x] = w;
                    ww += w;
                }
                for (int x = 0; x < xmax; x++)
                {
                    if (ww != 0.0) k[x] /= ww;
                    double f = k[x] * (1 << 22);
                    kk[xx * ksize + x] = f < 0 ? (int)(-0.5 + f) : (int)(0.5 + f);
                }
                bounds[2 * xx] = xmin;
                bounds[2 * xx + 1] = xmax;
            }
        }
    }

    internal sealed class Geo
    {
        public double Cx, Cy, Rim, H, Kz, Sc, Ccx, Ccy;
        public int? Level;
        public string Cls;
        public int X0, Y0, X1, Y1, N;

        public Geo(double cx, double cy, double rim, double h, double kz, int? level, string cls)
        {
            Cx = cx;
            Cy = cy;
            Rim = rim;
            H = h;
            Kz = kz;
            Level = level;
            Cls = cls;
            N = (int)Math.Floor(2 * rim + 0.5);
            X0 = (int)Math.Floor(cx - rim + 0.5);
            Y0 = (int)Math.Floor(cy - rim + 0.5);
            X1 = X0 + N;
            Y1 = Y0 + N;
            Sc = rim > 0 ? rim / Detect.RIM_1080 : h / 1080.0;
            Ccx = cx - X0;
            Ccy = cy - Y0;
        }

        public static Geo FromMod(Dictionary<string, string> m)
        {
            string lv = Detect.Get(m, "level");
            int? level = lv == "-1" ? -1 : lv == "0" ? 0 : lv == "1" ? (int?)1 : null;
            string c = Detect.Get(m, "class");
            if (c != "small" && c != "big") c = null;
            return new Geo(Detect.Num(m, "cx", 0), Detect.Num(m, "cy", 0), Detect.Num(m, "rim", 0),
                           Detect.Num(m, "h", 1080), Detect.Num(m, "kz", 0), level, c);
        }
    }

    internal sealed class Dot
    {
        public string Band, Why, Fit;
        public double Prior, X, Y, Dx, Dy, R, Fill, Conc, ConeDir, Score, Edge;
        public int NPx, Bw, Bh, Core, Cone;
        public bool ShapeOk;
    }

    internal sealed class Grid
    {
        public bool Ok;
        public string Why = "", Cls;
        public double Cell, Fx, Fy, ErrPx, Contrast, Cover;
        public int? Level;
        public int Teeth;
    }

    internal sealed class Analysis
    {
        public List<Dot> Dots;
        public Grid Grid;
        public Geo Geo;
        public double Ms;
        public byte[] Rgb;
        public int GrayMax;
    }

    internal sealed class Prior
    {
        public double Vx, Vy, Err;
    }

    internal sealed class Fix
    {
        public string How = "none", Note = "";
        public double Vx, Vy, Err, Cell, Kz;
        public int? Level, GainLevel;       // Level null: '?'
        public Dot Dot;

        public Fix Copy()
        {
            return (Fix)MemberwiseClone();
        }
    }

    internal sealed class Detect
    {
        public const double GRID_M = 65.0, RIM_1080 = 222.0;
        private const int CONE_S_MIN = 90, CONE_V_LO = 40, CONE_V_HI = 199;
        private const double DOT_D_1080 = 12.5;
        private const double PART_MIN = 0.30, PART_EDGE = 0.30, PART_ERR = 2.5;
        private const double GRID_MIN_SCORE = 5.0, GRID_MIN_AXIS = 2.5, GRID_MIN_MARGIN = 1.15;
        private const double GRID_MIN_COVER = 0.6, GRID_COVER_R = 0.7, GRID_MAX_RMS = 1.2;
        private const double LEVEL_TOL = 0.015, DOT_GRID_MAX = 8.0;
        private const int SECTORS = 8;

        private static readonly string[] BAND_NAME = { "yellow", "orange", "green", "blue", "pink" };
        private static readonly int[] BAND_LO = { 30, 14, 62, 118, 195 };
        private static readonly int[] BAND_HI = { 46, 27, 110, 175, 245 };
        private static readonly int[] BAND_S = { 170, 170, 120, 120, 100 };
        private static readonly int[] BAND_V = { 200, 200, 160, 160, 170 };
        private static readonly double[] BAND_W = { 1.0, 0.35, 0.35, 0.35, 0.35 };
        private static readonly double[] CELL_K = { 0.554, 0.7805, 1.4766, 2.953 };
        private static readonly int[] CELL_LEVEL = { -1, -1, 0, 1 };
        private static readonly string[] CELL_CLS = { "big", "small", null, null };

        public static string Get(Dictionary<string, string> m, string k)
        {
            string v;
            return m.TryGetValue(k, out v) ? v : null;
        }

        public static bool TryFloat(string s, out double v)
        {
            v = 0;
            return s != null && double.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out v);
        }

        public static double Num(Dictionary<string, string> m, string k, double d)
        {
            double v;
            return TryFloat(Get(m, k), out v) ? v : d;
        }

        private static double Hypot(double x, double y)
        {
            return Math.Sqrt(x * x + y * y);
        }

        private static double PyMod(double a, double b)
        {
            double r = a % b;
            if (r != 0 && (r < 0) != (b < 0)) r += b;
            return r;
        }

        public static double? KzTheory(int? level, string cls, double sc)
        {
            if (level == null) return null;
            if (level == -1)
            {
                if (cls == "small") return 0.7805 * sc;
                if (cls == "big") return 0.554 * sc;
                return null;
            }
            if (level == 0) return 1.4766 * sc;
            if (level == 1) return 2.953 * sc;
            return null;
        }

        public static double Gain(int? level)
        {
            return level == -1 ? 0.269 : level == 1 ? 0.123 : 0.246;
        }

        public static double? ViewLimit(string cls, double kz, double rim)
        {
            double R;
            if (cls == "small") R = 285.3;
            else if (cls == "big") R = 400.7;
            else return null;
            if (kz == 0) return null;
            return Math.Max(0.0, R - rim / kz);
        }

        // buffers kept between frames: 30 frames a second of large arrays would otherwise keep the collector busy
        private int nBuf = -1;
        private byte[] bH, bS, bV, bCoded, bEr, bGray, bTmp, bBlur, bHp;
        private byte[] seen;
        private byte[][] coneMask = new byte[5][];
        private bool[] coneValid = new bool[5];
        private readonly byte[] hlStrict = new byte[256], hlLoose = new byte[256];
        private int smStrict = 255, vmStrict = 255, smLoose = 255, vmLoose = 255;
        private int[] flood = new int[0];

        private int maskN = -1;
        private double maskCx, maskCy, maskR;
        private byte[] mask;
        private float[] wtsCol, wtsRow;
        private float[] prof1, prof2;

        private int sectHalf = -1;
        private double sectR0, sectR1;
        private int[] sectX, sectY;
        private byte[] sectS;
        private double[] sectC = new double[SECTORS], sectSn = new double[SECTORS];

        public Detect()
        {
            for (int i = 0; i < 5; i++)
            {
                bool strict = BAND_S[i] >= 170;
                byte[] hl = strict ? hlStrict : hlLoose;
                for (int h = Math.Max(0, BAND_LO[i]); h <= Math.Min(255, BAND_HI[i]); h++) hl[h] = (byte)(40 * (i + 1));
                if (strict)
                {
                    smStrict = Math.Min(smStrict, BAND_S[i]);
                    vmStrict = Math.Min(vmStrict, BAND_V[i]);
                }
                else
                {
                    smLoose = Math.Min(smLoose, BAND_S[i]);
                    vmLoose = Math.Min(vmLoose, BAND_V[i]);
                }
            }
            for (int s = 0; s < SECTORS; s++)
            {
                double ang = (s + 0.5) / SECTORS * 2 * Math.PI;
                sectC[s] = Math.Cos(ang);
                sectSn[s] = Math.Sin(ang);
            }
        }

        private void Ensure(int n)
        {
            if (n == nBuf) return;
            int nn = n * n;
            bH = new byte[nn];
            bS = new byte[nn];
            bV = new byte[nn];
            bCoded = new byte[nn];
            bEr = new byte[nn];
            bGray = new byte[nn];
            bTmp = new byte[nn];
            bBlur = new byte[nn];
            bHp = new byte[nn];
            seen = new byte[nn];
            coneMask = new byte[5][];
            prof1 = new float[n];
            prof2 = new float[n];
            nBuf = n;
        }

        public Analysis Analyse(byte[] rgb, Geo geo)
        {
            long t0 = Stopwatch.GetTimestamp();
            if (geo.N <= 0 || geo.N > 8192) throw new InvalidOperationException("capture box of " + geo.N + " px");
            Ensure(geo.N);
            Analysis a = new Analysis();
            a.Geo = geo;
            a.Rgb = rgb;
            a.Dots = FindDots(rgb, geo);
            a.GrayMax = Pil.RgbToL(rgb, geo.N * geo.N, bGray);
            a.Grid = MeasureGrid(geo);
            a.Ms = (Stopwatch.GetTimestamp() - t0) * 1000.0 / Stopwatch.Frequency;
            return a;
        }

        private static int Odd(double v)
        {
            int r = (int)Math.Round(v);
            return r % 2 != 0 ? r : r + 1;
        }

        // ------------------------------------------------------------------------------------------------ dots
        private List<Dot> FindDots(byte[] rgb, Geo geo)
        {
            int n = geo.N, nn = n * n;
            double sc = geo.Sc;
            Pil.RgbToHsv(rgb, nn, bH, bS, bV);
            for (int i = 0; i < 5; i++) coneValid[i] = false;
            double D = DOT_D_1080 * sc;
            double area = Math.PI / 4 * D * D;
            byte[] cd = bCoded, ed = bEr;
            for (int i = 0; i < nn; i++)
            {
                int h = bH[i], s = bS[i], v = bV[i], c = 0;
                if (s >= smStrict && v >= vmStrict) c = hlStrict[h];
                if (s >= smLoose && v >= vmLoose && hlLoose[h] > c) c = hlLoose[h];
                cd[i] = (byte)c;
                ed[i] = (byte)(c != 0 ? 255 : 0);
            }
            int k = Math.Max(3, Odd(5 * sc));
            Pil.BoxBlur(ed, ed, bTmp, n, k / 2);
            bool any = false;
            for (int i = 0; i < nn; i++)
            {
                if (ed[i] >= 254)
                {
                    ed[i] = 255;
                    any = true;
                }
                else
                {
                    ed[i] = 0;
                }
            }
            List<Dot> res = new List<Dot>();
            if (!any) return res;
            Array.Clear(seen, 0, nn);
            int limit = (int)(3 * area) + 20;
            List<int> comp = new List<int>(limit);
            StringBuilder why = new StringBuilder();
            for (int p0 = 0; p0 < nn; p0++)
            {
                if (ed[p0] == 0 || seen[p0] != 0) continue;
                int code = cd[p0];
                bool big = Flood(p0, code, n, limit, comp);
                if (big) continue;
                int bi = code / 40 - 1;
                int minx = int.MaxValue, maxx = int.MinValue, miny = int.MaxValue, maxy = int.MinValue, core = 0;
                long sumx = 0, sumy = 0;
                foreach (int q in comp)
                {
                    int qx = q % n, qy = q / n;
                    if (qx < minx) minx = qx;
                    if (qx > maxx) maxx = qx;
                    if (qy < miny) miny = qy;
                    if (qy > maxy) maxy = qy;
                    sumx += qx;
                    sumy += qy;
                    if (ed[q] != 0) core++;
                }
                Dot d = new Dot();
                d.Band = BAND_NAME[bi];
                d.Prior = BAND_W[bi];
                d.NPx = comp.Count;
                d.Bw = maxx - minx + 1;
                d.Bh = maxy - miny + 1;
                d.Fill = d.NPx / (double)(d.Bw * d.Bh);
                d.Core = core;
                double mx = sumx / (double)d.NPx, my = sumy / (double)d.NPx;
                d.X = geo.X0 + mx;
                d.Y = geo.Y0 + my;
                d.Dx = d.X - geo.Cx;
                d.Dy = d.Y - geo.Cy;
                d.R = Hypot(d.Dx, d.Dy);
                why.Length = 0;
                bool rim = false;
                double ra = d.NPx / area;
                if (!(0.75 <= ra && ra <= 1.2)) Add(why, "area");
                if (!(0.8 * D <= d.Bw && d.Bw <= 1.2 * D && 0.8 * D <= d.Bh && d.Bh <= 1.2 * D)) Add(why, "size");
                if (Math.Max(d.Bw, d.Bh) > 1.3 * Math.Min(d.Bw, d.Bh)) Add(why, "aspect");
                if (!(0.6 <= d.Fill && d.Fill <= 0.93)) Add(why, "fill");
                if (d.Core < 8 * sc * sc) Add(why, "core");
                if (d.R > geo.Rim - 0.6 * D - 2)
                {
                    Add(why, "rim");                     // clipped by the circle: the centroid would be off
                    rim = true;
                }
                d.ShapeOk = why.Length == 0;
                d.Why = why.ToString();
                double cx_ = 0, cy_ = 0;
                if (d.ShapeOk)
                {
                    d.Fit = "whole";
                    cx_ = mx;
                    cy_ = my;
                }
                else if (d.Band == "yellow" && !rim && d.NPx >= PART_MIN * area)
                {
                    double fx, fy, edge;
                    int inside;
                    if (DiscFit(comp, n, D, out fx, out fy, out edge, out inside))
                    {
                        double fr = Hypot(geo.X0 + fx - geo.Cx, geo.Y0 + fy - geo.Cy);
                        if (edge >= PART_EDGE && inside >= PART_MIN * area && fr <= geo.Rim - 0.6 * D - 2)
                        {
                            d.Fit = "part";
                            d.Edge = edge;
                            cx_ = fx;
                            cy_ = fy;
                            d.X = geo.X0 + fx;
                            d.Y = geo.Y0 + fy;
                            d.Dx = d.X - geo.Cx;
                            d.Dy = d.Y - geo.Cy;
                            d.R = fr;
                        }
                    }
                }
                if (d.Fit != null) Cone(d, ConeMask(bi, nn), n, cx_, cy_, D);
                res.Add(d);
            }
            return res;
        }

        private static void Add(StringBuilder sb, string s)
        {
            if (sb.Length > 0) sb.Append(',');
            sb.Append(s);
        }

        // the 8-connected pixels of one band code from p0 (at most limit kept), in the Python stack's order: the disc
        // fit's tie break depends on it
        private bool Flood(int p0, int code, int n, int limit, List<int> comp)
        {
            comp.Clear();
            byte[] cd = bCoded;
            int nn = n * n, last = n - 1;
            if (flood.Length < nn + 8) flood = new int[nn + 8];
            int[] st = flood;
            int sp = 0;
            st[sp++] = p0;
            seen[p0] = 1;
            int[] nb = new int[8];
            while (sp > 0)
            {
                int q = st[--sp];
                if (comp.Count < limit) comp.Add(q);
                int qx = q % n, cnt;
                if (qx == 0)
                {
                    nb[0] = q - n; nb[1] = q + n; nb[2] = q - n + 1; nb[3] = q + 1; nb[4] = q + n + 1;
                    cnt = 5;
                }
                else if (qx == last)
                {
                    nb[0] = q - n; nb[1] = q + n; nb[2] = q - n - 1; nb[3] = q - 1; nb[4] = q + n - 1;
                    cnt = 5;
                }
                else
                {
                    nb[0] = q - n; nb[1] = q + n; nb[2] = q - n - 1; nb[3] = q - 1; nb[4] = q + n - 1;
                    nb[5] = q - n + 1; nb[6] = q + 1; nb[7] = q + n + 1;
                    cnt = 8;
                }
                for (int i = 0; i < cnt; i++)
                {
                    int r = nb[i];
                    if (r >= 0 && r < nn && seen[r] == 0 && cd[r] == code)
                    {
                        seen[r] = 1;
                        st[sp++] = r;
                    }
                }
            }
            return comp.Count >= limit;
        }

        // a circle of the icon's diameter D fitted to a blob that failed the shape test (detect.py _disc_fit)
        private static bool DiscFit(List<int> comp, int n, double D, out double cx, out double cy, out double edgeShare,
                                    out int inside)
        {
            cx = cy = edgeShare = 0;
            inside = 0;
            HashSet<int> inb = new HashSet<int>(comp);
            double Rv = D / 2.0 - 0.5;
            List<int> ex = new List<int>(), ey = new List<int>();
            foreach (int q in comp)
            {
                if (!inb.Contains(q - 1) || !inb.Contains(q + 1) || !inb.Contains(q - n) || !inb.Contains(q + n))
                {
                    ex.Add(q % n);
                    ey.Add(q / n);
                }
            }
            if (ex.Count < 6) return false;
            int steps = Math.Max(24, (int)(2 * Math.PI * Rv / 0.5));
            double[] ox = new double[steps], oy = new double[steps];
            for (int i = 0; i < steps; i++)
            {
                ox[i] = Rv * Math.Cos(2 * Math.PI * i / steps);
                oy[i] = Rv * Math.Sin(2 * Math.PI * i / steps);
            }
            // the votes in first-seen order: Python's max() over a dict takes the first of equal peaks
            Dictionary<long, int> slot = new Dictionary<long, int>();
            List<long> keys = new List<long>();
            List<int> votes = new List<int>();
            for (int e = 0; e < ex.Count; e++)
            {
                for (int i = 0; i < steps; i++)
                {
                    long kx = (long)Math.Round(ex[e] + ox[i]), ky = (long)Math.Round(ey[e] + oy[i]);
                    long key = ((kx + 100000) << 32) | (ky + 100000);
                    int s;
                    if (slot.TryGetValue(key, out s))
                    {
                        votes[s]++;
                    }
                    else
                    {
                        slot[key] = keys.Count;
                        keys.Add(key);
                        votes.Add(1);
                    }
                }
            }
            int bestS = 0;
            for (int s = 1; s < votes.Count; s++) if (votes[s] > votes[bestS]) bestS = s;
            cx = (double)((keys[bestS] >> 32) - 100000);
            cy = (double)((keys[bestS] & 0xFFFFFFFFL) - 100000);
            int on = 0;
            for (int it = 0; it < 4; it++)
            {
                on = 0;
                double sx = 0, sy = 0;
                for (int e = 0; e < ex.Count; e++)
                {
                    double dx = ex[e] - cx, dy = ey[e] - cy;
                    double r = Hypot(dx, dy);
                    if (r > 1e-6 && Math.Abs(r - Rv) <= 1.5)
                    {
                        on++;
                        sx += ex[e] - Rv * dx / r;
                        sy += ey[e] - Rv * dy / r;
                    }
                }
                if (on == 0) return false;
                cx = sx / on;
                cy = sy / on;
            }
            double rr = (D / 2.0 + 0.5) * (D / 2.0 + 0.5);
            foreach (int q in comp)
            {
                double dx = q % n - cx, dy = q / n - cy;
                if (dx * dx + dy * dy <= rr) inside++;
            }
            edgeShare = Math.Min(1.0, on / (2 * Math.PI * Rv));
            return true;
        }

        private byte[] ConeMask(int bi, int nn)
        {
            if (coneMask[bi] == null) coneMask[bi] = new byte[nn];
            byte[] m = coneMask[bi];
            if (!coneValid[bi])
            {
                int lo = BAND_LO[bi], hi = BAND_HI[bi];
                for (int i = 0; i < nn; i++)
                {
                    int h = bH[i], v = bV[i];
                    m[i] = (byte)(h >= lo && h <= hi && bS[i] >= CONE_S_MIN && v >= CONE_V_LO && v <= CONE_V_HI ? 255 : 0);
                }
                coneValid[bi] = true;
            }
            return m;
        }

        // the annulus r0 <= r <= r1 around the disc, by sector (detect.py _sectors)
        private void Sectors(int half, double r0, double r1)
        {
            if (half == sectHalf && r0 == sectR0 && r1 == sectR1) return;
            List<int> xs = new List<int>(), ys = new List<int>();
            List<byte> ss = new List<byte>();
            for (int y = -half; y <= half; y++)
            {
                for (int x = -half; x <= half; x++)
                {
                    double r = Hypot(x, y);
                    if (r0 <= r && r <= r1)
                    {
                        double ang = PyMod(Math.Atan2((double)y, (double)x), 2 * Math.PI);
                        int sec = (int)(ang / (2 * Math.PI) * SECTORS) % SECTORS;
                        xs.Add(x);
                        ys.Add(y);
                        ss.Add((byte)sec);
                    }
                }
            }
            sectX = xs.ToArray();
            sectY = ys.ToArray();
            sectS = ss.ToArray();
            sectHalf = half;
            sectR0 = r0;
            sectR1 = r1;
        }

        private readonly int[] sectN = new int[SECTORS];

        private void Cone(Dot d, byte[] cm, int n, double mx, double my, double D)
        {
            int half = (int)Math.Round(3.2 * D);
            Sectors(half, 0.72 * D, 3.2 * D);
            int cxp = (int)Math.Round(mx), cyp = (int)Math.Round(my);
            Array.Clear(sectN, 0, SECTORS);
            for (int i = 0; i < sectX.Length; i++)
            {
                int x = cxp + sectX[i], y = cyp + sectY[i];
                if (x >= 0 && y >= 0 && x < n && y < n && cm[y * n + x] == 255) sectN[sectS[i]]++;
            }
            double sx = 0, sy = 0;
            int cnt = 0;
            for (int s = 0; s < SECTORS; s++)
            {
                cnt += sectN[s];
                sx += sectN[s] * sectC[s];
                sy += sectN[s] * sectSn[s];
            }
            d.Cone = cnt;
            if (cnt != 0)
            {
                d.Conc = Hypot(sx, sy) / cnt;
                d.ConeDir = Math.Atan2(sy, sx) * 180.0 / Math.PI;
            }
        }

        public static bool HasCone(Dot d, double sc)
        {
            return d.Cone >= 150 * sc * sc && d.Conc >= 0.5;
        }

        // ------------------------------------------------------------------------------------------------ grid
        private void Profiles(Geo geo, out double[] qx, out double[] qy)
        {
            int n = geo.N, nn = n * n;
            double sc = geo.Sc;
            double rr = geo.Rim - 14 * sc;
            if (mask == null || maskN != n || maskCx != geo.Ccx || maskCy != geo.Ccy || maskR != rr)
            {
                mask = Pil.FilledEllipse(n, geo.Ccx - rr, geo.Ccy - rr, geo.Ccx + rr, geo.Ccy + rr);
                wtsCol = new float[n];
                wtsRow = new float[n];
                ReduceAxes(mask, n, wtsCol, wtsRow, true);
                maskN = n;
                maskCx = geo.Ccx;
                maskCy = geo.Ccy;
                maskR = rr;
            }
            int rad = Math.Max(2, (int)Math.Round(3 * sc));
            Pil.BoxBlur(bGray, bBlur, bTmp, n, rad);
            for (int i = 0; i < nn; i++)
            {
                if (mask[i] == 0)
                {
                    bHp[i] = 128;
                    continue;
                }
                int v = bGray[i] - bBlur[i] + 128;            // subtract(.., 1, 128), then the +-12 clamp: icons and
                bHp[i] = (byte)(v < 116 ? 116 : v > 140 ? 140 : v);   // text are clamped so the faint lines count
            }
            ReduceAxes(bHp, n, prof1, prof2, false);
            qx = Smooth(prof1, wtsCol, n);
            qy = Smooth(prof2, wtsRow, n);
        }

        // reduce((1, n)) and reduce((n, 1)) on the image converted to mode F: a double sum times 1/n, stored as float32
        private static void ReduceAxes(byte[] img, int n, float[] col, float[] row, bool unused)
        {
            long[] sc = new long[n];
            double mult = 1.0 / n;
            for (int y = 0; y < n; y++)
            {
                long sr = 0;
                int o = y * n;
                for (int x = 0; x < n; x++)
                {
                    int v = img[o + x];
                    sr += v;
                    sc[x] += v;
                }
                row[y] = (float)(sr * mult);
            }
            for (int x = 0; x < n; x++) col[x] = (float)(sc[x] * mult);
        }

        // NaN stands for Python's None
        private static double[] Smooth(float[] prof, float[] w, int n)
        {
            double[] p = new double[n], q = new double[n];
            for (int i = 0; i < n; i++)
            {
                double ww = w[i];
                p[i] = ww > 40 ? ((double)prof[i] - 128.0) * 255.0 / ww : double.NaN;
            }
            for (int i = 0; i < n; i++)
            {
                if (double.IsNaN(p[i]))
                {
                    q[i] = double.NaN;
                    continue;
                }
                double a = i > 0 && !double.IsNaN(p[i - 1]) ? p[i - 1] : p[i];
                double b = i + 1 < n && !double.IsNaN(p[i + 1]) ? p[i + 1] : p[i];
                q[i] = 0.25 * a + 0.5 * p[i] + 0.25 * b;
            }
            return q;
        }

        private static void Comb(double[] q, double P, out double cOut, out double wOut, out double phase)
        {
            int B = Math.Max(12, 2 * (int)Math.Round(P / 2));
            double[] acc = new double[B], wsq = new double[B];
            for (int i = 0; i < q.Length; i++)
            {
                double v = q[i];
                if (double.IsNaN(v)) continue;
                double f = (i % P) / P * B;
                int b = (int)f;
                double t = f - b;
                b %= B;
                int b2 = (b + 1) % B;
                acc[b] += v * (1 - t);
                wsq[b] += (1 - t) * (1 - t);
                acc[b2] += v * t;
                wsq[b2] += t * t;
            }
            int h = B / 2;
            double best = -1e18, bw = 1.0;
            int bk = 0;
            for (int b = 0; b < B; b++)
            {
                int o2 = (b + h) % B;
                double w = wsq[b] + wsq[o2];
                if (w <= 0) continue;
                double z = (acc[b] - acc[o2]) / Math.Sqrt(w);
                if (z > best)
                {
                    best = z;
                    bk = b;
                    bw = w;
                }
            }
            int o = (bk + h) % B;
            cOut = acc[bk] - acc[o];
            wOut = bw;
            double[] sm = new double[B];
            for (int b = 0; b < B; b++) sm[b] = 0.25 * acc[(b + B - 1) % B] + 0.5 * acc[b] + 0.25 * acc[(b + 1) % B];
            int pk = 0;
            for (int b = 1; b < B; b++) if (sm[b] > sm[pk]) pk = b;
            double s0 = sm[(pk + B - 1) % B], s1 = sm[pk], s2 = sm[(pk + 1) % B];
            double den = s0 - 2 * s1 + s2;
            double off = den < 0 ? 0.5 * (s0 - s2) / den : 0.0;
            phase = PyMod((pk + Math.Max(-0.5, Math.Min(0.5, off))) * P / B, P);
        }

        private struct Tooth
        {
            public int K;
            public double P, S;
        }

        private static List<Tooth> Teeth(double[] q, double P, double phase)
        {
            int n = q.Length;
            int w = Math.Max(3, (int)Math.Round(0.15 * P));
            List<Tooth> res = new List<Tooth>();
            int k = (int)Math.Ceiling(-phase / P);
            while (phase + k * P <= n)
            {
                double t = phase + k * P;
                bool have = false;
                double best = 0;
                int bi = 0;
                int i0 = Math.Max(1, (int)Math.Floor(t - w)), i1 = Math.Min(n - 1, (int)Math.Ceiling(t + w) + 1);
                for (int i = i0; i < i1; i++)
                {
                    double v = q[i];
                    if (double.IsNaN(v) || double.IsNaN(q[i - 1]) || double.IsNaN(q[i + 1])) continue;
                    if (v >= q[i - 1] && v >= q[i + 1] && (!have || v > best))
                    {
                        have = true;
                        best = v;
                        bi = i;
                    }
                }
                if (have)
                {
                    double a = q[bi - 1], b0 = q[bi], c = q[bi + 1];
                    double den = a - 2 * b0 + c;
                    double off = den < 0 ? 0.5 * (a - c) / den : 0.0;
                    Tooth th;
                    th.K = k;
                    th.P = bi + Math.Max(-0.5, Math.Min(0.5, off));
                    th.S = best;
                    res.Add(th);
                }
                k++;
            }
            return res;
        }

        private Grid MeasureGrid(Geo geo)
        {
            Grid g = new Grid();
            double[] qx, qy;
            Profiles(geo, out qx, out qy);
            int cnt = 0;
            double sum2 = 0;
            foreach (double[] pr in new[] { qx, qy })
            {
                foreach (double v in pr)
                {
                    if (double.IsNaN(v)) continue;
                    cnt++;
                    sum2 += v * v;
                }
            }
            if (cnt < 50)
            {
                g.Why = "no profile";
                return g;
            }
            double sigma = Math.Sqrt(sum2 / cnt);
            if (sigma == 0) sigma = 1.0;
            int m = CELL_K.Length;
            double[] zs = new double[m], zmins = new double[m], Ps = new double[m], pxs = new double[m], pys = new double[m];
            for (int i = 0; i < m; i++)
            {
                double P0 = GRID_M * CELL_K[i] * geo.Sc;
                double c1, w1, p1, c2, w2, p2;
                Comb(qx, P0, out c1, out w1, out p1);
                Comb(qy, P0, out c2, out w2, out p2);
                zs[i] = (c1 + c2) / Math.Sqrt(w1 + w2) / sigma;
                zmins[i] = Math.Min(c1 / Math.Sqrt(w1), c2 / Math.Sqrt(w2)) / sigma;
                Ps[i] = P0;
                pxs[i] = p1;
                pys[i] = p2;
            }
            // sorted by score, best first; a stable sort, as Python's
            int top = 0;
            for (int i = 1; i < m; i++) if (zs[i] > zs[top]) top = i;
            int second = -1;
            for (int i = 0; i < m; i++) if (i != top && (second < 0 || zs[i] > zs[second])) second = i;
            double tot = zs[top], mn = zmins[top], P = Ps[top], px_ = pxs[top], py_ = pys[top];
            g.Contrast = tot;
            double margin = zs[second] > 0 ? tot / zs[second] : 9.9;
            if (tot < GRID_MIN_SCORE || mn < GRID_MIN_AXIS)
            {
                g.Why = "weak " + Fmt.F(tot, 1) + "/" + Fmt.F(mn, 1);
                return g;
            }
            if (margin < GRID_MIN_MARGIN)
            {
                g.Why = "ambiguous " + Fmt.F(Ps[top], 1) + " vs " + Fmt.F(Ps[second], 1);
                return g;
            }
            List<Tooth>[] keep = new List<Tooth>[2];
            int nPred = 0, nHit = 0;
            double rr = GRID_COVER_R * geo.Rim;
            for (int ax = 0; ax < 2; ax++)
            {
                double ph0 = ax == 0 ? px_ : py_, cc = ax == 0 ? geo.Ccx : geo.Ccy;
                List<Tooth> tt = Teeth(ax == 0 ? qx : qy, P, ph0);
                double smax = 0;
                bool first = true;
                foreach (Tooth th in tt)
                {
                    if (first || th.S > smax) smax = th.S;
                    first = false;
                }
                List<Tooth> kept = new List<Tooth>();
                HashSet<int> ks = new HashSet<int>();
                foreach (Tooth th in tt)
                {
                    if (th.S >= 0.35 * smax && th.S > 1.0)
                    {
                        kept.Add(th);
                        ks.Add(th.K);
                    }
                }
                keep[ax] = kept;
                int k = (int)Math.Ceiling((cc - rr - ph0) / P);
                while (ph0 + k * P <= cc + rr)
                {
                    nPred++;
                    if (ks.Contains(k)) nHit++;
                    k++;
                }
            }
            g.Cover = nPred != 0 ? nHit / (double)nPred : 0.0;
            if (keep[0].Count == 0 || keep[1].Count == 0)
            {
                g.Why = "teeth";
                return g;
            }
            if (g.Cover < GRID_MIN_COVER)
            {
                g.Why = "lines " + nHit + " of " + nPred;
                return g;
            }
            double num = 0, den = 0;
            foreach (List<Tooth> tt in keep)
            {
                double kb = 0, pb = 0;
                foreach (Tooth th in tt)
                {
                    kb += th.K;
                    pb += th.P;
                }
                kb /= tt.Count;
                pb /= tt.Count;
                foreach (Tooth th in tt)
                {
                    num += (th.K - kb) * (th.P - pb);
                    den += (th.K - kb) * (th.K - kb);
                }
            }
            if (den <= 0)
            {
                g.Why = "one line per axis";
                return g;
            }
            double Pm = num / den;
            if (Math.Abs(Pm / P - 1) > 0.03)
            {
                g.Why = "period fit " + Fmt.F(Pm, 1) + " vs " + Fmt.F(P, 1);
                return g;
            }
            double[] ph = new double[2];
            double resSum = 0;
            int nt = 0;
            for (int ax = 0; ax < 2; ax++)
            {
                double f = 0;
                foreach (Tooth th in keep[ax]) f += th.P - th.K * Pm;
                f /= keep[ax].Count;
                ph[ax] = f;
                foreach (Tooth th in keep[ax])
                {
                    double r = th.P - th.K * Pm - f;
                    resSum += r * r;
                    nt++;
                }
            }
            double rms = Math.Sqrt(resSum / nt);
            if (rms > GRID_MAX_RMS * geo.Sc)
            {
                g.Why = "lines off the period by " + Fmt.F(rms, 1) + " px rms";
                return g;
            }
            g.Fx = ph[0] + Pm * Math.Round((geo.Ccx - ph[0]) / Pm);
            g.Fy = ph[1] + Pm * Math.Round((geo.Ccy - ph[1]) / Pm);
            g.Cell = Pm;
            g.Teeth = nt;
            g.ErrPx = Math.Sqrt(0.3 * 0.3 + rms * rms);
            int bestCell = 0;
            double bestLog = double.MaxValue;
            for (int i = 0; i < m; i++)
            {
                double l = Math.Abs(Math.Log(Pm / (GRID_M * CELL_K[i] * geo.Sc)));
                if (l < bestLog)
                {
                    bestLog = l;
                    bestCell = i;
                }
            }
            if (Math.Abs(Pm / (GRID_M * CELL_K[bestCell] * geo.Sc) - 1) <= LEVEL_TOL)
            {
                g.Level = CELL_LEVEL[bestCell];
                g.Cls = CELL_CLS[bestCell];
            }
            g.Ok = true;
            return g;
        }

        // ------------------------------------------------------------------------------------------------ frame
        private static double Circ(double d)
        {
            return PyMod(d + GRID_M / 2, GRID_M) - GRID_M / 2;
        }

        // The fix for one analysed frame: the grid names the level and gives V modulo 65 m; the player's icon, or the
        // level -1 origin, or the prior picks the cell. See detect.py solve().
        public static Fix Solve(Analysis a, Dictionary<string, string> mod, Prior prior)
        {
            Geo geo = a.Geo;
            Grid g = a.Grid;
            double sc = geo.Sc;
            int? level = geo.Level;
            string cls = geo.Cls;
            double kz = geo.Kz;
            List<string> note = new List<string>();
            if (g.Ok && g.Level != null)
            {
                string newCls = (g.Level == -1 && g.Cls != null && cls != null) ? g.Cls : cls;
                if (level == null || kz == 0)
                {
                    double? k = (g.Level != -1 || newCls != null) ? KzTheory(g.Level, newCls, geo.H / 1080.0) : null;
                    kz = k ?? 0.0;
                    note.Add(k != null
                             ? "level " + (level == null ? "?" : level.Value.ToString(CultureInfo.InvariantCulture)) + "->" + g.Level + ", kz from the grid"
                             : "level -1 with the map class unknown: no scale");
                }
                else if (g.Level != level || newCls != cls)
                {
                    double? kMod = KzTheory(level, cls, sc);
                    double? kNew = KzTheory(g.Level, newCls, sc);
                    kz = kNew != null ? kNew.Value * (kMod != null ? kz / kMod.Value : 1.0) : 0.0;
                    note.Add("level " + level + "->" + g.Level);
                }
                level = g.Level;
                cls = newCls;
            }
            Fix fix = new Fix();
            fix.Level = g.Ok ? g.Level : null;
            fix.Cell = g.Ok ? g.Cell : 0.0;
            fix.Kz = kz;
            fix.GainLevel = level;
            if (!g.Ok)
            {
                fix.Note = "no grid (" + g.Why + ")";
                return fix;
            }
            if (g.Level == null)
            {
                fix.Note = "grid cell " + Fmt.F(g.Cell, 1) + " px matches no level (zooming?)";
                return fix;
            }
            if (kz == 0)
            {
                note.Add("no scale");
                fix.Note = string.Join("; ", note);
                return fix;
            }
            double px, py;
            bool havePos = TryFloat(Get(mod, "px"), out px);
            if (havePos) havePos = TryFloat(Get(mod, "py"), out py); else py = 0;
            double gvx = (geo.Cx - (geo.X0 + g.Fx)) / kz;
            double gvy = ((geo.Y0 + g.Fy) - geo.Cy) / kz;
            double gErr = g.ErrPx / kz;
            bool havePrior = prior != null;
            Dot bestD = null;
            double bestS = 0, bestVx = 0, bestVy = 0, bestEx = 0, bestEy = 0;
            List<string> offGrid = new List<string>();
            if (havePos)
            {
                foreach (Dot d in a.Dots)
                {
                    if (!(d.ShapeOk || d.Fit == "part") || !HasCone(d, sc)) continue;   // only the own icon has a cone
                    double vx = px - d.Dx / kz;
                    double vy = py + d.Dy / kz;
                    double ex = Circ(vx - gvx), ey = Circ(vy - gvy);
                    if (Math.Abs(ex) > DOT_GRID_MAX || Math.Abs(ey) > DOT_GRID_MAX)
                    {
                        offGrid.Add(d.Band + " off the grid by " + Fmt.Plus(ex, 1) + "," + Fmt.Plus(ey, 1) + " m");
                        continue;
                    }
                    double h = Hypot(ex, ey) / 6.0;
                    double s = d.Prior + 1.0 + 0.6 * Math.Exp(-(h * h));
                    if (d.Fit == "part") s -= 0.5;              // a whole disc with a cone wins over a fitted one
                    if (havePrior)
                    {
                        double pe = Math.Max(3.0, prior.Err);
                        double dist = Hypot(vx - prior.Vx, vy - prior.Vy);
                        double u = dist / (2 * pe + 5);
                        s += Math.Exp(-(u * u));
                        if (d.Band != "yellow" && dist > 3 * pe + 10) continue;   // another colour: only near the prediction
                    }
                    else if (d.Band != "yellow")
                    {
                        continue;
                    }
                    d.Score = s;
                    if (bestD == null || s > bestS)
                    {
                        bestD = d;
                        bestS = s;
                        bestVx = vx - ex;
                        bestVy = vy - ey;
                        bestEx = ex;
                        bestEy = ey;
                    }
                }
            }
            note.AddRange(offGrid);
            if (bestD != null)
            {
                bool part = bestD.Fit == "part";
                fix.How = "dot";
                fix.Vx = bestVx;
                fix.Vy = bestVy;
                fix.Err = Hypot(gErr, part ? PART_ERR : 0.5);
                fix.Dot = bestD;
                note.Add("dot+grid " + Fmt.Plus(bestEx, 1) + "," + Fmt.Plus(bestEy, 1)
                         + (part ? " (partial disc, " + Fmt.F(100 * bestD.Edge, 0) + "% of its rim)" : ""));
            }
            else if (level == -1 && cls != null)
            {
                double ex = Circ(gvx), ey = Circ(gvy);
                if (Math.Max(Math.Abs(ex), Math.Abs(ey)) > DOT_GRID_MAX)
                {
                    note.Add("level -1 but the grid is " + Fmt.Plus(ex, 1) + "," + Fmt.Plus(ey, 1) + " m off the origin");
                }
                else
                {
                    fix.How = "grid";
                    fix.Vx = 0.0;
                    fix.Vy = 0.0;
                    fix.Err = Hypot(gErr, 0.5);
                    note.Add("level -1: the whole map on the origin (grid " + Fmt.Plus(ex, 1) + "," + Fmt.Plus(ey, 1) + " m)");
                }
            }
            else if (havePrior)
            {
                double vx = gvx + GRID_M * Math.Round((prior.Vx - gvx) / GRID_M);
                double vy = gvy + GRID_M * Math.Round((prior.Vy - gvy) / GRID_M);
                double jx = vx - prior.Vx, jy = vy - prior.Vy;
                if (prior.Err > 20.0 || Math.Max(Math.Abs(jx), Math.Abs(jy)) > 26.0)
                {
                    note.Add("grid, prior too vague (err " + Fmt.F(prior.Err, 1) + ", jump " + Fmt.Plus(jx, 1) + "," + Fmt.Plus(jy, 1) + ")");
                }
                else
                {
                    fix.How = "grid";
                    fix.Vx = vx;
                    fix.Vy = vy;
                    fix.Err = Hypot(prior.Err * 0.5 + 0.5 * Math.Max(Math.Abs(jx), Math.Abs(jy)), gErr);
                    note.Add("grid jump " + Fmt.Plus(jx, 1) + "," + Fmt.Plus(jy, 1));
                }
            }
            else
            {
                note.Add("no dot, no prior");
            }
            fix.Note = string.Join("; ", note);
            return fix;
        }
    }
}
