"""为宣传视频采集素材（只读，不点击任何东西）：
1) 公招 tag 界面的清晰截图（5 个 tag、都未选中）
2) 游戏自己的鼠标指针（鼠标停在游戏窗口上时，用系统提供的“当前指针”信息绘制出来，和录屏软件显示指针的方式相同）

用法：python promo/capture_assets.py [--minutes 20]
输出：promo/assets/recruit.png, promo/assets/cursor.png, promo/assets/cursor.json（热点坐标）
"""
from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import winutil as w  # noqa: E402

w.set_dpi_aware()
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

ASSETS = os.path.join(HERE, "assets")
u32 = ctypes.WinDLL("user32")
gdi = ctypes.WinDLL("gdi32")
VP = ctypes.c_void_p


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("flags", wt.DWORD), ("hCursor", VP), ("ptScreenPos", wt.POINT)]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL), ("xHotspot", wt.DWORD), ("yHotspot", wt.DWORD), ("hbmMask", VP), ("hbmColor", VP)]


class BMIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


u32.GetCursorInfo.argtypes = [ctypes.POINTER(CURSORINFO)]
u32.GetIconInfo.argtypes = [VP, ctypes.POINTER(ICONINFO)]
u32.DrawIconEx.argtypes = [VP, ctypes.c_int, ctypes.c_int, VP, ctypes.c_int, ctypes.c_int, ctypes.c_uint, VP, ctypes.c_uint]
u32.LoadCursorW.restype, u32.LoadCursorW.argtypes = VP, [VP, VP]
u32.GetDC.restype, u32.GetDC.argtypes = VP, [VP]
u32.ReleaseDC.argtypes = [VP, VP]
u32.WindowFromPoint.restype, u32.WindowFromPoint.argtypes = VP, [wt.POINT]
u32.GetAncestor.restype, u32.GetAncestor.argtypes = VP, [VP, ctypes.c_uint]
gdi.CreateCompatibleDC.restype, gdi.CreateCompatibleDC.argtypes = VP, [VP]
gdi.CreateDIBSection.restype = VP
gdi.CreateDIBSection.argtypes = [VP, VP, ctypes.c_uint, ctypes.POINTER(VP), VP, wt.DWORD]
gdi.SelectObject.restype, gdi.SelectObject.argtypes = VP, [VP, VP]
gdi.DeleteObject.argtypes = [VP]
gdi.DeleteDC.argtypes = [VP]


def _render_cursor(hcur, size, bg):
    """把指针画到纯色背景上，返回 (H, W, 3) 数组"""
    screen = u32.GetDC(None)
    mem = gdi.CreateCompatibleDC(screen)
    bmi = BMIH(ctypes.sizeof(BMIH), size, -size, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = VP()
    bmp = gdi.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
    old = gdi.SelectObject(mem, bmp)
    buf = (ctypes.c_uint8 * (size * size * 4)).from_address(bits.value)
    ctypes.memset(bits, bg, size * size * 4)
    u32.DrawIconEx(mem, 0, 0, hcur, 0, 0, 0, None, 3)  # DI_NORMAL
    arr = np.frombuffer(buf, dtype=np.uint8).reshape(size, size, 4)[:, :, :3][:, :, ::-1].astype(np.float32).copy()
    gdi.SelectObject(mem, old)
    gdi.DeleteObject(bmp)
    gdi.DeleteDC(mem)
    u32.ReleaseDC(None, screen)
    return arr


def grab_cursor():
    """当前鼠标指针 → (RGBA 图片, 热点)。分别画在黑底和白底上，算出真实透明度（彩色/单色指针都适用）"""
    ci = CURSORINFO(ctypes.sizeof(CURSORINFO))
    if not u32.GetCursorInfo(ctypes.byref(ci)) or not ci.hCursor or not (ci.flags & 1):
        return None
    info = ICONINFO()
    if not u32.GetIconInfo(ci.hCursor, ctypes.byref(info)):
        return None
    for b in (info.hbmMask, info.hbmColor):
        if b:
            gdi.DeleteObject(b)
    size = 96
    black, white = _render_cursor(ci.hCursor, size, 0), _render_cursor(ci.hCursor, size, 255)
    alpha = np.clip(255 - (white - black).mean(axis=2), 0, 255)
    color = np.where(alpha[..., None] > 0, black * 255 / np.maximum(alpha[..., None], 1), 0)
    rgba = np.dstack([np.clip(color, 0, 255), alpha]).astype(np.uint8)
    img = Image.fromarray(rgba, "RGBA")
    bbox = img.getbbox()
    if not bbox:
        return None
    return img, (int(info.xHotspot), int(info.yHotspot)), ci


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=20)
    a = ap.parse_args()
    os.makedirs(ASSETS, exist_ok=True)
    import ocr_engine as oe
    import recruit_core as rc
    pools = {k: rc.Pool(k) for k in ("cn", "en")}
    ocr = None
    arrow = u32.LoadCursorW(None, VP(32512))  # 系统默认箭头，用来区分“游戏自己的指针”
    have_shot = os.path.exists(os.path.join(ASSETS, "recruit.png"))
    have_cur = os.path.exists(os.path.join(ASSETS, "cursor.png"))
    end = time.time() + a.minutes * 60
    last = ""
    while time.time() < end and not (have_shot and have_cur):
        h = w.find_game_hwnd()
        r = w.client_rect(h) if h and not w.is_minimized(h) else None
        state = "no game window" if not r else f"game {r[2]}x{r[3]}"
        if r and not have_cur:
            got = grab_cursor()
            if got:
                img, hot, ci = got
                under = u32.GetAncestor(u32.WindowFromPoint(ci.ptScreenPos), 2)
                if under == h and ci.hCursor != arrow:
                    img.save(os.path.join(ASSETS, "cursor.png"))
                    json.dump({"hotspot": hot}, open(os.path.join(ASSETS, "cursor.json"), "w"))
                    print(f"CURSOR captured {img.size} hotspot={hot}", flush=True)
                    have_cur = True
                elif under == h:
                    state += ", pointer over game is the standard Windows arrow"
        if r and not have_shot:
            ocr = ocr or oe.OCR()
            frame, _ = w.grab(r)
            s = ocr.scan(frame, pools)
            state += f", tags {len(s.tags)}"
            if len(s.tags) == 5 and not s.selected:
                time.sleep(1.0)
                frame, _ = w.grab(w.client_rect(h))
                Image.fromarray(frame[:, :, ::-1]).save(os.path.join(ASSETS, "recruit.png"))
                print(f"SCREEN captured {r[2]}x{r[3]}", flush=True)
                have_shot = True
        if state != last:
            print(time.strftime("%H:%M:%S"), state, flush=True)
            last = state
        time.sleep(1.0 if r else 5.0)
    print("DONE" if have_shot and have_cur else f"TIMEOUT screen={have_shot} cursor={have_cur}", flush=True)


if __name__ == "__main__":
    main()
