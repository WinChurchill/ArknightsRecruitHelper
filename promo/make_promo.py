"""明日方舟 公招助手 —— 宣传视频生成器（明日方舟风格 UI 动效）

用法：
  python promo/make_promo.py <公招界面截图.png> [--music 歌曲.mp3 --music-start 秒] [--out ...] [--preview 秒数...]

- 截图：游戏公开招募 tag 界面（越清晰越好，1920x1080 最佳）。脚本会自动识别 tag 位置。
- 卡片和括号用程序自带的叠加层代码绘制，和真实效果一致。
- --preview 只导出指定时间点的单帧 PNG，方便检查画面。
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import types

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import gamecard as gc  # noqa: E402
import ocr_engine as oe  # noqa: E402
import recruit_core as rc  # noqa: E402
from app import TEXT, App  # noqa: E402

W, H, FPS, DUR = 1920, 1080, 30, 30.0
FONTS = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")

# ---- 明日方舟风格配色 ----
BG0 = (14, 14, 16)
BG1 = (24, 24, 28)
WHITE = (240, 240, 240)
GREY = (150, 150, 156)
DIM = (90, 90, 96)
BLUE = (0, 153, 220)
YELLOW = (255, 201, 60)
ORANGE = (255, 122, 26)
PURPLE = (167, 123, 255)

COPY = {
    "zh": {
        "hook": "公招 tag 还在手动查表？", "hook_en": "STILL LOOKING UP RECRUIT TAGS BY HAND?",
        "s2": "进入公招界面 · 自动识别 tag", "s2_en": "AUTO-DETECTS YOUR RECRUITMENT TAGS",
        "s3": "保底组合 · 一眼看懂", "s3_en": "GUARANTEED COMBOS AT A GLANCE",
        "s4": "点一下 · 自动勾选 tag + 9 小时", "s4_en": "ONE CLICK  //  TAGS AND 9H TIMER SET FOR YOU",
        "s5": "高级资深干员 · 绝不错过", "s5_en": "NEVER MISS A TOP OPERATOR AGAIN",
        "feat": [("国服 · 国际服 · 日服 · 韩服", "CN / GLOBAL / JP / KR"),
                 ("中文 · English · 日本語 · 한국어", "4 INTERFACE LANGUAGES"),
                 ("只在公招界面工作 · CPU ≈0.3%", "LIGHTWEIGHT // ONLY WAKES ON RECRUIT"),
                 ("开源免费 · 一键安装", "FREE & OPEN SOURCE // ONE-CLICK INSTALL")],
        "title": "明日方舟 公招助手", "title_en": "ARKNIGHTS RECRUIT HELPER",
        "cta": "GitHub 搜索 / SEARCH", "disclaimer": "非官方玩家工具，与鹰角网络 / 悠星无关  ·  Unofficial fan tool, not affiliated with Hypergryph / Yostar",
    },
}
REPO = "github.com/WinChurchill/ArknightsRecruitHelper"


# ------------------------------------------------------------------ 工具
def ease_out(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def ease_in_out(x):
    x = max(0.0, min(1.0, x))
    return 4 * x ** 3 if x < 0.5 else 1 - (-2 * x + 2) ** 3 / 2


def prog(t, a, b):
    return max(0.0, min(1.0, (t - a) / (b - a)))


_fc = {}


def F(size, bold=True, en=False, var="Bold Condensed"):
    key = (int(size), bold, en, var)
    if key not in _fc:
        if en:
            f = ImageFont.truetype(os.path.join(FONTS, "bahnschrift.ttf"), int(size))
            try:
                f.set_variation_by_name(var)
            except Exception:  # noqa: BLE001
                pass
        else:
            f = ImageFont.truetype(os.path.join(FONTS, "msyhbd.ttc" if bold else "msyh.ttc"), int(size))
        _fc[key] = f
    return _fc[key]


def spaced(d, xy, text, font, fill, spacing=0.12, anchor="la"):
    """字间距加宽的英文（明日方舟界面里常见的样式）"""
    x, y = xy
    total = sum(d.textlength(c, font=font) for c in text) + spacing * font.size * (len(text) - 1)
    if anchor[0] == "m":
        x -= total / 2
    elif anchor[0] == "r":
        x -= total
    for c in text:
        d.text((x, y), c, font=font, fill=fill, anchor="l" + anchor[1])
        x += d.textlength(c, font=font) + spacing * font.size
    return total


def mixed_text(d, xy, text, size, fill, anchor="lm"):
    """中日韩混排：韩文用 Malgun Gothic，其余用雅黑（逐段画）"""
    import re
    runs = re.findall("[" + chr(0xAC00) + "-" + chr(0xD7AF) + "]+|[^" + chr(0xAC00) + "-" + chr(0xD7AF) + "]+", text)
    fonts = [ImageFont.truetype(os.path.join(FONTS, "malgunbd.ttf" if 0xAC00 <= ord(r[0]) <= 0xD7AF else "msyhbd.ttc"), int(size))
             for r in runs]
    total = sum(d.textlength(r, font=f) for r, f in zip(runs, fonts))
    x, y = xy
    if anchor[0] == "m":
        x -= total / 2
    for r, f in zip(runs, fonts):
        d.text((x, y), r, font=f, fill=fill, anchor="l" + anchor[1])
        x += d.textlength(r, font=f)


def alpha_paste(base, layer, xy=(0, 0), alpha=1.0):
    if alpha <= 0:
        return
    if alpha < 1:
        a = layer.getchannel("A").point(lambda v: int(v * alpha))
        layer = layer.copy()
        layer.putalpha(a)
    base.alpha_composite(layer, (int(xy[0]), int(xy[1])))


# ------------------------------------------------------------------ 背景与 HUD
def make_background():
    bg = Image.new("RGBA", (W, H), BG0 + (255,))
    d = ImageDraw.Draw(bg)
    for y in range(H):  # 竖向渐变
        c = tuple(int(BG0[i] + (BG1[i] - BG0[i]) * (1 - abs(y / H - 0.5) * 2)) for i in range(3))
        d.line([(0, y), (W, y)], fill=c + (255,))
    for x in range(0, W, 120):  # 细网格
        d.line([(x, 0), (x, H)], fill=(255, 255, 255, 7))
    for y in range(0, H, 120):
        d.line([(0, y), (W, y)], fill=(255, 255, 255, 7))
    return bg


def hatch_layer(offset):
    """斜线纹理（缓慢移动）"""
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    o = int(offset) % 28
    for x in range(-H, W + H, 28):
        d.line([(x + o, H), (x + o + H, 0)], fill=(255, 255, 255, 6), width=2)
    return lay


def hud(d, t):
    """四角的系统信息（明日方舟风格的小字和细线）"""
    f = F(20, en=True, var="SemiBold Condensed")
    spaced(d, (60, 50), "RECRUIT HELPER // V1.1.0", f, GREY + (255,), 0.18)
    d.line([(60, 78), (330, 78)], fill=DIM + (255,), width=1)
    d.rectangle([60, 76, 64, 80], fill=BLUE + (255,))
    spaced(d, (W - 60, 50), f"T+{t:05.2f}", f, GREY + (255,), 0.18, anchor="ra")
    for i in range(12):  # 右上角刻度
        x = W - 60 - i * 14
        h = 10 if (i + int(t * 6)) % 4 == 0 else 5
        d.line([(x, 84), (x, 84 + h)], fill=(GREY if h > 5 else DIM) + (255,), width=2)
    spaced(d, (60, H - 50), "UNOFFICIAL // FAN-MADE TOOL", F(18, en=True, var="SemiBold Condensed"),
           DIM + (255,), 0.2, anchor="ld")


def caption(img, t, t0, t1, zh, en, accent=BLUE):
    """斜切的下方字幕条：左侧色条 + 中文大字 + 英文小字"""
    if t < t0 - 0.05 or t > t1 + 0.4:
        return
    pin = ease_out(prog(t, t0, t0 + 0.45))
    pout = ease_in_out(prog(t, t1, t1 + 0.35))
    d0 = ImageDraw.Draw(img)
    fz, fe = F(62), F(26, en=True, var="SemiBold Condensed")
    tw = max(d0.textlength(zh, font=fz), d0.textlength(en, font=fe) * 1.2) + 120
    lay = Image.new("RGBA", (int(tw) + 80, 190), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    d.polygon([(0, 20), (tw + 40, 20), (tw, 180), (0, 180)], fill=(10, 10, 12, 210))
    d.rectangle([0, 20, 10, 180], fill=accent + (255,))
    d.line([(24, 32), (180, 32)], fill=accent + (255,), width=3)
    d.text((40, 98), zh, font=fz, fill=WHITE + (255,), anchor="lm")
    spaced(d, (42, 148), en, fe, GREY + (255,), 0.1, anchor="lm")
    x = -lay.width + (lay.width + 80) * pin - (lay.width + 120) * pout
    alpha_paste(img, lay, (x, H - 300), 1.0)


# ------------------------------------------------------------------ 游戏画面与叠加层
class Scene:
    def __init__(self, shot_path, lang):
        self.lang = lang
        self.tx = TEXT[lang]
        src = Image.open(shot_path).convert("RGB")
        self.game = self._fit_169(src)
        arr = np.array(self.game.convert("RGB"))[:, :, ::-1].copy()
        self.pools = {k: rc.Pool(k) for k in ("cn", "en")}
        o = oe.OCR()
        s = o.scan(arr, self.pools, "zh")
        if not s.ok:
            raise SystemExit("截图里没识别到公招 tag，请换一张公招 tag 界面的截图")
        self.scan = s
        self.pool = self.pools[s.srv]
        self.p = s.pitch
        print(f"tags: {[self.pool.tags[x] for x in s.tags]}  pitch={s.pitch:.1f}")
        # 时间文字的位置（用来做 01→09 的滚动）
        boxes = o.read_boxes(arr, 1)
        self.time_box = next((b for t, b in boxes if oe.RECRUIT_TIME_RE.search(t)), None)

    @staticmethod
    def _fit_169(src):
        """把截图裁成 16:9 并放大到 1920x1080（低分辨率截图会略微锐化）"""
        w, h = src.size
        if w / h > 16 / 9:
            nw = int(h * 16 / 9)
            src = src.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else:
            nh = int(w * 9 / 16)
            top = int((h - nh) * 0.35)
            src = src.crop((0, top, w, top + nh))
        if src.size != (W, H):
            src = src.resize((W, H), Image.LANCZOS)
            if src.width > w:
                src = src.filter(ImageFilter.UnsharpMask(radius=2, percent=80, threshold=2))
        return src.convert("RGBA")

    def model(self, tags):
        """借用主程序的 build_model 生成卡片数据"""
        fake = types.SimpleNamespace(pools=self.pools, cur_server=self.scan.srv, cfg={"show3": False},
                                     current_tags=lambda: list(tags),
                                     t=lambda key, **kw: self.tx[key].format(**kw))
        return App.build_model(fake)

    def card(self, model, hover=None):
        """用叠加层的真实绘制代码画「招募建议」竖排卡片"""
        c = object.__new__(gc.GameCard)
        c.tx, c.hover, c.offset, c.pages, c.more, c.shown, c.combo_key = self.tx, hover, 0, [], 0, 0, None
        dl, dt, dr, db = self.scan.dialog()
        cw = min(4.4 * self.p, W - dr - 0.4 * self.p)
        c.args = (model, self.p, int(cw), int(db - dt), True, None, "v")
        c._paint()
        return c.img, (dr + 0.12 * self.p, dt)

    def brackets(self, tids, color):
        b = object.__new__(gc.BracketLayer)
        out = {}
        b.lw = types.SimpleNamespace(show_image=lambda img, x, y: out.update(img=img, xy=(x, y)), hide=lambda: None)
        b.key = None
        pts = [(tid, *self.scan.centers[tid]) for tid in tids if tid in self.scan.centers]
        b.brackets(pts, self.p, color, set())
        return out.get("img"), out.get("xy", (0, 0))

    def paint_button(self, img, tid, text, selected):
        """把某个 tag 按钮画成选中（游戏蓝）或替换文字"""
        cx, cy = self.scan.centers[tid]
        p = self.p
        d = ImageDraw.Draw(img)
        d.rectangle([cx - 0.98 * p, cy - 0.33 * p, cx + 0.98 * p, cy + 0.33 * p],
                    fill=(BLUE if selected else (49, 49, 49)) + (255,))
        d.text((cx, cy), text, font=F(0.30 * p, bold=False), fill=(255, 255, 255, 255), anchor="mm")


# ------------------------------------------------------------------ 场景
def render_frame(sc: Scene, t: float, cache: dict) -> Image.Image:
    c = COPY[sc.lang]
    img = cache["bg"].copy()
    alpha_paste(img, hatch_layer(t * 12))
    d = ImageDraw.Draw(img)

    # ---- S1 0~3.6：开场钩子 ----
    if t < 3.9:
        a = 1 - prog(t, 3.4, 3.9)
        p1 = ease_out(prog(t, 0.2, 0.9))
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        bw = 1500 * p1
        dl.polygon([(W / 2 - bw / 2 - 60, 430), (W / 2 + bw / 2 + 60, 430), (W / 2 + bw / 2, 650), (W / 2 - bw / 2 - 120, 650)],
                   fill=(10, 10, 12, 230))
        dl.rectangle([W / 2 - bw / 2 - 60, 430, W / 2 + bw / 2 + 60, 436], fill=BLUE + (255,))
        if t > 0.6:
            pt = ease_out(prog(t, 0.6, 1.2))
            dl.text((W / 2, 520 + 30 * (1 - pt)), c["hook"], font=F(96), fill=WHITE + (int(255 * pt),), anchor="mm")
            spaced(dl, (W / 2, 610), c["hook_en"], F(32, en=True, var="SemiBold Condensed"),
                   GREY + (int(255 * pt),), 0.14, anchor="mm")
        for i, (x, y) in enumerate([(W / 2 - 760, 400), (W / 2 + 700, 680)]):  # 角标
            q = ease_out(prog(t, 0.9 + i * 0.15, 1.4 + i * 0.15))
            dl.line([(x, y), (x + 60 * q, y)], fill=YELLOW + (255,), width=4)
            dl.line([(x, y), (x, y + (40 if i == 0 else -40) * q)], fill=YELLOW + (255,), width=4)
        alpha_paste(img, lay, alpha=a)

    # ---- S2~S5 游戏画面 ----
    if 3.5 <= t < 24.2:
        six = t >= 20.0
        game = cache["game6"] if six else cache["game"]
        frame = game.copy()
        # S4：按钮变蓝 + 时间滚动
        if not six and t >= 16.7:
            for k, tid in enumerate(cache["best"]["tids"]):
                if t >= 16.7 + k * 0.25:
                    sc.paint_button(frame, tid, sc.pool.tags[tid], True)
            roll_hours(sc, frame, t)
        # 叠加层
        if t >= 6.2:
            for tid in (cache["tags6"] if six else sc.scan.tags):
                pass
        if 5.0 <= t < 9.6 and not six:  # S2：逐个识别（白色细括号）
            n = int(min(5, (t - 5.0) / 0.35 + 1))
            bimg, bxy = cache["scan_br"][n - 1]
            alpha_paste(frame, bimg, bxy)
            scan_line(frame, t, sc)
        if t >= 9.6:
            br_img, br_xy = cache["br6"] if six else cache["br"]
            alpha_paste(frame, br_img, br_xy, ease_out(prog(t, 9.6 if not six else 20.3, 10.0 if not six else 20.7)))
            hover = cache["best"] if (not six and 15.4 <= t < 16.7) else None
            card_img, card_xy = (cache["card6"] if six else (cache["card_hover"] if hover else cache["card"]))
            pin = ease_out(prog(t, 9.8 if not six else 20.2, 10.4 if not six else 20.7))
            alpha_paste(frame, card_img, (card_xy[0] + 120 * (1 - pin), card_xy[1]), pin)
        if not six:
            cursor(frame, t, cache)
        if six:
            six_pulse(frame, t, cache)
        # 镜头：缓慢推近 + 入场擦除
        z = 1.0 + 0.06 * ease_in_out(prog(t, 3.5, 24))
        cx, cy = cache["focus"]
        crop_w, crop_h = W / z, H / z
        x0 = min(max(cx - crop_w / 2, 0), W - crop_w)
        y0 = min(max(cy - crop_h / 2, 0), H - crop_h)
        view = frame.crop((int(x0), int(y0), int(x0 + crop_w), int(y0 + crop_h))).resize((W, H), Image.LANCZOS)
        if t < 4.3:  # 斜向擦除入场
            m = Image.new("L", (W, H), 0)
            q = ease_out(prog(t, 3.5, 4.3)) * (W + 600)
            ImageDraw.Draw(m).polygon([(0, 0), (q, 0), (q - 600, H), (0, H)], fill=255)
            view.putalpha(m)
        if 19.85 <= t < 20.15:  # 切到 6★ 的闪白
            view = Image.blend(view.convert("RGB"), Image.new("RGB", (W, H), (255, 255, 255)),
                               1 - abs(t - 20.0) / 0.15).convert("RGBA")
        out_a = 1 - prog(t, 23.8, 24.2)
        alpha_paste(img, view, alpha=out_a)
        d = ImageDraw.Draw(img)
        frame_corners(d)
        caption(img, t, 4.3, 9.4, c["s2"], c["s2_en"])
        caption(img, t, 9.8, 15.0, c["s3"], c["s3_en"], PURPLE)
        caption(img, t, 15.3, 19.6, c["s4"], c["s4_en"])
        caption(img, t, 20.4, 23.6, c["s5"], c["s5_en"], ORANGE)

    # ---- S6 24~27.6：功能卡片 ----
    if 24.0 <= t < 27.9:
        a = 1 - prog(t, 27.5, 27.9)
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        spaced(dl, (160, 210), "FEATURES", F(30, en=True, var="SemiBold Condensed"), GREY + (255,), 0.3)
        dl.line([(160, 240), (420, 240)], fill=BLUE + (255,), width=3)
        for i, (zh, en) in enumerate(c["feat"]):
            q = ease_out(prog(t, 24.2 + i * 0.25, 24.8 + i * 0.25))
            x, y = 160 + (i % 2) * 820, 300 + (i // 2) * 290
            x += 80 * (1 - q)
            col = [BLUE, YELLOW, PURPLE, ORANGE][i]
            dl.rectangle([x, y, x + 760, y + 240], fill=(20, 20, 24, int(235 * q)))
            dl.rectangle([x, y, x + 760, y + 5], fill=col + (int(255 * q),))
            spaced(dl, (x + 30, y + 60), f"0{i + 1}", F(64, en=True, var="Bold Condensed"), col + (int(255 * q),), 0.05, "lm")
            mixed_text(dl, (x + 30, y + 140), zh, 46, WHITE + (int(255 * q),))
            spaced(dl, (x + 32, y + 196), en, F(24, en=True, var="SemiBold Condensed"), GREY + (int(255 * q),), 0.12, "lm")
            dl.rectangle([x + 740, y + 220, x + 752, y + 232], fill=col + (int(255 * q),))
        alpha_paste(img, lay, alpha=a)

    # ---- S7 27.6~30：结尾 ----
    if t >= 27.6:
        q = ease_out(prog(t, 27.6, 28.3))
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dl = ImageDraw.Draw(lay)
        icon = cache["icon"]
        alpha_paste(lay, icon, (W / 2 - 64, 250 + 20 * (1 - q)), q)
        dl.text((W / 2, 470), c["title"], font=F(104), fill=WHITE + (int(255 * q),), anchor="mm")
        spaced(dl, (W / 2, 560), c["title_en"], F(40, en=True, var="Bold Condensed"), GREY + (int(255 * q),), 0.32, "mm")
        bw = 900 * ease_out(prog(t, 28.0, 28.6))
        dl.polygon([(W / 2 - bw / 2 - 30, 640), (W / 2 + bw / 2 + 30, 640), (W / 2 + bw / 2, 720), (W / 2 - bw / 2 - 60, 720)],
                   fill=BLUE + (int(255 * q),))
        if t > 28.3:
            r = ease_out(prog(t, 28.3, 28.8))
            dl.text((W / 2 - 15, 680), REPO, font=F(38, en=True, var="SemiBold Condensed"), fill=(255, 255, 255, int(255 * r)),
                    anchor="mm")
        dl.text((W / 2, 800), c["disclaimer"], font=F(22, bold=False), fill=DIM + (int(255 * q),), anchor="mm")
        alpha_paste(img, lay, alpha=1 - prog(t, 29.5, 30.0))

    hud(ImageDraw.Draw(img), t)
    return img.convert("RGB")


def frame_corners(d):
    """画面四角的白色角框"""
    L, m = 46, 36
    for (x, y, dx, dy) in ((m, m + 60, 1, 1), (W - m, m + 60, -1, 1), (m, H - m - 60, 1, -1), (W - m, H - m - 60, -1, -1)):
        d.line([(x, y), (x + dx * L, y)], fill=WHITE + (200,), width=3)
        d.line([(x, y), (x, y + dy * L)], fill=WHITE + (200,), width=3)


def scan_line(frame, t, sc):
    """蓝色扫描线扫过 tag 区域"""
    q = prog(t, 4.9, 6.6)
    if q <= 0 or q >= 1:
        return
    dl, dt, dr, db = sc.scan.dialog()
    y = dt + (db - dt) * q
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(40):
        d.line([(dl, y - k), (dr, y - k)], fill=BLUE + (int(90 * (1 - k / 40)),))
    d.line([(dl, y), (dr, y)], fill=(120, 210, 255, 255), width=3)
    frame.alpha_composite(lay)
    # 右侧读数
    d = ImageDraw.Draw(frame)
    n = min(5, int((t - 5.0) / 0.35 + 1)) if t >= 5.0 else 0
    spaced(d, (dl + 10, dt - 0.35 * sc.p), f"SCANNING // TAGS {n}/5", F(30, en=True, var="SemiBold Condensed"),
           (120, 210, 255, 255), 0.14, anchor="ld")


def roll_hours(sc, frame, t):
    """时间的「小时」从 01 滚到 09（按下箭头 8 次的效果）"""
    if not sc.time_box:
        return
    x0, y0, x1, y1 = sc.time_box
    hw = (x1 - x0) * 0.22  # 小时两位数大约占时间文字宽度的 22%
    q = ease_in_out(prog(t, 17.1, 18.1))
    hour = 1 + int(round(8 * q)) if t >= 17.1 else 1
    if hour == 1 and t < 17.1:
        return
    d = ImageDraw.Draw(frame)
    bg = frame.getpixel((int(x0 - 6), int((y0 + y1) / 2)))
    d.rectangle([x0 - 2, y0 - 4, x0 + hw + 6, y1 + 4], fill=bg)
    f = F((y1 - y0) * 1.05, en=True, var="SemiLight")
    d.text((x0 + hw / 2 + 2, (y0 + y1) / 2), f"{hour:02d}", font=f, fill=(58, 58, 60, 255), anchor="mm")
    if 17.1 <= t < 18.2:  # 下箭头按下的闪烁
        arr = sc.scan.arrows()
        if arr:
            ax, ay = arr["h_down"]
            r = 0.5 * sc.p
            d.rectangle([ax - 0.95 * sc.p, ay - 0.3 * sc.p, ax + 0.95 * sc.p, ay + 0.3 * sc.p],
                        outline=BLUE + (255,), width=3)
            _ = r


def cursor(frame, t, cache):
    """鼠标从右下移到最佳组合按钮并点击"""
    if not (14.6 <= t < 19.5):
        return
    sx, sy = W - 200, H - 120
    tx, ty = cache["best_btn"]
    q = ease_in_out(prog(t, 14.6, 15.5))
    x, y = sx + (tx - sx) * q, sy + (ty - sy) * q
    d = ImageDraw.Draw(frame)
    if 16.2 <= t < 16.9:  # 点击波纹
        r = 10 + 70 * prog(t, 16.2, 16.9)
        d.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255, int(255 * (1 - prog(t, 16.2, 16.9)))), width=4)
    s = 1.0 if not (16.2 <= t < 16.35) else 0.85
    pts = [(0, 0), (0, 36), (9, 27), (16, 42), (22, 39), (15, 25), (27, 25)]
    poly = [(x + px * s * 1.3, y + py * s * 1.3) for px, py in pts]
    d.polygon([(px + 3, py + 3) for px, py in poly], fill=(0, 0, 0, 120))
    d.polygon(poly, fill=(255, 255, 255, 255), outline=(20, 20, 20, 255))


def six_pulse(frame, t, cache):
    """6★：卡片最佳按钮的橙色光晕 + 「★6」大字"""
    bx, by, bw, bh = cache["best6_rect"]
    q = (math.sin((t - 20.6) * 5) + 1) / 2 if t >= 20.6 else 0
    lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    for k in range(6):
        g = 6 + k * 5
        d.rectangle([bx - g, by - g, bx + bw + g, by + bh + g], outline=ORANGE + (int((60 - k * 9) * (0.4 + 0.6 * q)),), width=4)
    frame.alpha_composite(lay)
    p = ease_out(prog(t, 20.5, 21.0))
    if p > 0:
        d = ImageDraw.Draw(frame)
        x, y = cache["six_xy"]
        size = 200 * (1.6 - 0.6 * p)
        d.text((x, y), "6", font=F(size, en=True, var="Bold Condensed"), fill=ORANGE + (int(255 * p),), anchor="mm")
        gc.star(d, x + size * 0.42, y - size * 0.12, size * 0.17, ORANGE + (int(255 * p),))


# ------------------------------------------------------------------ 准备素材
def prepare(sc: Scene):
    import app as appmod
    cache = {"bg": make_background()}
    cache["game"] = sc.game.copy()
    model = sc.model(sc.scan.tags)
    best = model["best"]
    cache["best"] = best
    cache["card"] = sc.card(model)
    cache["card_hover"] = sc.card(model, hover=best)
    col = gc.BADGE[best["min"]][0]
    cache["br"] = sc.brackets(best["tids"], "#%02x%02x%02x" % col)
    cache["scan_br"] = [sc.brackets(sc.scan.tags[:n], "#0099dc") for n in range(1, 6)]
    # 卡片里最佳按钮的位置（用于鼠标）
    card_img, (cx, cy) = cache["card"]
    c = object.__new__(gc.GameCard)
    c.tx, c.hover, c.offset, c.pages, c.more, c.shown, c.combo_key = sc.tx, None, 0, [], 0, 0, None
    dl, dt, dr, db = sc.scan.dialog()
    c.args = (model, sc.p, card_img.width, card_img.height, True, None, "v")
    c._paint()
    (x0, y0, x1, y1) = next(h[0] for h in c.hits if h[1] == "combo")
    cache["best_btn"] = (cx + (x0 + x1) / 2 + 30, cy + (y0 + y1) / 2 + 6)
    cache["focus"] = ((dl + cx + card_img.width) / 2, (dt + db) / 2)
    # 6★ 版本：把 tag 换成 高级资深干员 等
    tags6 = [11, 1, 19, 12, 9][: len(sc.scan.tags)]
    g6 = sc.game.copy()
    sc6 = sc.scan.shifted(0, 0)
    sc6.centers = {n: sc.scan.centers[o] for n, o in zip(tags6, sc.scan.tags)}
    sc6.tags = tags6
    orig_scan = sc.scan
    sc.scan = sc6
    for tid in tags6:
        sc.paint_button(g6, tid, sc.pool.tags[tid], False)
    m6 = sc.model(tags6)
    cache["game6"] = g6
    cache["card6"] = sc.card(m6)
    cache["br6"] = sc.brackets(m6["best"]["tids"], "#%02x%02x%02x" % gc.BADGE[6][0])
    c6 = object.__new__(gc.GameCard)
    c6.tx, c6.hover, c6.offset, c6.pages, c6.more, c6.shown, c6.combo_key = sc.tx, None, 0, [], 0, 0, None
    c6.args = (m6, sc.p, cache["card6"][0].width, cache["card6"][0].height, True, None, "v")
    c6._paint()
    (x0, y0, x1, y1) = next(h[0] for h in c6.hits if h[1] == "combo")
    ox, oy = cache["card6"][1]
    cache["best6_rect"] = (ox + x0, oy + y0, x1 - x0, y1 - y0)
    cache["six_xy"] = (dl + (dr - dl) * 0.52, dt - 0.2 * sc.p)
    cache["tags6"] = tags6
    sc.scan = orig_scan
    icon = appmod.make_icon(128).convert("RGBA")
    cache["icon"] = icon
    return cache


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shot")
    ap.add_argument("--lang", default="zh")
    ap.add_argument("--out", default=os.path.join(HERE, "out", "promo_16x9.mp4"))
    ap.add_argument("--preview", nargs="*", type=float)
    ap.add_argument("--music", help="背景音乐文件（你自己的，例如官方 OST）；不填则无声")
    ap.add_argument("--music-start", type=float, default=0.0, help="从歌曲的第几秒开始用")
    ap.add_argument("--music-db", type=float, default=-3.0, help="音乐音量（dB）")
    a = ap.parse_args()
    sc = Scene(a.shot, a.lang)
    cache = prepare(sc)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    if a.preview:
        for t in a.preview:
            p = os.path.join(os.path.dirname(a.out), f"preview_{t:05.2f}.png")
            render_frame(sc, t, cache).save(p)
            print("preview", p)
        return
    import imageio_ffmpeg
    n = int(DUR * FPS)
    video_only = a.out.replace(".mp4", "_video.mp4") if a.music else a.out
    w = imageio_ffmpeg.write_frames(video_only, (W, H), fps=FPS, codec="libx264", pix_fmt_out="yuv420p", macro_block_size=1,
                                    output_params=["-crf", "18", "-preset", "medium", "-movflags", "+faststart"])
    w.send(None)
    for i in range(n):
        w.send(render_frame(sc, i / FPS, cache).tobytes())
        if i % 60 == 0:
            print(f"frame {i}/{n}", flush=True)
    w.close()
    if a.music:
        import audio
        audio.mux_music(video_only, a.music, a.out, imageio_ffmpeg.get_ffmpeg_exe(), DUR,
                        start=a.music_start, volume_db=a.music_db)
        os.remove(video_only)
    print("done", a.out)


if __name__ == "__main__":
    main()
