"""Windows 相关：DPI、游戏窗口、截图、点击、管理员权限、自启动任务、快捷方式。"""
from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes as wt
import os
import subprocess
import sys
import time

u32 = ctypes.windll.user32
k32 = ctypes.windll.kernel32
adv = ctypes.windll.advapi32

GAME_TITLES = ("明日方舟", "Arknights", "アークナイツ", "명일방주")
TASK_PREFIX = "ArkRecruitHelper_"
CREATE_NO_WINDOW = 0x08000000


def set_dpi_aware():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        try:
            u32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


# ------------------------------------------------------------------ game window
GAME_EXES = ("arknights.exe",)   # 官方 PC 端（国服/国际服）进程名


def process_name(hwnd) -> str:
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)  # 有限查询权限：对管理员进程也可用
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(520)
        n = wt.DWORD(520)
        if k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value).lower()
        return ""
    finally:
        k32.CloseHandle(h)


def find_game_hwnd() -> int | None:
    """任意版本的明日方舟窗口：按标题（明日方舟/Arknights/アークナイツ/명일방주）或进程名识别"""
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wt.HWND, wt.LPARAM)
    def cb(h, _):
        if u32.IsWindowVisible(h):
            n = u32.GetWindowTextLengthW(h)
            if 0 < n < 64:
                buf = ctypes.create_unicode_buffer(n + 1)
                u32.GetWindowTextW(h, buf, n + 1)
                if buf.value.strip() in GAME_TITLES:
                    found.append(h)
                    return False
            cls = ctypes.create_unicode_buffer(64)
            u32.GetClassNameW(h, cls, 64)
            if cls.value == "UnityWndClass" and process_name(h) in GAME_EXES:
                found.append(h)
                return False
        return True

    u32.EnumWindows(cb, 0)
    return found[0] if found else None


def window_alive(hwnd) -> bool:
    return bool(hwnd) and bool(u32.IsWindow(hwnd))


def is_minimized(hwnd) -> bool:
    return bool(u32.IsIconic(hwnd))


def foreground() -> int:
    return u32.GetForegroundWindow()


def client_rect(hwnd) -> list[int] | None:
    r = wt.RECT()
    if not u32.GetClientRect(hwnd, ctypes.byref(r)):
        return None
    pt = wt.POINT(0, 0)
    u32.ClientToScreen(hwnd, ctypes.byref(pt))
    if r.right < 200 or r.bottom < 150:
        return None
    return [pt.x, pt.y, r.right, r.bottom]


def process_is_elevated(hwnd) -> bool | None:
    """游戏进程是否以管理员运行。拿不到令牌（拒绝访问）也视为“是”。"""
    pid = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = k32.OpenProcess(0x1000, False, pid.value)
    if not h:
        return True
    tok = wt.HANDLE()
    try:
        if not adv.OpenProcessToken(h, 0x8, ctypes.byref(tok)):
            return True
        el, n = wt.DWORD(), wt.DWORD()
        adv.GetTokenInformation(tok, 20, ctypes.byref(el), 4, ctypes.byref(n))
        k32.CloseHandle(tok)
        return bool(el.value)
    finally:
        k32.CloseHandle(h)


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


FROZEN = getattr(sys, "frozen", False)
APP_NAME = "ArknightsRecruitHelper"
# 安装到 Program Files：只有管理员能修改。以管理员运行的计划任务只执行这里的文件，
# 普通程序无法替换它们来“借道”获得管理员权限。
INSTALL_DIR = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), APP_NAME)
LEGACY_INSTALL_DIR = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", APP_NAME)  # v1.0.0 位置
INSTALLED_EXE = os.path.join(INSTALL_DIR, APP_NAME + ".exe")


def pythonw() -> str:
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return w if os.path.exists(w) else exe


def app_cmd(exe: str | None = None) -> tuple[str, list[str], str]:
    """启动本程序的 (可执行文件, 前置参数, 工作目录)。exe 版直接运行 exe；源码版用 pythonw app.py"""
    if FROZEN:
        e = exe or sys.executable
        return e, [], os.path.dirname(e)
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    return pythonw(), [script], os.path.dirname(script)


def relaunch_as_admin(args: list[str], wait=False) -> bool:
    exe, pre, cwd = app_cmd()
    params = subprocess.list2cmdline(pre + args)
    if not wait:
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, params, cwd, 1)
        return r > 32
    ps = (f"$p=Start-Process -FilePath '{exe}' -ArgumentList '{params.replace(chr(39), chr(39) * 2)}' "
          f"-Verb RunAs -Wait -PassThru; exit $p.ExitCode")
    return run_ps(ps) == 0


def is_installed_copy() -> bool:
    return not FROZEN or os.path.normcase(os.path.abspath(sys.executable)) == os.path.normcase(INSTALLED_EXE)


def ui_lang() -> str:
    """按 Windows 显示语言选择界面语言：中文/日语/韩语，其他用英语"""
    try:
        primary = ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF
        return {0x04: "zh", 0x11: "ja", 0x12: "ko"}.get(primary, "en")
    except Exception:  # noqa: BLE001
        return "zh"


def window_title(hwnd) -> str:
    n = u32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    u32.GetWindowTextW(hwnd, buf, n + 1)
    return buf.value.strip()


def start_menu_dir() -> str:
    return os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")


# ------------------------------------------------------------------ capture
def _mss():
    import mss
    return mss.MSS() if hasattr(mss, "MSS") else mss.mss()


def virtual_screen() -> dict:
    with _mss() as sct:
        return dict(sct.monitors[0])


def grab(area):
    """area=[x,y,w,h] 屏幕坐标；None=全部显示器。返回 (BGR ndarray, (left, top))"""
    import numpy as np
    with _mss() as sct:
        if area:
            box = {"left": area[0], "top": area[1], "width": area[2], "height": area[3]}
        else:
            box = dict(sct.monitors[0])
        img = np.array(sct.grab(box))[:, :, :3].copy()
    return img, (box["left"], box["top"])


# ------------------------------------------------------------------ our windows
GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW = 0x80000, 0x20, 0x80
WS_EX_NOACTIVATE = 0x08000000


def hwnd_of(win) -> int:
    win.update_idletasks()
    return u32.GetParent(win.winfo_id()) or win.winfo_id()


def exclude_from_capture(win) -> bool:
    try:
        return bool(u32.SetWindowDisplayAffinity(hwnd_of(win), 0x11))
    except Exception:  # noqa: BLE001
        return False


def add_exstyle(win, flags):
    h = hwnd_of(win)
    u32.SetWindowLongW(h, GWL_EXSTYLE, u32.GetWindowLongW(h, GWL_EXSTYLE) | flags)


# ------------------------------------------------------------------ input
MAX_CLICKS = 24


class ClickAborted(Exception):
    pass


def click_sequence(hwnd, points: list[tuple[int, int]], delay=0.18, bounds=None):
    """依次点击屏幕坐标，结束后把鼠标放回原处。需要和游戏同等（管理员）权限。

    安全限制：只点击 bounds（游戏窗口客户区）内的点、最多 MAX_CLICKS 次；
    每次点击前确认游戏仍在前台、且用户没有动鼠标，否则立即停止。"""
    if len(points) > MAX_CLICKS:
        raise ClickAborted("too many clicks")
    if bounds:
        bx, by, bw, bh = bounds
        for x, y in points:
            if not (bx <= x < bx + bw and by <= y < by + bh):
                raise ClickAborted("point outside game window")
    old = wt.POINT()
    u32.GetCursorPos(ctypes.byref(old))
    if foreground() != hwnd:
        u32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
    last = None
    for x, y in points:
        if foreground() != hwnd:
            raise ClickAborted("game not in foreground")
        cur = wt.POINT()
        u32.GetCursorPos(ctypes.byref(cur))
        if last and abs(cur.x - last[0]) + abs(cur.y - last[1]) > 6:
            raise ClickAborted("mouse moved by user")
        # 先移到附近再移到目标并停顿，确保游戏先收到鼠标移动再收到按下
        u32.SetCursorPos(int(x) + 2, int(y) + 2)
        time.sleep(0.03)
        u32.SetCursorPos(int(x), int(y))
        u32.mouse_event(0x1, 0, 0, 0, 0)  # 0 位移的 MOVE 事件
        time.sleep(0.08)
        u32.mouse_event(0x2, 0, 0, 0, 0)
        time.sleep(0.05)
        u32.mouse_event(0x4, 0, 0, 0, 0)
        last = (int(x), int(y))
        time.sleep(delay)
    u32.SetCursorPos(old.x, old.y)


# ------------------------------------------------------------------ 安全检查
TRUSTED_PUBLISHERS = ("Hypergryph", "Yostar", "GRYPHLINE", "bilibili")


def verify_signed(path: str) -> tuple[bool, str]:
    """检查 exe 是否有有效的数字签名，且发布者是明日方舟的官方厂商"""
    if not path or not os.path.isfile(path) or not path.lower().endswith(".exe"):
        return False, "not an exe"
    q = path.replace("'", "''")
    ps = (f"$s=Get-AuthenticodeSignature -LiteralPath '{q}';"
          "Write-Output ($s.Status.ToString() + '|' + $s.SignerCertificate.Subject)")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True,
                             timeout=20, creationflags=CREATE_NO_WINDOW).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return False, "check failed"
    status, _, subject = out.partition("|")
    ok = status == "Valid" and any(p.lower() in subject.lower() for p in TRUSTED_PUBLISHERS)
    return ok, subject or status


def safe_app_dirs(paths) -> list[str]:
    """只允许删除本程序自己的文件夹（绝对路径，且文件夹名就是程序名）"""
    out = []
    for pth in paths:
        if not pth or not os.path.isabs(pth):
            continue
        norm = os.path.normpath(pth)
        if os.path.basename(norm) == APP_NAME and len(norm) > len(APP_NAME) + 4:
            out.append(norm)
    return out


# ------------------------------------------------------------------ powershell / tasks / shortcuts
def run_ps(script: str) -> int:
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    return subprocess.call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                           creationflags=CREATE_NO_WINDOW)


def _task_xml(args: str, trigger: str, exe: str | None = None, command: tuple[str, str] | None = None) -> str:
    """trigger: "logon" 登录时 / "watch" 从现在起每 3 分钟 / "" 无（手动运行）"""
    cmd, pre, here = app_cmd(exe)
    if trigger == "logon":
        trig = "<Triggers><LogonTrigger><Enabled>true</Enabled><Delay>PT20S</Delay></LogonTrigger></Triggers>"
    elif trigger == "watch":
        start = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 60))
        trig = (f"<Triggers><TimeTrigger><StartBoundary>{start}</StartBoundary><Enabled>true</Enabled>"
                "<Repetition><Interval>PT3M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>"
                "</TimeTrigger></Triggers>")
    else:
        trig = "<Triggers/>"
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")  # noqa: E731
    command_line, arguments = command if command else (cmd, subprocess.list2cmdline(pre + args.split()))
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>Arknights recruitment helper</Description></RegistrationInfo>
  {trig}
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>HighestAvailable</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <StartWhenAvailable>true</StartWhenAvailable>
    <Priority>6</Priority>
  </Settings>
  <Actions Context="Author"><Exec>
    <Command>{esc(command_line)}</Command>
    <Arguments>{esc(arguments)}</Arguments>
    <WorkingDirectory>{esc(here)}</WorkingDirectory>
  </Exec></Actions>
</Task>"""


def create_task(name: str, args: str, trigger: str = "", exe: str | None = None,
                command: tuple[str, str] | None = None) -> bool:
    import tempfile
    path = os.path.join(tempfile.gettempdir(), f"{TASK_PREFIX}{name}.xml")
    with open(path, "w", encoding="utf-16") as f:
        f.write(_task_xml(args, trigger, exe, command))
    r = subprocess.call(["schtasks", "/create", "/tn", TASK_PREFIX + name, "/xml", path, "/f"],
                        creationflags=CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(path)
    return r == 0


def run_task(name: str) -> bool:
    return subprocess.call(["schtasks", "/run", "/tn", TASK_PREFIX + name], creationflags=CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def delete_task(name: str):
    subprocess.call(["schtasks", "/delete", "/tn", TASK_PREFIX + name, "/f"], creationflags=CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def task_exists(name: str) -> bool:
    return subprocess.call(["schtasks", "/query", "/tn", TASK_PREFIX + name], creationflags=CREATE_NO_WINDOW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def desktop_dir() -> str:
    buf = ctypes.create_unicode_buffer(260)
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf)  # CSIDL_DESKTOPDIRECTORY
    return buf.value


def create_shortcut(lnk: str, target: str, args: str, icon: str, workdir: str):
    q = lambda s: s.replace("'", "''")  # noqa: E731
    run_ps(f"$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{q(lnk)}');"
           f"$s.TargetPath='{q(target)}';$s.Arguments='{q(args)}';$s.IconLocation='{q(icon)}';"
           f"$s.WorkingDirectory='{q(workdir)}';$s.WindowStyle=7;$s.Save()")


def find_launcher() -> tuple[str, str] | None:
    """找鹰角启动器 (路径, 启动参数)"""
    import winreg
    roots = [(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
             (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")]
    for root, path in roots:
        try:
            k = winreg.OpenKey(root, path)
        except OSError:
            continue
        for i in range(winreg.QueryInfoKey(k)[0]):
            try:
                sk = winreg.OpenKey(k, winreg.EnumKey(k, i))
                name = winreg.QueryValueEx(sk, "DisplayName")[0]
                if "鹰角" in name or "Hypergryph" in name:
                    loc = winreg.QueryValueEx(sk, "InstallLocation")[0]
                    exe = os.path.join(loc, "Launcher.exe")
                    if os.path.exists(exe):
                        return exe, "--game=arknights"
            except OSError:
                continue
    return None
