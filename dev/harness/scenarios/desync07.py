"""0.7.1: the game ignores some Map presses (a fast double tap, the map's animation: the player's 0.7.0 log), so the
mod's Map toggle drifts and the radar vanishes with the map closed, or draws over the open map. The mouse sets it
right (mapview.lua): with the map closed the camera turns with the mouse, with it open it stays still. Like the real
game, two more worlds are there all mission long, so it's key mode.

  7.0 s   I look around (the camera follows the mouse): from now on a still camera may say the map is open
  9.0 s   Tab, but the game ignores it: the mod hides the radar (0.7.0's bug)
 10.0 s   I look around: the camera turns with the mouse, so the map is closed and the radar is back
 13.0 s   Tab opens the map; 14.0 s Tab again, ignored (the map stays open): the radar draws over the map
 15.0 s   I move the mouse on the map, the camera stays still: the map is open again
 18.0 s   Tab closes it
 19.5 s   Esc (the pause menu), then the mouse moves with the camera still: that opens nothing

Run:  python -I dev/harness/run.py --mod dev/build/Treasure-Radar-0.7.1 --scenario desync07 \
        --options core,loot_all,extras_all,radar_medium,markers_50,opacity_100
"""


def build(s):
    s.screen(1920, 1080).run(seconds=22, fps=30)

    s.world('ship', at=0.0, filler=3200, spread=60, seed=11)
    s.world('mission', at=1.0, filler=4000, spread=300, seed=7)
    s.world('hud_a', at=1.0, main=False)
    s.world('hud_b', at=1.0, main=False)

    s.unit('medal', 6, 28)
    s.unit('rare', 25, 10)
    s.unit('common', -30, 40)
    s.unit('super', 60, -20)

    s.camera(0.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(7.0, 0, 0, 1.8, yaw=0, pitch=-6)
    s.camera(7.5, 0, 0, 1.8, yaw=40, pitch=-6)       # looking around, the mouse below
    s.camera(10.0, 0, 0, 1.8, yaw=40, pitch=-6)
    s.camera(10.5, 0, 0, 1.8, yaw=80, pitch=-6)      # again, after the ignored Tab
    s.camera(22.0, 0, 0, 1.8, yaw=80, pitch=-6)      # still from here on: the map, then the pause menu

    s.raw_mouse(7.0, 7.5, 10, 0)
    s.press('tab', 9.0)                              # ignored by the game: no map
    s.raw_mouse(10.0, 10.5, 10, 0)
    s.map_open(13.0, 18.0, press=False)              # the game's map, 13 to 18 s
    s.press('tab', 13.0)                             # opens it
    s.press('tab', 14.0)                             # ignored by the game: the map stays open
    s.raw_mouse(15.0, 16.0, 20, 5)                   # moving round the map: the camera stays still
    s.press('tab', 18.0)                             # closes it
    s.press('escape', 19.5)                          # the pause menu
    s.raw_mouse(20.2, 21.2, 20, 0)                   # the menu's cursor: the camera stays still

    s.render_frames('6.5s', '9.4s', '11s', '13.6s', '14.6s', '16.5s', '19s', '21.5s')

    # ---------------------------------------------------------------- checks
    s.check('no frame errors', lambda r: not r.log_has(r'frame error'))
    s.check('key mode (worlds there from the start)',
            lambda r: r.log_has(r'map: a second world is there with the map closed too; the Map key decides'))

    def radar(frame):
        return lambda r: r.count(frame, world='main', tex='radar/')

    def ignored_open(r):
        before, hidden, back = radar('6.5s')(r), radar('9.4s')(r), radar('11s')(r)
        said = r.log_has(r'map: closed \(the camera turns with the mouse')
        return before > 0 and hidden == 0 and back > 0 and said, \
            'radar/* draws: before %s, after the ignored Tab %s, after looking around %s; logged: %s' % (
                before, hidden, back, said)
    s.check('an ignored Tab hides the radar; looking around brings it back', ignored_open)

    def ignored_close(r):
        # the map's draws in the top world: 0.7's rim (TOP + 900-919) or 0.8's overlay and legend (TOP + 920-949)
        opened, drifted, fixed = (r.count(f, world='top', layer=(1900, 1949)) for f in ('13.6s', '14.6s', '16.5s'))
        over = radar('14.6s')(r)
        said = r.log_has(r'map: open \(the mouse moves and the camera stays still')
        return opened > 0 and drifted == 0 and over > 0 and fixed > 0 and radar('16.5s')(r) == 0 and said, \
            'map draws: open %s, after the ignored Tab %s (radar/* %s), after the mouse %s (radar/* %s); logged: %s' % (
                opened, drifted, over, fixed, radar('16.5s')(r), said)
    s.check('an ignored Tab on the open map: moving the mouse with the camera still opens it again', ignored_close)
    s.check('Tab closes it', lambda r: (r.count('19s', world='top') == 0 and radar('19s')(r) > 0,
                                        'top-world draws %s, radar/* %s' % (r.count('19s', world='top'),
                                                                             radar('19s')(r))))

    def esc(r):
        n = len(r.log_lines(r'map: open \(the mouse moves'))
        top = r.count('21.5s', world='top')
        return n == 1 and top == 0, 'mouse opens logged %d (1 expected); top-world draws in the menu %s' % (n, top)
    s.check('after Esc the mouse opens nothing', esc)
