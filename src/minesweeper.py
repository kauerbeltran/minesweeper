"""
MINESWEEPER - Atari-style terminal edition
===========================================
Controls:
  [1/2/3]    Choose difficulty at startup
  Mouse      Left-click = dig, right-click = flag (Windows console)
  W/A/S/D    Move the cursor (arrow keys work too)
  [Space]    Dig the selected cell
  [F]        Flag: cycles hidden -> flag -> question mark -> hidden
  [C]        Chord: reveal neighbours when flags match the number
  [P]        Pause (freezes the timer, hides the board)
  [M]        Toggle sound on/off
  [N]        Start a new game with the same difficulty
  [D]        Change difficulty (after a game ends)
  [Q]        Quit

Features:
  * Mouse support via the pure win32 console API - no dependencies
  * Guaranteed safe opening: mines are placed AFTER your first dig and
    never under or beside your first pick, so the opening flood-fills
  * Live timer, mine counter, flags remaining, best time per difficulty
  * Sound effects (built-in winsound), flood-fill reveal, chording
  * Pause, question marks, wrong-flag marking on loss
  * Three difficulties: Beginner 9x9, Intermediate 16x16, Expert 16x30
"""

import atexit
import json
import os
import random
import sys
import threading
import time

# ----------------------------------------------------------------- ANSI ----
def _enable_vt() -> None:
    """Enable ANSI escape processing on Windows 10+ consoles."""
    if os.name == "nt":
        os.system("")

CSI = "\x1b["
RESET = CSI + "0m"
BOLD = CSI + "1m"
DIM = CSI + "2m"
REVERSE = CSI + "7m"
RED = CSI + "91m"
GREEN = CSI + "92m"
YELLOW = CSI + "93m"
CYAN = CSI + "96m"

NUMBER_COLORS = {
    1: CSI + "94m",   # blue
    2: CSI + "92m",   # green
    3: CSI + "91m",   # red
    4: CSI + "95m",   # magenta
    5: CSI + "93m",   # yellow
    6: CSI + "96m",   # cyan
    7: CSI + "97m",   # white
    8: CSI + "90m",   # gray
}

# ----------------------------------------------------------------- data ----
NEIGHBOR = [(-1, -1), (-1, 0), (-1, 1),
            (0, -1),           (0, 1),
            (1, -1),  (1, 0),  (1, 1)]

DIFFICULTIES = {
    "1": ("Beginner",      9,  9, 10),
    "2": ("Intermediate", 16, 16, 40),
    "3": ("Expert",       16, 30, 99),
}

# Console cell of board cell (0, 0). render() must match these.
BOARD_X0 = 4
BOARD_Y0 = 6

# ------------------------------------------------------- best times ----
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
elif sys.argv and sys.argv[0]:
    APP_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    APP_DIR = os.getcwd()
BEST_FILE = os.path.join(APP_DIR, "best_times.json")


def _load_best_times() -> dict:
    try:
        with open(BEST_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


BEST_TIMES = _load_best_times()


def best_time(name: str):
    return BEST_TIMES.get(name)


def save_best_time(name: str, seconds: int) -> bool:
    """Store a new record if it beats the old one. True when improved."""
    old = BEST_TIMES.get(name)
    if old is None or seconds < old:
        BEST_TIMES[name] = seconds
        try:
            with open(BEST_FILE, "w", encoding="utf-8") as f:
                json.dump(BEST_TIMES, f)
        except Exception:
            pass
        return True
    return False


def _fmt_time(seconds: int) -> str:
    mm, ss = divmod(int(seconds), 60)
    return f"{mm:02d}:{ss:02d}"


# ---------------------------------------------------------------- sound ----
class Sound:
    """Tiny beeper built on winsound (Windows only, zero dependencies)."""

    def __init__(self) -> None:
        self.enabled = True

    def _beep(self, freq: int, ms: int) -> None:
        if not self.enabled or os.name != "nt":
            return
        try:
            import winsound
            winsound.Beep(freq, ms)
        except Exception:
            pass

    def dig(self) -> None:
        self._beep(700, 25)

    def flag(self) -> None:
        self._beep(1100, 25)

    def unflag(self) -> None:
        self._beep(850, 25)

    def boom(self) -> None:
        for freq, ms in ((500, 120), (350, 150), (200, 180), (100, 250)):
            self._beep(freq, ms)

    def win(self) -> None:
        for freq, ms in ((523, 90), (659, 90), (784, 90), (1047, 160)):
            self._beep(freq, ms)

    def pause(self) -> None:
        self._beep(600, 40)


SOUND = Sound()


# ----------------------------------------------------------------- input ----
# Windows: keyboard AND mouse are read from the console input buffer via
# ReadConsoleInput (pure ctypes, no dependencies). POSIX: keyboard only.
ENABLE_MOUSE_INPUT = 0x0010
ENABLE_WINDOW_INPUT = 0x0008
ENABLE_QUICK_EDIT_MODE = 0x0040
ENABLE_EXTENDED_FLAGS = 0x0080
ENABLE_LINE_INPUT = 0x0002
ENABLE_ECHO_INPUT = 0x0004
ENABLE_PROCESSED_INPUT = 0x0001

KEY_EVENT_TYPE = 0x0001
MOUSE_EVENT_TYPE = 0x0002
MOUSE_MOVED_FLAG = 0x0004

VK_MAP = {0x23: "end", 0x24: "home", 0x25: "left",
          0x26: "up", 0x27: "right", 0x28: "down"}

if os.name == "nt":
    import ctypes

    class _COORD(ctypes.Structure):
        _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

    class _KEY_EVENT_RECORD(ctypes.Structure):
        _fields_ = [("bKeyDown", ctypes.c_int),
                    ("wRepeatCount", ctypes.c_short),
                    ("wVirtualKeyCode", ctypes.c_short),
                    ("wVirtualScanCode", ctypes.c_short),
                    ("UnicodeChar", ctypes.c_wchar),
                    ("dwControlKeyState", ctypes.c_int)]

    class _MOUSE_EVENT_RECORD(ctypes.Structure):
        _fields_ = [("dwMousePosition", _COORD),
                    ("dwButtonState", ctypes.c_int),
                    ("dwControlKeyState", ctypes.c_int),
                    ("dwEventFlags", ctypes.c_int)]

    class _INPUT_RECORD(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("KeyEvent", _KEY_EVENT_RECORD),
                        ("MouseEvent", _MOUSE_EVENT_RECORD)]
        _anonymous_ = ("_U",)
        _fields_ = [("EventType", ctypes.c_short), ("_U", _U)]


class ConsoleIO:
    """Keyboard + mouse input on Windows; keyboard-only elsewhere."""

    def __init__(self) -> None:
        self.handle = None
        self.old_mode = None
        self.mouse_ok = False
        if os.name == "nt":
            self._init_windows()

    def _init_windows(self) -> None:
        k32 = ctypes.windll.kernel32
        self._k32 = k32
        k32.CreateFileW.restype = ctypes.c_void_p
        k32.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint,
                                    ctypes.c_uint, ctypes.c_void_p,
                                    ctypes.c_uint, ctypes.c_uint,
                                    ctypes.c_void_p]
        k32.GetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        k32.SetConsoleMode.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        k32.ReadConsoleInputW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                          ctypes.c_uint, ctypes.c_void_p]
        k32.WriteConsoleInputW.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                           ctypes.c_uint, ctypes.c_void_p]
        # CONIN$ always refers to the console input buffer, even when
        # stdin is redirected. GENERIC_READ|GENERIC_WRITE, share rw, OPEN_EXISTING.
        h = k32.CreateFileW("CONIN$", 0xC0000000, 3, None, 3, 0, None)
        if not h or h == 0xFFFFFFFF:
            return                      # no console attached
        self.handle = h
        mode = ctypes.c_int(0)
        if k32.GetConsoleMode(h, ctypes.byref(mode)):
            self.old_mode = mode.value
        new_mode = (self.old_mode or 0) | ENABLE_MOUSE_INPUT | ENABLE_WINDOW_INPUT \
                   | ENABLE_EXTENDED_FLAGS
        new_mode &= ~ENABLE_QUICK_EDIT_MODE          # stop Windows eating clicks
        new_mode &= ~(ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT | ENABLE_PROCESSED_INPUT)
        if k32.SetConsoleMode(h, new_mode):
            self.mouse_ok = True
        atexit.register(self.restore)

    def restore(self) -> None:
        if self.handle is not None and self.old_mode is not None:
            try:
                self._k32.SetConsoleMode(self.handle, self.old_mode)
            except Exception:
                pass

    def read(self):
        """Return a key string, or ('click'|'rclick', x, y) for a mouse click."""
        if os.name != "nt" or self.handle is None:
            return self._read_posix()
        return self._read_windows()

    def _read_windows(self):
        rec = _INPUT_RECORD()
        n = ctypes.c_int(0)
        while True:
            ok = self._k32.ReadConsoleInputW(self.handle, ctypes.byref(rec),
                                             1, ctypes.byref(n))
            if not ok or n.value == 0:
                return ""
            if rec.EventType == KEY_EVENT_TYPE:
                if rec.KeyEvent.bKeyDown:
                    vk = rec.KeyEvent.wVirtualKeyCode
                    if vk in VK_MAP:
                        return VK_MAP[vk]
                    ch = rec.KeyEvent.UnicodeChar
                    if ch:
                        return ch
                # ignore key-up events
            elif rec.EventType == MOUSE_EVENT_TYPE:
                if rec.MouseEvent.dwEventFlags & MOUSE_MOVED_FLAG:
                    continue                     # ignore mouse motion
                buttons = rec.MouseEvent.dwButtonState
                x = rec.MouseEvent.dwMousePosition.X
                y = rec.MouseEvent.dwMousePosition.Y
                if buttons & 1:
                    return ("click", x, y)
                if buttons & 2:
                    return ("rclick", x, y)
            # focus / menu / window-size events - ignore

    def _read_posix(self):
        try:
            import termios
            import tty
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                ch = sys.stdin.read(1)
                if ch == "\x1b":
                    ch += sys.stdin.read(2)
                    return {"\x1b[A": "up", "\x1b[B": "down",
                            "\x1b[D": "left", "\x1b[C": "right"}.get(ch, "")
                return ch
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except OSError:
            raise SystemExit(
                "\n  This game needs an interactive console window.\n"
                "  Run Minesweeper.exe directly (double-click it, or start it\n"
                "  from a terminal - not with redirected input).")


CONSOLE = ConsoleIO()


# ----------------------------------------------------------------- game ----
class Tile:
    __slots__ = ("mine", "revealed", "flag", "qmark", "adj")

    def __init__(self) -> None:
        self.mine = False
        self.revealed = False
        self.flag = False
        self.qmark = False
        self.adj = 0


class Game:
    def __init__(self, difficulty_key: str) -> None:
        self.name, self.width, self.height, self.mine_count = DIFFICULTIES[difficulty_key]
        self.board = [[Tile() for _ in range(self.width)] for _ in range(self.height)]
        self.cursor = [0, 0]
        self.first_move = True
        self.state = "playing"          # playing | won | lost
        self.running = True             # timer thread runs while True
        self.new_best = False
        self.start_time = time.time()
        self.final_time = None
        self.flag_count = 0
        self.paused = False
        self._pause_started = None
        self._paused_total = 0.0
        self.lock = threading.Lock()

    # -------------------------------------------------- board helpers ----
    def in_bounds(self, r: int, c: int) -> bool:
        return 0 <= r < self.height and 0 <= c < self.width

    def neighbors(self, r: int, c: int):
        for dr, dc in NEIGHBOR:
            nr, nc = r + dr, c + dc
            if self.in_bounds(nr, nc):
                yield nr, nc

    def elapsed(self) -> int:
        end = self.final_time if self.final_time is not None else time.time()
        if self._pause_started is not None:
            end = self._pause_started   # timer frozen while paused
        return int(end - self.start_time - self._paused_total)

    def flags_left(self) -> int:
        return self.mine_count - self.flag_count

    def toggle_pause(self) -> None:
        if self._pause_started is None:
            self._pause_started = time.time()
            self.paused = True
        else:
            self._paused_total += time.time() - self._pause_started
            self._pause_started = None
            self.paused = False
        SOUND.pause()

    def place_mines(self, safe_r: int, safe_c: int) -> None:
        """Place mines after the first dig, keeping the opening safe."""
        safe = {(safe_r, safe_c)} | set(self.neighbors(safe_r, safe_c))
        spots = [(r, c) for r in range(self.height)
                 for c in range(self.width) if (r, c) not in safe]
        for r, c in random.sample(spots, min(self.mine_count, len(spots))):
            self.board[r][c].mine = True
        self._recompute_adjacency()

    def _recompute_adjacency(self) -> None:
        for r in range(self.height):
            for c in range(self.width):
                t = self.board[r][c]
                if not t.mine:
                    t.adj = sum(1 for nr, nc in self.neighbors(r, c)
                                if self.board[nr][nc].mine)

    # ------------------------------------------------------ game moves ----
    def dig(self, r: int, c: int) -> None:
        t = self.board[r][c]
        if t.revealed or t.flag:
            return
        if self.first_move:
            self.place_mines(r, c)
            self.first_move = False
        if t.mine:
            for row in self.board:
                for tt in row:
                    if tt.mine:
                        tt.revealed = True
            self._finish("lost")
            return
        stack = [(r, c)]
        while stack:
            rr, cc = stack.pop()
            tt = self.board[rr][cc]
            if tt.revealed or tt.flag:
                continue
            tt.revealed = True
            if tt.adj == 0:
                for nr, nc in self.neighbors(rr, cc):
                    if not self.board[nr][nc].revealed:
                        stack.append((nr, nc))
        SOUND.dig()
        self._check_win()

    def chord(self, r: int, c: int) -> None:
        """Reveal the neighbours of a number when its flags match it."""
        t = self.board[r][c]
        if not t.revealed or t.adj == 0:
            return
        flagged = sum(1 for nr, nc in self.neighbors(r, c) if self.board[nr][nc].flag)
        if flagged != t.adj:
            return
        for nr, nc in self.neighbors(r, c):
            if self.state != "playing":
                return
            nt = self.board[nr][nc]
            if not nt.flag and not nt.revealed:
                self.dig(nr, nc)

    def cycle_flag(self, r: int, c: int) -> None:
        """Cycle a cell: hidden -> flag -> question mark -> hidden."""
        t = self.board[r][c]
        if t.revealed:
            return
        if not t.flag and not t.qmark:
            t.flag = True
            self.flag_count += 1
            SOUND.flag()
        elif t.flag:
            t.flag = False
            t.qmark = True
            self.flag_count -= 1
            SOUND.unflag()
        else:
            t.qmark = False
            SOUND.unflag()

    def _check_win(self) -> None:
        if all(t.revealed or t.mine for row in self.board for t in row):
            for row in self.board:
                for t in row:
                    if t.mine:
                        t.flag = True
            self.flag_count = self.mine_count
            self.new_best = save_best_time(self.name, self.elapsed())
            self._finish("won")

    def _finish(self, state: str) -> None:
        self.state = state
        self.final_time = time.time()
        if state == "won":
            SOUND.win()
        elif state == "lost":
            SOUND.boom()

    # ------------------------------------------------------- rendering ----
    def _tile_char(self, t: Tile) -> str:
        if t.revealed:
            if t.mine:
                return RED + "*" + RESET
            if t.adj > 0:
                return NUMBER_COLORS[t.adj] + str(t.adj) + RESET
            return " "
        if self.state == "lost" and t.flag and not t.mine:
            return RED + "\u2717" + RESET      # wrongly flagged
        if t.flag:
            return YELLOW + "\u2691" + RESET
        if t.qmark:
            return CYAN + "?" + RESET
        return DIM + "\u00b7" + RESET

    def render(self) -> None:
        with self.lock:
            os.system("cls" if os.name == "nt" else "clear")
            best = best_time(self.name)
            best_str = _fmt_time(best) if best is not None else "--:--"
            sound_str = "on" if SOUND.enabled else "off"
            print(f"{BOLD}  M I N E S W E E P E R{RESET}  {DIM}[{self.name}]{RESET}")
            print(f"  Mines: {self.mine_count}   Flags: {self.flag_count}   "
                  f"Time: {_fmt_time(self.elapsed())}   "
                  f"Best: {best_str}   Sound: {sound_str}")
            print()
            print("  Mouse: L=dig R=flag   [Space] Dig  [F] Flag  [C] Chord  "
                  "[P] Pause  [M] Sound  [N] New  [Q] Quit")
            print()
            header = "    " + "".join(f"{c % 10} " for c in range(self.width))
            print(header)
            for r, row in enumerate(self.board):
                line = f"  {r:>2} "
                for c, t in enumerate(row):
                    if self.paused:
                        ch = DIM + "\u00b7" + RESET   # board hidden while paused
                    else:
                        ch = self._tile_char(t)
                    if (not self.paused and self.state == "playing"
                            and self.cursor == [r, c]):
                        line += REVERSE + ch + " " + RESET
                    else:
                        line += ch + " "
                print(line)
            if self.paused:
                print(f"\n  {BOLD}{YELLOW}PAUSED{RESET}  - board hidden, timer frozen")
                print("  [P] Resume   [Q] Quit")
            elif self.state == "won":
                extra = f"  {YELLOW}{BOLD}NEW BEST!{RESET}" if self.new_best else ""
                print(f"\n  {BOLD}{GREEN}YOU WIN!{RESET}  "
                      f"Cleared in {_fmt_time(self.elapsed())}{extra}")
                print("  [Space] Play again   [D] Change difficulty   "
                      "any other key quits")
            elif self.state == "lost":
                print(f"\n  {BOLD}{RED}BOOM - GAME OVER{RESET}")
                print("  [Space] Play again   [D] Change difficulty   "
                      "any other key quits")


def timer_loop(game: Game) -> None:
    """Refresh the clock once per second while the game is running."""
    while game.running and game.state == "playing":
        time.sleep(1)
        if game.running and game.state == "playing":
            game.render()


# ------------------------------------------------------------------ flow ----
def choose_difficulty():
    os.system("cls" if os.name == "nt" else "clear")
    print(f"{BOLD}\n  M I N E S W E E P E R{RESET}\n")
    print("  [1] Beginner       9 x 9    10 mines")
    print("  [2] Intermediate  16 x 16   40 mines")
    print("  [3] Expert        16 x 30   99 mines")
    print("\n  [Q] Quit")
    while True:
        inp = CONSOLE.read()
        if isinstance(inp, tuple):
            continue                     # ignore mouse in menus
        k = inp.lower()
        if k in DIFFICULTIES:
            return k
        if k == "q":
            return None


def play_session(difficulty_key: str):
    """Run one game; returns the next action: difficulty key | 'MENU' | None."""
    game = Game(difficulty_key)
    threading.Thread(target=timer_loop, args=(game,), daemon=True).start()
    game.render()

    moves = {
        "w": (-1, 0), "up": (-1, 0),
        "s": (1, 0), "down": (1, 0),
        "a": (0, -1), "left": (0, -1),
        "d": (0, 1), "right": (0, 1),
    }

    while game.state == "playing":
        inp = CONSOLE.read()

        # ---- paused: only resume or quit ----
        if game.paused:
            if isinstance(inp, str):
                k = inp.lower()
                if k == "p":
                    game.toggle_pause()
                    game.render()
                elif k in ("q", "\x03"):
                    game.running = False
                    return None
            continue

        # ---- mouse: left = dig, right = flag ----
        if isinstance(inp, tuple):
            kind, x, y = inp
            c = (x - BOARD_X0) // 2
            r = y - BOARD_Y0
            if 0 <= r < game.height and 0 <= c < game.width:
                if kind == "click":
                    game.dig(r, c)
                else:
                    game.cycle_flag(r, c)
                game.render()
            continue

        # ---- keyboard ----
        k = inp.lower()
        if k in ("q", "\x03"):
            game.running = False
            return None
        if k in moves:
            dr, dc = moves[k]
            game.cursor[0] = max(0, min(game.height - 1, game.cursor[0] + dr))
            game.cursor[1] = max(0, min(game.width - 1, game.cursor[1] + dc))
            game.render()
        elif k == " ":
            game.dig(*game.cursor)
            game.render()
        elif k == "f":
            game.cycle_flag(*game.cursor)
            game.render()
        elif k == "c":
            game.chord(*game.cursor)
            game.render()
        elif k == "p":
            game.toggle_pause()
            game.render()
        elif k == "m":
            SOUND.enabled = not SOUND.enabled
            game.render()
        elif k == "n":
            game.running = False
            return difficulty_key

    # game finished - wait for the next action
    while True:
        inp = CONSOLE.read()
        game.running = False
        if isinstance(inp, tuple):
            continue                     # ignore mouse on the end screen
        k = inp.lower()
        if k == " ":
            return difficulty_key
        if k == "d":
            return "MENU"
        return None


def main() -> None:
    _enable_vt()
    if os.name == "nt":
        # Make sure the board always fits (expert is 64 chars wide)
        os.system("mode con: cols=110 lines=50 >nul 2>&1")
    difficulty = choose_difficulty()
    while difficulty is not None:
        difficulty = play_session(difficulty)
        if difficulty == "MENU":
            difficulty = choose_difficulty()
    print("\n  Thanks for playing!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
    except Exception:
        # Never let the console close silently - always show the error.
        import traceback
        traceback.print_exc()
        try:
            CONSOLE.restore()
            input("\nAn error occurred - press Enter to close...")
        except Exception:
            pass
