"""Unit kinds the scenarios can place: name -> resource ids (hex) of the unit kind.

The loot kinds are read from the addon's own KINDS table (so a build that adds or renames a kind is picked up without
touching the harness), with LOOT below as the fallback. Kinds the addon doesn't know yet (enemy structures, objectives,
anything else to test) go in EXTRA, or a scenario adds its own with Scenario.kind(name, ids). A scenario can also give
a raw 16-digit hex id instead of a kind name.
"""
import re

# Treasure Radar 0.5.1's KINDS (fallback when the addon source can't be parsed)
LOOT = {
    'credit': {'units': ['bd6f4de16b9aedcd']},
    'medal': {'units': ['773c4184e4bad0df']},
    'common': {'units': ['307e09e7698881ba', '294eda665270ac42', 'cf1ad44dedd1f257', '5016ee397fdcfb6c',
                         '64b49b9d8a445266', '700e9500e95541bf', '86f3cb87d97942b4', '4efcb7e844be9e93',
                         'a2414ed6e129c19f', 'b39fcf5c73d5c383', 'beb2a0f09e36bf72', 'd463836441cd0ba7',
                         'e4eeb96023df6a99']},
    'rare': {'units': ['8208ea6cb095be54', 'ad972a2e815a49aa', 'bd30758426ed2566', 'defe062c2567c23d']},
    'super': {'units': ['9d4935fa69b6b41a', 'b4d6f2f83bde45a9']},
    'requisition': {'units': ['da3c547d0e0e442f']},
    'ammo': {'units': ['79ccffd281e3f3a9'], 'supply': True},
    'grenade': {'units': ['97af34fbf093409c'], 'supply': True},
    'stim': {'units': ['b4ca4c5b922f7965'], 'supply': True},
}

# Kinds the addon doesn't draw (yet): add structures and objectives here, e.g.
#   'fabricator': {'units': ['0123456789abcdef'], 'group': 'structure'},
# Every entry needs 'units' (one or more hex ids); any other key is free-form and ends up in run.json.
EXTRA = {
}

# The camera unit's id (any id no kind uses)
CAMERA_UNIT = 'c0ffee00c0ffee00'

KIND_RE = re.compile(r"\{\s*id\s*=\s*'(\w+)'(.*?)units\s*=\s*\{([^}]*)\}", re.S)
HEX_RE = re.compile(r"'([0-9a-fA-F]{16})'")


def parse_addon_kinds(src):
    """{kind: {'units': [...], 'supply': bool, 'rgb': (r, g, b)}} from an addon's `local KINDS = { ... }` table."""
    if isinstance(src, bytes):
        src = src.decode('utf-8', 'replace')
    m = re.search(r'local\s+KINDS\s*=\s*\{', src)
    if not m:
        return {}
    out = {}
    for km in KIND_RE.finditer(src, m.end()):
        name, middle, units = km.group(1), km.group(2), km.group(3)
        if 'id =' in middle:          # walked into the next table: stop
            break
        ids = [h.lower() for h in HEX_RE.findall(units)]
        if not ids:
            continue
        rgb = re.search(r'rgb\s*=\s*\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', middle)
        out[name] = {'units': ids, 'supply': bool(re.search(r'supply\s*=\s*true', middle)),
                     'rgb': tuple(int(v) for v in rgb.groups()) if rgb else None}
        # the KINDS table ends at its closing "}" on a line of its own
        tail = src[km.end():km.end() + 40]
        if re.match(r'\s*\}\s*,?\s*\n\}', tail):
            break
    return out


def parse_addon_textures(src):
    """{texture hex: short name} from the addon's TEXTURES / GLYPHS assignments (names like 'medal', 'sweep',
    'glyph') or, for 0.6 bundles, its T.TEX table (names like 'icons/medal', 'radar/sweep/03')."""
    if isinstance(src, bytes):
        src = src.decode('utf-8', 'replace')
    names = {}
    for m in re.finditer(r"TEXTURES\.(\w+)(?:\[(\d+)\])?\s*=\s*'([0-9a-fA-F]{16})'", src):
        names[m.group(3).lower()] = m.group(1) if m.group(2) is None else '%s[%s]' % (m.group(1), m.group(2))
    for m in re.finditer(r"GLYPHS\[(\d+)\]\['(.)'\]\s*=\s*\{\s*'([0-9a-fA-F]{16})'", src):
        names[m.group(3).lower()] = 'glyph%s:%s' % (m.group(1), m.group(2))
    # 0.6 bundles: T.TEX['icons/medal'] = '<hex>' (names are texture paths)
    for m in re.finditer(r"T\.TEX\['([^']+)'\]\s*=\s*'([0-9a-fA-F]{16})'", src):
        names[m.group(2).lower()] = m.group(1)
    return names


class Registry:
    def __init__(self, addon_src=None):
        self.kinds = {}
        parsed = parse_addon_kinds(addon_src) if addon_src else {}
        self.source = 'addon' if parsed else 'fallback'
        for name, k in (parsed or LOOT).items():
            self.kinds[name] = dict(k, group='loot')
        for name, k in EXTRA.items():
            self.kinds.setdefault(name, dict(k))

    def add(self, name, units, **info):
        if isinstance(units, str):
            units = [units]
        self.kinds[name] = dict(info, units=[u.lower() for u in units])

    def resolve(self, kind, variant=0):
        """(kind name, hex id) for a kind name (the `variant`-th of its ids, wrapping) or a raw hex id."""
        if kind in self.kinds:
            ids = self.kinds[kind]['units']
            return kind, ids[variant % len(ids)]
        if re.fullmatch(r'[0-9a-fA-F]{1,16}', kind):
            hx = kind.lower().rjust(16, '0')
            for name, k in self.kinds.items():
                if hx in k['units']:
                    return name, hx
            return 'raw', hx
        raise KeyError('unknown unit kind %r (known: %s)' % (kind, ', '.join(sorted(self.kinds))))

    def all_ids(self):
        s = set()
        for k in self.kinds.values():
            s.update(k['units'])
        return s

    def names(self, group=None):
        return [n for n, k in self.kinds.items() if group is None or k.get('group') == group]
