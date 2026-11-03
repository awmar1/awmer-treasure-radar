"""Runs a mod's real boot script (Chef Loader + its addons) in a real Lua 5.1 against the fake engine, frame by frame
through a scenario, and writes what it drew as PNGs plus run.json.

    r = Runner(mod_dir, ['core', 'ledger', 'medal'], scenario, out_dir)
    result = r.run(render=[120, 240])
"""
import json
import os
import re
import shutil
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
PYLIB = os.path.join(os.path.dirname(HERE), 'tools', '_pylib')
if PYLIB not in sys.path:
    sys.path.insert(0, PYLIB)

from lupa import lua51  # noqa: E402

import archive  # noqa: E402
import kinds as kinds_mod  # noqa: E402
import render as render_mod  # noqa: E402

PATCH_NAME = '9ba626afa44a3aa3.patch_'
BOOT_ID = 'f476df93691895fa'
UI_MATERIAL = 'e2d6ed90906c1e8b'
LOG_NAME = 'treasure_radar'       # the loader's FILES (read from the boot source when it says otherwise)

# Lua run before the boot script: io/os as in game, with %LOCALAPPDATA% / %APPDATA% pointing into the run folder and
# relative paths resolved against it (in game they're relative to the game's folder, where data\ is).
ENV_LUA = r"""
local run_dir, lad, ad = ...
local real_open, real_getenv, real_lines = io.open, os.getenv, io.lines
local function resolve(p)
  if type(p) == 'string' and not p:match('^%a:[\\/]') and not p:match('^[\\/]') then return run_dir .. '\\' .. p end
  return p
end
io.open = function(p, m) return real_open(resolve(p), m) end
io.lines = function(p, ...) if p == nil then return real_lines() end return real_lines(resolve(p), ...) end
os.getenv = function(k)
  if k == 'LOCALAPPDATA' then return lad end
  if k == 'APPDATA' then return ad end
  return real_getenv(k)
end
os.exit = function() error('os.exit called (the harness refuses it)', 2) end
HARNESS_PRINTS = {}
print = function(...)
  local t = {}
  for i = 1, select('#', ...) do t[i] = tostring((select(i, ...))) end
  HARNESS_PRINTS[#HARNESS_PRINTS + 1] = table.concat(t, '\t')
end
"""


def load_engine(L):
    """Runs engine.lua in a LuaRuntime (as the chunk '@engine.lua', so tracebacks name it) and returns E."""
    with open(os.path.join(HERE, 'engine.lua'), 'rb') as f:
        got = L.globals().loadstring(f.read(), '@engine.lua')
    fn, err = got if isinstance(got, tuple) else (got, None)
    if fn is None:
        raise SystemExit('engine.lua does not compile: %s' % err)
    return fn()


def parse_dump(text):
    """E.dump() -> [(world slot, (kind, layer, x, y, w, h, (a, r, g, b), texture, order, gui id, world name))]"""
    out = []
    if not text:
        return out
    for i, line in enumerate(text.split('\n')):
        p = line.split('\t')
        if len(p) < 14:
            continue
        tex = p[13] if p[13] != '-' else None
        out.append((int(p[1]), (p[0], float(p[4]), float(p[5]), float(p[6]), float(p[7]), float(p[8]),
                                (int(p[9]), int(p[10]), int(p[11]), int(p[12])), tex, i, int(p[3]), p[2])))
    return out


def parse_lines(text):
    out = []
    if not text:
        return out
    for line in text.split('\n'):
        p = line.split('\t')
        if len(p) == 10:
            out.append(tuple(float(v) for v in p))
    return out


class Result:
    """What a run left: the log, per-frame counts, the captured frames' draw calls. Scenario checks get this."""

    def __init__(self):
        self.log = ''
        self.counts = {}            # frame -> {'main_rect': n, ...}
        self.draws = {}             # frame -> parsed records (captured frames only)
        self.frames_t = {}          # frame -> time
        self.tex_names = {}         # hex -> addon name ('medal', 'sweep[3]', 'glyph2:5')
        self.crashed = None
        self.scenario = None

    def log_has(self, pattern):
        return re.search(pattern, self.log, re.M) is not None

    def log_lines(self, pattern):
        return [l for l in self.log.splitlines() if re.search(pattern, l)]

    def frame(self, spec):
        return self.scenario.frame_of(spec)

    def draws_of(self, frame, tex=None, world=None, layer=None, kind=None):
        """The captured draw calls of a frame (spec like 300 or '10s'), filtered: tex = an addon texture name (prefix
        match: 'sweep' matches 'sweep[3]'; 'medal' matches only 'medal'; one ending in '/' matches every name under it,
        'radar/' matches 'radar/sweep/03') or hex; world = 'main' / 'top'; layer =
        (lo, hi) inclusive; kind = 'rect' / 'bitmap'. None if the frame wasn't captured."""
        f = self.frame(frame)
        if f not in self.draws:
            return None
        out = []
        for slot, r in self.draws[f]:
            if world == 'main' and slot != 0 or world == 'top' and slot == 0:
                continue
            if kind and r[0] != kind:
                continue
            if layer and not (layer[0] <= r[1] <= layer[1]):
                continue
            if tex:
                name = self.tex_names.get(r[7] or '', r[7] or '')
                if not (name == tex or r[7] == tex or (name.startswith(tex + '[')) or name.startswith(tex + ':')
                        or tex.endswith('/') and name.startswith(tex)):
                    continue
            out.append((slot, r))
        return out

    def count(self, frame, **kw):
        d = self.draws_of(frame, **kw)
        return None if d is None else len(d)


class Runner:
    def __init__(self, mod_dir, options, scenario, out_dir, verbose=True, keep_run=False):
        self.mod_dir = os.path.abspath(mod_dir)
        self.options = list(options)
        self.sc = scenario
        self.out_dir = os.path.abspath(out_dir)
        self.verbose = verbose
        self.keep_run = keep_run    # False: the patch copies in _run/data are deleted after the run
        self.run_dir = os.path.join(self.out_dir, '_run')
        self.errors, self.notes = [], []

    def say(self, *a):
        if self.verbose:
            print(*a, flush=True)

    # ---------------------------------------------------------------- setup
    def lay_out(self):
        """<run>/data/9ba626afa44a3aa3.patch_<n> (+ .gpu_resources, .stream) for the options in order, and the
        user folders with the player's settings file."""
        if os.path.isdir(self.run_dir):
            shutil.rmtree(self.run_dir)
        data = os.path.join(self.run_dir, 'data')
        os.makedirs(data)
        self.lad = os.path.join(self.run_dir, 'LocalAppData')
        self.ad = os.path.join(self.run_dir, 'AppData', 'Roaming')
        os.makedirs(os.path.join(self.lad, 'Temp'))     # 0.9.1: the companion files go to %LOCALAPPDATA%\Temp
        saves = os.path.join(self.ad, 'Arrowhead', 'Helldivers2', 'saves')
        os.makedirs(saves)
        with open(os.path.join(saves, '%s_user_settings.config' % self.sc.peer), 'w', newline='\n') as f:
            f.write(self.sc.settings_text())
        for rel, text in self.sc.files.items():
            p = os.path.join(self.run_dir, rel.replace('/', os.sep))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, 'w', newline='\n') as f:
                f.write(text)
        self.patches = []
        for n, opt in enumerate(self.options):
            src = archive.option_patch(self.mod_dir, opt)
            if not os.path.exists(src):
                raise SystemExit('no option folder %r in %s (no %s)' % (opt, self.mod_dir, src))
            dst = os.path.join(data, PATCH_NAME + str(n))
            for ext in ('', '.gpu_resources', '.stream'):
                if os.path.exists(src + ext):
                    shutil.copyfile(src + ext, dst + ext)
            self.patches.append((opt, archive.Patch(dst)))
        if self.sc.extra_lua:
            dst = os.path.join(data, PATCH_NAME + str(len(self.options)))
            archive.write_lua_patch(dst, self.sc.extra_lua)
            self.patches.append(('(scenario lua)', archive.Patch(dst)))

    def find_resources(self):
        """The boot script, the addon sources (for kinds and texture names) and every texture in the archives."""
        self.boot = None
        self.addon_src = b''
        self.textures = {}          # hex -> (patch, entry)
        for opt, p in self.patches:
            for hx, src in p.lua_resources():
                if hx == BOOT_ID and self.boot is None:
                    self.boot = (opt, src)
                elif src.startswith(b'-- HD2-Addon:'):
                    self.addon_src += src + b'\n'
            for e in p.of_type(archive.TEXTURE_TYPE):
                self.textures.setdefault(e.hex, (p, e))
        if self.boot is None:
            raise SystemExit('no boot script (Lua resource %s) in the options %s' % (BOOT_ID, ','.join(self.options)))
        m = re.search(rb"local FILES = '([^']+)'", self.boot[1])
        self.log_name = m.group(1).decode() if m else LOG_NAME
        self.kinds = kinds_mod.Registry(self.addon_src or None)
        for name, k in self.sc.extra_kinds.items():
            self.kinds.add(name, k['units'], **{a: b for a, b in k.items() if a != 'units'})
        self.tex_names = kinds_mod.parse_addon_textures(self.addon_src) if self.addon_src else {}

    def texture_pixels(self, hx):
        t = self.textures.get(hx)
        if not t:
            return None
        return t[0].texture_rgba(t[1])

    def start_lua(self):
        L = lua51.LuaRuntime(unpack_returned_tuples=True)
        self.L = L
        L.execute(ENV_LUA, self.run_dir, self.lad, self.ad)
        E = load_engine(L)
        self.E = E
        E.w, E.h = self.sc.w, self.sc.h
        E.peer = self.sc.peer
        E.strict_units = self.sc.strict_units
        for kind, calls in self.sc.fragile_kinds.items():
            known = self.kinds.kinds.get(kind)
            ids = known['units'] if known else [self.kinds.resolve(kind)[1]]
            for hx in ids:
                for what in calls:
                    E.set_fragile(hx, what)
        for hx in self.textures:
            E.set_texture_loaded(hx)
        for hx in self.sc.extra_textures:
            E.set_texture_loaded(hx)

    # ---------------------------------------------------------------- the timeline
    def prepare_units(self):
        sc = self.sc
        mains = [w for w in sc.worlds if w['main']]
        if not mains:
            sc.world('main', at=0.0)
            mains = [w for w in sc.worlds if w['main']]
        default_world = mains[-1]['name']
        self.units = []
        for i, u in enumerate(sc.units):
            kind, hx = self.kinds.resolve(u['kind'], u['variant'])
            d = dict(u, kind=kind, hex=hx, world=u['world'] or default_world, uid=None, state='pending', i=i)
            if d['pickup_at'] is not None and d['remove_after'] is not None:
                d['remove_at'] = d['pickup_at'] + d['remove_after']
            else:
                d['remove_at'] = None
            self.units.append(d)
        self.world_state = {w['name']: 'pending' for w in sc.worlds}

    def apply_timeline(self, t, dt):
        """Worlds coming and going, units appearing / picked up / removed, the camera, input. For time t."""
        sc, E = self.sc, self.E
        # the previous frame's time as the run loop computes it (fno * dt): t - dt can round below it, and a one-frame
        # event right on a frame boundary (a wheel at 20.3 s at 30 fps) then fired on two frames
        prev = (round(t / dt) - 1) * dt
        for w in sc.worlds:
            st = self.world_state[w['name']]
            if st == 'pending' and t >= w['at'] and (w['until'] is None or t < w['until']):
                E.new_world(w['name'], w['main'])
                self.world_state[w['name']] = 'live'
                if w['filler']:
                    avoid = self.L.table_from({h: True for h in self.kinds.all_ids()})
                    E.add_filler(w['name'], w['filler'], w['seed'], w['spread'], avoid)
                if w['main']:
                    # anything left in a world that went away with the old main world
                    for o in sc.worlds:
                        if o['name'] != w['name'] and self.world_state[o['name']] == 'live' and o['main']:
                            self.world_state[o['name']] = 'gone'
                    for u in self.units:
                        if u['state'] == 'live' and u['world'] != w['name']:
                            u['state'] = 'gone'
                self.event_log.append((round(t, 4), 'world %s %s (%d units)' % (
                    w['name'], 'is the main world' if w['main'] else 'opened', E.num_units(w['name']))))
                if w['main']:
                    self.cam_dirty = True
            elif st == 'live' and w['until'] is not None and t >= w['until']:
                E.destroy_world(w['name'])
                self.world_state[w['name']] = 'gone'
                self.event_log.append((round(t, 4), 'world %s went away' % w['name']))
        # units
        for u in self.units:
            if u['state'] == 'pending' and self.world_state.get(u['world']) == 'live' and \
                    (u['spawn_at'] is None or t >= u['spawn_at']) and (u['pickup_at'] is None or t < u['pickup_at']):
                u['uid'] = E.add_unit(u['world'], u['hex'], u['x'], u['y'], u['z'], 0)
                u['state'] = 'live'
                if u['spawn_at'] is not None:
                    self.event_log.append((round(t, 4), 'spawned %s at %.0f, %.0f' % (u['kind'], u['x'], u['y'])))
            if u['state'] == 'live' and u['pickup_at'] is not None and t >= u['pickup_at']:
                E.kill_unit(u['uid'])
                u['state'] = 'dead'
                self.event_log.append((round(t, 4), 'picked up %s%s at %.0f, %.0f' % (
                    u['kind'], ' (%s)' % u['label'] if u['label'] else '', u['x'], u['y'])))
            if u['state'] == 'dead' and u['remove_at'] is not None and t >= u['remove_at']:
                E.remove_unit(u['uid'])
                u['state'] = 'removed'
        # the camera unit: in the main world, after its other units
        main = self.E.main
        if main is not None and self.cam_dirty:
            self.cam_dirty = False
            E.make_camera_unit(None, kinds_mod.CAMERA_UNIT)
        x, y, z, yaw, pitch, fov = sc.camera_at(t)
        E.set_camera(x, y, z, yaw, pitch, fov if fov is not None else 50.0)
        self.cam_now = (x, y, z, yaw, pitch, fov if fov is not None else 50.0)
        # input
        cx, cy = self.cursor
        wheel, rx, ry = 0.0, 0.0, 0.0
        for (et, kind, data) in sc.events:
            if kind == 'cursor' and et <= t:
                cx, cy = data
            elif kind == 'wheel' and prev < et <= t:
                wheel += data
            elif kind == 'raw' and et <= t < data[0]:
                rx, ry = rx + data[1], ry + data[2]
            elif kind == 'resize' and prev < et <= t:
                E.w, E.h = data
                self.event_log.append((round(t, 4), 'screen %dx%d' % data))
        self.cursor = (cx, cy)
        E.set_input(','.join(sc.keys_at(t)), ','.join(sc.mouse_at(t)), cx, cy, wheel, rx, ry)

    def truth_units(self):
        return [(u['x'], u['y'], u['z']) for u in self.units if u['state'] == 'live']

    # ---------------------------------------------------------------- the run
    def run(self, render=None, capture=None, contact=True):
        t_start = time.time()
        sc = self.sc
        os.makedirs(self.out_dir, exist_ok=True)
        for f in os.listdir(self.out_dir):
            if re.match(r'frame_\d+\.png$', f) or f in ('contact.png', 'run.json'):
                os.remove(os.path.join(self.out_dir, f))
        self.lay_out()
        self.find_resources()
        self.start_lua()
        self.prepare_units()
        self.event_log = []
        self.cam_dirty = False
        self.cursor = (sc.w / 2, sc.h / 2)
        total = sc.total_frames()
        render_set = sorted({sc.frame_of(f) for f in (render if render is not None else sc.frames)} & set(range(1, total + 1)))
        # draw calls are kept for the frames rendered, the scenario's own frames (its checks look at those even when
        # --frames renders others) and its capture list
        capture_set = set(render_set) | {sc.frame_of(f) for f in list(capture or []) + list(sc.capture) + list(sc.frames)}
        res = Result()
        res.scenario, res.tex_names = sc, self.tex_names
        res.lad = self.lad          # the run's %LOCALAPPDATA% (the log; the companion files in its Temp)
        renderer = render_mod.Renderer(self.texture_pixels, sc.w, sc.h)
        G = self.L.globals()
        dt = 1.0 / sc.fps

        # the boot script, as the game runs it: the chunk, then init(), then update(dt) / render() every frame
        boot_opt, boot_src = self.boot
        self.say('boot %s from %s (%d bytes); options %s' % (BOOT_ID, boot_opt, len(boot_src), ','.join(self.options)))
        aborted = None
        self.E.begin_frame(0.0)
        try:
            got = G.loadstring(boot_src, '@boot')
            chunk, err = got if isinstance(got, tuple) else (got, None)
            if chunk is None:
                raise SystemExit('boot does not compile: %s' % err)
            chunk()
            if self.lua_type(G.init) == 'function':
                G.init()
        except Exception as e:  # noqa: BLE001  (a Lua error escaping the boot script)
            aborted = 'boot raised: %s' % e
        frames_out = []
        counts = []
        t = 0.0
        for fno in range(1, total + 1) if not aborted else []:
            t = fno * dt
            self.E.begin_frame(dt)
            self.apply_timeline(t, dt)
            try:
                if self.lua_type(G.update) == 'function':
                    G.update(dt)
                if self.lua_type(G.render) == 'function':
                    G.render()
            except Exception as e:  # noqa: BLE001
                aborted = 'frame %d: a Lua error escaped update/render: %s' % (fno, e)
            c = self.E.counts
            row = {k: c[k] for k in c}
            counts.append((fno, row))
            res.frames_t[fno] = t
            crashed = self.E.crashed
            if fno in capture_set or crashed:
                res.draws[fno] = parse_dump(self.E.dump())
            if fno in render_set or crashed:
                cam = render_mod.Cam(*self.cam_now[:5], self.cam_now[5], self.E.w, self.E.h)
                renderer.set_size(int(self.E.w), int(self.E.h))
                img = renderer.frame(fno, cam, res.draws[fno], parse_lines(self.E.dump_lines()), self.truth_units(),
                                     sc.map_open_at(t), sc.hud_settings)
                p = os.path.join(self.out_dir, 'frame_%04d.png' % fno)
                img.save(p)
                frames_out.append((p, fno, t, sc.map_open_at(t)))
            if crashed:
                aborted = 'ENGINE CRASH in frame %d (t=%.2f s): %s' % (fno, t, crashed)
                res.crashed = {'frame': fno, 't': t, 'message': crashed, 'traceback': self.E.crash_trace}
            if aborted:
                break
        if not aborted:
            try:
                if self.lua_type(G.shutdown) == 'function':
                    G.shutdown()
            except Exception as e:  # noqa: BLE001
                self.errors.append('shutdown raised: %s' % e)
        res.counts = dict(counts)
        res.log = self.read_text(os.path.join(self.lad, self.log_name + '.log'))

        # ---------------------------------------------------------------- the report
        warnings = []
        for line in (self.E.dump_warnings() or '').split('\n'):
            if line:
                n, f0, t0, msg = line.split('\t', 3)
                warnings.append({'count': int(n), 'first_frame': int(f0), 'first_t': round(float(t0), 3), 'message': msg})
        missing = []
        for line in (self.E.dump_missing() or '').split('\n'):
            if line:
                f0, name = line.split('\t', 1)
                missing.append({'first_frame': int(f0), 'name': name})
        prints = [self.L.globals().HARNESS_PRINTS[i + 1] for i in range(len(self.L.globals().HARNESS_PRINTS))]
        log_lines = res.log.splitlines()
        err_re = re.compile(r'frame error|\berror: |could not (start|compile)|switched off|failed to start|crashed in|'
                            r'kept off|addon search failed|skipped .*patch')
        addon_errors = [l for l in log_lines if err_re.search(l)]
        frame_errors = [l for l in log_lines if 'frame error' in l]
        checks = []
        for desc, fn in sc.checks:
            try:
                r = fn(res)
                ok, detail = (r if isinstance(r, tuple) else (bool(r), ''))
            except Exception as e:  # noqa: BLE001
                ok, detail = False, 'check raised %s: %s' % (type(e).__name__, e)
            checks.append({'check': desc, 'ok': bool(ok), 'detail': detail})
        unknown = [{'texture': k, 'first_frame': v} for k, v in sorted(renderer.unknown.items(), key=lambda kv: kv[1])]
        keys = sorted({k for _, row in counts for k in row})
        report = {
            'scenario': sc.name,
            'mod': self.mod_dir,
            'options': self.options,
            'screen': [sc.w, sc.h], 'fps': sc.fps, 'frames_run': len(counts), 'seconds': round(t, 3),
            'ok': not aborted and not frame_errors and not addon_errors and all(c['ok'] for c in checks),
            'aborted': aborted,
            'crash': res.crashed,
            'errors': self.errors + ([aborted] if aborted else []),
            'frame_errors': frame_errors,
            'addon_errors': addon_errors,
            'checks': checks,
            'warnings': warnings,
            'missing_engine_functions': missing,
            'unknown_textures': unknown,
            'prints': prints[-50:],
            'events': self.event_log,
            'log_tail': log_lines[-60:],
            'rendered': [{'frame': f, 't': round(tt, 3), 'png': os.path.basename(p), 'map_open': m}
                         for p, f, tt, m in frames_out],
            'textures_in_archives': len(self.textures),
            'kinds_from': self.kinds.source,
            'engine_stats': {k: self.E.stats[k] for k in self.E.stats},
            'counts_keys': keys,
            'counts': [[f] + [row.get(k, 0) for k in keys] for f, row in counts],
            'wall_seconds': round(time.time() - t_start, 2),
        }
        report['frame_summary'] = self.draw_summaries(res, frames_out)
        with open(os.path.join(self.out_dir, 'run.json'), 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=1)
        if contact and frames_out:
            items = [(p, 'frame %d  t=%.1fs%s' % (fno, tt, '  MAP OPEN' if m else '')) for p, fno, tt, m in frames_out]
            render_mod.contact_sheet(items, os.path.join(self.out_dir, 'contact.png'),
                                     title='%s | %s | %s' % (sc.name, os.path.basename(self.mod_dir), ','.join(self.options)))
        self.report = report
        if not self.keep_run:      # the copies of the mod's archives are ~20 MB a run; the log and settings stay
            shutil.rmtree(os.path.join(self.run_dir, 'data'), ignore_errors=True)
        return res, report

    def draw_summaries(self, res, frames_out):
        """For each rendered frame: draw calls per addon texture name (sweep frames and glyphs folded) and world."""
        out = {}
        for _, fno, _, _ in frames_out:
            agg = {}
            for slot, r in res.draws.get(fno, []):
                if r[0] == 'rect':
                    name = 'rect'
                else:
                    name = self.tex_names.get(r[7] or '', r[7] or '?')
                    name = re.sub(r'\[\d+\]$', '', name)
                    name = re.sub(r'^glyph\d:.*', 'glyph', name)
                key = ('top:' if slot else '') + name
                agg[key] = agg.get(key, 0) + 1
            out[str(fno)] = dict(sorted(agg.items()))
        return out

    def lua_type(self, v):
        return self.L.globals().type(v)

    @staticmethod
    def read_text(p):
        try:
            with open(p, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except OSError:
            return ''
