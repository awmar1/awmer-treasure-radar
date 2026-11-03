local T, chef = ...
-- The legend (C.LEGEND): what's on this map, in a small panel left of the game's open map (the 0.8 mock's look). A row
-- per loot kind seen this mission in value order (C.RANK, from view.lua's VW.legend), then the nests: its icon and a
-- count, "5" while all are left, "3/5" once some are taken (a kind that's all gone in muted).
-- Not world-anchored, so it stays up while the map is panned. Sizes are the mock's 1080p pixels times s = S.h / 1080;
-- the panel follows the panel opacity. Layers TOP + 930-939 (the open map's world). Hidden with the mod's HUD (F7).
-- C.LEGEND (0.9.3): 'map' only beside the open map; 'always' the same panel while the map is closed too, left of the
-- corner radar (radar.place) when the radar is shown, else where it sits beside the open map, on the main world's
-- layers 960-962 (chef.TOP layers reach only the open map's world, which is gone while the map is closed). Its rows
-- come from view.lua's VW.legend, made every frame while C.LEGEND is 'always' (map open or not).
local M = {}
local C, D, U = T.mod.config, T.mod.draw, T.mod.ui
local floor = math.floor
local TOP = chef.TOP or 2000
local RGB = C.RGB
local color = chef.color

local RIM, GAP = 225, 16                  -- the map's rim line from its centre, and the gap to the panel (1080p px)
local RH, ICON, FS = 21, 16, 13           -- row height, icon size, the count's font size
local NEST_BOX = 20                       -- ov/nest_m's box (as overlay.lua draws it)
local L_PANEL, L_ICON, L_TEXT = TOP + 930, TOP + 931, TOP + 932
local C_PANEL, C_ICON, C_TEXT = 960, 961, 962     -- 'always', the map closed: the main world

-- "5" and "3/5", made once
local strs = {}
local function count_of(left, total)
  local key = left * 4096 + total
  local v = strs[key]
  if not v then v = (left == total) and tostring(total) or (left .. '/' .. total); strs[key] = v end
  return v
end

-- where the panel goes: its right edge, its centre's height, its three layers (nil: not drawn this frame)
local function spot(S, VW, s)
  if VW.open then
    return S.map.cx - (RIM + GAP) * s, S.map.cy, L_PANEL, L_ICON, L_TEXT
  end
  if C.LEGEND ~= 'always' or S.map_open then return nil end
  local R = T.mod.radar
  if C.RADAR and R and R.place then
    local rx, ry, rr = R.place(S)
    return rx - rr - GAP * s, ry, C_PANEL, C_ICON, C_TEXT
  end
  return S.map.cx - (RIM + GAP) * s, S.map.cy, C_PANEL, C_ICON, C_TEXT
end

function M.draw(S)
  if not C.LEGEND or S.hidden then return end
  local VW = T.mod.view
  if not (VW and S.map and S.map.cx) then return end
  local s = S.h / 1080
  local lx1, ly, lp, li, lt = spot(S, VW, s)
  if not lx1 then return end
  local L = VW.legend
  local rows = #L
  local nests = L.nests
  local nest_row = nests and nests[2] and nests[2] > 0
  local n = rows + (nest_row and 1 or 0)
  if n == 0 then return end
  local cap = U.cap(FS, s)

  local tw = 0
  for i = 1, rows do
    local w = D.text_w(count_of(L[i].left, L[i].total), cap)
    if w > tw then tw = w end
  end
  if nest_row then
    local w = D.text_w(count_of(nests[1], nests[2]), cap)
    if w > tw then tw = w end
  end
  local lw = (8 + 16 + 7 + 9) * s + tw
  local lh = (7 + RH * n + 5) * s
  local lx0 = lx1 - lw
  local ly0 = ly - lh / 2
  local top = ly0 + lh
  U.rrect(lx0, ly0, lx1, top, s, D.A(200), D.A(110), 1.0, lp)

  local t, m = RGB.text, RGB.muted
  local on, off = color(t[1], t[2], t[3], 255), color(m[1], m[2], m[3], 255)
  local ix, tx = lx0 + 16 * s, lx0 + 31 * s
  for i = 1, n do
    local cy = top - (7 + RH * (i - 1) + RH / 2) * s
    local left, total
    if i <= rows then
      local row = L[i]
      left, total = row.left, row.total
      D.icon(row.kind, ix, cy, ICON * s, 255, li)
    else
      left, total = nests[1], nests[2]
      local b = NEST_BOX * s
      D.texc('ov/nest_m', ix, cy, b, b, color(255, 255, 255, 255), li)
    end
    U.text_mid(tx, cy - 0.5 * s, count_of(left, total), cap, left > 0 and on or off, lt)
  end
end

return M
