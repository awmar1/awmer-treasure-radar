local T, chef = ...
-- World markers in the game's ping style, over the loot near me (track.pickups within config.MARKERS m, 3D from my
-- feet). A pin is a ground dot on the pickup, a thin stem up to a thin diamond holding the kind's icon, and the
-- distance above it ("18 M"), all in cream; a pin on my waypoint (pings.lua) in ping cyan. Supplies get a smaller
-- pin, piles a count ("x2") at the diamond's lower right, and far pins fade and shrink a little. Pins keep their size
-- on screen (like the game's pings); nearer pins sit on top. Shown while S.markers_on; not while F7 hides the mod's
-- views, the map is open (it covers them) or the loot list is stale. Textures: pin/disc (the diamond), pin/dot
-- (dev/src/art/pin.py), icons/*. Layers 860-899.
--
-- Export, for other views (waypoint pins):
--   markers.pin(S, x, y, z, opts) -> drawn, cx, cy, top
--     One pin at a world point (z = the ground under it). opts (a table; every field optional, nil = {}):
--       kind    a kind record: its icon in the diamond (D.icon; loot icons carry their colors, so no tint)
--       tint    {r, g, b}: tint the kind's icon (white textures, e.g. map/*)
--       icon    function(cx, cy, size, alpha, layer): draws the diamond's glyph instead of a kind (e.g. pings.icon)
--       text    the line above the diamond (uppercase, the glyph set); default the distance ("18 M"); false = none
--       n       a pile's count, shown when > 1
--       small   true: the smaller supply-size pin
--       alpha   0..1, multiplies the pin's own fade (default 1)
--       dist    meters, for the text and the far fade (default: 3D from my feet)
--       range   where the far look is full (default config.MARKERS, or 50)
--       layer   the pin's base layer (it uses layer .. layer + 4); default by distance in 862-896, nearer on top
--       wp      true: my waypoint's colors (ping cyan); also when x, y is one of pings.waypoints
--     Returns false when the point is behind me or off screen, else true, the diamond's center (screen pixels,
--     bottom-left origin, e.g. for D.hit) and the pin's top edge (its text's top; the diamond's with text = false).
--   markers.scale(S, d, range) -> u, k, f
--     A pin's size d meters away (range as in opts): u pixels per unit (from S.h and the HUD scale), k the far
--     shrink (1 near, 0.8 far) and f how far into the far look it is (0..1). A pin's sizes are in units of u * k.
--   markers.rise(small) -> units (of u * k) from the ground dot's center up to the top of the pin's text
local M = {}
local C, D = T.mod.config, T.mod.draw
local floor, max, min, sqrt, abs = math.floor, math.max, math.min, math.sqrt, math.abs

-- in units (u pixels each, from S.h): the diamond's center-to-corner size (disc), icon size, stem length, dot radius,
-- text cap height, text baseline above the diamond's center
local BIG = { disc = 12, icon = 11.5, stem = 11, dot = 1.8, cap = 7.9, base = 16 }
local SMALL = { disc = 8.5, icon = 8.5, stem = 7, dot = 1.5, cap = 6.5, base = 11.5 }
local DISC_SPAN = 64 / 26       -- pin/disc: the diamond's corners 26 px from the center of a 64 px texture
local DOT_SPAN = 16 / 5         -- pin/dot: a 5 px disc radius in a 16 px texture
local LIFT = 0.05               -- the ground dot's height over the pickup's origin (m)
local WP_MATCH = 1.5            -- m: a pile this close (past its kind's stack radius) to a loot waypoint is that waypoint

-- x, y is one of my waypoints (pings.lua): a far waypoint's pin, drawn by pings with markers.pin
local function is_waypoint(x, y)
  local P = T.mod.pings
  local W = P and type(P.waypoints) == 'table' and P.waypoints
  if not W then return false end
  for i = 1, #W do
    local w = W[i]
    if type(w) == 'table' and w.x and w.y and abs(w.x - x) < 0.01 and abs(w.y - y) < 0.01 then return true end
  end
  return false
end
-- the pickup p is on one of my waypoints: the waypoint's mark, or its kind's pile at the same spot
local function on_waypoint(p, W)
  for i = 1, #W do
    local w = W[i]
    if type(w) == 'table' then
      if w.mark == p then return true end
      if w.kind == p.kind and w.x and w.y then
        local r = (p.kind.stack or 0) + WP_MATCH
        if (w.x - p.x) ^ 2 + (w.y - p.y) ^ 2 <= r * r then return true end
      end
    end
  end
  return false
end

local dists = {}                -- '18 M' by whole meter, made once
local function dist_text(d)
  if d >= 999.5 then return D.dist(d) end
  local m = floor(d + 0.5)
  local s = dists[m]
  if not s then s = D.dist(m); dists[m] = s end
  return s
end
local count_strs = {}
local function count_str(n)
  local s = count_strs[n]
  if not s then s = tostring(n); count_strs[n] = s end
  return s
end

function M.scale(S, d, range)
  local H = T.mod.hud
  local hs = H and H.scale and H.scale() / 0.85 or 1
  hs = max(0.75, min(1.5, hs))
  -- far: from 35% of the range out, down to 80% size
  local f = max(0, min(1, (d - 0.35 * range) / (0.65 * range)))
  return S.h / 770 * hs, 1 - 0.2 * f, f        -- u: 1.4 px at 1080p
end

function M.rise(small)
  local P = small and SMALL or BIG
  return P.dot + P.stem + P.disc + P.base + P.cap
end

local NONE = {}
function M.pin(S, x, y, z, opts)
  opts = opts or NONE
  if not chef.world_to_screen then return false end
  local gx, gy = chef.world_to_screen(x, y, (z or 0) + LIFT)
  if not gx then return false end
  local P = opts.small and SMALL or BIG

  local d = opts.dist
  if not d then
    local me = S.me
    d = sqrt((x - me.x) ^ 2 + (y - me.y) ^ 2 + ((z or 0) - me.z) ^ 2)
  end
  local range = opts.range or C.MARKERS or 50
  -- far: from 35% of the range out, down to 80% size and 55% alpha; the last 10% fades out
  local u, k, f = M.scale(S, d, range)
  local a = (1 - 0.45 * f) * (opts.alpha or 1) * C.MARKER_OPACITY
  if d > 0.9 * range then a = a * max(0, (range - d) / (0.1 * range)) end
  if a <= 0.02 then return false end

  local disc_r = P.disc * u * k
  local dot_r = P.dot * u * k
  local stem = P.stem * u * k
  local cx, cy = gx, gy + dot_r + stem + disc_r
  local str = opts.text
  if str == nil then str = dist_text(d) end
  local top = str and cy + (P.base + P.cap) * u * k or cy + disc_r
  if cx < -disc_r or cx > S.w + disc_r or top < 0 or gy - dot_r > S.h then return false end

  local layer = opts.layer
  if not layer then layer = 862 + 5 * floor(max(0, min(6, (1 - d / range) * 7))) end
  local text = (opts.wp or is_waypoint(x, y)) and C.RGB.ping or C.RGB.text
  local A = floor(255 * a)
  -- ground dot, stem, diamond, glyph, text
  local ds = 2 * dot_r * DOT_SPAN
  D.texc('pin/dot', gx, gy, ds, ds, D.color(text[1], text[2], text[3], floor(204 * a)), layer)
  local sw = max(1, floor(u * 0.7 + 0.5))
  local s0 = gy + dot_r * 0.6
  D.rect(floor(gx - sw / 2 + 0.5), s0, sw, cy - disc_r - s0, D.color(text[1], text[2], text[3], floor(128 * a)), layer)
  local span = DISC_SPAN * disc_r
  D.texc('pin/disc', cx, cy, span, span, D.color(text[1], text[2], text[3], A), layer + 1)
  local isz = P.icon * u * k
  if opts.icon then
    pcall(opts.icon, cx, cy, isz, A, layer + 2)
  elseif opts.kind then
    D.icon(opts.kind, cx, cy, isz, A, layer + 2, opts.tint)
  end
  local c = D.color(text[1], text[2], text[3], A)
  if str then D.text(cx, cy + P.base * u * k, str, P.cap * u * k, c, layer + 3, 'c') end
  local n = opts.n
  if n and n > 1 then
    local ccap = P.cap * 0.78 * u * k
    local nx, ny = cx + disc_r * 0.62, cy - disc_r * 0.92
    local w = D.text(nx, ny, 'X', ccap * 0.72, c, layer + 3)
    D.text(nx + w + 0.12 * ccap, ny, count_str(n), ccap, c, layer + 3)
  end
  return true, cx, cy, top
end

-- the loot's pins
local opts = {}                 -- reused every frame
function M.draw(S)
  local range = C.MARKERS
  if not range or not S.markers_on or S.hidden or S.map_open then return end
  local tr = T.mod.track
  if not tr or tr.stale or not chef.world_to_screen then return end
  local me = S.me
  local r2 = range * range
  local P = T.mod.pings
  local W = P and type(P.waypoints) == 'table' and #P.waypoints > 0 and P.waypoints or nil
  opts.range = range
  for _, p in ipairs(tr.pickups) do
    local a = tr.alpha(p, S.t)
    if a then
      local d2 = (p.x - me.x) ^ 2 + (p.y - me.y) ^ 2 + (p.z - me.z) ^ 2
      if d2 <= r2 then
        local k = p.kind
        opts.kind, opts.n, opts.small, opts.alpha, opts.dist = k, p.n, k.supply, a, sqrt(d2)
        opts.wp = W ~= nil and on_waypoint(p, W)
        M.pin(S, p.x, p.y, p.z, opts)
      end
    end
  end
end

return M
