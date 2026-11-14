"""逐像素透明的游戏风格叠加层（Windows UpdateLayeredWindow）。

- 卡片和括号都画成带 Alpha 的图片交给系统合成：半透明磨砂外框、柔和阴影、抗锯齿文字，和游戏公招框一致
- 所有尺寸以“tag 行距 p”为单位 → 任意分辨率下比例相同
- 只在内容/位置/悬停变化时重绘 → 空闲时零开销
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import os
import tkinter as tk

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import winutil as w

# ---- 独立的 DLL 句柄，设置 64 位安全的参数类型 ----
_u32 = ctypes.WinDLL("user32")
_gdi = ctypes.WinDLL("gdi32")
VP = ctypes.c_void_p


class _BLEND(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class _BMIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


_u32.GetDC.restype, _u32.GetDC.argtypes = VP, [VP]
_u32.ReleaseDC.argtypes = [VP, VP]
_u32.UpdateLayeredWindow.argtypes = [VP, VP, ctypes.POINTER(wt.POINT), ctypes.POINTER(wt.SIZE), VP,
                                     ctypes.POINTER(wt.POINT), wt.DWORD, ctypes.POINTER(_BLEND), wt.DWORD]
_gdi.CreateCompatibleDC.restype, _gdi.CreateCompatibleDC.argtypes = VP, [VP]
_gdi.CreateDIBSection.restype = VP
_gdi.CreateDIBSection.argtypes = [VP, VP, ctypes.c_uint, ctypes.POINTER(VP), VP, wt.DWORD]
_gdi.SelectObject.restype, _gdi.SelectObject.argtypes = VP, [VP, VP]
_gdi.DeleteObject.argtypes = [VP]
_gdi.DeleteDC.argtypes = [VP]


def _premultiplied_bgra(img: Image.Image) -> bytes:
    a = np.asarray(img.convert("RGBA"), dtype=np.uint16)
    al = a[..., 3:4]
    rgb = (a[..., :3] * al + 127) // 255
    return np.dstack([rgb[..., 2], rgb[..., 1], rgb[..., 0], al[..., 0]]).astype(np.uint8).tobytes()


class LayeredWindow:
    """一个用 RGBA 图片显示的置顶窗口（截图不可见）。click_through=True 时鼠标穿透。"""

    def __init__(self, root, click_through=False):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.withdraw()
        self.win.update_idletasks()
        flags = w.WS_EX_LAYERED | w.WS_EX_TOOLWINDOW | w.WS_EX_NOACTIVATE
        if click_through:
            flags |= w.WS_EX_TRANSPARENT
        w.add_exstyle(self.win, flags)
        self.hwnd = w.hwnd_of(self.win)
        self.capture_safe = w.exclude_from_capture(self.win)
        self.visible = False
        self.geom = None

    def show_image(self, img: Image.Image, x: int, y: int):
        W, H = img.size
        x, y = int(x), int(y)
        if (x, y, W, H) != self.geom:
            self.win.geometry(f"{W}x{H}+{x}+{y}")
            self.geom = (x, y, W, H)
        if not self.visible:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
            self.visible = True
        data = _premultiplied_bgra(img)
        screen = _u32.GetDC(None)
        mem = _gdi.CreateCompatibleDC(screen)
        bmi = _BMIH(ctypes.sizeof(_BMIH), W, -H, 1, 32, 0, 0, 0, 0, 0, 0)
        bits = VP()
        bmp = _gdi.CreateDIBSection(mem, ctypes.byref(bmi), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, data, len(data))
        old = _gdi.SelectObject(mem, bmp)
        try:
            _u32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(wt.POINT(x, y)), ctypes.byref(wt.SIZE(W, H)),
                                     mem, ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(_BLEND(0, 0, 255, 1)), 2)
        finally:
            _gdi.SelectObject(mem, old)
            _gdi.DeleteObject(bmp)
            _gdi.DeleteDC(mem)
            _u32.ReleaseDC(None, screen)

    def hide(self):
        if self.visible:
            self.win.withdraw()
            self.visible = False


# ------------------------------------------------------------------ 字体
_FONT_DIR = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
_font_cache: dict = {}


class FontSpec(tuple):
    """字号/粗细/是否拉丁字体。实际字体按要画的文字决定（韩文 → Malgun Gothic，假名 → Yu Gothic，其他 → 雅黑）"""
    __slots__ = ()

    def __new__(cls, size, bold=False, latin=False):
        return super().__new__(cls, (max(9, int(round(size))), bold, latin))


def font(size: float, bold=False, latin=False) -> FontSpec:
    return FontSpec(size, bold, latin)


HANGUL = "[" + chr(0xAC00) + "-" + chr(0xD7AF) + chr(0x1100) + "-" + chr(0x11FF) + chr(0x3130) + "-" + chr(0x318F) + "]"
KANA = "[" + chr(0x3040) + "-" + chr(0x30FF) + "]"


def _real_font(spec: FontSpec, text: str) -> ImageFont.FreeTypeFont:
    import re
    size, bold, latin = spec
    script = "ko" if re.search(HANGUL, text or "") else "ja" if re.search(KANA, text or "") else "zh"
    key = (size, bold, latin, script)
    if key not in _font_cache:
        by_script = {
            "ko": ["malgunbd.ttf", "malgun.ttf"] if bold else ["malgun.ttf"],
            "ja": ["YuGothB.ttc", "meiryob.ttc", "YuGothM.ttc"] if bold else ["YuGothM.ttc", "meiryo.ttc"],
            "zh": ["msyhbd.ttc", "msyh.ttc"] if bold else ["msyh.ttc"],
        }[script]
        names = (["bahnschrift.ttf"] if latin and script == "zh" else []) + by_script             + ["segoeuib.ttf" if bold else "segoeui.ttf", "arial.ttf"]
        for n in names:
            try:
                _font_cache[key] = ImageFont.truetype(os.path.join(_FONT_DIR, n), size)
                break
            except OSError:
                continue
        else:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def draw_text(d: ImageDraw.ImageDraw, xy, text, font=None, **kw):
    d.text(xy, text, font=_real_font(font, text), **kw)


def text_w(d: ImageDraw.ImageDraw, s: str, f) -> float:
    return d.textlength(s, font=_real_font(f, s))


# ------------------------------------------------------------------ 配色（取自游戏公招框）
FRAME = (214, 213, 209, 150)      # 半透明磨砂外框（盖在游戏已模糊的背景上）
FRAME_EDGE = (255, 255, 255, 70)
CARD = (243, 243, 242, 255)
LABEL = (94, 94, 96, 255)
SUB = (128, 128, 131, 255)
BTN = (49, 49, 49, 255)
BTN_HOVER = (0, 153, 220, 255)
WARN = (199, 119, 0, 255)
OP_COLOR = {6: (226, 98, 0, 255), 5: (184, 138, 0, 255)}   # 浅色卡片上可读的高星颜色
BADGE = {6: ((255, 122, 26), (255, 255, 255)), 5: ((255, 201, 60), (58, 42, 0)),
         4: ((167, 123, 255), (255, 255, 255)), 3: ((51, 169, 230), (255, 255, 255)),
         1: ((154, 154, 154), (255, 255, 255))}


def star(d: ImageDraw.ImageDraw, cx, cy, r, fill):
    """五角星（字体里不一定有 ★，所以自己画）"""
    import math
    pts = []
    for i in range(10):
        rr = r if i % 2 == 0 else r * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    d.polygon(pts, fill=fill)


def rarity_badge(d, x, y, w, h, n, p, fg):
    """徽章里的“4★”：数字 + 画出来的星"""
    fnum = font(0.27 * p, True, latin=True)
    tw = d.textlength(str(n), font=_real_font(fnum, str(n)))
    r = 0.1 * p
    total = tw + 0.04 * p + 2 * r
    sx = x + (w - total) / 2
    draw_text(d, (sx, y + h / 2), str(n), font=fnum, fill=fg, anchor="lm")
    star(d, sx + tw + 0.04 * p + r, y + h / 2 - 0.01 * p, r, fg)


def _shadowed_card(img: Image.Image, box, p):
    """在 img 上画带柔和投影的内卡片"""
    x0, y0, x1, y1 = [int(v) for v in box]
    pad = int(0.12 * p) + 2
    sh = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rectangle([pad, pad + int(0.03 * p), pad + x1 - x0, pad + y1 - y0 + int(0.03 * p)],
                                 fill=(0, 0, 0, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(max(1, 0.05 * p)))
    img.alpha_composite(sh, (x0 - pad, y0 - pad))
    ImageDraw.Draw(img).rectangle([x0, y0, x1, y1], fill=CARD)


def _wrap(d, words, sep, f, maxw):
    """把 tag 列表按宽度折行：['远程位 +', '费用回复']"""
    # 单个词比一行还宽（如「고급 특별 채용」）：先按空格拆，再不行按字拆
    units = []
    for i, wd in enumerate(words):
        last = i == len(words) - 1
        if text_w(d, wd + ("" if last else sep), f) <= maxw:
            units.append(wd + ("" if last else sep))
            continue
        parts = wd.split(" ") if " " in wd.strip() else list(wd)
        joiner = " " if " " in wd.strip() else ""
        for j, part in enumerate(parts):
            tail = (joiner if j < len(parts) - 1 else ("" if last else sep))
            units.append(part + tail)
    lines, cur = [], ""
    for piece in units:
        if cur and text_w(d, cur + piece.rstrip(), f) > maxw:
            lines.append(cur.rstrip())
            cur = piece.lstrip()
        else:
            cur += piece
    if cur:
        lines.append(cur.rstrip())
    return lines


# ------------------------------------------------------------------ 卡片
class GameCard:
    """公招对话框旁的「招募建议」卡片。orient='h' 贴在下方（横排），'v' 贴在侧边（竖排）。"""

    def __init__(self, root, texts, on_pick, on_hover, on_close, on_admin):
        self.tx = texts
        self.on_pick, self.on_hover, self.on_close, self.on_admin = on_pick, on_hover, on_close, on_admin
        self.lw = LayeredWindow(root)
        self.win = self.lw.win
        self.capture_safe = self.lw.capture_safe
        self.args = None
        self.pos = (0, 0)
        self.hits = []
        self.hover = None
        self.img = None
        self.visible = False
        self.offset = 0          # 当前页第一个组合的序号
        self.pages = []          # 之前各页的起点（用于“上一页”）
        self.more = 0            # 本页之后还剩几个组合
        self.shown = 0
        self.combo_key = None
        self.win.bind("<MouseWheel>", self._wheel)
        self.win.bind("<Motion>", self._motion)
        self.win.bind("<Leave>", lambda e: self._set_hover(None))
        self.win.bind("<Button-1>", self._click)

    def set_texts(self, texts):
        self.tx = texts

    # ---- API（与旧版一致）----
    def render(self, model, p, W, H, admin_ok, busy_text=None, orient="h"):
        self.args = (model, p, int(W), int(H), admin_ok, busy_text, orient)
        self.hover = None
        key = tuple(c["tids"] for c in (model or {}).get("combos", []))
        if key != self.combo_key:  # 新的一组 tag：回到第一页
            self.combo_key, self.offset, self.pages = key, 0, []
        self._paint()

    def place(self, x, y, W=None, H=None):
        pos = (int(x), int(y))
        if pos != self.pos:
            self.pos = pos
            if self.visible and self.img is not None:
                self.lw.show_image(self.img, *self.pos)

    def show(self, v=True):
        if v and self.img is not None:
            if not self.visible:
                self.lw.show_image(self.img, *self.pos)
            self.visible = True
        elif not v:
            self.lw.hide()
            self.visible = False

    # ---- 交互 ----
    def _hit(self, x, y):
        for (x0, y0, x1, y1), kind, payload in self.hits:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return kind, payload
        return None, None

    def _motion(self, e):
        kind, payload = self._hit(e.x, e.y)
        self.win.configure(cursor="hand2" if kind else "")
        self._set_hover(payload if kind == "combo" else None)

    def _set_hover(self, combo):
        if combo is self.hover:
            return
        self.hover = combo
        self._paint()
        if self.visible:
            self.lw.show_image(self.img, *self.pos)
        self.on_hover(combo)

    def _click(self, e):
        kind, payload = self._hit(e.x, e.y)
        if kind == "combo":
            self.on_pick(payload)
        elif kind == "close":
            self.on_close()
        elif kind == "admin":
            self.on_admin()
        elif kind == "next":
            self._page(+1)
        elif kind == "prev":
            self._page(-1)

    def _wheel(self, e):
        self._page(+1 if e.delta < 0 else -1)

    def _page(self, step):
        if step > 0 and self.more > 0:
            self.pages.append(self.offset)
            self.offset = self.offset + self.shown
        elif step < 0 and self.pages:
            self.offset = self.pages.pop()
        else:
            return
        self.hover = None
        self._paint()
        if self.visible:
            self.lw.show_image(self.img, *self.pos)

    # ---- 绘制 ----
    def _paint(self):
        model, p, W, H, admin_ok, busy, orient = self.args
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, W - 1, H - 1], fill=FRAME)
        d.line([0, 0, W - 1, 0], fill=FRAME_EDGE, width=max(1, int(p / 40)))
        self.hits = []
        # 关闭 ✕
        fx = font(0.24 * p)
        cx, cy = W - 0.22 * p, 0.2 * p
        draw_text(d, (cx, cy), "×", font=fx, fill=(90, 90, 92, 255), anchor="mm")
        self.hits.append(((cx - 0.2 * p, 0, W, 0.4 * p), "close", None))
        if orient == "v":
            self._paint_v(img, d, model, p, W, H, admin_ok, busy)
        else:
            self._paint_h(img, d, model, p, W, H, admin_ok, busy)
        self.img = img

    def _header_texts(self, model, busy):
        star = model["star"] if model else 0
        col = BADGE.get(star, ((128, 128, 131),))[0] if (star >= 4 or star == 1) else SUB[:3]
        sub = busy or (model["title"] if model else "")
        return sub, ((0, 153, 220) if busy else col)

    def _button(self, img, d, c, x, y, bw, lines, p, f, line_h):
        bh = max(0.62 * p, len(lines) * line_h + 0.24 * p)
        hov = c is self.hover
        d.rectangle([x, y, x + bw, y + bh], fill=BTN_HOVER if hov else BTN)
        col, fg = BADGE[c["min"]]
        bdw = 0.56 * p
        d.rectangle([x, y, x + bdw, y + bh], fill=col + (255,))
        rarity_badge(d, x, y, bdw, bh, c["min"], p, fg + (255,))
        ty = y + bh / 2 - (len(lines) - 1) * line_h / 2
        for i, ln in enumerate(lines):
            draw_text(d, (x + bdw + 0.18 * p, ty + i * line_h), ln, font=f, fill=(255, 255, 255, 255), anchor="lm")
        self.hits.append(((x, y, x + bw, y + bh), "combo", c))
        return bh

    def _ops_line(self, d, c, x, y, maxw, p, max_lines=1):
        """干员名流式排版：5★/6★ 上色，放不下时以「等 N 名」结尾"""
        f = font(0.21 * p)
        lh = 0.3 * p
        sep = " · "
        ops = c["ops"]
        more_w = text_w(d, self.tx["ops_more"].format(n=99), f) + 0.1 * p
        cx, line = x, 0
        for i, (name, r) in enumerate(ops):
            piece = (sep if cx > x else "") + name
            pw = text_w(d, piece, f)
            last_line = line == max_lines - 1
            reserve = more_w if (last_line and i < len(ops) - 1) else 0
            if cx + pw + reserve > x + maxw and cx > x:
                if last_line:
                    draw_text(d, (cx + 0.08 * p, y + line * lh), self.tx["ops_more"].format(n=len(ops) - i),
                           font=f, fill=SUB, anchor="la")
                    break
                line, cx = line + 1, x
                piece, pw = name, text_w(d, name, f)
            color = OP_COLOR.get(r, SUB)
            draw_text(d, (cx, y + line * lh), piece, font=f, fill=color, anchor="la")
            cx += pw
        return (line + 1) * lh

    def _pager(self, d, x, y, p, more, anchor_left=True):
        """「▲」「▼ 还有 N 个」翻页按钮（三角形自己画，避免字体缺字）"""
        f = font(0.22 * p, True)
        h = 0.36 * p
        cx = x
        if self.pages:
            t = 0.1 * p
            d.polygon([(cx + 0.1 * p, y + h / 2 + t / 2), (cx + 0.1 * p + 2 * t, y + h / 2 + t / 2),
                       (cx + 0.1 * p + t, y + h / 2 - t)], fill=SUB)
            self.hits.append(((cx, y, cx + 0.45 * p, y + h), "prev", None))
            cx += 0.55 * p
        if more:
            t = 0.1 * p
            d.polygon([(cx + 0.1 * p, y + h / 2 - t / 2), (cx + 0.1 * p + 2 * t, y + h / 2 - t / 2),
                       (cx + 0.1 * p + t, y + h / 2 + t)], fill=BTN_HOVER)
            label = self.tx["more_combos"].format(n=more)
            draw_text(d, (cx + 0.4 * p, y + h / 2), label, font=f, fill=BTN_HOVER, anchor="lm")
            self.hits.append(((cx, y, cx + 0.5 * p + text_w(d, label, f), y + h), "next", None))

    def _paint_h(self, img, d, model, p, W, H, admin_ok, busy):
        x0, y0, x1, y1 = 0.55 * p, 0.16 * p, W - 0.55 * p, H - 0.16 * p
        _shadowed_card(img, (x0, y0, x1, y1), p)
        cy = (y0 + y1) / 2
        lx = x0 + 0.5 * p
        draw_text(d, (lx, cy - 0.2 * p), self.tx["card_label"], font=font(0.31 * p, True), fill=LABEL, anchor="lm")
        sub, col = self._header_texts(model, busy)
        draw_text(d, (lx, cy + 0.24 * p), sub, font=font(0.24 * p, True), fill=col + (255,), anchor="lm")
        if not admin_ok and not busy:  # 右侧预留位置给提示，避免和按钮重叠
            fa = font(0.2 * p)
            lines = _wrap(d, list(self.tx["need_admin_short"].lstrip("⚠ ")), "", fa, 2.6 * p)
            tw = max(text_w(d, ln, fa) for ln in lines)
            ty = cy - (len(lines) - 1) * 0.14 * p
            for i, ln in enumerate(lines):
                draw_text(d, (x1 - 0.2 * p, ty + i * 0.28 * p), ln, font=fa, fill=WARN, anchor="rm")
            self.hits.append(((x1 - 0.2 * p - tw, y0, x1, y1), "admin", None))
            x1 = x1 - tw - 0.45 * p
        combos = (model or {}).get("combos", [])
        bx = x0 + 3.0 * p
        if not combos:
            draw_text(d, (bx, cy), (model or {}).get("subtitle", ""), font=font(0.27 * p), fill=LABEL, anchor="lm")
            return
        f = font(0.28 * p, True)
        show_ops = H > 1.55 * p
        by = (cy - 0.62 * p / 2 - (0.12 * p if show_ops else 0))
        page = combos[self.offset:]
        pager_w = 2.0 * p
        self.shown = 0
        for i, c in enumerate(page):
            label = " + ".join(c["tags"]) + ("  ·  3:50" if c["min"] == 1 else "")
            bw = 0.56 * p + 0.18 * p + text_w(d, label, f) + 0.3 * p
            if bx + bw + (pager_w if i < len(page) - 1 else 0) > x1 - 0.2 * p and i:
                break
            self._button(img, d, c, bx, by, bw, [label], p, f, 0.36 * p)
            if show_ops:
                self._ops_line(d, c, bx + 2, by + 0.68 * p, bw, p)
            bx += bw + 0.2 * p
            self.shown += 1
        self.more = len(page) - self.shown
        if self.more or self.pages:
            self._pager(d, bx, cy - 0.18 * p, p, self.more)

    def _paint_v(self, img, d, model, p, W, H, admin_ok, busy):
        x0, y0, x1, y1 = 0.16 * p, 0.42 * p, W - 0.16 * p, H - 0.16 * p
        _shadowed_card(img, (x0, y0, x1, y1), p)
        lx = x0 + 0.28 * p
        draw_text(d, (lx, y0 + 0.42 * p), self.tx["card_label"], font=font(0.31 * p, True), fill=LABEL, anchor="lm")
        sub, col = self._header_texts(model, busy)
        y = y0 + 0.82 * p
        fs = font(0.24 * p, True)
        for ln in _wrap(d, list(sub), "", fs, x1 - lx - 0.2 * p) or [""]:
            draw_text(d, (lx, y), ln, font=fs, fill=col + (255,), anchor="lm")
            y += 0.32 * p
        y += 0.12 * p
        d.line([lx, y, x1 - 0.28 * p, y], fill=(210, 210, 208, 255), width=max(1, int(p / 40)))
        y += 0.22 * p
        bottom = y1 - 0.2 * p
        if not admin_ok and not busy:
            fa = font(0.19 * p)
            lines = _wrap(d, list(self.tx["need_admin_short"].lstrip("⚠ ")), "", fa, x1 - lx - 0.2 * p)
            ay = y1 - 0.15 * p - len(lines) * 0.27 * p
            for i, ln in enumerate(lines):
                draw_text(d, (lx, ay + i * 0.27 * p), ln, font=fa, fill=WARN, anchor="la")
            self.hits.append(((x0, ay, x1, y1), "admin", None))
            bottom = ay - 0.15 * p
        combos = (model or {}).get("combos", [])
        if not combos:
            fsub = font(0.25 * p)
            for ln in _wrap(d, list((model or {}).get("subtitle", "")), "", fsub, x1 - lx - 0.2 * p):
                draw_text(d, (lx, y), ln, font=fsub, fill=LABEL, anchor="la")
                y += 0.34 * p
            return
        bw = x1 - lx - 0.28 * p
        f = font(0.27 * p, True)
        line_h = 0.34 * p
        page = combos[self.offset:]
        pager_h = 0.5 * p
        self.shown = 0
        for i, c in enumerate(page):
            tags = list(c["tags"]) + (["3:50"] if c["min"] == 1 else [])
            avail = bw - 0.56 * p - 0.3 * p
            fb = f  # 最长的 tag 放不下时先把字缩小一点（最多到 82%），实在不行才拆词
            widest = max(tags, key=lambda t: text_w(d, t + " +", f))
            for k in (0.94, 0.88, 0.82):
                if text_w(d, widest + " +", fb) <= avail:
                    break
                fb = font(0.27 * p * k, True)
            lines = _wrap(d, tags, " + ", fb, avail)
            need = max(0.62 * p, len(lines) * line_h + 0.24 * p) + 0.66 * p
            reserve = pager_h if i < len(page) - 1 or self.pages else 0
            if y + need + reserve > bottom and i:
                break
            bh = self._button(img, d, c, lx, y, bw, lines, p, fb, line_h)
            y += bh + 0.06 * p
            y += self._ops_line(d, c, lx + 2, y, bw, p, max_lines=2) + 0.16 * p
            self.shown += 1
        self.more = len(page) - self.shown
        if self.more or self.pages:
            self._pager(d, lx, bottom - 0.4 * p, p, self.more)


# ------------------------------------------------------------------ 括号标记
class BracketLayer:
    """给推荐 tag 画游戏风格的角括号。窗口只覆盖 tag 区域，鼠标穿透；内容不变时不重绘。"""

    def __init__(self, root):
        self.lw = LayeredWindow(root, click_through=True)
        self.win = self.lw.win
        self.capture_safe = self.lw.capture_safe
        self.vs = w.virtual_screen()
        self.key = None

    def clear(self):
        self.key = None
        self.lw.hide()

    def show(self, v=True):
        if not v:
            self.clear()

    def brackets(self, centers, pitch, color, selected=()):
        if not centers:
            self.clear()
            return
        p = pitch
        key = (tuple((t, round(x), round(y)) for t, x, y in centers), round(p, 1), color, frozenset(selected))
        if key == self.key:
            return
        self.key = key
        hw, hh, m = 1.0 * p, 0.34 * p, 0.10 * p
        L = 0.30 * p
        lw = max(2, int(round(p / 15)))
        ext = hw + m + lw + 2
        xs = [x for _, x, _ in centers]
        ys = [y for _, _, y in centers]
        X0, Y0 = int(min(xs) - ext), int(min(ys) - hh - m - lw - 2)
        X1, Y1 = int(max(xs) + ext), int(max(ys) + hh + m + lw + 2)
        img = Image.new("RGBA", (X1 - X0, Y1 - Y0), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
        for tid, x, y in centers:
            x0, y0 = x - hw - m - X0, y - hh - m - Y0
            x1, y1 = x + hw + m - X0, y + hh + m - Y0
            for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                hx = sorted([cx, cx + dx * L])
                vy = sorted([cy, cy + dy * L])
                ox = 0 if dx > 0 else -lw
                oy = 0 if dy > 0 else -lw
                d.rectangle([hx[0], cy + oy, hx[1], cy + oy + lw - 1], fill=rgb)
                d.rectangle([cx + ox, vy[0], cx + ox + lw - 1, vy[1]], fill=rgb)
            if tid not in selected:
                t = 0.22 * p
                d.polygon([(x1 - t, y0), (x1, y0), (x1, y0 + t)], fill=rgb)
        self.lw.show_image(img, X0, Y0)
