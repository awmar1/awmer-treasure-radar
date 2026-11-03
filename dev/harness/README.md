# Treasure Radar test harness

Runs a Treasure Radar build's **real Lua** offline: the game's boot script (Chef Loader inside it) and the addons,
straight out of the option folders' patch archives, in a real Lua 5.1 (lupa), against a fake Stingray engine. A
scenario scripts a session (worlds, loot, pickups, camera, keys, the map), every frame runs `update(dt)` / `render()`
like the game would, and what the mod drew is rendered to PNGs with Pillow.

Nothing in the mod folder is written: the archives are copied into `out/<scenario>/_run/data/`.

## Run it

From the mod folder (Git Bash or PowerShell; forward slashes work in both):

    python -I dev/harness/run.py --mod . --options core,ledger,loot,markers_50 --scenario mission
    python -I dev/harness/run.py --mod . --options core,ledger,loot --scenario map_top
    python -I dev/harness/run.py --mod . --options core,ledger,loot --scenario quick --frames 120,240,6.5s
    python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.6.0 --scenario mission06         --options core,ledger,compass,bezel,pings,overlay,markers_50,map_objective,map_side,map_nest,map_structure,loot
    python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.6.0 --scenario tester06         --options core,compass,bezel,pings,map_objective,map_nest,loot,tester
    python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.7.0 --scenario mission07         --options core,loot_all,extras_all,radar_medium,markers_50,opacity_100
    python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.7.0-measure --scenario measure07 --options core
    python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.7.1 --scenario desync07         --options core,loot_all,extras_all,radar_medium,markers_50,opacity_100
    python -I dev/harness/selftest.py          # the harness's own tests (engine edges, crash handling)

Python comes from the system; the libraries (Pillow, lupa with Lua 5.1) come from `dev/tools/_pylib`, which `run.py`
puts on the path itself. Nothing is pip-installed and no `__pycache__` is written.

| flag | |
|---|---|
| `--mod` | the mod folder (the one with `core/`, `ledger/`, ... option folders) |
| `--options` | option folders in load order, comma separated. Groups: `loot` (also `@loot`, `kinds`, `@all-kinds`) = credit, medal, common, rare, super, requisition, ammo, grenade, stim; `samples`; `supply`. In PowerShell quote anything with `@` in it (`"core,@loot"`): unquoted it is a splatting parse error |
| `--scenario` | a name in `dev/harness/scenarios/` (`.py` or `.json`) or a path to one |
| `--frames` | frames to render: numbers and/or times (`120,240,4.5s`); `none` renders nothing. Default: the scenario's own |
| `--seconds` | override the scenario's length |
| `--out` | output folder (default `dev/harness/out/<scenario>`) |
| `--keep-run` | keep the archive copies in `_run/data` (deleted after the run by default, ~20 MB) |
| `--quiet` | no progress lines |

Exit code: **0** ok, **1** the run aborted (engine crash or a Lua error escaping `update`), **2** errors in the
loader's log (frame errors, compile errors, a switched-off addon...) or a failed check.

### Output (`out/<scenario>/`)

- `frame_NNNN.png`: the frames rendered (NNNN = frame number; frame 1 is t = 1/fps).
- `contact.png`: all of them on one sheet, labelled with frame, time and MAP OPEN.
- `run.json`:
  - run status: `ok`, `aborted`, `crash` (frame, time, message, Lua traceback);
  - from the log: `frame_errors`, `addon_errors`, `log_tail`;
  - `events`: worlds, pickups and spawns as they happened;
  - `checks`;
  - `warnings`: engine warnings with count and first frame;
  - `missing_engine_functions`: anything the mod looked up that the fake doesn't have;
  - `unknown_textures`, `prints`;
  - per-frame draw `counts`;
  - `frame_summary`: draws per addon texture name per rendered frame (`top:` = the map's world);
  - `engine_stats`.
- `_run/`: the fake game folder:
  - `LocalAppData/` holds the loader's real log file;
  - `AppData/Roaming/Arrowhead/Helldivers2/saves/<peer>_user_settings.config` holds the settings the addon reads.

The terminal shows the last `started`, `world` and `ledger:` log lines, errors, warnings, missing functions, the checks
and the frames written.

### Shipped scenarios

**`mission`** (2560x1440, 22 s)

- Timeline:
  - a ship world, then a mission world (6000 filler units) with every loot kind;
  - a medal and a credit picked up (10 s, 11 s), a common spawned (12 s);
  - F8 twice, F7 twice, Tab held twice, numpad +;
  - the map open 19.5-21 s.
- 10 checks:
  - the started, mission and ledger log lines, and no frame errors;
  - no radar before the world settles;
  - the medal leaves the radar, the ledger shows the check mark, and `medal 0/1` is logged;
  - F8 hides markers; F7 and Tab hide the radar;
  - nothing in the map world.
- Frames worth a look:
  - `frame_0150`: radar, ledger, markers;
  - `frame_0345`: after the pickups;
  - `frame_0570`: the 100 m zoom;
  - `frame_0600`: the map open.

**`map_top`**: 1920x1080 with `calibrate = true` (an extra options file), and the map opened twice. It checks that
layer 2960 lands in the top world at 1960 while the map is open, and that nothing is left there when it closes.

**`quick.json`**: a short 1080p mission written as JSON, with a scenario-defined kind (`example_structure`).

The scenarios above are for 0.5.1's texture names. These two are for 0.6 builds (textures by path, `T.TEX`):

**`mission06`** (2560x1440, 23 s)

- Timeline:
  - `mission`'s worlds and loot, plus a TCS tower (objective), a medium bug hole (nest), a detector tower (side
    objective) and a fabricator (structure), each a scenario kind with its id from `dev/src/addon/structures.lua`;
  - at 9.8 s numpad 1 sets a waypoint on the medal I'm looking at; picking it up (10 s) clears it;
  - F8 twice, F7 twice, Tab held twice, numpad +, F9 on the TCS tower;
  - the map open 19.5-21.2 s: numpad 9 picks an icon, numpad 1 sets its waypoint, a wheel tick and a click; numpad 3
    clears the waypoints after it closes.
- 17 checks: the loader line (0.6.x), no frame errors, ledger counts, the structures found, nothing at 3 s, `map/*`
  marks on the radar, compass pips, the waypoint shown then cleared (and logged), the medal leaving the radar with the
  ledger's check, pins and F8, F7 and Tab hiding `radar/*`, F9's log line, top-world draws only while the map is open,
  the map waypoint, and numpad 3.
- Frames worth a look:
  - `frame_0285`: radar with objective and structure icons, compass pips, ledger, pins;
  - `frame_0297`: the ping bracket with the ping key, the waypoint over the medal, its toast;
  - `frame_0600`: the map open: the rim band, the overlay, the selection ring and its tooltip.

**`tester06`** (1920x1080, 13 s): the Tester option. The probe loads as a second addon, calibration is on (numpad 5,
8 and 0 with the map open; the save goes into the run folder's `%LOCALAPPDATA%`), and the guessed kinds are on (a
thumper is found next to the TCS tower). F11 asks the probe for a census; F9 stays the mod's and the probe ignores it.
10 checks. `frame_0180` shows the guides on the map's rim.

These three are for 0.7 builds (everything on by default; no Tester, no calibration):

**`mission07`** (2560x1440, 24 s): `mission06`'s worlds, loot and structures, plus two non-main worlds there from the
mission's start, as in the real game, so the world list can't tell the map open and the Map key (Tab) decides.
- Timeline: numpad 1 on the medal (picked up at 10 s) and on a sample ring (12.2 s); F8 and F7 twice; Tab tapped twice
  0.3 s apart; numpad +, F9; the map open 19.5-21.2 s with numpad 9 (nothing), numpad 1 (a toast to close the map and
  aim), a wheel tick and a click; numpad 3 after.
- 22 checks: `mission06`'s (without Tab-hold hiding and map selection), plus: the compass pips on the measured strip
  (from the `compass:` geometry line), key mode confirmed by the worlds there all along, two quick taps leaving the
  map closed, rim marks and the waypoint on the open map with no overlay, numpad 9 selecting nothing, and numpad 1 on
  the open map setting nothing.
- `frame_0600`: the open map's quiet rim: small marks just outside the rim, the waypoint and the nearest distance.

**`desync07`** (1920x1080, 22 s; 0.7.1): the game ignores some Map presses, so the mod's toggle drifts; the mouse sets
it right. Two non-main worlds from the start (key mode). I look around at 7 s (the camera follows `raw_mouse`); Tab at
9 s is ignored by the game (no map), and looking around at 10 s brings the radar back; the map open 13-18 s with a
second Tab at 14 s ignored (the radar draws over it) until the mouse moves at 15 s with the camera still; Esc at 19.5 s,
then the mouse moves with the camera still and opens nothing. 6 checks.

**`measure07`** (1920x1080, 15 s): the measurement build. The ship with kind `46cab355bd8d4d37` made fragile, then a
mission with two worlds there all along. F12 on the ship (nothing), F12 in the mission, Tab opens the map (2 notches
in, 1 out, the cursor moved), F12, Tab closes it, F12. 13 checks: the logger's lines (header, snapshots, zoom notches,
the close line), no engine crash, and the `MEASURE n LOGGED` note in both worlds.

## Write a scenario

A Python file in `scenarios/` with `build(s)`:

```python
def build(s):
    s.screen(2560, 1440).run(seconds=20, fps=30)
    s.hud(scale=1.0, offset=0)                       # the settings file (default offset 1, scale 0.85, map_position 0, curve 0)
    s.world('ship', at=0, filler=3000)
    s.world('mission', at=1.0, filler=6000, spread=450, seed=7)   # becomes the main world; 'ship' is destroyed
    s.unit('medal', 6, 28, pickup_at=10.0)           # alive turns false at 10 s, removed from the world 0.3 s later
    s.ring('common', 3, radius=1.0, cx=30, cy=45)
    s.unit('common', 12, 18, spawn_at=12.0)
    s.camera(0, x=0, y=0, z=1.8, yaw=0, pitch=-5)    # keyframes, linear in between
    s.camera(20, x=10, y=30, z=1.8, yaw=90, pitch=-5)
    s.press('f8', at=12.5); s.hold('tab', at=16.0, seconds=0.8)
    s.map_open(19.5, 21.0)
    s.render_frames('3s', '9.5s', '11.5s', 600)
    s.check('the medal is gone from the radar',
            lambda r: r.count('11.5s', tex='medal', layer=(905, 925)) == 0)
```

Units: meters, x east, y north, z up; yaw degrees clockwise from north, pitch degrees up; times in seconds since the
start. GUI positions in checks are pixels from the bottom left, like the engine's.

**Methods** (all chain):

- Setup:
  - `screen(w, h, at=None)`: the back buffer size; with `at`, a resize mid-run.
  - `run(seconds, fps)`.
  - `hud(**kw)`: settings file keys (`offset`, `scale`, `map_position`, `curve`, with or without `hud_`; `None` leaves a key out).
  - `player(peer_id)`: what `Network.peer_id()` returns, and so the settings file's name.
- Worlds:
  - `world(name, at, until=None, filler=0, spread=400, seed=1, main=True)`. A `main` world replaces the main world at `at`, and the old one is destroyed with its GUIs. `main=False` is an extra world from `at` to `until`.
  - `map_open(t0, t1, press=True)`: a second world while the map is open (the loader's top world), and Tab tapped at `t0` and `t1` as the player opens and closes it (0.7 goes by the Map key: the game keeps other worlds all mission). The renderer draws a map stand-in at the bottom right. For the real game's case, add `world(name, at, main=False)` worlds from the mission's start and open the map with `press('tab', t)` alone.
- Units:
  - `unit(kind, x, y, z=0, variant=0, world=None, spawn_at=None, pickup_at=None, remove_after=0.3, label=None)`. `kind` is a kind name or a raw 16-digit hex id; `variant` picks which of the kind's ids.
  - `ring(kind, n, radius, cx, cy, z, start)`.
- Camera:
  - `camera(t, x, y, z=1.6, yaw=0, pitch=0, fov=None)`: vertical fov, 50 by default.
- Input:
  - `press(key, at)` (2 frames), `hold(key, at, seconds)`. Keys: `f1`..`f12`, `tab`, `numpad +`, `numpad -`, letters, digits, ...
  - `cursor(at, x, y)`, `click(button, at)`, `mouse_hold(button, at, seconds)`, `wheel(at, delta)`.
  - `raw_mouse(t0, t1, dx, dy=0)`: raw mouse counts every frame from `t0` to `t1` (`Mouse.axis` of `'mouse'`, as in the
    game). The camera doesn't follow by itself: give it keyframes that turn with the mouse (the map closed) or none.
- Frames and checks:
  - `render_frames(*frames)`.
  - `capture_frames(*frames)`: keep the draw calls for checks without rendering.
  - `check(description, fn)`: `fn(result)` returns a bool or `(bool, detail)`.
- Extras:
  - `kind(name, ids, **info)`: a kind of the scenario's own, such as a structure or objective. Permanent ones go in `kinds.EXTRA`.
  - `options_file(mod='mods/chef/treasure_radar', **values)`: an extra `-- HD2-Options:` resource, merged by the loader with the ticked options'. For example, `options_file(calibrate=True)`.
  - `lua_resource(source, res_id=None)`: any extra Lua resource, such as an addon under test. Both of these ship in one more patch file after the options' archives.
  - `texture_loaded(*hexes)`: textures `Application.can_get` reports loaded although no archive has them. They draw magenta.
  - `file(relpath, text)`: an extra file in the run folder, e.g. `('LocalAppData/x.txt', '...')`.
  - `units_strict('crash' | 'warn')`: see the engine section.
  - `fragile(kind, *calls)`: units of this kind (a name or a raw id) crash the game on these calls (`Unit.world_position`
    by default; `Unit.num_cameras` can be named too). One kind on the ship did that to `Unit.world_position`.

**JSON scenarios**: each key is a method name. An object passes keyword arguments, a list passes positional ones, and a
list of objects or lists calls the method once per item. `notes` is free text. JSON has no checks; the generic ones
(log errors, crashes) still decide the exit code. See `scenarios/quick.json`.

**Kinds**: the loot kinds and their unit ids are parsed from the addon's own `local KINDS = {...}`, so a build that
adds or renames kinds needs no harness change (`kinds.LOOT` is the 0.5.1 fallback). The addon's
`TEXTURES.x = '<hex>'` and `GLYPHS` lines give texture names (`medal`, `sweep[3]`, `glyph2:5`) for checks and
`frame_summary`.

**The Result API** (`runner.Result`, what checks get):

- `r.log_has(regex)`, `r.log_lines(regex)`: the loader's log file.
- `r.draws_of(frame, tex=None, world=None, layer=None, kind=None)`: the draw calls of a captured frame.
  - Filters:
    - `frame` is a number or `'10.5s'`;
    - `tex` is an addon texture name, or a hex id. 0.5.1 names match as a prefix up to an index (`sweep` matches
      `sweep[3]`; `medal` only `medal`). 0.6 names are paths (`icons/medal`); one ending in `/` matches every texture
      under it (`radar/` matches `radar/sweep/03`);
    - `world` is `'main'` or `'top'`;
    - `layer` is an inclusive `(lo, hi)` range;
    - `kind` is `'rect'` or `'bitmap'`.
  - Each record is `(slot, (kind, layer, x, y, w, h, (a, r, g, b), tex, order, gui id, world name))`.
- `r.count(frame, **same filters)`.
  - Both return `None` for a frame that wasn't captured.
  - The scenario's `render_frames` are always captured, even when `--frames` renders others.
- `r.counts[frame]`: per-frame totals (`main_rect`, `main_bitmap`, `top_bitmap`, `lines`...).
- `r.frames_t`, `r.tex_names`, `r.crashed`.

0.5.1 layer bands for checks:

| what | layers |
|---|---|
| world markers | 870-889 |
| radar | 890-950 (icons 905-925) |
| ledger | 900-920 |
| top world | the draw's layer - 1000, e.g. calibration 2960 -> 1960 |

## The fake engine (`engine.lua`)

Installed as the global `stingray`; `engine.lua` returns `E`, the control table the runner uses. Emulated:

- `Application`:
  - `main_world`;
  - `worlds`: the main world first, then the others (the open map is the "top" world);
  - `back_buffer_size`;
  - `can_get('texture'|'material', id)`: true for every texture in the enabled archives and the UI material `e2d6ed90906c1e8b`.
- `World`:
  - `time`, `num_units`;
  - `units`: a fresh table each call; the camera unit is one of them;
  - `create_screen_gui`, `destroy_gui`, `create_line_object`.
- `Unit`:
  - `alive`;
  - `debug_name`: `#ID[<16-digit hex of the unit's resource id>]`;
  - `world_position`, `num_cameras`, `camera`.
- `Camera`:
  - `world_position`, `world_rotation`, `vertical_fov`;
  - `world_to_screen`: pixels from the bottom left; z is depth, negative behind. This is the same math as the renderer, checked by the selftest.
- `Gui`: `rect`, `bitmap`, `material`; `Material.set_texture`. Every draw is recorded with world, GUI, layer (pos.z),
  position, size, color and texture.
- `LineObject`: `reset`, `add_line`, `dispatch`.
- Value types:
  - `Vector3`, `Vector2`;
  - `Color`: `(a, r, g, b)` or `(r, g, b)`;
  - `Quaternion`: `forward`, `right`, `up`, `to_elements`;
  - `IdString64`: `from_hex`, `to_hex`.
- Input:
  - `Keyboard`: `button_index`, `button_name`, `button`, `pressed`, `released`;
  - `Mouse`: `axis_index`, `axis`, `button_index`, `button`, `pressed`;
  - `Network.peer_id`.
- Handles (worlds, units, GUIs, cameras, materials, line objects) are opaque userdata, like the engine's.
- `io` and `os` are the real ones, except:
  - relative paths resolve against the run folder;
  - `os.getenv('LOCALAPPDATA')` and `os.getenv('APPDATA')` point into `_run/`;
  - `os.exit` raises an error;
  - `print` is captured into `run.json` `prints`.

**Sharp edges** (where the real game punishes mistakes):

- **Unknown functions are nil.** `stingray.Gui.text` is `nil`, as a missing engine function would be. Every lookup of
  a missing name is listed in `missing_engine_functions`.
- **A stale value.** Vector3, Vector2, Color, Quaternion and IdString64 are one-frame temporaries. Using one made in an
  earlier frame is listed in `warnings`. A stale Color also **draws white**.
- **A GUI used after its world went away is a fatal crash.** The same goes for a GUI after `World.destroy_gui`, a GUI
  destroyed twice, or one destroyed through another world, and for line objects. The run **aborts** at once, every
  later engine call fails, and the crash is recorded with its Lua traceback; the frame is still rendered.
- **Dead units.**
  - `Unit.world_position`, `Unit.camera` and `Camera.*` on a picked-up (dead) or removed unit are fatal too
    (`units_strict('warn')` turns that into a warning).
  - `Unit.alive` is false for those.
  - `Unit.debug_name` and `Unit.num_cameras` on a removed unit warn and still answer (stale handle).
- **Fragile kinds.** A call that a scenario's `fragile(...)` names is fatal on any unit of that kind, alive or not.
  Which kinds the real game crashes on is mostly unknown; one ship kind crashed on `Unit.world_position`.
- **Timing.**
  - A world destroyed takes its units and GUIs with it.
  - A pickup turns `alive` false at once and leaves `World.units` `remove_after` seconds later.
  - Filler units (random ids, none a known kind) make the loader's unit scan as long as in a real mission.

## What it does not emulate

- **The game itself**: the map's real rendering (the renderer shows a flat stand-in rectangle), the HUD, terrain,
  occlusion, physics, AI, missions ending, the ship, other players.
- **Real stale-handle behaviour.** What the engine does with a removed unit's handle is unknown; the harness picks
  "crash" for position and camera calls and "warn and answer" for names.
- **Engine API beyond the list above**:
  - no `Gui.text` or fonts (the addon draws text with its own glyph textures, which the harness renders from the archives);
  - no materials but the UI one;
  - no `World.spawn_unit`, `Script`, `Level`, `Physics` or audio.

  Anything else a build calls shows up as missing and fails like a nil call in game.
- **Textures and timing**:
  - Textures are decoded only as R8G8B8A8 or B8G8R8A8 with one mip, the format the build writes; others draw magenta.
  - Blending is plain alpha over the background, tinted by the draw colour, with no sRGB or HDR handling.
  - Fixed frame time (1/fps). There is no real-time clock pressure, so a slow frame never shows.
- **Input and screen**: key repeat, a gamepad, focus changes, and the cursor locked during gameplay. A screen resize
  only changes `back_buffer_size`.
- **Approximations**: the camera is a plain pinhole with z up and no lens distortion. World positions of map pings and
  objectives aren't modelled (add them as kinds once known).

## Files

| file | |
|---|---|
| `run.py` | the CLI |
| `runner.py` | lays out the run folder, starts Lua, runs the timeline, writes `run.json`; `Result` for checks |
| `engine.lua` | the fake `stingray` |
| `scenario.py` | the scenario API and the JSON loader |
| `kinds.py` | unit kinds (parsed from the addon, `LOOT` fallback, `EXTRA`), texture names (0.5.1's `TEXTURES` / `GLYPHS`, 0.6's `T.TEX`) |
| `archive.py` | a minimal patch-archive reader (TOC, Lua sources, R8G8B8A8 textures) and `write_lua_patch` |
| `render.py` | frames and the contact sheet |
| `selftest.py` | tests of the harness itself |
| `scenarios/` | `mission.py`, `map_top.py`, `quick.json`; for 0.6 builds `mission06.py`, `tester06.py`, `ship06.py`, `probe_mission06.py`; for 0.7 builds `mission07.py`, `measure07.py`, `desync07.py` |

## Findings from the 0.5.1 runs

- **Stale handle in the loader.** The loader's unit scan spans frames, and it calls `Unit.debug_name` on a unit
  removed meanwhile (warned once in `mission`, frame ~310). It works here; what the real engine does is unknown.
- **Calibration label overflow.** With `calibrate = true` at 1920x1080, the calibration label runs past the right edge
  (`out/map_top/frame_0180.png`).
- **Ledger beside the map.** With the map open, the ledger pills show to the left of the map area
  (`out/mission/frame_0600.png`); in game the real map covers a different area than the stand-in.
