"""OCR + 公招界面几何（tag 按钮位置、选中状态、时间箭头）。坐标均为截图内坐标。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import recruit_core as rc

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
        from rapidocr_onnxruntime import RapidOCR
        # 4 线程：速度和用满全部核心一样，CPU 占用减半
        self.engine = RapidOCR(intra_op_num_threads=4, inter_op_num_threads=1)

    def read_boxes(self, img, scale=1):
        import cv2
        if scale != 1:
            img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        result, _ = self.engine(img)
        out = []
        for box, text, _score in result or []:
            xs = [p[0] / scale for p in box]
            ys = [p[1] / scale for p in box]
            out.append((text, (min(xs), min(ys), max(xs), max(ys))))
        return out

    def scan(self, img, pools: dict) -> Scan:
        h, w = img.shape[:2]
        small = h * w < 1_500_000
        boxes = self.read_boxes(img, 2 if small else 1)
        srv, tags = rc.detect_tags([t for t, _ in boxes], pools)
        pool = pools[srv]
        rects = _rects(boxes, pool, 0, 0)
        if 0 < len(tags) < 5 and not small:  # 第二遍：放大 tag 附近区域补漏
            xs = [v for r in rects.values() for v in (r[0], r[2])]
            ys = [v for r in rects.values() for v in (r[1], r[3])]
            mx, my = max(150, (max(xs) - min(xs)) * 0.6), max(80, (max(ys) - min(ys)) * 1.2)
            x0, x1 = int(max(0, min(xs) - mx)), int(min(w, max(xs) + mx))
            y0, y1 = int(max(0, min(ys) - my)), int(min(h, max(ys) + my))
            more = self.read_boxes(img[y0:y1, x0:x1].copy(), 2)
            _, tags2 = rc.detect_tags([t for t, _ in more], {srv: pool})
            tags += [t for t in tags2 if t not in tags]
            for k, r in _rects(more, pool, x0, y0).items():
                rects.setdefault(k, r)
            boxes += [(t, (a + x0, b + y0, c + x0, d + y0)) for t, (a, b, c, d) in more]
        s = Scan(srv=srv, tags=tags)
        if not rects:
            return s
        s.centers = {k: ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2) for k, r in rects.items()}
        _geometry(s, rects)
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
