"""Scenarios: what happens in a simulated session, on a timeline in seconds.

A scenario is a Python file in scenarios/ with a `build(s)` function that calls the methods below on `s`, or a JSON
file whose keys are those method names (see README.md). Times are seconds since the game started (the loader's clock).
Coordinates are meters: x east, y north, z up. Yaw is degrees clockwise from north, pitch degrees up.

    def build(s):
        s.screen(2560, 1440)
        s.run(seconds=20, fps=30)
        s.world('mission', at=0, filler=6000)
        s.camera(0, x=0, y=0, z=1.6, yaw=0, pitch=-5)
        s.unit('medal', 30, 40, 0, pickup_at=12)
        s.press('f8', at=9)
        s.map_open(14, 16)
"""
import json
import math
import os


class Scenario:
    def __init__(self, name):
        self.name = name
        self.w, self.h = 1920, 1080
        self.seconds, self.fps = 10.0, 30
        self.worlds = []            # dicts: name, at, until, filler, spread, seed, main, map
        self.units = []             # dicts: kind, variant, x, y, z, world, spawn_at, pickup_at, remove_after, label
        self.cam_keys = []          # (t, x, y, z, yaw, pitch, fov)
        self.events = []            # (t, kind, data): resize, cursor, wheel, raw
        self.keys = []              # (t0, t1, name): a key held over [t0, t1)
        self.mouse = []             # (t0, t1, button)
        self.hud_settings = {'hud_offset': 1, 'hud_scale': 0.85, 'hud_map_position': 0, 'hud_curve': 0}
        self.peer = '1100001a2b3c4d5'
        self.frames = []            # default frames to render (frame numbers, or times like '5s')
        self.capture = []           # frames whose draw calls are kept (for checks) even when not rendered
        self.extra_kinds = {}       # name -> {'units': [...], ...}
        self.extra_textures = []    # texture ids Application.can_get reports loaded besides the archives' own
        self.strict_units = 'crash'
        self.fragile_kinds = {}     # kind -> [engine calls that crash the game on that kind's units]
        self.files = {}             # extra files in the run folder: path relative to it -> text
        self.truth = True           # draw the scenario's units in the background (gray stakes)
        self.checks = []            # (description, function(result) -> bool or (bool, detail))
        self.extra_lua = []         # (hex id, source): Lua resources in one extra patch file after the options'
        self.notes = ''

    # ---------------------------------------------------------------- setup
    def screen(self, w, h, at=None):
        """The back buffer size (at=None: from the start; at=t: a resize mid-run)."""
        if at is None:
            self.w, self.h = int(w), int(h)
        else:
            self.events.append((float(at), 'resize', (int(w), int(h))))
        return self

    def run(self, seconds=None, fps=None):
        if seconds is not None:
            self.seconds = float(seconds)
        if fps is not None:
            self.fps = int(fps)
        return self

    def hud(self, **kw):
        """HUD settings in the player's settings file: hud_offset, hud_scale, hud_map_position, hud_curve (the
        names may be given without the hud_ prefix). None leaves the key out of the file."""
        for k, v in kw.items():
            self.hud_settings[k if k.startswith('hud_') else 'hud_' + k] = v
        return self

    def player(self, peer_id):
        """What Network.peer_id() returns (and so the settings file's name)."""
        self.peer = str(peer_id)
        return self

    def render_frames(self, *frames):
        """Default frames to render: frame numbers, or times as strings like '4.5s'."""
        self.frames = list(frames)
        return self

    def capture_frames(self, *frames):
        """Frames whose draw calls are kept for checks without rendering them."""
        self.capture = list(frames)
        return self

    def kind(self, name, units, **info):
        """A unit kind of the scenario's own (e.g. a structure): one id or a list of ids."""
        self.extra_kinds[name] = dict(info, units=[units] if isinstance(units, str) else list(units))
        return self

    def texture_loaded(self, *hexes):
        """Texture ids Application.can_get('texture', ...) says are loaded although no enabled archive has them
        (they draw as magenta boxes)."""
        self.extra_textures.extend(h.lower() for h in hexes)
        return self

    def file(self, relpath, text):
        """An extra file in the run folder before the run, e.g. ('LocalAppData/treasure_radar_zoom.txt', '75 150')."""
        self.files[relpath] = text
        return self

    def lua_resource(self, source, res_id=None):
        """An extra Lua resource (e.g. an addon or options file of a mod under test), shipped in one extra patch file
        that comes after the options' archives (as if one more option were ticked)."""
        res_id = res_id or '%016x' % (0x7e57000000000000 + len(self.extra_lua) + 1)
        self.extra_lua.append((res_id, source))
        return self

    def options_file(self, mod='mods/chef/treasure_radar', **values):
        """An extra options file for a mod: options_file(calibrate=True) is an "-- HD2-Options:" resource that
        returns { calibrate = true }, merged by the loader with the ticked options' own."""
        def lua(v):
            if isinstance(v, bool):
                return 'true' if v else 'false'
            if isinstance(v, (int, float)):
                return repr(v)
            if isinstance(v, dict):
                return '{ ' + ', '.join('[%s] = %s' % (lua(k), lua(x)) for k, x in v.items()) + ' }'
            if isinstance(v, (list, tuple)):
                return '{ ' + ', '.join(lua(x) for x in v) + ' }'
            return '"%s"' % str(v).replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"')
        body = ', '.join('%s = %s' % (k, lua(v)) for k, v in values.items())
        return self.lua_resource('-- HD2-Options: %s\n-- (written by the test harness)\nreturn { %s }\n' % (mod, body))

    def units_strict(self, mode):
        """'crash' (default): Unit.world_position / Unit.camera / Camera.* on a picked-up or removed unit abort the
        run like the game would; 'warn': they only warn."""
        self.strict_units = mode
        return self

    def fragile(self, kind, *calls):
        """Units of this kind (a name, or a raw hex id) crash the game on these engine calls, alive or not, like
        Unit.world_position on a ship unit did. By default Unit.world_position; Unit.num_cameras can be named too."""
        self.fragile_kinds[kind] = list(calls) or ['Unit.world_position']
        return self

    # ---------------------------------------------------------------- the world
    def world(self, name, at=0.0, until=None, filler=0, spread=400.0, seed=1, main=True):
        """A world. main=True: it becomes the main world at `at` (the previous main world is destroyed then; until:
        when it goes away with no main world after it). main=False: an extra world (listed after the main one) from
        `at` to `until`. `filler` units of random ids (none of them a known kind) are scattered within `spread` m."""
        self.worlds.append({'name': name, 'at': float(at), 'until': None if until is None else float(until),
                            'filler': int(filler), 'spread': float(spread), 'seed': int(seed), 'main': bool(main),
                            'map': False})
        return self

    def map_open(self, t0, t1, press=True):
        """The game's map open from t0 to t1: a second world exists meanwhile (drawing at layer >= 2000 lands
        there), and the renderer shows a map stand-in at the bottom right. press: Tab (the Map key) is tapped at t0
        and t1 too, as the player opens and closes it (0.7 goes by the key: the game keeps other worlds all along)."""
        self.worlds.append({'name': 'map@%g' % t0, 'at': float(t0), 'until': float(t1), 'filler': 0, 'spread': 0.0,
                            'seed': 0, 'main': False, 'map': True})
        if press:
            self.hold('tab', t0, 0.05)
            self.hold('tab', t1, 0.05)
        return self

    def unit(self, kind, x, y, z=0.0, variant=0, world=None, spawn_at=None, pickup_at=None, remove_after=0.3,
             label=None):
        """A unit of a kind (a name from kinds.py or the scenario's own, or a raw hex id) at x, y, z. variant: which
        of the kind's ids. spawn_at: it appears then. pickup_at: picked up then (Unit.alive turns false) and removed
        from the world `remove_after` seconds later (None: never removed)."""
        self.units.append({'kind': kind, 'variant': int(variant), 'x': float(x), 'y': float(y), 'z': float(z),
                           'world': world, 'spawn_at': spawn_at, 'pickup_at': pickup_at,
                           'remove_after': remove_after, 'label': label})
        return self

    def ring(self, kind, n, radius, cx=0.0, cy=0.0, z=0.0, start=0.0, **kw):
        """n units of a kind on a circle around (cx, cy), the first at bearing `start` degrees."""
        for i in range(n):
            a = math.radians(start + 360.0 * i / n)
            self.unit(kind, cx + radius * math.sin(a), cy + radius * math.cos(a), z, variant=i, **kw)
        return self

    def camera(self, t, x, y, z=1.6, yaw=0.0, pitch=0.0, fov=None):
        """A camera keyframe (linear in between; yaw takes the short way round). fov: vertical, degrees (50 when
        never given)."""
        self.cam_keys.append((float(t), float(x), float(y), float(z), float(yaw), float(pitch),
                              None if fov is None else float(fov)))
        self.cam_keys.sort(key=lambda k: k[0])
        return self

    # ---------------------------------------------------------------- input
    def hold(self, key, at, seconds):
        """A key held down from `at` for `seconds` (names: 'f7', 'f8', 'tab', 'numpad +', 'numpad -', letters...)."""
        self.keys.append((float(at), float(at) + float(seconds), key))
        return self

    def press(self, key, at):
        """A tap: down for 2 frames."""
        self.keys.append((float(at), float(at) + 2.0 / self.fps - 1e-6, key))
        return self

    def cursor(self, at, x, y):
        """The mouse cursor (window pixels, as the engine gives them) from `at` on."""
        self.events.append((float(at), 'cursor', (float(x), float(y))))
        return self

    def mouse_hold(self, button, at, seconds):
        """A mouse button ('left', 'right', 'middle') held from `at` for `seconds`."""
        self.mouse.append((float(at), float(at) + float(seconds), button))
        return self

    def click(self, button, at):
        self.mouse.append((float(at), float(at) + 2.0 / self.fps - 1e-6, button))
        return self

    def wheel(self, at, delta):
        """The mouse wheel turned by `delta` for one frame."""
        self.events.append((float(at), 'wheel', float(delta)))
        return self

    def raw_mouse(self, t0, t1, dx, dy=0.0):
        """Raw mouse movement (Mouse.axis of 'mouse'): dx, dy counts every frame from t0 to t1. The camera doesn't
        follow by itself: give it keyframes that turn with the mouse (the map closed) or none (the map open)."""
        self.events.append((float(t0), 'raw', (float(t1), float(dx), float(dy))))
        return self

    # ---------------------------------------------------------------- checks
    def check(self, description, fn):
        """A check run after the run: fn(result) -> bool or (bool, detail). See runner.Result."""
        self.checks.append((description, fn))
        return self

    # ---------------------------------------------------------------- timeline helpers (used by the runner)
    def frame_of(self, spec):
        if isinstance(spec, str):
            spec = spec.strip()
            if spec.endswith('s'):
                return max(1, int(round(float(spec[:-1]) * self.fps)))
            return int(spec)
        return int(spec)

    def total_frames(self):
        return int(round(self.seconds * self.fps))

    def camera_at(self, t):
        """(x, y, z, yaw, pitch, fov or None) at time t."""
        ks = self.cam_keys
        if not ks:
            return (0.0, 0.0, 1.6, 0.0, 0.0, None)
        if t <= ks[0][0]:
            return ks[0][1:]
        for a, b in zip(ks, ks[1:]):
            if a[0] <= t <= b[0]:
                f = 0.0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
                dyaw = ((b[4] - a[4] + 180.0) % 360.0) - 180.0
                if a[6] is None or b[6] is None:
                    fov = a[6] if b[6] is None else b[6]
                else:
                    fov = a[6] + (b[6] - a[6]) * f
                return (a[1] + (b[1] - a[1]) * f, a[2] + (b[2] - a[2]) * f, a[3] + (b[3] - a[3]) * f,
                        a[4] + dyaw * f, a[5] + (b[5] - a[5]) * f, fov)
        return ks[-1][1:]

    def keys_at(self, t):
        return sorted({k for (t0, t1, k) in self.keys if t0 <= t < t1})

    def mouse_at(self, t):
        return sorted({b for (t0, t1, b) in self.mouse if t0 <= t < t1})

    def map_open_at(self, t):
        return any(w['map'] and w['at'] <= t < (w['until'] if w['until'] is not None else 1e18) for w in self.worlds)

    def settings_text(self):
        # "key = value" lines; the addon finds a key after a line break, so a key is never the first line
        lines = ['-- user settings (written by the Treasure Radar test harness)']
        for k, v in self.hud_settings.items():
            if v is not None:
                lines.append('%s = %s' % (k, v))
        return '\n'.join(lines) + '\n'


def load(name_or_path, scenarios_dir):
    """A Scenario from scenarios/<name>.py / .json, or a path to one."""
    path = name_or_path
    if not os.path.exists(path):
        for ext in ('.py', '.json'):
            p = os.path.join(scenarios_dir, name_or_path + ext)
            if os.path.exists(p):
                path = p
                break
    if not os.path.exists(path):
        have = sorted(os.path.splitext(f)[0] for f in os.listdir(scenarios_dir)
                      if f.endswith(('.py', '.json')) and not f.startswith('_'))
        raise SystemExit('no scenario %r (have: %s)' % (name_or_path, ', '.join(have)))
    name = os.path.splitext(os.path.basename(path))[0]
    s = Scenario(name)
    if path.endswith('.json'):
        with open(path, 'r', encoding='utf-8') as f:
            apply_json(s, json.load(f))
    else:
        ns = {'__file__': path, '__name__': 'scenario_' + name}
        with open(path, 'r', encoding='utf-8') as f:
            code = compile(f.read(), path, 'exec')
        exec(code, ns)
        if 'build' not in ns:
            raise SystemExit('%s has no build(s) function' % path)
        ns['build'](s)
    return s


JSON_KEYS = ('screen', 'run', 'hud', 'player', 'render_frames', 'capture_frames', 'kind', 'texture_loaded', 'file',
             'lua_resource', 'options_file',
             'units_strict', 'fragile', 'world', 'map_open', 'unit', 'ring', 'camera', 'hold', 'press', 'cursor',
             'mouse_hold', 'click', 'wheel')


def apply_json(s, spec):
    """JSON scenarios: each key is a Scenario method. A list of objects / lists calls it once per item; an object
    passes keyword arguments, a list positional ones; anything else is the one argument. "notes" is free text."""
    for key, val in spec.items():
        if key in ('notes', 'comment'):
            s.notes = str(val)
            continue
        if key not in JSON_KEYS:
            raise SystemExit('scenario JSON: unknown key %r (known: %s)' % (key, ', '.join(JSON_KEYS)))
        fn = getattr(s, key)
        if isinstance(val, list) and val and all(isinstance(v, (dict, list)) for v in val):
            items = val
        else:
            items = [val]
        for it in items:
            if isinstance(it, dict):
                fn(**it)
            elif isinstance(it, list):
                fn(*it)
            else:
                fn(it)
