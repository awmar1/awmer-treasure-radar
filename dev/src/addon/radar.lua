local T, chef = ...
-- The corner radar while the map is closed: a miniature of the game's own map. A dark disc with one thin cream rim,
-- the game's 65 m grid (a faint "+" at each crossing, anchored on the world origin as the map's is, so it slides past
-- as I move), my yellow dot and a faint view cone, and a small north tick on the rim with an N inside it. No sonar
-- rings, no bearing ticks, no blobs.
--   loot       track.stacks within the range as small icons (a count on piles); none past the range or while
--              track.stale
--   rings      nests and structures (T.mod.objectives.marks) within the range: a small hollow ring in kind.rgb, as
--              on the game's map before it shows its own icon; a done one dim, with objectives.done_tex(mark) on it
--   marks      objectives, side objectives and extraction as their map/* icons tinted kind.rgb (side objectives
--              C.RGB.side), held just inside the rim past the range; points of interest within the range only
--   waypoints  T.mod.pings.waypoints on top, the waypoint glyph in ping cyan, held inside the rim the same way
-- Heading up by default (Arsenal: Rotate With View): my cone points up and the grid, the rings and the N turn round
-- me; north up otherwise. Smaller than 0.7 and moved up the right edge, clear of the game's chat lines and chat box
-- (M.place; dev/harness/chat_check.py checks it at 1080p, 1440p and 2160p for each Size). Hidden while the map is
-- open (the map is the big view then).
-- Zoom: the numpad's + and - step through ZOOMS, as in 0.5.1 (remembered between launches, same file and format).
-- Textures: radar/* (dev/src/art/radar.py), icons/* (icons.py), map/* (the map kinds), ping/wp (ping.py). Layers
-- 900-949.
-- Exports: radar.range() -> the range now (meters from me to the rim); radar.place(S) -> cx, cy, R (screen px,
-- bottom-left origin: where the radar is drawn).
local M = {}
local C, D = T.mod.config, T.mod.draw
local floor, ceil, max, sqrt, sin, cos, pi = math.floor, math.ceil, math.max, math.sqrt, math.sin, math.cos, math.pi
local fmt = string.format

-- The textures' geometry (radar.py). Units are R/100 (the mockup's: the rim's radius is 100 units).
-- rim: RIM px across, the rim RIM_PX from its center; disc: the same, DISC and DISC_PX.
local RIM, RIM_PX, DISC, DISC_PX = 256, 124, 128, 62
-- cone/NN: CONE_U units across, centered CONE_OFF units out from the apex along frame NN's bearing
local CONE_U, CONE_OFF, CONE_FRAMES = 28, 13, 32
local ME_U = 13                            -- my dot (32 px at 2 px a unit in radar.py), drawn a little smaller
local CROSS_U, CROSS_FRAMES = 10, 8        -- a grid crossing, 8 frames over 90 degrees (a "+" repeats every 90)
local RING_U = 12.5                        -- a nest or structure ring (the ring is 12/32 of it in radius)
local NORTH_U, NORTH_FRAMES = 12, 32       -- the north tick (24 px for 12 units)
local GRID = 65                            -- the game's map grid, meters, anchored on the world origin
local GRID_MIN = 22                        -- px at 1080p: the grid doubles until its crossings are this far apart
local CONE_NAMES, CROSS_NAMES = {}, {}
for i = 1, CONE_FRAMES do CONE_NAMES[i] = fmt('radar/cone/%02d', i) end
for i = 1, CROSS_FRAMES do CROSS_NAMES[i] = fmt('radar/cross/%02d', i) end
local DARK = { 11, 14, 16 }
local SIZES = { [0.6] = 'small', [0.75] = 'medium', [1.0] = 'large' }
local RING_CAT = { nest = true, structure = true }
local CLAMP_CAT = { objective = true, side_objective = true, extract = true }   -- held inside the rim past the range

-- ------------------------------------------------------------------ placement
-- The radar's radius at Size: large and its rim's gap to the HUD's right edge, in screen heights; CHAT_TOP is the top
-- of the game's chat (its lines and box, measured at HUD Scale 0.9 and scaled with a larger one), CHAT_GAP the space
-- kept above it. 1080p, medium: radius 109 px, center 1767, 527 from the bottom left.
local RADIUS, EDGE, CHAT_TOP, CHAT_GAP = 0.135, 0.04, 0.375, 0.012
M.RADIUS, M.EDGE, M.CHAT_TOP, M.CHAT_GAP = RADIUS, EDGE, CHAT_TOP, CHAT_GAP

function M.place(S)
  local H = T.mod.hud
  local h, right = S.h, S.w
  if H and H.sides then local _, r = H.sides(S.w, h); right = r end
  local k = H and H.scale and max(1, H.scale() / 0.9) or 1
  local R = RADIUS * h * C.MAP_SCALE
  return right - EDGE * h - R, (CHAT_TOP * k + CHAT_GAP) * h + R, R
end

-- ------------------------------------------------------------------ zoom (the numpad's + and -), as in 0.5.1
-- The range steps through ZOOMS. The Arsenal range is where it starts; the last zoom is remembered between launches
-- in %LOCALAPPDATA%\treasure_radar_zoom.txt ("<range> <the Arsenal range it was zoomed from>": a new Arsenal pick
-- starts over). The file's place is looked up in init, so the simulator can move it.
local ZOOMS = { 50, 75, 100, 150, 200, 250, 300, 400, 500 }
local ZOOM_IN_KEYS = { 'numpad +', 'num +', 'numpad plus' }      -- the numpad's (the main row's keys don't register)
local ZOOM_OUT_KEYS = { 'numpad -', 'num -', 'numpad minus' }
local RANGE = C.RANGE
local ZOOM_FILE = nil
local range_now = RANGE
local note_text, note_until = nil, 0

local function load_zoom()
  local ok, dir = pcall(os.getenv, 'LOCALAPPDATA')
  if ok and type(dir) == 'string' and dir ~= '' then ZOOM_FILE = dir .. '\\treasure_radar_zoom.txt' end
  if not ZOOM_FILE then return end
  local okf, f = pcall(io.open, ZOOM_FILE, 'r')
  if okf and f then
    local v, base = (f:read('*l') or ''):match('^(%d+)%s+(%d+)')
    f:close()
    v, base = tonumber(v), tonumber(base)
    if v and base == RANGE and v >= 25 and v <= 1000 then range_now = v end
  end
end
local function set_range(v)
  range_now = v
  note_text, note_until = v .. ' M', chef.time() + 2
  if ZOOM_FILE then
    local okf, f = pcall(io.open, ZOOM_FILE, 'w')
    if okf and f then f:write(tostring(v), ' ', tostring(RANGE), '\n'); f:close() end
  end
  chef.log('radar range: %d m', v)
end
local function zoom_step(dir)
  if dir < 0 then
    for i = #ZOOMS, 1, -1 do if ZOOMS[i] < range_now then set_range(ZOOMS[i]); return end end
  else
    for i = 1, #ZOOMS do if ZOOMS[i] > range_now then set_range(ZOOMS[i]); return end end
  end
end
local function any_key(list)
  for i = 1, #list do if chef.key_pressed(list[i]) then return true end end
  return false
end

function M.range() return range_now end

-- ------------------------------------------------------------------ life cycle
local placed = { w = -1, h = -1, x = -1, y = -1, r = -1 }   -- the placement last logged (once a mission, or on change)
local icon_failed = false           -- pings.icon raised an error: waypoints stay off the radar this session
local counts = {}                   -- count strings '2', '3', ... made once

function M.init()
  if not C.RADAR then return end
  load_zoom()
  chef.log('radar: %s, %s, range %d m%s', SIZES[C.MAP_SCALE] or tostring(C.MAP_SCALE),
    C.ROTATE and 'turning with my view' or 'north up', range_now,
    range_now ~= RANGE and fmt(' (zoomed; Arsenal %d m)', RANGE) or '')
end

function M.reset(S) placed.w = -1 end

function M.update(S)
  if not C.RADAR or S.hidden or S.map_open then return end
  if any_key(ZOOM_IN_KEYS) then zoom_step(-1) elseif any_key(ZOOM_OUT_KEYS) then zoom_step(1) end
end

-- an objective mark's alpha, as track.alpha (n may be missing: there); a done mark keeps n = 0 and stays (drawn as
-- done), any other mark whose units are all gone fades out over C.FADE
local function mark_alpha(m, t)
  if m.state == 'done' or (m.n or 1) > 0 then return 1 end
  if not m.gone_t then return nil end
  local a = 1 - (t - m.gone_t) / C.FADE
  if a <= 0 then return nil end
  return a
end

-- the waypoint glyph in ping cyan; pings.icon if the texture is missing (a raise there turns waypoints off)
local function waypoint(x, y, size)
  local c = C.RGB.ping
  if D.has('ping/wp') then D.texc('ping/wp', x, y, size, size, D.color(c[1], c[2], c[3], 255), 934); return true end
  local P = T.mod.pings
  if icon_failed or not (P and type(P.icon) == 'function') then return false end
  local ok, err = pcall(P.icon, x, y, size, 255, 934)
  if not ok then
    icon_failed = true
    chef.log('radar: pings.icon failed (%s); waypoints stay off the radar', tostring(err))
  end
  return ok
end

-- ------------------------------------------------------------------ draw
function M.draw(S)
  if not C.RADAR or S.hidden or S.map_open then return end
  local cx, cy, R = M.place(S)
  local u = R / 100
  if placed.w ~= S.w or placed.h ~= S.h or placed.x ~= floor(cx) or placed.y ~= floor(cy) or placed.r ~= floor(R) then
    placed.w, placed.h, placed.x, placed.y, placed.r = S.w, S.h, floor(cx), floor(cy), floor(R)
    chef.log('screen %dx%d: radar at %d, %d (from the bottom left), radius %d, %s', S.w, S.h, floor(cx), floor(cy),
      floor(R), C.ROTATE and 'turning with my view' or 'north up')
  end
  local rotate = C.ROTATE
  local fx, fy = S.fx, S.fy
  local north = rotate and -S.heading or 0          -- north's bearing on screen, clockwise from up
  local text, me_rgb = C.RGB.text, C.RGB.me
  local scale = (R - 7 * u) / range_now            -- px a meter: the range lands 7 units inside the rim
  local mx, my = S.me.x, S.me.y

  -- the panel and its rim
  local pa = D.A(175)
  if pa > 0 then
    local ds = R * DISC / DISC_PX
    D.texc('radar/disc', cx, cy, ds, ds, D.color(DARK[1], DARK[2], DARK[3], pa), 900)
  end
  local rs = R * RIM / RIM_PX
  D.texc('radar/rim', cx, cy, rs, rs, D.color(255, 255, 255, 255), 902)

  -- the game's grid: a faint "+" at each crossing inside the rim, the crossings GRID m apart (doubled when zoomed out)
  local step = GRID
  while step * scale < GRID_MIN * S.h / 1080 do step = step * 2 end
  local reach = (R - 6 * u) / scale                -- meters from me to the last crossing drawn
  local i0, i1 = ceil((mx - reach) / step), floor((mx + reach) / step)
  local j0, j1 = ceil((my - reach) / step), floor((my + reach) / step)
  if (i1 - i0 + 1) * (j1 - j0 + 1) <= 400 then
    local cname = CROSS_NAMES[floor((north % (pi / 2)) / (pi / 2) * CROSS_FRAMES + 0.5) % CROSS_FRAMES + 1]
    local csz, cc, reach2 = CROSS_U * u, D.color(text[1], text[2], text[3], 80), reach * reach
    for i = i0, i1 do
      for j = j0, j1 do
        local dx, dy = i * step - mx, j * step - my
        if dx * dx + dy * dy <= reach2 then
          if rotate then dx, dy = dx * fy - dy * fx, dx * fx + dy * fy end
          D.texc(cname, cx + dx * scale, cy + dy * scale, csz, csz, cc, 901)
        end
      end
    end
  end

  -- my view cone
  local ci = rotate and 1 or floor((S.heading % (2 * pi)) / (2 * pi) * CONE_FRAMES + 0.5) % CONE_FRAMES + 1
  local ca = (ci - 1) * 2 * pi / CONE_FRAMES        -- that frame's bearing: its center sits out along it
  D.texc(CONE_NAMES[ci], cx + sin(ca) * CONE_OFF * u, cy + cos(ca) * CONE_OFF * u, CONE_U * u, CONE_U * u,
    D.color(me_rgb[1], me_rgb[2], me_rgb[3], 70), 903)

  -- nests and structures (rings), objectives and extraction (icons), under the loot
  local O = T.mod.objectives
  if O and type(O.marks) == 'table' then
    local size, rsz = max(12, 12 * u), max(11, RING_U * u)
    local dim, side, done_rgb = C.RGB.dim, C.RGB.side, C.RGB.done
    local done_tex = type(O.done_tex) == 'function' and O.done_tex
    for _, m in ipairs(O.marks) do
      local k = m.kind
      local a = type(k) == 'table' and k.on ~= false and type(m.x) == 'number' and type(m.y) == 'number' and mark_alpha(m, S.t)
      if a then
        local dx, dy = m.x - mx, m.y - my
        if rotate then dx, dy = dx * fy - dy * fx, dx * fx + dy * fy end
        local d = sqrt(dx * dx + dy * dy)
        local ring, clamp = RING_CAT[k.cat], CLAMP_CAT[k.cat]
        if d <= range_now or clamp then
          if d > range_now then dx, dy = dx / d * range_now, dy / d * range_now end
          local sx, sy, A = cx + dx * scale, cy + dy * scale, floor(255 * a)
          local done = m.state == 'done'
          local rgb = done and dim or (k.cat == 'side_objective' and side) or k.rgb
          local sz = ring and rsz or size
          if ring then
            D.texc('radar/ring', sx, sy, sz, sz, D.color(rgb[1], rgb[2], rgb[3], A), 906)
          else
            D.icon(k, sx, sy, sz, A, 908, rgb)
          end
          if done and done_tex then
            local ok, tex = pcall(done_tex, m)
            if ok and type(tex) == 'string' then
              local osz = 0.62 * sz
              D.texc(tex, sx + 0.42 * sz, sy - 0.3 * sz, osz, osz, D.color(done_rgb[1], done_rgb[2], done_rgb[3], A), 909)
            end
          end
        end
      end
    end
  end

  -- the loot within the range, least important first (track sorts the stacks) and each kind on its own layer, so
  -- the more important one is on top where icons overlap
  local tr = T.mod.track
  if tr and not tr.stale then
    local loot_size, supply_size = max(11, 11 * u), max(8, 8.5 * u)
    local cap = max(7.9, 5.5 * u)
    local range2 = range_now * range_now
    for _, s in ipairs(tr.stacks) do
      local a = tr.alpha(s, S.t)
      if a then
        local k = s.kind
        local dx, dy = s.x - mx, s.y - my
        if dx * dx + dy * dy <= range2 then
          if rotate then dx, dy = dx * fy - dy * fx, dx * fx + dy * fy end
          local sx, sy = cx + dx * scale, cy + dy * scale
          local size = k.supply and supply_size or loot_size
          local alpha = floor(255 * a)
          D.icon(k, sx, sy, size, alpha, 921 - (k.rank or 9))
          if s.n > 1 then
            local str = counts[s.n]
            if not str then str = tostring(s.n); counts[s.n] = str end
            D.text(sx + size * 0.42, sy - size * 0.62, str, cap, D.color(text[1], text[2], text[3], alpha), 923)
          end
        end
      end
    end
  end

  -- waypoints (pings.lua) on top; past the range just inside the rim
  local P = T.mod.pings
  if P and type(P.waypoints) == 'table' then
    local size = max(13, 12 * u)
    for _, w in ipairs(P.waypoints) do
      if type(w) == 'table' and type(w.x) == 'number' and type(w.y) == 'number' then
        local dx, dy = w.x - mx, w.y - my
        if rotate then dx, dy = dx * fy - dy * fx, dx * fx + dy * fy end
        local d = sqrt(dx * dx + dy * dy)
        if d > range_now then dx, dy = dx / d * range_now, dy / d * range_now end
        if not waypoint(cx + dx * scale, cy + dy * scale, size) then break end
      end
    end
  end

  -- me
  D.texc('radar/me', cx, cy, ME_U * u, ME_U * u, D.color(me_rgb[1], me_rgb[2], me_rgb[3], 255), 936)

  -- north: a small tick pointing out of the rim and an N just inside it
  local ns, ncap = max(10, NORTH_U * u), max(7.9, 8 * u)
  local sn, cn = sin(north), cos(north)
  D.texc(D.rot('radar/north', NORTH_FRAMES, north), cx + sn * (R + 2 * u), cy + cn * (R + 2 * u), ns, ns,
    D.color(text[1], text[2], text[3], 255), 938)
  local lx, ly = cx + sn * (R - 10 * u), cy + cn * (R - 10 * u)
  D.text(lx, ly - ncap / 2, 'N', ncap, D.color(text[1], text[2], text[3], 230), 939, 'c')

  -- the range for 2 s after a zoom, low on the left inside the rim
  if note_text and S.t < note_until then
    local ncap2 = max(8, 6 * u)
    D.text(cx - 0.55 * R, cy - 0.61 * R, note_text, ncap2, D.color(text[1], text[2], text[3], 165), 944, 'c')
  end
end

return M
