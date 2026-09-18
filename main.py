import os, sys, json, re, shutil, struct, glob, time, threading, subprocess
import socket, socketserver, select
import tempfile, ctypes
import tkinter as tk
from tkinter import messagebox
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Tuple, List

import customtkinter as ctk
import requests
import psutil

APP_NAME = "DiscordCrack"
APP_VERSION = "1.0"
DISCORD_LOCAL = Path(os.environ.get("LOCALAPPDATA", "C:/Users/PC/AppData/Local")) / "Discord"
BACKUP_SUFFIX = ".original_backup"

QUALITY_PATCHES: List[Tuple[str, str, str]] = [
    ("canUseHighVideoFPS",
     r"canUseHighVideoFPS\s*\(\s*\)\s*\{[^}]{0,200}\}",
     "canUseHighVideoFPS(){return true}"),
    ("canUseHighVideoQuality",
     r"canUseHighVideoQuality\s*\(\s*\)\s*\{[^}]{0,200}\}",
     "canUseHighVideoQuality(){return true}"),
    ("canStreamHighQuality",
     r"canStreamHighQuality\s*\(\s*\)\s*\{[^}]{0,200}\}",
     "canStreamHighQuality(){return true}"),
    ("isStreamQualityEnabled",
     r"isStreamQualityEnabled\s*\(\s*\)\s*\{[^}]{0,200}\}",
     "isStreamQualityEnabled(){return true}"),
    ("hasPremiumGuildSubscription",
     r"hasPremiumGuildSubscription\s*\(\s*\)\s*\{[^}]{0,200}\}",
     "hasPremiumGuildSubscription(){return true}"),
    ("maxFPS_15", r'(?<="maxFPS"\s*:\s*)15(?=\s*[,}])', "120"),
    ("maxFPS_30", r'(?<="maxFPS"\s*:\s*)30(?=\s*[,}])', "120"),
    ("fps_cap_30", r'(?<=fps\s*:\s*)30(?=\s*[,}])', "120"),
    ("fps_cap_15", r'(?<=fps\s*:\s*)15(?=\s*[,}])', "120"),
    ("maxResolution_720", r'(?<="maxResolution"\s*:\s*)720(?=\s*[,}])', "2160"),
    ("height_720", r'(?<="height"\s*:\s*)720(?=\s*[,}])', "2160"),
    ("width_1280", r'(?<="width"\s*:\s*)1280(?=\s*[,}])', "3840"),
    ("maxBitrate", r'(?<="maxBitrate"\s*:\s*)(?:2500|8000|96000)(?=\s*[,}])', "500000"),
    ("videoBitrate", r'(?<=videoBitrate\s*:\s*)(?:2500|8000|96000|500)(?=\s*[,}])', "500000"),
    ("VIDEO_QUALITY_MODE_AUTO", r'"VIDEO_QUALITY_MODE_AUTO"', '"VIDEO_QUALITY_MODE_FULL"'),
    ("premiumType_2", r'premiumType\s*[=!]=\s*2', "true"),
    ("isPremium_check", r'this\._isPremium\s*&&', "true &&"),
]

BRAZIL_PATCHES: List[Tuple[str, str, str]] = [
    ("brazil_flag_true", r'"brazil"\s*:\s*true', '"brazil":false'),
    ("brazil_video_disabled", r'"video_disabled_brazil"\s*:\s*true', '"video_disabled_brazil":false'),
    ("brazil_block", r'"brazil_block"\s*:\s*true', '"brazil_block":false'),
    ("video_brazil", r'"video_brazil[^"]*"\s*:\s*true', '"video_brazil_bypass":false'),
    ("country_BR_strict", r'"BR"\s*===\s*\w+(?:\.\w+)*', "false"),
    ("country_BR_loose", r'\w+(?:\.\w+)*\s*===\s*"BR"', "false"),
    ("countryCode_BR", r'countryCode\s*[=!]=\s*["\']BR["\']', "false"),
    ("region_brazil", r'region\s*[=!]=\s*["\']brazil["\']', "false"),
    ("anpd_block", r'"anpd_compliance[^"]*"\s*:\s*true', '"anpd_compliance_disabled":false'),
    ("goLiveRegionBlock", r'isGoLiveRegionBlocked\s*\(\s*\)\s*\{[^}]{0,300}\}', "isGoLiveRegionBlocked(){return false}"),
    ("isVideoRegionBlocked", r'isVideoRegionBlocked\s*\(\s*\)\s*\{[^}]{0,300}\}', "isVideoRegionBlocked(){return false}"),
    ("isStreamingDisabledForRegion", r'isStreamingDisabledForRegion\s*\(\s*\)\s*\{[^}]{0,300}\}', "isStreamingDisabledForRegion(){return false}"),
    ("geoGatedFeature_video", r'geoGatedFeature\s*\(\s*["\']video[^"\']*["\']\s*\)', "false"),
    ("restrictedCountries_BR", r'restrictedCountries\s*\.\s*includes\s*\(\s*["\']BR["\']\s*\)', "false"),
    ("blockedRegions_BR", r'blockedRegions\s*\.\s*includes\s*\(\s*["\']BR["\']\s*\)', "false"),
]

class AsarReader:
    def __init__(self, path: str):
        self.path = path
        self.header: Dict = {}
        self.data_offset: int = 0

    def load(self) -> None:
        with open(self.path, "rb") as f:
            f.read(4)
            header_block_size = struct.unpack("<I", f.read(4))[0]
            header_object_size = struct.unpack("<I", f.read(4))[0]
            json_size = struct.unpack("<I", f.read(4))[0]
            header_json = f.read(json_size)
            self.header = json.loads(header_json.decode("utf-8"))
            self.data_offset = 8 + header_block_size

    def extract_all(self, dest: str, log_fn=None) -> None:
        os.makedirs(dest, exist_ok=True)
        unpacked_dir = self.path + ".unpacked"

        def walk(node, base):
            for name, info in node.items():
                full = os.path.join(base, name)
                if "files" in info:
                    os.makedirs(full, exist_ok=True)
                    walk(info["files"], full)
                elif info.get("unpacked"):
                    src = os.path.join(unpacked_dir, os.path.relpath(full, dest))
                    if os.path.exists(src):
                        os.makedirs(os.path.dirname(full), exist_ok=True)
                        shutil.copy2(src, full)
                elif "offset" in info:
                    os.makedirs(os.path.dirname(full), exist_ok=True)
                    with open(self.path, "rb") as f:
                        f.seek(self.data_offset + int(info["offset"]))
                        data = f.read(info["size"])
                    with open(full, "wb") as out:
                        out.write(data)

        walk(self.header.get("files", {}), dest)

    @staticmethod
    def pack(src_dir: str, dest_path: str) -> None:
        files: Dict = {"files": {}}
        file_list: List[Tuple[str, str]] = []

        def scan(node, base_path, rel_path=""):
            for entry in sorted(os.listdir(base_path)):
                full = os.path.join(base_path, entry)
                rel = f"{rel_path}/{entry}".lstrip("/")
                if os.path.isdir(full):
                    node["files"][entry] = {"files": {}}
                    scan(node["files"][entry], full, rel)
                else:
                    node["files"][entry] = {"size": os.path.getsize(full), "offset": "0"}
                    file_list.append((rel, full))

        scan(files, src_dir)
        current_offset = 0

        def assign_offsets(node):
            nonlocal current_offset
            for name, info in node["files"].items():
                if "files" in info:
                    assign_offsets(info)
                elif "offset" in info:
                    info["offset"] = str(current_offset)
                    current_offset += info["size"]

        assign_offsets(files)
        header_json = json.dumps(files, separators=(",", ":")).encode("utf-8")
        json_size = len(header_json)
        padding_size = (4 - (json_size % 4)) % 4
        header_object_size = 4 + json_size + padding_size
        header_block_size = header_object_size + 4

        with open(dest_path, "wb") as out:
            out.write(struct.pack("<I", 4))
            out.write(struct.pack("<I", header_block_size))
            out.write(struct.pack("<I", header_object_size))
            out.write(struct.pack("<I", json_size))
            out.write(header_json)
            if padding_size > 0:
                out.write(b"\x00" * padding_size)
            for _, full_path in file_list:
                with open(full_path, "rb") as f:
                    out.write(f.read())


class PatchEngine:
    def __init__(self, discord_path: Path, log_fn):
        self.discord_path = discord_path
        self.log = log_fn
        self.temp_dir: Optional[str] = None
        self.patch_report: List[Dict] = []

    def find_asar(self) -> Optional[Path]:
        core_candidates = []
        # Pattern 1: inside versioned app-* subfolder (standard install)
        p1 = str(self.discord_path / "app-*" / "modules" / "discord_desktop_core-*" /
                  "discord_desktop_core" / "core.asar")
        core_candidates.extend(glob.glob(p1))
        # Pattern 2: directly under discord_path (portable / custom)
        p2 = str(self.discord_path / "modules" / "discord_desktop_core-*" /
                  "discord_desktop_core" / "core.asar")
        core_candidates.extend(glob.glob(p2))
        if core_candidates:
            return Path(sorted(core_candidates)[-1])

        # Pattern 3: app.asar fallback
        fallback = []
        for app_dir in sorted(self.discord_path.glob("app-*"), reverse=True):
            a = app_dir / "resources" / "app.asar"
            if a.exists():
                fallback.append(str(a))
                break
        a2 = self.discord_path / "resources" / "app.asar"
        if a2.exists():
            fallback.append(str(a2))
        if fallback:
            return Path(sorted(fallback)[-1])

        self.log(f"Buscado em: {self.discord_path}")
        self.log("  -> app-*/modules/discord_desktop_core-*/discord_desktop_core/core.asar")
        self.log("  -> resources/app.asar")
        return None

    def backup_asar(self, asar: Path) -> Path:
        backup = Path(str(asar) + BACKUP_SUFFIX)
        if not backup.exists():
            shutil.copy2(asar, backup)
            self.log(f"Backup salvo: {backup.name}")
        else:
            self.log(f"Backup ja existe: {backup.name}")
        return backup

    def restore_asar(self, asar: Path) -> bool:
        backup = Path(str(asar) + BACKUP_SUFFIX)
        if backup.exists():
            shutil.copy2(backup, asar)
            self.log(f"Restaurado: {asar.name}")
            return True
        self.log("Backup nao encontrado")
        return False

    def is_patched(self, asar: Path) -> bool:
        return Path(str(asar) + BACKUP_SUFFIX).exists()

    def apply_patches(self, quality=True, brazil=True) -> bool:
        asar = self.find_asar()
        if not asar:
            self.log("ASAR nao encontrado")
            return False
        self.log(f"ASAR encontrado: {asar}")
        self.backup_asar(asar)
        self.temp_dir = tempfile.mkdtemp(prefix="discordcrack_")
        self.log(f"Extraindo para: {self.temp_dir}")
        try:
            reader = AsarReader(str(asar))
            reader.load()
            reader.extract_all(self.temp_dir, self.log)
            self.log("Extracao completa")
        except Exception as e:
            self.log(f"Erro ao extrair ASAR: {e}")
            return False
        total_patches = 0
        patch_sets = []
        if quality:
            patch_sets.append(("QUALIDADE", QUALITY_PATCHES))
        if brazil:
            patch_sets.append(("BRASIL", BRAZIL_PATCHES))
        for label, patches in patch_sets:
            self.log(f"\nAplicando patches de {label}...")
            for pname, pattern, replacement in patches:
                count = self._patch_dir(self.temp_dir, pattern, replacement, pname)
                if count > 0:
                    self.log(f"  [{pname}] -> {count} ocorrencia(s)")
                    total_patches += count
                    self.patch_report.append({"name": pname, "hits": count})
        self.log(f"\nTotal substituicoes: {total_patches}")
        self.log(f"\nReempacotando ASAR...")
        try:
            AsarReader.pack(self.temp_dir, str(asar))
            self.log(f"ASAR reempacotado com sucesso")
        except Exception as e:
            self.log(f"Erro ao reempacotar: {e}")
            self.restore_asar(asar)
            return False
        finally:
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        return True

    def _patch_dir(self, directory: str, pattern: str, replacement: str, name: str) -> int:
        total = 0
        for root, dirs, files in os.walk(directory):
            for fname in files:
                if not fname.endswith((".js", ".json", ".ts")):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    new_content, count = re.subn(pattern, replacement, content)
                    if count > 0:
                        with open(fpath, "w", encoding="utf-8", errors="ignore") as f:
                            f.write(new_content)
                        total += count
                except Exception:
                    pass
        return total


def fetch_free_proxies(log_fn) -> List[Dict]:
    log_fn("Buscando proxies gratuitos...")
    sources = [
        "https://api.proxyscrape.com/v3/free-proxy-list/get?request=displayproxies&protocol=socks5&timeout=5000&country=all&simplified=true",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    ]
    raw_proxies = []
    for url in sources:
        try:
            r = requests.get(url, timeout=8)
            if r.status_code == 200:
                for line in r.text.strip().split("\n"):
                    line = line.strip()
                    if ":" in line:
                        parts = line.split(":")
                        if len(parts) == 2:
                            try:
                                raw_proxies.append({"host": parts[0].strip(), "port": int(parts[1].strip())})
                            except ValueError:
                                pass
        except Exception:
            pass
    log_fn(f"{len(raw_proxies)} proxies encontrados - testando latencia...")
    working = []
    lock = threading.Lock()

    def test_proxy(p):
        try:
            start = time.time()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.5)
            s.connect((p["host"], p["port"]))
            s.sendall(b"\x05\x01\x00")
            r = s.recv(2)
            if len(r) >= 2 and r[0] == 5 and r[1] == 0:
                domain = b"discord.com"
                req = b"\x05\x01\x00\x03" + bytes([len(domain)]) + domain + b"\x01\xbb"
                s.sendall(req)
                resp = s.recv(10)
                if len(resp) >= 2 and resp[1] == 0:
                    latency = int((time.time() - start) * 1000)
                    with lock:
                        working.append({**p, "latency": latency})
            s.close()
        except Exception:
            pass

    threads = [threading.Thread(target=test_proxy, args=(p,), daemon=True) for p in raw_proxies[:80]]
    for t in threads: t.start()
    for t in threads: t.join(timeout=4)
    working.sort(key=lambda x: x["latency"])
    log_fn(f"{len(working)} proxies SOCKS5 verificados")
    return working[:10]


def find_discord_exe(discord_path: Path) -> Optional[Path]:
    candidates = sorted(discord_path.glob("app-*/Discord.exe"), reverse=True)
    return candidates[0] if candidates else None


def launch_discord_with_proxy(discord_path: Path, proxy_host: str, proxy_port: int, log_fn) -> bool:
    exe = find_discord_exe(discord_path)
    if not exe:
        log_fn("Discord.exe nao encontrado")
        return False
    for proc in psutil.process_iter(["name", "pid"]):
        if proc.info["name"] and "discord" in proc.info["name"].lower():
            try:
                psutil.Process(proc.info["pid"]).terminate()
                log_fn(f"Discord (PID {proc.info['pid']}) encerrado")
            except Exception:
                pass
    time.sleep(1.5)
    flags = [
        str(exe),
        f"--proxy-server=socks5://{proxy_host}:{proxy_port}",
        "--ignore-certificate-errors",
        "--disable-background-networking=false",
        "--enable-features=WebRTC-H264WithOpenH264FFmpeg",
    ]
    log_fn(f"Lancando Discord com proxy {proxy_host}:{proxy_port}...")
    subprocess.Popen(flags, close_fds=True)
    log_fn("Discord iniciado com proxy por-processo (SSL bypass ativo)")
    log_fn("Apenas o Discord usa o proxy - jogos e outros apps nao sao afetados")
    return True


def launch_discord_direct(discord_path: Path, log_fn) -> bool:
    exe = find_discord_exe(discord_path)
    if not exe:
        log_fn("Discord.exe nao encontrado")
        return False
    for proc in psutil.process_iter(["name", "pid"]):
        if proc.info["name"] and "discord" in proc.info["name"].lower():
            try:
                psutil.Process(proc.info["pid"]).terminate()
            except Exception:
                pass
    time.sleep(1.5)
    subprocess.Popen([str(exe)], close_fds=True)
    log_fn("Discord iniciado (sem proxy - apenas patches de cliente ativos)")
    return True


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def request_admin_restart():
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable,
                                         " ".join(f'"{a}"' for a in sys.argv), None, 1)
    sys.exit()


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

COLORS = {
    "bg": "#0d0f14", "surface": "#141720", "card": "#1a1d27",
    "border": "#252836", "accent": "#5865F2", "accent2": "#3ba55d",
    "danger": "#ed4245", "warn": "#faa61a", "text": "#e3e5e8",
    "muted": "#6d7079", "success": "#57f287",
}
FONT = "Segoe UI"


class LogPanel(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["card"], corner_radius=12, **kwargs)
        self._text = ctk.CTkTextbox(self, font=(FONT, 12), fg_color=COLORS["bg"],
                                     text_color="#a8b4c8", wrap="word",
                                     border_width=0, corner_radius=8, state="disabled")
        self._text.pack(fill="both", expand=True, padx=8, pady=8)

    def log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self._text.configure(state="normal")
        self._text.insert("end", f"[{ts}] {msg}\n")
        self._text.see("end")
        self._text.configure(state="disabled")

    def clear(self):
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.configure(state="disabled")


class StatusBadge(ctk.CTkFrame):
    def __init__(self, master, label: str, **kwargs):
        super().__init__(master, fg_color=COLORS["card"], corner_radius=10, **kwargs)
        self._lbl = ctk.CTkLabel(self, text=label, font=(FONT, 11, "bold"), text_color=COLORS["muted"])
        self._lbl.pack(side="left", padx=(12, 4), pady=6)
        self._val = ctk.CTkLabel(self, text="--", font=(FONT, 11), text_color=COLORS["muted"])
        self._val.pack(side="left", padx=(0, 12), pady=6)

    def set(self, text: str, color: str = COLORS["text"]):
        self._val.configure(text=text, text_color=color)


class DiscordCrackApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION} -- BR Bypass + Quality Unlock")
        self.geometry("960x780")
        self.minsize(800, 650)
        self.configure(fg_color=COLORS["bg"])
        self.discord_path = DISCORD_LOCAL
        self.free_proxies: List[Dict] = []
        self._build_ui()
        self._detect_discord()

    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=COLORS["surface"], corner_radius=0, height=64)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="  DiscordCrack", font=(FONT, 22, "bold"),
                     text_color=COLORS["accent"]).pack(side="left", padx=20, pady=12)
        ctk.CTkLabel(header, text=f"v{APP_VERSION} -- Contra a censura BR",
                     font=(FONT, 12), text_color=COLORS["muted"]).pack(side="left", padx=4)
        admin_text = "ADMIN" if is_admin() else "USER (sem admin)"
        admin_color = COLORS["success"] if is_admin() else COLORS["warn"]
        ctk.CTkLabel(header, text=admin_text, font=(FONT, 11, "bold"),
                     text_color=admin_color).pack(side="right", padx=20)

        main = ctk.CTkFrame(self, fg_color=COLORS["bg"], corner_radius=0)
        main.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(main, fg_color=COLORS["surface"], corner_radius=0, width=220)
        sidebar.pack(fill="y", side="left")
        sidebar.pack_propagate(False)
        self._build_sidebar(sidebar)

        content = ctk.CTkFrame(main, fg_color=COLORS["bg"], corner_radius=0)
        content.pack(fill="both", expand=True, side="left", padx=16, pady=16)

        self._tabs: Dict[str, ctk.CTkFrame] = {}
        for name in ["patcher", "proxy", "logs", "sobre"]:
            f = ctk.CTkFrame(content, fg_color=COLORS["bg"], corner_radius=0)
            self._tabs[name] = f

        self._build_patcher(self._tabs["patcher"])
        self._build_proxy(self._tabs["proxy"])
        self._build_logs(self._tabs["logs"])
        self._build_sobre(self._tabs["sobre"])
        self._show_tab("patcher")

    def _build_sidebar(self, sb):
        ctk.CTkLabel(sb, text="NAVEGACAO", font=(FONT, 10, "bold"),
                     text_color=COLORS["muted"]).pack(anchor="w", padx=16, pady=(20, 6))
        self._nav_btns = {}
        nav = [("patcher", " Patcher ASAR"), ("proxy", " Proxy Launcher"),
               ("logs", " Logs"), ("sobre", " Sobre")]
        for key, lbl in nav:
            b = ctk.CTkButton(sb, text=lbl, font=(FONT, 13), fg_color="transparent",
                              hover_color=COLORS["border"], text_color=COLORS["text"],
                              anchor="w", height=40, corner_radius=8,
                              command=lambda k=key: self._show_tab(k))
            b.pack(fill="x", padx=10, pady=2)
            self._nav_btns[key] = b

        ctk.CTkLabel(sb, text="STATUS", font=(FONT, 10, "bold"),
                     text_color=COLORS["muted"]).pack(anchor="w", padx=16, pady=(24, 6))
        self._badge_discord = StatusBadge(sb, "Discord")
        self._badge_discord.pack(fill="x", padx=10, pady=3)
        self._badge_patch = StatusBadge(sb, "Patch")
        self._badge_patch.pack(fill="x", padx=10, pady=3)
        self._badge_proxy = StatusBadge(sb, "Proxy")
        self._badge_proxy.pack(fill="x", padx=10, pady=3)

    def _show_tab(self, name: str):
        for k, f in self._tabs.items():
            f.pack_forget()
        self._tabs[name].pack(fill="both", expand=True)
        for k, b in self._nav_btns.items():
            b.configure(fg_color=COLORS["accent"] if k == name else "transparent")

    def _build_patcher(self, parent):
        ctk.CTkLabel(parent, text="Patcher de ASAR", font=(FONT, 20, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", pady=(0, 4))
        ctk.CTkLabel(parent, text="Modifica o core.asar do Discord em Python puro -- sem Node.js",
                     font=(FONT, 12), text_color=COLORS["muted"]).pack(anchor="w", pady=(0, 8))

        pc = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        pc.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(pc, text="Caminho do Discord", font=(FONT, 12, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(8, 4))
        pr = ctk.CTkFrame(pc, fg_color="transparent")
        pr.pack(fill="x", padx=16, pady=(0, 8))
        self._path_entry = ctk.CTkEntry(pr, font=(FONT, 11), fg_color=COLORS["bg"],
                                         border_color=COLORS["border"], text_color=COLORS["text"])
        self._path_entry.pack(fill="x", side="left", expand=True, padx=(0, 8))
        self._path_entry.insert(0, str(DISCORD_LOCAL))
        ctk.CTkButton(pr, text="Detectar", font=(FONT, 12), fg_color=COLORS["accent"],
                      hover_color="#4752c4", width=90, command=self._detect_discord).pack(side="left")

        oc = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        oc.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(oc, text="Opcoes de Patch", font=(FONT, 12, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(8, 4))
        self._var_quality = tk.BooleanVar(value=True)
        self._var_brazil = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(oc, text="Qualidade Maxima sem Nitro (1080p/4K, 60fps+, bitrate max)",
                         font=(FONT, 12), text_color=COLORS["text"], fg_color=COLORS["accent"],
                         hover_color="#4752c4", variable=self._var_quality).pack(anchor="w", padx=24, pady=2)
        ctk.CTkCheckBox(oc, text="Bypass do Bloqueio Brasileiro (remove flags de regiao no cliente)",
                         font=(FONT, 12), text_color=COLORS["text"], fg_color=COLORS["accent2"],
                         hover_color="#2d8a4e", variable=self._var_brazil).pack(anchor="w", padx=24, pady=(2, 8))

        self._patch_log = LogPanel(parent)
        self._patch_log.pack(fill="both", expand=True, pady=(0, 8))

        br = ctk.CTkFrame(parent, fg_color="transparent")
        br.pack(fill="x")
        self._btn_patch = ctk.CTkButton(br, text="APLICAR PATCHES",
                                         font=(FONT, 13, "bold"), fg_color=COLORS["accent"],
                                         hover_color="#4752c4", height=42, corner_radius=10,
                                         command=self._do_patch)
        self._btn_patch.pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(br, text="Restaurar Original", font=(FONT, 13), fg_color=COLORS["card"],
                      hover_color=COLORS["border"], border_width=1, border_color=COLORS["border"],
                      height=42, corner_radius=10, command=self._do_restore).pack(side="left", expand=True, fill="x", padx=(6, 0))

    def _build_proxy(self, parent):
        ctk.CTkLabel(parent, text="Proxy Launcher", font=(FONT, 20, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", pady=(0, 2))
        ctk.CTkLabel(parent, text="Lanca o Discord com proxy por-processo -- jogos NAO sao afetados",
                     font=(FONT, 12), text_color=COLORS["muted"]).pack(anchor="w", pady=(0, 8))

        mc = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        mc.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(mc, text="Fonte do Proxy", font=(FONT, 12, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", padx=16, pady=(8, 4))
        self._proxy_mode = tk.StringVar(value="auto")
        modes = [
            ("auto", "Auto - buscar proxy gratuito mais rapido"),
            ("tor", "Tor Browser (127.0.0.1:9150) - recomendado"),
            ("tord", "Tor Daemon (127.0.0.1:9050)"),
            ("custom", "Personalizado"),
        ]
        for val, text in modes:
            ctk.CTkRadioButton(mc, text=text, font=(FONT, 12), text_color=COLORS["text"],
                               fg_color=COLORS["accent"], hover_color="#4752c4",
                               variable=self._proxy_mode, value=val,
                               command=self._update_proxy_fields).pack(anchor="w", padx=24, pady=1)

        cr = ctk.CTkFrame(mc, fg_color="transparent")
        cr.pack(fill="x", padx=16, pady=(4, 8))
        ctk.CTkLabel(cr, text="Host:", font=(FONT, 11), text_color=COLORS["muted"]).pack(side="left", padx=(0, 4))
        self._proxy_host = ctk.CTkEntry(cr, width=170, font=(FONT, 11), fg_color=COLORS["bg"],
                                         border_color=COLORS["border"], placeholder_text="1.2.3.4")
        self._proxy_host.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(cr, text="Porta:", font=(FONT, 11), text_color=COLORS["muted"]).pack(side="left", padx=(0, 4))
        self._proxy_port = ctk.CTkEntry(cr, width=70, font=(FONT, 11), fg_color=COLORS["bg"],
                                         border_color=COLORS["border"], placeholder_text="1080")
        self._proxy_port.pack(side="left")
        ctk.CTkButton(cr, text="Testar", font=(FONT, 11), fg_color=COLORS["card"], border_width=1,
                      border_color=COLORS["border"], hover_color=COLORS["border"], width=65, height=30,
                      command=self._test_proxy).pack(side="left", padx=(8, 0))

        lc = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        lc.pack(fill="x", pady=(0, 8))
        lh = ctk.CTkFrame(lc, fg_color="transparent")
        lh.pack(fill="x", padx=16, pady=(6, 4))
        ctk.CTkLabel(lh, text="Proxies Gratuitos Encontrados", font=(FONT, 12, "bold"),
                     text_color=COLORS["text"]).pack(side="left")
        ctk.CTkButton(lh, text="Buscar", font=(FONT, 11), fg_color=COLORS["accent"],
                      hover_color="#4752c4", width=75, height=26,
                      command=self._fetch_proxies).pack(side="right")
        self._proxy_list_text = ctk.CTkTextbox(lc, height=75, font=("Consolas", 11),
                                                fg_color=COLORS["bg"], text_color=COLORS["text"],
                                                border_width=0, corner_radius=8, state="disabled")
        self._proxy_list_text.pack(fill="x", padx=8, pady=(0, 6))

        # Bottom action buttons packed before proxy log so they are guaranteed visible
        lr = ctk.CTkFrame(parent, fg_color="transparent")
        lr.pack(fill="x", side="bottom", pady=(4, 0))
        ctk.CTkButton(lr, text="Lancar Discord COM Proxy", font=(FONT, 13, "bold"),
                      fg_color=COLORS["accent2"], hover_color="#2d8a4e", height=42, corner_radius=10,
                      command=self._do_launch_proxy).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(lr, text="Lancar Sem Proxy", font=(FONT, 13), fg_color=COLORS["card"],
                      hover_color=COLORS["border"], border_width=1, border_color=COLORS["border"],
                      height=42, corner_radius=10, command=self._do_launch_direct).pack(side="left", expand=True, fill="x", padx=(6, 0))

        self._proxy_log = LogPanel(parent)
        self._proxy_log.pack(fill="both", expand=True, side="top", pady=(0, 6))
        self._update_proxy_fields()

    def _build_logs(self, parent):
        ctk.CTkLabel(parent, text="Logs Completos", font=(FONT, 20, "bold"),
                     text_color=COLORS["text"]).pack(anchor="w", pady=(0, 10))
        self._main_log = LogPanel(parent)
        self._main_log.pack(fill="both", expand=True, pady=(0, 8))
        ctk.CTkButton(parent, text="Limpar Logs", font=(FONT, 12), fg_color=COLORS["card"],
                      hover_color=COLORS["border"], border_width=1, border_color=COLORS["border"],
                      height=36, corner_radius=8, command=self._main_log.clear).pack(anchor="e")

    def _build_sobre(self, parent):
        ctk.CTkLabel(parent, text="DiscordCrack v2.0", font=(FONT, 24, "bold"),
                     text_color=COLORS["accent"]).pack(pady=(20, 4))
        ctk.CTkLabel(parent, text="Contra a censura do governo brasileiro\nCamera e Go Live liberados -- Qualidade maxima sem Nitro",
                     font=(FONT, 13), text_color=COLORS["muted"], justify="center").pack(pady=(0, 20))
        ic = ctk.CTkFrame(parent, fg_color=COLORS["card"], corner_radius=12)
        ic.pack(fill="x", padx=40, pady=8)
        info_text = (
            "COMO FUNCIONA\n\n"
            "1. PATCH DE ASAR (lado do cliente)\n"
            "   Desempacota o core.asar do Discord em Python puro\n"
            "   Remove flags de bloqueio de regiao do Brasil\n"
            "   Remove verificacoes de Nitro para qualidade de video\n"
            "   Desbloqueia 1080p/4K, 60fps+, bitrate maximo\n"
            "   Reempacota e salva backup do original\n\n"
            "2. PROXY POR-PROCESSO (lado do servidor)\n"
            "   Discord iniciado com --proxy-server= (flag do Electron)\n"
            "   APENAS o Discord passa pelo proxy -- jogos nao sao afetados\n"
            "   Suporte a Tor Browser (127.0.0.1:9150)\n"
            "   Proxies gratuitos auto-buscados e testados por latencia\n"
            "   NAO e uma VPN de sistema -- sem latencia em jogos\n\n"
            "Setembro 2026 -- Liberdade de expressao e direito de todos."
        )
        tb = ctk.CTkTextbox(ic, font=("Consolas", 11), fg_color=COLORS["bg"],
                             text_color="#8ea0c8", border_width=0, corner_radius=8, height=300)
        tb.pack(fill="x", padx=8, pady=8)
        tb.insert("1.0", info_text)
        tb.configure(state="disabled")

    def _log(self, msg: str):
        if hasattr(self, "_main_log"):
            self._main_log.log(msg)

    def _detect_discord(self):
        if hasattr(self, "_path_entry"):
            self.discord_path = Path(self._path_entry.get())
        exe = find_discord_exe(self.discord_path)
        if exe:
            self._badge_discord.set(f"OK {exe.parent.name}", COLORS["success"])
            self._log(f"Discord encontrado: {exe}")
        else:
            self._badge_discord.set("Nao encontrado", COLORS["danger"])
            self._log(f"Discord nao encontrado em: {self.discord_path}")
            return
        engine = PatchEngine(self.discord_path, self._log)
        asar = engine.find_asar()
        if asar:
            is_p = engine.is_patched(asar)
            self._badge_patch.set("Patcheado" if is_p else "Original",
                                   COLORS["success"] if is_p else COLORS["warn"])
            self._log(f"ASAR: {asar.name} ({'patcheado' if is_p else 'original'})")
        else:
            self._badge_patch.set("ASAR?", COLORS["muted"])

    def _do_patch(self):
        if not is_admin():
            if messagebox.askyesno("Admin Necessario",
                                   "Para modificar arquivos do Discord, e necessario Administrador.\nReiniciar como Admin?"):
                request_admin_restart()
            return

        def run():
            self._btn_patch.configure(state="disabled", text="Aplicando...")
            self.discord_path = Path(self._path_entry.get())
            engine = PatchEngine(self.discord_path,
                                  lambda m: (self._patch_log.log(m), self._log(m)))
            ok = engine.apply_patches(quality=self._var_quality.get(), brazil=self._var_brazil.get())
            if ok:
                self._badge_patch.set("Patcheado", COLORS["success"])
                self._patch_log.log("\nPATCHES APLICADOS COM SUCESSO!")
                self._patch_log.log("   Reinicie o Discord para aplicar as mudancas")
                messagebox.showinfo("Sucesso!", "Patches aplicados!\n\nReinicie o Discord na aba Proxy.")
            else:
                self._badge_patch.set("Falha", COLORS["danger"])
                messagebox.showerror("Erro", "Falha ao aplicar patches. Veja os logs.")
            self._btn_patch.configure(state="normal", text="APLICAR PATCHES")

        threading.Thread(target=run, daemon=True).start()

    def _do_restore(self):
        if not is_admin():
            messagebox.showwarning("Admin Necessario", "Execute como Administrador para restaurar.")
            return
        self.discord_path = Path(self._path_entry.get())
        engine = PatchEngine(self.discord_path, lambda m: (self._patch_log.log(m), self._log(m)))
        asar = engine.find_asar()
        if asar:
            engine.restore_asar(asar)
            self._badge_patch.set("Original", COLORS["warn"])

    def _update_proxy_fields(self):
        enabled = self._proxy_mode.get() == "custom"
        state = "normal" if enabled else "disabled"
        self._proxy_host.configure(state=state)
        self._proxy_port.configure(state=state)

    def _test_proxy(self):
        host, port = self._get_proxy_target()
        if not host:
            messagebox.showwarning("Proxy", "Configure o proxy primeiro.")
            return

        def run():
            self._proxy_log.log(f"Testando {host}:{port}...")
            try:
                start = time.time()
                s = socket.create_connection((host, port), timeout=5)
                s.close()
                ms = int((time.time() - start) * 1000)
                self._proxy_log.log(f"Proxy OK - {ms}ms")
                self._badge_proxy.set(f"OK {host}:{port} ({ms}ms)", COLORS["success"])
            except Exception as e:
                self._proxy_log.log(f"Proxy inacessivel: {e}")
                self._badge_proxy.set("Inacessivel", COLORS["danger"])

        threading.Thread(target=run, daemon=True).start()

    def _get_proxy_target(self) -> Tuple[Optional[str], int]:
        mode = self._proxy_mode.get()
        if mode == "tor": return "127.0.0.1", 9150
        elif mode == "tord": return "127.0.0.1", 9050
        elif mode == "custom":
            h = self._proxy_host.get().strip()
            try: p = int(self._proxy_port.get().strip())
            except ValueError: return None, 0
            return h, p
        elif mode == "auto" and self.free_proxies:
            best = self.free_proxies[0]
            return best["host"], best["port"]
        return None, 0

    def _fetch_proxies(self):
        def run():
            self._proxy_list_text.configure(state="normal")
            self._proxy_list_text.delete("1.0", "end")
            self._proxy_list_text.insert("end", "Buscando...\n")
            self._proxy_list_text.configure(state="disabled")
            self.free_proxies = fetch_free_proxies(lambda m: (self._proxy_log.log(m), self._log(m)))
            self._proxy_list_text.configure(state="normal")
            self._proxy_list_text.delete("1.0", "end")
            for p in self.free_proxies:
                self._proxy_list_text.insert("end", f"{p['host']}:{p['port']}  ({p['latency']}ms)\n")
            if not self.free_proxies:
                self._proxy_list_text.insert("end", "Nenhum proxy encontrado.\n")
            self._proxy_list_text.configure(state="disabled")

        threading.Thread(target=run, daemon=True).start()

    def _do_launch_proxy(self):
        host, port = self._get_proxy_target()
        if not host:
            if self._proxy_mode.get() == "auto":
                messagebox.showinfo("Proxies", "Clique em 'Buscar' primeiro para encontrar proxies.")
            else:
                messagebox.showwarning("Proxy", "Configure o proxy primeiro.")
            return

        def run():
            self._proxy_log.log(f"\nUsando proxy: {host}:{port}")
            ok = launch_discord_with_proxy(self.discord_path, host, port,
                                            lambda m: (self._proxy_log.log(m), self._log(m)))
            if ok:
                self._badge_proxy.set(f"OK {host}:{port}", COLORS["success"])

        threading.Thread(target=run, daemon=True).start()

    def _do_launch_direct(self):
        def run():
            launch_discord_direct(self.discord_path, lambda m: (self._proxy_log.log(m), self._log(m)))
            self._badge_proxy.set("sem proxy", COLORS["muted"])

        threading.Thread(target=run, daemon=True).start()


def main():
    if not is_admin():
        try:
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", sys.executable,
                " ".join(f'"{a}"' for a in sys.argv), None, 1)
            if result > 32:
                sys.exit(0)
        except Exception:
            pass
    app = DiscordCrackApp()
    app.mainloop()


if __name__ == "__main__":
    main()
