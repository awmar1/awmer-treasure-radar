"""Writes dev/src/addon/structures.lua (the map's kinds: objectives, structures, nests, POIs, extraction) from the
research table dev/research/structures_data.lua.

    python -I dev/tools/gen_structures.py

Output is compact data, no notes: return { kinds = { { id, cat, label, units, faction, conf, done, tex, rgb? }, ... } }
  cat     the research's `category` (objective side_objective structure nest poi extract)
  label   short HUD label, uppercase, only characters the glyph textures cover
  conf    'verified' | 'likely' | 'guess' (objectives.lua ships guesses only in Tester builds)
  done    the research's done_signal: 'unknown' or 'swap:<16 hex>'
  tex     the shared white map icon (dev/src/art/map_icons.py), tinted with rgb at draw time
  rgb     only where kinds.lua's default isn't right (side objectives, extraction); objectives default to
          config.RGB.objective, nests and structures to config.RGB.hostile, POIs to config.RGB.text (cream)
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '_pylib'))
from lupa import lua51  # noqa: E402

DEV = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
SRC = os.path.join(DEV, 'research', 'structures_data.lua')
OUT = os.path.join(DEV, 'src', 'addon', 'structures.lua')

GLYPHS = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ.,:/-+%'()?!#<> ")
CATS = ('objective', 'side_objective', 'structure', 'nest', 'poi', 'extract')
CONFS = ('verified', 'likely', 'guess')

# Side objectives: the wiki says the game marks them blue. A saturated blue is close to the stim icon (60, 140, 255)
# and reads dark on the map; the ping cyan (113, 245, 255) and the player yellow (255, 233, 0) are off limits. A light
# violet-blue keeps "blue = side objective" at a clearly different hue and lightness from all three.
RGB_SIDE = (150, 140, 255)
RGB_EXTRACT = (255, 136, 36)      # the game's extraction icon is orange (config.RGB.objective)

LABELS = {
    'bug_hole_small': 'BUG HOLE', 'bug_hole_medium': 'BUG HOLE', 'bug_hole_large': 'BUG HOLE',
    'bug_colony_spawner': 'BUG HOLE', 'shrieker_nest': 'SHRIEKER NEST', 'spore_spewer': 'SPORE SPEWER',
    'tcs_tower': 'TCS TOWER', 'egg_sack': 'EGG SACKS', 'spore_lung': 'SPORE LUNG', 'hive_core_drill': 'CORE DRILL',
    'thumper': 'THUMPER', 'fabricator': 'FABRICATOR', 'automaton_bunker': 'BOT BUNKER',
    'automaton_colony_spawner': 'BOT SPAWNER', 'cannon_tower': 'CANNON TURRET', 'turret_emplacement': 'TURRET',
    'aa_emplacement': 'AA TURRET', 'factory_chimney': 'FACTORY', 'landing_pad': 'LANDING PAD',
    'detector_tower': 'DETECTOR TOWER', 'stratagem_jammer': 'STRATAGEM JAMMER',
    'gunship_facility': 'GUNSHIP FABRICATOR', 'command_bunker': 'COMMAND BUNKER', 'airbase_tower': 'CONTROL TOWER',
    'ammo_stockpile': 'AMMO STOCKPILE', 'network_tower': 'NETWORK TOWER',
    'automaton_orbital_cannon': 'ORBITAL CANNON', 'assembly_site': 'ASSEMBLY SITE', 'uranium_silo': 'URANIUM SILO',
    'resource_silo': 'RESOURCE SILO', 'cooling_structure': 'COOLING TOWER', 'drug_distillery': 'DISTILLERY',
    'refinery': 'REFINERY', 'filling_station': 'FILLING STATION', 'hack_turrets': 'TURRETS',
    'automaton_terminal': 'TERMINAL', 'automaton_intel': 'INTEL', 'automaton_dropoff': 'DROP-OFF',
    'mine_bunker_entrance': 'MINE ENTRANCE', 'illuminate_spawner': 'WARP PORTAL',
    'illuminate_attack_ship': 'ATTACK SHIP', 'illuminate_turret': 'TURRET', 'illuminate_turret_tactical': 'TURRET',
    'illuminate_tesla_tower': 'TESLA TOWER', 'illuminate_laser_tower': 'LASER TOWER',
    'illuminate_shield_module': 'SHIELD MODULE', 'illuminate_module_base': 'TECH HUB',
    'stratagem_scrambler': 'SCRAMBLER', 'harvester_site': 'HARVESTER', 'monolith': 'MONOLITH',
    'landed_ship': 'LANDED SHIP', 'weather_device': 'WEATHER DEVICE', 'water_temple_well': 'TEMPLE WELL',
    'portal_batteries': 'BATTERIES', 'illuminate_gate': 'GATE', 'sarcophagus': 'SARCOPHAGUS',
    'icbm_silo': 'ICBM SILO', 'sam_site': 'SAM SITE', 'seaf_artillery': 'SEAF ARTILLERY',
    'communications_relay': 'COMMS RELAY', 'colony_relay': 'COLONY RELAY', 'power_station': 'POWER STATION',
    'research_station': 'RESEARCH STATION', 'oil_pump': 'OIL PUMP', 'prospecting_drill': 'DRILL',
    'seismic_probe': 'SEISMIC PROBE', 'generator': 'GENERATOR', 'truth_transmitter': 'TRANSMITTER',
    'intel': 'INTEL', 'escape_pod': 'ESCAPE POD', 'black_box': 'BLACK BOX', 'cargo_container': 'CARGO',
    'civilian_door': 'CIVILIAN DOOR', 'shuttle_hatch': 'SHUTTLE HATCH', 'flag': 'FLAG',
    'objective_dropoff': 'DROP-OFF', 'city_cannon': 'ORBITAL CANNON', 'bunker_cache': 'BUNKER CACHE',
    'super_earth_cache': 'SUPPLY CACHE', 'smuggler_cache': 'SMUGGLER CACHE', 'exploration_cache': 'REWARD BOX',
    'intel_sample': 'INTEL', 'extraction': 'EXTRACTION',
}

# shared icons (dev/src/art/map_icons.py): by type first, then by category and faction
TOWERS = {'detector_tower', 'stratagem_jammer', 'stratagem_scrambler', 'tcs_tower', 'network_tower',
          'truth_transmitter', 'communications_relay', 'colony_relay', 'airbase_tower', 'weather_device'}
SILOS = {'icbm_silo'}


def tex_for(k):
    kid, cat, fac = k['id'], k['cat'], k['faction']
    if kid in SILOS:
        return 'map/silo'
    if kid in TOWERS:
        return 'map/tower'
    if cat == 'nest':
        return 'map/nest'
    if cat == 'structure':
        return {'terminid': 'map/nest', 'automaton': 'map/outpost', 'illuminate': 'map/illuminate'}.get(fac, 'map/outpost')
    return {'objective': 'map/objective', 'side_objective': 'map/side', 'poi': 'map/poi',
            'extract': 'map/extract'}[cat]


def rgb_for(k):
    if k['cat'] == 'side_objective':
        return RGB_SIDE
    if k['cat'] == 'extract':
        return RGB_EXTRACT
    return None


def lua_list(t):
    return [t[i] for i in range(1, len(t) + 1)]


def main():
    L = lua51.LuaRuntime(unpack_returned_tuples=True)
    data = L.execute(open(SRC, encoding='utf-8').read())
    kinds, seen = [], set()
    for e in lua_list(data):
        kid = e['id']
        if kid in seen:
            raise SystemExit('duplicate kind id %s' % kid)
        seen.add(kid)
        cat, conf, done = e['category'], e['confidence'], e['done_signal'] or 'unknown'
        if cat not in CATS:
            raise SystemExit('%s: unknown category %r' % (kid, cat))
        if conf not in CONFS:
            raise SystemExit('%s: unknown confidence %r' % (kid, conf))
        if done != 'unknown' and not re.fullmatch(r'swap:[0-9a-f]{16}', done):
            raise SystemExit('%s: unknown done signal %r' % (kid, done))
        label = LABELS.get(kid)
        if not label:
            raise SystemExit('%s: no label (add it to LABELS)' % kid)
        bad = set(label) - GLYPHS
        if bad or label != label.upper():
            raise SystemExit('%s: label %r has characters the glyphs lack: %r' % (kid, label, sorted(bad)))
        units = lua_list(e['units'])
        for u in units:
            if not re.fullmatch(r'[0-9a-f]{16}', u):
                raise SystemExit('%s: bad unit id %r' % (kid, u))
        k = {'id': kid, 'cat': cat, 'label': label, 'units': units, 'faction': e['faction'] or 'any', 'conf': conf,
             'done': done}
        k['tex'] = tex_for(k)
        k['rgb'] = rgb_for(k)
        kinds.append(k)
    unused = set(LABELS) - seen
    if unused:
        print('note: labels for ids not in the data: %s' % ', '.join(sorted(unused)))

    out = ['local T, chef = ...',
           '-- Generated by dev/tools/gen_structures.py from dev/research/structures_data.lua: do not edit by hand.',
           "-- The map's kinds (see kinds.lua and CONTRACT.md). conf: verified and likely ship in every build, guess only",
           '-- in Tester builds (objectives.lua). done: unknown, or swap:<unit id> (a destroyed variant spawns in its place).',
           'return { kinds = {']
    for k in kinds:
        units = ', '.join("'%s'" % u for u in k['units'])
        rgb = ', rgb = { %d, %d, %d }' % k['rgb'] if k['rgb'] else ''
        out.append("  { id = '%s', cat = '%s', label = '%s', units = { %s }, faction = '%s', conf = '%s', done = '%s', "
                   "tex = '%s'%s }," % (k['id'], k['cat'], k['label'], units, k['faction'], k['conf'], k['done'],
                                         k['tex'], rgb))
    out.append('} }')
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(out) + '\n')

    # check: the written file loads under Lua 5.1 and holds the same kinds
    back = L.execute(open(OUT, encoding='utf-8').read())
    assert len(lua_list(back['kinds'])) == len(kinds)
    by = {}
    for k in kinds:
        by.setdefault(k['conf'], []).append(k['id'])
    texs = sorted(set(k['tex'] for k in kinds))
    print('wrote %s: %d kinds (%s); textures used: %s' % (
        os.path.relpath(OUT, DEV), len(kinds), ', '.join('%s %d' % (c, len(by.get(c, []))) for c in CONFS),
        ', '.join(texs)))
    print('normal builds (verified + likely): %s' % ', '.join(by.get('verified', []) + by.get('likely', [])))


if __name__ == '__main__':
    main()
