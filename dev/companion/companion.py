"""Treasure Radar companion: tells the mod where the open tactical map is looking.

It reads the mod's line (treasure_radar_mod.txt), captures only the map circle from the game's window (1.3: on any
monitor, the box taken relative to the window's client area; the primary screen when no game window is found), finds
the player's own icon (or the 65 m grid) in it, and writes the view centre V to treasure_radar_fix.txt. The file format
is dev/docs/COMPANION_INTERFACE.md (v1.2). Pixels only: no game memory, no input, no window hooks, no network (the
game's window is only looked up by its title, for where it sits on the desktop).

Both files live in %LOCALAPPDATA%\\Temp, the one AppData folder the Microsoft Store Python does not redirect into
its package. Next to them the companion keeps its own log (treasure_radar_companion.log, new at every start) and a
folder of recorded captures (treasure_radar_frames: PNGs of the circle, a few per map open and the frames that gave
no fix, with frames.txt naming each one's mod line and fix line) for replay with --shot and --mod.

    python companion.py                 run until Ctrl+C (run_companion.cmd sets PYTHONPATH for Pillow)
    python companion.py --log           ... with one line per frame
    python companion.py --dir D         use folder D instead of %LOCALAPPDATA%\\Temp
    python companion.py --once          one cycle, then exit
    python companion.py --shot S.jpg --mod "seq=1 ... end"      detect on a screenshot, print the fix line (S: a
                                                                full screen, or a recorded frame of the circle)
    python companion.py --shot S.jpg --dir D --once             one file cycle with the screenshot as the screen
"""
import argparse
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

try:
    from PIL import Image
except ImportError:                                   # pragma: no cover
    sys.stderr.write('Pillow is missing. Start the companion with run_companion.cmd (it points PYTHONPATH at '
                     'dev\\tools\\_pylib).\n')
    sys.exit(2)

import detect

VERSION = '1.3 (interface v1.2)'
MOD_FILE = 'treasure_radar_mod.txt'
FIX_FILE = 'treasure_radar_fix.txt'
LOG_FILE = 'treasure_radar_companion.log'    # the companion's own log, new at every start
FRAMES_DIR = 'treasure_radar_frames'         # recorded captures (PNG) and frames.txt, for replay
FRAMES_LIST = 'frames.txt'
FRAMES_MAX = 100                             # recorded frames per companion session, then one note
FRAMES_FIRST = 3                             # ... of them the first frames of every map open
PERIOD = 1.0 / 30                 # at most 30 fixes per second
IDLE_SLEEP = 0.100                # the interface: idle polls every 100 ms
STALE_S = 1.0                     # no new seq for this long: the game is not writing (closed, paused, alt-tabbed)
GAME_TITLE = 'HELLDIVERS\u2122 2'    # the game window's title (FindWindowW)
GAME_PART = 'HELLDIVERS'           # ... else the foreground window, when its title holds this
STATIC_N = 20                      # this many byte-identical captures in a row while open=1: the capture is static
STATIC_NOTE = ("the capture is static: the game's window is not being captured (exclusive fullscreen? try "
               "borderless)")


# ---------------------------------------------------------------------------------------------------- the files
def default_dir():
    """%LOCALAPPDATA%\\Temp, made when missing. Temp and not %LOCALAPPDATA% itself: the Microsoft Store Python is an
    MSIX package, and Windows redirects a package's writes under %LOCALAPPDATA% and %APPDATA% into
    %LOCALAPPDATA%\\Packages\\<package>\\LocalCache, where the game never looks; Temp is exempt."""
    d = os.environ.get('LOCALAPPDATA')
    if not d:
        d = os.path.join(os.path.expanduser('~'), 'AppData', 'Local')
    d = os.path.join(d, 'Temp')
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def packaged_python():
    """True when this interpreter runs inside an MSIX package (the Microsoft Store Python): kernel32's
    GetCurrentPackageFullName answers APPMODEL_ERROR_NO_PACKAGE (15700) for a plain process and anything else (the
    buffer size error) for a packaged one. Not Windows, or no such function: not packaged."""
    try:
        import ctypes
        fn = ctypes.WinDLL('kernel32').GetCurrentPackageFullName
        fn.argtypes = [ctypes.POINTER(ctypes.c_uint32), ctypes.c_wchar_p]
        fn.restype = ctypes.c_int32
        n = ctypes.c_uint32(0)
        return fn(ctypes.byref(n), None) != 15700
    except Exception:
        return False


STORE_NOTE = (
    'note: this Python is the Microsoft Store build (an MSIX package). Windows redirects its writes under',
    '      %LOCALAPPDATA% and %APPDATA% into the package\'s own folder, where the game never looks, so the',
    '      companion keeps its files in %LOCALAPPDATA%\\Temp. If the mod\'s log (%LOCALAPPDATA%\\treasure_radar.log)',
    '      shows no "companion:" lines while this runs, install Python from python.org and start it again.')


def parse_line(text):
    """One `key=value ... end` line as a dict of strings, or None when the line is partial (no trailing `end`)."""
    if not text:
        return None
    line = text.splitlines()[0] if text.strip() else ''
    toks = line.split()
    if not toks or toks[-1] != 'end':
        return None
    out = {}
    for t in toks[:-1]:
        k, sep, v = t.partition('=')
        if sep:
            out[k] = v
    return out


def read_mod(path):
    """(dict or None, mtime or None, the line as read). None, None, '' when the file is missing; None, mtime, text
    when the line is partial."""
    try:
        st = os.stat(path)
        with open(path, 'rb') as f:
            raw = f.read(4096)
    except OSError:
        return None, None, ''
    text = raw.decode('utf-8', 'replace')
    return parse_line(text), st.st_mtime, text.strip()


def num(v, nd):
    """A plain decimal with nd decimals (never an exponent, never -0.0)."""
    s = '%.*f' % (nd, v)
    if s.lstrip('-').strip('0.') == '':
        s = s.lstrip('-')
    return s


def format_fix(seq, ts, fix):
    parts = ['seq=%s' % seq, 'ts=%s' % num(ts, 3), 'how=%s' % fix['how']]
    if fix['how'] != 'none':
        parts += ['vx=%s' % num(fix['vx'], 1), 'vy=%s' % num(fix['vy'], 1)]
    parts += ['err=%s' % num(fix.get('err', 0.0), 1), 'level=%s' % fix['level'],
              'cell=%s' % num(fix.get('cell', 0.0), 1), 'end']
    return ' '.join(parts)


def write_fix(path, line):
    """Write the line to path.tmp and replace path with it. False when the target stayed busy (the mod reading it)."""
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='ascii', newline='\n') as f:
        f.write(line + '\n')
    for i in range(4):
        try:
            os.replace(tmp, path)
            return True
        except PermissionError:                       # Windows: the mod has the file open this very moment
            time.sleep(0.002 * (i + 1))
    return False


# ---------------------------------------------------------------------------------------------------- capture
def _dpi_aware():
    """Physical pixels: without this a scaled desktop (125 %, 150 %) would hand us scaled coordinates."""
    try:
        import ctypes
        try:
            if ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):   # per monitor v2
                return
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except (AttributeError, OSError):
            pass
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


class ScreenGrabber:
    """The game window's client area through GDI BitBlt of just the box (PIL's ImageGrab copies the whole screen
    first). 1.3: the window is found by its title (GAME_TITLE; else the foreground window whose title holds
    GAME_PART), its client rect taken in screen coordinates (GetClientRect + ClientToScreen), and the box, in the
    client's pixels, offset by the client's origin; screen_size() is the client's size, so capture() scales the mod's
    w, h against it. No game window: the primary screen, as 1.2. self.where says which, for the log."""

    name = 'screen'

    def __init__(self):
        self.mode = None
        self.why = ''
        self._size = None
        self._hwnd = None
        self._org = (0, 0)
        self.where = 'the primary screen (no game window found)'
        _dpi_aware()                                  # per-monitor v2, before any GDI or window call
        try:
            self._init_gdi()
            self.mode = 'bitblt'
        except Exception as e:                        # not Windows, or GDI refused: fall back to PIL
            self.why = 'BitBlt unavailable (%s)' % e
            try:
                from PIL import ImageGrab
                self._grab = ImageGrab.grab
                self.mode = 'imagegrab'
            except Exception as e2:
                self.why += '; ImageGrab unavailable (%s)' % e2

    def _init_gdi(self):
        import ctypes
        from ctypes import wintypes
        u, g = ctypes.WinDLL('user32'), ctypes.WinDLL('gdi32')
        H = ctypes.c_void_p
        u.GetDC.restype, u.GetDC.argtypes = H, [H]
        u.ReleaseDC.argtypes = [H, H]
        u.GetSystemMetrics.argtypes = [ctypes.c_int]
        u.FindWindowW.restype, u.FindWindowW.argtypes = H, [wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.GetForegroundWindow.restype, u.GetForegroundWindow.argtypes = H, []
        u.GetWindowTextW.restype, u.GetWindowTextW.argtypes = ctypes.c_int, [H, wintypes.LPWSTR, ctypes.c_int]
        u.IsWindow.restype, u.IsWindow.argtypes = wintypes.BOOL, [H]
        u.IsIconic.restype, u.IsIconic.argtypes = wintypes.BOOL, [H]
        u.GetClientRect.restype, u.GetClientRect.argtypes = wintypes.BOOL, [H, ctypes.POINTER(wintypes.RECT)]
        u.ClientToScreen.restype, u.ClientToScreen.argtypes = wintypes.BOOL, [H, ctypes.POINTER(wintypes.POINT)]
        self._wt = wintypes
        g.CreateCompatibleDC.restype, g.CreateCompatibleDC.argtypes = H, [H]
        g.CreateCompatibleBitmap.restype, g.CreateCompatibleBitmap.argtypes = H, [H, ctypes.c_int, ctypes.c_int]
        g.SelectObject.restype, g.SelectObject.argtypes = H, [H, H]
        g.DeleteObject.argtypes = [H]
        g.DeleteDC.argtypes = [H]
        g.BitBlt.argtypes = [H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, H, ctypes.c_int,
                             ctypes.c_int, wintypes.DWORD]
        g.GetDIBits.argtypes = [H, H, wintypes.UINT, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]

        class BMIH(ctypes.Structure):
            _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                        ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD),
                        ('biCompression', wintypes.DWORD), ('biSizeImage', wintypes.DWORD),
                        ('biXPelsPerMeter', wintypes.LONG), ('biYPelsPerMeter', wintypes.LONG),
                        ('biClrUsed', wintypes.DWORD), ('biClrImportant', wintypes.DWORD)]

        self._ct, self._u, self._g, self._BMIH = ctypes, u, g, BMIH
        self._hdc = u.GetDC(None)
        if not self._hdc:
            raise OSError('GetDC failed')
        self._mdc = g.CreateCompatibleDC(self._hdc)
        if not self._mdc:
            raise OSError('CreateCompatibleDC failed')
        self._bm = None

    def _title(self, hwnd):
        buf = self._ct.create_unicode_buffer(256)
        self._u.GetWindowTextW(hwnd, buf, 256)
        return buf.value

    def _find(self):
        """The game's window: the one found before while it still exists, else FindWindowW by its title, else the
        foreground window when its title holds GAME_PART. None: not found."""
        u = self._u
        if self._hwnd and u.IsWindow(self._hwnd):
            return self._hwnd
        hwnd = u.FindWindowW(None, GAME_TITLE)
        if not hwnd:
            fg = u.GetForegroundWindow()
            if fg and GAME_PART in self._title(fg).upper():
                hwnd = fg
        self._hwnd = hwnd or None
        return self._hwnd

    def _client(self):
        """(x, y, w, h) of the game window's client area in screen pixels, or None (no window, or minimised)."""
        hwnd = self._find()
        if not hwnd or self._u.IsIconic(hwnd):
            return None
        wt, ct = self._wt, self._ct
        r = wt.RECT()
        if not self._u.GetClientRect(hwnd, ct.byref(r)):
            self._hwnd = None
            return None
        pt = wt.POINT(0, 0)
        if not self._u.ClientToScreen(hwnd, ct.byref(pt)):
            self._hwnd = None
            return None
        w, h = r.right - r.left, r.bottom - r.top
        if w <= 0 or h <= 0:
            return None
        return pt.x, pt.y, w, h

    def screen_size(self):
        if self.mode == 'bitblt':
            c = self._client()
            if c:
                x, y, w, h = c
                self._org = (x, y)
                self.where = 'the game window "%s", client %dx%d at (%d, %d)' % (self._title(self._hwnd), w, h, x, y)
                return w, h
            self._org = (0, 0)
            self.where = 'the primary screen (no game window found)'
            return self._u.GetSystemMetrics(0), self._u.GetSystemMetrics(1)
        if self.mode == 'imagegrab':
            if self._size is None:
                self._size = self._grab().size     # one full grab, once
            return self._size
        return None

    def grab(self, box):
        x0, y0, x1, y1 = box
        w, h = x1 - x0, y1 - y0
        if self.mode == 'imagegrab':
            return self._grab(bbox=box).convert('RGB')
        if self.mode != 'bitblt':
            raise OSError(self.why)
        ct, g = self._ct, self._g
        if self._size != (w, h):
            if self._bm:
                g.DeleteObject(self._bm)
            self._bm = g.CreateCompatibleBitmap(self._hdc, w, h)
            if not self._bm:
                raise OSError('CreateCompatibleBitmap failed')
            bi = self._BMIH()
            bi.biSize, bi.biWidth, bi.biHeight = ct.sizeof(self._BMIH), w, -h        # top-down rows
            bi.biPlanes, bi.biBitCount, bi.biCompression = 1, 32, 0                 # BI_RGB, BGRX
            self._bi = bi
            self._buf = ct.create_string_buffer(w * h * 4)
            self._size = (w, h)
        old = g.SelectObject(self._mdc, self._bm)
        ox, oy = self._org                            # the client's origin, from this frame's screen_size()
        ok = g.BitBlt(self._mdc, 0, 0, w, h, self._hdc, x0 + ox, y0 + oy, 0x00CC0020)       # SRCCOPY
        g.SelectObject(self._mdc, old)                # GetDIBits wants the bitmap out of the DC
        if not ok:
            raise OSError('BitBlt failed')
        rows = g.GetDIBits(self._mdc, self._bm, 0, h, self._buf, ct.byref(self._bi), 0)
        if rows != h:
            raise OSError('GetDIBits returned %s rows' % rows)
        return Image.frombytes('RGB', (w, h), self._buf.raw, 'raw', 'BGRX', 0, 1)

    def close(self):
        if self.mode == 'bitblt':
            try:
                if self._bm:
                    self._g.DeleteObject(self._bm)
                self._g.DeleteDC(self._mdc)
                self._u.ReleaseDC(None, self._hdc)
            except Exception:
                pass
            self.mode = None


class ShotGrabber:
    """A screenshot standing in for the screen (tests, --shot)."""

    mode = 'shot'
    why = ''

    def __init__(self, path):
        self.name = os.path.basename(path)
        self.img = Image.open(path).convert('RGB')

    def screen_size(self):
        return self.img.size

    def grab(self, box):
        return self.img.crop(box)

    where = 'a screenshot'

    def close(self):
        pass


def capture(grabber, geo, mod):
    """The crop_box square, in the mod's pixel frame. When the screen (1.3: the game window's client area) is not the
    size the mod laid its HUD out for (w x h in the line), the box is scaled to it and the crop scaled back. A "screen" the size of the box
    itself is a recorded frame (treasure_radar_frames, --shot): taken as is."""
    box = geo.box
    try:
        w, h = float(mod.get('w', 0)), float(mod.get('h', 0))
    except ValueError:
        w = h = 0.0
    size = grabber.screen_size()
    if size and tuple(size) == (geo.n, geo.n) and (w, h) != (geo.n, geo.n):
        return grabber.grab((0, 0, geo.n, geo.n)), ''
    if size and w > 0 and h > 0 and (abs(size[0] / w - 1) > 0.002 or abs(size[1] / h - 1) > 0.002):
        sx, sy = size[0] / w, size[1] / h
        sbox = (int(round(box[0] * sx)), int(round(box[1] * sy)), int(round(box[2] * sx)), int(round(box[3] * sy)))
        return grabber.grab(sbox).resize((geo.n, geo.n), Image.BILINEAR), 'scaled %.3f' % sx
    return grabber.grab(box), ''


# ---------------------------------------------------------------------------------------------------- tracking
class Tracker:
    """The last fix advanced by the mouse counts the mod reported since: the prior for the next frame."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.v = None                 # dict(vx, vy, err, level)
        self.last_grid = None         # (level, cell) of the previous frame, for the level gate
        self.cx = self.cy = 0.0       # raw counts since the fix (estimated where seqs were skipped)
        self.unseen = 0.0             # the part of that estimate we did not see (counts), for the error

    def add_counts(self, m, jump, prev):
        """Fold in one newly read mod line. jump = how many seqs it advanced since the last line we read."""
        try:
            if 'cmx' in m and 'cmy' in m and prev and 'cmx' in prev and 'cmy' in prev:
                # the cumulative counters (since the mod's first write of the game session) in both lines: exact,
                # whatever seqs we missed. poll() makes the new session's first line the baseline (seq went back)
                dx = float(m['cmx']) - float(prev['cmx'])
                dy = float(m['cmy']) - float(prev['cmy'])
                self.cx += dx
                self.cy += dy
                return
            mx, my = float(m.get('mx', 0)), float(m.get('my', 0))
        except ValueError:
            return
        j = max(1, jump)
        # v1 sends per-write deltas and we poll slower than the mod writes: the skipped writes are estimated as
        # copies of the one we see (steady mouse motion)
        self.cx += mx * j
        self.cy += my * j
        self.unseen += (j - 1) * math.hypot(mx, my)

    def prior(self, level, cls, kz, rim):
        if self.v is None or level is None:
            return None               # no level (the mod's is ? and the grid named none): no fix this frame anyway
        if self.v['level'] is not None and self.v['level'] != level:
            self.reset()              # a zoom step recentres the view on the map cursor: the old V says nothing
            return None
        g = detect.GAIN.get(level, 0.246)
        vx = self.v['vx'] + self.cx * g
        vy = self.v['vy'] - self.cy * g
        moved = math.hypot(self.cx, self.cy) * g
        err = self.v['err'] + 0.03 * moved + 0.5 * self.unseen * g
        lim = detect.view_limit(cls, kz, rim)
        if lim is not None:
            cvx, cvy = max(-lim, min(lim, vx)), max(-lim, min(lim, vy))
            if (cvx, cvy) != (vx, vy) and cls == 'big':
                err += 5.0            # the big map's radius is a less certain number than the small one's
            vx, vy = cvx, cvy
        return {'vx': vx, 'vy': vy, 'err': err}

    def gate(self, fix, mod_level):
        """A measured level that differs from the mod's goes out only once two frames in a row agree on it (the mod
        adopts it, and a zoom animation passes through other levels' cells for a frame)."""
        prev = self.last_grid
        self.last_grid = (fix['level'], fix['cell'])
        if fix['level'] == '?' or fix['level'] == mod_level:
            return fix
        if prev and prev[0] == fix['level'] and prev[1] and abs(fix['cell'] / prev[1] - 1) < 0.01:
            return fix
        out = dict(fix, how='none', level='?')
        out['note'] = (fix.get('note', '') + '; level %s (mod %s) seen once: waiting for a second frame'
                       % (fix['level'], mod_level)).lstrip('; ')
        return out

    def update(self, fix, level):
        if fix['how'] == 'none':
            return
        self.v = {'vx': fix['vx'], 'vy': fix['vy'], 'err': fix['err'], 'level': level}
        self.cx = self.cy = self.unseen = 0.0


# ---------------------------------------------------------------------------------------------------- recording
class Recorder:
    """Keeps some captures as PNG in <folder>/treasure_radar_frames, so a wrong fix can be replayed later (--shot on
    the PNG with the mod line frames.txt keeps for it): the first FRAMES_FIRST frames of every map open; at level 0
    and +1 the frames that gave no fix or a level other than the mod's, one a second at most; at -1 the frames
    without a fix, one per 2 s; FRAMES_MAX in all per session. Old PNGs and txt files in the folder go at every
    start, nothing else is touched."""

    def __init__(self, folder):
        self.dir = os.path.join(folder, FRAMES_DIR)
        self.list_path = os.path.join(self.dir, FRAMES_LIST)
        self.n = 0                    # saved this session
        self.open_n = 0               # frames since the map opened
        self.last = {}                # rule -> monotonic time of its last save
        self.full = False             # FRAMES_MAX reached
        self.why = None               # the folder could not be made or emptied: nothing is recorded
        try:
            os.makedirs(self.dir, exist_ok=True)
            for name in os.listdir(self.dir):
                if name.lower().endswith(('.png', '.txt')):
                    os.remove(os.path.join(self.dir, name))
        except OSError as e:
            self.why = str(e)

    def opened(self):
        """The map (re)opened: its first frames are wanted again."""
        self.open_n = 0

    def rule(self, fix, mod_level):
        """Which rule wants this frame kept, or None."""
        self.open_n += 1
        if self.open_n <= FRAMES_FIRST:
            return 'open'
        measured = fix['level']
        if fix['how'] != 'none' and (measured == '?' or str(measured) == mod_level):
            return None
        whole = mod_level == '-1' or (mod_level == '?' and measured == -1)
        rule, gap = ('L-1', 2.0) if whole else ('L0', 1.0)
        now = time.monotonic()
        if now - self.last.get(rule, -1e9) < gap:
            return None
        self.last[rule] = now
        return rule

    def save(self, img, mod, mod_text, fix, line):
        """The capture as PNG plus one line in frames.txt (name, the mod line as read, the fix line; tabs between).
        Returns the file name, or None (not wanted, the cap, or the folder refused)."""
        if self.why is not None or self.rule(fix, mod.get('level', '?')) is None:
            return None
        if self.n >= FRAMES_MAX:
            self.full = True
            return None
        try:
            seq = int(float(mod.get('seq', 0)))
        except ValueError:
            seq = 0
        t = time.time()
        name = '%s.%03d_seq%04d_L%s_%s.png' % (time.strftime('%H%M%S', time.localtime(t)), int(t * 1000) % 1000,
                                               seq, mod.get('level', '?').replace('?', 'x'), fix['how'])
        try:
            img.save(os.path.join(self.dir, name), 'PNG')
            with open(self.list_path, 'a', encoding='utf-8', newline='\n') as f:
                f.write('%s\t%s\t%s\n' % (name, mod_text, line))
        except OSError:
            return None
        self.n += 1
        return name


# ---------------------------------------------------------------------------------------------------- one frame
def idle_reason(m):
    """Why this mod line gets no frame (None: capture one). level=? and kz=0 are no reason: the mod's level tracker
    can lose the level, and the grid period measures it (and so kz). class=? idles only when the grid then shows
    level -1, whose scale depends on the class (frame() checks that)."""
    if m is None:
        return 'no mod line'
    if m.get('open') != '1':
        return 'map closed'
    try:
        rim = float(m.get('rim', 0))
        float(m.get('cx', 0))
        float(m.get('cy', 0))
    except (TypeError, ValueError):
        return 'bad numbers'
    if rim <= 0:
        return 'no map circle (rim 0)'
    return None


def frame(grabber, mod, tracker, ts=None, gate=False):
    """Capture, detect and solve one frame. Returns (fix line, fix dict, analysis, extra log text); the line is None
    when nothing may be written (the grid shows level -1 and the mod's class is ?: fix['note'] says so). gate: name
    a level other than the mod's only once two frames in a row agree on it (the running loop; a single screenshot
    has no second frame)."""
    geo = detect.Geo.from_mod(mod)
    t_cap = time.time() if ts is None else ts
    img, scaled = capture(grabber, geo, mod)
    lo, hi = img.convert('L').getextrema()
    a = detect.analyse(img, geo)
    g = a.grid
    if g.ok and g.level == -1 and geo.cls is None:
        tracker.reset()
        tracker.last_grid = None
        return None, {'how': 'none', 'level': -1, 'cell': g.cell, 'err': 0.0, 'dot': None,
                      'note': 'class unknown at level -1'}, a, ''
    level = g.level if (g.ok and g.level is not None) else geo.level
    cls = g.cls if (g.ok and g.level == -1 and g.cls) else geo.cls
    prior = tracker.prior(level, cls, detect.kz_theory(level, cls, geo.sc) or geo.kz, geo.rim)
    fix = detect.solve(a, mod, prior)
    if gate:
        fix = tracker.gate(fix, geo.level)
    tracker.update(fix, level)
    extra = []
    if hi < 12:
        extra.append('black capture (exclusive fullscreen?)')
    if scaled:
        extra.append(scaled)
    return format_fix(mod.get('seq', '0'), t_cap, fix), fix, a, '; '.join(extra)


def log_text(mod, fix, a, extra):
    g = a.grid
    v = ('V=(%.1f,%.1f) err=%.1f' % (fix['vx'], fix['vy'], fix['err'])) if fix['how'] != 'none' else 'V=-'
    d = fix.get('dot')
    dt = (' dot=(%+.1f,%+.1f)px' % (d.dx, d.dy)) if d is not None else ''
    cands = sum(1 for x in a.dots if x.shape_ok)
    s = ('seq=%s level %s->%s cell=%.1f how=%s %s%s discs=%d %.1fms %s'
         % (mod.get('seq'), mod.get('level'), fix['level'], g.cell if g.ok else 0.0, fix['how'], v, dt, cands, a.ms,
            fix.get('note', '')))
    return s + ('; ' + extra if extra else '')


# ---------------------------------------------------------------------------------------------------- the loop
class Companion:
    def __init__(self, folder, grabber, log=False, out=sys.stdout):
        self.folder = folder
        self.mod_path = os.path.join(folder, MOD_FILE)
        self.fix_path = os.path.join(folder, FIX_FILE)
        self.log_path = os.path.join(folder, LOG_FILE)
        self.grabber = grabber
        self.log = log
        self.out = out
        self.tracker = Tracker()
        self.rec = Recorder(folder)
        self.mod = None               # the last complete mod line
        self.mod_text = ''            # ... as read
        self.seq = None               # its seq (int)
        self.seq_t = None             # monotonic time the seq last changed
        self.state = None
        self.stats = {'dot': 0, 'grid': 0, 'none': 0, 'busy': 0}
        self.stats_t = time.monotonic()
        self.last_fix = None
        self.warned = set()
        self.open = None              # the current map open's totals (from entering 'active' to leaving it)
        self.where = None             # 1.3: where the last capture came from (said when it changes)
        self.prev_img = None          # 1.3: the last capture's bytes, and how many in a row were the same
        self.same_n = 0
        try:
            with open(self.log_path, 'w', encoding='utf-8') as f:    # new at every start
                f.write('')
        except OSError as e:
            self.log_path = None
            self.say('note: no companion log (%s)' % e)

    def say(self, s, console=True):
        """One line to the console (unless console is False) and to the companion's log."""
        s = time.strftime('%H:%M:%S ') + s + '\n'
        if console:
            self.out.write(s)
            self.out.flush()
        if self.log_path:
            try:
                with open(self.log_path, 'a', encoding='utf-8') as f:     # opened per line: nothing held open
                    f.write(s)
            except OSError:
                pass

    def poll(self):
        """Read the mod file. Returns the idle reason, or None when a frame should be processed."""
        m, mtime, text = read_mod(self.mod_path)
        now = time.monotonic()
        if mtime is None:
            self.tracker.reset()
            return 'no mod file in %s' % self.folder
        if m is not None:
            try:
                seq = int(float(m.get('seq', '')))
            except ValueError:
                seq = None
            if seq is not None and seq != self.seq:
                first = self.seq is None
                if not first and seq < self.seq:
                    self.tracker.reset()          # a new game session
                    first = True
                jump = 1 if first else seq - self.seq
                if first:
                    self.seq_t = now - max(0.0, time.time() - mtime)    # an old leftover file counts as stale
                else:
                    self.seq_t = now
                was_open = self.mod is not None and self.mod.get('open') == '1'
                if m.get('open') != '1' or not was_open:
                    self.tracker.reset()          # the map (re)opened: where the game opens it is unknown
                elif not first:
                    self.tracker.add_counts(m, jump, self.mod)
                self.mod, self.seq, self.mod_text = m, seq, text
        if self.mod is None:
            return 'no complete mod line yet'
        if self.seq_t is None or now - self.seq_t > STALE_S:
            self.tracker.reset()
            return 'mod line stale (game closed, paused or alt-tabbed?)'
        why = idle_reason(self.mod)
        if why:
            self.tracker.reset()
        return why

    def cycle(self):
        """One poll, and one frame when the map is open. Returns True when a frame was processed."""
        why = self.poll()
        if why:
            self.set_state('idle: ' + why)
            self.prev_img, self.same_n = None, 0      # the static count runs only while open=1
            return False
        try:
            line, fix, a, extra = frame(self.grabber, self.mod, self.tracker, gate=True)
        except Exception as e:
            self.set_state('frame failed: %s: %s' % (type(e).__name__, e))
            return False
        where = getattr(self.grabber, 'where', None)
        if where and where != self.where:
            self.where = where
            self.say('capture: ' + where)
        self.static(a.img)
        if line is None:
            self.set_state('idle: ' + fix['note'])
            return False
        self.set_state('active: map open, mod level %s, %s map' % (self.mod.get('level'), self.mod.get('class')))
        ok = write_fix(self.fix_path, line)
        self.stats[fix['how']] += 1
        if not ok:
            self.stats['busy'] += 1
        self.last_fix = (line, fix)
        if extra and extra not in self.warned:
            self.warned.add(extra)
            self.say('note: ' + extra)
        o = self.open
        if o is not None:
            o['frames'] += 1
            o[fix['how']] += 1
            o['levels'].add(str(fix['level']))
            o['seq1'] = self.seq
            if fix['how'] != 'none':
                o['last'] = (fix['vx'], fix['vy'], fix['err'], fix['how'], fix['level'])
        if self.rec.save(a.img, self.mod, self.mod_text, fix, line):
            if o is not None:
                o['saved'] += 1
        elif self.rec.full and 'frames full' not in self.warned:
            self.warned.add('frames full')
            self.say('frames: %d recorded this session, the cap; no more until the next start' % FRAMES_MAX)
        if self.log:
            self.out.write(log_text(self.mod, fix, a, extra) + ('' if ok else ' [fix file busy, not written]') + '\n')
            self.out.flush()
        return True

    def static(self, img):
        """1.3: STATIC_N byte-identical captures in a row while open=1 (only those reach here): one note, once."""
        b = img.tobytes()
        if b == self.prev_img:
            self.same_n += 1
        else:
            self.same_n = 1
            self.prev_img = b
        if self.same_n >= STATIC_N and 'static' not in self.warned:
            self.warned.add('static')
            self.say(STATIC_NOTE)

    def set_state(self, s):
        if s != self.state:
            was = bool(self.state and self.state.startswith('active'))
            if was:
                self.report(force=True)
            if was and not s.startswith('active'):
                self.open_summary()
            self.state = s
            self.say(s)
            if s.startswith('active'):
                self.stats = {'dot': 0, 'grid': 0, 'none': 0, 'busy': 0}
                self.stats_t = time.monotonic()
                if self.open is None:
                    self.open = {'seq0': self.seq, 'seq1': self.seq, 't0': time.monotonic(), 'frames': 0, 'dot': 0,
                                 'grid': 0, 'none': 0, 'levels': set(), 'last': None, 'saved': 0}
                    self.rec.opened()

    def open_summary(self):
        """One line per map open, at its close (the log's record of it)."""
        o, self.open = self.open, None
        if o is None:
            return
        levels = ', '.join(sorted(o['levels'], key=lambda x: (x == '?', x))) or '-'
        last = 'none'
        if o['last']:
            vx, vy, err, how, lv = o['last']
            last = 'V=(%.1f, %.1f) err %.1f m (%s, level %s)' % (vx, vy, err, how, lv)
        self.say('map open done: seq %s-%s, %d frames in %.1f s: dot %d, grid %d, none %d; levels seen %s; last %s; '
                 '%d frames recorded' % (o['seq0'], o['seq1'], o['frames'], time.monotonic() - o['t0'], o['dot'],
                                         o['grid'], o['none'], levels, last, o['saved']))

    def close(self):
        """The end of the run: the open's report and summary when the map is still open."""
        if self.state and self.state.startswith('active'):
            self.report(force=True)
            self.open_summary()

    def report(self, force=False):
        now = time.monotonic()
        dt = now - self.stats_t
        n = self.stats['dot'] + self.stats['grid'] + self.stats['none']
        if not force and dt < 5.0:
            return
        if n:
            last = ''
            if self.last_fix:
                f = self.last_fix[1]
                last = ', last: how=%s level=%s' % (f['how'], f['level'])
                if f['how'] != 'none':
                    last += ' V=(%.1f, %.1f) err %.1f m' % (f['vx'], f['vy'], f['err'])
            self.say('%d frames in %.1f s (%.1f/s): dot %d, grid %d, none %d%s%s'
                     % (n, dt, n / dt if dt > 0 else 0, self.stats['dot'], self.stats['grid'], self.stats['none'],
                        ', busy %d' % self.stats['busy'] if self.stats['busy'] else '', last))
        self.stats = {'dot': 0, 'grid': 0, 'none': 0, 'busy': 0}
        self.stats_t = now

    def run(self, once=False):
        nxt = time.monotonic()
        while True:
            active = self.cycle()
            if once:
                return active
            if active:
                if not self.log:
                    self.report()
                nxt += PERIOD
                now = time.monotonic()
                if nxt < now:
                    nxt = now                     # we are slower than 30 Hz: no catching up
                time.sleep(max(0.0, nxt - now))
            else:
                time.sleep(IDLE_SLEEP)
                nxt = time.monotonic()


# ---------------------------------------------------------------------------------------------------- CLI
def parse_prior(s):
    if not s:
        return None
    parts = [float(x) for x in s.replace(' ', '').split(',')]
    return {'vx': parts[0], 'vy': parts[1], 'err': parts[2] if len(parts) > 2 else 5.0}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Treasure Radar companion %s: finds the open map\'s view centre on '
                                             'screen and hands it to the mod.' % VERSION)
    ap.add_argument('--dir', help='folder of the two files, the companion log and the recorded frames (default: '
                                  '%%LOCALAPPDATA%%\\Temp)')
    ap.add_argument('--shot', help='use this screenshot instead of capturing the screen')
    ap.add_argument('--mod', help='with --shot: this mod line instead of the file; prints the fix line')
    ap.add_argument('--prior', help='with --mod: a prior V as "vx,vy[,err]" (world metres)')
    ap.add_argument('--log', action='store_true', help='one log line per frame')
    ap.add_argument('--once', action='store_true', help='one cycle, then exit')
    args = ap.parse_args(argv)

    if args.mod is not None:
        if not args.shot:
            ap.error('--mod needs --shot')
        m = parse_line(args.mod)
        if m is None:
            print('the --mod line has no trailing "end": ignored, as the interface says')
            return 1
        why = idle_reason(m)
        if why:
            print('idle: %s' % why)
            return 0
        grabber = ShotGrabber(args.shot)
        tr = Tracker()
        p = parse_prior(args.prior)
        if p:
            tr.v = dict(p, level=None)                # good for whatever level the frame shows
        line, fix, a, extra = frame(grabber, m, tr)
        if line is None:
            print('idle: %s' % fix['note'])
            return 0
        if args.log:
            print(log_text(m, fix, a, extra))
        print(line)
        return 0

    folder = args.dir or default_dir()
    grabber = ShotGrabber(args.shot) if args.shot else ScreenGrabber()
    comp = Companion(folder, grabber, log=args.log)
    con = not args.once                       # --once: the startup lines go to the log only
    comp.say('Treasure Radar companion %s' % VERSION, con)
    comp.say('folder: %s' % folder, con)
    comp.say('log: %s' % (comp.log_path or 'none'), con)
    if comp.rec.why:
        comp.say('frames: not recorded (%s)' % comp.rec.why, con)
    else:
        comp.say('frames: the first %d of every map open and the frames without a fix, %d at most, in %s'
                 % (FRAMES_FIRST, FRAMES_MAX, comp.rec.dir), con)
    size = grabber.screen_size()
    comp.say('capture: %s%s%s, %s' % (grabber.mode, ' %dx%d' % tuple(size) if size else '',
                                      (' (' + grabber.why + ')') if grabber.why else '',
                                      getattr(grabber, 'where', 'the screen')), con)
    comp.where = getattr(grabber, 'where', None)
    if packaged_python():
        for line in STORE_NOTE:
            comp.say(line, con)
    comp.say('waiting for the mod; Ctrl+C stops', con)
    try:
        comp.run(once=args.once)
    except KeyboardInterrupt:
        comp.say('stopped')
    finally:
        comp.close()
        grabber.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
