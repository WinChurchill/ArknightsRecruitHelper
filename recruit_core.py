"""明日方舟公开招募 - 数据 & 组合计算核心 / Arknights recruitment core logic."""
from __future__ import annotations

import difflib
import itertools
import json
import os
import re
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")

SOURCES = {
    "cn": "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData/master/zh_CN/gamedata/excel/",
    "en": "https://raw.githubusercontent.com/Kengxxiao/ArknightsGameData_YoStar/main/en_US/gamedata/excel/",
}
MIRRORS = [  # 国内网络 raw.githubusercontent 不通时的备用
    "",
    "https://ghfast.top/",
    "https://gh-proxy.com/",
]

PROFESSION_TAG_ID = {
    "WARRIOR": 1, "SNIPER": 2, "TANK": 3, "MEDIC": 4,
    "SUPPORT": 5, "CASTER": 6, "SPECIAL": 7, "PIONEER": 8,
}
POSITION_TAG_ID = {"MELEE": 9, "RANGED": 10}
TOP_ID, SENIOR_ID, STARTER_ID, ROBOT_ID = 11, 14, 17, 28


# ---------------------------------------------------------------- data build
def _rarity(v) -> int:
    if isinstance(v, int):
        return v + 1
    m = re.search(r"(\d)", str(v))
    return int(m.group(1)) if m else 0


def _parse_recruit_detail(text: str) -> dict[str, int]:
    """recruitDetail 文本 -> {干员名: 星级}"""
    names: dict[str, int] = {}
    for sec in re.split(r"-{5,}", text):
        m = re.search(r"(★+)\s*(?:\\n|\n)", sec)
        if not m:
            continue
        stars = len(m.group(1))
        body = sec[m.end():]
        body = re.sub(r"<[^>]*>", "", body)
        for n in body.split("/"):
            n = n.strip()
            if n:
                names[n] = stars
    return names


def build_pool(gacha: dict, chars: dict) -> dict:
    tags = {t["tagId"]: t["tagName"] for t in gacha["gachaTags"] if t["tagId"] < 1000}
    name2tid = {v: k for k, v in tags.items()}
    pool_names = _parse_recruit_detail(gacha["recruitDetail"])
    by_name: dict[str, list] = {}
    for cid, c in chars.items():
        if cid.startswith("char_"):
            by_name.setdefault(c["name"].strip().strip("'\""), []).append(c)
    ops = []
    for name, stars in pool_names.items():
        cands = by_name.get(name, [])
        c = next((x for x in cands if _rarity(x["rarity"]) == stars), cands[0] if cands else None)
        if c is None:
            print(f"[warn] 找不到干员 {name}")
            continue
        tid = set()
        tid.add(PROFESSION_TAG_ID[c["profession"]])
        tid.add(POSITION_TAG_ID[c["position"]])
        if stars == 6:
            tid.add(TOP_ID)
        if stars == 5:
            tid.add(SENIOR_ID)
        for t in c.get("tagList") or []:
            if t in name2tid:
                tid.add(name2tid[t])
        ops.append({"name": name, "rarity": stars, "tags": sorted(tid)})
    return {"tags": {str(k): v for k, v in tags.items()}, "ops": ops}


def _fetch_json(url: str) -> dict:
    err = None
    for m in MIRRORS:
        try:
            req = urllib.request.Request(m + url, headers={"User-Agent": "ak-recruit-tool"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            err = e
    raise RuntimeError(f"下载失败 / download failed: {url}: {err}")


META_PATH = os.path.join(DATA_DIR, "meta.json")
CHECK_INTERVAL = 6 * 3600  # 每 6 小时最多检查一次


def _load_meta() -> dict:
    try:
        with open(META_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def _gacha_sig(g: dict) -> str:
    import hashlib
    raw = json.dumps([g["recruitDetail"], g["gachaTags"]], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def update_data(log=print, force=True) -> list[str]:
    """检查并更新招募池。force=False 时只在公招数据有变化时才下载大文件。
    返回有更新的服务器列表。"""
    import time
    os.makedirs(DATA_DIR, exist_ok=True)
    meta = _load_meta()
    changed = []
    for srv, base in SOURCES.items():
        g = _fetch_json(base + "gacha_table.json")
        sig = _gacha_sig(g)
        have = os.path.exists(os.path.join(DATA_DIR, f"pool_{srv}.json"))
        if not force and have and meta.get(srv, {}).get("sig") == sig:
            continue
        log(f"[{srv}] 下载 character_table (约10MB+) ...")
        c = _fetch_json(base + "character_table.json")
        pool = build_pool(g, c)
        with open(os.path.join(DATA_DIR, f"pool_{srv}.json"), "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False, indent=1)
        meta[srv] = {"sig": sig, "ops": len(pool["ops"])}
        changed.append(srv)
        log(f"[{srv}] 完成: {len(pool['ops'])} 名干员")
    meta["checked"] = time.time()
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=1)
    return changed


def auto_update_due(interval: float = CHECK_INTERVAL) -> bool:
    import time
    return time.time() - _load_meta().get("checked", 0) > interval


# ---------------------------------------------------------------- pools
class Pool:
    def __init__(self, server: str):
        self.server = server
        with open(os.path.join(DATA_DIR, f"pool_{server}.json"), encoding="utf-8") as f:
            d = json.load(f)
        self.tags: dict[int, str] = {int(k): v for k, v in d["tags"].items()}
        self.ops = [dict(o, tags=set(o["tags"])) for o in d["ops"]]
        self._norm = {_norm(v): k for k, v in self.tags.items()}

    def match_text(self, text: str) -> tuple[int | None, float]:
        """OCR 文本 -> (tagId, 置信度)"""
        n = _norm(text)
        if not n:
            return None, 0.0
        if n in self._norm:
            return self._norm[n], 1.0
        is_cjk = bool(re.search(r"[一-鿿]", n))
        if is_cjk and len(n) < 2:
            return None, 0.0
        if not is_cjk and len(n) < 3:
            return None, 0.0
        best = difflib.get_close_matches(n, list(self._norm), n=1, cutoff=0.0)
        if not best:
            return None, 0.0
        ratio = difflib.SequenceMatcher(None, n, best[0]).ratio()
        cutoff = 0.66 if is_cjk else 0.8
        # 防止 “资深干员” 被识别成 “高级资深干员” 之类的误配
        if ratio >= cutoff and abs(len(n) - len(best[0])) <= max(1, len(best[0]) // 4):
            return self._norm[best[0]], ratio
        return None, ratio


def _norm(s: str) -> str:
    s = s.lower().replace("—", "-").replace("－", "-").replace("_", "-")
    return re.sub(r"[\s·.,:;'\"()（）\[\]【】]", "", s)


def detect_tags(texts: list[str], pools: dict[str, Pool]) -> tuple[str, list[int]]:
    """在所有服务器数据里匹配，返回 (服务器, tagId 列表)"""
    best_srv, best = None, []
    for srv, pool in pools.items():
        found = []
        for t in texts:
            tid, _ = pool.match_text(t)
            if tid is not None and tid not in found:
                found.append(tid)
        if len(found) > len(best):
            best_srv, best = srv, found
    return best_srv or next(iter(pools)), best


# ---------------------------------------------------------------- combos
def calc(pool: Pool, tag_ids: list[int]) -> list[dict]:
    """返回所有 1~3 tag 组合的结果，按保底星级排序"""
    results = []
    tag_ids = list(dict.fromkeys(tag_ids))
    for r in (1, 2, 3):
        for combo in itertools.combinations(tag_ids, r):
            cs = set(combo)
            if ROBOT_ID in cs:
                ops = [o for o in pool.ops if cs <= o["tags"] and o["rarity"] == 1]
                if ops:
                    results.append({"tags": combo, "min": 1, "max": 1, "ops": ops, "robot": True})
                continue
            if STARTER_ID in cs:
                continue
            ops = [
                o for o in pool.ops
                if cs <= o["tags"] and 3 <= o["rarity"] <= 6
                and (o["rarity"] < 6 or TOP_ID in cs)
            ]
            if not ops:
                continue
            ops.sort(key=lambda o: -o["rarity"])
            rs = [o["rarity"] for o in ops]
            results.append({"tags": combo, "min": min(rs), "max": max(rs), "ops": ops, "robot": False})

    # 去冗余：多加一个 tag 但结果完全相同的组合不显示；小车只保留单 tag 那条
    kept = []
    for x in sorted(results, key=lambda x: len(x["tags"])):
        sig = (x["min"], frozenset(o["name"] for o in x["ops"]))
        redundant = any(
            set(y["tags"]) < set(x["tags"])
            and (y["robot"] and x["robot"]
                 or (y["min"], frozenset(o["name"] for o in y["ops"])) == sig)
            for y in kept
        )
        if not redundant:
            kept.append(x)

    def key(x):
        lvl = 4.5 if x["robot"] else x["min"]  # 小车排在 4 星和 5 星之间
        return (-lvl, len(x["ops"]), len(x["tags"]))

    kept.sort(key=key)
    return kept


def verdict(results: list[dict]) -> tuple[str, int]:
    """返回 (等级key, 星级)：six/five/four/robot/three/none"""
    if not results:
        return "none", 0
    mins = [r["min"] for r in results if not r["robot"]]
    top = max(mins) if mins else 3
    if top >= 6:
        return "six", 6
    if top == 5:
        return "five", 5
    if top == 4:
        return "four", 4
    if any(r["robot"] for r in results):
        return "robot", 1
    return "three", 3
