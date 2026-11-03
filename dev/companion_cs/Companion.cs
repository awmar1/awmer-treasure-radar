// Treasure Radar companion: tells the mod where the open tactical map is looking. A port of dev/companion/companion.py
// 1.3 (interface v1.2, dev/docs/COMPANION_INTERFACE.md), for release: one small exe, no Python, no console window.
//
// It reads the mod's line (treasure_radar_mod.txt), captures only the map circle from the game's window while that line
// says the map is open, finds the player's icon or the 65 m grid in it, and writes the view centre V to
// treasure_radar_fix.txt. Pixels only: no game memory, no input, no window hooks, no network.
//
//     TreasureRadarCompanion.exe                     run until the game has gone
//     ... --log                                      one line per frame (to a console, when started from one)
//     ... --dir D                                    use folder D instead of %LOCALAPPDATA%\Temp
//     ... --once                                     one cycle, then exit
//     ... --record                                   keep some captures as PNG for replay (they show desktop content)
//     ... --shot S.png --mod "seq=1 ... end"         detect on a screenshot, print the fix line
//     ... --shot S.png --dir D --once                one file cycle with the screenshot as the screen
//     ... --batch LIST, --seq LIST                   replay "png<TAB>mod line[<TAB>prior]" rows (tests, compare.py)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Imaging;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace TreasureRadar
{
    internal static class Native
    {
        [StructLayout(LayoutKind.Sequential)]
        public struct RECT { public int Left, Top, Right, Bottom; }

        [StructLayout(LayoutKind.Sequential)]
        public struct POINT { public int X, Y; }

        [StructLayout(LayoutKind.Sequential)]
        public struct BITMAPINFOHEADER
        {
            public uint biSize;
            public int biWidth, biHeight;
            public ushort biPlanes, biBitCount;
            public uint biCompression, biSizeImage;
            public int biXPelsPerMeter, biYPelsPerMeter;
            public uint biClrUsed, biClrImportant;
        }

        [DllImport("user32.dll")] public static extern IntPtr GetDC(IntPtr hwnd);
        [DllImport("user32.dll")] public static extern int ReleaseDC(IntPtr hwnd, IntPtr hdc);
        [DllImport("user32.dll")] public static extern int GetSystemMetrics(int i);
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern IntPtr FindWindowW(string cls, string title);
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll", CharSet = CharSet.Unicode)] public static extern int GetWindowTextW(IntPtr hwnd, StringBuilder s, int n);
        [DllImport("user32.dll")] public static extern bool IsWindow(IntPtr hwnd);
        [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr hwnd);
        [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr hwnd, out RECT r);
        [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr hwnd, ref POINT p);
        [DllImport("user32.dll")] public static extern bool SetProcessDpiAwarenessContext(IntPtr ctx);
        [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
        [DllImport("shcore.dll")] public static extern int SetProcessDpiAwareness(int v);
        [DllImport("gdi32.dll")] public static extern IntPtr CreateCompatibleDC(IntPtr hdc);
        [DllImport("gdi32.dll")] public static extern IntPtr CreateCompatibleBitmap(IntPtr hdc, int w, int h);
        [DllImport("gdi32.dll")] public static extern IntPtr SelectObject(IntPtr hdc, IntPtr obj);
        [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr obj);
        [DllImport("gdi32.dll")] public static extern bool DeleteDC(IntPtr hdc);
        [DllImport("gdi32.dll")] public static extern bool BitBlt(IntPtr dst, int x, int y, int w, int h, IntPtr src, int sx, int sy, uint rop);
        [DllImport("gdi32.dll")] public static extern int GetDIBits(IntPtr hdc, IntPtr bm, uint start, uint lines, byte[] bits, ref BITMAPINFOHEADER bi, uint usage);
        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)] public static extern bool MoveFileExW(string a, string b, uint flags);
        [DllImport("kernel32.dll")] public static extern bool AttachConsole(int pid);
        [DllImport("winmm.dll")] public static extern uint timeBeginPeriod(uint ms);
        [DllImport("winmm.dll")] public static extern uint timeEndPeriod(uint ms);
    }

    internal interface IGrabber
    {
        string Mode { get; }
        string Why { get; }
        string Where { get; }
        bool ScreenSize(out int w, out int h);
        byte[] Grab(int x0, int y0, int x1, int y1);    // RGB, valid until the next call
        void Close();
    }

    // The game window's client area through GDI BitBlt of just the box. The window is found by its title (else the
    // foreground window whose title holds HELLDIVERS), the box, in the client's pixels, offset by the client's origin.
    // No game window: the primary screen. Where says which, for the log.
    internal sealed class ScreenGrabber : IGrabber
    {
        private const string GAME_TITLE = "HELLDIVERS™ 2";
        private const string GAME_PART = "HELLDIVERS";
        private const string NO_WINDOW = "the primary screen (no game window found)";
        private IntPtr hdc, mdc, bm, hwnd;
        private int bw, bh, ox, oy;
        private byte[] bgrx, rgb;
        private string mode, why = "", where = NO_WINDOW;

        public string Mode { get { return mode; } }
        public string Why { get { return why; } }
        public string Where { get { return where; } }

        public ScreenGrabber()
        {
            hdc = Native.GetDC(IntPtr.Zero);
            if (hdc != IntPtr.Zero) mdc = Native.CreateCompatibleDC(hdc);
            if (mdc != IntPtr.Zero) mode = "bitblt";
            else why = "BitBlt unavailable";
        }

        private static string Title(IntPtr h)
        {
            StringBuilder s = new StringBuilder(256);
            Native.GetWindowTextW(h, s, 256);
            return s.ToString();
        }

        public static bool GameWindowExists()
        {
            return Native.FindWindowW(null, GAME_TITLE) != IntPtr.Zero;
        }

        private IntPtr Find()
        {
            if (hwnd != IntPtr.Zero && Native.IsWindow(hwnd)) return hwnd;
            IntPtr h = Native.FindWindowW(null, GAME_TITLE);
            if (h == IntPtr.Zero)
            {
                IntPtr fg = Native.GetForegroundWindow();
                if (fg != IntPtr.Zero && Title(fg).ToUpperInvariant().Contains(GAME_PART)) h = fg;
            }
            hwnd = h;
            return h;
        }

        private bool Client(out int x, out int y, out int w, out int h)
        {
            x = y = w = h = 0;
            IntPtr win = Find();
            if (win == IntPtr.Zero || Native.IsIconic(win)) return false;
            Native.RECT r;
            if (!Native.GetClientRect(win, out r))
            {
                hwnd = IntPtr.Zero;
                return false;
            }
            Native.POINT p = new Native.POINT();
            if (!Native.ClientToScreen(win, ref p))
            {
                hwnd = IntPtr.Zero;
                return false;
            }
            w = r.Right - r.Left;
            h = r.Bottom - r.Top;
            x = p.X;
            y = p.Y;
            return w > 0 && h > 0;
        }

        public bool ScreenSize(out int w, out int h)
        {
            w = h = 0;
            if (mode == null) return false;
            int x, y;
            if (Client(out x, out y, out w, out h))
            {
                ox = x;
                oy = y;
                where = "the game window \"" + Title(hwnd) + "\", client " + w + "x" + h + " at (" + x + ", " + y + ")";
                return true;
            }
            ox = oy = 0;
            where = NO_WINDOW;
            w = Native.GetSystemMetrics(0);
            h = Native.GetSystemMetrics(1);
            return true;
        }

        public byte[] Grab(int x0, int y0, int x1, int y1)
        {
            if (mode == null) throw new IOException(why);
            int w = x1 - x0, h = y1 - y0;
            if (w != bw || h != bh)
            {
                if (bm != IntPtr.Zero) Native.DeleteObject(bm);
                bm = Native.CreateCompatibleBitmap(hdc, w, h);
                if (bm == IntPtr.Zero)
                {
                    bw = bh = 0;
                    throw new IOException("CreateCompatibleBitmap failed");
                }
                bgrx = new byte[w * h * 4];
                rgb = new byte[w * h * 3];
                bw = w;
                bh = h;
            }
            IntPtr old = Native.SelectObject(mdc, bm);
            bool ok = Native.BitBlt(mdc, 0, 0, w, h, hdc, x0 + ox, y0 + oy, 0x00CC0020);     // SRCCOPY
            Native.SelectObject(mdc, old);                // GetDIBits wants the bitmap out of the DC
            if (!ok) throw new IOException("BitBlt failed");
            Native.BITMAPINFOHEADER bi = new Native.BITMAPINFOHEADER();
            bi.biSize = (uint)Marshal.SizeOf(typeof(Native.BITMAPINFOHEADER));
            bi.biWidth = w;
            bi.biHeight = -h;                             // top-down rows
            bi.biPlanes = 1;
            bi.biBitCount = 32;
            int rows = Native.GetDIBits(mdc, bm, 0, (uint)h, bgrx, ref bi, 0);
            if (rows != h) throw new IOException("GetDIBits returned " + rows + " rows");
            for (int i = 0, p = 0, q = 0, nn = w * h; i < nn; i++, p += 4, q += 3)
            {
                rgb[q] = bgrx[p + 2];
                rgb[q + 1] = bgrx[p + 1];
                rgb[q + 2] = bgrx[p];
            }
            return rgb;
        }

        public void Close()
        {
            if (mode == null) return;
            if (bm != IntPtr.Zero) Native.DeleteObject(bm);
            Native.DeleteDC(mdc);
            Native.ReleaseDC(IntPtr.Zero, hdc);
            mode = null;
        }
    }

    // A screenshot standing in for the screen (tests, --shot)
    internal sealed class ShotGrabber : IGrabber
    {
        private readonly byte[] img;
        private readonly int w, h;

        public string Mode { get { return "shot"; } }
        public string Why { get { return ""; } }
        public string Where { get { return "a screenshot"; } }

        public ShotGrabber(string path)
        {
            using (Bitmap b = new Bitmap(path))
            {
                w = b.Width;
                h = b.Height;
                img = new byte[w * h * 3];
                BitmapData d = b.LockBits(new Rectangle(0, 0, w, h), ImageLockMode.ReadOnly, PixelFormat.Format24bppRgb);
                byte[] row = new byte[Math.Abs(d.Stride)];
                for (int y = 0; y < h; y++)
                {
                    Marshal.Copy(new IntPtr(d.Scan0.ToInt64() + y * d.Stride), row, 0, row.Length);
                    for (int x = 0; x < w; x++)
                    {
                        img[(y * w + x) * 3] = row[x * 3 + 2];
                        img[(y * w + x) * 3 + 1] = row[x * 3 + 1];
                        img[(y * w + x) * 3 + 2] = row[x * 3];
                    }
                }
                b.UnlockBits(d);
            }
        }

        public bool ScreenSize(out int sw, out int sh)
        {
            sw = w;
            sh = h;
            return true;
        }

        public byte[] Grab(int x0, int y0, int x1, int y1)
        {
            int cw = x1 - x0, ch = y1 - y0;
            byte[] o = new byte[cw * ch * 3];
            for (int y = Math.Max(y0, 0); y < Math.Min(y1, h); y++)
            {
                int sx = Math.Max(x0, 0), ex = Math.Min(x1, w);
                if (ex > sx) Buffer.BlockCopy(img, (y * w + sx) * 3, o, ((y - y0) * cw + sx - x0) * 3, (ex - sx) * 3);
            }
            return o;
        }

        public void Close() { }
    }

    internal sealed class FrameResult
    {
        public string Line, Extra = "";
        public Fix Fix;
        public Analysis A;
    }

    // The last fix advanced by the mouse counts the mod reported since: the prior for the next frame
    internal sealed class Tracker
    {
        private bool haveV;
        public double Vx, Vy, Err;
        public int? VLevel;
        private bool haveGrid;
        private int? gridLevel;
        private double gridCell;
        private double cx, cy, unseen;

        public void Reset()
        {
            haveV = false;
            haveGrid = false;
            cx = cy = unseen = 0;
        }

        public void ClearGrid()
        {
            haveGrid = false;
        }

        public void SetPrior(double vx, double vy, double err)
        {
            haveV = true;
            Vx = vx;
            Vy = vy;
            Err = err;
            VLevel = null;                                // good for whatever level the frame shows
        }

        public void AddCounts(Dictionary<string, string> m, long jump, Dictionary<string, string> prev)
        {
            string a = Detect.Get(m, "cmx"), b = Detect.Get(m, "cmy");
            if (a != null && b != null && prev != null && prev.ContainsKey("cmx") && prev.ContainsKey("cmy"))
            {
                double m1, m2, p1, p2;
                if (!Detect.TryFloat(a, out m1) || !Detect.TryFloat(prev["cmx"], out p1)
                    || !Detect.TryFloat(b, out m2) || !Detect.TryFloat(prev["cmy"], out p2)) return;
                cx += m1 - p1;
                cy += m2 - p2;
                return;
            }
            double mx = 0, my = 0;
            string s = Detect.Get(m, "mx");
            if (s != null && !Detect.TryFloat(s, out mx)) return;
            s = Detect.Get(m, "my");
            if (s != null && !Detect.TryFloat(s, out my)) return;
            long j = Math.Max(1, jump);
            cx += mx * j;
            cy += my * j;
            unseen += (j - 1) * Math.Sqrt(mx * mx + my * my);
        }

        public Prior GetPrior(int? level, string cls, double kz, double rim)
        {
            if (!haveV || level == null) return null;     // no level: no fix this frame anyway
            if (VLevel != null && VLevel != level)
            {
                Reset();                                  // a zoom step recentres the view on the map cursor
                return null;
            }
            double g = Detect.Gain(level);
            double vx = Vx + cx * g, vy = Vy - cy * g;
            double moved = Math.Sqrt(cx * cx + cy * cy) * g;
            double err = Err + 0.03 * moved + 0.5 * unseen * g;
            double? lim = Detect.ViewLimit(cls, kz, rim);
            if (lim != null)
            {
                double l = lim.Value;
                double cvx = Math.Max(-l, Math.Min(l, vx)), cvy = Math.Max(-l, Math.Min(l, vy));
                if ((cvx != vx || cvy != vy) && cls == "big") err += 5.0;   // the big map's radius is less certain
                vx = cvx;
                vy = cvy;
            }
            Prior p = new Prior();
            p.Vx = vx;
            p.Vy = vy;
            p.Err = err;
            return p;
        }

        // A measured level that differs from the mod's goes out only once two frames in a row agree on it
        public Fix Gate(Fix fix, int? modLevel)
        {
            bool had = haveGrid;
            int? pl = gridLevel;
            double pc = gridCell;
            haveGrid = true;
            gridLevel = fix.Level;
            gridCell = fix.Cell;
            if (fix.Level == null || fix.Level == modLevel) return fix;
            if (had && pl == fix.Level && pc != 0 && Math.Abs(fix.Cell / pc - 1) < 0.01) return fix;
            Fix o = fix.Copy();
            o.How = "none";
            o.Level = null;
            o.Note = (fix.Note + "; level " + fix.Level + " (mod " + (modLevel == null ? "None" : modLevel.ToString())
                      + ") seen once: waiting for a second frame").TrimStart(';', ' ');
            return o;
        }

        public void Update(Fix fix, int? level)
        {
            if (fix.How == "none") return;
            haveV = true;
            Vx = fix.Vx;
            Vy = fix.Vy;
            Err = fix.Err;
            VLevel = level;
            cx = cy = unseen = 0;
        }
    }

    // Keeps some captures as PNG, only with --record (they hold whatever the screen shows there): the first frames of
    // every map open and the frames without a fix, FRAMES_MAX in all, frames.txt naming each one's mod and fix lines
    internal sealed class Recorder
    {
        private const string FRAMES_DIR = "treasure_radar_frames", FRAMES_LIST = "frames.txt";
        public const int FRAMES_MAX = 100, FRAMES_FIRST = 3;
        public readonly string Dir;
        public string Why;
        public bool Full;
        private readonly string listPath;
        private int n, openN;
        private readonly Dictionary<string, double> last = new Dictionary<string, double>();

        public Recorder(string folder)
        {
            Dir = Path.Combine(folder, FRAMES_DIR);
            listPath = Path.Combine(Dir, FRAMES_LIST);
            try
            {
                Directory.CreateDirectory(Dir);
                foreach (string f in Directory.GetFiles(Dir))
                {
                    string e = Path.GetExtension(f).ToLowerInvariant();
                    if (e == ".png" || e == ".txt") File.Delete(f);
                }
            }
            catch (Exception e)
            {
                Why = e.Message;
            }
        }

        public void Opened()
        {
            openN = 0;
        }

        private string Rule(Fix fix, string modLevel)
        {
            openN++;
            if (openN <= FRAMES_FIRST) return "open";
            string measured = fix.Level == null ? "?" : fix.Level.Value.ToString(CultureInfo.InvariantCulture);
            if (fix.How != "none" && (measured == "?" || measured == modLevel)) return null;
            bool whole = modLevel == "-1" || (modLevel == "?" && fix.Level == -1);
            string rule = whole ? "L-1" : "L0";
            double gap = whole ? 2.0 : 1.0, now = Companion.Monotonic(), t;
            if (last.TryGetValue(rule, out t) && now - t < gap) return null;
            last[rule] = now;
            return rule;
        }

        public bool Save(byte[] rgb, int side, Dictionary<string, string> mod, string modText, Fix fix, string line)
        {
            string lv = Detect.Get(mod, "level") ?? "?";
            if (Why != null || Rule(fix, lv) == null) return false;
            if (n >= FRAMES_MAX)
            {
                Full = true;
                return false;
            }
            double sq = Detect.Num(mod, "seq", 0);
            DateTime now = DateTime.Now;
            string name = now.ToString("HHmmss.fff", CultureInfo.InvariantCulture) + "_seq" + ((long)sq).ToString("D4", CultureInfo.InvariantCulture)
                          + "_L" + lv.Replace('?', 'x') + "_" + fix.How + ".png";
            try
            {
                using (Bitmap b = new Bitmap(side, side, PixelFormat.Format24bppRgb))
                {
                    BitmapData d = b.LockBits(new Rectangle(0, 0, side, side), ImageLockMode.WriteOnly, PixelFormat.Format24bppRgb);
                    byte[] row = new byte[Math.Abs(d.Stride)];
                    for (int y = 0; y < side; y++)
                    {
                        for (int x = 0; x < side; x++)
                        {
                            row[x * 3] = rgb[(y * side + x) * 3 + 2];
                            row[x * 3 + 1] = rgb[(y * side + x) * 3 + 1];
                            row[x * 3 + 2] = rgb[(y * side + x) * 3];
                        }
                        Marshal.Copy(row, 0, new IntPtr(d.Scan0.ToInt64() + y * d.Stride), row.Length);
                    }
                    b.UnlockBits(d);
                    b.Save(Path.Combine(Dir, name), ImageFormat.Png);
                }
                File.AppendAllText(listPath, name + "\t" + modText + "\t" + line + "\n", new UTF8Encoding(false));
            }
            catch (Exception)
            {
                return false;
            }
            n++;
            return true;
        }
    }

    internal sealed class Stats
    {
        public int Dot, Grid, None, Busy;

        public void Add(string how)
        {
            if (how == "dot") Dot++;
            else if (how == "grid") Grid++;
            else None++;
        }
    }

    internal sealed class OpenTotals
    {
        public long Seq0, Seq1;
        public double T0;
        public int Frames, Saved;
        public Stats S = new Stats();
        public HashSet<string> Levels = new HashSet<string>();
        public string Last;
    }

    internal sealed class Companion
    {
        public const string VERSION = "1.3 (interface v1.2), C# build";
        private const string MOD_FILE = "treasure_radar_mod.txt", FIX_FILE = "treasure_radar_fix.txt";
        private const string LOG_FILE = "treasure_radar_companion.log";
        private const string MUTEX_NAME = "Local\\TreasureRadarCompanion.1";
        private const string GAME_PROCESS = "helldivers2";
        private const double PERIOD = 1.0 / 30;           // at most 30 fixes per second
        private const int IDLE_SLEEP_MS = 100;            // the interface: idle polls every 100 ms
        private const double STALE_S = 1.0;               // no new seq for this long: the game is not writing
        private const int STATIC_N = 20;
        private const string STATIC_NOTE = "the capture is static: the game's window is not being captured (exclusive fullscreen? try borderless)";
        private const long LOG_MAX = 256 * 1024;          // the log stops here, with one line saying so
        private static readonly DateTime EPOCH = new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc);

        public static double Now()
        {
            return (DateTime.UtcNow - EPOCH).TotalSeconds;
        }

        public static double Monotonic()
        {
            return Stopwatch.GetTimestamp() / (double)Stopwatch.Frequency;
        }

        // --------------------------------------------------------------------------------------------- the files
        public static string DefaultDir()
        {
            string d = Environment.GetEnvironmentVariable("LOCALAPPDATA");
            if (string.IsNullOrEmpty(d))
                d = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), "AppData", "Local");
            d = Path.Combine(d, "Temp");
            try
            {
                Directory.CreateDirectory(d);
            }
            catch (Exception)
            {
            }
            return d;
        }

        private static readonly char[] WS = { ' ', '\t', '\r', '\n', '\f', '\v' };

        public static Dictionary<string, string> ParseLine(string text)
        {
            if (string.IsNullOrEmpty(text)) return null;
            int e = text.IndexOfAny(new[] { '\r', '\n' });
            string line = text.Trim().Length == 0 ? "" : (e >= 0 ? text.Substring(0, e) : text);
            string[] toks = line.Split(WS, StringSplitOptions.RemoveEmptyEntries);
            if (toks.Length == 0 || toks[toks.Length - 1] != "end") return null;
            Dictionary<string, string> o = new Dictionary<string, string>();
            for (int i = 0; i < toks.Length - 1; i++)
            {
                int eq = toks[i].IndexOf('=');
                if (eq >= 0) o[toks[i].Substring(0, eq)] = toks[i].Substring(eq + 1);
            }
            return o;
        }

        private static readonly byte[] readBuf = new byte[4096];

        private static bool ReadMod(string path, out Dictionary<string, string> m, out double mtime, out string text)
        {
            m = null;
            mtime = 0;
            text = "";
            try
            {
                DateTime t = File.GetLastWriteTimeUtc(path);
                if (t.Year < 1700) return false;          // the answer for a missing file
                int n;
                using (FileStream f = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                    n = f.Read(readBuf, 0, readBuf.Length);
                string s = Encoding.UTF8.GetString(readBuf, 0, n);
                m = ParseLine(s);
                mtime = (t - EPOCH).TotalSeconds;
                text = s.Trim();
                return true;
            }
            catch (Exception)
            {
                return false;
            }
        }

        private static string NumStr(double v, int nd)
        {
            string s = Fmt.F(v, nd);
            if (s.TrimStart('-').Trim('0', '.').Length == 0) s = s.TrimStart('-');
            return s;
        }

        private static string LevelStr(int? l)
        {
            return l == null ? "?" : l.Value.ToString(CultureInfo.InvariantCulture);
        }

        public static string FormatFix(string seq, double ts, Fix fix)
        {
            StringBuilder b = new StringBuilder();
            b.Append("seq=").Append(seq).Append(" ts=").Append(NumStr(ts, 3)).Append(" how=").Append(fix.How);
            if (fix.How != "none") b.Append(" vx=").Append(NumStr(fix.Vx, 1)).Append(" vy=").Append(NumStr(fix.Vy, 1));
            b.Append(" err=").Append(NumStr(fix.Err, 1)).Append(" level=").Append(LevelStr(fix.Level));
            b.Append(" cell=").Append(NumStr(fix.Cell, 1)).Append(" end");
            return b.ToString();
        }

        // Write the line to path.tmp and replace path with it. False when the target stayed busy (the mod reading it)
        private static bool WriteFix(string path, string line)
        {
            string tmp = path + ".tmp";
            try
            {
                File.WriteAllText(tmp, line + "\n", Encoding.ASCII);
            }
            catch (Exception)
            {
                return false;
            }
            for (int i = 0; i < 4; i++)
            {
                if (Native.MoveFileExW(tmp, path, 1)) return true;    // MOVEFILE_REPLACE_EXISTING, as os.replace
                Thread.Sleep(2 * (i + 1));
            }
            return false;
        }

        // ----------------------------------------------------------------------------------------------- capture
        private static void DpiAware()
        {
            try
            {
                if (Native.SetProcessDpiAwarenessContext(new IntPtr(-4))) return;     // per monitor v2
            }
            catch (Exception)
            {
            }
            try
            {
                if (Native.SetProcessDpiAwareness(2) == 0) return;
            }
            catch (Exception)
            {
            }
            try
            {
                Native.SetProcessDPIAware();
            }
            catch (Exception)
            {
            }
        }

        // The crop_box square, in the mod's pixel frame. When the screen is not the size the mod laid its HUD out for,
        // the box is scaled to it and the crop scaled back. A "screen" the size of the box is a recorded frame: as is.
        private static byte[] Capture(IGrabber gr, Geo geo, Dictionary<string, string> mod, out string scaled)
        {
            scaled = "";
            double w = 0, h = 0;
            string ws = Detect.Get(mod, "w"), hs = Detect.Get(mod, "h");
            if ((ws != null && !Detect.TryFloat(ws, out w)) || (hs != null && !Detect.TryFloat(hs, out h)))
            {
                w = 0;
                h = 0;
            }
            int sw, sh;
            bool have = gr.ScreenSize(out sw, out sh);
            if (have && sw == geo.N && sh == geo.N && (w != geo.N || h != geo.N)) return gr.Grab(0, 0, geo.N, geo.N);
            if (have && w > 0 && h > 0 && (Math.Abs(sw / w - 1) > 0.002 || Math.Abs(sh / h - 1) > 0.002))
            {
                double sx = sw / w, sy = sh / h;
                int x0 = (int)Math.Round(geo.X0 * sx), y0 = (int)Math.Round(geo.Y0 * sy);
                int x1 = (int)Math.Round(geo.X1 * sx), y1 = (int)Math.Round(geo.Y1 * sy);
                scaled = "scaled " + Fmt.F(sx, 3);
                return Pil.ResizeBilinear(gr.Grab(x0, y0, x1, y1), x1 - x0, y1 - y0, geo.N, geo.N);
            }
            return gr.Grab(geo.X0, geo.Y0, geo.X1, geo.Y1);
        }

        public static string IdleReason(Dictionary<string, string> m)
        {
            if (m == null) return "no mod line";
            if (Detect.Get(m, "open") != "1") return "map closed";
            double rim = 0, t;
            string r = Detect.Get(m, "rim"), cx = Detect.Get(m, "cx"), cy = Detect.Get(m, "cy");
            if ((r != null && !Detect.TryFloat(r, out rim)) || (cx != null && !Detect.TryFloat(cx, out t))
                || (cy != null && !Detect.TryFloat(cy, out t))) return "bad numbers";
            if (rim <= 0) return "no map circle (rim 0)";
            return null;
        }

        public static FrameResult Frame(IGrabber gr, Detect det, Dictionary<string, string> mod, Tracker tr, bool gate)
        {
            Geo geo = Geo.FromMod(mod);
            double tCap = Now();
            string scaled;
            byte[] img = Capture(gr, geo, mod, out scaled);
            Analysis a = det.Analyse(img, geo);
            Grid g = a.Grid;
            FrameResult r = new FrameResult();
            r.A = a;
            if (g.Ok && g.Level == -1 && geo.Cls == null)
            {
                tr.Reset();
                tr.ClearGrid();
                Fix idle = new Fix();
                idle.Level = -1;
                idle.Cell = g.Cell;
                idle.Note = "class unknown at level -1";
                r.Fix = idle;
                return r;
            }
            int? level = (g.Ok && g.Level != null) ? g.Level : geo.Level;
            string cls = (g.Ok && g.Level == -1 && g.Cls != null) ? g.Cls : geo.Cls;
            double? kt = Detect.KzTheory(level, cls, geo.Sc);
            double kzp = kt != null && kt.Value != 0 ? kt.Value : geo.Kz;
            Prior prior = tr.GetPrior(level, cls, kzp, geo.Rim);
            Fix fix = Detect.Solve(a, mod, prior);
            if (gate) fix = tr.Gate(fix, geo.Level);
            tr.Update(fix, level);
            List<string> extra = new List<string>();
            if (a.GrayMax < 12) extra.Add("black capture (exclusive fullscreen?)");
            if (scaled.Length > 0) extra.Add(scaled);
            r.Extra = string.Join("; ", extra);
            r.Fix = fix;
            r.Line = FormatFix(Detect.Get(mod, "seq") ?? "0", tCap, fix);
            return r;
        }

        public static string LogText(Dictionary<string, string> mod, FrameResult r)
        {
            Fix fix = r.Fix;
            Grid g = r.A.Grid;
            string v = fix.How != "none" ? "V=(" + Fmt.F(fix.Vx, 1) + "," + Fmt.F(fix.Vy, 1) + ") err=" + Fmt.F(fix.Err, 1) : "V=-";
            string dt = fix.Dot != null ? " dot=(" + Fmt.Plus(fix.Dot.Dx, 1) + "," + Fmt.Plus(fix.Dot.Dy, 1) + ")px" : "";
            int cands = r.A.Dots.Count(x => x.ShapeOk);
            string s = "seq=" + Detect.Get(mod, "seq") + " level " + Detect.Get(mod, "level") + "->" + LevelStr(fix.Level)
                       + " cell=" + Fmt.F(g.Ok ? g.Cell : 0.0, 1) + " how=" + fix.How + " " + v + dt + " discs=" + cands
                       + " " + Fmt.F(r.A.Ms, 1) + "ms " + fix.Note;
            return r.Extra.Length > 0 ? s + "; " + r.Extra : s;
        }

        // ---------------------------------------------------------------------------------------------- the loop
        private readonly string modPath, fixPath;
        private string logPath;
        private long logSize;
        private readonly IGrabber grabber;
        private readonly bool frameLog;
        private readonly Detect det = new Detect();
        private readonly Tracker tracker = new Tracker();
        private readonly Recorder rec;
        private Dictionary<string, string> mod;
        private string modText = "";
        private long? seq;
        private double? seqT;
        private string state;
        private Stats stats = new Stats();
        private double statsT = Monotonic();
        private Fix lastFix;
        private readonly HashSet<string> warned = new HashSet<string>();
        private OpenTotals open;
        private string where;
        private byte[] prevImg;
        private int sameN;
        private bool hiRes;

        private Companion(string folder, IGrabber gr, bool log, bool record)
        {
            modPath = Path.Combine(folder, MOD_FILE);
            fixPath = Path.Combine(folder, FIX_FILE);
            logPath = Path.Combine(folder, LOG_FILE);
            grabber = gr;
            frameLog = log;
            if (record) rec = new Recorder(folder);
            try
            {
                File.WriteAllText(logPath, "");           // new at every start
            }
            catch (Exception e)
            {
                logPath = null;
                Say("note: no companion log (" + e.Message + ")");
            }
        }

        private void Say(string s, bool console = true)
        {
            s = DateTime.Now.ToString("HH:mm:ss ", CultureInfo.InvariantCulture) + s + "\n";
            if (console) Console.Out.Write(s);
            if (logPath == null) return;
            try
            {
                if (logSize + s.Length > LOG_MAX)
                {
                    File.AppendAllText(logPath, "log full (" + LOG_MAX + " bytes): no more lines this run\n");
                    logPath = null;
                    return;
                }
                File.AppendAllText(logPath, s);           // opened per line: nothing held open
                logSize += s.Length;
            }
            catch (Exception)
            {
            }
        }

        private string Poll()
        {
            Dictionary<string, string> m;
            double mtime;
            string text;
            double now = Monotonic();
            if (!ReadMod(modPath, out m, out mtime, out text))
            {
                tracker.Reset();
                return "no mod file in " + Path.GetDirectoryName(modPath);
            }
            if (m != null)
            {
                double sq;
                long? s = Detect.TryFloat(Detect.Get(m, "seq"), out sq) ? (long?)(long)sq : null;
                if (s != null && s != seq)
                {
                    bool first = seq == null;
                    if (!first && s < seq)
                    {
                        tracker.Reset();                  // a new game session
                        first = true;
                    }
                    long jump = first ? 1 : s.Value - seq.Value;
                    seqT = first ? now - Math.Max(0.0, Now() - mtime) : now;   // an old leftover file counts as stale
                    bool wasOpen = mod != null && Detect.Get(mod, "open") == "1";
                    if (Detect.Get(m, "open") != "1" || !wasOpen) tracker.Reset();   // the map (re)opened
                    else if (!first) tracker.AddCounts(m, jump, mod);
                    mod = m;
                    seq = s;
                    modText = text;
                }
            }
            if (mod == null) return "no complete mod line yet";
            if (seqT == null || now - seqT.Value > STALE_S)
            {
                tracker.Reset();
                return "mod line stale (game closed, paused or alt-tabbed?)";
            }
            string why = IdleReason(mod);
            if (why != null) tracker.Reset();
            return why;
        }

        private bool Cycle()
        {
            string why = Poll();
            if (why != null)
            {
                SetState("idle: " + why);
                sameN = 0;                                // the static count runs only while open=1
                return false;
            }
            FrameResult r;
            try
            {
                r = Frame(grabber, det, mod, tracker, true);
            }
            catch (Exception e)
            {
                SetState("frame failed: " + e.GetType().Name + ": " + e.Message);
                return false;
            }
            if (grabber.Where != where)
            {
                where = grabber.Where;
                Say("capture: " + where);
            }
            Static(r.A);
            Fix fix = r.Fix;
            if (r.Line == null)
            {
                SetState("idle: " + fix.Note);
                return false;
            }
            SetState("active: map open, mod level " + Detect.Get(mod, "level") + ", " + Detect.Get(mod, "class") + " map");
            bool ok = WriteFix(fixPath, r.Line);
            stats.Add(fix.How);
            if (!ok) stats.Busy++;
            lastFix = fix;
            if (r.Extra.Length > 0 && warned.Add(r.Extra)) Say("note: " + r.Extra);
            OpenTotals o = open;
            if (o != null)
            {
                o.Frames++;
                o.S.Add(fix.How);
                o.Levels.Add(LevelStr(fix.Level));
                o.Seq1 = seq ?? 0;
                if (fix.How != "none")
                    o.Last = "V=(" + Fmt.F(fix.Vx, 1) + ", " + Fmt.F(fix.Vy, 1) + ") err " + Fmt.F(fix.Err, 1) + " m (" + fix.How + ", level " + LevelStr(fix.Level) + ")";
            }
            if (rec != null)
            {
                if (rec.Save(r.A.Rgb, r.A.Geo.N, mod, modText, fix, r.Line))
                {
                    if (o != null) o.Saved++;
                }
                else if (rec.Full && warned.Add("frames full"))
                {
                    Say("frames: " + Recorder.FRAMES_MAX + " recorded this session, the cap; no more until the next start");
                }
            }
            if (frameLog)
            {
                Console.Out.Write(LogText(mod, r) + (ok ? "" : " [fix file busy, not written]") + "\n");
                Console.Out.Flush();
            }
            return true;
        }

        private void Static(Analysis a)
        {
            byte[] b = a.Rgb;
            int len = a.Geo.N * a.Geo.N * 3;
            bool same = prevImg != null && prevImg.Length == len && sameN > 0;
            if (same)
            {
                for (int i = 0; i < len; i++)
                {
                    if (b[i] != prevImg[i])
                    {
                        same = false;
                        break;
                    }
                }
            }
            if (same)
            {
                sameN++;
            }
            else
            {
                sameN = 1;
                if (prevImg == null || prevImg.Length != len) prevImg = new byte[len];
                Buffer.BlockCopy(b, 0, prevImg, 0, len);
            }
            if (sameN >= STATIC_N && warned.Add("static")) Say(STATIC_NOTE);
        }

        private void SetState(string s)
        {
            if (s == state) return;
            bool was = state != null && state.StartsWith("active", StringComparison.Ordinal);
            if (was) Report(true);
            if (was && !s.StartsWith("active", StringComparison.Ordinal)) OpenSummary();
            state = s;
            Say(s);
            if (s.StartsWith("active", StringComparison.Ordinal))
            {
                stats = new Stats();
                statsT = Monotonic();
                if (open == null)
                {
                    open = new OpenTotals();
                    open.Seq0 = open.Seq1 = seq ?? 0;
                    open.T0 = Monotonic();
                    if (rec != null) rec.Opened();
                }
            }
        }

        private void OpenSummary()
        {
            OpenTotals o = open;
            open = null;
            if (o == null) return;
            List<string> lv = o.Levels.ToList();
            lv.Sort((a, b) => a == "?" ? (b == "?" ? 0 : 1) : b == "?" ? -1 : string.CompareOrdinal(a, b));
            Say("map open done: seq " + o.Seq0 + "-" + o.Seq1 + ", " + o.Frames + " frames in " + Fmt.F(Monotonic() - o.T0, 1)
                + " s: dot " + o.S.Dot + ", grid " + o.S.Grid + ", none " + o.S.None + "; levels seen "
                + (lv.Count > 0 ? string.Join(", ", lv) : "-") + "; last " + (o.Last ?? "none") + "; " + o.Saved + " frames recorded");
        }

        private void Finish()
        {
            if (state != null && state.StartsWith("active", StringComparison.Ordinal))
            {
                Report(true);
                OpenSummary();
            }
        }

        private void Report(bool force)
        {
            double now = Monotonic(), dt = now - statsT;
            int n = stats.Dot + stats.Grid + stats.None;
            if (!force && dt < 5.0) return;
            if (n > 0)
            {
                string last = "";
                if (lastFix != null)
                {
                    last = ", last: how=" + lastFix.How + " level=" + LevelStr(lastFix.Level);
                    if (lastFix.How != "none") last += " V=(" + Fmt.F(lastFix.Vx, 1) + ", " + Fmt.F(lastFix.Vy, 1) + ") err " + Fmt.F(lastFix.Err, 1) + " m";
                }
                Say(n + " frames in " + Fmt.F(dt, 1) + " s (" + Fmt.F(dt > 0 ? n / dt : 0, 1) + "/s): dot " + stats.Dot + ", grid " + stats.Grid
                    + ", none " + stats.None + (stats.Busy > 0 ? ", busy " + stats.Busy : "") + last);
            }
            stats = new Stats();
            statsT = now;
        }

        // Why the loop should end, or null. Looked at once a second. The game counts as there while its window or its
        // process exists, or the mod is still writing its line (so a title or a process name that differs on some
        // machine cannot stop the companion mid-game).
        private const double PROCESS_S = 10.0;
        private double watchStart, watchSeen = -1, watchNext, processNext;
        private bool processThere;

        private string Watchdog(double graceStart, double graceGone)
        {
            double now = Monotonic();
            if (now < watchNext) return null;
            watchNext = now + 1.0;
            if (GameThere(now))
            {
                watchSeen = now;
                return null;
            }
            if (watchSeen < 0)
                return now - watchStart >= graceStart ? "the game did not appear within " + Fmt.F(graceStart, 0) + " s" : null;
            return now - watchSeen >= graceGone ? "the game has been gone for " + Fmt.F(graceGone, 0) + " s" : null;
        }

        private bool GameThere(double now)
        {
            if (seqT != null && now - seqT.Value < 5.0) return true;
            if (ScreenGrabber.GameWindowExists()) return true;
            if (now >= processNext)                       // listing the processes costs far more than the rest of idle
            {
                processNext = now + PROCESS_S;
                Process[] ps = Process.GetProcessesByName(GAME_PROCESS);
                processThere = ps.Length > 0;
                foreach (Process p in ps) p.Dispose();
            }
            return processThere;
        }

        private void HiRes(bool on)
        {
            if (on == hiRes) return;
            try
            {
                // 1 ms sleeps while the map is open, or Sleep(33) rounds up to 47 ms; none while idle
                if (on) Native.timeBeginPeriod(1);
                else Native.timeEndPeriod(1);
            }
            catch (Exception)
            {
            }
            hiRes = on;
        }

        private void Run(bool once, bool watch, double graceStart, double graceGone)
        {
            watchStart = Monotonic();
            double nxt = Monotonic();
            while (true)
            {
                bool active = Cycle();
                if (once) return;
                if (active)
                {
                    HiRes(true);
                    if (!frameLog) Report(false);
                    nxt += PERIOD;
                    double now = Monotonic();
                    if (nxt < now) nxt = now;             // slower than 30 Hz: no catching up
                    int ms = (int)Math.Ceiling((nxt - now) * 1000);
                    if (ms > 0) Thread.Sleep(ms);
                }
                else
                {
                    HiRes(false);
                    Thread.Sleep(IDLE_SLEEP_MS);
                    nxt = Monotonic();
                }
                if (watch)
                {
                    string end = Watchdog(graceStart, graceGone);
                    if (end != null)
                    {
                        Say("exiting: " + end);
                        return;
                    }
                }
            }
        }

        // --------------------------------------------------------------------------------------------------- CLI
        private static string Usage()
        {
            return "Treasure Radar companion " + VERSION + "\n"
                   + "  (no arguments)        run until the game has gone\n"
                   + "  --dir D               folder of the two files and the log (default %LOCALAPPDATA%\\Temp)\n"
                   + "  --log                 one line per frame\n"
                   + "  --once                one cycle, then exit\n"
                   + "  --record              keep some captures as PNG (they show what is on screen there)\n"
                   + "  --grace-start S       seconds to wait for the game to appear (default 600)\n"
                   + "  --grace-gone S        seconds after the game has gone before exiting (default 30)\n"
                   + "  --shot S.png          use this screenshot instead of capturing the screen\n"
                   + "  --mod \"seq=1 ... end\" with --shot: this mod line instead of the file; prints the fix line\n"
                   + "  --prior vx,vy[,err]   with --mod: a prior V in world metres\n"
                   + "  --bench N             with --mod: repeat the detection N times, print min and median ms\n"
                   + "  --batch LIST          png<TAB>mod line[<TAB>prior] rows, each on its own, in one process\n"
                   + "  --seq LIST            the same rows through one tracker with the level gate\n";
        }

        private static int Replay(string shot, string modLine, string priorStr, bool log, int bench)
        {
            Dictionary<string, string> m = ParseLine(modLine);
            if (m == null)
            {
                Console.Out.WriteLine("the --mod line has no trailing \"end\": ignored, as the interface says");
                return 1;
            }
            string why = IdleReason(m);
            if (why != null)
            {
                Console.Out.WriteLine("idle: " + why);
                return 0;
            }
            IGrabber gr = new ShotGrabber(shot);
            Tracker tr = new Tracker();
            if (!string.IsNullOrEmpty(priorStr)) SetPrior(tr, priorStr);
            Detect det = new Detect();
            FrameResult r = Frame(gr, det, m, tr, false);
            if (r.Line == null)
            {
                Console.Out.WriteLine("idle: " + r.Fix.Note);
                return 0;
            }
            if (log) Console.Out.WriteLine(LogText(m, r));
            Console.Out.WriteLine(r.Line);
            if (bench > 0)
            {
                string sc;
                byte[] img = Capture(gr, r.A.Geo, m, out sc);
                double[] t = new double[bench];
                for (int i = 0; i < bench; i++) t[i] = det.Analyse(img, r.A.Geo).Ms;
                Array.Sort(t);
                Console.Out.WriteLine("bench min=" + Fmt.F(t[0], 2) + " median=" + Fmt.F(t[bench / 2], 2));
            }
            return 0;
        }

        // Tests: rows of "png<TAB>mod line[<TAB>prior]" in one process. --batch: each row on its own, as --mod. --seq:
        // through one tracker with the level gate, the counts folded in as poll() does, the path --mod never takes.
        // Prints the log line and the fix line of each row
        private static int ReplayRows(string list, bool sequence)
        {
            Tracker tr = new Tracker();
            Detect det = new Detect();
            Dictionary<string, string> prev = null;
            long prevSeq = 0;
            foreach (string row in File.ReadAllLines(list))
            {
                string[] c = row.Split('\t');
                if (c.Length < 2) continue;
                Dictionary<string, string> m = ParseLine(c[1]);
                if (sequence)
                {
                    long sq = (long)Detect.Num(m, "seq", 0);
                    bool wasOpen = prev != null && Detect.Get(prev, "open") == "1";
                    if (prev == null || sq < prevSeq || Detect.Get(m, "open") != "1" || !wasOpen) tr.Reset();
                    else tr.AddCounts(m, sq - prevSeq, prev);
                    prev = m;
                    prevSeq = sq;
                }
                else
                {
                    tr.Reset();
                    if (c.Length > 2 && c[2].Length > 0) SetPrior(tr, c[2]);
                }
                string why = IdleReason(m);
                if (why != null)
                {
                    tr.Reset();
                    Console.Out.WriteLine("idle: " + why);
                    continue;
                }
                FrameResult r = Frame(new ShotGrabber(c[0]), det, m, tr, sequence);
                if (r.Line == null) Console.Out.WriteLine("idle: " + r.Fix.Note);
                else Console.Out.WriteLine(LogText(m, r) + "\n" + r.Line);
            }
            return 0;
        }

        private static void SetPrior(Tracker tr, string s)
        {
            string[] p = s.Replace(" ", "").Split(',');
            tr.SetPrior(double.Parse(p[0], CultureInfo.InvariantCulture), double.Parse(p[1], CultureInfo.InvariantCulture),
                        p.Length > 2 ? double.Parse(p[2], CultureInfo.InvariantCulture) : 5.0);
        }

        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                return Main2(args);
            }
            catch (Exception e)
            {
                Console.Error.WriteLine(e.GetType().Name + ": " + e.Message);
                return 3;
            }
        }

        private static int Main2(string[] args)
        {
            string dir = null, shot = null, modLine = null, priorStr = null, seqList = null, batchList = null;
            bool log = false, once = false, record = false;
            int bench = 0;
            double graceStart = 600, graceGone = 30;
            if (args.Length > 0) Native.AttachConsole(-1);    // a winexe has no console of its own
            for (int i = 0; i < args.Length; i++)
            {
                string a = args[i];
                Func<string> val = () =>
                {
                    if (++i >= args.Length) throw new ArgumentException(a + " needs a value");
                    return args[i];
                };
                if (a == "--dir") dir = val();
                else if (a == "--shot") shot = val();
                else if (a == "--mod") modLine = val();
                else if (a == "--prior") priorStr = val();
                else if (a == "--seq") seqList = val();
                else if (a == "--batch") batchList = val();
                else if (a == "--bench") bench = int.Parse(val(), CultureInfo.InvariantCulture);
                else if (a == "--grace-start") graceStart = double.Parse(val(), CultureInfo.InvariantCulture);
                else if (a == "--grace-gone") graceGone = double.Parse(val(), CultureInfo.InvariantCulture);
                else if (a == "--log") log = true;
                else if (a == "--once") once = true;
                else if (a == "--record") record = true;
                else
                {
                    Console.Out.Write(Usage());
                    return a == "--help" || a == "-h" ? 0 : 2;
                }
            }
            if (seqList != null) return ReplayRows(seqList, true);
            if (batchList != null) return ReplayRows(batchList, false);
            if (modLine != null)
            {
                if (shot == null) throw new ArgumentException("--mod needs --shot");
                return Replay(shot, modLine, priorStr, log, bench);
            }
            // only one running companion: a second start leaves the first one's log alone and goes
            bool created = true;
            using (Mutex single = shot == null ? new Mutex(true, MUTEX_NAME, out created) : null)
            {
                if (!created) return 0;
                DpiAware();                               // per-monitor v2, before any GDI or window call
                string folder = dir ?? DefaultDir();
                IGrabber gr = shot != null ? (IGrabber)new ShotGrabber(shot) : new ScreenGrabber();
                Companion c = new Companion(folder, gr, log, record);
                bool con = !once;
                c.Say("Treasure Radar companion " + VERSION, con);
                c.Say("folder: " + folder, con);
                c.Say("log: " + (c.logPath ?? "none"), con);
                c.Say(record ? (c.rec.Why != null ? "frames: not recorded (" + c.rec.Why + ")" : "frames: recorded in " + c.rec.Dir) : "frames: not recorded", con);
                int sw, sh;
                string size = gr.ScreenSize(out sw, out sh) ? " " + sw + "x" + sh : "";
                c.Say("capture: " + gr.Mode + size + (gr.Why.Length > 0 ? " (" + gr.Why + ")" : "") + ", " + gr.Where, con);
                c.where = gr.Where;
                c.Say("waiting for the mod", con);
                try
                {
                    c.Run(once, shot == null, graceStart, graceGone);
                }
                catch (Exception e)
                {
                    c.Say("stopped: " + e.GetType().Name + ": " + e.Message);
                }
                finally
                {
                    c.Finish();
                    c.HiRes(false);
                    gr.Close();
                    if (single != null) single.ReleaseMutex();
                }
            }
            return 0;
        }
    }
}
