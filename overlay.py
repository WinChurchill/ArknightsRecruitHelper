"""游戏风格的界面组件：叠加层上的 tag 括号标记、结果面板、组合列表（主窗口也复用）。"""
from __future__ import annotations

import tkinter as tk

import winutil as w

# ---- 明日方舟风格配色 ----
ACCENT = "#0099DC"       # 游戏蓝
BG = "#1B1B1D"
PANEL = "#232326"
ROW = "#2C2C30"
ROW_HOVER = "#3A3A40"
CHIP = "#46464C"
LINE = "#3C3C42"
TXT = "#F2F2F2"
SUB = "#8E8E96"
WARN = "#FFB400"
STAR = {6: "#FF7A1A", 5: "#FFC93C", 4: "#C9A3FF", 3: "#4FB8FF", 2: "#D9E36B", 1: "#B4B4B4"}
CN = "Microsoft YaHei UI"
EN = "Bahnschrift"


def px(n) -> int:  # tk 字号：负数=像素
    return -max(9, int(round(n)))


# ------------------------------------------------------------------ 标记层
class Marks:
    """覆盖全部显示器的透明、鼠标穿透、截图不可见画布。"""
    KEY = "#010203"

    def __init__(self, root):
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=self.KEY)
        self.win.attributes("-transparentcolor", self.KEY)
        self.vs = w.virtual_screen()
        self.win.geometry(f"{self.vs['width']}x{self.vs['height']}+{self.vs['left']}+{self.vs['top']}")
        self.cv = tk.Canvas(self.win, bg=self.KEY, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.win.update()
        w.add_exstyle(self.win, w.WS_EX_LAYERED | w.WS_EX_TRANSPARENT | w.WS_EX_TOOLWINDOW | w.WS_EX_NOACTIVATE)
        self.capture_safe = w.exclude_from_capture(self.win)

    def clear(self):
        self.cv.delete("all")

    def show(self, v=True):
        if v:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
        else:
            self.win.withdraw()

    def brackets(self, centers, pitch, color, selected=()):
        """centers: [(tid, x, y)] 屏幕坐标。给按钮画游戏风格的角括号。"""
        self.clear()
        p = pitch
        hw, hh, m = 1.0 * p, 0.34 * p, 0.10 * p
        L = 0.30 * p
        lw = max(2, int(p / 14))
        ox, oy = self.vs["left"], self.vs["top"]
        for tid, x, y in centers:
            x0, y0, x1, y1 = x - hw - m - ox, y - hh - m - oy, x + hw + m - ox, y + hh + m - oy
            for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                self.cv.create_line(cx, cy, cx + dx * L, cy, fill=color, width=lw, capstyle="projecting")
                self.cv.create_line(cx, cy, cx, cy + dy * L, fill=color, width=lw, capstyle="projecting")
            # 未选中的待选 tag：右上角小三角提示“点这里”
            if tid not in selected:
                t = 0.22 * p
                self.cv.create_polygon(x1 - t, y0, x1, y0, x1, y0 + t, fill=color, outline="")


# ------------------------------------------------------------------ 组合列表
class ResultView(tk.Frame):
    """结论 + 组合卡片列表。model 由 App.build_model 生成。"""

    def __init__(self, master, width, scale, on_pick, on_hover, texts):
        super().__init__(master, bg=PANEL)
        self.W, self.f = width, scale
        self.on_pick, self.on_hover, self.tx = on_pick, on_hover, texts
        self.model = None

    def set_size(self, width, scale):
        self.W, self.f = width, scale

    def render(self, model):
        self.model = model
        for c in self.winfo_children():
            c.destroy()
        if not model:
            return
        self._verdict(model)
        for i, c in enumerate(model["combos"]):
            self._row(c, i == 0)
        if not model["combos"]:
            tk.Label(self, text=model["empty"], bg=PANEL, fg=SUB, font=(CN, px(self.f)),
                     wraplength=self.W - 24, justify="left").pack(fill="x", padx=12, pady=(2, 10))

    def _verdict(self, m):
        f, W = self.f, self.W
        color = STAR.get(m["star"], SUB)
        cv = tk.Canvas(self, width=W, height=int(f * 4.2), bg=PANEL, highlightthickness=0)
        cv.pack(fill="x")
        h = int(f * 4.2)
        cv.create_rectangle(0, 0, W, h, fill=PANEL, outline="")
        cv.create_text(14, h / 2, text=str(m["star"]) if m["star"] else "–", anchor="w", fill=color,
                       font=(EN, px(f * 3.0), "bold"))
        cv.create_text(14 + f * 2.1, h / 2 - f * 0.55, text="★", anchor="w", fill=color, font=(CN, px(f * 1.3)))
        x = 14 + f * 3.6
        cv.create_text(x, h / 2 - f * 0.75, text=m["title"], anchor="w", fill=TXT, font=(CN, px(f * 1.25), "bold"))
        cv.create_text(x, h / 2 + f * 0.85, text=m["subtitle"], anchor="w", fill=SUB, font=(CN, px(f * 0.9)),
                       width=W - x - 80)
        if m.get("time"):
            t = cv.create_text(W - 14, h / 2, text=m["time"], anchor="e", fill=TXT, font=(EN, px(f * 1.3), "bold"))
            x0, y0, x1, y1 = cv.bbox(t)
            r = cv.create_rectangle(x0 - 8, y0 - 2, x1 + 8, y1 + 2, fill=ACCENT, outline="")
            cv.tag_lower(r)
            cv.tag_lower(cv.find_all()[0])
        cv.create_line(0, h - 1, W, h - 1, fill=LINE)

    def _row(self, c, first):
        f, W = self.f, self.W
        color = STAR[c["min"]]
        cv = tk.Canvas(self, width=W, bg=ROW, highlightthickness=0, cursor="hand2")
        cv.pack(fill="x", pady=(0, 1))
        pad = 12
        # 星级
        cv.create_text(pad + 6, f * 0.5, text=c["label"], anchor="nw", fill=color, font=(EN, px(f * 1.35), "bold"))
        x = pad + f * 3.3
        y = f * 0.55
        for name in c["tags"]:
            t = cv.create_text(x + 7, y, text=name, anchor="nw", fill=TXT, font=(CN, px(f * 0.95), "bold"))
            x0, y0, x1, y1 = cv.bbox(t)
            r = cv.create_rectangle(x0 - 7, y0 - 2, x1 + 7, y1 + 2, fill=CHIP, outline="")
            cv.tag_lower(r)
            x = x1 + 12
        y = y + f * 1.9
        x = pad + f * 3.3
        # 干员（流式排版，按星级上色）
        for name, r in c["ops"]:
            t = cv.create_text(x, y, text=name, anchor="nw", fill=STAR.get(r, SUB), font=(CN, px(f * 0.88)))
            x0, y0, x1, y1 = cv.bbox(t)
            if x1 > W - pad and x > pad + f * 3.3 + 1:
                x, y = pad + f * 3.3, y + f * 1.45
                cv.coords(t, x, y)
                x0, y0, x1, y1 = cv.bbox(t)
            x = x1 + f * 0.7
        h = int(y + f * 1.8)
        cv.configure(height=h)
        bar = cv.create_rectangle(0, 0, 4, h, fill=color, outline="")
        bg = cv.create_rectangle(0, 0, W, h, fill=ROW, outline="")
        cv.tag_lower(bg)
        hint = cv.create_text(W - pad, f * 0.6, text=self.tx["pick"], anchor="ne", fill=ACCENT,
                              font=(CN, px(f * 0.85), "bold"), state="hidden")

        def enter(_):
            cv.itemconfigure(bg, fill=ROW_HOVER)
            cv.itemconfigure(hint, state="normal")
            self.on_hover(c)

        def leave(_):
            cv.itemconfigure(bg, fill=ROW)
            cv.itemconfigure(hint, state="hidden")
            self.on_hover(None)

        cv.bind("<Enter>", enter)
        cv.bind("<Leave>", leave)
        cv.bind("<Button-1>", lambda e: self.on_pick(c))


# ------------------------------------------------------------------ 嵌入游戏的卡片
# 取自游戏公招对话框的实际配色
G_FRAME = "#C9C8C4"     # 对话框半透明外框
G_CARD = "#F3F3F2"      # 内卡片
G_LABEL = "#5E5E60"     # “职业需求”这类标签
G_SUB = "#8A8A8C"
G_BTN = "#313131"       # tag 按钮
G_BLUE = "#0099DC"      # 选中/确认蓝
BADGE = {6: ("#FF7A1A", "white"), 5: ("#FFC93C", "#3A2A00"), 4: ("#A77BFF", "white"),
         3: ("#33A9E6", "white"), 1: ("#9A9A9A", "white")}


class GameCard:
    """贴在公招对话框正下方、和对话框同风格的卡片：「招募建议」+ 组合按钮（点击自动选择）。"""

    def __init__(self, root, texts, on_pick, on_hover, on_close, on_admin):
        self.tx = texts
        self.on_pick, self.on_hover, self.on_close, self.on_admin = on_pick, on_hover, on_close, on_admin
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.97)
        self.cv = tk.Canvas(self.win, bg=G_FRAME, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        self.win.withdraw()
        self.win.update_idletasks()
        w.add_exstyle(self.win, w.WS_EX_TOOLWINDOW | w.WS_EX_NOACTIVATE)
        self.capture_safe = w.exclude_from_capture(self.win)
        self.visible = False

    def set_texts(self, texts):
        self.tx = texts

    def render(self, model, p, W, H, admin_ok, busy_text=None):
        cv = self.cv
        cv.delete("all")
        cv.configure(width=W, height=H)
        f = p * 0.30
        pad_x, pad_y = 0.55 * p, 0.16 * p
        x0, y0, x1, y1 = pad_x, pad_y, W - pad_x, H - pad_y
        cv.create_rectangle(0, 0, W, H, fill=G_FRAME, outline="")
        # 内卡片 + 轻微阴影（同游戏）
        cv.create_rectangle(x0 + 2, y0 + 2, x1 + 2, y1 + 2, fill="#B5B4B0", outline="")
        cv.create_rectangle(x0, y0, x1, y1, fill=G_CARD, outline="")
        # 左侧标签，位置与「招募预算」对齐
        lx = x0 + 0.5 * p
        cy = (y0 + y1) / 2
        cv.create_text(lx, cy - 0.22 * p, text=self.tx["card_label"], anchor="w", fill=G_LABEL,
                       font=(CN, px(f * 1.05), "bold"))
        star = model["star"] if model else 0
        sub_color = BADGE.get(star, (G_SUB,))[0] if star >= 4 or star == 1 else G_SUB
        sub = busy_text or (model["title"] if model else "")
        cv.create_text(lx, cy + 0.25 * p, text=sub, anchor="w", fill=G_BLUE if busy_text else sub_color,
                       font=(CN, px(f * 0.85), "bold"))
        # 关闭
        xb = cv.create_text(W - 0.18 * p, 0.12 * p, text="✕", anchor="ne", fill="#6E6E70", font=(CN, px(f * 0.75)))
        cv.tag_bind(xb, "<Button-1>", lambda e: self.on_close())
        if not admin_ok and not busy_text:  # 小提示：点击以管理员重启（按钮照常显示）
            t = cv.create_text(x1 - 0.1 * p, y1 - 0.05 * p, text=self.tx["need_admin_short"], anchor="se",
                               fill="#C77700", font=(CN, px(f * 0.72)))
            cv.tag_bind(t, "<Button-1>", lambda e: self.on_admin())

        bx = x0 + 3.0 * p
        combos = (model or {}).get("combos", [])
        if not combos:
            cv.create_text(bx, cy, text=(model or {}).get("subtitle", ""), anchor="w", fill=G_LABEL,
                           font=(CN, px(f * 0.95)))
            return
        bh = 0.70 * p                      # 与游戏 tag 按钮同高
        by = cy - 0.30 * p if H > 1.55 * p else cy
        gap = 0.18 * p
        shown = 0
        for i, c in enumerate(combos):
            label = " + ".join(c["tags"]) + ("  ·  3:50" if c["min"] == 1 else "")
            tw = self._text_w(label, f)
            bw = 0.75 * p + tw + 0.45 * p
            more_w = 0.9 * p if i < len(combos) - 1 else 0
            if bx + bw + more_w > x1 - 0.2 * p and shown:
                cv.create_text(bx, by, text=f"+{len(combos) - i}", anchor="w", fill=G_SUB,
                               font=(EN, px(f * 1.0), "bold"))
                break
            self._button(c, bx, by - bh / 2, bw, bh, label, f, p, H)
            bx += bw + gap
            shown += 1

    def _text_w(self, s, f):
        t = self.cv.create_text(-1000, -1000, text=s, font=(CN, px(f), "bold"))
        x0, _, x1, _ = self.cv.bbox(t)
        self.cv.delete(t)
        return x1 - x0

    def _button(self, c, x, y, bw, bh, label, f, p, H):
        cv = self.cv
        tag = f"b{id(c)}"
        bg = cv.create_rectangle(x, y, x + bw, y + bh, fill=G_BTN, outline="", tags=tag)
        col, fg = BADGE[c["min"]]
        bdw = 0.62 * p
        cv.create_rectangle(x, y, x + bdw, y + bh, fill=col, outline="", tags=tag)
        cv.create_text(x + bdw / 2, y + bh / 2, text=c["label"], fill=fg, font=(EN, px(f * 0.95), "bold"), tags=tag)
        cv.create_text(x + bdw + 0.2 * p, y + bh / 2, text=label, anchor="w", fill="white",
                       font=(CN, px(f), "bold"), tags=tag)
        if H > 1.55 * p:  # 按钮下方：可能出的干员
            names = " · ".join(n for n, _ in c["ops"][:4]) + (" …" if len(c["ops"]) > 4 else "")
            cv.create_text(x + 2, y + bh + 0.08 * p, text=names, anchor="nw", fill=G_SUB,
                           font=(CN, px(f * 0.78)), width=bw, tags=tag)

        def enter(_):
            cv.itemconfigure(bg, fill=G_BLUE)
            cv.configure(cursor="hand2")
            self.on_hover(c)

        def leave(_):
            cv.itemconfigure(bg, fill=G_BTN)
            cv.configure(cursor="")
            self.on_hover(None)
        cv.tag_bind(tag, "<Enter>", enter)
        cv.tag_bind(tag, "<Leave>", leave)
        cv.tag_bind(tag, "<Button-1>", lambda e: self.on_pick(c))

    def place(self, x, y, W, H):
        self.win.geometry(f"{int(W)}x{int(H)}+{int(x)}+{int(y)}")

    def show(self, v=True):
        if v and not self.visible:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
        elif not v and self.visible:
            self.win.withdraw()
        self.visible = v


# ------------------------------------------------------------------ 叠加面板
class Panel:
    """浮在游戏旁边、可点击的结果面板（截图不可见）。"""

    def __init__(self, root, texts, on_pick, on_hover, on_close, on_admin, on_moved):
        self.root, self.tx = root, texts
        self.on_close, self.on_admin, self.on_moved = on_close, on_admin, on_moved
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.96)
        self.win.configure(bg=LINE)
        self.inner = tk.Frame(self.win, bg=PANEL)
        self.inner.pack(fill="both", expand=True, padx=1, pady=1)
        self.W, self.f = 330, 13
        self.view = ResultView(self.inner, self.W, self.f, on_pick, on_hover, texts)
        self.win.withdraw()
        self.win.update_idletasks()
        w.add_exstyle(self.win, w.WS_EX_TOOLWINDOW | w.WS_EX_NOACTIVATE)
        self.capture_safe = w.exclude_from_capture(self.win)
        self.visible = False
        self._drag = None

    def set_texts(self, texts):
        self.tx = texts
        self.view.tx = texts

    def render(self, model, scale_px, admin_ok, busy_text=None):
        f = max(11, min(16, scale_px))
        self.f, self.W = f, int(f * 25)
        self.view.set_size(self.W, f)
        for c in self.inner.winfo_children():
            if c is not self.view:
                c.destroy()
        self.view.pack_forget()
        self._header()
        self.view.pack(fill="x")
        self.view.render(model)
        self._footer(admin_ok, busy_text)

    def _header(self):
        f, W = self.f, self.W
        h = int(f * 2.3)
        cv = tk.Canvas(self.inner, width=W, height=h, bg=BG, highlightthickness=0, cursor="fleur")
        cv.pack(fill="x")
        cv.create_rectangle(0, 0, 4, h, fill=ACCENT, outline="")
        t = cv.create_text(14, h / 2, text=self.tx["panel_title"], anchor="w", fill=TXT, font=(CN, px(f), "bold"))
        cv.create_text(cv.bbox(t)[2] + 10, h / 2 + 1, text="RECRUITMENT", anchor="w", fill=SUB,
                       font=(EN, px(f * 0.8)))
        x = cv.create_text(W - 12, h / 2, text="✕", anchor="e", fill=SUB, font=(CN, px(f)))
        cv.tag_bind(x, "<Button-1>", lambda e: self.on_close())
        cv.tag_bind(x, "<Enter>", lambda e: cv.itemconfigure(x, fill=TXT))
        cv.tag_bind(x, "<Leave>", lambda e: cv.itemconfigure(x, fill=SUB))
        cv.bind("<ButtonPress-1>", self._drag_start)
        cv.bind("<B1-Motion>", self._drag_move)
        cv.bind("<ButtonRelease-1>", self._drag_end)

    def _footer(self, admin_ok, busy_text):
        f = self.f
        fr = tk.Frame(self.inner, bg=BG)
        fr.pack(fill="x")
        if busy_text:
            tk.Label(fr, text=busy_text, bg=BG, fg=ACCENT, font=(CN, px(f * 0.85), "bold"),
                     anchor="w").pack(fill="x", padx=12, pady=6)
        elif not admin_ok:
            lb = tk.Label(fr, text=self.tx["need_admin"], bg=BG, fg=WARN, font=(CN, px(f * 0.85)),
                          anchor="w", justify="left", wraplength=self.W - 24, cursor="hand2")
            lb.pack(fill="x", padx=12, pady=6)
            lb.bind("<Button-1>", lambda e: self.on_admin())
        else:
            tk.Label(fr, text=self.tx["pick_hint"], bg=BG, fg=SUB, font=(CN, px(f * 0.8)),
                     anchor="w").pack(fill="x", padx=12, pady=5)

    def _drag_start(self, e):
        self._drag = (e.x_root - self.win.winfo_x(), e.y_root - self.win.winfo_y())

    def _drag_move(self, e):
        if self._drag:
            self.win.geometry(f"+{e.x_root - self._drag[0]}+{e.y_root - self._drag[1]}")

    def _drag_end(self, e):
        if self._drag:
            self._drag = None
            self.on_moved(self.win.winfo_x(), self.win.winfo_y())

    def size(self):
        self.win.update_idletasks()
        return self.win.winfo_reqwidth(), self.win.winfo_reqheight()

    def place(self, x, y):
        self.win.geometry(f"+{int(x)}+{int(y)}")

    def show(self, v=True):
        if v and not self.visible:
            self.win.deiconify()
            self.win.attributes("-topmost", True)
        elif not v and self.visible:
            self.win.withdraw()
        self.visible = v
