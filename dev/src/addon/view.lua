local T, chef = ...
-- The open map's model (0.9, CONTRACT.md "0.9"): which zoom level the game's Tab map is at, where a world point sits
-- on it when that is known, and what the map views draw from it (the loot clusters, the legend's rows, the waypoint).
-- No calibration: the numbers are the 0.8 measuring runs' (1080p, HUD Scale 0.9); px scale with the screen height,
-- and HUD Scale changes none of them.
-- Three zoom levels on every map (dev/docs/RESEARCH_MAP.md): -1 is the whole map centred on the world origin; 0 and
-- +1 are a window centred on the game's map cursor. A mission starts at 0, the level lasts across closes all mission,
-- and the wheel steps it and stops at both ends. Every mission starts at 0, not only the first: the one direct measure
-- (the field log of 2026-10-28, world 7) has the game back at 0 after the last mission ended at -1. Were that ever
-- wrong, one notch out (the clamp) or a dot fix at -1 finds the level. px per m at 1080p: -1 = rim / R_map (KW: 0.7805 on a small map, R
-- 285.3 m; 0.554 on a big one, R 401 m), 0 = 1.4766, +1 = 2.953. The 65 m grid sits on the origin.
-- The map's size class comes from the mission's own unit count (World.num_units on the main world, the count in the
-- loader's "world N: mission (K units)" line): small 4000..11000, big above that with no upper end (the field saw
-- 25868). It is re-read every CENSUS_EVERY s until it stops growing (a load can count low at first), and two piles of
-- loot beyond FAR0 m on an axis make the map big whatever the count says (the small map's R is 285.3 m; the piles'
-- spots are ones track already read, no new engine call). One log line per class. Below 4000 the size isn't measured,
-- and -1 gets no world icons (logged once).
-- Where the map cursor is (so where 0 and +1 are centred) is native HUD state no Lua can read. World icons there come
-- only from a fresh fix of the screen-reading companion (dev/docs/COMPANION_INTERFACE.md). The mod writes its line to
-- %LOCALAPPDATA%\Temp\treasure_radar_mod.txt every frame while the map is open, and once more with open=0 at the
-- close (Temp, not %LOCALAPPDATA% itself: the Microsoft Store Python redirects AppData writes into its own package
-- folder, Temp it leaves alone). It reads the companion's treasure_radar_fix.txt from the same folder. A fix is fresh
-- while how isn't none and its seq is one of the mod's last FRESH writes of this open. The view's centre V is then
-- the fix's, advanced by the mouse counts of the writes after it (GAIN per count; Vx += mx g, Vy -= my g). There is no
-- distance gate (0.9.2: 0.9.1's "V no further from the player than the rim's reach + 10 m" threw good fixes away on
-- long pans). A fix taken before a write at the whole-map level isn't used (a zoom in from there re-centres the
-- view). The line also carries cmx, cmy: the sum of every write's mx, my this session, so the companion loses no
-- counts of lines it missed. The line goes out every frame while open even with the level or the class not known
-- (level=? kz=0). A fresh fix whose level isn't ? and differs from the mod's (a level not known counting as
-- different) is adopted, with one log line per change.
-- The hold (0.9.2): the last V a fix gave in this open is kept with the seq of the write it is current for, and every
-- later write's mouse counts carry it on (at that write's level's GAIN), with no time limit. While no fresh fix gives
-- V at 0 / +1, the hold does (VW.trusted, and VW.held). The game stops its view R_map - rim / k from the origin on
-- each axis (REVIEW_0.8.2: 135.0 m on a small map at 0), and the map cursor 0.183 h beyond that (RESEARCH_MAP 9): the
-- hold's point follows the cursor (stopped there too), V is that point clamped to the view's stop (by the class; at
-- the level of the fix it began from, never inside that fix's V). The hold drops at the map's close (the open=0 write,
-- reset, idle) and when the level leaves -1 (a zoom in from the whole map re-centres the view on the cursor); a step
-- between 0 and +1 keeps it. At -1 V is the origin. One log line when it takes over, one when it drops.
-- Without a fresh fix or a hold nothing world-anchored is drawn at 0 / +1. Without the companion the mod is whole-map
-- only (0.9.3: logged once a session, "no companion fix this session: ...", once the map has been open at 0 / +1 for
-- NOFIX_T s with no fix ever read; nothing on screen).
-- Settled (0.9.3, PLAN_0.9.3.md "B"): at 0 / +1 the icons show only once the estimate stopped moving. VW.settled is
-- false while any mouse count (or a wheel notch) came within SETTLE s, until a dot fix of a write made after the
-- mouse stopped has given V, and while the level is unsure (lo ~= hi); the hold and the fix path run underneath all
-- the same. At -1 (V the origin) the icons are always settled. VW.fade ramps 0..1 over FADE_T s toward "trusted and
-- settled" (overlay.lua multiplies its alphas by it, and draws the fade-out's tail). Dot fixes place V; a grid fix
-- (the companion's grid phase on the hold's prior) is taken only while the hold exists, within GRID_AGREE m of it,
-- with neither axis of its own V within STOP_NEAR m of the view's stop (stop_of: 0.9.2's clamp-corner fixes), and,
-- at an open made on the move (the player faster than WALK m/s), not before that open's first dot fix. The V drawn
-- (VW.vx, VW.vy) eases toward the model's (VW.tvx, VW.tvy): within EASE_DEAD m nothing moves, beyond it the drawn V
-- eases over EASE_T s, beyond SNAP_M m it snaps; while nothing shows it simply follows. At an open on the move, one
-- line at its first dot fix at 0 / +1: "open on the move: player moved X m before the first dot fix, V moved Y m"
-- (the player from the open's write to the fix's; V from the player's spot at the open, the mouse's pan taken out:
-- the walking hypothesis of RESEARCH_MAP 10, logged, not implemented).
-- The level is kept as bounds (sl0..sl1), and the ends make it exact. Three things leave it unsure: a frame with two
-- notches may have zoomed once; a notch just after a Map press may or may not have zoomed; an open mapview took back
-- or found late widens it.
-- A notch within BUSY s of a step the game took does nothing, in the game and here: the zoom is still running. The
-- field log's fixes measure it (2026-10-28: 8 bursts with gaps of 20-290 ms took one step each, the mod's count ran
-- ahead, and the icons stayed away or sat at the wrong scale until "zooming in and out a bunch"); no two real steps
-- were ever seen within 290 ms, and steps 480 and 540 ms apart were real. A notch at the end of the wheel moves nothing
-- and starts no such wait.
-- A level still unsure after UNSURE_GRACE s, with -1 inside its bounds, draws at -1 (VW.level stays nil, the mod line
-- level=?). The trade: if the game is really at 0 or +1 the icons sit wrong by x1.9 - x5 until any notch or a dot fix
-- settles it; the other way the icons stay away until the wheel hits the end, the report we started from. Unsure states
-- are rare (3 "not known" lines in 4359 log lines) and the grace leaves a companion's fix time to answer first.
-- The shadow (0.8.2): mapview may think the map closed while the game ignored the press. From a Map press that closes
-- the map (key mode), a second level follows the wheel as if the map were open. V.follows and V.doubts kill it, and
-- V.stills confirm it. A cold open takes it over. A take-back of a press open the game ignored goes back to the level
-- at the press (or the confirmed shadow's, or the hull of both).
-- Clusters are made in screen space every frame from track's piles inside the circle. In C.RANK order, each pile
-- joins the first cluster whose seed (its first pile) is closer than JOIN px, else it seeds a new one. A cluster sits
-- at its piles' mean. Tables are reused (valid for this frame).
-- Log lines (mapview's V.note): the class, every notch, the level known or not, the shadow's life, the fix fresh /
-- stale / not used, a level taken from a fix, the hold used / dropped.
local VW = {}
local C = T.mod.config
local max, min, sqrt, abs, log, floor = math.max, math.min, math.sqrt, math.abs, math.log, math.floor
local sort = table.sort
local fmt = string.format

-- ------------------------------------------------------------------ the numbers (px at 1080p)
local KL = { [0] = 1.4766, [1] = 2.953 }                 -- px per m at levels 0 and +1, on every map
local KW = { small = 0.7805, big = 0.554 }               -- px per m at -1: the whole map (rim / R_MAP)
local R_MAP = { small = 285.3, big = 401 }               -- m: the map's half-size (the log says it)
local SMALL0, SMALL1 = 4000, 11000                       -- the unit count: small 4000..11000, big above that
local GAIN = { [-1] = 0.269, [0] = 0.246, [1] = 0.123 }  -- m the view's centre moves per raw mouse count
local LO, HI = -1, 1          -- the levels (the wheel stops at both ends)
local ZOOM_EASE = 0.15        -- s the game's zoom takes per x2 (eyeballed)
local NOTCH_SETTLE = 0.25     -- s after a Map press in which a notch may or may not have zoomed the game's map
local BUSY = 0.3              -- s after a step the game took in which it ignores the wheel (measured, see above)
local UNSURE_GRACE = 0.8      -- s after the last notch or the open before an unsure level draws at -1
local CENSUS_EVERY = 0.5      -- s between reads of the unit count, and looks at the piles' extent
local CENSUS_STILL = 5        -- s without growth: the count is final
local CENSUS_LONG = 30        -- s after the first read: the count is final anyway
local FAR0, FAR1 = 300, 430   -- m on an axis: a pile out here is off a small map (R 285.3) and on a big one (R 401)
local FAR_PILES = 2           -- this many of them: one stray pile decides nothing
local FRESH = 45              -- a fix is fresh while its seq is one of the mod's last FRESH writes (0.9.1: 15)
local RING = 128              -- the mod's writes kept: seq, time, mouse counts, level, the player's spot (0.9.1: 32)
local PIN = 0.183 * 1080      -- px at 1080p: how far out the map cursor stops once the view stops (RESEARCH_MAP 9)
local ADOPT_QUIET = 0.4       -- s: a fix's level counts once it was captured this long after the last notch
local OPEN_QUIET = 0.5        -- s: and this long after the open (the map's animation)
local JOIN = 13               -- px: a pile this close to a cluster's seed joins it
local IN = 2                  -- px: piles this far inside the rim are on the map
local WP_MATCH = 3            -- m: a cluster holds the waypoint if a pile of the waypoint's kind is this close to it
-- B (0.9.3): show only when settled
local SETTLE = 0.2            -- s: the icons at 0 / +1 hide while any mouse count (or a notch) came this recently
local FADE_T = 0.1            -- s: their fade in and out (a linear ramp)
local GRID_AGREE = 32         -- m: a grid fix is taken only this close to the hold (one 65 m cell / 2)
local STOP_NEAR = 1           -- m: and never with an axis of its own V this close to the view's stop
local EASE_DEAD = 1.5         -- m: a fix this close to the drawn V moves nothing
local EASE_T = 0.1            -- s: beyond that the drawn V eases toward it over this long
local SNAP_M = 25             -- m: beyond this it snaps (a real re-centre)
local WALK = 0.5              -- m/s: an open made with the player faster than this is made on the move
local SPEED_T = 0.25          -- s: the player's speed is measured over this long
local NOFIX_T = 1.0           -- s open at 0 / +1 with no fix ever read before the "no companion fix" line

VW.open, VW.trusted = false, false
VW.level, VW.lo, VW.hi = 0, 0, 0       -- the level (nil: not known), and its bounds
VW.class, VW.census = nil, nil         -- 'small' | 'big' | nil (not measured); the unit count it came from
VW.k, VW.cx, VW.cy, VW.r = KL[0], 0, 0, 0
VW.vx, VW.vy = 0, 0                    -- the view's centre in world m, while trusted
VW.clusters, VW.n = {}, 0
VW.legend = { nests = { 0, 0 } }
VW.waypoint = nil
VW.fix = nil                           -- the last fix line read: { seq, ts, how, vx, vy, err, level, cell }
VW.fresh = false                       -- that fix is fresh (how not none, its seq one of the last FRESH writes)
VW.held = false                        -- V comes from the hold (the last fix's V carried on by the mouse), not a fix
VW.settled = false                     -- 0.9.3: the icons may show (B: no mouse within SETTLE, a dot fix since, level known)
VW.fade = 0                            -- 0.9.3: the icons' alpha, 0..1 (FADE_T ramps toward trusted and settled)
VW.tvx, VW.tvy = 0, 0                  -- 0.9.3: the model's V (VW.vx, VW.vy is the V drawn, eased toward it)
VW.seq = 0                             -- the mod line's last seq

local RANK_I = {}
for i, id in ipairs(C.RANK) do RANK_I[id] = i end
local function rank_of(kind) return RANK_I[kind.id] or 99 end

local function log2(x) return log(x) / log(2) end

local function note(t, ...)
  local V = T.mod.mapview
  if V and V.note then V.note(t, ...) else chef.log(...) end
end

-- ------------------------------------------------------------------ the map's size class
local class = nil             -- 'small' | 'big' | nil (not measured yet)
local census_t0, census_next, census_grew, census_max, census_done = nil, 0, 0, nil, false
local function kl(l)          -- a level's px per m at 1080p, or nil (the whole map's, while the size isn't known)
  if l == LO then return class and KW[class] or nil end
  return KL[l]
end
local function kz(l) return kl(l) or KW.small end   -- for the zoom's easing only

local function far_piles()    -- the piles out of a small map's reach: spots track already read
  local tr = T.mod.track
  local n = 0
  if tr and not tr.stale and type(tr.stacks) == 'table' then
    for _, m in ipairs(tr.stacks) do
      local a = max(abs(m.x or 0), abs(m.y or 0))
      if a >= FAR0 and a <= FAR1 then n = n + 1 end
    end
  end
  return n
end

local function census(t)
  if not t or (census_done and class == 'big') or t < census_next then return end
  census_next = t + CENSUS_EVERY
  census_t0 = census_t0 or t
  if not census_done then
    local w = chef.world and chef.world()
    local n = w and chef.call('World.num_units', w)
    if type(n) == 'number' then
      n = floor(n + 0.5)
      if not census_max or n > census_max then census_max, census_grew = n, t end
      VW.census = census_max
      local c = n > SMALL1 and 'big' or n >= SMALL0 and 'small' or nil
      if c and c ~= class and class ~= 'big' then
        class, VW.class = c, c
        chef.log('map: world %d, %d units: a %s map (levels -1, 0, +1; the whole map at %.4f px/m at 1080p, R %.1f m)',
          chef.world_id() or 0, n, c, KW[c], R_MAP[c])
      end
    end
    if t - census_t0 >= CENSUS_LONG or (census_max and t - census_grew >= CENSUS_STILL) then
      census_done = true
      if not census_max then
        chef.log('map: the unit count is not available: the map size is not measured (no world icons at the ' ..
          'whole-map level)')
      elseif not class then
        chef.log('map: world %d, %d units: the map size is not measured (below %d): no world icons at the whole-map ' ..
          'level', chef.world_id() or 0, census_max, SMALL0)
      end
    end
  end
  if class ~= 'big' and far_piles() >= FAR_PILES then
    class, VW.class = 'big', 'big'
    chef.log('map: world %d: piles beyond %d m: a big map (levels -1, 0, +1; the whole map at %.4f px/m at 1080p, ' ..
      'R %.1f m)', chef.world_id() or 0, FAR0, KW.big, R_MAP.big)
  end
end

-- ------------------------------------------------------------------ the zoom level
-- a level state: sl0..sl1, the level's bounds
local M, SH, SNAP, TMP = { sl0 = 0, sl1 = 0 }, { sl0 = 0, sl1 = 0 }, { sl0 = 0, sl1 = 0 }, { sl0 = 0, sl1 = 0 }
VW.main, VW.shadow = M, SH    -- main, shadow (the press's: SNAP; scratch: TMP)
VW.shadow_is = nil            -- nil | 'alive' | 'confirmed' | 'pending'
local function copy(d, s) d.sl0, d.sl1 = s.sl0, s.sl1 end
local function hull(d, s) d.sl0, d.sl1 = min(d.sl0, s.sl0), max(d.sl1, s.sl1) end

local function step(m, d)     -- one notch: past an end the game's zoom stays there
  if d > 0 then m.sl0, m.sl1 = min(HI, m.sl0 + 1), min(HI, m.sl1 + 1)
  else m.sl0, m.sl1 = max(LO, m.sl0 - 1), max(LO, m.sl1 - 1) end
end
local function widen(m, n)
  if n <= 0 then return end
  m.sl0, m.sl1 = max(LO, m.sl0 - n), min(HI, m.sl1 + n)
end
local function skid(m, n)     -- n notches (up if n > 0) the game may or may not have taken: only that bound moves
  if n > 0 then m.sl1 = min(HI, m.sl1 + n) elseif n < 0 then m.sl0 = max(LO, m.sl0 + n) end
end
local function notch(m, n)    -- a frame's n notches: one step for sure (the game takes one zoom step a frame at least)
  local one = n > 0 and 1 or -1
  step(m, one)
  skid(m, n - one)
end
local function level(m)       -- the level (nil while not known), its upper and lower bounds
  local a, b = m.sl0, m.sl1
  return a == b and b or nil, b, a
end
local busy_m, busy_s = { t = -1e9, sure = false }, { t = -1e9, sure = false }   -- the notches' timers (see wheel)
local function whole(d) return d >= 1 and floor(d) or d <= -1 and -floor(-d) or 0 end
local function lvs(m)
  local a, b = m.sl0, m.sl1
  return a == b and fmt('%d', b) or fmt('%d..%d', a, b)
end

local target, shown = log2(KL[0]), log2(KL[0])   -- log2 of k at 1080p: the level's, and the one drawn (eases)
local last_open, last_nm, last_ns, last_fixes = nil, 0, 0, 0
local last_press, last_follows, last_stills, last_doubts = nil, 0, 0, 0
local open_kind = nil         -- how this open began: 'press' (SNAP holds M at it), 'cold', nil
local sh_alive, sh_ok, sh_pending = false, false, false   -- the shadow: follows the map; confirmed; frozen (an open)
local wheel_open, wheel_close = 0, 0   -- V.wheel_any at the last open / close
local last_notch = -1e9       -- S.t of the last wheel notch (a fix's level counts ADOPT_QUIET s after it)
local said_known = true      -- the level was known at the last look (logged when that changes)
local mcx, mcy = 0, 0         -- the map circle's centre (S.map)

function VW.to_screen(x, y)
  local k = VW.k
  return VW.cx + x * k, VW.cy + y * k
end

function VW.inside(sx, sy, margin)
  local dx, dy, r = sx - mcx, sy - mcy, VW.r - (margin or 0)
  if r <= 0 then return false end
  return dx * dx + dy * dy <= r * r
end

-- ------------------------------------------------------------------ the shadow
local function shadow_set()
  VW.shadow_is = sh_alive and (sh_pending and 'pending' or sh_ok and 'confirmed' or 'alive') or nil
end
local function start(t, from, why)
  copy(SH, from)
  sh_alive, sh_ok, sh_pending = true, false, false
  shadow_set()
  note(t, 'map: shadow started (%s): level %s', why, lvs(SH))
end
local function kill(t, why)
  if not sh_alive then return end
  sh_alive, sh_ok, sh_pending = false, false, false
  shadow_set()
  if why then note(t, 'map: shadow dropped (%s)', why) end
end

-- ------------------------------------------------------------------ opens, closes, presses, notches
local function opened(t, V)
  last_open = V.t_open
  wheel_open = V.wheel_any or 0
  if V.cold then
    open_kind = 'cold'
    if sh_alive then
      -- the game's map was open since the mod's close, and the shadow followed it
      note(t, 'map: cold open: the shadow (%s) taken: level %s', VW.shadow_is, lvs(SH))
      copy(M, SH)
      kill(t, nil)
    else
      -- mapview found the game's map already open: the wheel it took for the game's other uses may have been the map's
      widen(M, (V.wheel_any or 0) - wheel_close)
    end
  end
  local _, hi = level(M)
  target = log2(kz(hi))
  shown = target              -- no easing from the last open
  note(t, 'map: open %d (%s): level %s', V.opens or 0, open_kind or 'seen', lvs(M))
end

local function closed(t, V)
  last_open = nil
  wheel_close = V.wheel_any or 0
  if sh_pending then kill(t, 'the map closed again') end
end

-- mapview took a false open back (the camera turned with the mouse: the game's map was closed)
local function take_back(t, V)
  copy(TMP, M)                -- the level as this open left it
  local why, kept
  if open_kind == 'press' then
    if (V.stills_press or 0) > 0 then
      -- a real open (the game's map was open, and is closed now): keep the level as the close found it
      why, kept = 'press open, real: a still move since the press', "the open's"
    else
      -- the game ignored the press: back to the level at it
      why, kept = 'press open, not real', "the press's"
      copy(M, SNAP)
      if sh_alive and sh_pending then
        -- or the game was open before the press, and the press closed it
        if sh_ok then copy(M, SH); kept = "the shadow's (confirmed)"
        else hull(M, SH); kept = "the hull of the press's and the shadow's" end
      end
    end
  else
    widen(M, (V.wheel_any or 0) - wheel_open)
    why, kept = open_kind == 'cold' and 'cold open' or 'an open', "the open's, widened"
  end
  note(t, "map: open taken back (%s): kept %s: level %s (the open's %s, the press's %s)", why, kept, lvs(M), lvs(TMP),
    open_kind == 'press' and lvs(SNAP) or '-')
  open_kind = nil
  if V.mode == 'key' then start(t, TMP, 'a take-back: the game may still be open') else kill(t, 'a take-back') end
  last_follows = V.follows or 0   -- the take-back's own follow
end

-- a Map press: opening keeps M as it was (SNAP) and freezes the shadow; closing starts a shadow (key mode)
local function press(t, V)
  last_press = V.t_press
  if V.press_open then
    copy(SNAP, M)
    open_kind = 'press'
    if sh_alive and not sh_pending then
      sh_pending = true
      shadow_set()
      note(t, 'map: shadow pending (a Map press opened the map; the game may have been open, and closed now)')
    end
  else
    open_kind = nil
    if sh_pending then kill(t, 'the map closed again') end
    if V.mode == 'key' then start(t, M, 'a Map press closed the map: the game may have ignored it') end
  end
end

-- the wheel's notches (mapview counts them open and shut); one within NOTCH_SETTLE of a press may or may not have
-- zoomed the game's map: it only moves the level's bound its way
-- a frame's n notches on a level, its own timer b: b.t the last step that moved a bound, b.sure that the game took it
local function wheel(m, b, n, t, settle)
  if b.sure and t - b.t < BUSY then return end     -- the zoom is still running: the game ignores these
  local a0, a1 = m.sl0, m.sl1
  if settle then skid(m, n) else notch(m, n) end
  if m.sl0 ~= a0 or m.sl1 ~= a1 then b.t, b.sure = t, not settle end
end

local function notches(t, V)
  local settle = V.t_press and t - V.t_press < NOTCH_SETTLE
  local n = whole((V.notches_mission or 0) - last_nm)
  if n ~= 0 then
    last_nm = last_nm + n
    wheel(M, busy_m, n, t, settle)
  end
  n = whole((V.notches_shut or 0) - last_ns)
  if n ~= 0 then
    last_ns = last_ns + n
    if sh_alive and not sh_pending then wheel(SH, busy_s, n, t, false) end
    if settle then wheel(M, busy_m, n, t, true) end
  end
  if (V.wheel_frame or 0) ~= 0 then last_notch = t end
end

-- mapview's evidence: doubts and follows kill the shadow, stills confirm it (or drop a pending one), fixes take back
local function evidence(S, t, V)
  if (V.doubts or 0) ~= last_doubts then
    last_doubts = V.doubts or 0
    kill(t, "Esc, a frame gap or a camera jump: the game's map is closed")
  end
  if (V.fixes or 0) ~= last_fixes then
    last_fixes = V.fixes or 0
    take_back(t, V)
  end
  local live = S.map_open and V.t_open
  if (V.follows or 0) ~= last_follows then
    last_follows = V.follows or 0
    if not live then kill(t, "the camera followed the mouse: the game's map is closed") end
  end
  if (V.stills or 0) ~= last_stills then
    last_stills = V.stills or 0
    if sh_alive and not live and not sh_pending and not sh_ok then
      sh_ok = true
      shadow_set()
      note(t, 'map: shadow confirmed (the mouse moved, the camera stayed still): level %s', lvs(SH))
    elseif live and sh_pending then
      kill(t, 'the camera stayed still with the mouse: the press did open the map')
    end
  end
  return live
end

-- this frame's log lines: the notch, the level known or not
local function tell(t, V, known, lo, hi)
  local w = V.wheel_frame or 0
  if w ~= 0 then
    local open = V.t_open
    note(t, 'map: notch %+g at %.2f s (%s s into the open, %s s after a press; %s): notches %g, level %d..%d (%s); ' ..
      'shadow %s', w, t, open and fmt('%.2f', t - open) or '-', V.t_press and fmt('%.2f', t - V.t_press) or '-',
      open and 'open' or 'shut', V.notches_mission or 0, lo, hi, known ~= nil and 'known' or 'not known',
      sh_alive and fmt('%s, level %s', VW.shadow_is, lvs(SH)) or 'none')
  end
  local is = known ~= nil
  if is ~= said_known then
    note(t, 'map: the level is %s (%d..%d)', is and 'known' or 'not known', lo, hi)
    said_known = is
  end
end

-- ------------------------------------------------------------------ the companion (COMPANION_INTERFACE.md)
local mod_path, fix_path = nil, nil
do
  local ok, dir = pcall(os.getenv, 'LOCALAPPDATA')
  if ok and type(dir) == 'string' and dir ~= '' then
    dir = dir .. '\\Temp'   -- the one AppData folder the Store Python doesn't redirect (it exists on every Windows)
    mod_path, fix_path = dir .. '\\treasure_radar_mod.txt', dir .. '\\treasure_radar_fix.txt'
  end
end
local seq = 0                 -- +1 per write, from 1 per game session
local ring = {}               -- the write with seq q: ring[q % RING + 1]
for i = 1, RING do ring[i] = { seq = 0, t = 0, mx = 0, my = 0, level = nil, px = 0, py = 0 } end
local carry_x, carry_y = 0, 0 -- the mouse's fractions of a count, for the next write
local cum_x, cum_y = 0, 0     -- the counts of every write this session (the line's cmx, cmy: the sum of its mx, my)
local wrote_open = false      -- the last line said open=1
local open_seq = 1            -- the seq of this open's first open=1 write
local wrote_t = nil           -- S.t of the last write (one a frame at most)
local write_failed = false
local said_paths = false      -- the two paths, logged once per game session at the first write
local said_first_fix = false  -- the first fix read this game session, logged once
local said_nofix = false      -- "no companion fix this session" logged (once a game session)
local nofix_since = nil       -- S.t this open has been at 0 / +1 since (for that line)
-- B (0.9.3)
local move_t = -1e9           -- S.t of this open's last frame with mouse counts or a notch
local dot_t = nil             -- the write time of the newest dot fix that gave V this open
local ex, ey, shown_ok, ease_rate = 0, 0, false, 0   -- the V drawn, whether it's set, m/s while easing (0: not)
local walk = { on = false, px = 0, py = 0, seq = 0, dot = false, zoomed = false }  -- this open: made on the move?
local sp = { x = 0, y = 0, t = nil, v = 0 }   -- the player's speed (m/s over SPEED_T)
local Sref = nil

local function entry(q)       -- the write with seq q, while the ring holds it
  if q < 1 or q > seq or seq - q >= RING then return nil end
  local e = ring[q % RING + 1]
  if e.seq == q then return e end
end

-- the hold (the header): tx, ty the point it follows (the map cursor's), not clamped; ax, ay the size of the fix's own
-- V on each axis, al its level (there the view's stop is never taken inside it); seq the last write counted, level its
-- level; fix, fvx, fvy the fix it began from; whole: a write at -1 since
local hold = { on = false, tx = 0, ty = 0, ax = 0, ay = 0, al = 0, seq = 0, level = 0, fix = 0, fvx = 0, fvy = 0,
  whole = false }
local function hold_stop(sx, l)   -- the view's stop on each axis at level l (sx: the map's), not inside the fix's V
  if l ~= hold.al then return sx, sx end
  return max(sx, hold.ax), max(sx, hold.ay)
end
local said_hold = false       -- 'holding V' logged (once each time the hold takes over from the fixes)
local function stop_of(S, l)  -- m: where the game stops its view on each axis at level 0 / +1 (nil: not known)
  local r = S.map and S.map.r
  if not class or not r or not KL[l] then return nil end
  return max(0, R_MAP[class] - r / (KL[l] * S.h / 1080))
end
local function hold_pan() return sqrt((hold.tx - hold.fvx) ^ 2 + (hold.ty - hold.fvy) ^ 2) end
local function hold_drop(t, why)
  if not hold.on then return end
  hold.on, VW.held, said_hold = false, false, false
  note(t, 'companion: hold dropped (%s; held from fix seq %d, %d writes, %.1f m of pan)', why, hold.fix,
    seq - hold.fix, hold_pan())
end

local function write_line(S, open, lvl, dx, dy)
  if not mod_path or wrote_t == S.t then return end
  wrote_t = S.t
  seq = seq + 1
  VW.seq = seq
  carry_x, carry_y = carry_x + dx, carry_y + dy
  local mx, my = floor(carry_x + 0.5), floor(carry_y + 0.5)
  carry_x, carry_y = carry_x - mx, carry_y - my
  cum_x, cum_y = cum_x + mx, cum_y + my
  local map, me = S.map or {}, S.me
  local px, py = me and me.x or 0, me and me.y or 0
  local e = ring[seq % RING + 1]
  e.seq, e.t, e.mx, e.my, e.level, e.px, e.py = seq, S.t or 0, mx, my, lvl, px, py
  local k = (lvl ~= nil and class) and kl(lvl)       -- kz 0 while the level or the class isn't known
  local h = S.h or 1080
  local line = fmt('seq=%d t=%.3f open=%d level=%s class=%s w=%d h=%d cx=%.1f cy=%.1f rim=%.1f kz=%s px=%.1f ' ..
    'py=%.1f mx=%d my=%d cmx=%.0f cmy=%.0f end\n', seq, S.t or 0, open and 1 or 0,
    lvl ~= nil and fmt('%d', lvl) or '?', class or '?', floor((S.w or 1920) + 0.5), floor(h + 0.5), map.cx or 0,
    h - (map.cy or 0), map.r or 0, k and fmt('%.4f', k * h / 1080) or '0', px, py, mx, my, cum_x, cum_y)
  if open and not wrote_open then open_seq = seq end
  local ok, f = pcall(io.open, mod_path, 'w')
  if ok and f then
    pcall(f.write, f, line)
    pcall(f.close, f)
    if not said_paths then
      said_paths = true
      chef.log('companion: mod line -> %s, fix <- %s', mod_path, fix_path)
    end
  elseif not write_failed then
    write_failed = true
    chef.log('companion: %s could not be written (the companion gets nothing)', mod_path)
  end
  wrote_open = open
  if not open then hold_drop(S.t, 'the map closed') end
end

-- the fix: the last whole line read (a line without its end is a partial write: the previous values stay)
local fix = { seq = 0, ts = '', how = 'none', vx = nil, vy = nil, err = nil, level = nil, cell = 0 }
local fix_new = false         -- a line whose level isn't looked at yet
local last_text, boot = nil, nil   -- the file as last read; as first read this session (a past session's: ignored)
local said_fresh, said_unused = false, nil
local function parse(text)
  local line = text:match('^[^\r\n]*') or ''
  local last
  local q, ts, how, vx, vy, err, lv, cell
  for tok in line:gmatch('%S+') do
    last = tok
    local k, v = tok:match('^([%w_]+)=(.*)$')
    if k == 'seq' then q = tonumber(v) elseif k == 'ts' then ts = v elseif k == 'how' then how = v
    elseif k == 'vx' then vx = tonumber(v) elseif k == 'vy' then vy = tonumber(v)
    elseif k == 'err' then err = tonumber(v) elseif k == 'level' then lv = tonumber(v)
    elseif k == 'cell' then cell = tonumber(v) end
  end
  if last ~= 'end' or not q then return false end
  fix.seq, fix.ts, fix.how = floor(q + 0.5), ts or '', how or 'none'
  fix.vx, fix.vy, fix.err, fix.cell = vx, vy, err, cell or 0
  fix.level = (lv == -1 or lv == 0 or lv == 1) and lv or nil
  return true
end
local function read_fix()
  local V = T.mod.mapview
  local text = fix_path and V and V.read_file and V.read_file(fix_path)
  if type(text) ~= 'string' then
    if boot == nil then boot = false end    -- no file at the first look: every fix written later is this session's
    return
  end
  if boot == nil then boot = text end
  if text == boot or text == last_text then return end
  last_text = text
  if parse(text) then
    fix_new, VW.fix = true, fix
    if not said_first_fix then
      said_first_fix = true
      chef.log('companion: first fix read (seq %d)', fix.seq)
    end
  end
end
local function in_window(q) return q >= 1 and q <= seq and seq - q < FRESH end
-- and of this open (a fix from before the map closed doesn't hold for the next open: the game's view may have moved)
local function this_open(q) return in_window(q) and q >= open_seq end

-- a fresh fix's level, when it differs from the mod's (a level not known counts as different): adopted (the grid
-- period is a measurement, the notches an inference)
local function adopt(t, V)
  if not fix_new then return end
  fix_new = false
  local fl = fix.level
  if fl == nil or fix.how == 'none' or not this_open(fix.seq) then return end
  local e = entry(fix.seq)
  if not e or e.t < last_notch + ADOPT_QUIET or e.t < (V.t_open or 0) + OPEN_QUIET then return end
  local known = level(M)
  if known == fl then return end
  local was = lvs(M)
  M.sl0, M.sl1 = fl, fl
  note(t, 'companion: level %d from the fix (seq %d, a %.1f px grid cell); the mod had %s', fl, fix.seq,
    fix.cell or 0, was)
end

-- V from the fix: its vx, vy advanced by the mouse counts of the writes after it; or nil and why not (0.9.2: no
-- distance gate)
local function centre(lvl)
  local e0 = entry(fix.seq)
  if not e0 then return nil, nil, 'its seq is not in the ring' end
  local fl = fix.level
  if fl == nil then fl = e0.level end
  if fl ~= 0 and fl ~= 1 then return nil, nil, 'taken at the whole-map level' end
  local vx, vy = fix.vx, fix.vy
  if not (vx and vy) then return nil, nil, 'no vx, vy' end
  for q = fix.seq + 1, seq do
    local e = entry(q)
    if e then
      if e.level == LO then return nil, nil, 'the map went to the whole-map level after it' end
      local g = GAIN[e.level] or GAIN[lvl]
      vx, vy = vx + e.mx * g, vy - e.my * g
    end
  end
  return vx, vy, nil
end

-- the hold: a fix's V taken over (current for this write); then carried on by the writes after it
local function hold_set(vx, vy, lvl)
  hold.on, hold.tx, hold.ty, hold.seq, hold.level, hold.whole = true, vx, vy, seq, lvl, false
  hold.fix, hold.fvx, hold.fvy = fix.seq, fix.vx or vx, fix.vy or vy
  hold.ax, hold.ay, hold.al = abs(hold.fvx), abs(hold.fvy), lvl  -- the fix's V: the game's view was there
end
local function hold_advance(S, t)
  for q = hold.seq + 1, seq do
    local e = entry(q)
    if not e then hold_drop(t, 'its writes left the ring'); return end
    local l = e.level
    if l == LO then hold.whole = true elseif l ~= nil then hold.level = l end
    l = (l ~= nil and l ~= LO) and l or hold.level
    local g = GAIN[e.level] or GAIN[l]
    hold.tx, hold.ty = hold.tx + e.mx * g, hold.ty - e.my * g
    local stop = e.level ~= LO and stop_of(S, l)
    if stop then              -- the cursor stops PIN px beyond the view's stop
      local sx, sy = hold_stop(stop, l)
      local px, py = sx + PIN / KL[l], sy + PIN / KL[l]
      hold.tx, hold.ty = max(-px, min(px, hold.tx)), max(-py, min(py, hold.ty))
    end
  end
  hold.seq = seq
end
local function hold_v(S, lvl) -- V from the hold: its point, clamped to where the game stops the view
  local stop = stop_of(S, lvl)
  if not stop then return hold.tx, hold.ty end
  local sx, sy = hold_stop(stop, lvl)
  return max(-sx, min(sx, hold.tx)), max(-sy, min(sy, hold.ty))
end

-- ------------------------------------------------------------------ B (0.9.3): settled, grid gates, ease, walking
local function speed(S, t)
  local me = S.me
  if not me then return end
  if not sp.t or t < sp.t then sp.x, sp.y, sp.t = me.x, me.y, t; return end
  local d = t - sp.t
  if d >= SPEED_T then
    sp.v = sqrt((me.x - sp.x) ^ 2 + (me.y - sp.y) ^ 2) / d
    sp.x, sp.y, sp.t = me.x, me.y, t
  end
end
local function b_open(S, t)   -- a new open: nothing settled, the drawn V not set, made on the move or not
  move_t, dot_t, shown_ok, ease_rate = -1e9, nil, false, 0
  VW.fade, VW.settled = 0, false
  nofix_since = nil
  local me = S.me
  walk.on, walk.dot, walk.zoomed, walk.seq = sp.v > WALK, false, false, seq
  walk.px, walk.py = me and me.x or 0, me and me.y or 0
  if walk.on then
    note(t, 'map: open on the move (the player at %.1f m/s): no grid fix before its first dot fix', sp.v)
  end
end
local function b_close(t)     -- an open on the move that never got its dot fix at 0 / +1: said too
  if walk.on and walk.zoomed and not walk.dot then note(t, 'open on the move: no dot fix before the close') end
  walk.on = false
end
-- a grid fix's V (vx, vy: advanced to this write) is taken only on these terms; nil, or why not
local function grid_refused(S, lvl, vx, vy)
  if walk.on and not walk.dot then return 'a grid fix before the first dot fix of an open on the move' end
  if not hold.on then return 'a grid fix with no hold to agree with' end
  local stop = stop_of(S, fix.level or lvl)
  if stop and fix.vx and fix.vy and (abs(fix.vx) >= stop - STOP_NEAR or abs(fix.vy) >= stop - STOP_NEAR) then
    return "a grid fix on the view's stop"
  end
  local hx, hy = hold_v(S, lvl)
  if (vx - hx) ^ 2 + (vy - hy) ^ 2 > GRID_AGREE * GRID_AGREE then
    return fmt('a grid fix more than %d m from the hold', GRID_AGREE)
  end
  return nil
end
-- a dot fix gave V: its write's time (settled once that's after the mouse stopped); the walking line
local function dot_used(t, vx, vy)
  local e = entry(fix.seq)
  if e and (dot_t == nil or e.t > dot_t) then dot_t = e.t end
  if walk.on and not walk.dot then
    walk.dot = true
    local x0, y0 = walk.px, walk.py
    local pm = e and sqrt((e.px - x0) ^ 2 + (e.py - y0) ^ 2) or 0
    -- the mouse's pan from the open to the fix's write, taken out of V's move
    local pan_x, pan_y = 0, 0
    for q = walk.seq + 1, fix.seq do
      local w = entry(q)
      if w and w.level ~= LO then
        local g = GAIN[w.level] or GAIN[0]
        pan_x, pan_y = pan_x + w.mx * g, pan_y - w.my * g
      end
    end
    local fvx, fvy = fix.vx or vx, fix.vy or vy
    local vm = sqrt((fvx - pan_x - x0) ^ 2 + (fvy - pan_y - y0) ^ 2)
    note(t, 'open on the move: player moved %.1f m before the first dot fix, V moved %.1f m', pm, vm)
  end
end
-- the V drawn: follows the model's while nothing shows; while shown, eases (EASE_DEAD, EASE_T, SNAP_M)
local function ease(vx, vy, dt, whole_map)
  if not vx then shown_ok, ease_rate = false, 0; return end
  if not shown_ok or VW.fade <= 0 or whole_map then
    ex, ey, shown_ok, ease_rate = vx, vy, true, 0
    return
  end
  local gx, gy = vx - ex, vy - ey
  local d = sqrt(gx * gx + gy * gy)
  if d > SNAP_M then ex, ey, ease_rate = vx, vy, 0; return end
  if ease_rate <= 0 and d <= EASE_DEAD then return end
  ease_rate = max(ease_rate, d / EASE_T)
  local step = ease_rate * (dt or 0)
  if step >= d or d < 1e-6 then ex, ey, ease_rate = vx, vy, 0
  else ex, ey = ex + gx * step / d, ey + gy * step / d end
end

local function freshness(t, open)
  local fresh = (open and fix.how ~= 'none' and this_open(fix.seq)) and true or false
  VW.fresh = fresh
  if fresh ~= said_fresh then
    if fresh then
      note(t, 'companion: fix fresh (seq %d, the mod at %d; %s, V %s, %s, err %s m, level %s, cell %.1f px)', fix.seq,
        seq, fix.how, fix.vx and fmt('%.1f', fix.vx) or '-', fix.vy and fmt('%.1f', fix.vy) or '-',
        fix.err and fmt('%.1f', fix.err) or '-', fix.level and fmt('%d', fix.level) or '?', fix.cell or 0)
    else
      local why = not open and 'the map closed' or fix.how == 'none' and 'how none' or
        fix.seq < open_seq and in_window(fix.seq) and 'from before this open' or
        fmt('not one of the last %d writes', FRESH)
      note(t, 'companion: fix stale (%s; its seq %d, the mod at %d)', why, fix.seq, seq)
    end
    said_fresh = fresh
    said_unused = nil
  end
  return fresh
end

-- ------------------------------------------------------------------ clusters
local piles, np = {}, 0
local function by_rank(a, b)
  local ra, rb = rank_of(a.kind), rank_of(b.kind)
  if ra ~= rb then return ra < rb end
  if a.x ~= b.x then return a.x < b.x end
  return a.y < b.y
end

-- also: seedx, seedy (its first pile's spot), alpha (its piles' track.alpha, the highest), dist (m from S.me to its
-- nearest pile, 2D), wp (nil, or its pile that holds VW.waypoint)
local function new_cluster() return { sx = 0, sy = 0, wx = 0, wy = 0, piles = 0, total = 0, marks = {}, alpha = 1, dist = 0 } end

local function clusters(S, tr, s)
  VW.n = 0
  if not (tr and not tr.stale and type(tr.stacks) == 'table') then return end
  local k, cx, cy = VW.k, VW.cx, VW.cy
  local lim = VW.r - IN * s
  if lim <= 0 then return end
  local lim2 = lim * lim
  np = 0
  local stacks = tr.stacks
  for i = 1, #stacks do
    local m = stacks[i]
    if m.kind and tr.alpha(m, S.t) then
      local dx, dy = cx + m.x * k - mcx, cy + m.y * k - mcy
      if dx * dx + dy * dy <= lim2 then np = np + 1; piles[np] = m end
    end
  end
  for i = np + 1, #piles do piles[i] = nil end
  if np == 0 then return end
  sort(piles, by_rank)

  local list, n = VW.clusters, 0
  local join2 = (JOIN * s) ^ 2
  local me = S.me
  for i = 1, np do
    local m = piles[i]
    local sx, sy = cx + m.x * k, cy + m.y * k
    local c = nil
    for j = 1, n do
      local o = list[j]
      local ex, ey = sx - o.seedx, sy - o.seedy
      if ex * ex + ey * ey < join2 then c = o; break end
    end
    if not c then
      n = n + 1
      c = list[n]
      if not c then c = new_cluster(); list[n] = c end
      c.seedx, c.seedy = sx, sy
      c.sx, c.sy, c.wx, c.wy, c.piles, c.total = 0, 0, 0, 0, 0, 0
      c.kind, c.valuable, c.mixed, c.alpha, c.dist, c.wp = m.kind, nil, false, 0, math.huge, nil
      local marks = c.marks
      for q = #marks, 1, -1 do marks[q] = nil end
    end
    local p = c.piles + 1
    c.piles, c.marks[p] = p, m
    c.sx, c.sy = c.sx + sx, c.sy + sy
    c.wx, c.wy = c.wx + m.x, c.wy + m.y
    c.total = c.total + (m.n > 0 and m.n or 1)
    if m.kind ~= c.kind then c.mixed = true end
    if not c.valuable and C.VALUABLE[m.kind.id] then c.valuable = m.kind end
    local a = tr.alpha(m, S.t) or 0
    if a > c.alpha then c.alpha = a end
    local ex, ey = m.x - me.x, m.y - me.y
    local d = sqrt(ex * ex + ey * ey)
    if d < c.dist then c.dist = d end
  end
  for j = 1, n do
    local c = list[j]
    local p = c.piles
    c.sx, c.sy, c.wx, c.wy = c.sx / p, c.sy / p, c.wx / p, c.wy / p
  end
  VW.n = n

  local w = VW.waypoint
  if w and w.kind then
    local r2 = WP_MATCH * WP_MATCH
    for j = 1, n do
      local c = list[j]
      for q = 1, c.piles do
        local m = c.marks[q]
        if m.kind == w.kind and (m == w.mark or (m.x - w.x) ^ 2 + (m.y - w.y) ^ 2 <= r2) then c.wp = m; break end
      end
      if c.wp then break end
    end
  end
end

local rows_kinds = nil
local function legend(tr, Ob)
  local L = VW.legend
  if not rows_kinds then
    rows_kinds = {}
    local K = T.mod.kinds
    for _, id in ipairs(C.RANK) do
      local kind = K and K.by_id and K.by_id[id]
      if kind and kind.on ~= false then rows_kinds[#rows_kinds + 1] = kind end
    end
  end
  local n = 0
  if tr and tr.seen and tr.left then
    for i = 1, #rows_kinds do
      local kind = rows_kinds[i]
      local total = tr.seen(kind)
      if total > 0 then
        n = n + 1
        local row = L[n]
        if not row then row = {}; L[n] = row end
        row.kind, row.left, row.total = kind, min(tr.left(kind), total), total
      end
    end
  end
  for i = n + 1, #L do L[i] = nil end
  local left, total = 0, 0
  if Ob and type(Ob.marks) == 'table' then
    for _, m in ipairs(Ob.marks) do
      if m.kind and m.kind.cat == 'nest' then
        total = total + 1
        if m.state ~= 'done' then left = left + 1 end
      end
    end
  end
  L.nests[1], L.nests[2] = left, total
end


-- ------------------------------------------------------------------ life cycle
local function close_line(S)
  if wrote_open then write_line(S, false, (level(M)), 0, 0) end
end

function VW.reset(S)
  hold_drop(S and S.t, 'the mission changed')
  close_line(S)
  M.sl0, M.sl1 = 0, 0
  sh_alive, sh_ok, sh_pending, open_kind = false, false, false, nil
  shadow_set()
  target, shown = log2(KL[0]), log2(KL[0])
  last_open, last_nm, last_ns, last_fixes = nil, 0, 0, 0
  last_press, last_follows, last_stills, last_doubts = nil, 0, 0, 0
  wheel_open, wheel_close, last_notch, said_known = 0, 0, -1e9, true
  class, VW.class, VW.census = nil, nil, nil
  census_t0, census_next, census_grew, census_max, census_done = nil, 0, 0, nil, false
  busy_m.t, busy_m.sure, busy_s.t, busy_s.sure = -1e9, false, -1e9, false
  fix.seq, fix.how, fix.level, fix_new, VW.fix, VW.fresh = 0, 'none', nil, false, nil, false
  said_fresh, said_unused = false, nil
  VW.level, VW.lo, VW.hi, VW.n, VW.waypoint = 0, 0, 0, 0, nil
  said_hold, hold.whole = false, false
  VW.open, VW.trusted, VW.vx, VW.vy, VW.held = false, false, 0, 0, false
  VW.settled, VW.fade, VW.tvx, VW.tvy = false, 0, 0, 0
  move_t, dot_t, shown_ok, ease_rate, nofix_since = -1e9, nil, false, 0, nil
  walk.on, sp.t, sp.v = false, nil, 0
  census(S and S.t)
end

function VW.idle(S)
  hold_drop(S and S.t, 'out of a mission')
  close_line(S)
  VW.open, VW.trusted, VW.n, VW.fresh, VW.held = false, false, 0, false, false
  VW.settled, VW.fade, shown_ok, walk.on = false, 0, false, false
end

function VW.shutdown()
  if Sref then pcall(close_line, Sref) end
end

-- the level to draw at: the known one, or -1 for an unsure level that has stayed unsure a while (the header says why)
local function drawn_level(V, t, known, lo)
  if known == nil and lo == LO and class and t - max(last_notch, V.t_open or -1e9) >= UNSURE_GRACE then return LO end
  return known
end

-- ------------------------------------------------------------------ V, settled, the fade (a function of its own:
-- Lua 5.1 allows VW.update 60 upvalues)
local function place(S, t, known, lo, hi, fresh, zoomed)
  -- V: the origin at the whole map (its size known); at 0 / +1 a fresh fix's (a dot fix's; a grid fix's on B's
  -- terms), else the hold's; else nothing world-anchored
  local vx, vy, why = nil, nil, nil
  local held = false
  if zoomed and known == LO then
    if class then vx, vy = 0, 0 end
  elseif zoomed and known ~= nil then
    if fresh then
      vx, vy, why = centre(known)
      if vx and fix.how ~= 'dot' then
        why = grid_refused(S, known, vx, vy)
        if why then vx, vy = nil, nil end
      end
      if why ~= said_unused then
        if why then note(t, 'companion: fix seq %d not used (%s)', fix.seq, why) end
        said_unused = why
      end
    end
    if vx then
      if fix.how == 'dot' then dot_used(t, vx, vy) end
      hold_set(vx, vy, known)
      said_hold = false
    elseif hold.on then
      vx, vy = hold_v(S, known)
      held = true
      if not said_hold then
        said_hold = true
        note(t, 'companion: holding V from fix seq %d (%d writes, %.1f m of pan)', hold.fix, seq - hold.fix,
          hold_pan())
      end
    end
  end
  -- no companion: one line a session, once the map has been at 0 / +1 a while with no fix ever read
  if known ~= nil and known ~= LO then
    walk.zoomed = true
    nofix_since = nofix_since or t
    if not said_first_fix and not said_nofix and t - nofix_since >= NOFIX_T then
      said_nofix = true
      chef.log('no companion fix this session: world icons at the whole-map zoom only')
    end
  else
    nofix_since = nil
  end
  -- settled (B): at -1 always; at 0 / +1 no mouse within SETTLE, a dot fix of a later write, the level known
  local settled = false
  if vx then
    if known == LO then settled = true
    else settled = lo == hi and t - move_t >= SETTLE and dot_t ~= nil and dot_t > move_t end
  end
  VW.held = held
  VW.trusted = vx ~= nil
  VW.settled = settled
  local dt = S.dt or 0
  if not VW.trusted then VW.fade = 0
  elseif settled then VW.fade = min(1, VW.fade + dt / FADE_T)
  else VW.fade = max(0, VW.fade - dt / FADE_T) end
  ease(vx, vy, dt, known == LO)
  VW.tvx, VW.tvy = vx or 0, vy or 0
  VW.vx, VW.vy = vx and ex or 0, vx and ey or 0
  VW.cx, VW.cy = mcx - VW.vx * VW.k, mcy - VW.vy * VW.k
end

function VW.update(S)
  Sref = S
  local V = T.mod.mapview
  local map = S.map
  local s = S.h / 1080
  local t = S.t
  local P = T.mod.pings
  VW.waypoint = C.PINGS and P and type(P.waypoints) == 'table' and P.waypoints[1] or nil
  census(t)
  if not V then VW.open, VW.trusted, VW.n = false, false, 0; return end

  if V.t_press ~= last_press then press(t, V) end
  notches(t, V)
  local live = evidence(S, t, V)
  speed(S, t)
  if live and V.t_open ~= last_open then opened(t, V); b_open(S, t)
  elseif not live and last_open then closed(t, V); b_close(t) end

  -- the companion: the mod's line (every frame the map is open, once more at the close), then the fix
  local dx, dy = 0, 0
  if V.mouse then dx, dy = V.mouse() end
  if S.map_open and (dx ~= 0 or dy ~= 0 or (V.wheel_frame or 0) ~= 0) then move_t = t end   -- B: not settled
  local known = level(M)
  if S.map_open or wrote_open then write_line(S, S.map_open and true or false, known, dx, dy) end
  if S.map_open then
    read_fix()
    adopt(t, V)
  end
  local fresh = freshness(t, S.map_open)
  local hi, lo
  known, hi, lo = level(M)
  tell(t, V, known, lo, hi)
  -- the hold: carried on by this frame's write; dropped when the level leaves -1, and at the close
  if hold.on then
    if not S.map_open then hold_drop(t, 'the map closed') else hold_advance(S, t) end
    if known == LO then hold.whole = true end
    if hold.whole and known ~= nil and known ~= LO then hold_drop(t, 'the zoom in from the whole map') end
  end

  VW.open = (live and V.top_now and map and map.cx and map.r and true) or false
  VW.level, VW.lo, VW.hi = known, lo, hi
  if not VW.open then
    VW.trusted, VW.n, VW.held, VW.settled, VW.fade = false, 0, false, false, 0
    shown_ok, ease_rate, nofix_since = false, 0, nil
    if C.LEGEND == 'always' then legend(T.mod.track, T.mod.objectives) end   -- the legend while the map is closed
    return
  end

  -- the zoom eases toward the level's k (in x2 steps per ZOOM_EASE s)
  local drawn = drawn_level(V, t, known, lo)
  local zk = kz(drawn or hi)
  target = log2(zk)
  local stepz = (S.dt or 0) / ZOOM_EASE
  local gap = target - shown
  if abs(gap) <= stepz then shown = target elseif gap > 0 then shown = shown + stepz else shown = shown - stepz end
  local zoomed = shown == target
  VW.k = zoomed and zk * s or 2 ^ shown * s
  VW.r, mcx, mcy = map.r, map.cx, map.cy

  place(S, t, drawn, lo, hi, fresh, zoomed)

  local tr = T.mod.track
  if VW.trusted then clusters(S, tr, s) else VW.n = 0 end
  legend(tr, T.mod.objectives)
end

return VW
