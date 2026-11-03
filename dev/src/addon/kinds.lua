local T, chef = ...
-- Every kind the mod knows. Loot and supplies in ledger order (the most valuable first, supplies last), with their
-- units' resource ids; then the map's kinds (objectives, structures, points of interest) from structures.lua.
-- Pickups of a kind within `stack` meters of each other share one icon on the map views, with a count.
local K = {}
local C = T.mod.config

K.loot = {
  { id = 'credit', label = 'SUPER CREDITS', icon = 'coin', rgb = { 115, 233, 242 }, stack = 2, units = { 'bd6f4de16b9aedcd' } },
  { id = 'medal', label = 'MEDALS', icon = 'star', rgb = { 255, 221, 31 }, stack = 2, units = { '773c4184e4bad0df' } },
  { id = 'common', label = 'COMMON SAMPLES', icon = 'vial', rgb = { 69, 255, 141 }, stack = 2,
    units = { '307e09e7698881ba', '294eda665270ac42', 'cf1ad44dedd1f257', '5016ee397fdcfb6c', '64b49b9d8a445266',
              '700e9500e95541bf', '86f3cb87d97942b4', '4efcb7e844be9e93', 'a2414ed6e129c19f', 'b39fcf5c73d5c383',
              'beb2a0f09e36bf72', 'd463836441cd0ba7', 'e4eeb96023df6a99' } },
  { id = 'rare', label = 'RARE SAMPLES', icon = 'diamond', rgb = { 255, 129, 41 }, stack = 2,
    units = { '8208ea6cb095be54', 'ad972a2e815a49aa', 'bd30758426ed2566', 'defe062c2567c23d' } },
  { id = 'super', label = 'SUPER SAMPLES', icon = 'crystal', rgb = { 255, 114, 211 }, stack = 2, units = { '9d4935fa69b6b41a', 'b4d6f2f83bde45a9' } },
  { id = 'requisition', label = 'REQUISITION', icon = 'slip', rgb = { 255, 233, 0 }, stack = 2, units = { 'da3c547d0e0e442f' } },
  { id = 'ammo', label = 'AMMO', icon = 'ammo', rgb = { 255, 234, 128 }, stack = 10, supply = true, units = { '79ccffd281e3f3a9' } },
  { id = 'grenade', label = 'GRENADES', icon = 'grenade', rgb = { 135, 170, 45 }, stack = 10, supply = true, units = { '97af34fbf093409c' } },
  { id = 'stim', label = 'STIMS', icon = 'cross', rgb = { 60, 140, 255 }, stack = 10, supply = true, units = { 'b4ca4c5b922f7965' } },
}

-- the map's kinds: structures.lua returns { kinds = { { id, cat, label, rgb?, tex?, units, ... } } } (see CONTRACT.md)
K.map = {}
local data = T.mod.structures
if type(data) == 'table' and type(data.kinds) == 'table' then
  for _, k in ipairs(data.kinds) do
    if type(k.units) == 'table' and #k.units > 0 then K.map[#K.map + 1] = k end
  end
end

K.by_unit, K.by_id = {}, {}
for i, k in ipairs(K.loot) do
  k.cat = k.supply and 'supply' or 'loot'
  k.rank = i
  k.tex = k.tex or ('icons/' .. k.id)
  k.on = C.kind_on(k.id)
end
for i, k in ipairs(K.map) do
  k.rank = #K.loot + i
  k.stack = k.stack or 0
  k.rgb = k.rgb or (k.cat == 'objective' or k.cat == 'side_objective') and C.RGB.objective
          or (k.cat == 'structure' or k.cat == 'nest') and C.RGB.hostile or C.RGB.text
  k.tex = k.tex or ('map/' .. k.id)
  k.on = C.map_kind_on(k.cat)
end
for _, list in ipairs({ K.loot, K.map }) do
  for _, k in ipairs(list) do
    K.by_id[k.id] = k
    for _, u in ipairs(k.units) do K.by_unit[u] = k end
  end
end

-- Fallback icons, 9 x 9 (X = the kind's color, o = dark outline, . = empty), for when the textures can't be used.
K.SPRITE = {
  coin = { '...ooo...', '.ooXXXoo.', '.oXXXXXo.', 'oXXXXXXXo', 'oXXXoXXXo', 'oXXXXXXXo', '.oXXXXXo.', '.ooXXXoo.', '...ooo...' },
  star = { '....o....', '...oXo...', 'oooXXXooo', 'oXXXXXXXo', '.oXXXXXo.', '..oXXXo..', '.oXXoXXo.', '.oXo.oXo.', '.oo...oo.' },
  vial = { '..ooooo..', '..oXXXo..', '...oXo...', '..oXXXo..', '.oXXXXXo.', '.oXXXXXo.', '.oXXXXXo.', '.oXXXXXo.', '..ooooo..' },
  diamond = { '....o....', '...oXo...', '..oXXXo..', '.oXXXXXo.', 'oXXXXXXXo', '.oXXXXXo.', '..oXXXo..', '...oXo...', '....o....' },
  crystal = { '...ooo...', '..oXXXo..', '.oXXXXXo.', '.oXXoXXo.', '.oXXoXXo.', '.oXXXXXo.', '.oXXXXXo.', '..oXXXo..', '...ooo...' },
  slip = { 'oooooooo.', 'oXXXXXXo.', 'oXooooXoo', 'oXXXXXXXo', 'oXooooXXo', 'oXXXXXXXo', 'oXoooXXXo', 'oXXXXXXXo', 'ooooooooo' },
  ammo = { '.X.X.X...', '.X.X.X...', 'ooooooooo', 'oXXXXXXXo', 'oXoooooXo', 'oXXXXXXXo', 'oXXXXXXXo', 'oXXXXXXXo', 'ooooooooo' },
  grenade = { '....oo...', '...oXXo..', '..ooooo..', '.oXXXXXo.', 'oXXXXXXXo', 'oXXoXXXXo', 'oXXXXXXXo', '.oXXXXXo.', '..ooooo..' },
  cross = { '...ooo...', '...oXo...', '...oXo...', 'oooXXXooo', 'oXXXXXXXo', 'oooXXXooo', '...oXo...', '...oXo...', '...ooo...' },
  square = { 'ooooooooo', 'oXXXXXXXo', 'oXXXXXXXo', 'oXXXXXXXo', 'oXXXXXXXo', 'oXXXXXXXo', 'oXXXXXXXo', 'oXXXXXXXo', 'ooooooooo' },
}
K.CHECK = { '........X', '.......XX', '......XX.', 'X....XX..', 'XX..XX...', '.XXXX....', '..XX.....', '.........', '.........' }

return K
