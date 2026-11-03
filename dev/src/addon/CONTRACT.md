# Treasure Radar 0.9 addon: module contract

The addon is one Lua resource bundled from the module files listed in `modules.txt` (by `dev/tools/bundle.py`).
Game Lua is PUC-Rio **Lua 5.1.4**: no `goto`, no `//`, no bit ops, no integer division, no `table.unpack`
(use `unpack`), no `#!`. `math.atan2` exists. Every module must load under lupa's `lua51`.

## Module files

Each module file starts with `local T, chef = ...` and returns a table (or nil). The bundle wraps it as
`T.mod['<name>'] = (function(...) <file> end)(T, chef)` in `modules.txt` order, so a module can read `T.mod.x` at load
time only if `x` comes earlier; at run time (inside functions) any module can be read. Missing modules are
nil: always guard with `local m = T.mod.x; if m then ... end` when calling into a module owned by someone else.

Shared values:

| Name | What |
|---|---|
| `T.chef` | the loader's API (see below), also passed as `chef` |
| `T.version` | version string |
| `T.TEX[name]` | texture resource id (16 hex) for every PNG under `dev/src/textures/` (name = path without `.png`, e.g. `icons/medal`). Use `T.mod.draw.tex(name, ...)`, never ids. |
| `T.mod.config` | options and the shared palette (`config.lua`) |
| `T.mod.kinds` | every kind the mod knows: loot, supplies, objectives, structures (`kinds.lua`) |
| `T.mod.draw` | drawing helpers (`draw.lua`) |
| `T.mod.hud` | game HUD settings and geometry (`hud.lua`) |
| `T.mod.track` | loot piles and counts (`track.lua`) |
| `T.mod.view` | the open map's model: the level, V, the clusters, the companion hook (see "0.9" below) |
| `T.mod.main` | the frame loop; it is what the addon returns to the loader |

## Life cycle

`main` calls, for each module in `main.PIPE` that exists (in that order):

- `M.init()` once, after all modules loaded.
- `M.reset(S)` at the start of every mission (a new world).
- `M.update(S)` every frame in a mission (logic, input). Even when hidden.
- `M.draw(S)` every frame in a mission, after every `update`. Each module decides itself whether it draws
  (options, `S.hidden`, `S.map_open`).
- `M.idle(S)` every frame outside a mission, once a mission was seen (pause watches here).
- `M.blind(S)` (0.8.2) instead of `update` and `draw` on a frame in a mission without a camera (`S` isn't refreshed):
  mapview keeps that frame's wheel, raw mouse counts and presses for the next full frame.
- `M.shutdown()`.

`main.PIPE` order: `hud, mapview, track, objectives, pings, view, markers, radar, compass, legend, overlay`
(0.8: `view` is new; `ledger` became `legend`; `bezel` is retired, see `dev/src/retired/`. 0.9: `measure` is retired.
0.9.1: `camprobe`, 0.9.0's one-build camera probe, is gone: it found a static camera and nothing that follows the map,
RESEARCH_MAP.md section 4.
0.9.2: lineprobe added after view, an experiment: a line object of its own in each of the engine's other worlds and a
3 m control circle through `chef.line`, every frame in a mission, plus its log lines; no unit or camera calls, no
rects, text or bitmaps. A world keeps its line object and radius while it stays listed; one that leaves the list is
forgotten untouched (`World.destroy_line_object` is never called), so the open map's world, which comes and goes with
every open, costs one line object per open. It switches itself off on a missing function it needs, 10 errors or 500
line objects made. To be removed once the mission's screenshots are read.
0.9.3: lineprobe is retired (the line-object route is closed, RESEARCH_MAP.md): `dev/src/retired/lineprobe-0.9.2.lua`.)

## The frame state `S` (one table, reused every frame; read-only for everyone but main and mapview)

| Field | What |
|---|---|
| `S.t`, `S.dt`, `S.frame` | loader time (s), frame delta, frame number |
| `S.w`, `S.h` | screen size in pixels. Screen GUI origin is **bottom-left**, +y up |
| `S.px` | UI unit: `max(1, floor(h/540 + 0.5))` (2 at 1080p, 3 at 1440p, 4 at 4K) |
| `S.cam` | `chef.camera()`: `{x, y, z, fx, fy, fz, yaw, fov}` (world: +x east, +y north, +z up) |
| `S.me` | `{x, y, z}` my feet (`cam.z - 1.6`) |
| `S.fx`, `S.fy` | my view direction on the ground, unit length (north = 0, 1) |
| `S.heading` | radians, 0 = north, clockwise (`atan2(fx, fy)`) |
| `S.hidden` | F7: the player hid the mod's HUD (radar, legend, compass, overlay; world markers too since 0.8) |
| `S.map_open` | the game's map is open (set by `mapview.update`; false if mapview is missing) |
| `S.map` | `{cx, cy, r}`: where the game's map circle is on screen and its rim radius (from `hud`) |
| `S.opacity` | panel opacity 0..1 (option, or the game's HUD background opacity) |
| `S.markers_on` | always true since 0.8 (F8 is gone) |
| `S.need_loot` | something on screen uses the loot lists (main: options, `S.hidden`, `pings.wants_loot()`) |

## Marks (what the draw modules draw)

Loot piles from `track` and structures from `objectives` share one shape, so radar, compass, bezel, overlay and
markers can treat them the same way:

```lua
mark = {
  kind = k,          -- a kind record from T.mod.kinds
  x = 0, y = 0, z = 0,
  n = 1,             -- how many are still there (0 = gone; it then fades out for config.FADE s)
  gone_t = nil,      -- S.t when n hit 0 (draw with alpha = 1 - (S.t - gone_t) / FADE, skip when <= 0)
  state = nil,       -- structures only: 'active' | 'done' | 'unknown' (a done mark keeps n = 0 and stays drawn, dimmed)
  label = nil,       -- structures only: the text to show (e.g. MEDIUM NEST); views show mark.label or mark.kind.label
  units = { ... },   -- the units behind it (engine handles; only valid in this world)
}
```

- `track.stacks`: loot piles for the map-like views (pickups of a kind within `kind.stack` m in 2D share one).
- `track.pickups`: loot piles for world markers and waypoints (within 2 m in 3D).
- `track.left(kind)`, `track.seen(kind)`: how many are left / the most seen at once this mission.
- `track.near(kind_or_nil, x, y, z, radius)`: the closest pickup pile (for re-linking a waypoint after a rescan).
- `track.alpha(mark, t)`: 1 while there, fading to 0 over `config.FADE` once gone, nil once faded (skip it).
- `track.stale`: true right after the list resumed from a pause, until the fresh list is in (draw no loot then).
- `T.mod.objectives.marks`: structure/objective marks, same shape plus `state` and `label`, least important first.
  Done marks: tint `config.RGB.dim` and draw `objectives.done_tex(mark)` small over the icon. Also
  `objectives.wants(S)`, `set_state(mark, state)`, `nearest(x, y, radius)`; F9 (`config.KEYS.done`) marks the one in view done.
- `track.watch`: track's loot list (objectives lines its own slower list up with it).

## Map, pings and overlay

- `T.mod.mapview`: `top_now` (a second world this frame), `mode` ('list' | 'key'), `proven`, `notches`,
  `notches_mission` (mouse wheel since the map opened / this mission), `panned`, `t_open`, `opens`, `cursor()`
  (bottom-left origin, or nil), `binds` (the player's Map and ping bindings, read-only, defaults if unread).
  0.8.2 (the mouse evidence and the presses, for view.lua): `cold`, `fixes` (opens taken back), `follows` (the camera
  followed the mouse: the game's map is closed), `stills` (a move ended with the camera still: it's open), `doubts`
  (Esc, a frame gap, a camera jump), `notches_shut` (the wheel while the mod thinks the map is closed), `wheel_frame`
  (this frame's notches, any state, blind frames' too), `t_press`, `press_open` (the last Map press: when, and whether
  it opened the toggle), `mouse()` (this frame's raw counts plus the blind frames'), `pressed(bind)` (a mouse button
  pressed in the blind frames counts in the next full frame), `note(t, fmt, ...)` (chef.log, at most 20 lines a second), `blind(S)`. No mouse evidence
  counts within 0.5 s of a Map press (the open/close animation). 0.8.3: a FOLLOW needs, at all times, at least
  max(0.015, a fifth of the learned) degrees per count (slower: the camera drifting, logged as a slow turn, the run
  restarts); for view.lua's take-back, `stills_press` (stills since the last Map press) and `follow_since` (s from
  that press to the last FOLLOW, or nil).
- `T.mod.pings`: `aimed` (the mark nearest my crosshair, map closed), `waypoints` (up to 3,
  `{ x, y, z, label, kind, mark }`), `icon(cx, cy, size, alpha, layer)` (the waypoint glyph), `pinged(mark)`,
  `wants_loot()`, `keys`. Views draw each waypoint with `pings.icon`.
- mapview also gives `read_file(path)` and `getenv(name)` (view.lua's companion hook reads the fix through them).
- `T.mod.overlay`: `update(S)`, `draw(S)` only (0.8: no `cal` or `scale()`; the model is `T.mod.view`).
- `T.mod.pings` also has `P.toggle(S, mark, src)` (the same as Numpad 1 on that mark; 0.9 has no caller on the map).
- Keys (`config.KEYS`, keyboard only): `wp_set` numpad 1 sets or clears a waypoint on the aimed mark, `wp_clear`
  numpad 3 clears them all. 0.7 dropped the map selection (numpad 7 / 9): the game's map cursor can't be read. The mod
  never presses a key or pings: the ping is the game's own (the player's CommunicationSpot bind, Q by default).

## Kinds

```lua
kind = {
  id = 'medal', label = 'MEDAL', cat = 'loot' | 'supply' | 'objective' | 'side_objective' | 'structure' | 'nest' | 'poi' | 'extract',
  rgb = { r, g, b }, tex = 'icons/medal', icon = 'star' (fallback sprite), stack = 2, rank = 1,
  supply = true|nil, units = { '<16 hex>', ... }, on = true|false (its Arsenal option),
}
```

`kinds.loot` (loot and supplies, ledger order), `kinds.map` (objectives/structures/POI, from `structures.lua`),
`kinds.by_unit[hex]`, `kinds.by_id[id]`.

## Drawing helpers (`T.mod.draw`, call it `D`)

- `D.color(r, g, b, a)`, `D.rgb(rgb, a)`: engine colors (one-frame temporaries: make them every frame, never keep).
- `D.A(a)`: alpha scaled by panel opacity (panels only; icons and text stay solid).
- `D.tex(name, x, y, w, h, c, layer)` -> bool: a texture by name, bottom-left corner. False if missing/unusable.
- `D.texc(name, cx, cy, w, h, c, layer)` -> bool: centered.
- `D.rot(prefix, n, angle)` -> texture name of a pre-rotated frame: `prefix .. '/' .. %02d` with frames 01..n
  at clockwise angles `(i-1) * 360/n` degrees from screen-up. (Bitmaps can't rotate: anything that turns ships as
  frames.)
- `D.icon(kind, cx, cy, size, alpha, layer)` -> draws the kind's icon centered (texture, or its fallback sprite).
- `D.text(x, y, str, cap, c, layer, align)` -> width. Glyph textures (`glyphs.lua`), `cap` = cap height in pixels,
  `y` = baseline, `align` = `'l'` (default), `'c'`, `'r'`. Falls back to the loader's pixel font.
- `D.text_w(str, cap)`.
- `D.rect`, `D.dot(cx, cy, size, c, layer)`, `D.dots_ring(cx, cy, r, n, size, c, layer)`.
- 0.6's `D.hit` / `D.hits_prev` (clickable spots on the open map) are gone in 0.7, with the map selection.

## Layers

| Band | Use |
|---|---|
| 860-899 | world markers, waypoint pins (main world, under the open map) |
| 900-949 | radar, ledger (main world, the open map covers them) |
| 950-959 | compass pips (951-958) |
| 960-962 | (0.9.3) the legend with `C.LEGEND = 'always'` while the map is closed: panel, icons, text (main world) |
| 980-999 | toasts/notes |
| `chef.TOP` + 900-919 | bezel: rim marks just outside the open map's rim, no band (top world: over the open map) |
| `chef.TOP` + 920-949 | map overlay (920-929, 940-949) and legend (930-939) |
| `chef.TOP` + 950-974 | (free since 0.7: was the map selection and calibration) |
| `chef.TOP` + 975-979 | toasts on the open map (pings) |

Only draw at `chef.TOP + ...` while `S.map_open` (the loader keeps top-world GUIs only while something draws there).

## Game style (see `config.RGB`)

Cream-white frames and text, color only on loot, thin lines, no glow, flat. Game colors: text `#FFFFED`, rim
`#C9C5AA`, player `#FFE900`, native pings `#71F5FF` (never use for our own marks), objective `#FF8824`.

## Rules

- No engine call except through `chef.*`. Never call `World.unit_by_id`, `UnitComponent.unit`, `Unit.has_mesh`,
  one-argument `Application.can_get`, `Gui.resolution` with an argument.
- Nothing heavy per frame: no table allocation per mark per frame where avoidable; scans go through `chef.watch`.
- Logs: `chef.log(fmt, ...)`, once per change (never per frame).

## 0.9: on the game's map (the look of `dev/docs/mock_0.8_map_detail.png` at -1; `dev/docs/RESEARCH_MAP.md`)

0.8.3's cursor model is retired: the T model and its bounds (`VW.err`, trust, `TRUST`), click anchoring,
`C.OPEN_RULE`, the big map's pin at -3 (`BIG_G0`, `BIG_G1`, `GAIN_MID`), `LATE_FOLLOW`, `MARK_SLACK` / `MARK_HIT`,
`C.HOVER` / `VW.hover` / `VW.cursor` (the hover label and click-to-waypoint), `C.MEASURE`, `C.CURSOR_GAIN` and
`measure.lua`. The old files are in `dev/src/retired/addon-0.8.3/` and `dev/src/retired/sim-0.8.3/`. There is no
calibration, no option for any of this, and no debug UI.

**The levels.** Every map has three zoom levels, and the wheel stops at both ends (wheel up = in).

- A mission starts at 0, and the level lasts across closes all mission.
- -1 shows the whole map, centred on the world origin. 0 and +1 show a window centred on the game's map cursor.
- px per m at 1080p (times `S.h / 1080`; HUD Scale changes none of them):

  | Level | px per m |
  |---|---|
  | -1 | rim / R_map: 0.7805 on a small map (R 285.3 m), 0.554 on a big one (R 401 m) |
  | 0 | 1.4766 |
  | +1 | 2.953 |

- North is up. A world point (x, y) is on screen (bottom-left origin) at `S.map.cx + (x - Vx) * k, S.map.cy + (y - Vy) * k`.
- The game's grid is 65 m, anchored on the origin. `S.map` (hud.lua) is the circle: (1674.0, 260.5), rim 222, at 1920x1080 with HUD Scale 0.9.

**The level is kept as bounds** (`sl0..sl1`), and reaching an end makes it exact. Three things leave it unsure:

- A frame with two or more notches may have zoomed only once: one step for sure, the rest may or may not have happened.
- A notch within 0.25 s of a Map press may or may not have zoomed.
- An open that mapview takes back, or finds late.

Each notch is logged, as is the level becoming known or unknown. The shadow (0.8.2) is kept: while the mod thinks the
map is closed after a Map press, a second level follows the wheel as if it were open.

**The map's class** comes from the census, `World.num_units` on the main world (the K of the loader's
"world N: mission (K units)" line):

- small: 4000..11000;
- big: above 11000, with no upper end (the field saw 25868);
- below 4000 is not measured. Then nothing world-anchored is drawn at -1.

The count is re-read every 0.5 s until it stands still for 5 s (30 s at most), and two loot piles 300-430 m out on an
axis make the map big whatever the count says (from spots track already read: no new engine call).

It is logged once per class, as `map: world N, K units: a small map (...)` or `map: world N: piles beyond 300 m: a big
map (...)`, and once at the end if nothing was measured, as `... the map size is not measured (below 4000) ...`.

A notch within 0.3 s of a step the game took is ignored, by the game and by view.lua. A level still unsure 0.8 s after
the last notch or the open, with -1 inside its bounds, draws at -1 (`VW.level` stays nil; view.lua's header has the
trade).

**What is drawn:**

- **-1:** V is the origin, so the clusters, nest rings and the waypoint chevron are drawn (only when the class is measured).
- **0 / +1:** world-anchored marks appear only with a fresh companion fix or the hold (below). Otherwise only the legend is
  drawn on the open map; the compass stays up in the main world.

Screen-anchored things are unchanged by the level: the radar, the compass, the world markers, pings and toasts.

**The companion hook** (`dev/docs/COMPANION_INTERFACE.md`; view.lua). The mod writes one line to
`%LOCALAPPDATA%\Temp\treasure_radar_mod.txt` (0.9.1: Temp, the one AppData folder the Microsoft Store Python does
not redirect into its package; the folder exists on every Windows, the mod creates nothing):

- when: every frame while the map is open, and once more with `open=0` at the close, the mission's end or shutdown;
- how: `pcall(io.open, path, 'w')`; one write a frame at most;
- logged once per game session, at the first write that succeeds: `companion: mod line -> <mod path>, fix <- <fix
  path>`;
- format (`level=?`, `kz=0` while the level is not known; `class=?` when not measured; `kz=0` too when the class isn't
  measured):

```
seq=N t=S.t open=0|1 level=-1|0|1|? class=small|big|? w=W h=H cx=CX cy=CY rim=R kz=K px=PX py=PY mx=MX my=MY cmx=CMX cmy=CMY end
```

The keys:

- `cy` is `h - S.map.cy`, from the top.
- `kz` is the level's px per m at this resolution.
- `px`, `py` are my feet.
- `mx`, `my` are the raw mouse counts since the previous write, rounded with the fraction carried; `my > 0` is down the
  screen. Counts while the map is closed are not included.
- `cmx`, `cmy` (coordinator addition) are the sum of every write's `mx`, `my` this game session (same signs), so a
  companion that misses lines loses no counts.

It reads `%LOCALAPPDATA%\Temp\treasure_radar_fix.txt` (mapview's `read_file`) every frame while open:

- A line without the final `end` token is a partial write and is ignored; the previous fix stays.
- The file's text at the session's first read is a past session's, and is ignored.
- The first fix parsed in the game session is logged once: `companion: first fix read (seq N)`.

The ring keeps the mod's last 128 writes (`RING`; 0.9.1: 32): seq, t, mx, my, level, my spot. A fix is **fresh** when
all of these hold:

- `how` isn't `none`;
- its `seq` is one of the mod's last 45 writes (`FRESH`; 0.9.1: 15);
- it was written during this open.

It is logged once when it becomes fresh (`companion: fix fresh (...)`) and once when it goes stale
(`companion: fix stale (why; ...)`). With no file at all, the mod is whole-map only.

At 0 / +1 with a fresh fix, V is the fix's `vx, vy` advanced by the mouse counts of the writes after its seq:
`Vx += mx * g`, `Vy -= my * g`, with g per write's level = 0.269 / 0.246 / 0.123 m per count at -1 / 0 / +1. A fix is not
used (logged once per reason, `companion: fix seq N not used (...)`) when any of these hold:

- its seq left the ring;
- it was taken at -1;
- it has no vx, vy;
- (0.9.2) one of the writes after it was at -1 (`the map went to the whole-map level after it`: a zoom in from the
  whole map re-centres the view on the cursor).

0.9.1's distance gate (`SANE`: V further from my spot than the rim's reach plus 10 m) is gone in 0.9.2: long pans put
the view far from the player, and it refused good fixes there.

**The hold rule (0.9.2):** the last V a fix gave in this open is kept with the seq of the write it is current for,
and every later write's mouse counts carry it on (at that write's level's g), with no time limit. While no fresh fix
gives V at 0 / +1, the hold does (`VW.trusted` and `VW.held` true). On each axis the point the counts move stops where
the map cursor stops (the view's stop plus 0.183 h px, RESEARCH_MAP.md section 9), and V is that point clamped to the
view's stop, R_map - rim / k from the origin by the class (at the level of the fix it began from, never inside that
fix's own V). It drops at the map's close (the `open=0` write), at reset and idle, when its writes leave the ring, and
when the level leaves -1 (a zoom in from the whole map); a step between 0 and +1 keeps it. At -1 V is the origin. Two
log lines: `companion: holding V from fix seq N (M writes, D m of pan)` when it takes over, `companion: hold dropped
(<why>; held from fix seq N, M writes, D m of pan)` when it drops.

**The adopt rule:** a fresh fix whose `level` isn't `?` and differs from the mod's level (a level not known counting as
different) replaces it. It is logged once per change: `companion: level L from the fix (seq N, a C px grid cell); the
mod had X`. This works at any level, and applies only once the fix's write was 0.4 s after the last notch and 0.5 s
after the open.

**The B rules (0.9.3, `dev/docs/PLAN_0.9.3.md`): settle, then show.** At 0 / +1 world icons show only while the
map stands still and a dot fix confirms where it stands:

- settled (above): the mouse still for 0.2 s, the level known, a dot fix written after the last movement; the
  overlay fades in over 0.1 s once settled and out over 0.1 s when a pan, a notch or a level change starts;
- a grid fix (`how` not `dot`) is used only when it agrees with the hold within `GRID_AGREE` (32 m), lies more than
  `STOP_NEAR` (1 m) inside the view's stop on both axes, and a hold exists; never before the first dot fix of an open
  made while the player moved faster than `WALK` (0.5 m/s, measured over 0.25 s). A refused one is logged once per
  change of reason (`companion: fix seq N not used (<reason>)`) and the hold carries on;
- the drawn V eases toward the model's: under `EASE_DEAD` (1.5 m) it does not move, over `SNAP_M` (25 m) it snaps,
  between it moves linearly in about `EASE_T` (0.1 s); it snaps while nothing is drawn;
- an open on the move logs `map: open on the move (the player at S m/s): no grid fix before its first dot fix`, then
  `open on the move: player moved A m before the first dot fix, V moved B m` (V's move from the player's spot at the
  open, the mouse pan taken out), or `open on the move: no dot fix before the close`;
- no companion: once the map has been open at 0 / +1 for 1 s with no fix ever read this session, one line
  `no companion fix this session: world icons at the whole-map zoom only`. -1 needs no companion.

**Keys:** F7 (hide everything), Numpad 1 and Numpad 3 only.

**Options (config.lua):** `C.LEGEND`, `C.COMPASS`, `C.OVERLAY` (on; `false` only in sims), `C.RADAR`, `C.MARKERS`,
`C.ROTATE`, `C.PINGS`, `C.MODE`, `C.MAP_OPACITY` and `C.MARKER_OPACITY` (0..1, default 1: the map's world icons; the
pins), `C.HELPER` (false for `helper = 'off'`: main.lua doesn't start the companion). Shared look:

- `C.RGB` (+ `muted` 150,146,128);
- `C.PANEL.fill` (12,13,14);
- `C.RANK` (value order: super, rare, credit, medal, common, requisition, ammo, grenade, stim);
- `C.VALUABLE` (the first six).

**0.9.3 options (the menu's keys, chef_sim's `options`):**

| Key | Values | Effect |
|---|---|---|
| `mode` -> `C.MODE` | `'all'` (default, also any other value) \| `'no_radar'` \| `'map_only'` | what shows outside the map: `'no_radar'` sets `C.RADAR` false; `'map_only'` sets `C.RADAR` false, `C.COMPASS` false and `C.MARKERS` nil (no world pins). The map's icons and the legend are never touched by it: `objectives.wants(S)` runs the structures list while the map is closed and not hidden whenever the radar, the overlay or the legend is on (0.9.2 ran it for the radar only, so with no radar the open map had no nests or objectives) |
| `legend` -> `C.LEGEND` | `'map'` (default, also nil or any other value) \| `'always'` \| `'off'` or `false` (-> `false`) | `'map'`: beside the open map only; `'always'`: also while the map is closed, left of the corner radar (or where it sits beside the open map when the radar is off), main layers 960-962; `false`: never |
| `kinds` | `{ credit = true, ... }` | the loot kinds shown everywhere; none ticked (no table) = all, as before (`loot` is the sims' older spelling) |
| `map_kinds` | `{ objective, extract, side_objective, nest, structure, poi }` | the same for the map's other marks (`extras` in sims) |
| `radar` | `'medium'` (default) \| `'large'` \| `'small'` | the menu has no Off since 0.9.3; `'off'` / `false` still work in sims |

**`T.mod.view`** (call it `VW`; read by overlay, legend, compass):

| Field | What |
|---|---|
| `VW.open` | the map is open and the model can be used this frame (`S.map_open`, mapview's top world up) |
| `VW.trusted` | V is known this frame: -1 on a measured class, or 0 / +1 with a fresh, usable fix or the hold (0.9.2), and the zoom settled. False = draw nothing world-anchored on the map |
| `VW.settled` | (0.9.3) true at -1 (class known); at 0 / +1: the level known (`lo == hi`), no mouse count or wheel notch for `SETTLE` (0.2 s), and a dot fix whose write is newer than the last movement. The overlay draws only while `VW.fade > 0`, which rises only while settled |
| `VW.fade` | (0.9.3) 0..1: rises at 1 / `FADE_T` (0.1 s) per s while trusted and settled, falls at the same rate otherwise, 0 at once while not trusted. Every overlay alpha is multiplied by it |
| `VW.tvx`, `VW.tvy` | (0.9.3) the model's V this frame (the fix, the hold or the origin), before the ease |
| `VW.held` | (0.9.2) true while V at 0 / +1 comes from the hold, not a fresh fix |
| `VW.level`, `VW.lo`, `VW.hi` | the level (nil while not known) and its bounds (-1..1) |
| `VW.class`, `VW.census` | 'small' \| 'big' \| nil (not measured, or not asked yet); the unit count it came from |
| `VW.k` | px per metre this frame (eased between levels, 0.15 s per x2) |
| `VW.vx`, `VW.vy` | the view's centre V in world m (0, 0 at -1), while trusted; since 0.9.3 the V drawn: eased toward `VW.tvx`, `VW.tvy` (see the B rules) |
| `VW.cx`, `VW.cy`, `VW.r` | the world origin's screen spot (`S.map.cx - Vx * k`, ...) and the map circle's radius |
| `VW.to_screen(x, y)` | -> sx, sy (bottom-left origin); no allocation |
| `VW.inside(sx, sy, margin)` | -> bool: within the circle, `margin` px in from the rim |
| `VW.clusters`, `VW.n` | the loot clusters this frame (reused tables, valid while `VW.trusted`): `{ sx, sy, wx, wy, kind, piles, total, mixed, valuable, marks, seedx, seedy, alpha, dist, wp }` |
| `VW.legend` | rows for the legend: `{ { kind, left, total }, ... }` in `C.RANK` order, then `VW.legend.nests = { left, total }` |
| `VW.waypoint` | nil, or `pings.waypoints[1]` |
| `VW.fix`, `VW.fresh`, `VW.seq` | the last fix line read (`{ seq, ts, how, vx, vy, err, level, cell }`), whether it is fresh, the mod line's last seq |
| `VW.main`, `VW.shadow`, `VW.shadow_is` | read-only: the level states (`sl0..sl1`) and the shadow's life (nil \| 'alive' \| 'confirmed' \| 'pending') |

**Layers (top world, while the map is open):**

- TOP + 920: nest and structure rings;
- 922-929: loot discs, icons and badges;
- 930-939: the legend;
- 945: the off-map waypoint chevron.

TOP + 950-959 are free again (the measure build's). The compass keeps 951-958 in the main world; the legend's
'always' panel uses 960-962 there while the map is closed (0.9.3).

**Drawing on screen GUIs:** only axis-aligned `chef.rect` and tinted `chef.bitmap` (no rotation, no lines, no
circles). Rings, discs, rounded corners and diamonds are textures (white, tinted by the draw colour):

- `ov/nest_s`, `ov/nest_m`: nest rings, 20 px box;
- `ov/disc`;
- `ov/chev/01..16`: the off-map waypoint chevron (`D.rot`);
- `ov/rr/*`: rounded-panel corners, fill and line (ui.lua).

That is 27 textures in all (`art/map_overlay.py`). Every distinct texture a frame uses costs the loader a GUI, so keep
the set small (sim `stats.txt` shows it).
