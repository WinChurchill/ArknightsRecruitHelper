"""明日方舟 公开招募助手 / Arknights Recruitment Helper

用法:
  app.py                 打开主窗口
  app.py --background    托盘后台待命，游戏启动时自动工作（开机自启用）
  app.py --with-game     启动鹰角启动器，游戏关闭后自动退出
  app.py --setup         首次设置向导
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import logging
import re
import threading
import time
import tkinter as tk
from tkinter import filedialog

import winutil as w

w.set_dpi_aware()  # 必须在 Tk 之前

import recruit_core as rc  # noqa: E402
import ocr_engine as oe  # noqa: E402
from ocr_engine import OCR, Scan  # noqa: E402
from gamecard import BracketLayer, GameCard  # noqa: E402
from overlay import (ACCENT, BG, CHIP, CN, EN, LINE, PANEL, ROW, STAR, SUB, TXT, WARN,  # noqa: E402
                     Panel, ResultView, px)

HERE = rc.USER_DIR  # 用户数据目录（exe 版在 %APPDATA%）
os.makedirs(HERE, exist_ok=True)
CONFIG_PATH = os.path.join(HERE, "config.json")
ASSETS = os.path.join(HERE, "assets")
# 计划任务以管理员执行的脚本/图标：exe 版放在 Program Files（只有管理员能改）
SCRIPTS_DIR = os.path.join(w.INSTALL_DIR, "assets") if w.FROZEN else ASSETS
PAUSED_FLAG = os.path.join(HERE, "paused.flag")  # “完全退出”标记：看门狗不再拉起，直到下次登录
LOG_PATH = os.path.join(HERE, "log.txt")
VERSION = "1.1.0"
PORT = 47391
HOTKEY_SCAN, HOTKEY_OVERLAY = "f8", "f9"
TICK_MS = 400
log = logging.getLogger("ark")
DIFF_T = 0.3  # 缩略图变化阈值
FAST_HIDE_T = 6.0  # 大于它视为离开了公招界面（实测：选 tag≈0.4，关对话框/切界面≈37~88）

TEXT = {
    "zh": {
        "app": "公招助手", "panel_title": "公开招募 · 分析",
        "pick": "点击自动选择 ›", "pick_hint": "点击组合 → 自动勾选 tag 并设置时间",
        "need_admin": "⚠ 游戏以管理员运行，自动点选需要本工具也以管理员运行 —— 点此重启",
        "applying": "正在为你选择 tag …", "applied": "已选择：{tags}  ·  {time}",
        "apply_fail": "自动选择未完全成功，请检查游戏内的 tag 和时间",
        "apply_stopped": "已停止自动选择：你移动了鼠标或切换了窗口（安全保护）",
        "v_six": "高级资深干员", "v_six_s": "选「高级资深干员」，9 小时必出六星",
        "v_five": "保底五星", "v_five_s": "{tags}",
        "v_four": "保底四星", "v_four_s": "{tags}",
        "v_robot": "小车", "v_robot_s": "只选「支援机械」，时间 3:50 必出一星小车",
        "v_three": "只能三星", "v_three_s": "建议刷新 tag；不刷就直接 9 小时",
        "empty3": "没有保底四星以上的组合。",
        "wait_game": "等待游戏启动…", "wait_recruit": "打开公开招募的 tag 选择界面即可",
        "game_on": "游戏已连接", "game_off": "未检测到游戏", "admin_on": "管理员", "admin_off": "非管理员",
        "manual": "手动选择 tag", "settings": "设置", "scan": "识别 (F8)",
        "loading_ocr": "正在加载 OCR…", "scan_none": "没有识别到公招 tag",
        "found": "识别到 {n} 个 tag · {srv} · {t:.1f}s",
        "srv_cn": "国服", "srv_en": "国际服",
        # settings
        "s_lang": "界面语言", "s_server": "服务器", "s_auto": "自动",
        "s_display": "显示", "s_overlay": "游戏内叠加层 (F9)", "s_watch": "自动识别", "s_show3": "显示保底三星的组合",
        "s_start": "启动方式", "st_manual": "手动打开", "st_logon": "开机后台待命（推荐）",
        "st_with_game": "随游戏启动（桌面快捷方式）",
        "st_desc": "后台待命：开机后在托盘静默等待，检测到游戏就自动工作，几乎不占资源。\n"
                   "随游戏启动：用新的桌面快捷方式「明日方舟 + 公招助手」一起启动，游戏关闭后自动退出。",
        "s_on_exit": "游戏关闭后", "ex_quit": "退出助手", "ex_stay": "继续后台等待",
        "s_area": "识别范围", "area_auto": "自动（游戏窗口）", "area_pick": "框选区域（模拟器）",
        "s_data": "干员数据", "data_update": "立即更新", "data_info": "国服 {cn} 人 · 国际服 {en} 人 · 上次检查 {t}",
        "s_launcher": "鹰角启动器", "browse": "浏览…",
        "s_remove": "移除自启动和快捷方式",
        "need_admin_short": "⚠ 以管理员运行才能自动点选（点此）", "card_label": "招募建议",
        "ops_more": "等 {n} 名", "more_combos": "还有 {n} 个", "s_style": "结果显示", "style_card": "嵌入公招界面", "style_panel": "侧边面板",
        "s_update": "数据更新时机", "up_game": "游戏启动时", "up_6h": "每 6 小时", "up_manual": "仅手动",
        "region_tip": "拖动框选游戏画面（模拟器窗口），Esc 取消",
        "updating": "正在更新数据…", "updated": "数据已更新", "uptodate": "数据已是最新",
        "update_fail": "更新失败：{e}",
        "applied_startup": "启动方式已保存", "startup_fail": "设置启动方式失败（需要管理员权限）",
        # tray
        "t_show": "打开主窗口", "t_overlay": "叠加层", "t_quit": "完全退出（下次开机再启动）",
        "t_sleep": "关闭（下次打开游戏时自动出现）",
        # wizard
        "w_title": "欢迎使用 公招助手", "w_sub": "进到公开招募界面，助手会直接在游戏画面上标出该选的 tag。",
        "w_shortcut": "在桌面创建「公招助手」快捷方式", "w_go": "开始使用",
        "w_admin": "完成时会请求一次管理员权限（用于自启动和自动点选，之后不再询问）。",
        "hotkeys": "F8 立即识别 · F9 显示/隐藏叠加层",
        "w_steps": "①  在游戏里打开「公开招募」，点开一个空的招募位\n"
                   "②  界面下方会出现「招募建议」，告诉你能不能出好干员\n"
                   "③  点一下建议，助手自动帮你选好 tag 和时间，你只要点确认",
        "w_install": "安装并开始使用", "w_start": "开始使用", "w_installing": "正在安装，请稍候…",
        "w_more": "更多选项", "w_auto": "之后开机会自动在后台待命，什么都不用管。",
        "u_btn": "卸载公招助手", "u_confirm": "确定要卸载公招助手吗？\n会删除程序、设置和所有快捷方式。",
    },
    "en": {
        "app": "Recruit Helper", "panel_title": "Recruitment",
        "pick": "Click to select ›", "pick_hint": "Click a combo → tags & timer set automatically",
        "need_admin": "⚠ The game runs as admin; auto-select needs this tool elevated too — click to restart",
        "applying": "Selecting tags…", "applied": "Selected: {tags}  ·  {time}",
        "apply_fail": "Auto-select didn't fully succeed — please check the tags and timer in game",
        "apply_stopped": "Auto-select stopped: you moved the mouse or switched windows (safety)",
        "v_six": "Top Operator", "v_six_s": "Pick Top Operator, 9h → guaranteed 6★",
        "v_five": "Guaranteed 5★", "v_five_s": "{tags}",
        "v_four": "Guaranteed 4★", "v_four_s": "{tags}",
        "v_robot": "Robot", "v_robot_s": "Pick only Robot at 3:50 → guaranteed 1★ robot",
        "v_three": "3★ only", "v_three_s": "Refresh the tags, or just run 9h",
        "empty3": "No combo guarantees 4★ or better.",
        "wait_game": "Waiting for the game…", "wait_recruit": "Open the Recruit tag screen",
        "game_on": "Game connected", "game_off": "Game not found", "admin_on": "Admin", "admin_off": "Not admin",
        "manual": "Pick tags manually", "settings": "Settings", "scan": "Scan (F8)",
        "loading_ocr": "Loading OCR…", "scan_none": "No recruitment tags found",
        "found": "{n} tags · {srv} · {t:.1f}s",
        "srv_cn": "CN", "srv_en": "Global",
        "s_lang": "Language", "s_server": "Server", "s_auto": "Auto",
        "s_display": "Display", "s_overlay": "In-game overlay (F9)", "s_watch": "Auto scan", "s_show3": "Show 3★ combos",
        "s_start": "Startup", "st_manual": "Manual", "st_logon": "Wait in background (recommended)",
        "st_with_game": "Launch with game (desktop shortcut)",
        "st_desc": "Background: sits in the tray after login and activates when the game opens — near-zero cost.\n"
                   "With game: a new desktop shortcut starts the game and this helper together; it exits with the game.",
        "s_on_exit": "When the game closes", "ex_quit": "Quit helper", "ex_stay": "Keep waiting",
        "s_area": "Scan area", "area_auto": "Auto (game window)", "area_pick": "Select area (emulator)",
        "s_data": "Operator data", "data_update": "Update now", "data_info": "CN {cn} · Global {en} · checked {t}",
        "s_launcher": "Hypergryph launcher", "browse": "Browse…",
        "s_remove": "Remove autostart & shortcuts",
        "need_admin_short": "⚠ Run as admin to auto-select (click)", "card_label": "Advice",
        "ops_more": "+{n} more", "more_combos": "{n} more", "s_style": "Result display", "style_card": "Inside recruit dialog", "style_panel": "Side panel",
        "s_update": "Check for new data", "up_game": "When game starts", "up_6h": "Every 6h", "up_manual": "Manual only",
        "region_tip": "Drag to select the game area (emulator), Esc to cancel",
        "updating": "Updating data…", "updated": "Data updated", "uptodate": "Data is up to date",
        "update_fail": "Update failed: {e}",
        "applied_startup": "Startup mode saved", "startup_fail": "Failed to set startup mode (admin needed)",
        "t_show": "Open window", "t_overlay": "Overlay", "t_quit": "Quit completely (until next sign-in)",
        "t_sleep": "Close (comes back next time the game opens)",
        "w_title": "Welcome to Recruit Helper", "w_sub": "Open the Recruit screen and the helper marks the tags to pick right on the game.",
        "w_shortcut": "Create a desktop shortcut", "w_go": "Get started",
        "w_admin": "You'll be asked for admin once (for autostart and auto-select); never again after.",
        "hotkeys": "F8 scan now · F9 toggle overlay",
        "w_steps": "1.  In the game, open Recruitment and tap an empty slot\n"
                   "2.  An 'Advice' row appears under the dialog and tells you if a good operator is possible\n"
                   "3.  Click the advice: tags and timer are set for you. Just press confirm",
        "w_install": "Install & start", "w_start": "Get started", "w_installing": "Installing, please wait…",
        "w_more": "More options", "w_auto": "It will quietly start with Windows from now on. Nothing else to do.",
        "u_btn": "Uninstall", "u_confirm": "Uninstall Recruit Helper?\nThis removes the program, its settings and all shortcuts.",
    },
}


import i18n  # noqa: E402

i18n.install(TEXT)
LANG_OPTIONS = [("zh", "中文"), ("en", "English"), ("ja", "日本語"), ("ko", "한국어")]
SERVERS = ("cn", "en", "jp", "kr")
TITLE_LANG = {"明日方舟": "zh", "Arknights": "zh", "アークナイツ": "ja", "명일방주": "ko"}


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return {}


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
    except Exception:  # noqa: BLE001
        pass


# ====================================================================== startup / install helpers
def ensure_assets():
    """生成图标和隐藏启动脚本"""
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    ico = os.path.join(SCRIPTS_DIR, "icon.ico")
    if not os.path.exists(ico):
        make_icon(256).save(ico, sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])
    vbs = os.path.join(SCRIPTS_DIR, "launch.vbs")
    with open(vbs, "w", encoding="utf-16", newline="") as f:
        f.write('CreateObject("WScript.Shell").Run "schtasks /run /tn ' + w.TASK_PREFIX
                + '" & WScript.Arguments(0), 0, False\r\n')
    return ico, vbs


def make_icon(size=64):
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = size
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s // 6, fill=(27, 27, 29, 255))
    d.polygon([(s * .5, s * .16), (s * .84, s * .5), (s * .5, s * .84), (s * .16, s * .5)], fill=(0, 153, 220, 255))
    d.polygon([(s * .5, s * .33), (s * .67, s * .5), (s * .5, s * .67), (s * .33, s * .5)], fill=(242, 242, 242, 255))
    d.rectangle([0, s - s // 14, s, s], fill=(255, 201, 60, 255))
    return im


def _lnk_names():
    return [os.path.join(w.desktop_dir(), "公招助手.lnk"),
            os.path.join(w.desktop_dir(), "明日方舟 + 公招助手.lnk"),
            os.path.join(w.start_menu_dir(), "公招助手.lnk")]


def apply_startup(mode: str, shortcut: bool, cfg: dict, exe: str | None = None) -> bool:
    """创建/删除计划任务与快捷方式。需要管理员。exe=安装后的程序路径（exe 版）"""
    ico, vbs = ensure_assets()
    ok = w.create_task("Open", "", exe=exe)
    if mode == "logon":
        # 登录时启动后台待命；另有看门狗每 3 分钟检查一次，进程不在就拉起（完全退出后不拉起）
        ok &= w.create_task("Logon", "--background --logon", trigger="logon", exe=exe)
        if w.FROZEN:
            ok &= w.create_task("Watch", "", trigger="watch", exe=exe,
                                command=("wscript.exe", f'//B //Nologo "{write_watchdog(exe or sys.executable)}"'))
    else:
        w.delete_task("Logon")
        w.delete_task("Watch")
    desk_lnk, game_lnk, menu_lnk = _lnk_names()
    if mode == "with_game":
        ok &= w.create_task("Game", "--with-game", exe=exe)
        icon = ico
        appdata_icon = os.path.join(os.environ.get("APPDATA", ""), "Hypergryph")
        if os.path.isdir(appdata_icon):
            for root, _, files in os.walk(appdata_icon):
                if "arknights.ico" in files:
                    icon = os.path.join(root, "arknights.ico")
                    break
        w.create_shortcut(game_lnk, "wscript.exe", f'"{vbs}" Game', icon, HERE)
    else:
        w.delete_task("Game")
        if os.path.exists(game_lnk):
            os.remove(game_lnk)
    # 开始菜单总是创建；桌面按选择
    w.create_shortcut(menu_lnk, "wscript.exe", f'"{vbs}" Open', ico, HERE)
    if shortcut:
        w.create_shortcut(desk_lnk, "wscript.exe", f'"{vbs}" Open', ico, HERE)
    elif os.path.exists(desk_lnk):
        os.remove(desk_lnk)
    return ok


def write_watchdog(exe: str) -> str:
    """看门狗脚本：助手没在运行、且用户没有“完全退出”时，以后台模式启动它"""
    os.makedirs(SCRIPTS_DIR, exist_ok=True)
    path = os.path.join(SCRIPTS_DIR, "watchdog.vbs")
    name = os.path.basename(exe)
    vbs = [
        'Set fso = CreateObject("Scripting.FileSystemObject")',
        f'If fso.FileExists("{PAUSED_FLAG}") Then WScript.Quit',
        f'If Not fso.FileExists("{exe}") Then WScript.Quit',
        'Set wmi = GetObject("winmgmts:")',
        f'Set ps = wmi.ExecQuery("select ProcessId from Win32_Process where Name=\'{name}\'")',
        'If ps.Count > 0 Then WScript.Quit',
        f'CreateObject("WScript.Shell").Run """{exe}"" --background", 0, False',
    ]
    with open(path, "w", encoding="utf-16", newline="") as f:
        f.write("\r\n".join(vbs) + "\r\n")
    return path


def remove_startup():
    for n in ("Open", "Logon", "Game", "Watch"):
        w.delete_task(n)
    for p in _lnk_names():
        if os.path.exists(p):
            os.remove(p)


def stop_running_instance():
    """更新时：让已在运行的旧版本退出，以便覆盖 exe"""
    try:
        c = socket.create_connection(("127.0.0.1", PORT), timeout=2)
        c.sendall(b"quit")
        c.close()
        time.sleep(2.0)
    except OSError:
        pass


def install_self() -> str | None:
    """exe 版：把自己复制到固定的安装位置，返回安装后的路径。源码版返回 None"""
    if not w.FROZEN:
        return None
    if w.is_installed_copy():
        return w.INSTALLED_EXE
    import shutil
    stop_running_instance()
    os.makedirs(w.INSTALL_DIR, exist_ok=True)
    for _ in range(10):
        try:
            shutil.copy2(sys.executable, w.INSTALLED_EXE)
            break
        except PermissionError:
            time.sleep(1)
    # v1.0.0 装在用户目录（普通程序可改）：迁移后删除旧副本
    for old in w.safe_app_dirs([w.LEGACY_INSTALL_DIR]):
        if os.path.normcase(old) != os.path.normcase(w.INSTALL_DIR):
            shutil.rmtree(old, ignore_errors=True)
    return w.INSTALLED_EXE


ARGS_RE = re.compile(r"^--[A-Za-z0-9_-]+(=[A-Za-z0-9_.-]+)?(\s+--[A-Za-z0-9_-]+(=[A-Za-z0-9_.-]+)?)*$")


def launch_game(cfg: dict):
    """以管理员身份启动启动器前做安全检查：必须是官方厂商有效签名的 exe，参数只能是简单的 --开关"""
    exe = cfg.get("launcher") or (w.find_launcher() or (None,))[0]
    args = cfg.get("launcher_args") or "--game=arknights"
    if not ARGS_RE.match(args):
        log.warning("launcher args rejected: %r", args)
        args = "--game=arknights"
    ok, who = w.verify_signed(exe or "")
    if not ok:
        log.warning("refused to start launcher %r: %s", exe, who)
        return None
    try:
        return subprocess.Popen([exe] + args.split(), cwd=os.path.dirname(exe))
    except OSError as e:
        log.warning("launcher start failed: %s", e)
        return None


def uninstall_everything():
    """移除计划任务、快捷方式，并在退出后删除程序和数据"""
    remove_startup()
    if w.FROZEN:
        dirs = w.safe_app_dirs([w.INSTALL_DIR, rc.USER_DIR, w.LEGACY_INSTALL_DIR])
        if not dirs:
            return
        cmd = "ping 127.0.0.1 -n 4 >nul & " + " & ".join(f'rmdir /s /q "{d}"' for d in dirs)
        subprocess.Popen(["cmd", "/c", cmd], creationflags=w.CREATE_NO_WINDOW, cwd=os.environ.get("TEMP", "C:\\"))


# ====================================================================== App
class App:
    def __init__(self, root: tk.Tk, mode: str):
        self.root, self.mode = root, mode
        self.cfg = load_config()
        self.lang = self.cfg.get("lang", "zh")
        self.pools: dict[str, rc.Pool] = {}
        self.cur_server = "cn"
        self.manual_tags: list[int] = []
        self.ocr: OCR | None = None
        self.ocr_loading = False
        self.hwnd = None
        self.last_find = 0.0
        self.game_seen = False
        self.game_elevated = False
        self.admin = w.is_admin()
        self.area = None
        self.scan: Scan | None = None
        self.scan_area = None
        self.prev_thumb = None
        self.ocr_thumb = None
        self.busy = False
        self.applying = False
        self.miss_streak = 0
        self.next_ocr_at = 0.0
        self.sleeping = False      # 用户关闭：休眠到下一次游戏启动
        self.title_lang = None     # 游戏窗口标题提示的语言
        self.model_dl = set()      # 正在下载的日/韩模型
        self.sleep_hwnd = None
        self.hover = None
        self.panel_closed_sig = None
        self.model = None
        self.model_sig = None
        self.status_msg = ""
        self.launcher_proc = None
        self.started = time.time()
        self.tray = None
        self.settings_win = None
        self.own = set()

        self.load_pools()
        self._build_main()
        self.marks = BracketLayer(root)
        self.panel = Panel(root, self.tx, self.apply_combo, self.on_hover, self.close_panel,
                           self.restart_admin, self.on_panel_moved)
        self.card = GameCard(root, self.tx, self.apply_combo, self.on_hover, self.close_panel, self.restart_admin)
        self.own |= {w.hwnd_of(root), w.hwnd_of(self.panel.win), w.hwnd_of(self.card.win)}
        self._setup_hotkeys()
        self._single_instance_server()
        self._setup_tray()
        root.protocol("WM_DELETE_WINDOW", self.on_main_close)
        if mode in ("background", "with_game"):
            root.withdraw()
        if mode == "with_game":
            self.start_launcher()
        root.after(300, self.tick)
        root.after(8000, self._auto_update_tick)

    # ------------------------------------------------------------ helpers
    @property
    def tx(self):
        return TEXT[self.lang]

    def t(self, key, **kw):
        return self.tx[key].format(**kw)

    def setcfg(self, **kw):
        self.cfg.update(kw)
        save_config(self.cfg)

    def status(self, msg):
        self.status_msg = msg
        self.root.after(0, self._refresh_status)

    # ------------------------------------------------------------ data
    def load_pools(self):
        self.pools = {}
        for srv in SERVERS:
            try:
                self.pools[srv] = rc.Pool(srv)
            except FileNotFoundError:
                pass
        if not self.pools:
            self.update_data(force=True)

    def pools_for_scan(self, lang="zh"):
        """某个识别模型对应的服务器数据（中文模型 → 国服+国际服；日文 → 日服；韩文 → 韩服）"""
        mode = self.cfg.get("server", "auto")
        if mode in self.pools:
            return {mode: self.pools[mode]}
        return {k: v for k, v in self.pools.items() if k in oe.LANG_SERVERS[lang]}

    def ocr_langs(self):
        """本次识别要尝试的模型顺序：设置指定 > 窗口标题提示 > 上次成功的 > 其他"""
        mode = self.cfg.get("server", "auto")
        if mode in oe.SERVER_LANG:
            return [oe.SERVER_LANG[mode]]
        first = self.title_lang or self.cfg.get("last_ocr_lang", "zh")
        return [first] + [x for x in ("zh", "ja", "ko") if x != first]

    def ensure_model(self, lang):
        """后台下载日/韩识别模型（只下载一次，校验 SHA-256）"""
        if lang == "zh" or oe.model_ready(lang) or lang in self.model_dl:
            return
        self.model_dl.add(lang)
        name = self.t("lang_" + lang)
        mb = round(sum(v[1] for v in oe.MODELS[lang].values()) / 1e6)
        self.status(self.t("dl_model", lang=name, mb=mb))

        def work():
            try:
                oe.download_model(lang, log=lambda m: log.info(m))
                log.info("model ready: %s", lang)
                self.status(self.t("dl_done", lang=name))
                self.ocr_thumb = None  # 立即重新识别
            except Exception as e:  # noqa: BLE001
                log.warning("model download failed: %s %s", lang, e)
                self.status(self.t("dl_fail", lang=name, e=e))
            finally:
                self.model_dl.discard(lang)
        threading.Thread(target=work, daemon=True).start()

    def update_data(self, force=True, silent=False):
        if getattr(self, "_updating", False):
            return
        self._updating = True

        def work():
            try:
                changed = rc.update_data(log=(lambda s: None) if silent else self.status, force=force)
                if changed or not self.pools:
                    self.root.after(0, self._reload_after_update)
                    self.status(self.t("updated"))
                elif not silent:
                    self.status(self.t("uptodate"))
            except Exception as e:  # noqa: BLE001
                if not silent:
                    self.status(self.t("update_fail", e=e))
            finally:
                self._updating = False
        if not silent:
            self.status(self.t("updating"))
        threading.Thread(target=work, daemon=True).start()

    def _reload_after_update(self):
        self.load_pools()
        self.model_sig = None
        self.refresh_all()

    def _auto_update_tick(self):
        """“每 6 小时”模式的定时检查"""
        if self.cfg.get("update_when", "game_start") == "interval" and rc.auto_update_due():
            self.update_data(force=False, silent=True)
        self.root.after(3600 * 1000, self._auto_update_tick)

    def _update_on_game_start(self):
        if self.cfg.get("update_when", "game_start") == "game_start" and rc.auto_update_due(1800):
            self.update_data(force=False, silent=True)

    # ------------------------------------------------------------ game lifecycle
    def start_launcher(self):
        if w.find_game_hwnd():
            return
        self.launcher_proc = launch_game(self.cfg)

    def on_game_start(self):
        self.game_seen = True
        r = w.client_rect(self.hwnd)
        log.info("game started: %s %s", w.process_name(self.hwnd) or "?", r[2:] if r else "?")
        self.game_elevated = bool(w.process_is_elevated(self.hwnd))
        self.title_lang = TITLE_LANG.get(w.window_title(self.hwnd))
        if self.cfg.get("server", "auto") in ("jp", "kr"):
            self.ensure_model(oe.SERVER_LANG[self.cfg["server"]])
        elif self.title_lang in ("ja", "ko"):
            self.ensure_model(self.title_lang)  # 日服/韩服客户端：提前下载对应模型
        self.load_ocr()
        self._update_on_game_start()
        self._refresh_status()

    def on_game_exit(self):
        self.game_seen = False
        self.hwnd = None
        self.scan = None
        self.prev_thumb = self.ocr_thumb = None
        self.hide_overlay()
        self.ocr = None  # 释放 OCR 模型内存
        self.refresh_all()
        log.info("game closed")
        if self.mode == "with_game" or (self.mode == "background" and self.cfg.get("on_exit", "stay") == "quit"):
            self.quit("game closed")

    def load_ocr(self):
        if self.ocr or self.ocr_loading:
            return
        self.ocr_loading = True

        def work():
            try:
                self.ocr = OCR()
            except Exception as e:  # noqa: BLE001
                self.status(f"OCR: {e}")
            finally:
                self.ocr_loading = False
                self._refresh_status()
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ watch loop
    def tick(self):
        try:
            self._tick()
        except Exception as e:  # noqa: BLE001
            self.status(f"tick: {e}")
        self.root.after(TICK_MS, self.tick)

    def _tick(self):
        now = time.time()
        if not w.window_alive(self.hwnd):
            self.hwnd = None
            if now - self.last_find > 2:
                self.last_find = now
                self.hwnd = w.find_game_hwnd()
            if not self.hwnd:
                if self.game_seen:
                    self.on_game_exit()
                elif self.mode == "with_game" and now - self.started > 30:
                    if self.launcher_proc is None or self.launcher_proc.poll() is not None:
                        if now - self.started > 900 or self.launcher_proc is not None:
                            self.quit("launcher closed without game")
                if not self.cfg.get("region"):
                    return
        if self.sleeping:
            if self.hwnd and self.hwnd == self.sleep_hwnd:
                return                      # 还是关闭时那一局游戏：继续休眠
            if not self.hwnd:
                self.sleep_hwnd = None      # 游戏关了：下次再打开就唤醒
                return
            self.sleeping = False           # 新的一局游戏：唤醒
            log.info("wake: new game window")
        if self.hwnd and not self.game_seen:
            self.on_game_start()

        region = self.cfg.get("region")
        if region:
            area, active = region, True
            self.load_ocr()
        else:
            if w.is_minimized(self.hwnd):
                self.hide_overlay()
                return
            area = w.client_rect(self.hwnd)
            fg = w.foreground()
            active = fg == self.hwnd or fg in self.own
        if not area:
            return
        if not active:
            self.hide_overlay()
            return
        if area != self.area:
            resized = not self.area or area[2:] != self.area[2:]
            self.area = area
            if resized:
                self.prev_thumb = self.ocr_thumb = None
        self.update_overlay()

        if not self.cfg.get("watch", True) or self.busy or self.applying or not self.ocr:
            return
        img, _ = w.grab(area)
        thumb = img[::8, ::8].mean(axis=2)
        # 快速关闭：正在显示建议时，画面和识别时相比大变（关闭对话框/切界面）→ 立刻隐藏，不等 OCR。
        # 用的是本来就有的缩略图，零额外开销；选 tag 这类小变化（≈0.4）远低于阈值。
        if self.scan and self.ocr_thumb is not None and self.ocr_thumb.shape == thumb.shape \
                and abs(self.ocr_thumb - thumb).mean() >= FAST_HIDE_T:
            log.info("fast hide: screen changed")
            self.scan = None
            self.hover = None
            self.hide_overlay()
            self.refresh_all()
        stable = self.prev_thumb is not None and self.prev_thumb.shape == thumb.shape \
            and abs(self.prev_thumb - thumb).mean() < DIFF_T
        self.prev_thumb = thumb
        if not stable:
            return  # 画面在变（动画/切换中）：等它稳定
        change = abs(self.ocr_thumb - thumb).mean() \
            if self.ocr_thumb is not None and self.ocr_thumb.shape == thumb.shape else 999
        if change < DIFF_T:
            return  # 和上次识别时一样：不用再 OCR
        # 退避：非公招画面上的小变化（倒计时、粒子）不要反复 OCR；切换界面这种大变化立即识别
        if change < 4 and time.time() < self.next_ocr_at:
            return
        self.ocr_thumb = thumb
        self.run_ocr(img, list(area))

    def run_ocr(self, img, area, cb=None):
        self.busy = True

        def work():
            try:
                t0 = time.time()
                s = None
                for i, lang in enumerate(self.ocr_langs()):
                    if not self.ocr.available(lang):
                        if s is not None and s.looks_recruit and not s.tags:
                            self.root.after(0, lambda la=lang: self.ensure_model(la))  # 公招界面但读不出 tag
                        continue
                    r = self.ocr.scan(img, self.pools_for_scan(lang), lang)
                    if s is None or r.ok:
                        s = r
                    if r.ok:
                        if self.cfg.get("last_ocr_lang") != lang:
                            self.cfg["last_ocr_lang"] = lang
                            save_config(self.cfg)
                        break
                    if not r.looks_recruit:
                        break  # 不是公招界面：不用再试其他语言（省 CPU）
                dt = time.time() - t0
                self.root.after(0, lambda: (cb or self.on_scan)(s, area, dt))
            except Exception as e:  # noqa: BLE001
                self.status(f"OCR: {e}")
            finally:
                self.busy = False
        threading.Thread(target=work, daemon=True).start()

    def scan_now(self):
        """F8：强制识别（找不到游戏时截全屏）"""
        if not self.ocr:
            self.load_ocr()
            self.status(self.t("loading_ocr"))
            return
        if self.busy:
            return
        area = self.cfg.get("region") or (w.client_rect(self.hwnd) if self.hwnd else None)
        img, origin = w.grab(area)
        self.ocr_thumb = None
        self.run_ocr(img, [origin[0], origin[1], img.shape[1], img.shape[0]])

    def on_scan(self, s: Scan, area, dt):
        if not s.ok:
            self.miss_streak += 1
            self.next_ocr_at = time.time() + min(5.0, 0.5 * 2 ** self.miss_streak)
        else:
            self.miss_streak, self.next_ocr_at = 0, 0.0
        if not s.ok:
            if self.scan:
                self.scan = None
                self.hover = None
                self.hide_overlay()
                self.refresh_all()
            return
        new_tags = not self.scan or (self.scan.srv, set(self.scan.tags)) != (s.srv, set(s.tags))
        self.scan, self.scan_area = s, area
        self.cur_server = s.srv
        if new_tags:
            self.panel_closed_sig = None
            self.hover = None
            name = self.t("srv_" + s.srv)
            self.status_msg = self.t("found", n=len(s.tags), srv=name, t=dt)
        self.refresh_all()

    # ------------------------------------------------------------ model
    def current_tags(self):
        return list(self.scan.tags) if self.scan else list(self.manual_tags)

    def build_model(self, limit=None):
        pool = self.pools.get(self.cur_server)
        tags = self.current_tags()
        if not pool or not tags:
            return None
        res = rc.calc(pool, tags)
        level, star = rc.verdict(res)
        show3 = self.cfg.get("show3", False)
        combos = []
        for r in res:
            if not r["robot"] and r["min"] < 4 and not show3:
                continue
            combos.append({
                "tids": tuple(r["tags"]), "tags": [pool.tags[x] for x in r["tags"]],
                "min": 1 if r["robot"] else r["min"], "label": "1★" if r["robot"] else f"{r['min']}★",
                "ops": [(o["name"], o["rarity"]) for o in r["ops"]],
                "time": (3, 50) if r["robot"] else (9, 0),
            })
        best = next((c for c in combos if c["min"] == star), combos[0] if combos else None)
        tagstr = " + ".join(best["tags"]) if best else ""
        title, sub, tm = {
            "six": (self.t("v_six"), self.t("v_six_s"), "09:00"),
            "five": (self.t("v_five"), self.t("v_five_s", tags=tagstr), "09:00"),
            "four": (self.t("v_four"), self.t("v_four_s", tags=tagstr), "09:00"),
            "robot": (self.t("v_robot"), self.t("v_robot_s"), "03:50"),
            "three": (self.t("v_three"), self.t("v_three_s"), "09:00"),
        }.get(level, ("", "", None))
        return {"star": star, "title": title, "subtitle": sub, "time": tm, "level": level,
                "combos": combos[:limit] if limit else combos, "best": best, "empty": self.t("empty3")}

    # ------------------------------------------------------------ overlay
    def hide_overlay(self):
        self.marks.clear()
        self.panel.show(False)
        self.card.show(False)

    def overlay_allowed(self):
        return (self.cfg.get("overlay", True) and self.scan and self.scan.ok
                and self.panel_closed_sig != (self.scan.srv, frozenset(self.scan.tags)))

    def update_overlay(self, rerender=False):
        if not self.overlay_allowed() or not self.area:
            self.hide_overlay()
            return
        s = self.scan
        # 截图区域就是当前区域（游戏窗口可能被拖动过）
        ox, oy = self.area[0], self.area[1]
        model = self.model
        if model is None:
            self.hide_overlay()
            return
        busy = self.t("applying") if self.applying else None
        card_rect = self._card_rect(s, ox, oy) if self.cfg.get("panel_style", "card") == "card" else None
        if card_rect:  # 嵌入游戏：对话框下方（横）或侧边（竖）
            orient, x, y, cw, ch = card_rect
            sig = ("card", orient, id(model), int(cw), int(ch), self.applying, self.admin_ok(), self.lang)
            if rerender or sig != getattr(self, "_panel_sig", None):
                self._panel_sig = sig
                self.card.set_texts(self.tx)
                self.card.render(model, s.pitch, cw, ch, self.admin_ok(), busy, orient)
            self.card.place(x, y, cw, ch)
            self.card.show(True)
            self.panel.show(False)
        else:
            f = s.pitch * 0.30
            sig = ("panel", id(model), round(f), self.applying, self.admin_ok(), self.lang)
            if rerender or sig != getattr(self, "_panel_sig", None):
                self._panel_sig = sig
                self.panel.set_texts(self.tx)
                self.panel.render({**model, "combos": model["combos"][:5]}, f, self.admin_ok(), busy)
            self.card.show(False)
        combo = self.hover or model["best"]
        if combo:
            pts = [(tid, ox + s.centers[tid][0], oy + s.centers[tid][1]) for tid in combo["tids"] if tid in s.centers]
            self.marks.brackets(pts, s.pitch, STAR[combo["min"]], s.selected)
        else:
            self.marks.clear()
        if not card_rect:
            self._place_panel(s, ox, oy)
            self.panel.show(True)

    def _card_rect(self, s: Scan, ox, oy):
        """在游戏窗口内找卡片位置：对话框下方够高 → 横排；否则左右两侧够宽 → 竖排；都不行 → None（侧边面板）"""
        d = s.dialog()
        if not d or not self.area:
            return None
        p = s.pitch
        dl, dt, dr, db = d[0] + ox, d[1] + oy, d[2] + ox, d[3] + oy
        gx0, gy0 = self.area[0], self.area[1]
        gx1, gy1 = gx0 + self.area[2], gy0 + self.area[3]
        below = gy1 - db
        if below >= 1.45 * p:
            y0 = db + 0.12 * p
            return "h", dl, y0, dr - dl, min(1.85 * p, gy1 - 0.06 * p - y0)
        right, left = gx1 - dr, dl - gx0
        for space, side in sorted([(right, "r"), (left, "l")], reverse=True):
            if space >= 2.8 * p:
                cw = min(space - 0.25 * p, 4.4 * p)
                x = dr + 0.12 * p if side == "r" else dl - 0.12 * p - cw
                return "v", x, dt, cw, db - dt
        return None

    def _place_panel(self, s: Scan, ox, oy):
        W, H = self.panel.size()
        p = s.pitch
        d = s.dialog()
        if not d:
            return
        dl, dt, dr, db = d[0] + ox, d[1] + oy, d[2] + ox, d[3] + oy
        vs = self.marks.vs
        sx0, sy0, sx1, sy1 = vs["left"], vs["top"], vs["left"] + vs["width"], vs["top"] + vs["height"]
        gx0, gx1 = self.area[0], self.area[0] + self.area[2]
        off = self.cfg.get("panel_offset")
        if off:
            x, y = dr + off[0] * p, dt + off[1] * p
        else:
            y = dt
            if dr + 0.3 * p + W <= gx1 - 0.2 * p:
                x = dr + 0.3 * p                 # 游戏内、公招框右侧
            elif gx1 + 8 + W <= sx1:
                x = gx1 + 8                      # 游戏窗口右边外侧
            elif gx0 - 8 - W >= sx0:
                x = gx0 - 8 - W                  # 游戏窗口左边外侧
            else:
                x = max(sx0, dl - 0.3 * p - W)   # 公招框左侧
        x = min(max(x, sx0), sx1 - W)
        y = min(max(y, sy0), sy1 - H)
        self.panel.place(x, y)

    def on_panel_moved(self, x, y):
        s = self.scan
        if not s or not self.area:
            return
        d = s.dialog()
        dr, dt = d[2] + self.area[0], d[1] + self.area[1]
        self.setcfg(panel_offset=[(x - dr) / s.pitch, (y - dt) / s.pitch])

    def on_hover(self, combo):
        self.hover = combo
        if self.scan:
            self.update_overlay()

    def close_panel(self):
        if self.scan:
            self.panel_closed_sig = (self.scan.srv, frozenset(self.scan.tags))
        self.hide_overlay()

    def toggle_overlay(self):
        self.setcfg(overlay=not self.cfg.get("overlay", True))
        self.panel_closed_sig = None
        self.update_overlay()
        self._sync_tray()

    # ------------------------------------------------------------ auto-select
    def admin_ok(self):
        return self.admin or not self.game_elevated

    def restart_admin(self):
        if w.relaunch_as_admin(["--background"] if self.mode != "normal" else []):
            self.quit("restart as admin")

    def apply_combo(self, combo):
        s = self.scan
        if not s or not self.hwnd or self.applying:
            return  # 没有游戏画面（手动模式）：只显示结果
        if not self.admin_ok():
            self.restart_admin()
            return
        self.applying = True
        self.hover = None
        self.update_overlay()
        target, ttime = set(combo["tids"]), combo["time"]
        area = list(self.area)

        def clicks_for(sc: Scan):
            ox, oy = area[0], area[1]
            pts = []
            for tid in list(sc.selected - target) + list(target - sc.selected):  # 先取消，再选择
                if tid in sc.centers:
                    x, y = sc.centers[tid]
                    pts.append((ox + x, oy + y))
            arr = sc.arrows()
            if arr and ttime:
                h, m = sc.time or (1, 0)
                H, M = ttime
                mu, md = (M // 10 - m // 10) % 6, (m // 10 - M // 10) % 6
                key, n = ("m_up", mu) if mu <= md else ("m_down", md)
                pts += [(ox + arr[key][0], oy + arr[key][1])] * n
                hu, hd = (H - h) % 9, (h - H) % 9
                key, n = ("h_up", hu) if hu <= hd else ("h_down", hd)
                pts += [(ox + arr[key][0], oy + arr[key][1])] * n
            return pts

        def done_ok(sc: Scan):
            return sc.ok and sc.selected == target and (sc.time is None or sc.time == ttime)

        stopped = {}

        def work():
            ok = False
            try:
                sc = s
                for _ in range(2):
                    pts = clicks_for(sc)
                    if pts:
                        w.click_sequence(self.hwnd, pts, bounds=area)
                    time.sleep(0.45)
                    img, _ = w.grab(area)
                    sc = self.ocr.scan(img, {s.srv: self.pools[s.srv]}, oe.SERVER_LANG[s.srv])
                    if done_ok(sc):
                        ok = True
                        break
                self.root.after(0, lambda: self.on_scan(sc, area, 0))
            except w.ClickAborted as e:
                log.info("auto-select stopped: %s", e)
                stopped["why"] = str(e)
            except Exception as e:  # noqa: BLE001
                log.exception("apply failed")
                self.status(f"apply: {e}")
            finally:
                def fin():
                    self.applying = False
                    self.prev_thumb = self.ocr_thumb = None
                    tm = f"{ttime[0]:02d}:{ttime[1]:02d}"
                    self.status(self.t("apply_stopped") if stopped.get("why") else
                                self.t("applied", tags=" + ".join(combo["tags"]), time=tm) if ok
                                else self.t("apply_fail"))
                    self.update_overlay(rerender=True)
                self.root.after(0, fin)
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------------ main window
    def _build_main(self):
        r = self.root
        for c in r.winfo_children():
            if not isinstance(c, tk.Toplevel):
                c.destroy()
        r.title(self.t("app"))
        r.configure(bg=BG)
        try:
            from PIL import ImageTk
            self._icon = ImageTk.PhotoImage(make_icon(64))
            r.iconphoto(True, self._icon)
        except Exception:  # noqa: BLE001
            pass
        r.geometry(self.cfg.get("geometry", "440x640"))
        r.minsize(400, 360)
        self.MW = 420

        head = tk.Canvas(r, height=52, bg=BG, highlightthickness=0)
        head.pack(fill="x")
        head.create_rectangle(0, 0, 4, 52, fill=ACCENT, outline="")
        head.create_text(16, 18, text=self.t("app"), anchor="w", fill=TXT, font=(CN, px(17), "bold"))
        head.create_text(16, 38, text="ARKNIGHTS · RECRUITMENT", anchor="w", fill=SUB, font=(EN, px(10)))
        self.head = head
        gear = tk.Label(r, text="⚙", bg=BG, fg=SUB, font=(CN, px(18)), cursor="hand2")
        gear.place(relx=1.0, x=-14, y=12, anchor="ne")
        gear.bind("<Button-1>", lambda e: self.open_settings())
        gear.bind("<Enter>", lambda e: gear.configure(fg=TXT))
        gear.bind("<Leave>", lambda e: gear.configure(fg=SUB))
        scan = tk.Label(r, text=self.t("scan"), bg=CHIP, fg=TXT, font=(CN, px(11)), cursor="hand2", padx=10, pady=3)
        scan.place(relx=1.0, x=-50, y=15, anchor="ne")
        scan.bind("<Button-1>", lambda e: self.scan_now())

        self.chips = tk.Frame(r, bg=BG)
        self.chips.pack(fill="x", padx=12, pady=(0, 8))

        # 可滚动结果区
        holder = tk.Frame(r, bg=PANEL)
        holder.pack(fill="both", expand=True, padx=12)
        self.mcv = tk.Canvas(holder, bg=PANEL, highlightthickness=0)
        self.mcv.pack(fill="both", expand=True)
        self.mview = ResultView(self.mcv, self.MW, 13, self.apply_combo, lambda c: self.on_hover(c), self.tx)
        self._mwin = self.mcv.create_window(0, 0, window=self.mview, anchor="nw")
        self.mview.bind("<Configure>", lambda e: self.mcv.configure(scrollregion=self.mcv.bbox("all")))
        self.mcv.bind("<Configure>", self._main_resize)
        r.bind_all("<MouseWheel>", lambda e: self.mcv.yview_scroll(int(-e.delta / 120), "units"))

        # 手动选择
        self.manual_open = False
        tog = tk.Label(r, text="▸ " + self.t("manual"), bg=BG, fg=SUB, font=(CN, px(12)), cursor="hand2", anchor="w")
        tog.pack(fill="x", padx=14, pady=(8, 2))
        self.manual_frame = tk.Frame(r, bg=BG)

        def toggle(_=None):
            self.manual_open = not self.manual_open
            tog.configure(text=("▾ " if self.manual_open else "▸ ") + self.t("manual"))
            if self.manual_open:
                self.manual_frame.pack(fill="x", padx=12, before=self.statusbar)
            else:
                self.manual_frame.pack_forget()
        tog.bind("<Button-1>", toggle)

        self.statusbar = tk.Label(r, text="", bg=BG, fg=SUB, font=(CN, px(10)), anchor="w")
        self.statusbar.pack(fill="x", padx=14, pady=(4, 8), side="bottom")
        self.refresh_all()

    def _main_resize(self, e):
        self.MW = e.width
        self.mcv.itemconfigure(self._mwin, width=e.width)
        if self.mview.W != e.width:
            self.mview.set_size(e.width, 13)
            self.mview.render(self.model)

    def _render_manual(self):
        fr = self.manual_frame
        for c in fr.winfo_children():
            c.destroy()
        pool = self.pools.get(self.cur_server)
        if not pool:
            return
        cur = set(self.current_tags())
        for i, (tid, name) in enumerate(sorted(pool.tags.items())):
            on = tid in cur
            b = tk.Label(fr, text=name, bg=ACCENT if on else CHIP, fg=TXT, font=(CN, px(11), "bold" if on else ""),
                         pady=4, cursor="hand2")
            b.grid(row=i // 5, column=i % 5, sticky="nsew", padx=1, pady=1)
            b.bind("<Button-1>", lambda e, t=tid: self.toggle_manual(t))
        for c in range(5):
            fr.grid_columnconfigure(c, weight=1)

    def toggle_manual(self, tid):
        if self.scan:  # 手动修正 OCR 结果：转成手动模式
            self.manual_tags = list(self.scan.tags)
            self.scan = None
            self.hide_overlay()
        if tid in self.manual_tags:
            self.manual_tags.remove(tid)
        else:
            self.manual_tags.append(tid)
        self.refresh_all()

    def _refresh_status(self):
        if not hasattr(self, "chips"):
            return
        for c in self.chips.winfo_children():
            c.destroy()

        def chip(text, on):
            tk.Label(self.chips, text=("● " if on else "○ ") + text, bg=CHIP if on else ROW,
                     fg=TXT if on else SUB, font=(CN, px(10)), padx=8, pady=2).pack(side="left", padx=(0, 6))
        chip(self.t("game_on") if self.hwnd else self.t("game_off"), bool(self.hwnd))
        if self.hwnd and self.game_elevated:
            chip(self.t("admin_on") if self.admin else self.t("admin_off"), self.admin)
        if self.ocr_loading:
            chip(self.t("loading_ocr"), False)
        self.statusbar.configure(text=self.status_msg or self.t("hotkeys"))

    def refresh_all(self):
        self.model = self.build_model()
        if hasattr(self, "mview"):
            self.mview.tx = self.tx
            if self.model:
                self.mview.render(self.model)
            else:
                self.mview.render(None)
                for c in self.mview.winfo_children():
                    c.destroy()
                msg = self.t("wait_recruit") if self.hwnd else self.t("wait_game")
                tk.Label(self.mview, text=msg, bg=PANEL, fg=SUB, font=(CN, px(13)), pady=30,
                         width=40).pack(fill="x")
            self._render_manual()
            self._refresh_status()
        if hasattr(self, "panel"):
            self.update_overlay(rerender=True)

    def show_main(self):
        if self.sleeping:
            log.info("wake: window opened")
        self.sleeping = False
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def on_main_close(self):
        self.setcfg(geometry=self.root.geometry())
        if self.cfg.get("startup", "manual") == "manual" and self.mode == "normal":
            self.quit("window closed (manual mode)")
        else:
            self.go_sleep()  # 关窗口 = 休眠，下次打开游戏自动出现

    def go_sleep(self):
        log.info("sleep until next game launch")
        self.sleeping = True
        self.sleep_hwnd = self.hwnd
        self.root.withdraw()
        self.hide_overlay()
        self.scan = None
        self.ocr = None  # 释放 OCR，醒来时再加载
        self.game_seen = False

    def full_quit(self):
        """完全退出：看门狗不再拉起，直到下次登录 Windows 或手动打开"""
        try:
            open(PAUSED_FLAG, "w").close()
        except OSError:
            pass
        self.quit("full quit from tray")

    # ------------------------------------------------------------ settings
    def open_settings(self):
        if self.settings_win and self.settings_win.winfo_exists():
            self.settings_win.lift()
            return
        s = tk.Toplevel(self.root)
        self.settings_win = s
        s.title(self.t("settings"))
        s.configure(bg=BG)
        s.resizable(False, False)
        s.transient(self.root)
        body = tk.Frame(s, bg=BG)
        body.pack(fill="both", padx=16, pady=12)
        self._settings_body(body)
        s.update_idletasks()
        self.own.add(w.hwnd_of(s))

    def _section(self, parent, title):
        tk.Label(parent, text=title, bg=BG, fg=SUB, font=(CN, px(11), "bold"), anchor="w").pack(fill="x", pady=(10, 3))
        tk.Frame(parent, bg=LINE, height=1).pack(fill="x", pady=(0, 6))

    def _seg(self, parent, options, value, on_change):
        """游戏风格分段按钮"""
        fr = tk.Frame(parent, bg=BG)
        fr.pack(fill="x")
        var = tk.StringVar(value=value)
        for val, label in options:
            tk.Radiobutton(fr, text=label, value=val, variable=var, indicatoron=False, bg=CHIP, fg=TXT,
                           selectcolor=ACCENT, activebackground="#555", activeforeground=TXT, relief="flat",
                           bd=0, font=(CN, px(11)), padx=10, pady=4, cursor="hand2",
                           command=lambda: on_change(var.get())).pack(side="left", padx=(0, 2))
        return var

    def _check(self, parent, text, key, default, after=None):
        var = tk.BooleanVar(value=self.cfg.get(key, default))

        def ch():
            self.setcfg(**{key: var.get()})
            if after:
                after()
        tk.Checkbutton(parent, text=text, variable=var, command=ch, bg=BG, fg=TXT, selectcolor=CHIP,
                       activebackground=BG, activeforeground=TXT, font=(CN, px(11)), anchor="w",
                       cursor="hand2").pack(fill="x")

    def _settings_body(self, b):
        self._section(b, self.t("s_lang"))
        self._seg(b, LANG_OPTIONS, self.lang, self.set_lang)
        self._section(b, self.t("s_server"))
        self._seg(b, [("auto", self.t("s_auto"))] + [(k, self.t("srv_" + k)) for k in SERVERS],
                  self.cfg.get("server", "auto"), lambda v: (self.setcfg(server=v), self.refresh_all()))
        self._section(b, self.t("s_display"))
        self._check(b, self.t("s_overlay"), "overlay", True, lambda: (self.update_overlay(), self._sync_tray()))
        tk.Label(b, text=self.t("s_style"), bg=BG, fg=TXT, font=(CN, px(11)), anchor="w").pack(fill="x", pady=(4, 0))
        self._seg(b, [("card", self.t("style_card")), ("panel", self.t("style_panel"))],
                  self.cfg.get("panel_style", "card"),
                  lambda v: (self.setcfg(panel_style=v), self.update_overlay(rerender=True)))
        self._check(b, self.t("s_watch"), "watch", True)
        self._check(b, self.t("s_show3"), "show3", False, self.refresh_all)

        self._section(b, self.t("s_start"))
        fr = tk.Frame(b, bg=BG)
        fr.pack(fill="x")
        var = tk.StringVar(value=self.cfg.get("startup", "manual"))
        for val in ("logon", "with_game", "manual"):
            tk.Radiobutton(fr, text=self.t("st_" + val), value=val, variable=var, bg=BG, fg=TXT, selectcolor=CHIP,
                           activebackground=BG, activeforeground=TXT, font=(CN, px(11)), anchor="w",
                           command=lambda: self.set_startup(var.get())).pack(fill="x")
        tk.Label(b, text=self.t("st_desc"), bg=BG, fg=SUB, font=(CN, px(10)), justify="left", wraplength=380,
                 anchor="w").pack(fill="x", pady=(2, 4))
        tk.Label(b, text=self.t("s_on_exit"), bg=BG, fg=TXT, font=(CN, px(11)), anchor="w").pack(fill="x")
        self._seg(b, [("stay", self.t("ex_stay")), ("quit", self.t("ex_quit"))], self.cfg.get("on_exit", "stay"),
                  lambda v: self.setcfg(on_exit=v))

        self._section(b, self.t("s_launcher"))
        lf = tk.Frame(b, bg=BG)
        lf.pack(fill="x")
        lv = tk.StringVar(value=self.cfg.get("launcher") or (w.find_launcher() or ("", ""))[0])
        tk.Entry(lf, textvariable=lv, bg=CHIP, fg=TXT, insertbackground=TXT, relief="flat",
                 font=(CN, px(10))).pack(side="left", fill="x", expand=True, ipady=3)

        def browse():
            p = filedialog.askopenfilename(filetypes=[("Launcher", "*.exe")])
            if p:
                lv.set(p)
                self.setcfg(launcher=p)
        tk.Button(lf, text=self.t("browse"), command=browse, bg=CHIP, fg=TXT, relief="flat",
                  font=(CN, px(10))).pack(side="left", padx=(4, 0))

        self._section(b, self.t("s_update"))
        self._seg(b, [("game_start", self.t("up_game")), ("interval", self.t("up_6h")), ("manual", self.t("up_manual"))],
                  self.cfg.get("update_when", "game_start"), lambda v: self.setcfg(update_when=v))

        self._section(b, self.t("s_area"))
        self._seg(b, [("auto", self.t("area_auto")), ("pick", self.t("area_pick"))],
                  "pick" if self.cfg.get("region") else "auto", self.set_area)

        self._section(b, self.t("s_data"))
        meta = rc._load_meta()
        when = time.strftime("%m-%d %H:%M", time.localtime(meta["checked"])) if meta.get("checked") else "-"
        counts = {k: len(self.pools[k].ops) if k in self.pools else 0 for k in SERVERS}
        tk.Label(b, text=self.t("data_info", cn=counts["cn"], en=counts["en"], jp=counts["jp"], kr=counts["kr"], t=when),
                 bg=BG, fg=SUB, font=(CN, px(10)), anchor="w").pack(fill="x")
        row = tk.Frame(b, bg=BG)
        row.pack(fill="x", pady=(4, 0))
        tk.Button(row, text=self.t("data_update"), command=lambda: self.update_data(force=True), bg=CHIP, fg=TXT,
                  relief="flat", font=(CN, px(10)), padx=10).pack(side="left")
        tk.Button(row, text=self.t("u_btn") if w.FROZEN else self.t("s_remove"), command=self.remove_all, bg=ROW, fg=SUB, relief="flat",
                  font=(CN, px(10)), padx=10).pack(side="right")

    def set_lang(self, lang):
        self.lang = lang
        self.setcfg(lang=lang)
        self._build_main()
        self.panel.set_texts(self.tx)
        self.model_sig = None
        self.refresh_all()
        if self.settings_win:
            self.settings_win.destroy()
            self.open_settings()
        self._setup_tray(rebuild=True)

    def set_area(self, v):
        if v == "auto":
            self.cfg.pop("region", None)
            save_config(self.cfg)
        else:
            self.select_region()

    def set_startup(self, mode):
        self.setcfg(startup=mode)
        shortcut = self.cfg.get("shortcut", True)
        if w.is_admin():
            ok = apply_startup(mode, shortcut, self.cfg, w.INSTALLED_EXE if w.FROZEN else None)
        else:
            ok = w.relaunch_as_admin(["--apply-startup"], wait=True)
        self.status(self.t("applied_startup") if ok else self.t("startup_fail"))

    def remove_all(self):
        if w.FROZEN:  # exe 版：完整卸载
            from tkinter import messagebox
            if messagebox.askyesno(self.t("u_btn"), self.t("u_confirm"), parent=self.settings_win or self.root):
                uninstall_everything()
                self.quit("uninstall")
            return
        self.setcfg(startup="manual", shortcut=False)
        if w.is_admin():
            remove_startup()
        else:
            w.relaunch_as_admin(["--remove-startup"], wait=True)
        self.status(self.t("applied_startup"))

    def select_region(self):
        m = w.virtual_screen()
        ov = tk.Toplevel(self.root)
        ov.overrideredirect(True)
        ov.geometry(f"{m['width']}x{m['height']}+{m['left']}+{m['top']}")
        ov.attributes("-alpha", 0.3)
        ov.attributes("-topmost", True)
        cv = tk.Canvas(ov, bg="black", highlightthickness=0, cursor="crosshair")
        cv.pack(fill="both", expand=True)
        cv.create_text(-m["left"] + 400, -m["top"] + 80, text=self.t("region_tip"), fill="white",
                       font=(CN, px(24), "bold"), anchor="w")
        st = {}

        def down(e):
            st.update(x=e.x_root, y=e.y_root, ox=e.x, oy=e.y,
                      rect=cv.create_rectangle(e.x, e.y, e.x, e.y, outline=ACCENT, width=3))

        def move(e):
            if "rect" in st:
                cv.coords(st["rect"], st["ox"], st["oy"], e.x, e.y)

        def up(e):
            if "x" not in st:
                return
            x0, y0 = min(st["x"], e.x_root), min(st["y"], e.y_root)
            ww, hh = abs(e.x_root - st["x"]), abs(e.y_root - st["y"])
            ov.destroy()
            if ww > 50 and hh > 50:
                self.setcfg(region=[x0, y0, ww, hh])
                self.area = None
                self.load_ocr()
        cv.bind("<ButtonPress-1>", down)
        cv.bind("<B1-Motion>", move)
        cv.bind("<ButtonRelease-1>", up)
        ov.bind("<Escape>", lambda e: ov.destroy())
        ov.focus_force()

    # ------------------------------------------------------------ hotkeys / tray / single instance
    def _setup_hotkeys(self):
        try:
            import keyboard
            keyboard.add_hotkey(HOTKEY_SCAN, lambda: self.root.after(0, self.scan_now))
            keyboard.add_hotkey(HOTKEY_OVERLAY, lambda: self.root.after(0, self.toggle_overlay))
        except Exception:  # noqa: BLE001
            pass

    def _setup_tray(self, rebuild=False):
        try:
            import pystray
        except ImportError:
            return
        if self.tray:
            if not rebuild:
                return
            self.tray.stop()
        a = self.root.after
        menu = pystray.Menu(
            pystray.MenuItem(self.t("t_show"), lambda: a(0, self.show_main), default=True),
            pystray.MenuItem(self.t("t_overlay"), lambda: a(0, self.toggle_overlay),
                             checked=lambda _: self.cfg.get("overlay", True)),
            pystray.MenuItem(self.t("settings"), lambda: a(0, lambda: (self.show_main(), self.open_settings()))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(self.t("t_sleep"), lambda: a(0, self.go_sleep)),
            pystray.MenuItem(self.t("t_quit"), lambda: a(0, self.full_quit)),
        )
        self.tray = pystray.Icon("ArkRecruit", make_icon(64), self.t("app"), menu)
        self.tray.run_detached()

    def _sync_tray(self):
        if self.tray:
            self.tray.update_menu()

    def _single_instance_server(self):
        def serve():
            while True:
                try:
                    c, _ = self._sock.accept()
                    msg = c.recv(64)
                    c.close()
                    if msg == b"show":
                        self.root.after(0, self.show_main)
                    elif msg == b"quit":
                        self.root.after(0, lambda: self.quit("replaced by update"))
                except OSError:
                    return
        threading.Thread(target=serve, daemon=True).start()

    def quit(self, reason="quit"):
        log.info("exit: %s", reason)
        try:
            self.setcfg(geometry=self.root.geometry())
        except tk.TclError:
            pass
        if self.tray:
            self.tray.stop()
        self.root.destroy()


# ====================================================================== wizard
def do_install(cfg: dict, lang: str, startup: str, shortcut: bool):
    launcher = w.find_launcher()
    cfg.update(lang=lang, startup=startup, shortcut=shortcut, setup_done=True,
               on_exit=cfg.get("on_exit", "stay"), version=VERSION)
    if launcher:
        cfg.update(launcher=launcher[0], launcher_args=launcher[1])
    save_config(cfg)
    exe = install_self()
    if w.is_admin():
        return apply_startup(startup, shortcut, cfg, exe)
    return w.relaunch_as_admin(["--apply-startup"], wait=True)



def run_wizard(root: tk.Tk, cfg: dict, installer: bool) -> bool:
    """首次设置（exe 版同时负责安装）。一个大按钮搞定，选项默认收起。返回 True=已完成"""
    win = tk.Toplevel(root)
    win.title("公招助手 / Recruit Helper")
    win.configure(bg=BG)
    win.resizable(False, False)
    try:
        from PIL import ImageTk
        win._icon = ImageTk.PhotoImage(make_icon(64))
        win.iconphoto(True, win._icon)
    except Exception:  # noqa: BLE001
        pass
    st = {"lang": cfg.get("lang") or w.ui_lang(), "startup": cfg.get("startup", "logon"),
          "shortcut": cfg.get("shortcut", True), "done": False, "more": False}
    body = tk.Frame(win, bg=BG)
    body.pack(fill="both", padx=26, pady=20)
    WRAP = 480

    def build(busy=False):
        T = TEXT[st["lang"]]
        for c in body.winfo_children():
            c.destroy()
        cv = tk.Canvas(body, width=WRAP, height=70, bg=BG, highlightthickness=0)
        cv.pack(fill="x")
        cv.create_rectangle(0, 8, 4, 62, fill=ACCENT, outline="")
        cv.create_text(16, 26, text=T["w_title"], anchor="w", fill=TXT, font=(CN, px(21), "bold"))
        cv.create_text(16, 52, text="ARKNIGHTS · RECRUITMENT HELPER  v" + VERSION, anchor="w", fill=SUB,
                       font=(EN, px(11)))
        steps = tk.Frame(body, bg=PANEL)
        steps.pack(fill="x", pady=(10, 4))
        tk.Label(steps, text=T["w_steps"], bg=PANEL, fg=TXT, font=(CN, px(13)), justify="left", anchor="w",
                 wraplength=WRAP - 28).pack(fill="x", padx=14, pady=12)
        if st["startup"] == "logon":
            tk.Label(body, text=T["w_auto"], bg=BG, fg=SUB, font=(CN, px(11)), anchor="w", wraplength=WRAP,
                     justify="left").pack(fill="x", pady=(4, 0))

        text = T["w_installing"] if busy else (T["w_install"] if installer else T["w_start"])
        go = tk.Label(body, text=text, bg=ACCENT, fg="white", font=(CN, px(16), "bold"), pady=12,
                      cursor="" if busy else "hand2")
        go.pack(fill="x", pady=(16, 6))
        if busy:
            return
        go.bind("<Button-1>", lambda e: finish())
        go.bind("<Enter>", lambda e: go.configure(bg="#1AA8E8"))
        go.bind("<Leave>", lambda e: go.configure(bg=ACCENT))

        # ---- 更多选项（默认收起）----
        more = tk.Label(body, text=("▾ " if st["more"] else "▸ ") + T["w_more"], bg=BG, fg=SUB,
                        font=(CN, px(11)), cursor="hand2", anchor="w")
        more.pack(fill="x", pady=(6, 0))
        more.bind("<Button-1>", lambda e: (st.update(more=not st["more"]), build()))
        if not st["more"]:
            return
        opt = tk.Frame(body, bg=BG)
        opt.pack(fill="x", pady=(4, 0))

        def seg(options, key):
            fr = tk.Frame(opt, bg=BG)
            fr.pack(fill="x", pady=(0, 6))
            var = tk.StringVar(value=st[key])
            for val, label in options:
                tk.Radiobutton(fr, text=label, value=val, variable=var, indicatoron=False, bg=CHIP, fg=TXT,
                               selectcolor=ACCENT, activebackground="#555", relief="flat", bd=0,
                               font=(CN, px(11)), padx=12, pady=5,
                               command=lambda: (st.update({key: var.get()}), build())).pack(side="left", padx=(0, 2))

        def label(text):
            tk.Label(opt, text=text, bg=BG, fg=SUB, font=(CN, px(11), "bold"), anchor="w").pack(fill="x", pady=(6, 3))
        label(T["s_lang"])
        seg(LANG_OPTIONS, "lang")
        label(T["s_start"])
        var = tk.StringVar(value=st["startup"])
        for val in ("logon", "with_game", "manual"):
            tk.Radiobutton(opt, text=T["st_" + val], value=val, variable=var, bg=BG, fg=TXT, selectcolor=CHIP,
                           activebackground=BG, activeforeground=TXT, font=(CN, px(12)), anchor="w",
                           command=lambda: (st.update(startup=var.get()), build())).pack(fill="x")
        tk.Label(opt, text=T["st_desc"], bg=BG, fg=SUB, font=(CN, px(10)), wraplength=WRAP, justify="left",
                 anchor="w").pack(fill="x", pady=(2, 6))
        sv = tk.BooleanVar(value=st["shortcut"])
        tk.Checkbutton(opt, text=T["w_shortcut"], variable=sv, command=lambda: st.update(shortcut=sv.get()),
                       bg=BG, fg=TXT, selectcolor=CHIP, activebackground=BG, activeforeground=TXT,
                       font=(CN, px(12)), anchor="w").pack(fill="x")
        tk.Label(opt, text=T["hotkeys"], bg=BG, fg=SUB, font=(CN, px(10)), anchor="w").pack(fill="x", pady=(8, 0))

    def finish():
        build(busy=True)
        win.update()
        do_install(cfg, st["lang"], st["startup"], st["shortcut"])
        st["done"] = True
        win.destroy()

    build()
    win.protocol("WM_DELETE_WINDOW", win.destroy)
    win.update_idletasks()
    x = (win.winfo_screenwidth() - win.winfo_reqwidth()) // 2
    y = (win.winfo_screenheight() - win.winfo_reqheight()) // 3
    win.geometry(f"+{x}+{y}")
    win.lift()
    win.attributes("-topmost", True)
    win.after(500, lambda: win.attributes("-topmost", False))
    win.focus_force()
    root.wait_window(win)
    return st["done"]


# ====================================================================== main
def setup_logging():
    """小日志文件（最多 2×256KB），记录启动/退出/游戏开关和所有异常，方便排查"""
    import logging.handlers
    h = logging.handlers.RotatingFileHandler(LOG_PATH, maxBytes=256 * 1024, backupCount=1, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%m-%d %H:%M:%S"))
    log.addHandler(h)
    log.setLevel(logging.INFO)
    sys.excepthook = lambda t, v, tb: log.error("uncaught", exc_info=(t, v, tb))
    threading.excepthook = lambda a: log.error("thread error", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    tk.Tk.report_callback_exception = lambda self, t, v, tb: log.error("tk callback error", exc_info=(t, v, tb))


def selftest(out: str | None) -> int:
    lines = [f"version {VERSION} frozen={w.FROZEN}", f"user_dir {rc.USER_DIR}"]
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        pools = {s: rc.Pool(s) for s in ("cn", "en")}
        extra = {s: rc.Pool(s) for s in ("jp", "kr")}
        lines.append("jp/kr pools " + " ".join(f"{k}={len(v.ops)}" for k, v in extra.items()))
        lines.append("i18n " + " ".join(f"{k}={len(v)}" for k, v in TEXT.items()))
        lines.append("pools " + " ".join(f"{k}={len(v.ops)}" for k, v in pools.items()))
        im = Image.new("RGB", (900, 300), (40, 40, 45))
        d = ImageDraw.Draw(im)
        font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 22)
        for i, t in enumerate(["高级资深干员", "近卫干员", "输出", "控场", "近战位"]):
            x, y = 60 + (i % 3) * 260, 60 + (i // 3) * 90
            d.rectangle([x, y, x + 200, y + 44], fill=(49, 49, 49))
            d.text((x + 20, y + 8), t, fill="white", font=font)
        t0 = time.time()
        s = OCR().scan(np.array(im)[:, :, ::-1].copy(), pools)
        lines.append(f"ocr {time.time() - t0:.2f}s tags=" + ",".join(pools[s.srv].tags[t] for t in s.tags))
        lines.append("verdict " + rc.verdict(rc.calc(pools[s.srv], s.tags))[0])
        code = 0 if len(s.tags) == 5 else 1
    except Exception as e:  # noqa: BLE001
        import traceback
        lines.append("ERROR " + traceback.format_exc())
        code = 2
    text = "\n".join(lines)
    if out:
        open(out, "w", encoding="utf-8").write(text)
    else:
        print(text)
    return code


def main():
    args = sys.argv[1:]
    cfg = load_config()
    exe = w.INSTALLED_EXE if w.FROZEN else None
    if "--apply-startup" in args:  # 由非管理员实例提权调用
        sys.exit(0 if apply_startup(cfg.get("startup", "manual"), cfg.get("shortcut", True), cfg, exe) else 1)
    if "--remove-startup" in args:
        remove_startup()
        sys.exit(0)
    if "--selftest" in args:  # 只读自检：数据、OCR 模型、识别一张生成的图片
        sys.exit(selftest(args[args.index("--selftest") + 1] if len(args) > args.index("--selftest") + 1 else None))

    # exe 版、且不是从安装位置运行（例如刚从下载文件夹双击）→ 安装 / 更新
    if not w.is_installed_copy():
        if "--quiet-install" in args:  # 无界面安装（默认选项）
            ok = do_install(cfg, cfg.get("lang") or w.ui_lang(), cfg.get("startup", "logon"), cfg.get("shortcut", True))
            if ok and "--no-launch" not in args:
                w.run_task("Open")
            sys.exit(0 if ok else 1)
        root = tk.Tk()
        root.withdraw()
        if run_wizard(root, cfg, installer=True):
            w.run_task("Open")  # 以管理员打开安装好的副本（不再弹 UAC）
        root.destroy()
        return

    mode = "with_game" if "--with-game" in args else "background" if "--background" in args else "normal"
    setup_logging()
    if mode == "normal" or "--logon" in args:  # 用户主动打开 / 新登录：取消“完全退出”标记
        try:
            os.remove(PAUSED_FLAG)
        except OSError:
            pass

    # 单实例：已有实例在运行 → 让它显示主窗口
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", PORT))
        sock.listen(4)
    except OSError:
        if mode == "with_game":  # 已在后台待命：只需启动游戏
            if not w.find_game_hwnd():
                launch_game(cfg)
        try:
            c = socket.create_connection(("127.0.0.1", PORT), timeout=2)
            c.sendall(b"show" if mode == "normal" else b"noop")
            c.close()
        except OSError:
            pass
        return

    root = tk.Tk()
    root.withdraw()
    if "--setup" in args or not cfg.get("setup_done"):
        if not run_wizard(root, cfg, installer=False) and not cfg.get("setup_done"):
            root.destroy()
            return
    App._sock = sock
    log.info("start v%s mode=%s admin=%s frozen=%s", VERSION, mode, w.is_admin(), w.FROZEN)
    app = App(root, mode)
    if mode == "normal":
        root.deiconify()
    root.mainloop()
    _ = app


if __name__ == "__main__":
    main()
