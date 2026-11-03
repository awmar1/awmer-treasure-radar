# Mod <-> companion interface (fixed 2026-10-27, v1; v1.1, v1.2 and v1.2 behaviour at the end)

Why: at map zoom levels 0 and +1 the game centres the map on its own cursor, and nothing in Lua can read where that
is (dev/docs/RESEARCH_MAP.md, sections 4, 5, 9). A companion program outside the game captures the screen, finds the
player's icon on the map (the mod knows the player's world position, so one icon fixes the view) or the 65 m grid,
and tells the mod the view centre V. The mod draws the world icons around V. The companion reads pixels only: no
game memory, no input.

Both sides implement exactly this file. Neither side edits it; a needed change is reported instead.

## Files

Both live in %LOCALAPPDATA% (the folder of treasure_radar.log). (v1.2: in %LOCALAPPDATA%\Temp, see the end.)

- `treasure_radar_mod.txt`: written by the mod, read by the companion.
- `treasure_radar_fix.txt`: written by the companion, read by the mod.

Each file holds ONE line: `key=value` fields separated by single spaces, terminated by the field `end` and a newline.
A reader ignores a line without the trailing `end` (a partial write) and keeps its previous values. Numbers are plain
decimals (`-3`, `114.2`, `0.5540`), never exponents. Unknown keys are ignored, so either side may add keys later.

The mod writes with one `f:write(line)` on a file opened with `'w'` (Lua 5.1 cannot rename over an existing file on
Windows). The companion writes to `treasure_radar_fix.txt.tmp` and `os.replace`s it over the target (atomic).

## treasure_radar_mod.txt (mod -> companion)

Written every frame while the map is open (the mod's mapview says open), and once more with `open=0` when it
closes. At most one write per frame.

| key | meaning |
|---|---|
| `seq` | integer, +1 per write, starts at 1 per game session |
| `t` | the mod's clock in seconds (the one in the log), 3 decimals |
| `open` | `1` while the map is open per mapview, else `0` |
| `level` | the mod's zoom level: `-1`, `0`, `1`, or `?` when not known |
| `class` | the map size class: `small`, `big`, or `?` (unmeasured) |
| `w` `h` | the screen size in px that hud.lua lays the HUD out for |
| `cx` `cy` | the map circle's centre in px, top-left origin, 1 decimal |
| `rim` | the circle's rim radius in px, 1 decimal (0.2056 h) |
| `kz` | px per metre at the current level (`0` when the level or the class is not known) |
| `px` `py` | the player's world x and y in metres (y is north), 1 decimal |
| `mx` `my` | raw mouse counts since the previous write: `mx` right is +, `my` DOWN (south) is + (the raw convention) |

Example:

    seq=4567 t=692.512 open=1 level=0 class=small w=1920 h=1080 cx=1674.0 cy=819.5 rim=222.0 kz=1.4766 px=114.2 py=210.0 mx=12 my=-3 end

## treasure_radar_fix.txt (companion -> mod)

Written after every capture (20-30 per second while the map is open; nothing while it is closed).

| key | meaning |
|---|---|
| `seq` | the mod line's `seq` that was current when the frame was captured |
| `ts` | the companion's wall clock, `time.time()`, 3 decimals |
| `how` | `dot` (the player icon fixed V), `grid` (the grid phase plus the prior fixed V), or `none` (no fix in this frame; `vx` `vy` absent) |
| `vx` `vy` | the view centre V in world metres: the world point drawn at the circle's centre (`cx`, `cy`) |
| `err` | the companion's error estimate for V in metres |
| `level` | the level measured from the grid period: cell = 65 x kz px, so at 1080p 50.7 (small) or 36.0 (big) is `-1`, 96 is `0`, 192 is `1`; `?` when the grid was not measured |
| `cell` | the measured grid cell in px, 1 decimal, `0` when not measured |

Example:

    seq=4567 ts=1761550000.123 how=dot vx=115.4 vy=211.2 err=1.5 level=0 cell=96.0 end

## Geometry (both sides)

The map is drawn north up. A world point W appears at

    sx = cx + (Wx - Vx) * kz
    sy = cy - (Wy - Vy) * kz

So from the player icon found at pixel (dx, dy) and the player at (px, py):

    Vx = px - (dx - cx) / kz
    Vy = py + (dy - cy) / kz

The grid lines are 65 m apart and anchored on the world origin, so a vertical grid line at screen x gives
`Vx mod 65 = ((cx - x) / kz) mod 65`, and likewise for y with the sign flipped. The grid alone gives V modulo 65 m on
each axis; the companion unwraps it with its previous V advanced by the mouse counts the mod reported since then.

Mouse gain, metres per raw count (measured; the same for all map sizes): level -1: 0.269, level 0: 0.246,
level +1: 0.123. The sign is the one 0.8.3's view.lua measured (its `move()`: `mx, my = dx * g, -dy * g`):

    Vx += mx * gain
    Vy -= my * gain        (raw my > 0 is a move down the screen = the view centre moves south)

Both sides use exactly this. A companion that sees the dot disagree with this prediction trusts the dot and reports
the error in `err`; it never flips the sign on its own.

Coordinate note for the mod: hud.lua keeps the circle centre with y measured from the BOTTOM of the screen
(260.5 at 1080p). The `cy` in the mod line is top-left: `cy = h - S.map.cy` (819.5 at 1080p). `rim` is 0.2056 h.

## How the mod uses a fix

- At level -1 the mod ignores fixes (the view is the whole map on the origin).
- At level 0 or +1 the mod draws the world icons only when it has a fix with `how` not `none` whose `seq` is within
  the last 15 of its own seqs (about a quarter second). It advances V by the mouse counts of its own writes after
  that seq times the gain for the level (it keeps a ring of its last 32 writes' `mx` `my`). Without a fresh fix it
  draws no world icons at 0 / +1.
- When a fix's `level` is not `?` and differs from the mod's level, the mod adopts the fix's level and logs one line
  per change: the companion's grid period is a direct measurement, the mod's notch count is an inference.
- The mod never trusts `vx` `vy` beyond the circle's rim plus 10 m, and never without `end`.

## How the companion uses the mod line

- Poll the file up to 30 times per second. With `open=0`, `level=?`, `class=?` or `kz=0`: idle (sleep 100 ms), write
  nothing.
- Otherwise capture the square `[cx - rim, cy - rim, cx + rim, cy + rim]` of the primary screen, find the player
  icon, measure the grid, write the fix. Order of preference: dot, then grid with a prior, else `none`.
- The player's own icon: measured from the user's screenshots (a yellow chevron in those; other squad slots may use
  other colours, so detect the four slot colours and prefer the candidate nearest the prior V's prediction).

## Not in v1

Teammate icons, objective icons, the cursor label (OCR), multiple monitors, non-primary-screen games, HUD scales
other than the one in the mod line's geometry (the geometry travels in the line, so a scale change only needs the
mod to send new numbers).

## v1.1 (2026-10-27): what the shipped code does beyond v1

Both sides were built against v1 and these points were settled while building; the code is the reference now.

- The mod line carries two more keys: `cmx` `cmy`, the running sums of every written `mx` `my` of the game session
  (same signs). The companion predicts from the `cmx` `cmy` deltas between the lines it read, so counts on lines it
  missed are not lost; it falls back to `mx` `my` times the seq jump when a line lacks them, and resets its baseline
  when `seq` goes backwards (a new game session).
- The mod writes the line every frame while the map is open even with `level=?` (then `kz=0`), and the companion
  does NOT idle on `level=?` or `kz=0`: it measures the grid period, names the level, derives kz itself (level 0 and
  +1 need no class; -1 needs the class, so `level=-1` with `class=?` is the one case it idles on), and writes the
  fix. A level is reported once two frames in a row agree. The mod adopts a fresh fix's level when it differs from
  its own, unknown counting as different, provided the fix was written at least 0.4 s after the last notch and 0.5 s
  after the open.
- Freshness on the mod side: `how` not `none`, the seq among the mod's last 15 writes, and the seq from the current
  open (a fix from before a reopen never counts). V from a fix is used only at 0 / +1; a fix is refused, with one log
  line per reason, when its seq left the 32-entry ring, it was taken at -1, it has no `vx` `vy`, or its V is further
  from the player than rim / kz + 10 m at the fix's level.
- Mouse counts while the map is closed are dropped from `mx` `my` (and so from `cmx` `cmy`).
- The companion retries `os.replace` up to 4 times when Windows refuses it (the mod holds the file open for a
  moment), then skips that frame.
- The player's own icon is a yellow DOT with a view cone (the chevron in v1's wording is the game's white map
  cursor). The mod's `px` `py` is the camera point, 2-3 m from the icon, so the companion uses the icon only to pick
  the 65 m cell and takes the exact V from the grid phase (`how=dot` still).
- Every fix needs the grid: no grid (mid-zoom, hidden grid) means `how=none`.
- The 0.8.2 review's metres are in a y-down frame; the mod's world y is north (up the screen), as v1's geometry says.
  The companion's tests flip the review's truths accordingly.

## v1.2 (2026-10-27): the Temp folder, the companion's log and recorded frames

The field test of 0.9.0 with companion 1.0 gave the mod no fix at all, although the companion found the icon and
wrote its file 12-17 times a second. The cause was not the protocol: the Microsoft Store Python is an MSIX
package, and Windows redirects a package's writes under %LOCALAPPDATA% and %APPDATA% into
`%LOCALAPPDATA%\Packages\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\LocalCache\Local\...`, so the fix
file landed where the game never looks (and the companion read the mod's file fine, reads are not redirected).
`%LOCALAPPDATA%\Temp` is exempt from the redirection (verified on the test machine).

- Both files now live in `%LOCALAPPDATA%\Temp`, the names unchanged: `treasure_radar_mod.txt` and
  `treasure_radar_fix.txt`. The mod derives the folder as `LOCALAPPDATA .. '\Temp'`; the companion's default folder
  is the same and it creates the folder when missing (`--dir` still overrides it). Nothing else changed: the lines,
  the 30 Hz loop, the freshness rules and the adopt rule are v1.1's.
- The mod logs two lines per game session into treasure_radar.log: `companion: mod line -> <mod path>, fix <- <fix
  path>` the first time it writes its line, and `companion: first fix read (seq N)` the first time it reads a fix.
  A log without the second line while the companion says `active` means the two sides are not looking at the same
  folder.
- The companion detects a packaged interpreter at startup (kernel32 `GetCurrentPackageFullName`: 15700 = not
  packaged) and prints a note saying why it uses the Temp folder and to install Python from python.org if the mod's
  log stays without `companion:` lines. It still runs.
- The companion keeps its own log, `treasure_radar_companion.log` in the same folder, new at every start: every
  console line (startup, state changes, the 5 s reports, notes) plus one line per map open at its close (`map open
  done: seq A-B, N frames in T s: dot d, grid g, none n; levels seen ...; last V=...; k frames recorded`).
- The companion records some captures as lossless PNG in `%LOCALAPPDATA%\Temp\treasure_radar_frames` (made at
  startup; its old `*.png` and `*.txt` are deleted then, nothing else): the first 3 frames of every map open; at
  levels 0 and +1 every frame with `how=none` or a measured level other than the mod's, at most one a second; at
  level -1 the frames without a fix, at most one per 2 s; 100 files per companion session, then one log line and
  no more. A file is named like `181107.512_seq0421_L0_none.png` (clock, the mod's seq and level, the fix's how),
  and `frames.txt` in the folder gets one tab-separated line per file: the name, the mod line as read, the fix line
  written. The PNG is the capture box itself (444 x 444 at 1080p), and `--shot <png> --mod "<mod line>"` replays
  it: the companion takes a shot the size of the box as the box.
- 0.9.0's camera probe is gone from the mod (RESEARCH_MAP.md section 4 has what it found).

## v1.2 behaviour, companion 1.2 (2026-10-27): no format change

The files, their lines and their fields stay exactly v1.2's. What changed is how each side uses them, after the
2026-10-27 mission (mod 0.9.1, companion 1.1: 74 recorded frames with `how=none`, and fixes that went stale while
the player panned). Companion 1.2 says `1.2 (interface v1.2)`; the mod side is 0.9.2.

Companion 1.2 (detect.py):
- The view cone's pixels are the band's own hue (`CONE_HUE_PAD = 0`; 1.1 widened the hue band by 4). The orange
  terrain of that mission (H 24-26) then filled every sector round the disc and the cone test threw the player's
  icon away; without the widening those frames measure a cone concentration of 0.90-0.93.
- A partial disc: a yellow blob that fails the shape test (the disc partly under another icon, or merged with a
  yellow objective marker) but holds at least 30 % of the disc's area gets a circle of the icon's radius fitted to
  its edge. It counts when at least 30 % of that circle's rim lies on the blob's edge, the fitted centre is inside
  the map circle and the view cone is at the fitted centre. Its fix is `how=dot` with `err` = hypot(grid error,
  2.5 m) instead of 0.5 m; a whole disc with a cone ranks above it.
- Level -1 with the class known: the whole map sits on the origin, so a grid whose phase is within 8 m (per axis)
  of the origin and no usable icon give `how=grid vx=0 vy=0` without a prior. The mod still takes no V from a fix
  at -1; the fix's level counts for the adopt rule as before.
- The Tracker's prior (the last fix advanced by the mouse counts since) survives frames without a fix, as in 1.1;
  a test now covers it. On the recorded frames 16 of the 74 `none` frames now give a fix.

Mod 0.9.2 (view.lua; this replaces v1.1's freshness rules and the rim-plus-10-m rule under "How the mod uses a
fix"):
- Fresh: `how` not `none`, the seq among the mod's last 45 writes (was 15) of the current open; the mouse-count ring
  holds 128 writes (was 32). `vx` `vy` and `end` are still required, and V still comes from a fix only at 0 / +1.
- No distance gate: a fix is no longer refused for a V further from the player than rim / kz + 10 m. A long pan
  puts the view far from the player, and the gate refused good fixes there.
- A fix taken before a later write of the same open at level -1 is not used (log: `the map went to the whole-map
  level after it`): a zoom in from the whole map re-centres the view on the cursor.
- The hold: the last V a fix gave in this open is carried on by every later write's mouse counts (at that write's
  level's gain), with no time limit, and gives V at 0 / +1 while no fresh fix does. On each axis it is clamped where
  the game stops the view (R_map - rim / k from the origin by the class, never inside the starting fix's own V at
  that fix's level); the point the counts move follows the map cursor, which stops 0.183 h px further
  (RESEARCH_MAP.md section 9). It drops at the map's close (the `open=0` write), at a new mission, out of a mission,
  when its writes leave the ring, and when the level leaves -1 (a zoom in from the whole map); a step between 0 and
  +1 keeps it. At -1 V is the origin. Log lines: `companion: holding V from fix seq N (M writes, D m of pan)` once
  when it takes over, `companion: hold dropped (<why>; held from fix seq N, M writes, D m of pan)` once when it
  drops.
- Without a fresh fix or a hold, nothing world-anchored is drawn at 0 / +1, as before.
