#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HOI4 Mod 创意工坊上传工具 v2.0
==============================
绕过 Paradox 启动器，直接调用 SteamCMD 将本地 Mod 上传到 Steam 创意工坊。

HOI4 Steam AppID: 394360
原理: steamcmd +login <user> <pass> +workshop_build_item <vdf> +quit

v2.0 相比 v1.0 的变化：
  - 全新界面：侧栏（Mod 历史记录 / 快捷操作）+ 卡片式主区 + 可折叠日志面板
  - 深色 / 浅色主题一键切换，界面字号可调
  - 窗口更大、可自由拉伸，且会记住大小和位置；设置里有多档尺寸预设
  - Mod 历史列表：所有上传过的 Mod 一目了然，单击即可切换
  - 预览图缩略图预览（含尺寸 / 文件大小检查）
  - Steam 登录测试（不上传，只验证账号）
  - 本机游戏版本核对（提醒 supported_version 是否匹配）
  - Mod 大小统计、非 ASCII 路径警告
  - 工坊页面快捷打开 / 复制链接、更新说明历史下拉
  - 运行日志自动落盘到 logs/，可导出
  - 登录数据完整兼容旧配置（uploader_config.json 不会被清空，并自动留有备份）
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, font as tkfont
import os
import re
import json
import shutil
import subprocess
import threading
import urllib.request
import zipfile
import time
import datetime
from typing import Optional

# ============================================================
# 常量
# ============================================================
HOI4_APP_ID = "394360"
CONFIG_FILE = "uploader_config.json"
BACKUP_FILE = "uploader_config.backup.json"
ICON_FILE = "uploader_icon.ico"
STEAMCMD_ZIP_URL = "https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip"

# SteamCMD 不能在含中文的路径下运行；VDF 也写到纯 ASCII 目录
STEAMCMD_DIR = r"E:\SteamCMD"
DEFAULT_HOI4_MOD_DIR = os.path.join(
    os.path.expanduser("~"),
    "Documents", "Paradox Interactive", "Hearts of Iron IV", "mod"
)
LOG_DIR = "logs"

VISIBILITY_MAP = {"0": "公开", "1": "仅好友", "2": "私密"}

PREVIEW_WARN_BYTES = 1 * 1024 * 1024   # 预览图超过 1MB 提醒

THEMES = {
    "dark": {
        "bg":        "#17191d",   # 窗口背景
        "side":      "#101216",   # 侧栏 / 状态栏
        "card":      "#20242b",   # 卡片
        "btn":       "#2a303a",   # 普通按钮
        "btn_press": "#242932",
        "hover":     "#333b47",
        "border":    "#2c333d",
        "text":      "#e6e9ee",
        "dim":       "#8b929c",
        "accent":    "#4f8cff",
        "accent_hover": "#6ba1ff",
        "success":   "#2f9e44",
        "success_hover": "#40b055",
        "success_press": "#278a3a",
        "danger":    "#e5534b",
        "warn":      "#d29922",
        "entry":     "#14161a",
        "sel":       "#2f5fb3",
        "log_bg":    "#111317",
    },
    "light": {
        "bg":        "#eef0f3",
        "side":      "#e2e5ea",
        "card":      "#ffffff",
        "btn":       "#e8ebef",
        "btn_press": "#dde1e7",
        "hover":     "#dfe3e9",
        "border":    "#cdd3db",
        "text":      "#1f2428",
        "dim":       "#6a7280",
        "accent":    "#2563eb",
        "accent_hover": "#3b82f6",
        "success":   "#16a34a",
        "success_hover": "#22b557",
        "success_press": "#128a3e",
        "danger":    "#dc2626",
        "warn":      "#b45309",
        "entry":     "#ffffff",
        "sel":       "#c7dbff",
        "log_bg":    "#f6f7f9",
    },
}


# ============================================================
# 工具函数
# ============================================================
def parse_descriptor(mod_dir: str) -> dict:
    """解析 mod 目录下的 descriptor.mod，返回 name / version / tags / supported_version"""
    result = {"name": "", "version": "", "supported_version": "", "tags": []}
    if not mod_dir or not os.path.isdir(mod_dir):
        return result
    desc_path = os.path.join(mod_dir, "descriptor.mod")
    if not os.path.isfile(desc_path):
        # 兼容旧格式：尝试找同目录下的 .mod 文件
        for f in os.listdir(mod_dir):
            if f.endswith(".mod"):
                desc_path = os.path.join(mod_dir, f)
                break
        else:
            return result

    try:
        with open(desc_path, "r", encoding="utf-8-sig", errors="replace") as f:
            content = f.read()
    except Exception:
        return result

    m = re.search(r'name\s*=\s*"([^"]*)"', content)
    if m:
        result["name"] = m.group(1)
    m = re.search(r'version\s*=\s*"([^"]*)"', content)
    if m:
        result["version"] = m.group(1)
    m = re.search(r'supported_version\s*=\s*"([^"]*)"', content)
    if m:
        result["supported_version"] = m.group(1)

    tags_match = re.search(r'tags\s*=\s*\{([^}]*)\}', content, re.DOTALL)
    if tags_match:
        result["tags"] = re.findall(r'"([^"]*)"', tags_match.group(1))

    return result


def vdf_escape(text: str) -> str:
    """VDF 值转义"""
    return text.replace("\\", "\\\\").replace('"', '\\"')


def generate_vdf(vdf_path: str, mod_dir: str, preview: str, title: str,
                 description: str, visibility: str, changenote: str,
                 published_id: str) -> None:
    """生成 workshop_build_item 用的 VDF 配置文件"""
    mod_dir_vdf = os.path.abspath(mod_dir).replace("\\", "\\\\")
    preview_vdf = os.path.abspath(preview).replace("\\", "\\\\") if preview else ""

    lines = [
        '"workshopitem"',
        '{',
        f'\t"appid"\t\t"{HOI4_APP_ID}"',
        f'\t"publishedfileid"\t"{published_id}"',
        f'\t"contentfolder"\t"{mod_dir_vdf}"',
    ]
    if preview_vdf:
        lines.append(f'\t"previewfile"\t"{preview_vdf}"')
    lines.extend([
        f'\t"visibility"\t"{visibility}"',
        f'\t"title"\t\t"{vdf_escape(title)}"',
        f'\t"description"\t"{vdf_escape(description)}"',
        f'\t"changenote"\t"{vdf_escape(changenote)}"',
        '}',
    ])

    with open(vdf_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def read_published_id_from_vdf(vdf_path: str) -> str:
    """上传完成后从 VDF 中读取 steamcmd 回写的 publishedfileid"""
    try:
        with open(vdf_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        m = re.search(r'"publishedfileid"\s*"(\d+)"', content)
        if m:
            return m.group(1)
    except Exception:
        pass
    return "0"


def find_steam_installation() -> Optional[str]:
    """尝试从常见路径和注册表查找 Steam 安装目录"""
    candidates = [
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "Steam"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Steam"),
        os.path.join(os.path.expanduser("~"), "AppData", "Local", "Steam"),
        "D:\\Steam", "E:\\Steam", "F:\\Steam",
    ]
    for p in candidates:
        if os.path.isdir(p):
            return p

    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        val, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)
        if val and os.path.isdir(val):
            return val
    except Exception:
        pass
    return None


def find_hoi4_game_version() -> Optional[str]:
    """从 Steam 库中读取本机 HOI4 的游戏版本（launcher-settings.json）"""
    steam = find_steam_installation()
    if not steam:
        return None

    libs = [steam]
    lf = os.path.join(steam, "steamapps", "libraryfolders.vdf")
    try:
        with open(lf, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for m in re.finditer(r'"path"\s+"([^"]+)"', content):
            p = m.group(1).replace("\\\\", "\\")
            if p not in libs:
                libs.append(p)
    except Exception:
        pass

    for lib in libs:
        acf = os.path.join(lib, "steamapps", "appmanifest_394360.acf")
        if not os.path.isfile(acf):
            continue
        try:
            with open(acf, "r", encoding="utf-8", errors="replace") as f:
                manifest = f.read()
            m = re.search(r'"installdir"\s*"([^"]*)"', manifest)
            if not m:
                continue
            game_dir = os.path.join(lib, "steamapps", "common", m.group(1))
            ls = os.path.join(game_dir, "launcher-settings.json")
            if os.path.isfile(ls):
                with open(ls, "r", encoding="utf-8", errors="replace") as f:
                    data = json.load(f)
                ver = data.get("rawVersion") or data.get("version")
                if ver:
                    return str(ver)
        except Exception:
            continue
    return None


def version_mismatch(supported: str, game: str) -> bool:
    """比较 supported_version 与游戏版本的大小版本号是否一致"""
    if not supported or not game:
        return False
    ms = re.match(r"(\d+)\.(\d+)", supported)
    mg = re.match(r"(\d+)\.(\d+)", game)
    if not ms or not mg:
        return False
    return (ms.group(1), ms.group(2)) != (mg.group(1), mg.group(2))


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} GB"


def path_key(p: str) -> str:
    """路径归一化（用于比较和查找，不改变配置文件里的原键）"""
    try:
        return os.path.normcase(os.path.normpath(p))
    except Exception:
        return p or ""


def has_non_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return False
    except UnicodeEncodeError:
        return True


# ============================================================
# 主应用
# ============================================================
class HOI4ModUploaderApp:
    def __init__(self, root: tk.Tk, dpi_scale: float = 1.0):
        self.root = root
        self.dpi = max(1.0, float(dpi_scale))
        root.title("HOI4 Mod 创意工坊上传工具  v2.0")
        root.minsize(980, 660)

        self.T = THEMES["dark"]   # 当前主题色板（load_config 后确定）

        # ---- 配置数据（先读配置，再建界面）----
        self.win_cfg = {"remember": True, "maximized": False,
                        "width": 0, "height": 0, "x": 0, "y": 0}
        self.changenote_history: list = []
        self.theme_name = "dark"
        self._font_scale = 1.0

        # ---- 状态 ----
        self.busy = False            # 正在上传或测试登录
        self.process: Optional[subprocess.Popen] = None
        self._steamcmd_downloading = False
        self._ui_ready = False
        self._log_fh = None
        self._thumb_img = None
        self._last_info = {"name": "", "version": "", "supported_version": "", "tags": []}

        self._make_vars()
        self.load_config()

        # ---- 字体（命名 Font 对象，改字号时原地调整）----
        self._build_fonts()
        self.style = ttk.Style()
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        root.configure(bg=self.T["bg"])
        self._style_setup()

        self._build_ui()
        self._apply_text_theme()
        self._set_win_icon(root)
        self._restore_geometry()

        # ---- 变量联动 ----
        self.preview_path.trace_add("write", self._on_preview_changed)
        self.published_id.trace_add("write", lambda *a: self._update_link_buttons())
        self.steamcmd_path.trace_add("write", lambda *a: self._check_steamcmd())

        self._detect_steamcmd()
        self._refresh_history()
        self._update_link_buttons()
        if self.mod_dir.get().strip():
            try:
                self._parse_mod(quiet=True)
            except Exception:
                pass

        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.bind("<Control-Return>", lambda e: self._start_upload())
        self._bind_wheel()
        self._ui_ready = True

    # ==========================================================
    # 变量
    # ==========================================================
    def _make_vars(self):
        self.mod_dir = tk.StringVar()
        self.steamcmd_path = tk.StringVar()
        self.steam_user = tk.StringVar()
        self.steam_pass = tk.StringVar()
        self.steam_guard = tk.StringVar()
        self.remember_pass = tk.BooleanVar(value=False)
        self.mod_title = tk.StringVar()
        self.preview_path = tk.StringVar()
        self.visibility = tk.StringVar(value="0")
        self.changenote = tk.StringVar()
        self.published_id = tk.StringVar(value="0")
        self.open_after = tk.BooleanVar(value=False)
        self.font_scale = tk.DoubleVar(value=1.0)
        self.theme_var = tk.StringVar(value="dark")
        self.win_remember = tk.BooleanVar(value=True)

    # ==========================================================
    # 配置持久化（合并式写入：绝不丢旧字段）
    # ==========================================================
    def _tool_dir(self) -> str:
        return os.path.dirname(os.path.abspath(__file__))

    def _config_path(self) -> str:
        return os.path.join(self._tool_dir(), CONFIG_FILE)

    def _read_config_file(self) -> dict:
        try:
            with open(self._config_path(), "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if isinstance(cfg, dict):
                return cfg
        except Exception:
            pass
        return {}

    def load_config(self):
        cfg = self._read_config_file()

        self.mod_dir.set(cfg.get("mod_dir", ""))
        self.steamcmd_path.set(cfg.get("steamcmd_path", ""))
        self.steam_user.set(cfg.get("steam_user", ""))
        # 旧版本不保存密码；新版仅当用户显式勾选"记住密码"时才存
        self.remember_pass.set(bool(cfg.get("remember_pass", False)))
        if self.remember_pass.get():
            self.steam_pass.set(cfg.get("steam_pass", ""))
        self.visibility.set(str(cfg.get("visibility", "0")))

        # 已发布ID按mod目录保存
        mod_ids = cfg.get("published_ids", {}) or {}
        pid = mod_ids.get(self.mod_dir.get(), None)
        if pid is None:   # 路径分隔符写法不同时的兜底查找
            key = path_key(self.mod_dir.get())
            for k, v in mod_ids.items():
                if path_key(k) == key:
                    pid = v
                    break
        self.published_id.set(str(pid) if pid not in (None, "") else "0")

        self.changenote_history = list(cfg.get("changenote_history", []) or [])
        self.open_after.set(bool(cfg.get("open_after_upload", False)))
        self.theme_name = cfg.get("theme", "dark")
        if self.theme_name not in THEMES:
            self.theme_name = "dark"
        try:
            self._font_scale = float(cfg.get("font_scale", 1.0))
        except (TypeError, ValueError):
            self._font_scale = 1.0
        self._font_scale = min(1.5, max(0.8, self._font_scale))

        win = cfg.get("window", {}) or {}
        if isinstance(win, dict):
            self.win_cfg.update({k: win.get(k, self.win_cfg.get(k)) for k in self.win_cfg})
        self.win_remember.set(bool(self.win_cfg.get("remember", True)))

        self.T = THEMES[self.theme_name]
        self.theme_var.set(self.theme_name)
        self.font_scale.set(self._font_scale)

    def _patch_config(self, update: dict):
        """读旧配置 → 合并 → 写回。首次写入前先留一份原始备份。"""
        cfg_path = self._config_path()
        old = self._read_config_file()
        cfg = dict(old)
        cfg.update(update)

        try:
            if os.path.isfile(cfg_path) and not os.path.isfile(
                    os.path.join(self._tool_dir(), BACKUP_FILE)):
                shutil.copy2(cfg_path, os.path.join(self._tool_dir(), BACKUP_FILE))
        except Exception:
            pass

        try:
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def save_all(self):
        """收集当前状态写入配置（合并式，不影响其他历史记录）"""
        cur = self.mod_dir.get().strip()
        pids = dict(self._read_config_file().get("published_ids", {}) or {})
        if cur:
            target_key = None
            for k in pids:
                if path_key(k) == path_key(cur):
                    target_key = k
                    break
            key = target_key if target_key is not None else os.path.normpath(cur)
            pids[key] = self.published_id.get().strip() or "0"

        data = {
            "mod_dir": cur,
            "steamcmd_path": self.steamcmd_path.get(),
            "steam_user": self.steam_user.get(),
            "visibility": self.visibility.get(),
            "published_ids": pids,
            "remember_pass": bool(self.remember_pass.get()),
            "steam_pass": self.steam_pass.get() if self.remember_pass.get() else "",
            "changenote_history": self.changenote_history[:10],
            "open_after_upload": bool(self.open_after.get()),
            "theme": self.theme_name,
            "font_scale": self._font_scale,
            "window": self._capture_window(),
        }
        self._patch_config(data)

    def _capture_window(self) -> dict:
        win = dict(self.win_cfg)
        win["remember"] = bool(self.win_remember.get())
        try:
            if self.root.state() == "zoomed":
                win["maximized"] = True
            else:
                win["maximized"] = False
                m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", self.root.winfo_geometry())
                if m:
                    w, h = int(m.group(1)), int(m.group(2))
                    # 忽略窗口尚未真正布局时的异常尺寸
                    if w >= 500 and h >= 400:
                        win["width"], win["height"] = w, h
                        win["x"], win["y"] = int(m.group(3)), int(m.group(4))
        except Exception:
            pass
        return win

    def _restore_geometry(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        win = self.win_cfg
        if win.get("remember") and win.get("width") and win.get("height"):
            w = min(win["width"], sw - 40)
            h = min(win["height"], sh - 60)
            x = max(-w + 120, min(win.get("x", 0), sw - 120))
            y = max(0, min(win.get("y", 0), sh - 80))
            self.root.geometry(f"{w}x{h}+{x}+{y}")
            if win.get("maximized"):
                self.root.state("zoomed")
            return
        # 默认尺寸：按屏幕和 DPI 自动放大，避免"小窗口"
        w = min(int(sw * 0.78), int(1500 * self.dpi), 2400)
        h = min(int(sh * 0.80), int(940 * self.dpi), 1500)
        w = max(w, 1080)
        h = max(h, 700)
        x = max(0, (sw - w) // 2 - int(60 * self.dpi))
        y = max(0, (sh - h) // 2 - int(40 * self.dpi))
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ==========================================================
    # 字体与主题
    # ==========================================================
    def _build_fonts(self):
        s = self._font_scale
        def mk(sz, bold=False):
            return tkfont.Font(family="Microsoft YaHei UI",
                               size=max(8, round(sz * s)),
                               weight="bold" if bold else "normal")
        self.F_TITLE = mk(14, True)
        self.F_H = mk(11, True)
        self.F_BODY = mk(10)
        self.F_SMALL = mk(9)
        self.F_BTN = mk(10)
        self.F_BIG = mk(13, True)
        self.F_MONO = tkfont.Font(family="Consolas", size=max(8, round(10 * s)))

    def _apply_font_scale(self):
        s = self._font_scale
        for font, base, bold in (
                (self.F_TITLE, 14, True), (self.F_H, 11, True),
                (self.F_BODY, 10, False), (self.F_SMALL, 9, False),
                (self.F_BTN, 10, False), (self.F_BIG, 13, True)):
            font.configure(size=max(8, round(base * s)),
                           weight="bold" if bold else "normal")
        self.F_MONO.configure(size=max(8, round(10 * s)))
        self.style.configure("History.Treeview", rowheight=self.px(46))

    def px(self, n) -> int:
        """按系统 DPI 缩放的像素值"""
        return max(1, int(round(n * self.dpi)))

    def _icon_path(self) -> str:
        return os.path.join(self._tool_dir(), ICON_FILE)

    def _set_win_icon(self, window) -> None:
        """给窗口设置应用图标（不存在时静默跳过）"""
        p = self._icon_path()
        if os.path.isfile(p):
            try:
                window.iconbitmap(p)
            except Exception:
                pass

    def _style_setup(self):
        T = self.T
        s = self.style
        s.configure(".", background=T["bg"], foreground=T["text"],
                    borderwidth=0, focuscolor=T["accent"])

        # 框架
        s.configure("Main.TFrame", background=T["bg"])
        s.configure("Side.TFrame", background=T["side"])
        s.configure("Card.TFrame", background=T["card"])
        s.configure("Upload.TFrame", background=T["card"])

        # 标签
        s.configure("TLabel", background=T["bg"], foreground=T["text"], font=self.F_BODY)
        s.configure("Dim.TLabel", background=T["bg"], foreground=T["dim"], font=self.F_SMALL)
        s.configure("Card.TLabel", background=T["card"], foreground=T["text"], font=self.F_BODY)
        s.configure("CardDim.TLabel", background=T["card"], foreground=T["dim"], font=self.F_SMALL)
        s.configure("CardWarn.TLabel", background=T["card"], foreground=T["warn"], font=self.F_SMALL)
        s.configure("Side.TLabel", background=T["side"], foreground=T["text"], font=self.F_BODY)
        s.configure("SideDim.TLabel", background=T["side"], foreground=T["dim"], font=self.F_SMALL)
        s.configure("Title.TLabel", background=T["side"], foreground=T["text"], font=self.F_TITLE)
        s.configure("CardTitle.TLabel", background=T["card"], foreground=T["text"], font=self.F_H)
        s.configure("Status.TLabel", background=T["side"], foreground=T["dim"],
                    font=self.F_SMALL, padding=(self.px(10), self.px(4)))

        # 按钮
        pad = (self.px(12), self.px(5))
        s.configure("TButton", background=T["btn"], foreground=T["text"], font=self.F_BTN,
                    padding=pad, bordercolor=T["border"], lightcolor=T["btn"], darkcolor=T["btn"])
        s.map("TButton",
              background=[("pressed", T["btn_press"]), ("active", T["hover"]), ("disabled", T["side"])],
              foreground=[("disabled", T["dim"])])
        s.configure("Ghost.TButton", background=T["side"], foreground=T["text"], font=self.F_BTN,
                    padding=pad, bordercolor=T["border"], lightcolor=T["side"], darkcolor=T["side"])
        s.map("Ghost.TButton",
              background=[("pressed", T["btn_press"]), ("active", T["hover"]), ("disabled", T["side"])],
              foreground=[("disabled", T["dim"])])
        s.configure("Success.TButton", background=T["success"], foreground="#ffffff",
                    font=self.F_BIG, padding=(self.px(24), self.px(9)),
                    bordercolor=T["success"], lightcolor=T["success"], darkcolor=T["success"])
        s.map("Success.TButton",
              background=[("pressed", T["success_press"]), ("active", T["success_hover"]), ("disabled", T["side"])],
              foreground=[("disabled", T["dim"])])
        s.configure("Danger.TButton", background=T["btn"], foreground=T["danger"], font=self.F_BTN,
                    padding=pad, bordercolor=T["border"], lightcolor=T["btn"], darkcolor=T["btn"])
        s.map("Danger.TButton",
              background=[("pressed", T["btn_press"]), ("active", T["hover"]), ("disabled", T["side"])],
              foreground=[("disabled", T["dim"])])

        # 输入框
        s.configure("TEntry", fieldbackground=T["entry"], foreground=T["text"],
                    bordercolor=T["border"], lightcolor=T["entry"], darkcolor=T["entry"],
                    insertcolor=T["text"], padding=self.px(4))
        s.map("TEntry",
              bordercolor=[("focus", T["accent"])],
              fieldbackground=[("disabled", T["side"])],
              foreground=[("disabled", T["dim"])])

        # 下拉框
        s.configure("TCombobox", fieldbackground=T["entry"], background=T["btn"],
                    foreground=T["text"], arrowcolor=T["text"], bordercolor=T["border"],
                    lightcolor=T["entry"], darkcolor=T["entry"], padding=self.px(3))
        s.map("TCombobox",
              bordercolor=[("focus", T["accent"])],
              fieldbackground=[("readonly", T["entry"]), ("disabled", T["side"])],
              foreground=[("disabled", T["dim"])])
        self.root.option_add("*TCombobox*Listbox.background", T["entry"])
        self.root.option_add("*TCombobox*Listbox.foreground", T["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", T["sel"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", T["text"])
        self.root.option_add("*TCombobox*Listbox.font", self.F_BODY)

        # 复选 / 单选
        s.configure("TCheckbutton", background=T["bg"], foreground=T["text"], font=self.F_BODY)
        s.map("TCheckbutton", background=[("active", T["bg"])], foreground=[("disabled", T["dim"])])
        s.configure("Card.TCheckbutton", background=T["card"], foreground=T["text"], font=self.F_BODY)
        s.map("Card.TCheckbutton", background=[("active", T["card"])], foreground=[("disabled", T["dim"])])
        s.configure("TRadiobutton", background=T["bg"], foreground=T["text"], font=self.F_BODY)
        s.map("TRadiobutton", background=[("active", T["bg"])])
        s.configure("Card.TRadiobutton", background=T["card"], foreground=T["text"], font=self.F_BODY)
        s.map("Card.TRadiobutton", background=[("active", T["card"])])

        # 进度条 / 滚动条 / 分隔线
        s.configure("Horizontal.TProgressbar", troughcolor=T["entry"], background=T["accent"],
                    bordercolor=T["entry"], lightcolor=T["accent"], darkcolor=T["accent"],
                    thickness=self.px(8))
        s.configure("TScrollbar", troughcolor=T["bg"], background=T["btn"],
                    bordercolor=T["bg"], lightcolor=T["btn"], darkcolor=T["btn"],
                    arrowcolor=T["dim"], arrowsize=self.px(11), width=self.px(10), gripcount=0)
        s.map("TScrollbar", background=[("active", T["hover"])])
        s.configure("TSeparator", background=T["border"])
        s.configure("Card.TSeparator", background=T["border"])

        # 历史列表
        s.configure("History.Treeview", background=T["card"], fieldbackground=T["card"],
                    foreground=T["text"], font=self.F_BODY, borderwidth=0,
                    rowheight=self.px(46))
        s.map("History.Treeview",
              background=[("selected", T["sel"])],
              foreground=[("selected", T["text"])])

    def _apply_theme(self):
        self.T = THEMES[self.theme_name]
        self.root.configure(bg=self.T["bg"])
        self._style_setup()
        self._apply_text_theme()
        if self._settings_win is not None and self._settings_win.winfo_exists():
            try:
                self._settings_win.configure(bg=self.T["bg"])
            except Exception:
                pass

    def _apply_text_theme(self):
        T = self.T
        for txt in (self.desc_text, self.log_text):
            txt.configure(bg=T["entry"] if txt is self.desc_text else T["log_bg"],
                          fg=T["text"], insertbackground=T["text"],
                          selectbackground=T["sel"], selectforeground=T["text"],
                          highlightbackground=T["border"], highlightcolor=T["accent"])
        self.log_text.tag_configure("error", foreground=T["danger"])
        self.log_text.tag_configure("success", foreground=T["success"])
        self.log_text.tag_configure("warn", foreground=T["warn"])
        self.log_text.tag_configure("dim", foreground=T["dim"])
        self.main_canvas.configure(bg=T["bg"])
        self.thumb_border.configure(highlightbackground=T["border"])

    # ==========================================================
    # UI 构建
    # ==========================================================
    def _build_ui(self):
        outer = ttk.Frame(self.root, style="Main.TFrame")
        outer.pack(fill="both", expand=True)

        # ---- 底部：状态栏（最先 pack，沉底）----
        self.status_var = tk.StringVar(value="就绪  |  Ctrl+Enter 快速上传")
        ttk.Label(self.root, textvariable=self.status_var, style="Status.TLabel",
                  anchor="w").pack(fill="x", side="bottom")

        # ---- 底部：日志面板（可折叠）----
        self._build_log_panel()

        # ---- 底部：上传操作栏 ----
        self._build_upload_bar()

        # ---- 左侧：侧栏 ----
        self._build_sidebar(outer)

        # ---- 中间：主区（可滚动）----
        main_wrap = ttk.Frame(outer, style="Main.TFrame")
        main_wrap.pack(side="left", fill="both", expand=True)
        self.main_canvas = tk.Canvas(main_wrap, bg=self.T["bg"],
                                     highlightthickness=0, bd=0)
        vs = ttk.Scrollbar(main_wrap, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=vs.set)
        self.main_canvas.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        inner = ttk.Frame(self.main_canvas, style="Main.TFrame")
        self._inner_win = self.main_canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all")))
        self.main_canvas.bind("<Configure>",
                              lambda e: self.main_canvas.itemconfigure(self._inner_win, width=e.width))

        self._build_card_mod(inner)
        self._build_card_account(inner)
        self._build_card_workshop(inner)
        ttk.Frame(inner, style="Main.TFrame", height=self.px(16)).pack(fill="x")

    # ---------- 日志面板 ----------
    def _build_log_panel(self):
        self.log_panel = ttk.Frame(self.root, style="Side.TFrame",
                                   padding=(self.px(10), self.px(4)))
        self.log_panel.pack(fill="x", side="bottom")

        head = ttk.Frame(self.log_panel, style="Side.TFrame")
        head.pack(fill="x")
        self.log_toggle_lbl = ttk.Label(head, text="▾  运行日志", style="Side.TLabel",
                                        font=self.F_H)
        self.log_toggle_lbl.pack(side="left")
        self.log_toggle_lbl.bind("<Button-1>", lambda e: self._toggle_log())
        ttk.Button(head, text="展开 / 收起", style="Ghost.TButton",
                   command=self._toggle_log).pack(side="right")
        ttk.Button(head, text="导出日志", style="Ghost.TButton",
                   command=self._export_log).pack(side="right", padx=(0, self.px(6)))
        ttk.Button(head, text="清空", style="Ghost.TButton",
                   command=lambda: self._set_log("")).pack(side="right", padx=(0, self.px(6)))

        self.log_text = tk.Text(self.log_panel, height=9, wrap="word",
                                font=self.F_MONO, state="disabled", relief="flat",
                                bd=0, padx=self.px(8), pady=self.px(6))
        self.log_text.pack(fill="both", expand=True, pady=(self.px(4), 0))

    def _toggle_log(self):
        if self.log_text.winfo_ismapped():
            self.log_text.pack_forget()
            self.log_toggle_lbl.configure(text="▸  运行日志")
        else:
            self.log_text.pack(fill="both", expand=True, pady=(self.px(4), 0))
            self.log_toggle_lbl.configure(text="▾  运行日志")
            self.log_text.see("end")

    # ---------- 上传操作栏 ----------
    def _build_upload_bar(self):
        bar = ttk.Frame(self.root, style="Upload.TFrame", padding=(self.px(14), self.px(10)))
        bar.pack(fill="x", side="bottom")

        self.upload_btn = ttk.Button(bar, text="▶  开始上传", style="Success.TButton",
                                     command=self._start_upload)
        self.upload_btn.pack(side="left")
        self.stop_btn = ttk.Button(bar, text="■  终止", style="Danger.TButton",
                                   command=self._stop_upload, state="disabled")
        self.stop_btn.pack(side="left", padx=(self.px(10), 0))

        self.phase_lbl = ttk.Label(bar, text="就绪", style="CardDim.TLabel")
        self.phase_lbl.pack(side="right", padx=(self.px(10), 0))

        self.progress = ttk.Progressbar(bar, mode="indeterminate", length=self.px(220))
        self.progress.pack(side="right", padx=self.px(10))

        ttk.Checkbutton(bar, text="上传成功后打开工坊页面", variable=self.open_after,
                        style="Card.TCheckbutton").pack(side="right", padx=self.px(6))

    # ---------- 侧栏 ----------
    def _build_sidebar(self, parent):
        side = ttk.Frame(parent, style="Side.TFrame", width=self.px(248),
                         padding=(self.px(14), self.px(12)))
        side.pack_propagate(False)
        side.pack(side="left", fill="y")

        ttk.Label(side, text="HOI4 Mod 上传工具", style="Title.TLabel").pack(anchor="w")
        ttk.Label(side, text="创意工坊 · SteamCMD 直传  v2.0",
                  style="SideDim.TLabel").pack(anchor="w", pady=(0, self.px(8)))
        ttk.Separator(side).pack(fill="x", pady=(0, self.px(8)))

        ttk.Label(side, text="我的 Mod（历史记录）", style="Side.TLabel",
                  font=self.F_H).pack(anchor="w")
        ttk.Label(side, text="单击载入 · 自动带上对应的已发布 ID",
                  style="SideDim.TLabel").pack(anchor="w", pady=(0, self.px(4)))

        self.history_tree = ttk.Treeview(side, style="History.Treeview",
                                         show="tree", selectmode="browse")
        self.history_tree.column("#0", stretch=True)
        self.history_tree.pack(fill="both", expand=True)
        self.history_tree.bind("<<TreeviewSelect>>", self._on_history_select)

        btns = ttk.Frame(side, style="Side.TFrame")
        btns.pack(fill="x", pady=(self.px(6), 0))
        ttk.Button(btns, text="刷新", style="Ghost.TButton",
                   command=self._refresh_history).pack(side="left", fill="x", expand=True)
        ttk.Button(btns, text="移除记录", style="Ghost.TButton",
                   command=self._remove_history).pack(side="left", fill="x", expand=True,
                                                      padx=(self.px(6), 0))

        ttk.Separator(side).pack(fill="x", pady=self.px(10))

        ttk.Button(side, text="打开工坊页面", style="Ghost.TButton",
                   command=self._open_workshop).pack(fill="x", pady=(0, self.px(6)))
        ttk.Button(side, text="打开 Mod 目录", style="Ghost.TButton",
                   command=self._open_mod_dir).pack(fill="x")

        self.side_steamcmd_lbl = ttk.Label(side, text="", style="SideDim.TLabel",
                                           wraplength=self.px(210), justify="left")
        self.side_steamcmd_lbl.pack(anchor="w", pady=(self.px(12), 0))

        bottom = ttk.Frame(side, style="Side.TFrame")
        bottom.pack(fill="x", side="bottom", pady=(self.px(8), 0))
        ttk.Button(bottom, text="主题", style="Ghost.TButton", width=5,
                   command=self._toggle_theme).pack(side="left")
        ttk.Button(bottom, text="A−", style="Ghost.TButton", width=4,
                   command=lambda: self._adjust_font(-0.05)).pack(side="left",
                                                                  padx=(self.px(4), 0))
        ttk.Button(bottom, text="A＋", style="Ghost.TButton", width=4,
                   command=lambda: self._adjust_font(0.05)).pack(side="left",
                                                                 padx=(self.px(4), 0))
        ttk.Button(bottom, text="设置", style="Ghost.TButton",
                   command=self._open_settings).pack(side="left", fill="x", expand=True,
                                                     padx=(self.px(4), 0))

    # ---------- 卡片工具 ----------
    def _card(self, parent, title, subtitle=""):
        card = ttk.Frame(parent, style="Card.TFrame",
                         padding=(self.px(14), self.px(10), self.px(14), self.px(12)))
        card.pack(fill="x", padx=self.px(14), pady=(self.px(12), 0))
        head = ttk.Frame(card, style="Card.TFrame")
        head.pack(fill="x")
        ttk.Label(head, text=title, style="CardTitle.TLabel").pack(side="left")
        if subtitle:
            ttk.Label(head, text="    " + subtitle, style="CardDim.TLabel").pack(side="left")
        ttk.Separator(card, style="Card.TSeparator").pack(fill="x",
                                                          pady=(self.px(6), self.px(8)))
        body = ttk.Frame(card, style="Card.TFrame")
        body.pack(fill="x")
        return body

    # ---------- 卡片① Mod 选择 ----------
    def _build_card_mod(self, parent):
        body = self._card(parent, "① Mod 选择", "包含 descriptor.mod 的文件夹")

        body.columnconfigure(0, weight=1)
        body.columnconfigure(1, weight=0)

        left = ttk.Frame(body, style="Card.TFrame")
        left.grid(row=0, column=0, sticky="new")

        row = ttk.Frame(left, style="Card.TFrame")
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.mod_dir, font=self.F_BODY).pack(
            side="left", fill="x", expand=True, padx=(0, self.px(6)))
        ttk.Button(row, text="浏览...", command=self._browse_mod_dir).pack(side="left")
        ttk.Button(row, text="解析", command=lambda: self._parse_mod()).pack(
            side="left", padx=(self.px(6), 0))
        ttk.Button(row, text="打开目录", command=self._open_mod_dir).pack(
            side="left", padx=(self.px(6), 0))

        self.mod_info_lbl = ttk.Label(left, text="尚未解析 Mod。", style="Card.TLabel",
                                      justify="left", wraplength=self.px(560))
        self.mod_info_lbl.pack(fill="x", anchor="w", pady=(self.px(8), 0))

        self.mod_extra_lbl = ttk.Label(left, text="", style="CardDim.TLabel",
                                       justify="left", wraplength=self.px(560))
        self.mod_extra_lbl.pack(fill="x", anchor="w")

        self.mod_warn_lbl = ttk.Label(left, text="", style="CardWarn.TLabel",
                                      justify="left", wraplength=self.px(560))
        self.mod_warn_lbl.pack(fill="x", anchor="w")

        # 右侧：预览图缩略图
        right = ttk.Frame(body, style="Card.TFrame")
        right.grid(row=0, column=1, sticky="ne", padx=(self.px(12), 0))
        self.thumb_border = tk.Frame(right, highlightthickness=1, bd=0,
                                     highlightbackground=self.T["border"])
        self.thumb_border.pack()
        w, h = self.px(240), self.px(135)
        self.thumb_lbl = ttk.Label(self.thumb_border, text="未选择预览图",
                                   style="CardDim.TLabel", anchor="center", width=28)
        self.thumb_lbl.pack(ipadx=1, ipady=1)
        self.thumb_border.configure(width=w + 2, height=h + 2)
        self.thumb_border.pack_propagate(False)
        self.thumb_lbl.bind("<Button-1>", self._open_preview_file)
        self.preview_hint = ttk.Label(right, text="建议 1920×1080", style="CardDim.TLabel")
        self.preview_hint.pack(anchor="e", pady=(self.px(3), 0))

    # ---------- 卡片② Steam 账号 ----------
    def _build_card_account(self, parent):
        body = self._card(parent, "② Steam 账号", "需拥有 HOI4；之前登录过可直接用缓存登录")

        r0 = ttk.Frame(body, style="Card.TFrame")
        r0.pack(fill="x")
        ttk.Label(r0, text="账 号", style="Card.TLabel").pack(side="left")
        ttk.Entry(r0, textvariable=self.steam_user, width=22,
                  font=self.F_BODY).pack(side="left", padx=(self.px(8), self.px(18)))
        ttk.Label(r0, text="密 码", style="Card.TLabel").pack(side="left")
        self.pass_entry = ttk.Entry(r0, textvariable=self.steam_pass, width=22,
                                    show="●", font=self.F_BODY)
        self.pass_entry.pack(side="left", padx=(self.px(8), self.px(14)))
        ttk.Checkbutton(r0, text="记住密码（明文存于本机配置）", variable=self.remember_pass,
                        style="Card.TCheckbutton").pack(side="left")

        r1 = ttk.Frame(body, style="Card.TFrame")
        r1.pack(fill="x", pady=(self.px(8), 0))
        ttk.Label(r1, text="Steam Guard", style="Card.TLabel").pack(side="left")
        ttk.Entry(r1, textvariable=self.steam_guard, width=14,
                  font=self.F_BODY).pack(side="left", padx=(self.px(8), self.px(8)))
        ttk.Label(r1, text="首次登录时填写验证码，之后可留空", style="CardDim.TLabel").pack(side="left")
        self.test_btn = ttk.Button(r1, text="测试登录", command=self._test_login)
        self.test_btn.pack(side="right")

        ttk.Label(body, text="提示：不勾选记住密码时，密码只在本次运行中使用，不会写入配置文件；"
                             "已在本机登录过 SteamCMD 时可以不填密码。",
                  style="CardDim.TLabel", justify="left",
                  wraplength=self.px(640)).pack(fill="x", anchor="w", pady=(self.px(8), 0))

    # ---------- 卡片③ 创意工坊信息 ----------
    def _build_card_workshop(self, parent):
        body = self._card(parent, "③ 创意工坊信息", "标题 / 描述 / 预览图 / 可见性")
        body.columnconfigure(1, weight=1)

        def glabel(r, text, sticky="w"):
            ttk.Label(body, text=text, style="Card.TLabel").grid(
                row=r, column=0, sticky=sticky, padx=(0, self.px(10)),
                pady=(self.px(5), 0))

        # 标题
        glabel(0, "标 题")
        ttk.Entry(body, textvariable=self.mod_title, font=self.F_BODY).grid(
            row=0, column=1, sticky="ew", pady=(self.px(5), 0))

        # 预览图
        glabel(1, "预览图")
        row = ttk.Frame(body, style="Card.TFrame")
        row.grid(row=1, column=1, sticky="ew", pady=(self.px(5), 0))
        row.columnconfigure(0, weight=1)
        ttk.Entry(row, textvariable=self.preview_path,
                  font=self.F_BODY).grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="选择...", command=self._browse_preview).grid(
            row=0, column=1, padx=(self.px(6), 0))
        ttk.Button(row, text="清除", command=lambda: self.preview_path.set("")).grid(
            row=0, column=2, padx=(self.px(6), 0))

        # 可见性 + 更新说明
        glabel(2, "可见性")
        row = ttk.Frame(body, style="Card.TFrame")
        row.grid(row=2, column=1, sticky="ew", pady=(self.px(5), 0))
        for val, text in VISIBILITY_MAP.items():
            ttk.Radiobutton(row, text=text, variable=self.visibility, value=val,
                            style="Card.TRadiobutton").pack(side="left", padx=(0, self.px(14)))
        ttk.Label(row, text="更新说明", style="Card.TLabel").pack(side="left",
                                                                 padx=(self.px(10), self.px(8)))
        self.changenote_combo = ttk.Combobox(row, textvariable=self.changenote,
                                             font=self.F_BODY, width=30)
        self.changenote_combo.pack(side="left", fill="x", expand=True)
        if self.changenote_history:
            self.changenote_combo["values"] = self.changenote_history

        # 描述
        glabel(3, "描 述", sticky="nw")
        wrap = ttk.Frame(body, style="Card.TFrame")
        wrap.grid(row=3, column=1, sticky="ew", pady=(self.px(5), 0))
        wrap.columnconfigure(0, weight=1)
        self.desc_text = tk.Text(wrap, height=5, wrap="word", font=self.F_BODY,
                                 relief="flat", bd=0, padx=self.px(6), pady=self.px(4))
        self.desc_text.grid(row=0, column=0, sticky="ew")
        dsb = ttk.Scrollbar(wrap, orient="vertical", command=self.desc_text.yview)
        self.desc_text.configure(yscrollcommand=dsb.set)
        dsb.grid(row=0, column=1, sticky="ns")

        # 已发布 ID
        glabel(4, "已发布ID")
        row = ttk.Frame(body, style="Card.TFrame")
        row.grid(row=4, column=1, sticky="ew", pady=(self.px(5), 0))
        ttk.Entry(row, textvariable=self.published_id, width=16,
                  font=self.F_BODY).pack(side="left")
        ttk.Label(row, text="0 = 新建发布；上传成功后自动回填，更新时无需改动",
                  style="CardDim.TLabel").pack(side="left", padx=(self.px(10), 0))
        self.copy_btn = ttk.Button(row, text="复制工坊链接", command=self._copy_link)
        self.copy_btn.pack(side="right")

    # ==========================================================
    # 鼠标滚轮（主滚动区）
    # ==========================================================
    def _bind_wheel(self):
        def on_wheel(e):
            try:
                w = self.root.winfo_containing(e.x_root, e.y_root)
            except Exception:
                return
            while w is not None:
                if w is self.main_canvas:
                    self.main_canvas.yview_scroll(-2 if e.delta > 0 else 2, "units")
                    return
                if isinstance(w, (tk.Text, ttk.Treeview, tk.Listbox)):
                    return   # 自带滚动的控件交给它们自己
                if isinstance(w, ttk.Combobox):
                    return
                w = getattr(w, "master", None)
        self.root.bind_all("<MouseWheel>", on_wheel, add="+")

    # ==========================================================
    # 浏览 & 解析
    # ==========================================================
    def _browse_mod_dir(self):
        initial = self.mod_dir.get() or DEFAULT_HOI4_MOD_DIR
        d = filedialog.askdirectory(title="选择 Mod 目录", initialdir=initial)
        if d:
            self.mod_dir.set(d)
            self._parse_mod()

    def _browse_preview(self):
        f = filedialog.askopenfilename(
            title="选择预览图",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.gif"), ("所有文件", "*.*")])
        if f:
            self.preview_path.set(f)

    def _open_preview_file(self, e=None):
        p = self.preview_path.get().strip()
        if p and os.path.isfile(p):
            try:
                os.startfile(p)
            except Exception:
                pass

    def _parse_mod(self, quiet: bool = False):
        d = self.mod_dir.get().strip()
        if not d or not os.path.isdir(d):
            if not quiet:
                messagebox.showwarning("提示", "请先选择有效的 Mod 目录", parent=self.root)
            return

        info = parse_descriptor(d)
        self._last_info = info
        if info["name"]:
            self.mod_title.set(info["name"])
        tags_str = "、".join(info["tags"]) if info["tags"] else "无"
        self.mod_info_lbl.config(
            text=f"名称：{info['name'] or '（未找到）'}        版本：{info['version'] or '（未指定）'}\n"
                 f"支持游戏版本：{info['supported_version'] or '（未指定）'}        标签：{tags_str}")
        self._log(f"[解析] {d}")
        self._log(f"[解析] 名称={info['name']} 版本={info['version']} 标签={info['tags']}", "dim")

        # 自动找预览图
        if not self.preview_path.get():
            for fname in ("thumbnail.png", "thumbnail.jpg", "preview.png", "preview.jpg"):
                p = os.path.join(d, fname)
                if os.path.isfile(p):
                    self.preview_path.set(p)
                    break

        # 加载该 Mod 对应的已发布 ID
        self._load_pid(d)

        # Mod 大小 + 游戏版本核对（后台线程，避免卡界面）
        threading.Thread(target=self._bg_scan_mod, args=(d,), daemon=True).start()

    def _load_pid(self, mod_dir: str):
        mod_ids = self._read_config_file().get("published_ids", {}) or {}
        pid = mod_ids.get(mod_dir)
        if pid is None:
            key = path_key(mod_dir)
            for k, v in mod_ids.items():
                if path_key(k) == key:
                    pid = v
                    break
        self.published_id.set(str(pid) if pid not in (None, "") else "0")

    def _bg_scan_mod(self, d):
        total, count = 0, 0
        try:
            for r, dirs, files in os.walk(d):
                for f in files:
                    try:
                        total += os.path.getsize(os.path.join(r, f))
                        count += 1
                    except OSError:
                        pass
        except Exception:
            pass
        gv = find_hoi4_game_version()
        try:
            self.root.after(0, lambda: self._mod_scan_done(d, total, count, gv))
        except Exception:
            pass

    def _mod_scan_done(self, d, total, count, game_version):
        if path_key(d) != path_key(self.mod_dir.get()):
            return   # 用户已切换到其他 Mod，丢弃过期结果

        extra = [f"Mod 大小：{human_size(total)}（{count} 个文件）"]
        sup = self._last_info.get("supported_version", "")
        if game_version:
            extra.append(f"本机游戏版本：{game_version}")
        self.mod_extra_lbl.config(text="      ·      ".join(extra))

        warns = []
        if version_mismatch(sup, game_version or ""):
            warns.append(f"⚠ Mod 声明支持 {sup}，与本机游戏版本 {game_version} 的大小版本不一致，"
                         f"玩家侧可能提示不兼容。")
        if has_non_ascii(d):
            warns.append("⚠ Mod 目录路径包含中文/非 ASCII 字符，SteamCMD 可能上传失败，"
                         "建议将 Mod 移到纯英文路径。")
        preview = self.preview_path.get().strip()
        if preview and has_non_ascii(preview):
            warns.append("⚠ 预览图路径包含中文/非 ASCII 字符，可能上传失败。")
        self.mod_warn_lbl.config(text="\n".join(warns))

    # ---------- 预览图缩略图 ----------
    def _on_preview_changed(self, *args):
        p = self.preview_path.get().strip()
        self._thumb_img = None
        dims = ""
        if p and os.path.isfile(p):
            tw, th = self.px(240), self.px(135)
            try:
                from PIL import Image, ImageTk   # 可选依赖
                im = Image.open(p)
                dims = f"{im.width}×{im.height}"
                ratio = min(tw / im.width, th / im.height)
                im = im.resize((max(1, int(im.width * ratio)),
                                max(1, int(im.height * ratio))))
                self._thumb_img = ImageTk.PhotoImage(im)
            except ImportError:
                try:
                    img = tk.PhotoImage(file=p)
                    dims = f"{img.width()}×{img.height()}"
                    fx = max(1, img.width() // tw + (1 if img.width() % tw else 0))
                    fy = max(1, img.height() // th + (1 if img.height() % th else 0))
                    img = img.subsample(max(fx, fy))
                    self._thumb_img = img
                except Exception:
                    self._thumb_img = None
            except Exception:
                self._thumb_img = None

            try:
                size = os.path.getsize(p)
                size_str = human_size(size)
            except OSError:
                size, size_str = 0, ""
        else:
            size, size_str = 0, ""

        if self._thumb_img is not None:
            self.thumb_lbl.configure(image=self._thumb_img, text="")
        else:
            self.thumb_lbl.configure(image="", text="未选择预览图\n（PNG / JPG）")

        hint = f"{dims}  ·  {size_str}" if dims else ("建议 1920×1080" if not p else "无法预览此格式")
        warn_style = size > PREVIEW_WARN_BYTES
        self.preview_hint.configure(
            text=(hint + "  ⚠ 超过 1MB，可能上传失败" if warn_style else hint))
        if warn_style:
            self.preview_hint.configure(foreground=self.T["warn"])
        else:
            self.preview_hint.configure(foreground=self.T["dim"])

    # ==========================================================
    # Mod 历史记录
    # ==========================================================
    def _refresh_history(self):
        tree = self.history_tree
        sel_key = path_key(tree.selection()[0]) if tree.selection() else None
        items = tree.get_children()
        if items:
            tree.delete(*items)

        entries = list(self._read_config_file().get("published_ids", {}).items())
        cur = self.mod_dir.get().strip()
        have_cur = False

        def add_item(key, pid):
            name = os.path.basename(key.rstrip("\\/")) or key
            exists = os.path.isdir(key)
            if exists:
                info = parse_descriptor(key)
                if info["name"]:
                    name = info["name"]
            suffix = f"ID {pid}" if str(pid) not in ("", "0") else "未上传"
            if not exists:
                suffix += "  （目录不存在）"
            tree.insert("", "end", iid=key, text=f" {name}\n {suffix}", open=False)

        for k, v in entries:
            add_item(k, v)
            if cur and path_key(k) == path_key(cur):
                have_cur = True
        if cur and not have_cur:
            add_item(cur, self.published_id.get())

        # 恢复选中
        if sel_key:
            for iid in tree.get_children():
                if path_key(iid) == sel_key:
                    tree.selection_set(iid)
                    break
        elif cur:
            for iid in tree.get_children():
                if path_key(iid) == path_key(cur):
                    tree.selection_set(iid)
                    break

    def _on_history_select(self, e=None):
        if not self._ui_ready:
            return
        sel = self.history_tree.selection()
        if not sel:
            return
        d = sel[0]
        if path_key(d) == path_key(self.mod_dir.get()):
            return
        self.mod_dir.set(d)
        self._parse_mod(quiet=True)
        self._log(f"[历史] 载入 Mod：{d}", "dim")

    def _remove_history(self):
        sel = self.history_tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先在左侧列表中选择一个 Mod 记录", parent=self.root)
            return
        key = sel[0]
        name = os.path.basename(key.rstrip("\\/"))
        if not messagebox.askyesno(
                "确认移除",
                f"确定移除「{name}」的上传记录吗？\n\n"
                "仅删除本工具里的 ID 映射记录，不会删除本地 Mod 文件，"
                "也不会删除 Steam 创意工坊上的物品。",
                parent=self.root):
            return
        cfg = self._read_config_file()
        pids = dict(cfg.get("published_ids", {}) or {})
        pids.pop(key, None)
        self._patch_config({"published_ids": pids})
        if path_key(key) == path_key(self.mod_dir.get()):
            self.published_id.set("0")
        self._refresh_history()
        self._log(f"[历史] 已移除记录：{key}", "dim")

    # ==========================================================
    # 快捷操作
    # ==========================================================
    def _update_link_buttons(self):
        has = self.published_id.get().strip() not in ("", "0")
        self.copy_btn.configure(state="normal" if has else "disabled")

    def _open_workshop(self):
        pid = self.published_id.get().strip()
        if not pid or pid == "0":
            messagebox.showinfo("提示", "当前 Mod 还没有已发布 ID（尚未上传过）。",
                                parent=self.root)
            return
        try:
            os.startfile(f"https://steamcommunity.com/sharedfiles/filedetails/?id={pid}")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开浏览器：{e}", parent=self.root)

    def _open_mod_dir(self):
        d = self.mod_dir.get().strip()
        if d and os.path.isdir(d):
            try:
                os.startfile(d)
            except Exception:
                pass
        else:
            messagebox.showwarning("提示", "Mod 目录不存在或未选择", parent=self.root)

    def _copy_link(self):
        pid = self.published_id.get().strip()
        if not pid or pid == "0":
            return
        url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={pid}"
        self.root.clipboard_clear()
        self.root.clipboard_append(url)
        self.status_var.set("已复制工坊链接：" + url)

    # ==========================================================
    # SteamCMD 检测 & 下载
    # ==========================================================
    def _detect_steamcmd(self):
        if self.steamcmd_path.get() and os.path.isfile(self.steamcmd_path.get()):
            self._check_steamcmd()
            return
        steam_dir = find_steam_installation()
        if steam_dir:
            candidate = os.path.join(steam_dir, "steamcmd.exe")
            if os.path.isfile(candidate):
                self.steamcmd_path.set(candidate)
                return
        self._check_steamcmd()

    def _check_steamcmd(self):
        p = self.steamcmd_path.get().strip()
        if p and os.path.isfile(p):
            self.side_steamcmd_lbl.configure(
                text=f"SteamCMD：✓ 已就绪", foreground=self.T["success"])
            if self._steamcmd_status_lbl is not None and self._steamcmd_status_lbl.winfo_exists():
                self._steamcmd_status_lbl.configure(
                    text=f"✓ SteamCMD 已就绪：{p}", foreground=self.T["success"])
            self.status_var.set("SteamCMD 已就绪：" + p)
        else:
            self.side_steamcmd_lbl.configure(
                text="SteamCMD：⚠ 未找到（可在设置中下载或指定）", foreground=self.T["warn"])
            if self._steamcmd_status_lbl is not None and self._steamcmd_status_lbl.winfo_exists():
                self._steamcmd_status_lbl.configure(
                    text="⚠ 未找到 SteamCMD，可点「自动下载」或「浏览」指定",
                    foreground=self.T["warn"])

    _steamcmd_status_lbl = None

    def _browse_steamcmd(self):
        f = filedialog.askopenfilename(title="选择 steamcmd.exe",
                                       filetypes=[("SteamCMD", "steamcmd.exe"),
                                                  ("可执行文件", "*.exe")])
        if f:
            self.steamcmd_path.set(f)

    def _download_steamcmd(self):
        if self._steamcmd_downloading:
            return
        self._steamcmd_downloading = True
        self.status_var.set("正在下载 SteamCMD...")

        def worker():
            try:
                tool_dir = STEAMCMD_DIR
                os.makedirs(tool_dir, exist_ok=True)
                zip_path = os.path.join(tool_dir, "steamcmd.zip")
                self._log(f"[下载] 从 {STEAMCMD_ZIP_URL} 下载 SteamCMD...")
                urllib.request.urlretrieve(STEAMCMD_ZIP_URL, zip_path)
                self._log("[下载] 解压中...")
                with zipfile.ZipFile(zip_path, "r") as z:
                    z.extractall(tool_dir)
                os.remove(zip_path)
                exe = os.path.join(tool_dir, "steamcmd.exe")
                if os.path.isfile(exe):
                    self.root.after(0, lambda: self.steamcmd_path.set(exe))
                    self._log(f"[下载] 完成：{exe}")
                    self.root.after(0, lambda: self.status_var.set("SteamCMD 下载完成"))
                else:
                    self._log("[下载] 错误：未找到 steamcmd.exe", "error")
            except Exception as e:
                self._log(f"[下载] 失败：{e}", "error")
                self.root.after(0, lambda: messagebox.showerror(
                    "下载失败", str(e), parent=self.root))
            finally:
                self._steamcmd_downloading = False

        threading.Thread(target=worker, daemon=True).start()

    # ==========================================================
    # 上传 & 登录测试
    # ==========================================================
    def _set_busy(self, busy: bool, phase: str = ""):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.upload_btn.configure(state=state)
        self.test_btn.configure(state=state)
        self.stop_btn.configure(state="normal" if busy else "disabled")
        if busy:
            self.progress.start(12)
        else:
            self.progress.stop()
        self._set_phase(phase or "就绪")

    def _set_phase(self, text: str):
        self.phase_lbl.configure(text=text)
        self.status_var.set(text)

    def _test_login(self):
        if self.busy:
            return
        steamcmd = self.steamcmd_path.get().strip()
        if not steamcmd or not os.path.isfile(steamcmd):
            messagebox.showwarning("提示", "请先在设置中指定有效的 steamcmd.exe",
                                   parent=self.root)
            return
        user = self.steam_user.get().strip()
        if not user:
            messagebox.showwarning("提示", "请输入 Steam 账号", parent=self.root)
            return

        cmd = [steamcmd, "+login", user]
        password = self.steam_pass.get()
        if password:
            cmd.append(password)
        guard = self.steam_guard.get().strip()
        if guard:
            cmd.append(guard)
        cmd.append("+quit")

        self._log("=" * 62)
        self._log(f"[登录测试] 账号：{user}（不上传任何内容）")
        self._set_busy(True, "正在测试登录...")

        def worker():
            saw_error = False
            try:
                exe = cmd[0]
                si, cf = self._hide_window_kwargs()
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, encoding="utf-8", errors="replace",
                                     bufsize=1, cwd=os.path.dirname(exe) or None,
                                     startupinfo=si, creationflags=cf)
                self.process = p
                for line in p.stdout:
                    line = line.rstrip()
                    if not line:
                        continue
                    tag = self._classify_line(line)
                    if tag == "error":
                        saw_error = True
                    self._log(line, tag)
                p.wait()
                rc = p.returncode
                ok = (rc == 0 and not saw_error)
                self._log("-" * 62)
                if ok:
                    self._log("[登录测试] ✓ 登录成功，账号可用", "success")
                else:
                    self._log(f"[登录测试] ✗ 未通过（退出码 {rc}），详见上方日志", "error")
                self.root.after(0, lambda: self._set_phase(
                    "登录测试通过 ✓" if ok else "登录测试未通过 ✗（详见日志）"))
            except Exception as e:
                self._log(f"[异常] {e}", "error")
            finally:
                self.process = None
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _start_upload(self):
        if self.busy:
            return

        # ---- 前置校验 ----
        mod_dir = self.mod_dir.get().strip()
        if not mod_dir or not os.path.isdir(mod_dir):
            messagebox.showwarning("提示", "请选择有效的 Mod 目录", parent=self.root)
            return
        desc_file = os.path.join(mod_dir, "descriptor.mod")
        if not os.path.isfile(desc_file):
            if not any(f.endswith(".mod") for f in os.listdir(mod_dir)):
                if not messagebox.askyesno(
                        "确认", "该目录下未找到 descriptor.mod，可能不是有效的 HOI4 Mod 目录。\n仍然继续上传吗？",
                        parent=self.root):
                    return

        steamcmd = self.steamcmd_path.get().strip()
        if not steamcmd or not os.path.isfile(steamcmd):
            messagebox.showwarning("提示", "请先在「设置」中指定有效的 steamcmd.exe",
                                   parent=self.root)
            return

        user = self.steam_user.get().strip()
        password = self.steam_pass.get()
        if not user:
            messagebox.showwarning("提示", "请输入 Steam 账号", parent=self.root)
            return
        if not password:
            if not messagebox.askyesno(
                    "确认", "未输入密码。如果之前在本工具登录过且登录态仍有效，可继续。\n是否继续？",
                    parent=self.root):
                return

        title = self.mod_title.get().strip()
        if not title:
            messagebox.showwarning("提示", "请输入 Mod 标题", parent=self.root)
            return

        preview = self.preview_path.get().strip()
        if preview and not os.path.isfile(preview):
            messagebox.showwarning("提示", "预览图文件不存在", parent=self.root)
            return
        if preview and os.path.isfile(preview) and os.path.getsize(preview) > PREVIEW_WARN_BYTES:
            if not messagebox.askyesno(
                    "确认", f"预览图为 {human_size(os.path.getsize(preview))}，超过 Steam 常见的 1MB 限制，"
                            "可能上传失败。\n仍然继续吗？", parent=self.root):
                return
        if has_non_ascii(mod_dir) or (preview and has_non_ascii(preview)):
            if not messagebox.askyesno(
                    "确认", "Mod 目录或预览图路径包含中文/非 ASCII 字符，SteamCMD 可能无法处理。\n仍然继续吗？",
                    parent=self.root):
                return

        pid = self.published_id.get().strip() or "0"
        is_update = pid != "0"
        action = "更新" if is_update else "新建"

        # ---- 生成 VDF ----
        vdf_path = os.path.join(STEAMCMD_DIR, "upload_workshop.vdf")
        description = self.desc_text.get("1.0", "end").strip()
        changenote = self.changenote.get().strip() or (
            f"Update {title}" if is_update else "Initial upload")

        try:
            generate_vdf(vdf_path, mod_dir, preview, title, description,
                         self.visibility.get(), changenote, pid)
        except Exception as e:
            messagebox.showerror("错误", f"生成 VDF 失败: {e}", parent=self.root)
            return

        # ---- 记录更新说明历史 ----
        if changenote:
            if changenote in self.changenote_history:
                self.changenote_history.remove(changenote)
            self.changenote_history.insert(0, changenote)
            self.changenote_history = self.changenote_history[:10]
            self.changenote_combo["values"] = self.changenote_history

        self._log("=" * 62)
        self._log(f"[上传] 模式：{action}  |  AppID: {HOI4_APP_ID}  |  PublishedID: {pid}")
        self._log(f"[上传] Mod：{title}")
        self._log(f"[上传] VDF：{vdf_path}", "dim")
        self._log("-" * 62)

        # ---- 构建 steamcmd 命令 ----
        cmd = [steamcmd, "+login", user]
        if password:
            cmd.append(password)
        guard = self.steam_guard.get().strip()
        if guard:
            cmd.append(guard)
        cmd.extend(["+workshop_build_item", vdf_path, "+quit"])

        self._set_busy(True, f"正在{action} Mod...")

        def worker():
            try:
                rc = self._exec_stream(cmd)
                self._handle_upload_result(rc, vdf_path, is_update, title)
            except Exception as e:
                self._log(f"[异常] {e}", "error")
                self.root.after(0, lambda: messagebox.showerror(
                    "执行异常", str(e), parent=self.root))
            finally:
                self.process = None
                self.root.after(0, lambda: self._set_busy(False))

        threading.Thread(target=worker, daemon=True).start()

    def _hide_window_kwargs(self):
        si, cf = None, 0
        if os.name == "nt":
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            cf = subprocess.CREATE_NO_WINDOW
        return si, cf

    def _exec_stream(self, cmd) -> int:
        """执行 steamcmd 并把输出实时送入日志面板"""
        si, cf = self._hide_window_kwargs()
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", bufsize=1,
                             cwd=os.path.dirname(cmd[0]) or None,
                             startupinfo=si, creationflags=cf)
        self.process = p
        for line in p.stdout:
            line = line.rstrip()
            if line:
                self._feed_line(line)
        p.wait()
        return p.returncode

    @staticmethod
    def _classify_line(line: str) -> Optional[str]:
        low = line.lower()
        if "error" in low or "failure" in low or "failed" in low:
            return "error"
        if "success" in low:
            return "success"
        if "warning" in low or "retrying" in low:
            return "warn"
        prefixes = ("connecting", "logging in", "waiting", "redirecting",
                    "updatestate", "shutdown", "getting", "verifying",
                    "loading", "setstagingfolder", "dlcs")
        if low.startswith(prefixes) or low.startswith("[----]"):
            return "dim"
        return None

    def _feed_line(self, line: str):
        low = line.lower()
        if "logging in" in low:
            self.root.after(0, lambda: self._set_phase("正在登录 Steam..."))
        elif "login failure" in low or "invalid password" in low:
            self.root.after(0, lambda: self._set_phase("登录失败"))
        elif "workshop_build_item" in low or ("upload" in low and "success" not in low):
            self.root.after(0, lambda: self._set_phase("正在上传 Mod 内容（大小决定耗时）..."))
        elif "success" in low and ("item" in low or "uploaded" in low):
            self.root.after(0, lambda: self._set_phase("上传完成，等待 Steam 确认..."))
        tag = self._classify_line(line)
        self._log(line, tag)

    def _handle_upload_result(self, rc, vdf_path, is_update, title):
        self._log("-" * 62)
        self._log(f"[SteamCMD] 退出码: {rc}")
        if rc == 0:
            new_id = read_published_id_from_vdf(vdf_path)
            if new_id and new_id != "0":
                url = f"https://steamcommunity.com/sharedfiles/filedetails/?id={new_id}"
                self._log(f"[成功] PublishedFileID: {new_id}", "success")
                self._log(f"[成功] 创意工坊链接: {url}", "success")

                def done():
                    self.published_id.set(new_id)
                    self.save_all()
                    self._refresh_history()
                    self.status_var.set("上传成功 ✓  " + url)
                    if self.open_after.get():
                        try:
                            os.startfile(url)
                        except Exception:
                            pass
                        return
                    if messagebox.askyesno(
                            "上传成功",
                            f"{'更新' if is_update else '发布'}成功！\n\n"
                            f"PublishedFileID: {new_id}\n"
                            f"链接: {url}\n\n"
                            f"（ID 已自动保存，下次直接点上传即可更新）\n\n"
                            f"是否现在打开工坊页面？",
                            parent=self.root):
                        try:
                            os.startfile(url)
                        except Exception:
                            pass
                self.root.after(0, done)
            else:
                self._log("[警告] 退出码为0但未读取到 PublishedFileID，请检查上方日志", "warn")
                self.root.after(0, lambda: messagebox.showwarning(
                    "可能成功", "SteamCMD 退出码为0，但未能从 VDF 中读取到 PublishedFileID。\n请查看日志确认。",
                    parent=self.root))
        else:
            self._log("[失败] SteamCMD 返回非零退出码，请检查上方日志中的错误信息", "error")
            self.root.after(0, lambda: messagebox.showerror(
                "上传失败",
                "SteamCMD 返回非零退出码。\n请查看底部「运行日志」中的详细错误信息。\n\n"
                "常见原因：账号密码错误、Steam Guard 验证失败、网络问题、Mod 目录无效。",
                parent=self.root))

    def _stop_upload(self):
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass
            self._log("[终止] 已终止 SteamCMD 进程", "warn")
            self._set_phase("已终止")

    # ==========================================================
    # 日志
    # ==========================================================
    def _log(self, msg: str, tag: Optional[str] = None):
        def _append():
            self.log_text.configure(state="normal")
            if tag:
                self.log_text.insert("end", msg + "\n", tag)
            else:
                self.log_text.insert("end", msg + "\n")
            # 只保留最近 2000 行，避免长会话内存膨胀
            if int(self.log_text.index("end-1c").split(".")[0]) > 2000:
                self.log_text.delete("1.0", "500.0")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        try:
            self.root.after(0, _append)
        except Exception:
            pass
        # 同步写入本地日志文件
        try:
            if self._log_fh is None:
                log_dir = os.path.join(self._tool_dir(), LOG_DIR)
                os.makedirs(log_dir, exist_ok=True)
                fname = datetime.date.today().strftime("uploader_%Y%m%d.log")
                self._log_fh = open(os.path.join(log_dir, fname), "a", encoding="utf-8")
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            self._log_fh.write(f"[{ts}] {msg}\n")
            self._log_fh.flush()
        except Exception:
            pass

    def _set_log(self, text: str):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        if text:
            self.log_text.insert("end", text)
        self.log_text.configure(state="disabled")

    def _export_log(self):
        content = self.log_text.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("提示", "当前日志为空", parent=self.root)
            return
        default = datetime.datetime.now().strftime("upload_log_%Y%m%d_%H%M%S.txt")
        f = filedialog.asksaveasfilename(
            title="导出日志", defaultextension=".txt", initialfile=default,
            filetypes=[("文本文件", "*.txt")], parent=self.root)
        if f:
            try:
                with open(f, "w", encoding="utf-8") as fh:
                    fh.write(content + "\n")
                self.status_var.set("日志已导出：" + f)
            except Exception as e:
                messagebox.showerror("错误", f"导出失败：{e}", parent=self.root)

    # ==========================================================
    # 主题 / 字号 / 设置
    # ==========================================================
    def _toggle_theme(self):
        self.theme_name = "light" if self.theme_name == "dark" else "dark"
        self.theme_var.set(self.theme_name)
        self._apply_theme()
        self._check_steamcmd()
        self.save_all()

    def _adjust_font(self, delta: float):
        self._font_scale = min(1.5, max(0.8, self._font_scale + delta))
        self.font_scale.set(self._font_scale)
        self._apply_font_scale()
        self.save_all()

    _settings_win = None

    def _open_settings(self):
        if self._settings_win is not None and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_force()
            return

        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title("设置")
        win.configure(bg=self.T["bg"])
        self._set_win_icon(win)
        win.transient(self.root)
        win.resizable(False, True)
        win.grab_set()

        body = ttk.Frame(win, style="Main.TFrame", padding=self.px(16))
        body.pack(fill="both", expand=True)

        def section(text):
            ttk.Label(body, text=text, style="Title.TLabel",
                      background=self.T["bg"]).pack(anchor="w", pady=(self.px(6), self.px(4)))
            ttk.Separator(body).pack(fill="x", pady=(0, self.px(6)))

        # ---- SteamCMD ----
        section("SteamCMD")
        row = ttk.Frame(body, style="Main.TFrame")
        row.pack(fill="x")
        ttk.Entry(row, textvariable=self.steamcmd_path,
                  font=self.F_BODY).pack(side="left", fill="x", expand=True,
                                         padx=(0, self.px(6)))
        ttk.Button(row, text="浏览...", command=self._browse_steamcmd).pack(side="left")
        ttk.Button(row, text="自动下载",
                   command=self._download_steamcmd).pack(side="left", padx=(self.px(6), 0))
        self._steamcmd_status_lbl = ttk.Label(body, text="", style="Dim.TLabel",
                                              wraplength=self.px(480), justify="left")
        self._steamcmd_status_lbl.pack(fill="x", anchor="w", pady=(self.px(4), 0))
        self._check_steamcmd()
        ttk.Label(body, text="SteamCMD 需放在纯英文路径下（默认 E:\\SteamCMD），"
                             "VDF 也会写到该目录。",
                  style="Dim.TLabel", wraplength=self.px(480),
                  justify="left").pack(fill="x", anchor="w")

        # ---- 窗口 ----
        section("窗口")
        row = ttk.Frame(body, style="Main.TFrame")
        row.pack(fill="x")
        ttk.Checkbutton(row, text="记住窗口大小和位置", variable=self.win_remember,
                        command=self.save_all).pack(side="left")
        ttk.Label(row, text="尺寸预设", style="TLabel").pack(side="left",
                                                            padx=(self.px(20), self.px(6)))
        preset = ttk.Combobox(row, state="readonly", width=16, font=self.F_BODY,
                              values=["跟随上次窗口大小", "1180 × 800", "1360 × 880",
                                      "1600 × 1000", "1920 × 1080", "最大化"])
        preset.current(0)
        preset.pack(side="left")

        def apply_preset():
            val = preset.get()
            sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
            try:
                if "最大化" in val:
                    self.root.state("zoomed")
                elif "×" in val:
                    w, h = [int(x.strip()) for x in val.split("×")]
                    m = re.match(r"(\d+)x(\d+)\+(-?\d+)\+(-?\d+)", self.root.winfo_geometry())
                    x = int(m.group(3)) if m else max(0, (sw - w) // 2)
                    y = int(m.group(4)) if m else max(0, (sh - h) // 2)
                    self.root.state("normal")
                    self.root.geometry(f"{min(w, sw - 20)}x{min(h, sh - 40)}+{x}+{y}")
                self.save_all()
                self.status_var.set("窗口尺寸已应用：" + val)
            except Exception as e:
                messagebox.showerror("错误", str(e), parent=win)

        ttk.Button(row, text="应用", command=apply_preset).pack(side="left",
                                                                padx=(self.px(6), 0))

        # ---- 外观 ----
        section("外观")
        row = ttk.Frame(body, style="Main.TFrame")
        row.pack(fill="x")
        ttk.Radiobutton(row, text="深色主题", value="dark", variable=self.theme_var,
                        command=self._on_theme_radio).pack(side="left")
        ttk.Radiobutton(row, text="浅色主题", value="light", variable=self.theme_var,
                        command=self._on_theme_radio).pack(side="left", padx=(0, self.px(20)))
        ttk.Label(row, text="界面字号", style="TLabel").pack(side="left",
                                                            padx=(0, self.px(6)))
        spin = ttk.Spinbox(row, from_=0.8, to=1.5, increment=0.05, width=6,
                           textvariable=self.font_scale, font=self.F_BODY,
                           command=lambda: self._on_font_spin())
        spin.pack(side="left")
        spin.bind("<Return>", lambda e: self._on_font_spin())
        spin.bind("<FocusOut>", lambda e: self._on_font_spin())

        # ---- 上传偏好 ----
        section("上传偏好")
        ttk.Checkbutton(body, text="上传成功后自动打开工坊页面", variable=self.open_after,
                        command=self.save_all).pack(anchor="w")

        # ---- 数据 ----
        section("数据")
        row = ttk.Frame(body, style="Main.TFrame")
        row.pack(fill="x")
        ttk.Button(row, text="打开配置文件", style="TButton",
                   command=lambda: self._startfile(self._config_path())).pack(side="left")
        ttk.Button(row, text="打开程序目录", style="TButton",
                   command=lambda: self._startfile(self._tool_dir())).pack(
            side="left", padx=(self.px(6), 0))
        ttk.Button(row, text="关于", style="TButton",
                   command=self._about).pack(side="left", padx=(self.px(6), 0))
        ttk.Label(body, text="配置与登录数据保存在 uploader_config.json（写入前自动备份到 "
                             "uploader_config.backup.json）。",
                  style="Dim.TLabel", wraplength=self.px(480),
                  justify="left").pack(fill="x", anchor="w", pady=(self.px(4), 0))

        ttk.Button(body, text="关闭", command=win.destroy).pack(pady=(self.px(10), 0))
        win.bind("<Escape>", lambda e: win.destroy())

        # 居中于主窗口
        win.update_idletasks()
        try:
            px_, py_ = self.root.winfo_rootx(), self.root.winfo_rooty()
            pw, ph = self.root.winfo_width(), self.root.winfo_height()
            ww, wh = win.winfo_width(), win.winfo_height()
            win.geometry(f"+{px_ + (pw - ww) // 2}+{py_ + (ph - wh) // 2}")
        except Exception:
            pass

    def _startfile(self, path):
        try:
            os.startfile(path)
        except Exception as e:
            messagebox.showerror("错误", str(e), parent=self.root)

    def _on_theme_radio(self):
        if self.theme_var.get() != self.theme_name:
            self.theme_name = self.theme_var.get()
            self._apply_theme()
            self._check_steamcmd()
            self.save_all()

    def _on_font_spin(self):
        try:
            val = float(self.font_scale.get())
        except (TypeError, ValueError):
            return
        val = min(1.5, max(0.8, val))
        if abs(val - self._font_scale) < 1e-6:
            return
        self._font_scale = val
        self._apply_font_scale()
        self.save_all()

    def _about(self):
        messagebox.showinfo(
            "关于",
            "HOI4 Mod 创意工坊上传工具 v2.0\n\n"
            "绕过 Paradox 启动器，直接调用 SteamCMD 上传 Mod 到创意工坊。\n"
            "HOI4 AppID: 394360\n\n"
            "数据文件：\n"
            "· uploader_config.json —— 账号 / 历史 ID / 偏好\n"
            "· uploader_config.backup.json —— 首次升级时的原始备份\n"
            "· logs\\ —— 每日运行日志\n\n"
            "详细说明见同目录 README.md。",
            parent=self.root)

    # ==========================================================
    # 关闭
    # ==========================================================
    def _on_close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("确认", "任务正在进行中，确定要退出吗？",
                                       parent=self.root):
                return
            try:
                self.process.terminate()
            except Exception:
                pass
        self.save_all()
        try:
            if self._log_fh:
                self._log_fh.close()
                self._log_fh = None
        except Exception:
            pass
        self.root.destroy()


# ============================================================
# 入口
# ============================================================
def main():
    dpi_scale = 1.0
    if os.name == "nt":
        try:
            from ctypes import windll
            try:
                windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
            try:
                dpi = windll.user32.GetDpiForSystem()
            except Exception:
                try:
                    hdc = windll.user32.GetDC(0)
                    dpi = windll.gdi32.GetDeviceCaps(hdc, 88)   # LOGPIXELSY
                    windll.user32.ReleaseDC(0, hdc)
                except Exception:
                    dpi = 96
            dpi_scale = dpi / 96.0
        except Exception:
            pass

    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", dpi_scale * 96 / 72.0)
    except Exception:
        pass

    app = HOI4ModUploaderApp(root, dpi_scale)
    root.mainloop()


if __name__ == "__main__":
    main()
