"""Module simulator: runs dev/src/addon straight from source (no bundle) against a fake chef (chef_sim.lua) and
renders the frames it draws, so views can be looked at without the game.

    python -I dev/src/sim/sim.py --list
    python -I dev/src/sim/sim.py walk [--frames 60,150] [--options '{"overlay": true}'] [--out DIR]
    python -I dev/src/sim/sim.py map08_out [--backdrop SHOT.jpg]

Output (default dev/out/sim/<scenario>/): frame_NNNN.png (full screen), map_NNNN.png (the open map, 2x) and
top_NNNN.png (the compass band, 2x) when rendered, sheet.png (every rendered frame), log.txt (chef.log),
warnings.txt (engine rules the addon broke: stale colors, top-layer draws with the map closed, unknown textures),
stats.txt (draws and distinct textures per frame: each texture costs the loader a GUI), checks.txt (a scenario's
'checks' on its rendered frames; the run exits 1 if one fails).

What is a stand-in: the background, the game's open map (a disk at hud.map) and the game's compass (a tick band at
the top). Their exact look and geometry aren't the game's; the mod's own draws are exact (positions, sizes, tints,
layer order). The pixel font (chef.text) is approximate. With a 'backdrop' (a game screenshot, read only) there are
no stand-ins: the mod's draws go over the game's own map and compass as the screenshot shows them.

Modules: modules.txt order; any other .lua file in src/addon is loaded just before main (so a new view module runs
without editing modules.txt). Scenarios: every SCENARIOS dict in scenarios/*.py (see scenarios/base.py).
"""
import sys, os, json, math, glob, argparse, importlib.util, random, time

HERE = os.path.dirname(os.path.abspath(__file__))
DEV = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(DEV, 'tools', '_pylib'))
from lupa import lua51                                      # noqa: E402
from PIL import Image, ImageDraw, ImageChops, ImageFont     # noqa: E402

ADDON = os.path.join(DEV, 'src', 'addon')
TEXTURES = os.path.join(DEV, 'src', 'textures')
OUT = os.path.join(DEV, 'out', 'sim')

# the player's own HUD settings (from their settings file); the sim writes its own copy for hud.lua to read
HUD_DEFAULT = {
    'hud_offset': 0, 'hud_scale': 0.89999997615814209, 'hud_map_position': 0, 'hud_background_opacity': 3,
    'hud_curve': 0, 'hud_compass': 0, 'hud_compass_width': 1, 'hud_compass_angle_range': 2,
    'hud_compass_small_notches': 0, 'hud_compass_ordinal_directions': 1, 'hud_map_navigation_mode': 1,
    'hud_samples': 0, 'hud_markers': 0, 'hud_primary_objective': 0, 'hud_secondary_objective': 0,
}
PEER = 'ed64736ca681ab28'


# ---------------------------------------------------------------------------------------------- scenarios
def load_scenarios():
    out = {}
    for path in sorted(glob.glob(os.path.join(HERE, 'scenarios', '*.py'))):
        name = 'sim_scn_' + os.path.splitext(os.path.basename(path))[0]
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for k, v in getattr(mod, 'SCENARIOS', {}).items():
            v = dict(v)
            v.setdefault('name', k)
            v.setdefault('source', os.path.basename(path))
            out[k] = v
    return out


def lerp_keys(keys, t, n):
    """keys: [(t, v1, v2, ...)] sorted by t; linear between, held outside."""
    if not keys:
        return None
    if t <= keys[0][0]:
        return list(keys[0][1:1 + n])
    for a, b in zip(keys, keys[1:]):
        if a[0] <= t <= b[0]:
            f = 0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
            return [a[i] + (b[i] - a[i]) * f for i in range(1, 1 + n)]
    return list(keys[-1][1:1 + n])


def in_spans(spans, t):
    return any(a <= t < b for a, b in spans or [])


LUA_LOADER = '''function(src, name)
    local f, e = loadstring(src, "@addon/" .. name .. ".lua")
    if not f then return false, e end
    local ok, r = pcall(f, T, chef)
    if not ok then return false, r end
    T.mod[name] = r
    return true
end'''

# the sim's own %APPDATA% and %LOCALAPPDATA% (folders in the run's out folder), never the player's
LUA_APPDATA = '''local a, la = ...
local g = os.getenv
os.getenv = function(k) if k == "APPDATA" then return a elseif k == "LOCALAPPDATA" then return la end return g(k) end'''


class Sim:
    def __init__(self, scn, options=None, out=None, backdrop=None):
        self.scn = scn
        self.w, self.h = scn.get('size', (1920, 1080))
        self.backdrop = backdrop or scn.get('backdrop')
        self.checks = []                # (frame, ok, message)
        self.out = out or os.path.join(OUT, scn['name'])
        os.makedirs(self.out, exist_ok=True)
        for old in glob.glob(os.path.join(self.out, '*.png')):
            os.remove(old)
        self.py_warnings, self.stats, self.rendered = [], [], []
        self.tex_cache = {}
        self.L = lua51.LuaRuntime(unpack_returned_tuples=True)
        L = self.L
        L.execute(open(os.path.join(HERE, 'chef_sim.lua'), encoding='utf-8').read())
        G = L.globals()
        self.G, self.SIM, self.chef = G, G.SIM, G.chef
        self.SIM.w, self.SIM.h = self.w, self.h
        self.SIM.peer = PEER
        # 0.9: the mission's unit count view.lua sizes the map by (small 4000..11000, big above that); None: no count
        self.SIM.num_units = scn.get('census', 7000)

        opts = dict(scn.get('options', {}))
        if options:
            opts.update(options)
        # 0.6's options: each view was its own option, so a scenario that lists any options has off what it doesn't
        # name. 0.7 has everything on unless a key says otherwise; a scenario with 'defaults': True (or no options at
        # all) runs with 0.7's defaults.
        if opts and not scn.get('defaults'):
            for k in ('ledger', 'compass', 'bezel', 'pings'):
                opts.setdefault(k, False)
            opts.setdefault('markers', 0)
            opts.setdefault('kinds', {})
            opts.setdefault('map_kinds', {})
        self.chef.options = self.to_lua(opts)
        # the Map key (Tab) tapped as the map opens and closes, as a player would (0.7 goes by the key); 'map_key':
        # False leaves it out (the world list alone)
        self.map_presses = []
        if scn.get('map_key', True):
            for (a, b) in scn.get('map_open', []):
                self.map_presses += [(a + 0.005, 'tab'), (b + 0.005, 'tab')]

        # the HUD settings file hud.lua reads, under a fake APPDATA
        hud = dict(HUD_DEFAULT)
        hud.update(scn.get('hud', {}))
        appdata = os.path.join(self.out, 'appdata')
        saves = os.path.join(appdata, 'Arrowhead', 'Helldivers2', 'saves')
        os.makedirs(saves, exist_ok=True)
        with open(os.path.join(saves, PEER + '_user_settings.config'), 'w') as f:
            f.write('{\n' + ''.join('\t%s = %r\n' % kv for kv in hud.items()) + '}\n')
        # the files the mod keeps in %LOCALAPPDATA% (radar zoom, the overlay's file) go to a fake one, emptied every run;
        # 0.9.1: the companion's two files live in its Temp subfolder (Windows has one; the mod creates no folder)
        localappdata = os.path.join(self.out, 'localappdata')
        temp = os.path.join(localappdata, 'Temp')
        os.makedirs(temp, exist_ok=True)
        for old in glob.glob(os.path.join(localappdata, 'treasure_radar*')) + glob.glob(os.path.join(temp, 'treasure_radar*')):
            os.remove(old)
        self.localappdata, self.temp = localappdata, temp
        # 0.9: a companion fix file already there at the start (a past session's), as text
        if scn.get('fix_file') is not None:
            with open(os.path.join(temp, 'treasure_radar_fix.txt'), 'w', encoding='utf-8') as f:
                f.write(scn['fix_file'])
        self.mod_lines = []             # (frame, the mod line's fields) for every frame the mod wrote one
        self._last_mod = None
        L.execute(LUA_APPDATA, appdata, localappdata)

        # textures: name = path under src/textures without .png; the sim's "resource id" is the name itself
        self.tex_files = {}
        for p in glob.glob(os.path.join(TEXTURES, '**', '*.png'), recursive=True):
            name = os.path.relpath(p, TEXTURES).replace('\\', '/')[:-4]
            self.tex_files[name] = p
        L.execute('T = { chef = chef, version = "0.7.0-sim", TEX = {}, mod = {} }')
        for name in self.tex_files:
            G.T.TEX[name] = name
            G.SIM.textures[name] = True

        # modules: modules.txt order, then any unlisted module file just before main
        listed = [l.strip() for l in open(os.path.join(ADDON, 'modules.txt'), encoding='utf-8')
                  if l.strip() and not l.strip().startswith('#')]
        extra = sorted(os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ADDON, '*.lua')))
        extra = [m for m in extra if m not in listed]
        order = [m for m in listed if m != 'main'] + extra + ['main']
        loader = L.eval(LUA_LOADER)
        self.loaded, self.missing = [], []
        for m in order:
            p = os.path.join(ADDON, m + '.lua')
            if not os.path.exists(p):
                self.missing.append(m)
                continue
            r = loader(open(p, encoding='utf-8').read(), m)
            ok, err = r if isinstance(r, tuple) else (r, None)
            if not ok:
                raise SystemExit('module %s failed to load: %s' % (m, err))
            self.loaded.append(m)
        self.M = G.T.mod.main
        self.K = G.T.mod.kinds
        # a scenario's own Lua, run once after the modules load: stand-ins for modules not written yet
        if scn.get('lua'):
            fn = L.eval('function(src) local f, e = loadstring(src, "=scenario") if not f then return false, e end '
                        'setfenv(f, setmetatable({ T = T, chef = chef, SIM = SIM }, { __index = _G })) '
                        'local ok, err = pcall(f) return ok, err end')
            r = fn(scn['lua'])
            ok, err = r if isinstance(r, tuple) else (r, None)
            if not ok:
                raise SystemExit('scenario lua failed: %s' % (err,))

        # units: (kind id or 16-hex unit kind, x, y, z[, t picked up / destroyed])
        self.units = []
        for i, u in enumerate(scn.get('units', [])):
            kid, hexkind = u[0], u[0]
            k = self.K.by_id[kid] if self.K else None
            if k is not None:
                hexkind = k.units[1]
            elif not (isinstance(kid, str) and len(kid) == 16):
                self.warn('scenario unit kind %r unknown (no such kind in this build): skipped' % (kid,))
                continue
            gone = u[4] if len(u) > 4 else None
            self.units.append({'unit': 'u%d' % (i + 1), 'kind': hexkind, 'x': u[1], 'y': u[2], 'z': u[3], 'gone': gone})
        lua_units, by_unit = L.table(), L.table()
        for i, u in enumerate(self.units):
            e = self.to_lua({'unit': u['unit'], 'kind': u['kind'], 'x': u['x'], 'y': u['y'], 'z': u['z'], 'alive': True})
            lua_units[i + 1] = e
            by_unit[u['unit']] = e
            u['lua'] = e
        self.SIM.units, self.SIM.by_unit = lua_units, by_unit

    def warn(self, s):
        if s not in self.py_warnings:
            self.py_warnings.append(s)

    def to_lua(self, v):
        if isinstance(v, dict):
            t = self.L.table()
            for k, x in v.items():
                t[k] = self.to_lua(x)
            return t
        if isinstance(v, (list, tuple)):
            t = self.L.table()
            for i, x in enumerate(v):
                t[i + 1] = self.to_lua(x)
            return t
        return v

    # ------------------------------------------------------------------ one frame
    def set_inputs(self, t, frame):
        scn, S = self.scn, self.SIM
        dt = scn.get('dt', 1 / 60)
        S.t, S.frame = t, frame
        x, y, z, yaw, pitch = lerp_keys(scn.get('camera', [(0, 0, 0, 1.6, 0, 0)]), t, 5)
        yr, pr = math.radians(yaw), math.radians(pitch)
        c = S.cam
        c.x, c.y, c.z = x, y, z
        c.fx, c.fy, c.fz = math.sin(yr) * math.cos(pr), math.cos(yr) * math.cos(pr), math.sin(pr)
        c.yaw = math.atan2(c.fx, c.fy)
        c.fov = math.radians(scn.get('fov', 70))
        S.worlds = max(scn.get('worlds', 1), 2 if in_spans(scn.get('map_open'), t) else 1)
        S.nocam = in_spans(scn.get('nocam'), t)
        S.mission = not in_spans(scn.get('ship'), t)
        wid = 1 + sum(1 for w in scn.get('new_world', []) if w <= t)
        if wid != S.world_id:
            S.world_id = wid
            self.G.SIM.new_world()
        down, pressed, mouse = self.L.table(), self.L.table(), self.L.table()
        for (a, b, name) in scn.get('hold', []):
            if a <= t < b:
                down[name] = True
        for (a, name) in scn.get('press', []) + self.map_presses:
            if a <= t < a + dt - 1e-9:
                pressed[name] = True
                down[name] = True
        for (a, b, name) in scn.get('mouse', []):
            if a <= t < b:
                mouse[name] = True
        S.down, S.pressed, S.mouse = down, pressed, mouse
        cur = lerp_keys(scn.get('cursor', []), t, 2)
        S.cursor = None if cur is None else self.to_lua(cur)
        S.wheel = sum(v for (a, v) in scn.get('wheel', []) if a <= t < a + dt - 1e-9)
        S.raw_x = sum(dx for (a, b, dx, dy) in scn.get('raw_mouse', []) if a <= t < b)
        S.raw_y = sum(dy for (a, b, dx, dy) in scn.get('raw_mouse', []) if a <= t < b)
        for u in self.units:
            u['lua'].alive = u['gone'] is None or t < u['gone']

    def step(self, frame):
        dt = self.scn.get('dt', 1 / 60)
        self.set_inputs(frame * dt, frame)
        self.SIM.draws = self.L.table()
        self.G.SIM.scan()
        self.M.update(dt)
        self.companion(frame)
        draws = self.SIM.draws
        n = len(draws)
        texs = {False: set(), True: set()}
        ops = {}
        for i in range(1, n + 1):
            d = draws[i]
            ops[d.op] = ops.get(d.op, 0) + 1
            if d.op == 'bitmap':
                texs[bool(d.top)].add(d.tex)
        self.stats.append((frame, frame * dt, n, ops, len(texs[False]), len(texs[True])))
        return draws

    # ------------------------------------------------------------------ the companion (COMPANION_INTERFACE.md)
    def read_mod_line(self):
        """the mod's Temp\treasure_radar_mod.txt as a dict (None: no file, or a line without its trailing end)"""
        p = os.path.join(self.temp, 'treasure_radar_mod.txt')
        try:
            with open(p, encoding='utf-8') as f:
                text = f.read()
        except OSError:
            return None
        if not text.endswith('\n'):
            self.warn('the mod line has no newline at its end')
        toks = text.split()
        if not toks or toks[-1] != 'end':
            return None
        out = {}
        for tok in toks[:-1]:
            k, _, v = tok.partition('=')
            out[k] = v
        return out

    def companion(self, frame):
        """a scenario's 'companion'(sim, frame, mod_line_fields) stands in for the screen reader, after the mod's
        update: a dict (or a str) it returns is written as treasure_radar_fix.txt (k=v ... end), read next frame"""
        fields = self.read_mod_line()
        if fields is not None and fields.get('seq') != self._last_mod:
            self._last_mod = fields.get('seq')
            self.mod_lines.append((frame, fields))
        fn = self.scn.get('companion')
        if not fn:
            return
        r = fn(self, frame, fields)
        if r is None:
            return
        if isinstance(r, dict):
            r = ' '.join('%s=%s' % kv for kv in r.items()) + ' end\n'
        p = os.path.join(self.temp, 'treasure_radar_fix.txt')
        with open(p + '.tmp', 'w', encoding='utf-8') as f:
            f.write(r)
        for i in range(20):         # Windows: a scanner holding the target for a moment refuses the replace
            try:
                os.replace(p + '.tmp', p)
                break
            except PermissionError:
                if i == 19:
                    raise
                time.sleep(0.01)

    def run(self, frames=None):
        total = self.scn.get('frames', 240)
        render = set(frames if frames is not None else self.scn.get('render', [total - 1]))
        for f in range(total):
            draws = self.step(f)
            if f in render:
                self.render(f, draws)
                if self.scn.get('checks'):
                    try:
                        res = self.scn['checks'](self, f) or []
                    except Exception as e:      # a check that breaks is a failure, not a crash
                        res = [(False, 'checks raised %s: %s' % (type(e).__name__, e))]
                    self.checks += [(f, bool(ok), msg) for ok, msg in res]
        return self.finish()

    # ------------------------------------------------------------------ rendering
    def color(self, c):
        if c is None:
            return (255, 0, 255, 255)
        a = c[4]
        return (int(c[1] or 0), int(c[2] or 0), int(c[3] or 0), int(255 if a is None else a))

    def tex_image(self, name, w, h, rgba):
        key = (name, w, h, rgba)
        im = self.tex_cache.get(key)
        if im is None:
            base = self.tex_cache.get(name)
            if base is None:
                base = Image.open(self.tex_files[name]).convert('RGBA')
                self.tex_cache[name] = base
            im = base.resize((w, h), Image.LANCZOS) if base.size != (w, h) else base.copy()
            if rgba != (255, 255, 255, 255):
                im = ImageChops.multiply(im, Image.new('RGBA', im.size, rgba))
            self.tex_cache[key] = im
        return im

    def background(self):
        w, h = self.w, self.h
        if self.backdrop:
            if os.path.exists(self.backdrop):
                return Image.open(self.backdrop).convert('RGBA').resize((w, h), Image.LANCZOS)
            self.warn('backdrop %s not found: the procedural ground instead' % self.backdrop)
        bg = self.scn.get('background')
        if bg and os.path.exists(bg):
            return Image.open(bg).convert('RGBA').resize((w, h))
        # a hazy, mid-tone planet surface: a sky band, then ground with low-contrast blotches
        im = Image.new('RGBA', (w, h), (0, 0, 0, 255))
        d = ImageDraw.Draw(im)
        hz = int(h * 0.42)
        for yy in range(h):
            if yy < hz:
                f = yy / hz
                col = (int(150 + 40 * f), int(160 + 30 * f), int(160 + 20 * f), 255)
            else:
                f = (yy - hz) / (h - hz)
                col = (int(96 - 30 * f), int(92 - 28 * f), int(70 - 22 * f), 255)
            d.line([(0, yy), (w, yy)], fill=col)
        rnd = random.Random(7)
        over = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        od = ImageDraw.Draw(over)
        for _ in range(140):
            cx, cy = rnd.uniform(0, w), rnd.uniform(hz, h)
            r = rnd.uniform(20, 140) * (0.4 + (cy - hz) / (h - hz))
            v = rnd.choice([(40, 38, 30, 60), (150, 140, 110, 45), (70, 80, 55, 50)])
            od.ellipse([cx - r * 2, cy - r * 0.5, cx + r * 2, cy + r * 0.5], fill=v)
        return Image.alpha_composite(im, over)

    def map_standin(self, im):
        """the game's open map (stand-in): a dark terrain disk with a cream rim, me at the center, north up"""
        m = self.G.T.mod.main.S.map
        if m.cx is None:
            return
        cx, cy, r = m.cx, self.h - m.cy, m.r
        over = Image.new('RGBA', im.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(over)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(34, 40, 34, 235))
        for k in range(-4, 5):
            d.line([(cx + k * r / 4, cy - r), (cx + k * r / 4, cy + r)], fill=(70, 78, 66, 120))
            d.line([(cx - r, cy + k * r / 4), (cx + r, cy + k * r / 4)], fill=(70, 78, 66, 120))
        mask = Image.new('L', im.size, 0)
        ImageDraw.Draw(mask).ellipse([cx - r, cy - r, cx + r, cy + r], fill=255)
        over.putalpha(ImageChops.multiply(over.getchannel('A'), mask))
        d = ImageDraw.Draw(over)
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(201, 197, 170, 255), width=max(1, round(self.h / 540)))
        s = self.h / 108
        d.polygon([(cx, cy - s * 1.4), (cx + s, cy + s), (cx, cy + s * 0.4), (cx - s, cy + s)], fill=(255, 233, 0, 255))
        d.text((cx - r, cy - r - 14), 'GAME MAP (stand-in)', fill=(201, 197, 170, 200))
        im.alpha_composite(over)

    def compass_standin(self, im, heading):
        """the game's compass (stand-in): ticks every 15 degrees over its angle range, at the top center. With
        compass.lua present the strip and the heading box go where its measured geometry says (compass.geometry(S));
        else +-90 degrees over +-0.18 w."""
        w, h = self.w, self.h
        d = ImageDraw.Draw(im)
        cx, y, half, span = w / 2, h * 0.045, w * 0.18, 90.0
        top, bottom = y - h * 0.008, y + h * 0.008
        comp = self.G.T.mod.compass
        if comp is not None and comp.geometry is not None:
            try:
                g = comp.geometry(self.G.T.mod.main.S)
                cx, y, half, span = g.cx, h - g.y, g.half, float(g.span)
                top, bottom = h - g.top, h - g.bottom
                hd = '%03d' % (round(math.degrees(heading)) % 360)
                bh = g.box_half * 0.8
                d.rectangle([cx - bh, bottom + 2, cx + bh, h - g.box], outline=(255, 255, 237, 160))
                d.text((cx - 9, bottom + 4), hd, fill=(255, 255, 237, 230))
            except Exception as e:
                self.warn('compass.geometry failed in the stand-in: %s' % (e,))
        d.line([(cx - half, y), (cx + half, y)], fill=(255, 255, 237, 60), width=1)
        for a in range(0, 360, 15):
            rel = (a - math.degrees(heading) + 540) % 360 - 180
            if abs(rel) > span:
                continue
            x = cx + rel / span * half
            if a % 90 == 0:
                d.text((x - 3, y - 6), 'NESW'[a // 90], fill=(255, 255, 237, 230))
            else:
                t = (bottom - top) * (0.5 if a % 45 == 0 else 0.25)
                d.line([(x, y - t), (x, y + t)], fill=(255, 255, 237, 200), width=1)
        d.text((cx - half, bottom + 2), 'compass (stand-in)', fill=(255, 255, 237, 120))

    def text_img(self, s, px, rgba):
        font = ImageFont.load_default()
        tw = len(s) * 6
        small = Image.new('L', (max(1, tw), 8), 0)
        ImageDraw.Draw(small).text((0, -2), s, fill=255, font=font)
        big = small.resize((max(1, tw * px), 8 * px), Image.NEAREST)
        out = Image.new('RGBA', big.size, rgba)
        out.putalpha(ImageChops.multiply(big, Image.new('L', big.size, rgba[3])))
        return out

    def project(self, x, y, z):
        r = self.chef.world_to_screen(x, y, z)
        if r is None or r[0] is None:
            return None
        return r

    def paste(self, im, patch, x, y_top):
        x, y_top = int(round(x)), int(round(y_top))
        if x >= im.width or y_top >= im.height or x + patch.width <= 0 or y_top + patch.height <= 0:
            return
        sx, sy = max(0, -x), max(0, -y_top)
        if sx or sy or x + patch.width > im.width or y_top + patch.height > im.height:
            patch = patch.crop((sx, sy, min(patch.width, im.width - x), min(patch.height, im.height - y_top)))
            x, y_top = x + sx, y_top + sy
        im.alpha_composite(patch, (x, y_top))

    def draw_op(self, im, d):
        H, op = self.h, d.op
        if op == 'rect':
            w, h = max(1, int(round(d.w))), max(1, int(round(d.h)))
            self.paste(im, Image.new('RGBA', (w, h), self.color(d.c)), d.x, H - d.y - d.h)
        elif op == 'bitmap':
            w, h = int(round(d.w)), int(round(d.h))
            if w > 0 and h > 0:
                self.paste(im, self.tex_image(d.tex, w, h, self.color(d.c)), d.x, H - d.y - d.h)
        elif op == 'text':
            px = max(1, int(round(d.px)))
            self.paste(im, self.text_img(str(d.s), px, self.color(d.c)), d.x, H - d.y - 8 * px)
        elif op == 'sprite':
            rows, cell, cols = d.rows, d.cell, d.cols
            n = len(rows)
            size = max(1, int(round(cell)))
            for ri in range(1, n + 1):
                for ci, ch in enumerate(rows[ri]):
                    c = None if ch == '.' else cols[ch]
                    if c is not None:
                        self.paste(im, Image.new('RGBA', (size, size), self.color(c)),
                                   d.x + ci * cell, H - d.y - n * cell + (ri - 1) * cell)
        elif op == 'line':
            a = self.project(d.a[1], d.a[2], d.a[3])
            b = self.project(d.b[1], d.b[2], d.b[3])
            if a and b:
                over = Image.new('RGBA', im.size, (0, 0, 0, 0))
                ImageDraw.Draw(over).line([(a[0], H - a[1]), (b[0], H - b[1])], fill=self.color(d.c), width=1)
                im.alpha_composite(over)

    def render(self, frame, draws):
        im = self.background()
        main, top = [], []
        for i in range(1, len(draws) + 1):
            d = draws[i]
            (top if d.top else main).append((d.layer or 900, i, d))
        main.sort(key=lambda e: (e[0], e[1]))
        top.sort(key=lambda e: (e[0], e[1]))
        S = self.G.T.mod.main.S
        standins = not (self.backdrop and os.path.exists(self.backdrop))
        if standins:
            self.compass_standin(im, S.heading or 0)
        for _, _, d in main:
            self.draw_op(im, d)
        map_open = self.SIM.worlds >= 2
        if map_open and standins:
            self.map_standin(im)
        for _, _, d in top:
            self.draw_op(im, d)
        cur = self.SIM.cursor
        if cur is not None:
            # the cursor is in window pixels from the top-left (what chef.cursor() is assumed to give)
            cx, cy = cur[1], cur[2]
            ImageDraw.Draw(im).polygon([(cx, cy), (cx, cy + 16), (cx + 4, cy + 12), (cx + 11, cy + 12)],
                                       fill=(255, 255, 255, 255), outline=(0, 0, 0, 255))
        im = im.convert('RGB')
        path = os.path.join(self.out, 'frame_%04d.png' % frame)
        im.save(path)
        self.rendered.append(path)
        m = S.map
        if map_open and m.cx is not None:
            r = m.r * 1.25
            crop = im.crop((int(m.cx - r), int(self.h - m.cy - r), int(m.cx + r), int(self.h - m.cy + r)))
            crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS).save(os.path.join(self.out, 'map_%04d.png' % frame))
        crop = im.crop((int(self.w * 0.25), 0, int(self.w * 0.75), int(self.h * 0.14)))
        crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS).save(os.path.join(self.out, 'top_%04d.png' % frame))

    def finish(self):
        G = self.G
        logs = G.SIM.logs
        with open(os.path.join(self.out, 'log.txt'), 'w', encoding='utf-8') as f:
            for i in range(1, len(logs) + 1):
                f.write(logs[i] + '\n')
        warns = [G.SIM.warnings[i] for i in range(1, len(G.SIM.warnings) + 1)] + self.py_warnings
        if self.missing:
            warns.append('modules not present (skipped): ' + ', '.join(self.missing))
        with open(os.path.join(self.out, 'warnings.txt'), 'w', encoding='utf-8') as f:
            f.write('\n'.join(warns) + ('\n' if warns else ''))
        with open(os.path.join(self.out, 'stats.txt'), 'w', encoding='utf-8') as f:
            f.write('frame      t  draws main_tex top_tex  ops\n')
            for (fr, t, n, ops, tm, tt) in self.stats:
                f.write('%5d %6.2f %6d %8d %7d  %s\n' % (fr, t, n, tm, tt, json.dumps(ops, sort_keys=True)))
        if self.rendered:
            ims = [Image.open(p) for p in self.rendered]
            sw, sh = self.w // 3, self.h // 3
            cols = min(3, len(ims))
            rows = (len(ims) + cols - 1) // cols
            sheet = Image.new('RGB', (cols * sw, rows * sh), (0, 0, 0))
            dr = ImageDraw.Draw(sheet)
            for i, (im, p) in enumerate(zip(ims, self.rendered)):
                x, y = (i % cols) * sw, (i // cols) * sh
                sheet.paste(im.resize((sw, sh), Image.LANCZOS), (x, y))
                dr.text((x + 4, y + 4), os.path.basename(p), fill=(255, 0, 255))
            sheet.save(os.path.join(self.out, 'sheet.png'))
        print('scenario %s: %d frames at %dx%d; modules: %s' % (self.scn['name'], len(self.stats), self.w, self.h,
                                                                ', '.join(self.loaded)))
        print('peak draws/frame %d, peak distinct textures: main %d, top %d' % (
            max((s[2] for s in self.stats), default=0), max((s[4] for s in self.stats), default=0),
            max((s[5] for s in self.stats), default=0)))
        print('rendered: %s' % ', '.join(os.path.basename(p) for p in self.rendered))
        print('warnings: %d%s' % (len(warns), ''.join('\n  ' + w for w in warns[:12])))
        failed = [c for c in self.checks if not c[1]]
        if self.scn.get('checks'):
            with open(os.path.join(self.out, 'checks.txt'), 'w', encoding='utf-8') as f:
                for (fr, ok, msg) in self.checks:
                    f.write('%5d %s %s\n' % (fr, 'ok  ' if ok else 'FAIL', msg))
            print('checks: %d, %d failed%s' % (len(self.checks), len(failed),
                                               ''.join('\n  %d %s' % (fr, msg) for fr, _, msg in failed[:12])))
        print('out: ' + self.out)
        return not failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('scenario', nargs='?')
    ap.add_argument('--list', action='store_true')
    ap.add_argument('--frames', help="frames to render, e.g. 60,150 (default: the scenario's)")
    ap.add_argument('--options', help="chef.options as JSON, merged over the scenario's")
    ap.add_argument('--size', help='WxH, e.g. 2560x1440')
    ap.add_argument('--backdrop', help="a game screenshot to draw over (no stand-ins), over the scenario's")
    ap.add_argument('--out')
    a = ap.parse_args(argv)
    scns = load_scenarios()
    if a.list or not a.scenario:
        for k, v in scns.items():
            print('%-18s %-10s %s' % (k, v['source'], v.get('about', '')))
        return
    if a.scenario not in scns:
        raise SystemExit('no scenario %r (try --list)' % a.scenario)
    scn = dict(scns[a.scenario])
    if a.size:
        w, h = a.size.lower().split('x')
        scn['size'] = (int(w), int(h))
    frames = [int(x) for x in a.frames.split(',')] if a.frames else None
    sim = Sim(scn, json.loads(a.options) if a.options else None, a.out, a.backdrop)
    if not sim.run(frames):
        sys.exit(1)


if __name__ == '__main__':
    main()
