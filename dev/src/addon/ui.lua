local T, chef = ...
-- Panels on the open map (the 0.8 mock's look): rounded rects made of rects and corner textures (ov/rr/*), text
-- placed by its vertical centre, and the two marks the glyph font hasn't got (a small X for "x3", a dot for " · ").
-- Origin bottom-left, +y up, pixels; s = S.h / 1080 (sizes are the mock's 1080p pixels).
local U = {}
local C, D = T.mod.config, T.mod.draw
local floor, max, min = math.floor, math.max, math.min
local color = chef.color

local RR = 3                  -- the corner radius at 1080p (the textures hold a third of it as the outline)
local CAP = 0.7               -- a glyph's cap height per pixel of the mock's font size

local function snap(v) return floor(v + 0.5) end

-- the cap height (px) of the mock's font size fs at scale s
function U.cap(fs, s) return fs * CAP * s end

-- A rounded panel from x0, y0 to x1, y1 (snapped to whole pixels): a fill of C.PANEL.fill at fill_a, and a rim-coloured
-- outline at rim_a, w px wide at 1080p (thinner than a pixel: fainter instead). The outline isn't drawn over the fill.
function U.rrect(x0, y0, x1, y1, s, fill_a, rim_a, w, layer)
  local X0, Y0, X1, Y1 = snap(x0), snap(y0), snap(x1), snap(y1)
  local W, H = X1 - X0, Y1 - Y0
  local u = max(1, snap(s))
  local R = RR * u
  if W < 2 * R or H < 2 * R then return end
  if fill_a and fill_a > 0 then
    local f = C.PANEL.fill
    local c = color(f[1], f[2], f[3], fill_a)
    D.rect(X0 + R, Y0 + u, W - 2 * R, H - 2 * u, c, layer)
    D.rect(X0 + u, Y0 + R, R - u, H - 2 * R, c, layer)
    D.rect(X1 - R, Y0 + R, R - u, H - 2 * R, c, layer)
    D.tex('ov/rr/fill_tl', X0, Y1 - R, R, R, c, layer)
    D.tex('ov/rr/fill_tr', X1 - R, Y1 - R, R, R, c, layer)
    D.tex('ov/rr/fill_bl', X0, Y0, R, R, c, layer)
    D.tex('ov/rr/fill_br', X1 - R, Y0, R, R, c, layer)
  end
  if rim_a and rim_a > 0 then
    local r = C.RGB.rim
    local c = color(r[1], r[2], r[3], floor(rim_a * min(1, (w or 1) * s / u) + 0.5))
    D.rect(X0 + R, Y1 - u, W - 2 * R, u, c, layer)
    D.rect(X0 + R, Y0, W - 2 * R, u, c, layer)
    D.rect(X0, Y0 + R, u, H - 2 * R, c, layer)
    D.rect(X1 - u, Y0 + R, u, H - 2 * R, c, layer)
    D.tex('ov/rr/line_tl', X0, Y1 - R, R, R, c, layer)
    D.tex('ov/rr/line_tr', X1 - R, Y1 - R, R, R, c, layer)
    D.tex('ov/rr/line_bl', X0, Y0, R, R, c, layer)
    D.tex('ov/rr/line_br', X1 - R, Y0, R, R, c, layer)
  end
end

-- text whose caps are centred on cy (the mock's 'lm' anchor; align 'c' / 'r' as D.text) -> width
function U.text_mid(x, cy, str, cap, c, layer, align)
  return D.text(x, cy - cap / 2, str, cap, c, layer, align)
end

-- "NAME x3": the name, then a smaller X and the count (n > 1), caps centred on cy -> width
local XS = 0.72               -- the X's size per cap
local function count_parts(cap)
  local gap = cap * 0.42      -- a space
  return gap, cap * XS
end
function U.count_w(name, n, cap)
  local w = D.text_w(name, cap)
  if n and n > 1 then
    local gap, xc = count_parts(cap)
    w = w + gap + D.text_w('X', xc) + cap * 0.16 + D.text_w(tostring(n), cap)
  end
  return w
end
function U.count_text(x, cy, name, n, cap, c, layer)
  local w = U.text_mid(x, cy, name, cap, c, layer)
  if n and n > 1 then
    local gap, xc = count_parts(cap)
    w = w + gap
    w = w + U.text_mid(x + w, cy, 'X', xc, c, layer) + cap * 0.16
    w = w + U.text_mid(x + w, cy, tostring(n), cap, c, layer)
  end
  return w
end

-- "A · B": two texts with a small square dot between, caps centred on cy -> width
local function dot_parts(cap) return cap * 0.75, max(1, snap(cap * 0.22)) end
function U.dot_w(a, b, cap)
  local gap = dot_parts(cap)
  return D.text_w(a, cap) + 2 * gap + D.text_w(b, cap)
end
function U.dot_text(x, cy, a, b, cap, c, layer)
  local gap, size = dot_parts(cap)
  local w = U.text_mid(x, cy, a, cap, c, layer)
  D.rect(snap(x + w + gap - size / 2), snap(cy - size / 2), size, size, c, layer)
  w = w + 2 * gap
  return w + U.text_mid(x + w, cy, b, cap, c, layer)
end

return U
