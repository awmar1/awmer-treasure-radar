// Test tool, not shipped: runs the Pil class on raw inputs, for parity_probe.py to compare with PIL itself.
//     parity_probe.exe hsv|l|blur|ellipse|resize|fmt ...
using System;
using System.Globalization;
using System.IO;
using System.Text;

namespace TreasureRadar
{
    internal static class ParityProbe
    {
        private static double D(string s)
        {
            return double.Parse(s, CultureInfo.InvariantCulture);
        }

        private static int Main(string[] a)
        {
            switch (a[0])
            {
                case "hsv":     // in.rgb out.hsv (three planes)
                {
                    byte[] rgb = File.ReadAllBytes(a[1]);
                    int c = rgb.Length / 3;
                    byte[] h = new byte[c], s = new byte[c], v = new byte[c], o = new byte[c * 3];
                    Pil.RgbToHsv(rgb, c, h, s, v);
                    for (int i = 0; i < c; i++)
                    {
                        o[i * 3] = h[i];
                        o[i * 3 + 1] = s[i];
                        o[i * 3 + 2] = v[i];
                    }
                    File.WriteAllBytes(a[2], o);
                    return 0;
                }
                case "l":       // in.rgb out.l
                {
                    byte[] rgb = File.ReadAllBytes(a[1]);
                    byte[] o = new byte[rgb.Length / 3];
                    Pil.RgbToL(rgb, o.Length, o);
                    File.WriteAllBytes(a[2], o);
                    return 0;
                }
                case "blur":    // in.l n radius out.l
                {
                    byte[] im = File.ReadAllBytes(a[1]);
                    int n = int.Parse(a[2]);
                    byte[] o = new byte[n * n], t = new byte[n * n];
                    Pil.BoxBlur(im, o, t, n, int.Parse(a[3]));
                    File.WriteAllBytes(a[4], o);
                    return 0;
                }
                case "ellipse": // n x0 y0 x1 y1 out.l
                    File.WriteAllBytes(a[6], Pil.FilledEllipse(int.Parse(a[1]), D(a[2]), D(a[3]), D(a[4]), D(a[5])));
                    return 0;
                case "resize":  // in.rgb w h outW outH out.rgb
                    File.WriteAllBytes(a[6], Pil.ResizeBilinear(File.ReadAllBytes(a[1]), int.Parse(a[2]), int.Parse(a[3]), int.Parse(a[4]), int.Parse(a[5])));
                    return 0;
                case "fmt":     // in.txt (one double per line, as R) out.txt (with 0, 1 and 3 decimals)
                {
                    StringBuilder b = new StringBuilder();
                    foreach (string row in File.ReadAllLines(a[1]))
                    {
                        double v = D(row);
                        b.Append(Fmt.F(v, 0)).Append(' ').Append(Fmt.F(v, 1)).Append(' ').Append(Fmt.F(v, 3)).Append('\n');
                    }
                    File.WriteAllText(a[2], b.ToString(), Encoding.ASCII);
                    return 0;
                }
            }
            return 2;
        }
    }
}
