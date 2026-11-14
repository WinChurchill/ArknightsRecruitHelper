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
def find_game_hwnd() -> int | None:
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


def pythonw() -> str:
    exe = sys.executable
    w = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return w if os.path.exists(w) else exe


def relaunch_as_admin(args: list[str], wait=False) -> bool:
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
    params = subprocess.list2cmdline([script] + args)
    if not wait:
        r = ctypes.windll.shell32.ShellExecuteW(None, "runas", pythonw(), params, None, 1)
        return r > 32
    ps = (f"$p=Start-Process -FilePath '{pythonw()}' -ArgumentList '{params.replace(chr(39), chr(39) * 2)}' "
          f"-Verb RunAs -Wait -PassThru; exit $p.ExitCode")
    return run_ps(ps) == 0


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
def click_sequence(hwnd, points: list[tuple[int, int]], delay=0.18):
    """依次点击屏幕坐标，结束后把鼠标放回原处。需要和游戏同等（管理员）权限。"""
    old = wt.POINT()
    u32.GetCursorPos(ctypes.byref(old))
    if foreground() != hwnd:
        u32.SetForegroundWindow(hwnd)
        time.sleep(0.15)
    for x, y in points:
        # 先移到附近再移到目标并停顿，确保游戏先收到鼠标移动再收到按下
        u32.SetCursorPos(int(x) + 2, int(y) + 2)
        time.sleep(0.03)
        u32.SetCursorPos(int(x), int(y))
        u32.mouse_event(0x1, 0, 0, 0, 0)  # 0 位移的 MOVE 事件
        time.sleep(0.08)
        u32.mouse_event(0x2, 0, 0, 0, 0)
        time.sleep(0.05)
        u32.mouse_event(0x4, 0, 0, 0, 0)
        time.sleep(delay)
    u32.SetCursorPos(old.x, old.y)


# ------------------------------------------------------------------ powershell / tasks / shortcuts
def run_ps(script: str) -> int:
    enc = base64.b64encode(script.encode("utf-16-le")).decode()
    return subprocess.call(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", enc],
                           creationflags=CREATE_NO_WINDOW)


def _task_xml(args: str, logon: bool) -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, "app.py")
    trig = "<Triggers><LogonTrigger><Enabled>true</Enabled><Delay>PT20S</Delay></LogonTrigger></Triggers>" if logon \
        else "<Triggers/>"
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")  # noqa: E731
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
    <Priority>6</Priority>
  </Settings>
  <Actions Context="Author"><Exec>
    <Command>{esc(pythonw())}</Command>
    <Arguments>{esc(subprocess.list2cmdline([script] + args.split()))}</Arguments>
    <WorkingDirectory>{esc(here)}</WorkingDirectory>
  </Exec></Actions>
</Task>"""


def create_task(name: str, args: str, logon: bool) -> bool:
    import tempfile
    path = os.path.join(tempfile.gettempdir(), f"{TASK_PREFIX}{name}.xml")
    with open(path, "w", encoding="utf-16") as f:
        f.write(_task_xml(args, logon))
    r = subprocess.call(["schtasks", "/create", "/tn", TASK_PREFIX + name, "/xml", path, "/f"],
                        creationflags=CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(path)
    return r == 0


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
