"""Turns one frame's recorded draw calls into a PNG, the way the game would show them.

Order: a muted terrain background seen through the scenario's camera (sky, ground, a faint grid, the scenario's units
as gray stakes), then the world's line objects, then every main-world GUI draw, then (map open) a stand-in for the
game's map at the bottom right, then the other world's draws over it. Within a world, draws are sorted by layer, then
by call order. GUI coordinates are pixels from the bottom left (converted to the image's top-left origin). Bitmaps are
the archives' own textures, scaled to the drawn size and tinted (multiplied) by the draw color. A texture id no archive
has draws as a magenta box with a cross.
"""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

MAGENTA = (255, 0, 255, 255)


# ------------------------------------------------------------------ the camera (the same math as engine.lua)
class Cam:
    def __init__(self, x, y, z, yaw_deg, pitch_deg, fov_deg, w, h):
        self.x, self.y, self.z = x, y, z
        yaw, pitch = math.radians(yaw_deg), math.radians(pitch_deg)
        sy, cy, sp, cp = math.sin(yaw), math.cos(yaw), math.sin(pitch), math.cos(pitch)
        self.f = (sy * cp, cy * cp, sp)
        self.r = (cy, -sy, 0.0)
        self.u = (-sy * sp, -cy * sp, cp)
        self.k = 1.0 / math.tan(math.radians(fov_deg) / 2)
        self.w, self.h = w, h
        self.yaw_deg, self.pitch_deg, self.fov_deg = yaw_deg, pitch_deg, fov_deg

    def view(self, x, y, z):
        dx, dy, dz = x - self.x, y - self.y, z - self.z
        f, r, u = self.f, self.r, self.u
        return (dx * r[0] + dy * r[1] + dz * r[2], dx * u[0] + dy * u[1] + dz * u[2], dx * f[0] + dy * f[1] + dz * f[2])

    def to_image(self, xc, yc, zc):
        """view coordinates -> image pixels (top-left origin)"""
        s = self.k * self.h / 2 / zc
        return self.w / 2 + xc * s, self.h / 2 - yc * s

    def project(self, x, y, z):
        xc, yc, zc = self.view(x, y, z)
        if zc <= 0.05:
            return None
        return self.to_image(xc, yc, zc) + (zc,)

    def segment(self, a, b, near=0.3):
        """a 3D segment clipped to the near plane, in image pixels, or None"""
        va, vb = self.view(*a), self.view(*b)
        if va[2] < near and vb[2] < near:
            return None
        if va[2] < near or vb[2] < near:
            t = (near - va[2]) / (vb[2] - va[2])
            p = tuple(va[i] + (vb[i] - va[i]) * t for i in range(3))
            if va[2] < near:
                va = p
            else:
                vb = p
        return self.to_image(*va) + self.to_image(*vb)


def map_center(w, h, hud):
    """Where the game's map opens (pixels, bottom-left origin): the game's HUD anchor, as measured for Treasure Radar
    (70/44 px corner at 1440 p, 254.4/301.3 px to the center at HUD Scale 0.85, moving 34/63 px per unit of scale)."""
    area = min(w, h * 16 / 9)
    off = hud.get('hud_offset')
    if not isinstance(off, (int, float)) or off < 0 or off > 1:
        off = 1
    s = hud.get('hud_scale')
    if not isinstance(s, (int, float)) or s < 0.3 or s > 3:
        s = 0.85
    ds = s - 0.85
    right = w - off * (w - area) / 2 - 70 / 1440 * h
    return right - (254.4 / 1440 + ds * 34 / 1440) * h, 44 / 1440 * h + (301.3 / 1440 + ds * 63 / 1440) * h


MAP_RIM = 0.2056      # the game's map radius, in screen heights


class Renderer:
    def __init__(self, textures, w, h, seed=7):
        """textures: {hex: (w, h, rgba bytes)} or a callable hex -> that / None"""
        self.textures = textures
        self.tex_cache = {}
        self.tint_cache = {}
        self.unknown = {}          # hex -> first frame drawn
        self.seed = seed
        self.terrain = None
        self.size = None
        self._font = None
        self.set_size(w, h)

    def set_size(self, w, h):
        if self.size == (w, h):
            return
        self.size = (w, h)
        self.terrain = self._make_terrain(w, h)

    # ---------------------------------------------------------------- textures
    def texture(self, hx):
        if hx in self.tex_cache:
            return self.tex_cache[hx]
        src = self.textures(hx) if callable(self.textures) else self.textures.get(hx)
        im = None
        if src:
            w, h, px = src
            im = Image.frombytes('RGBA', (w, h), px)
        self.tex_cache[hx] = im
        return im

    def tinted(self, hx, w, h, color):
        key = (hx, w, h, color)
        im = self.tint_cache.get(key)
        if im is not None:
            return im
        base = self.texture(hx)
        if base is None:
            return None
        im = base.resize((w, h), Image.BILINEAR if (w < base.width or h < base.height) else Image.BICUBIC,
                         reducing_gap=2.0 if (w < base.width / 2) else None)
        if color != (255, 255, 255, 255):
            r, g, b, a = color[1], color[2], color[3], color[0]
            im = ImageChops.multiply(im, Image.new('RGBA', (w, h), (r, g, b, a)))
        if len(self.tint_cache) > 6000:
            self.tint_cache.clear()
        self.tint_cache[key] = im
        return im

    # ---------------------------------------------------------------- the background
    def _make_terrain(self, w, h):
        rnd = random.Random(self.seed)
        tw, th = w * 2, h
        acc = Image.new('L', (tw, th), 128)
        # a few octaves of blurred noise: big soft patches down to grit
        for scale, weight in ((64, 0.5), (16, 0.3), (4, 0.15), (1, 0.08)):
            n = Image.effect_noise((max(2, tw // scale), max(2, th // scale)), 40 + rnd.random() * 10)
            n = n.resize((tw, th), Image.BICUBIC)
            acc = Image.blend(acc, n, weight)
        acc = acc.filter(ImageFilter.GaussianBlur(1))
        acc = ImageChops.multiply(acc, Image.new('L', (tw, th), 255)).point(lambda v: max(0, min(255, (v - 128) * 2 + 128)))
        dark = (34, 33, 28)
        light = (78, 74, 60)
        return Image.merge('RGB', [acc.point(lambda v, a=dark[i], b=light[i]: int(a + (b - a) * v / 255)) for i in range(3)])

    def background(self, cam, units, map_open, hud, grid=True):
        w, h = self.size
        img = Image.new('RGBA', (w, h), (0, 0, 0, 255))
        # the horizon: where a level view direction lands
        hz = h / 2 + math.tan(math.radians(cam.pitch_deg)) * cam.k * h / 2
        hzi = int(max(-1, min(h, hz)))
        if hzi > 0:
            sky = Image.new('RGB', (1, 256))
            top, bottom = (22, 26, 33), (58, 60, 62)
            sky.putdata([tuple(int(top[i] + (bottom[i] - top[i]) * (j / 255) ** 1.5) for i in range(3)) for j in range(256)])
            img.paste(sky.resize((w, hzi), Image.BILINEAR), (0, 0))
        if hzi < h:
            gw = self.terrain.width
            shift = int((cam.yaw_deg / 360.0) * gw * 2) % gw
            strip = self.terrain.crop((0, 0, gw, h - max(0, hzi)))
            strip = ImageChops.offset(strip, -shift, 0).crop((0, 0, w, h - max(0, hzi)))
            img.paste(strip, (0, max(0, hzi)))
            # haze near the horizon
            haze = Image.new('L', (1, 64))
            haze.putdata([int(150 * (1 - j / 63) ** 2) for j in range(64)])
            band = min(h - max(0, hzi), int(h * 0.12))
            if band > 0:
                img.paste((60, 62, 63, 255), (0, max(0, hzi), w, max(0, hzi) + band), haze.resize((w, band)))
        d = ImageDraw.Draw(img, 'RGBA')
        if grid:
            step, reach = 10, 160
            gx0, gy0 = int(cam.x // step) * step, int(cam.y // step) * step
            for i in range(-reach // step, reach // step + 1):
                for a, b in ((((gx0 + i * step), gy0 - reach, 0.0), ((gx0 + i * step), gy0 + reach, 0.0)),
                             ((gx0 - reach, gy0 + i * step, 0.0), (gx0 + reach, gy0 + i * step, 0.0))):
                    s = cam.segment(a, b)
                    if s:
                        d.line(s, fill=(120, 120, 100, 34), width=1)
        # the scenario's units: gray stakes on the ground (so the markers can be compared with where things are)
        for (x, y, z) in units:
            base, topp = cam.project(x, y, z), cam.project(x, y, z + 0.8)
            if not base or not topp:
                continue
            half = max(1.0, 0.18 * cam.k * h / 2 / base[2])
            y0, y1 = sorted((topp[1], base[1]))      # seen from high above, a stake's top can be the lower end
            d.rectangle((base[0] - half, y0, base[0] + half, y1), fill=(105, 105, 100, 200),
                        outline=(25, 25, 25, 220))
        return img

    def map_standin(self, img, hud):
        w, h = self.size
        cx, cy = map_center(w, h, hud)
        r = MAP_RIM * h
        cy_img = h - cy
        layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer, 'RGBA')
        d.ellipse((cx - r, cy_img - r, cx + r, cy_img + r), fill=(28, 44, 40, 255))
        for i in range(-6, 7):
            dx = i * r / 6
            half = math.sqrt(max(0.0, r * r - dx * dx))
            d.line((cx + dx, cy_img - half, cx + dx, cy_img + half), fill=(70, 110, 95, 90))
            d.line((cx - half, cy_img + dx, cx + half, cy_img + dx), fill=(70, 110, 95, 90))
        d.ellipse((cx - r, cy_img - r, cx + r, cy_img + r), outline=(190, 200, 170, 230), width=max(2, int(h / 500)))
        label = 'MAP (stand-in)'
        d.text((cx - d.textlength(label, font=self.font()) / 2, cy_img - r + 12), label, fill=(190, 200, 170, 200),
               font=self.font())
        img.alpha_composite(layer)

    def font(self):
        if self._font is None:
            try:
                self._font = ImageFont.load_default(size=max(12, self.size[1] // 90))
            except TypeError:
                self._font = ImageFont.load_default()
        return self._font

    # ---------------------------------------------------------------- draws
    @staticmethod
    def blit(img, src, x, y):
        W, H = img.size
        w, h = src.size
        if x >= W or y >= H or x + w <= 0 or y + h <= 0:
            return
        cx0, cy0 = max(0, -x), max(0, -y)
        cx1, cy1 = min(w, W - x), min(h, H - y)
        if cx0 or cy0 or cx1 != w or cy1 != h:
            src = src.crop((cx0, cy0, cx1, cy1))
        img.alpha_composite(src, (x + cx0, y + cy0))

    def draw_list(self, img, recs, frame):
        """recs: [(kind, layer, x, y, w, h, (a, r, g, b), tex hex or None, order)] of one world."""
        H = self.size[1]
        recs = sorted(recs, key=lambda r: (r[1], r[8]))
        for rec in recs:
            kind, layer, x, y, w, h, col, tex = rec[:8]
            x0, x1 = int(round(x)), int(round(x + w))
            y0, y1 = int(round(H - (y + h))), int(round(H - y))
            pw, ph = x1 - x0, y1 - y0
            if pw <= 0 or ph <= 0 or col[0] <= 0:
                continue
            if kind == 'rect':
                self.blit(img, Image.new('RGBA', (pw, ph), (col[1], col[2], col[3], col[0])), x0, y0)
                continue
            hx = tex if tex and len(tex) == 16 else None
            src = self.tinted(hx, pw, ph, col) if hx else None
            if src is None:
                self.unknown.setdefault(tex or '?', frame)
                box = Image.new('RGBA', (pw, ph), (255, 0, 255, 110))
                bd = ImageDraw.Draw(box)
                bd.rectangle((0, 0, pw - 1, ph - 1), outline=MAGENTA, width=max(1, min(pw, ph) // 12))
                bd.line((0, 0, pw - 1, ph - 1), fill=MAGENTA)
                bd.line((0, ph - 1, pw - 1, 0), fill=MAGENTA)
                self.blit(img, box, x0, y0)
            else:
                self.blit(img, src, x0, y0)

    def draw_lines(self, img, cam, lines):
        if not lines:
            return
        layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(layer, 'RGBA')
        for a, r, g, b, x1, y1, z1, x2, y2, z2 in lines:
            s = cam.segment((x1, y1, z1), (x2, y2, z2))
            if s:
                d.line(s, fill=(int(r), int(g), int(b), int(a)), width=max(1, self.size[1] // 720))
        img.alpha_composite(layer)

    def frame(self, frame_no, cam, recs, lines, units, map_open, hud):
        """recs: parsed draw records (see runner.parse_dump); returns an RGB image."""
        img = self.background(cam, units, map_open, hud)
        self.draw_lines(img, cam, lines)
        main = [r[1] for r in recs if r[0] == 0]
        tops = [r[1] for r in recs if r[0] != 0]
        self.draw_list(img, main, frame_no)
        if map_open:
            self.map_standin(img, hud)
        self.draw_list(img, tops, frame_no)
        return img.convert('RGB')


def contact_sheet(items, out_path, thumb_w=640, cols=3, title=None):
    """items: [(path to a frame PNG, label)]"""
    if not items:
        return None
    ims = []
    for p, label in items:
        im = Image.open(p).convert('RGB')
        tw = thumb_w
        th = int(im.height * tw / im.width)
        ims.append((im.resize((tw, th), Image.LANCZOS), label))
    th = ims[0][0].height
    pad, lab = 8, 22
    top = 30 if title else 0
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (thumb_w + pad) + pad, top + rows * (th + lab + pad) + pad), (16, 16, 18))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.load_default(size=15)
        tfont = ImageFont.load_default(size=18)
    except TypeError:
        font = tfont = ImageFont.load_default()
    if title:
        d.text((pad, 6), title, fill=(230, 230, 230), font=tfont)
    for i, (im, label) in enumerate(ims):
        r, c = divmod(i, cols)
        x, y = pad + c * (thumb_w + pad), top + pad + r * (th + lab + pad)
        d.text((x, y + 2), label, fill=(220, 220, 200), font=font)
        sheet.paste(im, (x, y + lab))
    sheet.save(out_path)
    return out_path
