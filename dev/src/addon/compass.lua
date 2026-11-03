local T, chef = ...
-- The nearest valuables on the game's compass (the 0.8 mock): up to MAX_PIPS piles of C.VALUABLE kinds as small icons
-- just above the strip at their bearing from me (relative to where I look), each with a short tick down to the strip
-- and its distance to its right ("97 M"). Nearest first; a pile within SPACING of one already shown, or whose label
-- would touch one, is left out (so a kind's piles in one direction show once). My waypoints (pings) come first, at
-- any distance (clamped to the strip's ends), in ping cyan: a loot waypoint with its pile's icon, any other with the
-- waypoint glyph. No marks, no bare numbers, no edge chevrons. Drawn while the map is open too (the game keeps its
-- compass); hidden with F7. Layers 951-958.
-- The geometry is the game's own, measured from screenshots (1920x1080, HUD Scale 0.9, compass 0, width 1, range 2):
-- the strip is 539 px long, 27 px per 10 degrees, its middle 39 px from the top; the heading box hangs under its center.
-- Everything is in screen heights, so any resolution works; HUD Scale scales it about the top center. The other compass
-- width and angle range settings aren't measured: they scale in proportion and are logged once.
local M = {}
local C, D = T.mod.config, T.mod.draw
local floor, max, min, abs, sqrt, atan2, deg = math.floor, math.max, math.min, math.abs, math.sqrt, math.atan2, math.deg
local sort, fmt = table.sort, string.format

-- ------------------------------------------------------------------ geometry (all of it, measured)
M.GEO = {
  ref_scale = 0.9,   -- the HUD Scale the numbers below were measured at
  mid = 0.0361,      -- the strip's middle (the game's markers sit on it), screen heights below the top (39 px at 1080)
  bottom = 0.0458,   -- the strip's bottom edge (49.5 px)
  half = 0.2495,     -- half the strip's length at Width 1 (269.5 px)
  box = 0.0620,      -- the heading box's bottom (67 px); it spans x within BOX_HALF of the center
  box_half = 0.022,  -- half the heading box's width, with a margin (it's about 40 px wide)
  icon = 0.0155,     -- icon size (about 17 px at 1080p; the strip is 21 px tall)
  cap = 0.0085,      -- distance text cap height (about 9 px at 1080p)
  gap = 0.003,       -- the strip (or the heading box) to the distance text
  edge = 0.012,      -- the chevron's center past the strip's end
  dot = 0.0095,      -- an edge dot's texture size (the disc inside is about 60% of it)
  -- per HUD setting (raw value -> number); only the defaults are measured (MEASURED), the rest scale in proportion
  width = { [0] = 0.75, [1] = 1.0, [2] = 1.25 },                    -- hud_compass_width: the strip's length (1 MEASURED)
  range = { [0] = 66.4, [1] = 83.0, [2] = 99.6, [3] = 132.8 },      -- hud_compass_angle_range: degrees each side (2 MEASURED)
  style = { [0] = 0 },                                              -- hud_compass: the strip moved down (0 MEASURED)
}
local GEO = M.GEO
local DEFAULT = { hud_compass_width = 1, hud_compass_angle_range = 2, hud_compass = 0 }
local MEASURED = { hud_compass_width = 1, hud_compass_angle_range = 2, hud_compass = 0 }

local EMPTY = {}

local noted = { hud_compass_width = {}, hud_compass_angle_range = {}, hud_compass = {} }
local function setting(raw, key, t)
  local v = raw[key]
  local r = v ~= nil and t[v] or nil
  if v ~= nil and v ~= MEASURED[key] and not noted[key][v] then
    noted[key][v] = true
    chef.log('compass: %s = %s is not measured; %s', key, tostring(v),
      r ~= nil and 'scaled from the measured default' or 'using the default geometry')
  end
  if r ~= nil then return r end
  return t[DEFAULT[key]]
end
local function hud_scale()
  local H = T.mod.hud
  local s = H and H.scale and H.scale()
  return type(s) == 'number' and s or GEO.ref_scale
end

local geo = { cx = 0, y = 0, half = 1, span = 99.6, line = 0, top = 0, bottom = 0, box = 0, box_half = 0, k = 1 }
local logged = { cx = nil, y = nil, half = nil, span = nil }

-- M.geometry(S) -> { cx, y, half, span, line, top, bottom, box, box_half, k }: screen px, bottom-left origin. cx: the
-- strip's center x; y: its middle (the pip row); line: the same (the old name); top, bottom: its edges; box: the heading
-- box's bottom, box_half its half width; half: px from the center to either end; span: degrees from the center to
-- either end; k: the size factor (HUD scale / ref). The table is reused: read it before the next call.
function M.geometry(S)
  local hud = T.mod.hud
  local r = hud and hud.raw or EMPTY
  local h = S.h
  local k = hud_scale() / GEO.ref_scale
  local g = geo
  local wf = setting(r, 'hud_compass_width', GEO.width)
  local down = setting(r, 'hud_compass', GEO.style)
  g.cx, g.k = S.w / 2, k
  g.half = GEO.half * h * wf * k
  g.span = setting(r, 'hud_compass_angle_range', GEO.range)
  g.y = h - (GEO.mid * k + down) * h
  g.line = g.y
  g.bottom = h - (GEO.bottom * k + down) * h
  g.top = g.y + (g.y - g.bottom)
  g.box = h - (GEO.box * k + down) * h
  g.box_half = GEO.box_half * h * k
  return g
end

local function log_geometry(g, S)
  if logged.cx and abs(logged.cx - g.cx) < 0.5 and abs(logged.y - g.y) < 0.5 and abs(logged.half - g.half) < 0.5
     and logged.span == g.span then return end
  logged.cx, logged.y, logged.half, logged.span = g.cx, g.y, g.half, g.span
  chef.log('compass: %dx%d, center x %d, middle %d px from the top, %d px for %g degrees each side (%.2f px/deg)',
    floor(S.w + 0.5), floor(S.h + 0.5), floor(g.cx + 0.5), floor(S.h - g.y + 0.5), floor(g.half + 0.5), g.span,
    g.half / g.span)
end
-- ------------------------------------------------------------------ strings (made once)
local dist_s, km_s, num_s = {}, {}, {}
local function dist_str(d)
  local m = floor(d + 0.5)
  if m < 1000 then
    local s = dist_s[m]
    if not s then s = D.dist(m); dist_s[m] = s end
    return s
  end
  local t = floor(d / 100 + 0.5)
  local s = km_s[t]
  if not s then s = fmt('%.1f KM', t / 10); km_s[t] = s end
  return s
end
M.dist_str = dist_str
local function num_str(n)
  local s = num_s[n]
  if not s then s = tostring(n); num_s[n] = s end
  return s
end
M.num_str = num_str

local function rel_deg(dx, dy, heading_deg)
  return (deg(atan2(dx, dy)) - heading_deg + 540) % 360 - 180
end

-- ------------------------------------------------------------------ the pips (the 0.8 mock)
-- Sizes in px at 1080p and HUD Scale 0.9 (times S.h / 1080 * k), measured up from the strip's top edge: the icon's
-- center and size, the tick (from just inside the strip up to under the icon) and its widths, the distance text's
-- middle, cap height and its x past the pip's center
local ICON_Y, ICON = 12.5, 14
local TICK0, TICK1, TICK_W, TICK_WP = -0.5, 4, 1.4, 2.0
local TEXT_Y, TEXT_CAP, TEXT_DX = 12, 7.9, 9.5
local MAX_PIPS = 4         -- the nearest valuables, my waypoints counted among them
local SPACING = 40         -- px at 1080p: a pile nearer than this to one already shown is left out
local PAD = 4              -- px at 1080p kept clear around each pip's icon and label
local WP_MATCH = 1.5       -- m: a pile this close (past its kind's stack radius) to a loot waypoint is that waypoint

local cand, n_cand = {}, 0          -- valuable piles in the strip's span: { m, d, rel, a }
local cpool = {}
local spans_a, spans_b, spans_x, n_spans = {}, {}, {}, 0   -- the pips placed this frame: extents (icon to label), x

local by_dist = function(a, b) return a.d < b.d end

-- the pip's extent (its icon's left edge to its label's right end) is free of the ones placed and SPACING from them
local function free(x, a, b, sp)
  for i = 1, n_spans do
    if (a < spans_b[i] and b > spans_a[i]) or abs(x - spans_x[i]) < sp then return false end
  end
  return true
end
local function take(x, a, b)
  n_spans = n_spans + 1
  spans_a[n_spans], spans_b[n_spans], spans_x[n_spans] = a, b, x
end

local function on_waypoint(m, wps)
  if not wps then return false end
  for i = 1, #wps do
    local w = wps[i]
    if type(w) == 'table' and w.kind == m.kind and w.x and w.y then
      local r = (m.kind.stack or 0) + WP_MATCH
      if (w.x - m.x) ^ 2 + (w.y - m.y) ^ 2 <= r * r then return true end
    end
  end
  return false
end

-- one pip: the tick, then (parts 2) the icon (a kind's, or the waypoint glyph), then (parts 3) the distance
local function pip(x, top, s, kind, d, a, wp, parts)
  local RGB = C.RGB
  local rgb = wp and RGB.ping or RGB.text
  local tw = max(1, floor((wp and TICK_WP or TICK_W) * s + 0.5))
  local ty = floor(top + TICK0 * s + 0.5)
  local th = max(2, floor((TICK1 - TICK0) * s + 0.5))
  D.rect(floor(x - tw / 2 + 0.5), ty, tw, th, D.rgb(rgb, floor(230 * a + 0.5)), wp and 955 or 951)
  if parts < 2 then return end
  local iy, isz, alpha = top + ICON_Y * s, ICON * s, floor(255 * a + 0.5)
  if kind then
    D.icon(kind, x, iy, isz, alpha, wp and 957 or 952)
  else
    local c = RGB.ping
    if D.has('ping/wp') then
      D.texc('ping/wp', x, iy, isz, isz, D.color(c[1], c[2], c[3], alpha), 957)
    else
      local P = T.mod.pings
      if P and type(P.icon) == 'function' then pcall(P.icon, x, iy, isz, alpha, 957) end
    end
  end
  if parts < 3 then return end
  local cap = TEXT_CAP * s
  D.text(x + TEXT_DX * s, top + TEXT_Y * s - cap / 2, dist_str(d), cap, D.rgb(rgb, alpha), wp and 958 or 954, 'l')
end

-- ------------------------------------------------------------------ draw
function M.draw(S)
  if not C.COMPASS or S.hidden then return end
  local g = M.geometry(S)
  log_geometry(g, S)
  local s = S.h / 1080 * g.k
  local cx, half, span, top = g.cx, g.half, g.span, g.top
  local me, t = S.me, S.t
  local hd = deg(S.heading)
  local cap = TEXT_CAP * s
  local sp, pad = SPACING * s, PAD * s
  local left, right = ICON * s / 2 + pad, TEXT_DX * s + pad
  n_spans = 0
  local shown = 0

  -- 1. my waypoints: always, at any distance (past an end: at that end)
  local P = T.mod.pings
  local wps = P and type(P.waypoints) == 'table' and P.waypoints or nil
  if wps then
    for i = 1, #wps do
      local w = wps[i]
      if shown < MAX_PIPS and type(w) == 'table' and w.x and w.y then
        local dx, dy = w.x - me.x, w.y - me.y
        local d = sqrt(dx * dx + dy * dy)
        local x = cx + max(-span, min(span, rel_deg(dx, dy, hd))) / span * half
        local k = w.kind
        local loot = type(k) == 'table' and k.id and C.VALUABLE[k.id] and k or nil
        -- one that would touch an earlier waypoint's pip drops its distance, then its icon (the tick stays)
        local a, b, parts = x - left, x + right + D.text_w(dist_str(d), cap), 3
        if not free(x, a, b, 0) then
          b, parts = x + left, 2
          if not free(x, a, b, 0) then a, b, parts = x, x, 1 end
        end
        pip(x, top, s, loot, d, 1, true, parts)
        take(x, a, b)
        shown = shown + 1
      end
    end
  end

  -- 2. the valuable piles in the strip's span, nearest first
  local n = 0
  local tr = T.mod.track
  if shown < MAX_PIPS and tr and not tr.stale and tr.stacks then
    local stacks = tr.stacks
    for i = 1, #stacks do
      local m = stacks[i]
      local k = m.kind
      if m.n > 0 and k and C.VALUABLE[k.id] then
        local a = tr.alpha(m, t)
        if a then
          local dx, dy = m.x - me.x, m.y - me.y
          local rel = rel_deg(dx, dy, hd)
          if rel >= -span and rel <= span and not on_waypoint(m, wps) then
            n = n + 1
            local e = cpool[n]
            if not e then e = {}; cpool[n] = e end
            e.m, e.d, e.rel, e.a = m, sqrt(dx * dx + dy * dy), rel, a
            cand[n] = e
          end
        end
      end
    end
  end
  for i = n + 1, n_cand do cand[i] = nil end
  n_cand = n
  if n > 1 then sort(cand, by_dist) end

  for i = 1, n do
    if shown >= MAX_PIPS then break end
    local e = cand[i]
    local x = cx + e.rel / span * half
    local a, b = x - left, x + right + D.text_w(dist_str(e.d), cap)
    if free(x, a, b, sp) then
      pip(x, top, s, e.m.kind, e.d, e.a, false, 3)
      take(x, a, b)
      shown = shown + 1
    end
  end
end

function M.reset(S)
  n_cand, n_spans = 0, 0
  for i = 1, #cand do cand[i] = nil end
end

return M
