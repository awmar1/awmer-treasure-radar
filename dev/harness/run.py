"""Treasure Radar test harness: runs a mod build's real Lua (Chef Loader + addons) in Lua 5.1 against a fake
Stingray engine through a scripted mission, and renders what it draws.

    python -I dev\\harness\\run.py --mod C:\\...\\Treasure-Radar-0.5.1 --options core,ledger,@loot,markers_50 \\
        --scenario mission --frames 120,240,10s

Output: dev\\harness\\out\\<scenario>\\ frame_NNNN.png, contact.png, run.json (and _run\\, the fake game folder:
data\\ with the patch files only with --keep-run, LocalAppData\\ with the loader's log, AppData\\Roaming\\ with the settings file).
Exit code: 0 ok, 1 the run aborted (engine crash, Lua error), 2 errors in the log or failed checks.
"""
import argparse
import os
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'tools', '_pylib'))
sys.path.insert(0, HERE)

import runner  # noqa: E402
import scenario as scenario_mod  # noqa: E402

# option groups: '@loot' -> every loot kind's option folder
GROUPS = {
    '@loot': ['credit', 'medal', 'common', 'rare', 'super', 'requisition', 'ammo', 'grenade', 'stim'],
    '@samples': ['common', 'rare', 'super'],
    '@supply': ['ammo', 'grenade', 'stim'],
}
GROUPS['@all-kinds'] = GROUPS['kinds'] = GROUPS['@loot']
# the same without the @ (PowerShell reads @name in a comma list as splatting unless it's quoted)
GROUPS['loot'], GROUPS['samples'], GROUPS['supply'] = GROUPS['@loot'], GROUPS['@samples'], GROUPS['@supply']


def expand_options(text, mod_dir):
    out = []
    for o in [x.strip() for x in text.split(',') if x.strip()]:
        for name in GROUPS.get(o, [o]):
            if name not in out:
                out.append(name)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mod', required=True, help='the mod folder (with core\\, ledger\\, ... option folders)')
    ap.add_argument('--options', default='core', help='option folders in load order, comma separated; '
                    'loot (or @loot) = every loot kind (%s); samples, supply' % ','.join(GROUPS['@loot']))
    ap.add_argument('--scenario', default='mission', help='a name in dev\\harness\\scenarios (.py / .json) or a path')
    ap.add_argument('--frames', default=None, help='frames to render: numbers and/or times like 4.5s (default: the '
                    "scenario's own); 'none' renders nothing")
    ap.add_argument('--out', default=None, help='output folder (default dev\\harness\\out\\<scenario>)')
    ap.add_argument('--seconds', type=float, default=None, help="override the scenario's length")
    ap.add_argument('--keep-run', action='store_true', help='keep the copies of the patch files in '
                    '<out>/_run/data (deleted after the run by default)')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args(argv)

    mod = os.path.abspath(a.mod)
    if not os.path.isdir(mod):
        raise SystemExit('no mod folder %s' % mod)
    sc = scenario_mod.load(a.scenario, os.path.join(HERE, 'scenarios'))
    if a.seconds:
        sc.seconds = a.seconds
    frames = None
    if a.frames is not None:
        frames = [] if a.frames.strip().lower() == 'none' else [f.strip() for f in a.frames.split(',') if f.strip()]
        frames = [f if f.endswith('s') else int(f) for f in frames]
    out = os.path.abspath(a.out or os.path.join(HERE, 'out', sc.name))
    opts = expand_options(a.options, mod)
    r = runner.Runner(mod, opts, sc, out, verbose=not a.quiet, keep_run=a.keep_run)
    res, rep = r.run(render=frames)

    say = print
    say('scenario %s: %d frames (%.1f s of game) in %.1f s' % (sc.name, rep['frames_run'], rep['seconds'],
                                                               rep['wall_seconds']))
    for pat in (r'\| started ', r'\| world \d+: ', r'ledger: '):
        lines = res.log_lines(pat)
        if lines:
            say('  log: ' + lines[-1].strip()[:200])
    if rep['aborted']:
        say('ABORTED: ' + rep['aborted'])
        if rep['crash'] and rep['crash'].get('traceback'):
            say(rep['crash']['traceback'])
    for l in rep['addon_errors'][:10]:
        say('  log error: ' + l.strip()[:200])
    for w in rep['warnings'][:10]:
        say('  warning x%d (from frame %d): %s' % (w['count'], w['first_frame'], w['message'][:160]))
    if rep['missing_engine_functions']:
        say('  missing engine functions: ' + ', '.join(m['name'] for m in rep['missing_engine_functions']))
    if rep['unknown_textures']:
        say('  unknown textures: ' + ', '.join(u['texture'] for u in rep['unknown_textures'][:12]))
    for c in rep['checks']:
        say('  [%s] %s%s' % ('ok' if c['ok'] else 'FAIL', c['check'], (': ' + c['detail']) if c['detail'] else ''))
    say('frames: ' + ', '.join(x['png'] for x in rep['rendered']))
    say('out: ' + out)
    if rep['aborted']:
        return 1
    return 0 if rep['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
