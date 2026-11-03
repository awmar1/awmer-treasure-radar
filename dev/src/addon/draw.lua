local T, chef = ...
-- Drawing helpers shared by every view: colors, textures by name, icons, text from glyph textures. Origin
-- bottom-left, +y up, pixels.
local D = {}
local K = T.mod.kinds
local floor, max, pi, cos, sin = math.floor, math.max, math.pi, math.cos, math.sin
local byte, sub, fmt = string.byte, string.sub, string.format
local TEX = T.TEX

local S = nil                       -- the frame state, set by D.frame

function D.frame(state)
  S = state
end

-- ------------------------------------------------------------------ colors (one-frame temporaries in the engine)
local color = chef.color
D.color = color
function D.rgb(rgb, a) return color(rgb[1], rgb[2], rgb[3], a or 255) end
function D.A(a) return floor(a * (S and S.opacity or 1) + 0.5) end

-- ------------------------------------------------------------------ textures by name
local missing = {}
function D.tex(name, x, y, w, h, c, layer)
  local id = TEX[name]
  if not id then
    if not missing[name] then missing[name] = true; chef.log('no texture named %s in this build', tostring(name)) end
    return false
  end
  return chef.bitmap(id, x, y, w, h, c, layer)
end
function D.texc(name, cx, cy, w, h, c, layer) return D.tex(name, cx - w / 2, cy - h / 2, w, h, c, layer) end
function D.has(name) return TEX[name] ~= nil end

-- a pre-rotated frame: prefix/01..prefix/n, frame i drawn turned (i-1)*360/n degrees clockwise from screen-up
local rot_names = {}
function D.rot(prefix, n, angle)
  local i = floor((angle % (2 * pi)) / (2 * pi) * n + 0.5) % n + 1
  local t = rot_names[prefix]
  if not t then t = {}; rot_names[prefix] = t end
  local name = t[i]
  if not name then name = fmt('%s/%02d', prefix, i); t[i] = name end
  return name
end

-- ------------------------------------------------------------------ shapes
function D.rect(x, y, w, h, c, layer) chef.rect(x, y, w, h, c, layer) end
function D.dot(cx, cy, size, c, layer) chef.rect(cx - size / 2, cy - size / 2, size, size, c, layer) end
function D.dots_ring(cx, cy, r, n, size, c, layer)
  for i = 0, n - 1 do
    local a = i / n * 2 * pi
    chef.rect(cx + cos(a) * r - size / 2, cy + sin(a) * r - size / 2, size, size, c, layer)
  end
end

-- ------------------------------------------------------------------ icons
-- A kind's icon centered on cx, cy, size pixels square: its texture tinted white (or tint_rgb) at alpha, or its
-- fallback sprite.
local white_alpha = {}
function D.icon(kind, cx, cy, size, alpha, layer, tint_rgb)
  alpha = alpha or 255
  local c = tint_rgb and color(tint_rgb[1], tint_rgb[2], tint_rgb[3], alpha) or color(255, 255, 255, alpha)
  if kind.tex and TEX[kind.tex] and chef.bitmap(TEX[kind.tex], cx - size / 2, cy - size / 2, size, size, c, layer) then return true end
  local rows = K.SPRITE[kind.icon or 'square'] or K.SPRITE.square
  local rgb = tint_rgb or kind.rgb
  local cell = size / 9
  chef.sprite(cx - size / 2, cy - size / 2, rows, cell, { X = color(rgb[1], rgb[2], rgb[3], alpha), o = color(10, 10, 12, floor(alpha * 0.85)) }, layer)
  return false
end

-- ------------------------------------------------------------------ text
-- glyphs.lua (made with the glyph textures) holds: { gap, space, sets = { { cap, pad, chars = { [byte] = { adv,
-- tw, th } } }, ... } } smallest set first. adv: advance in cap heights; tw, th: the texture's size in pixels; the
-- cap box's bottom-left sits pad pixels in from the texture's bottom-left. Texture names: glyphs/<cap>/<byte>.
local G = T.mod.glyphs
local glyph_ok = (type(G) == 'table' and type(G.sets) == 'table' and G.sets[1] ~= nil) or false
local GAP, SPACE = G and G.gap or 0.12, G and G.space or 0.4
local names = {}
local function set_for(cap)
  local sets = G.sets
  for i = 1, #sets do if sets[i].cap >= cap * 0.9 then return sets[i] end end
  return sets[#sets]
end
local function covered(set, str)
  for i = 1, #str do
    local b = byte(str, i)
    if b ~= 32 and not set.chars[b] then return false end
  end
  return true
end
local function fallback_px(cap) return max(1, floor(cap / 7 + 0.5)) end

function D.text_w(str, cap)
  str = tostring(str)
  if glyph_ok then
    local set = set_for(cap)
    if covered(set, str) then
      local w = 0
      for i = 1, #str do
        local b = byte(str, i)
        w = w + (b == 32 and SPACE or set.chars[b][1]) * cap + (i > 1 and GAP * cap or 0)
      end
      return w
    end
  end
  return chef.text_width(str, fallback_px(cap))
end

function D.text(x, y, str, cap, c, layer, align)
  str = tostring(str)
  if align == 'c' then x = x - D.text_w(str, cap) / 2 elseif align == 'r' then x = x - D.text_w(str, cap) end
  if glyph_ok then
    local set = set_for(cap)
    if covered(set, str) then
      local s = cap / set.cap
      local pad = set.pad * s
      local cx = x
      local list = names[set]
      if not list then list = {}; names[set] = list end
      for i = 1, #str do
        local b = byte(str, i)
        if b == 32 then cx = cx + SPACE * cap + GAP * cap
        else
          local e = set.chars[b]
          local name = list[b]
          if not name then name = 'glyphs/' .. set.cap .. '/' .. b; list[b] = name end
          local id = TEX[name]
          if not (id and chef.bitmap(id, cx - pad, y - pad, e[2] * s, e[3] * s, c, layer)) then
            glyph_ok = false
            chef.log('glyph textures not usable (%s); text uses the pixel font', name)
            break
          end
          cx = cx + e[1] * cap + GAP * cap
        end
      end
      if glyph_ok then return cx - x - GAP * cap end
    end
  end
  return chef.text(x, y, str, fallback_px(cap), c, layer) or 0
end

-- distances the game's way: "18 M", "1.2 KM"
function D.dist(d)
  if d < 1000 then return floor(d + 0.5) .. ' M' end
  return fmt('%.1f KM', d / 1000)
end

return D
