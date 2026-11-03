local T, chef = ...
-- Pings: help the player ping loot for the squad, and keep a few waypoints of my own (research 7.3).
--
-- 1. Ping assist (what the squad sees is the game's own ping: Q, CommunicationSpot, Tap). Every frame the tracked
--    pile (track.pickups, objectives.marks) nearest my crosshair by angle is P.aimed: in front of me, within
--    ASSIST_RANGE, inside a cone that widens up close (CONE_SIZE m around it, CONE_MIN..CONE_MAX), with hysteresis so
--    it doesn't flicker between two piles. It gets a thin cream bracket and, after a short dwell, a keycap with the
--    player's own ping key ("Q PING"). A tap of that key while aimed marks it pinged for PINGED_FOR s (the game's
--    ping time): the bracket dims and the keycap goes quiet. SPAM_N pings within SPAM_T s quiet every keycap for
--    SPAM_QUIET s. Nothing here presses a key, moves the aim or pings anything: the player does.
-- 2. Waypoints, only on my screen (P.waypoints: up to MAX_WP, the oldest replaced). The set key sets or clears one
--    on P.aimed (the map closed). A loot waypoint follows its pile across lists (track.near) and clears itself, with a
--    toast, once it's picked up or gone; an objective's once it's done. The clear key clears them all; a new mission
--    does too. Only keyboard keys set: never a mouse click or the wheel. 0.6's selection on the open map (numpad 7 / 9,
--    a hover ring and a tooltip) is gone in 0.7: the game's map cursor can't be read, and the game's map markers
--    aren't units, so there was nothing to point at but the mod's own marks.
-- 3. Drawing: waypoint pins in the world (markers.pin when markers is there, else my own), the bracket and keycap
--    (860-899), toasts (980-999; on the open map TOP + 975-979). Hidden with the mod's HUD (S.hidden); the logic
--    keeps running.
-- Exports: aimed, waypoints, icon(cx, cy, size, alpha, layer), pinged(mark), wants_loot(), keys.
-- Textures: ping/wp (dev/src/art/ping.py).
local P = {}
local C, D = T.mod.config, T.mod.draw
local sqrt, atan, atan2, acos = math.sqrt, math.atan, math.atan2, math.acos
local max, min, floor, abs, cos, sin, pi = math.max, math.min, math.floor, math.abs, math.cos, math.sin, math.pi
local fmt, upper, remove = string.format, string.upper, table.remove
local TOP = chef.TOP or 2000
local RGB = C.RGB

-- ------------------------------------------------------------------ tuning
local ASSIST_RANGE = 120        -- m, loot
local ASSIST_RANGE_MAP = 250    -- m, objectives and structures
local CONE_MIN, CONE_MAX = math.rad(2.5), math.rad(20)
local CONE_SIZE = 0.6           -- m around a pile the cone covers (so near piles get a wide cone)
local KEEP = 1.25               -- the aimed pile's cone is this much wider (hysteresis)
local COS_MAX = cos(CONE_MAX * KEEP)
local LIFT_LOOT, LIFT_MAP = 0.3, 1.5   -- m over a mark's origin the assist aims at
local TAP_MAX = 0.3             -- s: a ping key held longer is the comm wheel, not a ping
local PINGED_FOR = 6            -- s a ping lasts in game
local SPAM_N, SPAM_T, SPAM_QUIET = 3, 8, 8
local DWELL = 0.35              -- s on a pile before its keycap shows
local MAX_WP = 3
local MATCH = 1.5               -- m: a waypoint this close to a pile of its kind is that pile's
local RELINK = 3                -- m a pile may move between lists and still be the waypoint's
local TOAST_T = 2.5

-- ------------------------------------------------------------------ keys (keyboard only; see C.KEYS)
local KEYS = C.KEYS or {}
local function keyset(name, default)
  local k = KEYS[name] or default
  local list = { k }
  local n = k:match('^numpad (.+)$')
  if n then list[2] = 'num ' .. n end
  local label = upper(k):gsub('^NUMPAD ', 'NUM ')
  return { names = list, label = label }
end
local K_SET = keyset('wp_set', 'numpad 1')
local K_CLEAR = keyset('wp_clear', 'numpad 3')
P.keys = { set = K_SET, clear = K_CLEAR }
local function pressed(k)
  local l = k.names
  for i = 1, #l do if chef.key_pressed(l[i]) then return true end end
  return false
end
-- keep only the names the engine knows, when it says which it knows
local function prune(k)
  local known = {}
  for _, n in ipairs(k.names) do
    if type(chef.call('Keyboard.button_index', n)) == 'number' then known[#known + 1] = n end
  end
  if #known > 0 then k.names = known end
end
local DEFAULT_PING = { dev = 'key', names = { 'q' }, label = 'Q', trigger = 'Tap' }

-- ------------------------------------------------------------------ state
P.aimed, P.waypoints = nil, {}
local Sref = nil
local aim_t0, aim_lift = 0, LIFT_LOOT
local pinged = { {}, {}, {}, {} }   -- { kind, x, y, z, untl }
local ping_times, ping_i = { -99, -99, -99 }, 0
local quiet_until = -1
local ping_was, ping_t0, ping_target, ping_lift = false, nil, nil, LIFT_LOOT
local toast_s, toast_t = nil, -99
local last_pickups = nil
local n_loot_wp = 0

local function is_loot(k) return k ~= nil and (k.cat == 'loot' or k.cat == 'supply') end
local singular = {}
local function label_of(k, n)
  if not k then return 'WAYPOINT' end
  local l = k.label or upper(k.id or '?')
  if n and n > 1 then return l end
  local s = singular[k]
  if not s then
    s = l:match('SS$') and l or l:gsub('S$', '')
    singular[k] = s
  end
  return s
end
local function toast(S, s)
  toast_s, toast_t = s, S.t
end
local function count_loot()
  local n = 0
  for _, w in ipairs(P.waypoints) do if is_loot(w.kind) then n = n + 1 end end
  n_loot_wp = n
end

-- ------------------------------------------------------------------ the waypoint glyph (for every view)
function P.icon(cx, cy, size, alpha, layer)
  local t = RGB.ping   -- 0.8: the waypoint's colour everywhere (the pins and the compass are cyan too)
  local c = D.color(t[1], t[2], t[3], alpha or 255)
  if D.texc('ping/wp', cx, cy, size, size, c, layer) then return end
  local s = size * 0.5
  local th = max(1, floor(size / 12 + 0.5))
  D.rect(cx - s / 2, cy - s / 2, s, th, c, layer)
  D.rect(cx - s / 2, cy + s / 2 - th, s, th, c, layer)
  D.rect(cx - s / 2, cy - s / 2, th, s, c, layer)
  D.rect(cx + s / 2 - th, cy - s / 2, th, s, c, layer)
  D.dot(cx, cy, th * 2, c, layer)
end

-- ------------------------------------------------------------------ pinged marks (by kind and place: lists rebuild)
function P.pinged(m, t)
  if not m then return false end
  t = t or (Sref and Sref.t) or 0
  for i = 1, #pinged do
    local e = pinged[i]
    if e.untl and e.untl > t and e.kind == m.kind and (e.x - m.x) ^ 2 + (e.y - m.y) ^ 2 + (e.z - (m.z or 0)) ^ 2 <= 1 then
      return true
    end
  end
  return false
end
local function mark_pinged(S, m)
  local slot, oldest = nil, nil
  for i = 1, #pinged do
    local e = pinged[i]
    if not e.untl or e.untl <= S.t then slot = e; break end
    if not oldest or e.untl < oldest.untl then oldest = e end
  end
  slot = slot or oldest
  slot.kind, slot.x, slot.y, slot.z, slot.untl = m.kind, m.x, m.y, m.z or 0, S.t + PINGED_FOR
  ping_i = ping_i % SPAM_N + 1
  ping_times[ping_i] = S.t
  local n = 0
  for i = 1, SPAM_N do if S.t - ping_times[i] <= SPAM_T then n = n + 1 end end
  if n >= SPAM_N and quiet_until < S.t then
    quiet_until = S.t + SPAM_QUIET
    chef.log('pings: %d pings in %d s, ping hints quiet for %d s', SPAM_N, SPAM_T, SPAM_QUIET)
  end
end

-- ------------------------------------------------------------------ the assist: the pile nearest my crosshair
local RANGE2, RANGE_MAP2 = ASSIST_RANGE * ASSIST_RANGE, ASSIST_RANGE_MAP * ASSIST_RANGE_MAP
local function score(m, lift, range2, cam, fx, fy, fz, keep)
  local vx, vy, vz = m.x - cam.x, m.y - cam.y, (m.z or 0) + lift - cam.z
  local d2 = vx * vx + vy * vy + vz * vz
  if d2 < 1 or d2 > range2 then return nil end
  local d = sqrt(d2)
  local c = (vx * fx + vy * fy + vz * fz) / d
  if c < COS_MAX then return nil end
  local cone = atan(CONE_SIZE / d)
  if cone < CONE_MIN then cone = CONE_MIN elseif cone > CONE_MAX then cone = CONE_MAX end
  if keep then cone = cone * KEEP end
  local r = acos(min(1, c)) / cone
  if r > 1 then return nil end
  return r
end
-- the same pile or mark (the lists are rebuilt as new tables: compare kind and place)
local function same(a, b)
  return a == b or (a ~= nil and b ~= nil and a.kind == b.kind and a.x == b.x and a.y == b.y)
end
local function assist(S)
  local cam = S.cam
  local fx, fy, fz = cam.fx, cam.fy, cam.fz
  local fl = sqrt(fx * fx + fy * fy + fz * fz)
  if fl < 1e-6 then return nil end
  fx, fy, fz = fx / fl, fy / fl, fz / fl
  local prev = P.aimed
  local best, br, blift = nil, 2, LIFT_LOOT
  local tr = T.mod.track
  if tr and not tr.stale and type(tr.pickups) == 'table' then
    local list = tr.pickups
    for i = 1, #list do
      local m = list[i]
      if m.n > 0 then
        local r = score(m, LIFT_LOOT, RANGE2, cam, fx, fy, fz, same(m, prev))
        if r and r < br then best, br, blift = m, r, LIFT_LOOT end
      end
    end
  end
  local O = T.mod.objectives
  local marks = O and O.marks
  if type(marks) == 'table' then
    for i = 1, #marks do
      local m = marks[i]
      if type(m) == 'table' and m.kind and m.x and (m.n or 1) > 0 and m.state ~= 'done' then
        local r = score(m, LIFT_MAP, RANGE_MAP2, cam, fx, fy, fz, same(m, prev))
        if r and r < br then best, br, blift = m, r, LIFT_MAP end
      end
    end
  end
  return best, blift
end

-- ------------------------------------------------------------------ waypoints
local function dist2d(a, x, y) return sqrt((a.x - x) ^ 2 + (a.y - y) ^ 2) end
local function wp_remove(S, i, why)
  local w = remove(P.waypoints, i)
  if not w then return end
  if why then toast(S, why == 'cleared' and 'WAYPOINT CLEARED' or (w.label .. ' ' .. why)) end
  chef.log('pings: waypoint %s %s, %d left', w.label, why and string.lower(why) or 'removed', #P.waypoints)
  count_loot()
end
local function wp_add(S, m, src)
  local W = P.waypoints
  local k = m.kind
  local mark = m
  if is_loot(k) then
    local tr = T.mod.track
    mark = tr and tr.near and tr.near(k, m.x, m.y, m.z, RELINK + (k.stack or 0)) or nil
  end
  if #W >= MAX_WP then
    local old = remove(W, 1)
    chef.log('pings: waypoint %s replaced (the oldest)', old.label)
  end
  local w = { x = m.x, y = m.y, z = m.z or 0, label = label_of(k, 1), kind = k, mark = mark }
  if mark and mark ~= m then w.x, w.y, w.z = mark.x, mark.y, mark.z or 0 end
  W[#W + 1] = w
  toast(S, 'WAYPOINT: ' .. w.label)
  chef.log('pings: waypoint %s set (%s, %s), %d set', w.label, src, D.dist(dist2d(w, S.me.x, S.me.y)), #W)
  count_loot()
end
-- set a waypoint on m, or clear the one it has; r: how close a waypoint of its kind must be to count as its
local function wp_toggle(S, m, r, src)
  local W = P.waypoints
  for i = 1, #W do
    local w = W[i]
    if w == m or (m.kind and w.kind == m.kind and (w.mark == m or dist2d(w, m.x, m.y) <= r)) then
      wp_remove(S, i, 'cleared')
      return
    end
  end
  if not m.kind then return end
  wp_add(S, m, src)
end
-- the click-to-waypoint hook (the map overlay): the same as Numpad 1 on that mark
function P.toggle(S, m, src)
  if C.PINGS and type(m) == 'table' then wp_toggle(S, m, MATCH, src or 'map') end
end
local function wp_follow(S)
  local W = P.waypoints
  if #W == 0 then return end
  local tr = T.mod.track
  if tr and not tr.stale and tr.pickups ~= last_pickups then
    last_pickups = tr.pickups
    for i = #W, 1, -1 do
      local w = W[i]
      if is_loot(w.kind) then
        local p = tr.near(w.kind, w.x, w.y, w.z, RELINK)
        if p then w.mark, w.x, w.y, w.z = p, p.x, p.y, p.z or 0
        else wp_remove(S, i, 'GONE') end
      end
    end
  end
  for i = #W, 1, -1 do
    local w = W[i]
    local m = w.mark
    if m and m.n == 0 then wp_remove(S, i, is_loot(w.kind) and 'PICKED UP' or 'DONE')
    elseif m and not is_loot(w.kind) and m.state == 'done' then wp_remove(S, i, 'DONE') end
  end
end

-- ------------------------------------------------------------------ life cycle
function P.init(S)
  Sref = S
  for _, k in pairs(P.keys) do prune(k) end
  chef.log('pings: %s; keys: %s set or clear a waypoint on the aimed item, %s clear all',
    C.PINGS and 'on' or 'off', K_SET.label, K_CLEAR.label)
end

function P.reset(S)
  Sref = S
  for i = #P.waypoints, 1, -1 do P.waypoints[i] = nil end
  P.aimed = nil
  for i = 1, #pinged do pinged[i].untl = nil end
  quiet_until, toast_s = -1, nil
  ping_was, ping_t0, ping_target = false, nil, nil
  last_pickups = nil
  n_loot_wp = 0
end

function P.idle(S)
  P.aimed = nil
  ping_was, ping_t0, ping_target = false, nil, nil
end

-- main asks before the frame's update: is a loot list needed?
function P.wants_loot()
  if not C.PINGS then return false end
  if n_loot_wp > 0 then return true end
  return not (Sref and Sref.hidden)
end

function P.update(S)
  Sref = S
  if not C.PINGS then return end
  local V = T.mod.mapview
  wp_follow(S)

  -- the player's own ping key: a tap while aimed is a ping (the game's; I only note it)
  local b = V and V.binds and V.binds.ping or DEFAULT_PING
  local down
  if V and V.down then down = V.down(b) else down = chef.key_down('q') end
  if down and not ping_was then
    ping_t0, ping_target, ping_lift = S.t, P.aimed, aim_lift
    if b.trigger ~= 'Tap' and ping_target then mark_pinged(S, ping_target); ping_target = nil end
  elseif not down and ping_was then
    if ping_target and ping_t0 and S.t - ping_t0 <= TAP_MAX and not S.map_open then mark_pinged(S, ping_target) end
    ping_t0, ping_target = nil, nil
  end
  ping_was = down

  if S.map_open then
    P.aimed = nil
    if pressed(K_SET) then toast(S, 'CLOSE THE MAP AND AIM AT AN ITEM') end
  else
    local a, lift = assist(S)
    if not same(a, P.aimed) then aim_t0 = S.t end
    P.aimed, aim_lift = a, lift
    if pressed(K_SET) then
      if a then wp_toggle(S, a, MATCH, 'aimed') else toast(S, 'NO ITEM IN SIGHT') end
    end
  end
  if pressed(K_CLEAR) then
    local n = #P.waypoints
    for i = n, 1, -1 do P.waypoints[i] = nil end
    count_loot()
    if n > 0 then toast(S, 'WAYPOINTS CLEARED'); chef.log('pings: %d waypoints cleared', n) end
  end
end

-- ------------------------------------------------------------------ drawing: the world
-- a far waypoint's pin (markers.pin): the kind's icon in the disc and my glyph over the pin's top
local pin_opts = {}
local dists = {}
local function dist_text(d)
  if d >= 999.5 then return D.dist(d) end
  local m = floor(d + 0.5)
  local s = dists[m]
  if not s then s = D.dist(m); dists[m] = s end
  return s
end

-- the loot pin markers draws for this pile (same rule as markers.draw)
local function loot_pin_shown(S, w, d3)
  return T.mod.markers ~= nil and C.MARKERS and S.markers_on and is_loot(w.kind) and d3 <= C.MARKERS
    and w.mark ~= nil and w.mark.n > 0
end

local function draw_waypoints(S)
  local W = P.waypoints
  if #W == 0 then return end
  local M = T.mod.markers
  local me, t = S.me, RGB.text
  for i = 1, #W do
    local w = W[i]
    local d = sqrt((w.x - me.x) ^ 2 + (w.y - me.y) ^ 2 + (w.z - me.z) ^ 2)
    if loot_pin_shown(S, w, d) then
      -- the pile's own pin is there: my glyph floats over it (its distance is on the pin)
      local gx, gy = chef.world_to_screen(w.x, w.y, w.z + 0.05)
      if gx then
        local u, k = M.scale(S, d, C.MARKERS)
        local sz = 15 * u
        P.icon(gx, gy + M.rise(w.kind.supply) * u * k + sz * 0.75, sz, floor(255 * C.MARKER_OPACITY), 897)
      end
    elseif M and M.pin then
      pin_opts.dist, pin_opts.range, pin_opts.layer = d, d * 3 + 100, 894
      pin_opts.kind = w.kind
      pin_opts.tint = w.kind and not is_loot(w.kind) and (w.kind.rgb or t) or nil
      local shown, cx, _, top = M.pin(S, w.x, w.y, w.z, pin_opts)
      if shown then
        local u, k = M.scale(S, d, pin_opts.range)
        local sz = 15 * u * k
        P.icon(cx, top + sz * 0.75, sz, floor(255 * C.MARKER_OPACITY), 896)
      end
    else
      local gx, gy = chef.world_to_screen(w.x, w.y, w.z + 1.0)
      if gx then
        local sz = S.h / 45
        P.icon(gx, gy, sz, floor(255 * C.MARKER_OPACITY), 897)
        D.text(gx, gy - sz * 0.5 - S.h / 100 * 1.6, dist_text(d), S.h / 100, D.color(t[1], t[2], t[3], floor(235 * C.MARKER_OPACITY)), 898, 'c')
      end
    end
  end
end

-- a thin bracket: four corners, each with a dark edge
local function bracket(cx, cy, half, th, c, cd, layer)
  local arm = max(th * 3, floor(half * 0.42 + 0.5))
  for sx = -1, 1, 2 do
    for sy = -1, 1, 2 do
      local x0, y0 = cx + sx * half, cy + sy * half
      local hx = sx < 0 and x0 or x0 - arm
      local hy = sy < 0 and y0 or y0 - th
      local vx = sx < 0 and x0 or x0 - th
      local vy = sy < 0 and y0 or y0 - arm
      D.rect(hx - 1, hy - 1, arm + 2, th + 2, cd, layer)
      D.rect(vx - 1, vy - 1, th + 2, arm + 2, cd, layer)
      D.rect(hx, hy, arm, th, c, layer + 1)
      D.rect(vx, vy, th, arm, c, layer + 1)
    end
  end
end
-- a keycap: the key's label in a thin box, then a word
local function keycap(x, cy, key, word, cap, a, layer)
  local t, r, dk = RGB.text, RGB.rim, RGB.dark
  local th = max(1, floor(cap / 11 + 0.5))
  local w = max(D.text_w(key, cap) + cap * 0.9, cap * 1.8)
  local h = floor(cap * 1.8 + 0.5)
  local y = floor(cy - h / 2 + 0.5)
  x = floor(x + 0.5)
  D.rect(x, y, w, h, D.color(dk[1], dk[2], dk[3], floor(D.A(170) * a)), layer)
  local cr = D.color(r[1], r[2], r[3], floor(220 * a))
  D.rect(x, y, w, th, cr, layer + 1)
  D.rect(x, y + h - th, w, th, cr, layer + 1)
  D.rect(x, y, th, h, cr, layer + 1)
  D.rect(x + w - th, y, th, h, cr, layer + 1)
  local ct = D.color(t[1], t[2], t[3], floor(255 * a))
  D.text(x + w / 2, cy - cap / 2, key, cap, ct, layer + 2, 'c')
  if word then
    D.text(x + w + cap * 0.5, cy - cap / 2, word, cap, D.color(t[1], t[2], t[3], floor(235 * a)), layer + 2)
  end
end

local function draw_assist(S)
  local m = P.aimed
  if not m then return end
  local gx, gy = chef.world_to_screen(m.x, m.y, (m.z or 0) + aim_lift)
  if not gx then return end
  local half = S.h * 0.016
  local tx, ty = chef.world_to_screen(m.x, m.y, (m.z or 0) + aim_lift + 0.8)
  if tx then half = max(S.h * 0.016, min(S.h * 0.05, abs(ty - gy) * 0.75)) end
  local fade = min(1, (S.t - aim_t0) / 0.12)
  local was = P.pinged(m, S.t)
  local a = (was and 0.4 or 1) * fade
  local t, dk = RGB.text, RGB.dark
  local th = max(1, floor(S.h / 540 + 0.5))
  gx, gy, half = floor(gx + 0.5), floor(gy + 0.5), floor(half + 0.5)
  bracket(gx, gy, half, th, D.color(t[1], t[2], t[3], floor(240 * a)), D.color(dk[1], dk[2], dk[3], floor(110 * a)), 886)
  if was or S.t < quiet_until then return end
  local ka = min(1, (S.t - aim_t0 - DWELL) / 0.15)
  if ka <= 0 then return end
  local V = T.mod.mapview
  local b = V and V.binds and V.binds.ping or DEFAULT_PING
  if not b.dev then return end                -- bound to a pad only: no key to show
  local cap = max(8, floor(S.h / 96 + 0.5))
  keycap(gx + half + cap * 0.8, gy, b.label or 'Q', 'PING', cap, ka, 889)
end

local function draw_toast(S, layer)
  if not toast_s then return end
  local age = S.t - toast_t
  if age > TOAST_T then toast_s = nil; return end
  local a = min(1, (TOAST_T - age) / 0.4, age / 0.1)
  local cap = max(8, floor(S.h / 72 + 0.5))
  local t, dk = RGB.text, RGB.dark
  local w = D.text_w(toast_s, cap) + cap * 2
  local h = cap * 2.2
  local x, y = floor(S.w / 2 - w / 2 + 0.5), floor(S.h * 0.27 + 0.5)
  D.rect(x, y, w, h, D.color(dk[1], dk[2], dk[3], floor(D.A(160) * a)), layer)
  D.rect(x, y, w, max(1, floor(S.px / 2 + 0.5)), D.color(t[1], t[2], t[3], floor(150 * a)), layer + 1)
  D.text(S.w / 2, y + h / 2 - cap / 2, toast_s, cap, D.color(t[1], t[2], t[3], floor(255 * a)), layer + 2, 'c')
end

function P.draw(S)
  if not C.PINGS then return end
  if S.map_open then
    if S.hidden then return end
    local V = T.mod.mapview
    if V and V.top_now then draw_toast(S, TOP + 975) end
    return
  end
  if S.hidden then return end
  draw_waypoints(S)
  draw_assist(S)
  draw_toast(S, 980)
end

return P
