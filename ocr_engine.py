"""OCR + 公招界面几何（tag 按钮位置、选中状态、时间箭头）。坐标均为截图内坐标。"""
from __future__ import annotations

import hashlib
import os
import re
import urllib.request
from dataclasses import dataclass, field

import recruit_core as rc

# ---- OCR 识别模型：中/英用内置模型；日/韩模型按需下载（约 10/13MB），用固定的 SHA-256 校验 ----
SERVER_LANG = {"cn": "zh", "en": "zh", "jp": "ja", "kr": "ko"}
LANG_SERVERS = {"zh": ("cn", "en"), "ja": ("jp",), "ko": ("kr",)}
MODEL_DIR = os.path.join(rc.USER_DIR, "models")
MODEL_BASE = "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/master/"
MODELS = {
    "ja": {
        "rec": ("onnx/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile.onnx", 9753335,
                "e1075a67dba758ecfc7ebc78a10ae61c95ac8fb66a9c86fab5541e33f085cb7a"),
        "keys": ("paddle/PP-OCRv4/rec/japan_PP-OCRv4_rec_mobile/japan_dict.txt", 17332,
                 "1dcfcb41eec90576a945b3084f22ade11ced506e24f14879245b071698f308e8"),
    },
    "ko": {
        "rec": ("onnx/PP-OCRv5/rec/korean_PP-OCRv5_rec_mobile.onnx", 13488748,
                "cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b"),
        "keys": ("paddle/PP-OCRv5/rec/korean_PP-OCRv5_rec_mobile/ppocrv5_korean_dict.txt", 47451,
                 "a88071c68c01707489baa79ebe0405b7beb5cca229f4fc94cc3ef992328802d7"),
    },
}
# 公招时间一定是 0X:X0:00（1~9 小时、10 分钟一档）——任何语言的模型都能读出数字，用来判断“这是公招界面”
RECRUIT_TIME_RE = re.compile(r"(?<!\d)0?[1-9]\s*[:：]\s*[0-5]0\s*[:：]\s*00(?!\d)")


def _model_path(lang, kind):
    return os.path.join(MODEL_DIR, os.path.basename(MODELS[lang][kind][0]))


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_ready(lang) -> bool:
    if lang == "zh":
        return True
    return all(os.path.isfile(_model_path(lang, k)) and os.path.getsize(_model_path(lang, k)) == MODELS[lang][k][1]
               for k in MODELS[lang])


def download_model(lang, log=print):
    """下载并校验日/韩识别模型；校验不通过的文件不会被保存"""
    os.makedirs(MODEL_DIR, exist_ok=True)
    for kind, (path, size, sha) in MODELS[lang].items():
        dst = _model_path(lang, kind)
        if os.path.isfile(dst) and _sha256(dst) == sha:
            continue
        log(f"OCR model {lang}: {os.path.basename(path)} ({size // 1024} KB)")
        req = urllib.request.Request(MODEL_BASE + path, headers={"User-Agent": "ark-recruit-helper"})
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read(size + 1)
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
            raise ValueError(f"model checksum mismatch: {os.path.basename(path)}")
        tmp = dst + ".part"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, dst)

# 以“tag 行距 p”为单位的界面比例（实测于官方 PC 端）
BTN_HALF_W = 1.0      # tag 按钮半宽
BTN_HALF_H = 0.34     # tag 按钮半高
ARROW_UP_DY = -3.2    # 时间“上”箭头相对第一行 tag 的纵向偏移
ARROW_DOWN_DY = -1.18
DIALOG = (-4.0, -3.9, 4.5, 4.4)  # 公招对话框 左/上(相对第1列/第1行) 右(相对第3列)/下


@dataclass
class Scan:
    srv: str = "cn"
    tags: list = field(default_factory=list)          # tagId，按识别顺序
    centers: dict = field(default_factory=dict)       # tagId -> (cx, cy)
    pitch: float = 0.0                                 # 行距（像素）
    selected: set = field(default_factory=set)        # 游戏里已选中的 tagId
    time: tuple | None = None                         # (时, 分)
    cols: list = field(default_factory=list)          # 三列中心 x
    looks_recruit: bool = False                       # 看到了公招时间（即使 tag 语言不对）
    row1: float = 0.0                                  # 第一行中心 y

    @property
    def ok(self):
        return len(self.tags) >= 3

    def arrows(self):
        """返回 {'h_up','h_down','m_up','m_down': (x,y)}；无法定位时返回 None"""
        if len(self.cols) < 2 or not self.pitch:
            return None
        p = self.pitch
        return {
            "h_up": (self.cols[0], self.row1 + ARROW_UP_DY * p),
            "h_down": (self.cols[0], self.row1 + ARROW_DOWN_DY * p),
            "m_up": (self.cols[1], self.row1 + ARROW_UP_DY * p),
            "m_down": (self.cols[1], self.row1 + ARROW_DOWN_DY * p),
        }

    def dialog(self):
        if len(self.cols) < 3 or not self.pitch:
            return None
        p, (l, t, r, b) = self.pitch, DIALOG
        return (self.cols[0] + l * p, self.row1 + t * p, self.cols[2] + r * p, self.row1 + b * p)

    def shifted(self, dx, dy) -> "Scan":
        s = Scan(**{**self.__dict__})
        s.centers = {k: (x + dx, y + dy) for k, (x, y) in self.centers.items()}
        s.cols = [c + dx for c in self.cols]
        s.row1 = self.row1 + dy
        return s


class OCR:
    def __init__(self):
        self.engines = {}
        self.engine_for("zh")

    def engine_for(self, lang):
        if lang not in self.engines:
            from rapidocr_onnxruntime import RapidOCR
            # 4 线程：速度和用满全部核心一样，CPU 占用减半
            kw = dict(intra_op_num_threads=4, inter_op_num_threads=1)
            if lang != "zh":
                for kind, (_, _, sha) in MODELS[lang].items():  # 每次加载前重新校验，防止文件被替换
                    if _sha256(_model_path(lang, kind)) != sha:
                        raise ValueError(f"{lang} model file changed or corrupt")
                kw.update(rec_model_path=_model_path(lang, "rec"), rec_keys_path=_model_path(lang, "keys"))
            self.engines[lang] = RapidOCR(**kw)
        return self.engines[lang]

    def available(self, lang):
        return lang in self.engines or model_ready(lang)

    def read_boxes(self, img, scale=1, lang="zh"):
        import cv2
        if scale != 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        result, _ = self.engine_for(lang)(img)
        out = []
        for box, text, _score in result or []:
            xs = [p[0] / scale for p in box]
            ys = [p[1] / scale for p in box]
            out.append((text, (min(xs), min(ys), max(xs), max(ys))))
        return out

    def _fill_slots(self, img, s, pool, lang, rects):
        _fill_slots_impl(self, img, s, pool, lang, rects)

    def scan(self, img, pools: dict, lang="zh") -> Scan:
        h, w = img.shape[:2]
        small = h * w < 1_500_000
        boxes = self.read_boxes(img, 2 if small else 1, lang)
        srv, tags = rc.detect_tags([t for t, _ in boxes], pools)
        pool = pools[srv]
        rects = _rects(boxes, pool, 0, 0)
        if 0 < len(tags) < 5:  # 第二遍：换一个放大倍数重读 tag 附近区域补漏（两遍漏掉的字往往不同）
            xs = [v for r in rects.values() for v in (r[0], r[2])]
            ys = [v for r in rects.values() for v in (r[1], r[3])]
            mx, my = max(150, (max(xs) - min(xs)) * 0.6), max(80, (max(ys) - min(ys)) * 1.2)
            x0, x1 = int(max(0, min(xs) - mx)), int(min(w, max(xs) + mx))
            y0, y1 = int(max(0, min(ys) - my)), int(min(h, max(ys) + my))
            more = self.read_boxes(img[y0:y1, x0:x1].copy(), 3 if small else 2, lang)
            _, tags2 = rc.detect_tags([t for t, _ in more], {srv: pool})
            tags += [t for t in tags2 if t not in tags]
            for k, r in _rects(more, pool, x0, y0).items():
                rects.setdefault(k, r)
            boxes += [(t, (a + x0, b + y0, c + x0, d + y0)) for t, (a, b, c, d) in more]
        s = Scan(srv=srv, tags=tags)
        s.looks_recruit = any(RECRUIT_TIME_RE.search(t) for t, _ in boxes)
        if not rects:
            return s
        s.centers = {k: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2) for k, r in rects.items()}
        _geometry(s, rects)
        if 3 <= len(s.tags) < 5:
            self._fill_slots(img, s, pool, lang, rects)
        s.selected = {k for k, (cx, cy) in s.centers.items() if _is_selected(img, cx, cy, s.pitch)}
        s.time = _parse_time(boxes, s)
        return s


def _rects(boxes, pool, ox, oy):
    out = {}
    for text, (a, b, c, d) in boxes:
        tid, _ = pool.match_text(text)
        if tid is not None and tid not in out:
            out[tid] = (a + ox, b + oy, c + ox, d + oy)
    return out


def _cluster(vals, tol):
    groups = []
    for v in sorted(vals):
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return [sum(g) / len(g) for g in groups]


COL_STEP = 2.33  # 相邻两列 tag 按钮的间距（单位：行距 p）


def _fill_slots_impl(ocr, img, s: Scan, pool, lang, rects):
    """公招永远是 5 个按钮、位置固定。找到 3~4 个时，直接读缺的那个按钮（只做文字识别，不做文字定位），
    并只在“还没找到的 tag”里匹配。韩文短词（제어형/딜러/힐링）常被定位步骤漏掉，单独读按钮则能读对。"""
    import cv2
    p = s.pitch
    xs = [c[0] for c in s.centers.values()]
    ys = [c[1] for c in s.centers.values()]
    base_x, row1 = min(xs), min(ys)
    slots = [(base_x + i * COL_STEP * p, row1) for i in range(3)] + [(base_x + i * COL_STEP * p, row1 + p) for i in range(2)]
    h, w = img.shape[:2]
    for sx, sy in slots:
        if any(abs(cx - sx) < 0.6 * p and abs(cy - sy) < 0.4 * p for cx, cy in s.centers.values()):
            continue
        x0, x1 = int(sx - 0.95 * p), int(sx + 0.95 * p)
        y0, y1 = int(sy - 0.30 * p), int(sy + 0.30 * p)
        if x0 < 0 or y0 < 0 or x1 > w or y1 > h:
            continue
        crop = img[y0:y1, x0:x1]
        if crop.std() < 8:  # 空按钮（没有字）
            continue
        if crop.shape[0] < 40:
            crop = cv2.resize(crop, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        res, _ = ocr.engine_for(lang)(crop.copy(), use_det=False, use_cls=False)
        text = res[0][0] if res else ""
        tid, _ = pool.match_text(text)
        if tid is None or tid in s.tags:
            continue
        s.tags.append(tid)
        s.centers[tid] = (sx, sy)
        rects[tid] = (x0, y0, x1, y1)
        if len(s.tags) >= 5:
            break


def _geometry(s: Scan, rects):
    heights = sorted(r[3] - r[1] for r in rects.values())
    text_h = heights[len(heights) // 2]
    rows = _cluster([c[1] for c in s.centers.values()], text_h * 0.8)
    s.pitch = rows[1] - rows[0] if len(rows) >= 2 else text_h / 0.385
    s.row1 = rows[0]
    s.cols = _cluster([c[0] for c in s.centers.values()], s.pitch * 0.8)[:3]


def _is_selected(img, cx, cy, p) -> bool:
    """选中的 tag 按钮是游戏蓝 (#0099DC)，未选中是深灰"""
    x0, x1 = int(cx - 0.92 * p), int(cx - 0.78 * p)
    y0, y1 = int(cy - 0.12 * p), int(cy + 0.12 * p) + 1
    if x0 < 0 or y0 < 0 or x1 <= x0 or y1 > img.shape[0]:
        return False
    b, g, r = img[y0:y1, x0:x1].reshape(-1, 3).mean(axis=0)
    return b > 140 and b - r > 90


def _parse_time(boxes, s: Scan):
    """找 “01 : 00 : 00” 形式的时间文本（位于 tag 上方 1~3 行距）"""
    for text, (a, b, c, d) in boxes:
        cy = (b + d) / 2
        if not (s.row1 - 3 * s.pitch < cy < s.row1 - 1.3 * s.pitch):
            continue
        nums = re.findall(r"\d+", text)
        if len(nums) >= 2:
            try:
                hh, mm = int(nums[0]), int(nums[1])
            except ValueError:
                continue
            if 1 <= hh <= 9 and mm % 10 == 0 and mm < 60:
                return hh, mm
    return None
