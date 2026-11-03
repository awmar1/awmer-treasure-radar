# Treasure Radar companion (C#)

`TreasureRadarCompanion.exe` tells the mod where the open tactical map is looking. A Lua mod can't read that: on the two closer zoom levels the map centres on a cursor whose position lives in the game's native HUD. So the companion looks at the map on screen, finds the player's icon or the 65 m grid, works out the view centre, and hands it to the mod in a small text file.

This is the release build of the Python companion in `dev/companion/` (1.3, interface v1.2, see `dev/docs/COMPANION_INTERFACE.md`), which stays as the reference. It needs no Python, opens no window, and is about 60 KB.

## What it reads

| What | Where | When |
|---|---|---|
| The mod's status line | `%LOCALAPPDATA%\Temp\treasure_radar_mod.txt` | 10 times a second while idle, up to 30 while the map is open |
| Pixels of the map circle only, about 444 x 444 at 1080p | the game window's area, by GDI `BitBlt`; the primary screen if no game window is found | only while the mod's line is fresh and says the map is open |
| Whether the game is running | the window title `HELLDIVERS™ 2`, about once a second; the process name `helldivers2`, every 10 s, and only when the window isn't found | while the program runs |

Captured pixels stay in memory and are overwritten by the next frame.

## What it writes

Everything goes in `%LOCALAPPDATA%\Temp`:

| File | Content |
|---|---|
| `treasure_radar_fix.txt` | One line: sequence number, time, method, view centre, error estimate, zoom level, grid cell. Written as `.tmp`, then swapped in, so the mod never sees half a line. |
| `treasure_radar_companion.log` | State changes and a summary every 5 s while the map is open. It is replaced at each start and stops at 256 KB. It holds the folder path, which includes your Windows user name, and the game window's title and position. |
| `treasure_radar_frames\` | **Only with `--record`.** Up to 100 PNG captures of the map circle, plus `frames.txt`. They show whatever is on screen in that box, so check them before you share them. Each `--record` start deletes the PNG and TXT files from the previous one. |

It writes nothing else: no registry keys, no autostart entry, no settings, and nothing in the game folder.

## What it never does

- **No network.** There is no network code, and it sends nothing anywhere. You can check this by searching the source, or by listing the exe's references: `mscorlib`, `System`, `System.Core`, `System.Drawing`, `System.Numerics`. `System.dll` is there for `Process` and `Stopwatch`; it contains network classes too, but nothing here calls them.
- **No touching the game.** It doesn't read or write game memory, inject code, hook windows or send input. All it gets from the game is the same pixels you see.
- **No admin rights.**

We can't promise how any anti-cheat will treat a program that captures part of the screen. It uses the same plain Windows capture call that screenshot tools use. Don't run it if that's a risk you don't want.

## How it behaves

- **One instance:** a second start exits at once and leaves the first one's log alone (mutex `Local\TreasureRadarCompanion.1`).
- **Exits by itself:** after 10 minutes if the game never appears, or 30 s after the game has gone. The game counts as there while its window or process exists, or while the mod's line is still changing.
- **DPI:** per-monitor aware, so captures are in real pixels.
- **Capture source:** window-relative, so the game can be on either monitor. Exclusive fullscreen can't be captured this way; the log says so when the capture stays frozen. Use borderless.

Measured on the development PC with no game running, both programs against a fake mod in one session. These figures vary by a few tenths between runs (Python's idle figure ranged from 0.16% to 1.17%), so read them as "well under 1%" when idle:

| Share of one core | C# | Python |
|---|---|---|
| Idle, mod writing, map closed | 0.08-0.59% | 0.20-1.17% |
| Idle, no mod file | 0.16% | 0.16% |
| Idle, stale mod file | 0.16% | 0.31% |
| Capturing at 30 Hz | 25-29% | 32-45% |

Peak memory is about 35 MB.

## Command line

```
TreasureRadarCompanion.exe                     run until the game has gone
  --dir D                                      use folder D instead of %LOCALAPPDATA%\Temp
  --log                                        one line per frame (when started from a console)
  --once                                       one cycle, then exit
  --record                                     keep some captures as PNG (see above)
  --grace-start S, --grace-gone S              the exit waits, default 600 and 30 seconds
  --shot S.png --mod "seq=1 ... end" [--once]  detect on a screenshot, print the fix line
  --shot S.png --dir D --once                  one file cycle with the screenshot as the screen
  --prior vx,vy[,err]                          with --mod: a prior view centre, in metres
  --bench N                                    with --mod: repeat the detection, print the time
  --batch LIST, --seq LIST                     replay rows of png<TAB>mod line[<TAB>prior]
```

## Build it yourself

You only need the C# compiler that Windows 10 and 11 include:

```bash
dev\companion_cs\build.cmd
```

The output is `dev\build\companion\TreasureRadarCompanion.exe`. If it stops with `CS0016`, the old exe is still locked: close the companion, or wait a few seconds for antivirus to finish scanning it.

## Verify the shipped exe

This build:

- Size: 59904 bytes
- SHA-256: `3E9FEAA07A533A4B72EBAB910FC15AFC7BD858C321BEC1167EAB48BCC1B85A99`
- Compiler: `csc.exe` 4.8.9221.0, the one in `%WINDIR%\Microsoft.NET\Framework64\v4.0.30319`

**The build is not byte-for-byte reproducible, so your own build will have a different SHA-256.** This compiler rejects `/deterministic` (`error CS2007: Unrecognized option`). Two builds of the same source had the same size and differed in exactly three places: the PE timestamp, the 16-byte module id (MVID), and a 36-character generated GUID name. The output folder made no difference.

`verify_build.ps1` builds the source in a temporary folder and compares the result with an exe, allowing only those three places to differ:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File dev\companion_cs\verify_build.ps1 C:\path\to\TreasureRadarCompanion.exe
```

It prints `MATCH` or `DIFFERENT`. A different compiler version may produce different code, so use the version above.

## Tests

These need Python with Pillow (`dev/tools/_pylib` has it) and don't start the game:

```bash
python -B dev/companion_cs/compare.py
```

Runs Python and C# on the same frames and compares every fix line and log line. It covers `dev/companion/fixtures` and any frames recorded in `%LOCALAPPDATA%\Temp\treasure_radar_frames`, which it only reads.

```bash
python -B dev/companion_cs/parity_probe.py
```

Checks the image code in `Detect.cs` against Pillow, byte for byte. Set `PYTHONPATH=dev/tools/_pylib` first.

```bash
python -B dev/companion_cs/test_lifecycle.py
```

Tests the file protocol, single instance, automatic exit, `--record` and CPU use. The game must be closed, and it captures the map-circle box of your primary screen into memory while it runs.
