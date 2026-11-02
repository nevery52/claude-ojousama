"""Claude 大小姐：贴在 Claude 桌面应用窗口上的小挂件。

- 找到 Claude 的主窗口，贴在它上面，跟着它移动、缩放、最小化；Claude 关掉她就离开
- 可以拖动，松手时靠近 Claude 窗口的边就吸上去
- 读 state/sessions/*.json（感知插件写的），按 Claude 的状态换表情
- 呼吸、眨眼、换表情淡入淡出、被点到会 Q 弹
"""
import ctypes
import json
import logging
import math
import os
import random
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QWidget

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / 'art' / 'cut'
STATE = ROOT / 'state'
SESSIONS = STATE / 'sessions'
CONFIG = STATE / 'overlay.json'

EXPRESSIONS = ['idle', 'blink', 'think', 'work', 'ask', 'happy', 'tired', 'sleep', 'poke']
OPTIONAL_EXPRESSIONS = ['gaze', 'gaze_blink', 'pout', 'huff']   # 托腮和它的闭眼图；鼓腮、扭头不理你
BLINK_OF = {'idle': 'blink', 'gaze': 'gaze_blink'}   # 哪个姿势有对得上的闭眼图
LIFT = {'gaze': 0.025, 'gaze_blink': 0.025}          # 这些姿势往上提多少（占尺寸的比例）
SIZES = {'小': 140, '中': 180, '大': 240}
DEFAULT_CONFIG = {'size': 180, 'show_quota': True, 'show_bubble': True,
                  'anchor_h': 'right', 'off_h': 16, 'anchor_v': 'bottom', 'off_v': 120}
PILL_H = 22
BUBBLE_H = 32        # 头顶气泡占的高度
HEAD_TOP = 0.085     # 图片里她的头顶（呆毛尖）离图片上边的比例，各表情在 8%–12% 之间
ART_BOTTOM = 0.95    # 她身体的底边在图片里的位置，下面约 5% 是透明空白
BUBBLE_ERROR_LINGER = 4000   # "出错了"停留多久
BUBBLE_NIGHT_LINGER = 8000   # 深夜报时停留多久
GAZE_AFTER = 90      # 多久没动静，她就放下书托着下巴看你（秒）
AWAY_MINUTES = 10    # 你离开电脑多久（没碰键盘鼠标），回来时她会挥挥手
WAVE_SECONDS = 2.4   # 挥手多久
CALM = {'idle', 'gaze', 'sleep'}   # 闲着的姿势，它们之间慢慢过渡
HISTORY_SHOWN = 6    # 悬停时列出最近几件事
BUBBLE_LINGER = 2500       # 一件事做完后，气泡再停留多久（毫秒）
BUBBLE_DONE_LINGER = 5000  # "做完啦"停留多久
SNAP = 40            # 离 Claude 窗口边多近会被吸过去（逻辑像素）
EDGE_GAP = 4         # 吸上去后离边留一点点缝
HAPPY_SECONDS = 6    # 做完一件事后开心多久
PROUD_SECONDS = 10   # 改了好几个文件后，小得意多久
POKE_WINDOW = 3      # 几秒内连着戳算"连戳"
SULK_POKES = 3       # 连戳几下就生气
SULK_SECONDS = 5     # 生气多久才肯转回来
SPARKLES = [(0.20, 0.20, 0.035), (0.80, 0.30, 0.03), (0.15, 0.45, 0.025), (0.86, 0.14, 0.025)]   # 小得意时星星的位置和大小
SLEEP_MINUTES = 15   # 多久没动静就睡着
TIRED_PERCENT = 80   # 额度用到多少就累了
STALE_MINUTES = 30   # 忙碌状态多久没更新就当作已经结束（比如会话异常退出）
KEEP_DAYS = 3        # 旧的会话状态文件留几天
FRAME_MS = 16        # 约 60 帧
BREATH_SECONDS, BREATH_DEPTH = 4.2, 0.008   # 一次呼吸 4.2 秒，起伏 0.8%
STARTUP_LINK = Path.home() / 'AppData/Roaming/Microsoft/Windows/Start Menu/Programs/Startup/Claude 大小姐.lnk'
PRIORITY = {'asking': 4, 'working': 3, 'thinking': 2, 'done': 1, 'idle': 0}
MOOD_NAMES = {'asking': '等你确认', 'working': '干活中', 'thinking': '思考中', 'done': '完成啦', 'idle': '待机'}
LIMIT_NAMES = {'five_hour': '5 小时额度', 'seven_day': '7 天额度', 'spend_limit': '消费上限'}

SESSIONS.mkdir(parents=True, exist_ok=True)
logging.basicConfig(filename=STATE / 'overlay.log', level=logging.INFO, format='%(asctime)s %(message)s', encoding='utf-8')
log = logging.getLogger('ojousama')

# ---------------------------------------------------------------- Win32

user32 = ctypes.WinDLL('user32', use_last_error=True)
kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
dwmapi = ctypes.WinDLL('dwmapi')

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
WINEVENTPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND, wintypes.LONG,
                                  wintypes.LONG, wintypes.DWORD, wintypes.DWORD)

user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.IsWindow.argtypes = [wintypes.HWND]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsIconic.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
user32.GetWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetLastInputInfo.argtypes = [ctypes.c_void_p]
kernel32.GetTickCount.restype = wintypes.DWORD
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.SetWinEventHook.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.HMODULE, WINEVENTPROC,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.DWORD]
user32.SetWinEventHook.restype = wintypes.HANDLE
user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD)]
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateMutexW.restype = wintypes.HANDLE
dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]

GW_OWNER, GW_HWNDPREV = 4, 3
GWL_EXSTYLE = -20
WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x8, 0x80, 0x08000000
HWND_TOP = 0
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x1, 0x2, 0x4, 0x10
DWMWA_EXTENDED_FRAME_BOUNDS = 9
EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_MINIMIZESTART, EVENT_SYSTEM_MINIMIZEEND = 0x3, 0x16, 0x17
EVENT_OBJECT_LOCATIONCHANGE, OBJID_WINDOW = 0x800B, 0
WINEVENT_OUTOFCONTEXT = 0

_exe_cache = {}


def exe_of(pid):
    if pid not in _exe_cache:
        if len(_exe_cache) > 500:
            _exe_cache.clear()
        path = ''
        handle = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if handle:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
                path = buf.value
            kernel32.CloseHandle(handle)
        _exe_cache[pid] = path
    return _exe_cache[pid]


def pid_of(hwnd):
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def rect_of(hwnd):
    """窗口看得见的边框（不含 Windows 的透明阴影），物理像素 (左, 上, 右, 下)。"""
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def is_claude_window(hwnd):
    return (user32.IsWindow(hwnd) and user32.IsWindowVisible(hwnd)
            and user32.GetWindowTextLengthW(hwnd) > 0 and not user32.GetWindow(hwnd, GW_OWNER)
            and '\\anthropicclaude\\' in exe_of(pid_of(hwnd)).lower())


def find_claude():
    """Claude 桌面应用最大的那个主窗口。"""
    found = []

    def visit(hwnd, _):
        if is_claude_window(hwnd):
            left, top, right, bottom = rect_of(hwnd)
            found.append(((right - left) * (bottom - top), hwnd))
        return True

    user32.EnumWindows(WNDENUMPROC(visit), 0)
    return max(found)[1] if found else None


def cursor_pos():
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [('cbSize', wintypes.UINT), ('dwTime', wintypes.DWORD)]


def idle_ms():
    """你多久没碰键盘鼠标了（毫秒）。"""
    info = LASTINPUTINFO(ctypes.sizeof(LASTINPUTINFO), 0)
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 0
    return (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF


def clean_old_sessions():
    """删掉几天前的会话状态文件，但总留着最新的一个（里面有最后读到的额度）。"""
    files = sorted(SESSIONS.glob('*.json'), key=lambda p: p.stat().st_mtime)
    cutoff = time.time() - KEEP_DAYS * 86400
    for path in files[:-1]:
        if path.stat().st_mtime < cutoff:
            path.unlink(missing_ok=True)


def write_startup_link(enabled):
    """在"启动"文件夹放一个快捷方式：开机后大小姐安静地等着 Claude 打开。"""
    if not enabled:
        STARTUP_LINK.unlink(missing_ok=True)
        return
    pythonw = Path(sys.executable).with_name('pythonw.exe')
    script = (
        '$s = (New-Object -ComObject WScript.Shell).CreateShortcut($env:LINK); '
        '$s.TargetPath = $env:TARGET; $s.Arguments = \'"\' + $env:SCRIPT + \'"\'; '
        '$s.WorkingDirectory = $env:WORKDIR; $s.Description = "Claude 大小姐"; $s.Save()'
    )
    env = {**os.environ, 'LINK': str(STARTUP_LINK), 'TARGET': str(pythonw),
           'SCRIPT': str(Path(__file__).resolve()), 'WORKDIR': str(ROOT)}
    subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script],
                   env=env, check=True, creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)


def has_reset(limit):
    """这个额度窗口的重置时间是不是已经过了。"""
    try:
        return datetime.fromisoformat(limit.get('resetsAt')) <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return False


def describe_reset(iso):
    try:
        left = datetime.fromisoformat(iso) - datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return ''
    minutes = max(int(left.total_seconds() // 60), 0)
    if minutes >= 1440:
        return f'{minutes // 1440} 天后重置'
    if minutes >= 60:
        return f'{minutes // 60} 小时 {minutes % 60} 分后重置'
    return f'{minutes} 分钟后重置'


# ---------------------------------------------------------------- 挂件

class Ojousama(QWidget):
    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.Tool | Qt.NoDropShadowWindowHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.config = {**DEFAULT_CONFIG, **self.load_config()}
        self.sources = {name: QPixmap(str(ART / f'{name}.png')) for name in EXPRESSIONS}
        for name in OPTIONAL_EXPRESSIONS:   # 有这张图才用
            if (ART / f'{name}.png').exists():
                self.sources[name] = QPixmap(str(ART / f'{name}.png'))
        self.pixmaps, self.pixmap_key = {}, None

        self.claude = None
        self.missing_since = time.monotonic()
        self.ever_found = False
        self.hooks = []
        self.move_hook, self.move_pid = None, None

        self.mood, self.mood_since, self.last_activity = 'idle', 0, 0
        self.rate_limits, self.cost = [], None
        self.activity, self.history = None, None
        self.shown_name, self.prev_name, self.fade_start = 'idle', 'idle', 0
        self.poke_until = 0
        self.wave_until, self.away, self.returned_at = 0, False, 0
        self.pokes, self.sulk_start, self.sulk_until, self.sulk_over = [], 0, 0, True
        self.bounce_start = -10
        self.blink_until, self.next_blink = 0, time.monotonic() + 3
        self.drag = None

        self.resize_for_config()
        self.install_hooks()
        if 'autostart' not in self.config:
            self.set_autostart(True)   # 第一次运行：默认开机就陪着

        self.frame_timer = QTimer(self, interval=FRAME_MS, timeout=self.tick)    # 呼吸、淡入淡出、Q 弹
        self.frame_timer.setTimerType(Qt.PreciseTimer)
        self.state_timer = QTimer(self, interval=400, timeout=self.read_state)   # 读 Claude 的状态
        self.watch_timer = QTimer(self, interval=500, timeout=self.watch)        # 找 Claude 窗口
        self.follow_timer = QTimer(self, interval=50, timeout=self.poll_position)  # 跟着 Claude 窗口移动
        for timer in (self.frame_timer, self.state_timer, self.watch_timer, self.follow_timer):
            timer.start()
        self.next_cleanup = 0
        self.read_state()
        self.watch()

    # ---------- 设置

    def load_config(self):
        try:
            return json.loads(CONFIG.read_text('utf-8'))
        except (OSError, ValueError):
            return {}

    def save_config(self):
        STATE.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), 'utf-8')

    def resize_for_config(self):
        size = self.config['size']
        body = math.ceil(ART_BOTTOM * size)   # 图片底下那截透明空白不占地方
        self.setFixedSize(size, self.top_pad() + body + (PILL_H + 4 if self.config['show_quota'] else 0))

    def top_pad(self):
        # 头顶留给气泡的地方：图片顶上本来就有一截空白，只补不够的部分
        if not self.config['show_bubble']:
            return 0
        return max(0, math.ceil(BUBBLE_H - HEAD_TOP * self.config['size']))

    @property
    def hwnd(self):
        return int(self.winId())

    def dpr(self):
        return self.devicePixelRatioF() or 1.0

    # ---------- 跟着 Claude 窗口

    def install_hooks(self):
        # 前台切换、最小化/还原：马上调整叠放顺序
        self.on_event = WINEVENTPROC(self.win_event)
        for first, last in ((EVENT_SYSTEM_FOREGROUND, EVENT_SYSTEM_FOREGROUND),
                            (EVENT_SYSTEM_MINIMIZESTART, EVENT_SYSTEM_MINIMIZEEND)):
            self.hooks.append(user32.SetWinEventHook(first, last, None, self.on_event, 0, 0, WINEVENT_OUTOFCONTEXT))

    def hook_claude_moves(self):
        """只听 Claude 这一个程序的"位置变了"：窗口一动她就跟上，拖窗口时不会一顿一顿。"""
        pid = pid_of(self.claude) if self.claude else None
        if pid == self.move_pid:
            return
        if self.move_hook:
            user32.UnhookWinEvent(self.move_hook)
            self.move_hook = None
        self.move_pid = pid
        if pid:
            self.on_move = WINEVENTPROC(self.claude_moved)
            self.move_hook = user32.SetWinEventHook(EVENT_OBJECT_LOCATIONCHANGE, EVENT_OBJECT_LOCATIONCHANGE, None,
                                                    self.on_move, pid, 0, WINEVENT_OUTOFCONTEXT)

    def claude_moved(self, _hook, _event, hwnd, id_object, _child, _thread, _time):
        # Claude 打字输出时光标、文字区域也会发这个通知，很多，所以第一步就把它们筛掉
        if id_object != OBJID_WINDOW or hwnd != self.claude or self.drag:
            return
        try:
            x, y = self.target_position()
            user32.SetWindowPos(self.hwnd, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)
        except Exception:
            log.exception('move failed')

    def win_event(self, _hook, _event, _hwnd, _id_object, _child, _thread, _time):
        try:
            self.follow()
        except Exception:
            log.exception('follow failed')

    def poll_position(self):
        # 保险：窗口位置通知万一漏了（比如 Claude 刚重开），每秒再查 20 次，变了才动
        if self.claude and not self.drag:
            self.follow()

    def watch(self):
        if not (self.claude and is_claude_window(self.claude)):
            self.claude = find_claude()
            if self.claude:
                self.ever_found = True
                log.info('found Claude window %s', self.claude)
        self.hook_claude_moves()
        if self.claude:
            self.missing_since = time.monotonic()
            self.watch_timer.setInterval(500)
            self.notice_return()
        elif self.config.get('autostart'):
            # 开机就在的大小姐：Claude 没开时藏起来慢慢等，几乎不占资源
            self.watch_timer.setInterval(2000)
        else:
            # 由会话叫醒的大小姐：Claude 关掉了，她也跟着离开。刚启动时多等一会儿
            gone = time.monotonic() - self.missing_since
            if gone > (6 if self.ever_found else 60):
                log.info('Claude is gone, leaving')
                QApplication.quit()
                return
        if time.monotonic() >= self.next_cleanup:
            self.next_cleanup = time.monotonic() + 600
            clean_old_sessions()
        self.follow()

    def notice_return(self):
        """你离开了一阵子又回来时，她挥挥手。"""
        idle = idle_ms()
        if idle >= AWAY_MINUTES * 60 * 1000:
            self.away = True
        elif self.away and idle < 2000:
            self.away = False
            if self.isVisible() and self.mood in ('idle', 'done'):   # 在干活、等你确认时不打断
                self.returned_at = time.time() * 1000   # 你来了，她就醒着，不马上睡回去
                self.wave_until = time.monotonic() + WAVE_SECONDS
                self.bounce_start = time.monotonic()

    def tick(self):
        if self.isVisible():
            self.update()

    def follow(self, z_only=False):
        """贴到 Claude 窗口上，并且正好叠在它上面一层。"""
        if not self.claude or not user32.IsWindow(self.claude):
            self.hide()
            return
        if user32.IsIconic(self.claude):
            self.hide()
            return
        if not self.isVisible():
            self.show()
            self.make_no_activate()
        me = self.hwnd
        above = user32.GetWindow(self.claude, GW_HWNDPREV)
        flags = SWP_NOSIZE | SWP_NOACTIVATE
        if above == me:
            flags |= SWP_NOZORDER
            insert_after = 0
        elif above and user32.GetWindowLongPtrW(above, GWL_EXSTYLE) & WS_EX_TOPMOST:
            insert_after = HWND_TOP
        else:
            insert_after = above or HWND_TOP
        if self.drag:
            flags |= SWP_NOMOVE
            x = y = 0
        else:
            x, y = self.target_position()
            r = wintypes.RECT()
            user32.GetWindowRect(me, ctypes.byref(r))
            if (r.left, r.top) == (x, y):
                flags |= SWP_NOMOVE
        if flags & SWP_NOMOVE and flags & SWP_NOZORDER:
            return   # 位置和叠放都没变，什么也不用做
        user32.SetWindowPos(me, insert_after, x, y, 0, 0, flags)

    def make_no_activate(self):
        style = user32.GetWindowLongPtrW(self.hwnd, GWL_EXSTYLE)
        user32.SetWindowLongPtrW(self.hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)

    def my_size(self):
        d = self.dpr()
        return round(self.width() * d), round(self.height() * d)

    def target_position(self):
        left, top, right, bottom = rect_of(self.claude)
        w, h = self.my_size()
        d = self.dpr()
        c = self.config
        x = left + c['off_h'] * d if c['anchor_h'] == 'left' else right - w - c['off_h'] * d
        y = top + c['off_v'] * d if c['anchor_v'] == 'top' else bottom - h - c['off_v'] * d
        x = min(max(x, left), right - w)
        y = min(max(y, top), bottom - h)
        return self.on_grid(x), self.on_grid(y)

    def on_grid(self, v):
        """对齐到逻辑坐标、物理坐标都是整数的格子上。

        屏幕缩放 150% 时，奇数逻辑坐标对应半个物理像素（247 × 1.5 = 370.5），Qt 每次重画都会
        把她四舍五入挪 1 像素，再被拉回来，看起来就像在发抖。所以只停在 2 个逻辑像素
        （= 3 个物理像素）的倍数上；125%、175% 等缩放也一样找最小的整数步长。
        """
        d = self.dpr()
        step = next((n * d for n in range(1, 9) if abs(n * d - round(n * d)) < 1e-6), d)
        return round(round(v / step) * step)

    # ---------- 拖动与吸附

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            r = wintypes.RECT()
            user32.GetWindowRect(self.hwnd, ctypes.byref(r))
            self.drag = {'cursor': cursor_pos(), 'origin': (r.left, r.top), 'moved': False}

    def mouseMoveEvent(self, event):
        if not self.drag:
            return
        cx, cy = cursor_pos()
        sx, sy = self.drag['cursor']
        if abs(cx - sx) + abs(cy - sy) > 4 * self.dpr():
            self.drag['moved'] = True
        if self.drag['moved']:
            ox, oy = self.drag['origin']
            x, y = self.on_grid(ox + cx - sx), self.on_grid(oy + cy - sy)
            user32.SetWindowPos(self.hwnd, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE)

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.LeftButton or not self.drag:
            return
        moved = self.drag['moved']
        self.drag = None
        if moved:
            self.snap()
        else:
            self.poke()

    def snap(self):
        """松手：记住相对 Claude 窗口的位置；离边够近就吸上去。"""
        if not self.claude:
            return
        r = wintypes.RECT()
        user32.GetWindowRect(self.hwnd, ctypes.byref(r))
        left, top, right, bottom = rect_of(self.claude)
        w, h = self.my_size()
        d = self.dpr()
        x = min(max(r.left, left), right - w)
        y = min(max(r.top, top), bottom - h)
        gaps_h = {'left': x - left, 'right': right - (x + w)}
        gaps_v = {'top': y - top, 'bottom': bottom - (y + h)}
        anchor_h = min(gaps_h, key=gaps_h.get)
        anchor_v = min(gaps_v, key=gaps_v.get)
        off_h, off_v = gaps_h[anchor_h] / d, gaps_v[anchor_v] / d
        snapped = False
        if off_h < SNAP:
            off_h, snapped = EDGE_GAP, True
        if off_v < SNAP:
            off_v, snapped = EDGE_GAP, True
        self.config.update(anchor_h=anchor_h, off_h=round(off_h), anchor_v=anchor_v, off_v=round(off_v))
        self.save_config()
        self.follow()
        if snapped:
            self.bounce_start = time.monotonic()

    def poke(self):
        t = time.monotonic()
        if t < self.sulk_until:
            return   # 正在生气：扭过头去，再戳也不理你
        self.pokes = [p for p in self.pokes if t - p < POKE_WINDOW] + [t]
        self.bounce_start = t
        if len(self.pokes) >= SULK_POKES:
            # 连着戳太多下，有点犟的大小姐生气了：先鼓腮瞪你，再扭头不理你，过一会儿才转回来
            self.pokes, self.poke_until = [], 0
            self.sulk_start, self.sulk_until, self.sulk_over = t, t + SULK_SECONDS, False
        else:
            self.poke_until = t + 1.4

    def sulk_face(self, t):
        """生气时的表情；还没画鼓腮、扭头的图时，先用吃惊的图代替。"""
        if t - self.sulk_start > 0.9 and 'huff' in self.sources:
            return 'huff'
        return 'pout' if 'pout' in self.sources else 'poke'

    # ---------- 右键菜单

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        size_menu = menu.addMenu('大小')
        group = QActionGroup(size_menu)
        for label, size in SIZES.items():
            action = QAction(label, size_menu, checkable=True, checked=self.config['size'] == size)
            action.triggered.connect(lambda _=False, s=size: self.set_config(size=s))
            group.addAction(action)
            size_menu.addAction(action)
        quota = QAction('显示额度', menu, checkable=True, checked=self.config['show_quota'])
        quota.triggered.connect(lambda checked: self.set_config(show_quota=checked))
        menu.addAction(quota)
        bubble = QAction('显示气泡（我在做什么）', menu, checkable=True, checked=self.config['show_bubble'])
        bubble.triggered.connect(lambda checked: self.set_config(show_bubble=checked))
        menu.addAction(bubble)
        home = QAction('回到右下角', menu)
        home.triggered.connect(lambda: self.set_config(**{k: DEFAULT_CONFIG[k] for k in ('anchor_h', 'off_h', 'anchor_v', 'off_v')}))
        menu.addAction(home)
        autostart = QAction('开机就陪着我', menu, checkable=True, checked=bool(self.config.get('autostart')))
        autostart.triggered.connect(self.set_autostart)
        menu.addAction(autostart)
        menu.addSeparator()
        bye = QAction('先休息（下次开新对话时会再出现）', menu)
        bye.triggered.connect(QApplication.quit)
        menu.addAction(bye)
        menu.exec(event.globalPos())

    def set_autostart(self, enabled):
        try:
            write_startup_link(enabled)
        except Exception:
            log.exception('startup link failed')
            enabled = False
        self.config['autostart'] = bool(enabled)
        self.save_config()

    def set_config(self, **changes):
        self.config.update(changes)
        self.save_config()
        self.resize_for_config()
        self.pixmap_key = None
        self.follow()

    # ---------- Claude 的状态

    def read_state(self):
        now = time.time() * 1000
        best, best_key, latest_limits, last_activity = None, None, None, 0
        for path in SESSIONS.glob('*.json'):
            try:
                data = json.loads(path.read_text('utf-8'))
            except (OSError, ValueError):
                continue
            mood, updated = data.get('mood'), data.get('updated', 0)
            # 结束了的会话也留着最后读到的额度，大小姐重启后还能显示
            if data.get('rateLimits') and (latest_limits is None or updated > latest_limits[0]):
                latest_limits = (updated, data['rateLimits'], data.get('cost'))
            last_activity = max(last_activity, data.get('since', 0))
            if mood not in PRIORITY or now - updated > 12 * 3600 * 1000:
                continue
            if mood in ('asking', 'working', 'thinking') and now - updated > STALE_MINUTES * 60 * 1000:
                mood = 'idle'
            key = (PRIORITY[mood], updated)
            if best_key is None or key > best_key:
                best, best_key = {**data, 'mood': mood}, key
        if best:
            self.mood, self.mood_since = best['mood'], best.get('since', 0)
            self.activity, self.history = best.get('activity'), best.get('history')
        else:
            self.mood, self.mood_since, self.activity, self.history = 'idle', 0, None, None
        self.last_activity = last_activity
        if latest_limits:
            self.rate_limits, self.cost = latest_limits[1], latest_limits[2]
        self.setToolTip(self.tooltip())

    def is_proud(self):
        # 这一轮改了好几个文件：做完时有点小得意
        return self.mood == 'done' and isinstance(self.activity, dict) and bool(self.activity.get('proud'))

    def happy_seconds(self):
        return PROUD_SECONDS if self.is_proud() else HAPPY_SECONDS

    def live_limits(self):
        """额度的最新样子。服务器只在 Claude 回复时才发新数字，重置时间一过，
        旧的"100%"就不作数了：先当它已经清零，不用等下一次回复。"""
        return [{**limit, 'percentUsed': 0, 'wasReset': True} if has_reset(limit) else limit
                for limit in self.rate_limits]

    def is_tired(self):
        return any(limit.get('percentUsed', 0) >= TIRED_PERCENT for limit in self.live_limits())

    def expression(self):
        t = time.monotonic()
        if t < self.sulk_until:
            return self.sulk_face(t)
        if not self.sulk_over:
            self.sulk_over = True
            self.bounce_start = t   # 气消了，转回来时轻轻弹一下
        if t < self.poke_until:
            return 'poke'
        if self.mood == 'asking':
            return 'ask'
        if t < self.wave_until:
            return 'ask'            # 举手那张图，这时是在跟你打招呼
        text, _ = self.bubble()
        if text and self.activity.get('error'):
            return 'tired'          # 出错了：冒汗
        if self.mood == 'working':
            return 'work'
        if self.mood == 'thinking':
            return 'think'
        now = time.time() * 1000
        if self.mood == 'done' and now - self.mood_since < self.happy_seconds() * 1000:
            return 'happy'
        quiet = now - self.last_activity if self.last_activity else 0
        if min(quiet, now - self.returned_at) > SLEEP_MINUTES * 60 * 1000:
            return 'sleep'
        if self.is_tired():
            return 'tired'
        # 一阵子没动静：放下书，托着下巴静静看着你（有这张图时）
        if quiet > GAZE_AFTER * 1000 and 'gaze' in self.sources:
            return 'gaze'
        return 'idle'

    def tooltip(self):
        lines = [f'Claude 大小姐 · {MOOD_NAMES.get(self.mood, self.mood)}']
        for limit in self.live_limits():
            name = LIMIT_NAMES.get(limit.get('kind'), limit.get('kind'))
            if limit.get('wasReset'):
                lines.append(f'{name}：已经重置啦（Claude 下次回复后显示新的数字）')
                continue
            reset = describe_reset(limit.get('resetsAt'))
            lines.append(f'{name}：已用 {limit.get("percentUsed", 0):g}%' + (f'，{reset}' if reset else ''))
        if self.cost is not None:
            lines.append(f'最近一次对话花费：${self.cost:.2f}')
        if not self.rate_limits:
            lines.append('额度：还没读到（Claude 回复一次后就有了）')
        recent = [h for h in (self.history or []) if isinstance(h, dict) and h.get('text')][-HISTORY_SHOWN:]
        if recent:
            lines.append('')
            lines.append('刚才：')
            for h in recent:
                at = datetime.fromtimestamp(h.get('at', 0) / 1000).strftime('%H:%M')
                lines.append(f'{at}  {h["text"]}' + ('  ⚠️ 出错了' if h.get('error') else ''))
        return '\n'.join(lines)

    def quota_text(self):
        short = {'five_hour': '5h', 'seven_day': '7d'}
        parts = [f'{short.get(l.get("kind"), l.get("kind"))} {l.get("percentUsed", 0):.0f}%'
                 for l in self.live_limits() if l.get('kind') in short]
        return ' · '.join(parts)

    # ---------- 画

    def pixmap(self, name):
        size, d = self.config['size'], self.dpr()
        if self.pixmap_key != (size, d):
            self.pixmaps, self.pixmap_key = {}, (size, d)
        if name not in self.pixmaps:
            p = self.sources[name].scaled(round(size * d), round(size * d), Qt.KeepAspectRatio, Qt.SmoothTransformation)
            p.setDevicePixelRatio(d)
            self.pixmaps[name] = p
        return self.pixmaps[name]

    def lift(self, name):
        # 个别姿势画得高一点，比如托腮时书放得比较低，往上提一点才不会被额度条挡住
        return round(-LIFT.get(name, 0) * self.config['size'])

    def current_frame(self, t):
        name = self.expression()
        if name != self.shown_name:
            self.prev_name, self.shown_name, self.fade_start = self.shown_name, name, t
        # 眨眼：只有对得上闭眼图的姿势才眨（待机、托腮）
        if BLINK_OF.get(name) in self.sources and t >= self.next_blink:
            self.blink_until = t + 0.12
            self.next_blink = t + (0.3 if random.random() < 0.25 else random.uniform(2.5, 5.5))
        return name

    def paintEvent(self, _event):
        t = time.monotonic()
        name = self.current_frame(t)
        size = self.config['size']
        p = QPainter(self)
        p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # 呼吸 + Q 弹：以脚下中点为基准缩放。呼吸只上下起伏，慢一点、轻一点
        breathe = math.sin(t * 2 * math.pi / BREATH_SECONDS)
        sx, sy = 1, 1 + BREATH_DEPTH * breathe
        k = (t - self.bounce_start) / 0.45
        if 0 <= k < 1:
            wobble = math.exp(-4 * k) * math.sin(k * math.pi * 3)
            sx, sy = sx + 0.07 * wobble, sy - 0.09 * wobble
        bob = 2 * math.sin(t * 2 * math.pi / 4) if name == 'sleep' else 0
        p.translate(0, self.top_pad())
        p.save()
        foot = ART_BOTTOM * size   # 以她身体真正的底边为基准，底边不会跟着呼吸上下飘
        p.translate(size / 2, foot)
        p.scale(sx, sy)
        p.translate(-size / 2, -foot + bob)

        # 换表情时交叉淡化。闲着时换姿势（待机、托腮、睡着）慢一点、柔一点；干活时利落些
        calm = self.prev_name in CALM and name in CALM
        fade = min((t - self.fade_start) / (0.8 if calm else 0.22), 1)
        if calm:
            fade = fade * fade * (3 - 2 * fade)   # 缓入缓出
        if fade < 1:
            p.setOpacity(1 - fade)
            p.drawPixmap(0, self.lift(self.prev_name), self.pixmap(self.prev_name))
            p.setOpacity(fade)
        closed = BLINK_OF.get(name)
        shown = closed if closed in self.sources and t < self.blink_until and fade >= 1 else name
        p.drawPixmap(0, self.lift(shown), self.pixmap(shown))
        p.restore()
        p.setOpacity(1)

        if name == 'sleep':
            self.paint_zzz(p, t, size)
        if name == 'happy' and self.is_proud():
            self.paint_sparkles(p, t, size)
        if self.config['show_quota']:
            self.paint_quota(p, size)
        p.translate(0, -self.top_pad())
        if self.config['show_bubble']:
            self.paint_bubble(p, size)
        p.end()

    def bubble(self):
        """气泡现在该说什么、有多不透明：工具在跑时一直显示，结束后再停留一会儿，慢慢淡出。"""
        a = self.activity
        if not isinstance(a, dict) or not a.get('text'):
            return None, 0
        now = time.time() * 1000
        start, end = a.get('at', 0), a.get('end')
        fade_in = min((now - start) / 200, 1)
        if end is None:
            if self.mood not in ('working', 'asking') or now - start > STALE_MINUTES * 60 * 1000:
                return None, 0
            return a['text'], fade_in
        if a.get('error'):
            linger = BUBBLE_ERROR_LINGER
        elif '凌晨' in a['text']:
            linger = BUBBLE_NIGHT_LINGER
        elif a['text'].startswith('做完啦'):
            linger = BUBBLE_DONE_LINGER
        else:
            linger = BUBBLE_LINGER
        left = linger - (now - end)
        if left <= 0:
            return None, 0
        return a['text'], min(fade_in, left / 600, 1)

    def paint_bubble(self, p, size):
        text, alpha = self.bubble()
        if not text or alpha <= 0:
            return
        p.setOpacity(alpha)
        p.setFont(QFont('Microsoft YaHei', 9))
        metrics = p.fontMetrics()
        text = metrics.elidedText(text, Qt.ElideMiddle, size - 28)
        width = metrics.horizontalAdvance(text) + 20
        tip = self.top_pad() + HEAD_TOP * size + 2      # 小尾巴尖正好碰到呆毛
        rect = QRectF((size - width) / 2, tip - 7 - (BUBBLE_H - 9), width, BUBBLE_H - 9)
        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)
        tail = QPainterPath()   # 小尾巴指向她的头
        cx = size / 2 + 6
        tail.moveTo(cx - 5, rect.bottom() - 1)
        tail.lineTo(cx + 1, rect.bottom() + 7)
        tail.lineTo(cx + 5, rect.bottom() - 1)
        path = path.united(tail)
        asking = self.mood == 'asking' or bool(self.activity.get('error'))   # 等你确认、出错：红色
        p.fillPath(path, QColor(255, 252, 247, 245))
        p.setPen(QPen(QColor(200, 70, 50) if asking else QColor(217, 122, 74), 1.2))
        p.drawPath(path)
        p.setPen(QColor(150, 45, 35) if asking else QColor(107, 74, 51))
        p.drawText(rect, Qt.AlignCenter, text)
        p.setOpacity(1)

    def paint_sparkles(self, p, t, size):
        """小得意：头边几颗和发饰同款的四芒小星星，轮流一闪一闪。"""
        for i, (fx, fy, r) in enumerate(SPARKLES):
            glow = max(0.0, math.sin(t * 2 * math.pi / 1.6 + i * 1.7))
            if glow <= 0.05:
                continue
            cx, cy, s = fx * size, fy * size, r * size * (0.6 + 0.4 * glow)
            star = QPainterPath()
            star.moveTo(cx, cy - s)
            for dx, dy in ((0.22, -0.22), (1, 0), (0.22, 0.22), (0, 1), (-0.22, 0.22), (-1, 0), (-0.22, -0.22), (0, -1)):
                star.lineTo(cx + dx * s, cy + dy * s)
            p.setOpacity(glow)
            p.fillPath(star, QColor(255, 196, 110))
        p.setOpacity(1)

    def paint_zzz(self, p, t, size):
        font = QFont('Microsoft YaHei', max(size // 16, 9), QFont.Bold)
        p.setFont(font)
        for i in range(3):
            phase = (t / 2.4 + i / 3) % 1
            p.setPen(QColor(150, 110, 90, int(220 * (1 - phase))))
            p.drawText(QRectF(size * (0.70 + 0.06 * i), size * (0.22 - 0.16 * phase), 30, 30), 'z')

    def paint_quota(self, p, size):
        text = self.quota_text()
        if not text:
            return
        p.setFont(QFont('Microsoft YaHei', 9))
        width = p.fontMetrics().horizontalAdvance(text) + 18
        rect = QRectF((size - width) / 2, math.ceil(ART_BOTTOM * size) + 2, width, PILL_H)
        path = QPainterPath()
        path.addRoundedRect(rect, PILL_H / 2, PILL_H / 2)
        warn = self.is_tired()
        p.fillPath(path, QColor(255, 247, 238, 235))
        p.setPen(QPen(QColor(200, 70, 50) if warn else QColor(217, 122, 74), 1.2))
        p.drawPath(path)
        p.setPen(QColor(170, 50, 40) if warn else QColor(107, 74, 51))
        p.drawText(rect, Qt.AlignCenter, text)


def main():
    # 只留一个大小姐：每个会话都会叫她，已经在了就不重复出现
    mutex = kernel32.CreateMutexW(None, False, 'Local\\claude-ojousama-overlay')
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        return
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    widget = Ojousama()
    log.info('started')
    try:
        app.exec()
    finally:
        log.info('stopped')
        del widget, mutex


if __name__ == '__main__':
    main()
