local T, chef = ...
-- The map overlay (C.OVERLAY): Treasure Radar on the game's own open map, the look of dev/docs/mock_0.8_map_detail.png.
-- Every spot comes from view.lua's model (VW); while VW.trusted is false (0.9: the whole map with its size measured,
-- or level 0 / +1 with a fresh companion fix) nothing world-anchored is drawn: no loot, no rings, no waypoint chevron.
-- 0.9.3 (B): only while VW.settled too (at 0 / +1: the mouse still for view.lua's SETTLE s and a dot fix since, the
-- level known; always at -1), every alpha times VW.fade (0..1, a 0.1 s linear ramp in and out; the fade out's tail
-- is the one draw after VW.settled drops, at the V the hold carries on).
--   loot     each cluster's top-ranked icon (16 px at 1080p) on a faint dark disc; a badge at its lower right: "+N"
--            when the cluster mixes kinds (N more piles), else the pile count when it's more than one
--   nests    a hostile ring with a centre dot at the true spot (structures too: the game shows its own icon once it
--            has seen one, and covers ours). Main objectives get nothing: the game always marks them. A nest within
--            NEAR_OBJ px of one is left out. Done ones are dimmed, with their done mark (objectives.done_tex).
--   waypoint off the map: a cyan chevron just inside the rim, toward it. Loot off the map isn't shown.
-- Sizes are the mock's 1080p pixels times s = S.h / 1080; panels (the badges) follow the panel opacity.
-- (0.8.3's hover label and click-to-waypoint went with the cursor model: dev/src/retired/addon-0.8.3.)
-- Layers TOP + 920-949. Hidden with the mod's HUD.
local O = {}
local C, D, U = T.mod.config, T.mod.draw, T.mod.ui
local floor, sqrt, atan2 = math.floor, math.sqrt, math.atan2
local TOP = chef.TOP or 2000
local RGB = C.RGB
local color = chef.color

local ICON = 16
local DISC, DISC_A = 0.62, 95             -- the disc's radius per icon size, and its alpha
local NEST_BOX = 20                       -- the ring textures' box (ov/nest_m: ring 6.2 px, ov/nest_s: 4.8 px)
local NEAR_OBJ = 14                       -- px: a nest this close to a main objective is the game's to show
local DONE_A, DONE_MARK = 110, 11         -- a done ring's alpha, and its done mark's size
local CHEV, CHEV_IN = 16, 14              -- the waypoint chevron's size, and how far inside the rim it sits
local L_RING, L_DISC, L_ICON, L_BADGE, L_BTEXT = TOP + 920, TOP + 922, TOP + 923, TOP + 926, TOP + 927
local L_CHEV = TOP + 945

-- strings made once
local strs = {}
local function str_of(prefix, n)
  local t = strs[prefix]
  if not t then t = {}; strs[prefix] = t end
  local v = t[n]
  if not v then v = prefix .. n; t[n] = v end
  return v
end
local function badge_of(c)
  if c.mixed then return str_of('+', c.piles - 1) end
  if c.total > 1 then return str_of('', c.total) end
  return nil
end

-- ------------------------------------------------------------------ nests and structures
local obj_x, obj_y, n_obj = {}, {}, 0
local function rings(S, VW, s, a0)
  local Ob = T.mod.objectives
  if not (Ob and type(Ob.marks) == 'table') then return end
  local marks = Ob.marks
  n_obj = 0
  for i = 1, #marks do
    local m = marks[i]
    if m.kind and m.kind.cat == 'objective' then
      n_obj = n_obj + 1
      obj_x[n_obj], obj_y[n_obj] = VW.to_screen(m.x, m.y)
    end
  end
  local near2 = (NEAR_OBJ * s) ^ 2
  local box = NEST_BOX * s
  local done_tex = type(Ob.done_tex) == 'function' and Ob.done_tex
  for i = 1, #marks do
    local m = marks[i]
    local cat = m.kind and m.kind.cat
    if cat == 'nest' or cat == 'structure' then
      local sx, sy = VW.to_screen(m.x, m.y)
      if VW.inside(sx, sy, 6 * s) then
        local hidden = false
        for j = 1, n_obj do
          if (sx - obj_x[j]) ^ 2 + (sy - obj_y[j]) ^ 2 < near2 then hidden = true; break end
        end
        if not hidden then
          local tex = (m.kind.id == 'bug_hole_small') and 'ov/nest_s' or 'ov/nest_m'
          if m.state == 'done' then
            D.texc(tex, sx, sy, box, box, color(255, 255, 255, floor(DONE_A * a0)), L_RING)
            local dt = done_tex and done_tex(m)
            if dt then
              local d = DONE_MARK * s
              local t = RGB.text
              D.texc(dt, sx, sy, d, d, color(t[1], t[2], t[3], floor(220 * a0)), L_RING + 1)
            end
          else
            D.texc(tex, sx, sy, box, box, color(255, 255, 255, floor(255 * a0)), L_RING)
          end
        end
      end
    end
  end
end

-- ------------------------------------------------------------------ loot
local function badge(text, sx, sy, size, s, a)
  local cap = U.cap(9.5, s)
  local w = D.text_w(text, cap) + 5 * s
  local bx, top = sx + size * 0.30, sy - size * 0.22      -- the badge's top-left corner (the mock's, y flipped)
  U.rrect(bx, top - 11 * s, bx + w, top, s, D.A(235 * a), D.A(150 * a), 0.8, L_BADGE)
  local t = RGB.text
  U.text_mid(bx + w / 2, top - 5.7 * s, text, cap, color(t[1], t[2], t[3], floor(255 * a)), L_BTEXT, 'c')
end

local function loot(S, VW, s, f)
  local size = ICON * s
  for j = 1, VW.n do
    local c = VW.clusters[j]
    local a = c.alpha * f
    local r2 = 2 * size * DISC
    D.texc('ov/disc', c.sx, c.sy, r2, r2, color(0, 0, 0, floor(DISC_A * a)), L_DISC)
    D.icon(c.kind, c.sx, c.sy, size, floor(255 * a + 0.5), L_ICON)
    local b = badge_of(c)
    if b then badge(b, c.sx, c.sy, size, s, a) end
  end
end

-- ------------------------------------------------------------------ the waypoint off the map
local function chevron(S, VW, s, f)
  local w = VW.waypoint
  if not (w and w.x and w.y) then return end
  local sx, sy = VW.to_screen(w.x, w.y)
  if VW.inside(sx, sy, 4 * s) then return end
  local cx, cy = S.map.cx, S.map.cy
  local dx, dy = sx - cx, sy - cy
  local d = sqrt(dx * dx + dy * dy)
  if d < 1 then return end
  local r = VW.r - CHEV_IN * s
  local p = RGB.ping
  local size = CHEV * s
  D.texc(D.rot('ov/chev', 16, atan2(dx, dy)), cx + dx / d * r, cy + dy / d * r, size, size,
    color(p[1], p[2], p[3], floor(255 * f + 0.5)), L_CHEV)
end

-- ------------------------------------------------------------------ life cycle
function O.draw(S)
  if not C.OVERLAY or S.hidden then return end
  local VW = T.mod.view
  if not (VW and VW.open and VW.trusted) then return end
  -- VW.fade rises only while VW.settled; above 0 while not settled is the fade out's tail
  local f = (VW.fade or 0) * C.MAP_OPACITY
  if f <= 0 then return end
  local s = S.h / 1080
  rings(S, VW, s, f)
  loot(S, VW, s, f)
  chevron(S, VW, s, f)
end

return O
