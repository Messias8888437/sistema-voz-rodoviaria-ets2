import argparse
import ctypes
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from ctypes import wintypes
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_FILES = (
    "RodoviariaETS2.exe",
    "RodoviariaEngine.exe",
    "campainha.wav",
    "fundo_rodoviaria.wav",
    "THIRD-PARTY-NOTICES.txt",
)
PLUGIN_NAME = "scs-telemetry.dll"
PLUGIN_SHA256 = "1d03dbc7a975e72203c60a7b9998021ceb8800b836bf28a131279979ad386cd4"
DEFAULT_CONFIG = {
    "voice": "pt-BR-FranciscaNeural",
    "voice_volume": 1.75,
    "background_volume": 0.60,
    "bell_volume": 1.0,
    "echo": True,
    "profile": "automatico",
    "auto_announce": True,
}


def resource_path(name: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return root / "payload" / name


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_game_directory(path: Path) -> bool:
    return (
        (path / "bin" / "win_x64").is_dir()
        and (
            (path / "bin" / "win_x64" / "eurotrucks2.exe").is_file()
            or (path / "eurotrucks2.exe").is_file()
        )
    )


def find_game_directories() -> list[Path]:
    candidates: list[Path] = [
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Euro Truck Simulator 2"),
        Path(r"C:\Program Files\Steam\steamapps\common\Euro Truck Simulator 2"),
    ]
    try:
        import winreg

        registry_paths = (
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        )
        steam_roots: set[Path] = set()
        for hive, key_name in registry_paths:
            try:
                with winreg.OpenKey(hive, key_name) as key:
                    for value_name in ("SteamPath", "InstallPath"):
                        try:
                            value, _ = winreg.QueryValueEx(key, value_name)
                        except OSError:
                            continue
                        steam_roots.add(Path(value))
            except OSError:
                continue
        for steam_root in steam_roots:
            candidates.append(
                steam_root / "steamapps" / "common" / "Euro Truck Simulator 2"
            )
            libraries_file = steam_root / "steamapps" / "libraryfolders.vdf"
            if not libraries_file.is_file():
                continue
            text = libraries_file.read_text(encoding="utf-8", errors="replace")
            for library in re.findall(r'"path"\s+"([^"]+)"', text):
                library_root = Path(library.replace("\\\\", "\\"))
                candidates.append(
                    library_root / "steamapps" / "common" / "Euro Truck Simulator 2"
                )
    except ImportError:
        pass

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key not in seen and validate_game_directory(candidate):
            unique.append(candidate)
            seen.add(key)
    return unique


def install_plugin_as_admin(game_directory: Path) -> dict[str, str]:
    if not validate_game_directory(game_directory):
        raise ValueError(
            "A pasta selecionada não parece ser a instalação do ETS2 "
            "(não encontrei bin\\win_x64\\eurotrucks2.exe)."
        )
    source = resource_path(PLUGIN_NAME)
    if not source.is_file() or sha256(source) != PLUGIN_SHA256:
        raise RuntimeError("O arquivo do plugin no instalador não passou na verificação SHA-256.")

    plugin_directory = game_directory / "bin" / "win_x64" / "plugins"
    plugin_directory.mkdir(parents=True, exist_ok=True)
    destination = plugin_directory / PLUGIN_NAME
    if destination.is_file() and sha256(destination) == PLUGIN_SHA256:
        return {"plugin_path": str(destination), "status": "already_installed"}

    backup = ""
    if destination.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup_path = destination.with_name(f"{PLUGIN_NAME}.backup-{stamp}")
        suffix = 1
        while backup_path.exists():
            backup_path = destination.with_name(
                f"{PLUGIN_NAME}.backup-{stamp}-{suffix}"
            )
            suffix += 1
        shutil.copy2(destination, backup_path)
        backup = str(backup_path)

    temporary = destination.with_name(f"{PLUGIN_NAME}.installing")
    try:
        shutil.copy2(source, temporary)
        if sha256(temporary) != PLUGIN_SHA256:
            raise RuntimeError("A cópia do plugin falhou na verificação SHA-256.")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "plugin_path": str(destination),
        "status": "installed",
        "backup_path": backup,
    }


class ShellExecuteInfo(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", wintypes.ULONG),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", ctypes.c_void_p),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hkeyClass", ctypes.c_void_p),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", ctypes.c_void_p),
        ("hProcess", wintypes.HANDLE),
    ]


def elevated_plugin_install(game_directory: Path) -> dict[str, str]:
    result_path = Path(tempfile.gettempdir()) / (
        f"rodoviaria-plugin-{os.getpid()}-{time.time_ns()}.json"
    )
    executable = Path(sys.executable).resolve()
    parameters = subprocess.list2cmdline(
        [
            "--install-plugin",
            str(game_directory),
            "--result",
            str(result_path),
        ]
    )
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)
    shell32.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell32.ShellExecuteExW.restype = wintypes.BOOL
    info = ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x00000040
    info.lpVerb = "runas"
    info.lpFile = str(executable)
    info.lpParameters = parameters
    info.lpDirectory = str(executable.parent)
    info.nShow = 0

    try:
        if not shell32.ShellExecuteExW(ctypes.byref(info)):
            error = ctypes.get_last_error()
            if error == 1223:
                raise PermissionError("A solicitação de administrador foi cancelada.")
            raise ctypes.WinError(error)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.GetExitCodeProcess.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.GetExitCodeProcess.restype = wintypes.BOOL
        kernel32.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if exit_code.value != 0:
            detail = ""
            if result_path.is_file():
                detail = json.loads(result_path.read_text(encoding="utf-8")).get(
                    "error", ""
                )
            raise RuntimeError(detail or f"A instalação do plugin falhou ({exit_code.value}).")
        if not result_path.is_file():
            raise RuntimeError("O instalador elevado não retornou o resultado do plugin.")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if not result.get("ok"):
            raise RuntimeError(result.get("error", "Não foi possível instalar o plugin."))
        return result
    finally:
        if info.hProcess:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle(info.hProcess)
        result_path.unlink(missing_ok=True)


def run_plugin_helper(game_directory: str, result_file: str) -> int:
    result_path = Path(result_file)
    try:
        if not ctypes.windll.shell32.IsUserAnAdmin():
            raise PermissionError("O instalador do plugin precisa de permissão de administrador.")
        result = install_plugin_as_admin(Path(game_directory))
        result_path.write_text(
            json.dumps({"ok": True, **result}, ensure_ascii=False),
            encoding="utf-8",
        )
        return 0
    except Exception as error:
        result_path.write_text(
            json.dumps({"ok": False, "error": str(error)}, ensure_ascii=False),
            encoding="utf-8",
        )
        return 1


def create_desktop_shortcut(install_directory: Path) -> Path:
    desktop = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    shortcut_path = desktop / "RodoviariaETS2.lnk"
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    command = (
        "$shell = New-Object -ComObject WScript.Shell; "
        f"$link = $shell.CreateShortcut({quote(shortcut_path)}); "
        f"$link.TargetPath = {quote(install_directory / 'RodoviariaETS2.exe')}; "
        f"$link.WorkingDirectory = {quote(install_directory)}; "
        "$link.Description = 'Sistema de Voz Rodoviária para ETS2'; "
        f"$link.IconLocation = {quote(install_directory / 'RodoviariaETS2.exe')}; "
        "$link.Save()"
    )
    result = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive",
            "-Command", command,
        ],
        capture_output=True,
        text=True,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise RuntimeError(
            result.stderr.strip() or "O Windows não conseguiu criar o atalho."
        )
    return shortcut_path


class Installer:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Instalação do RodoviariaETS2")
        self.root.geometry("650x650")
        self.root.minsize(620, 620)
        self.root.configure(bg="#101318")
        self.root.option_add("*Font", ("Segoe UI", 10))
        self.install_directory = tk.StringVar(
            value=str(
                Path(os.environ.get("LOCALAPPDATA", Path.home()))
                / "Programs"
                / "RodoviariaETS2"
            )
        )
        games = find_game_directories()
        self.game_directory = tk.StringVar(value=str(games[0]) if games else "")
        self.plugin_destination = tk.StringVar()
        self.game_directory.trace_add("write", self.update_plugin_destination)
        self.update_plugin_destination()
        self.install_plugin = tk.BooleanVar(value=True)
        self.create_shortcut = tk.BooleanVar(value=True)
        self.run_after_install = tk.BooleanVar(value=True)
        self.status = tk.StringVar(value="Pronto para instalar.")
        self.build_ui()

    def build_ui(self) -> None:
        outer = tk.Frame(self.root, bg="#101318", padx=28, pady=24)
        outer.pack(fill="both", expand=True)
        tk.Label(
            outer,
            text="RodoviariaETS2",
            bg="#101318",
            fg="#f4f4f5",
            font=("Segoe UI", 22, "bold"),
        ).pack(anchor="w")
        tk.Label(
            outer,
            text="Assistente de instalação para Windows • ETS2 1.62",
            bg="#101318",
            fg="#a1a1aa",
        ).pack(anchor="w", pady=(2, 20))

        self.section(outer, "1. Pasta do aplicativo")
        install_row = tk.Frame(outer, bg="#101318")
        install_row.pack(fill="x", pady=(0, 15))
        tk.Entry(
            install_row, textvariable=self.install_directory, bg="#27272a",
            fg="#f4f4f5", insertbackground="#f4f4f5", relief="flat",
        ).pack(side="left", fill="x", expand=True, ipady=8)
        tk.Button(
            install_row, text="Procurar...", command=self.browse_install_directory,
            relief="flat", padx=12, pady=6,
        ).pack(side="left", padx=(8, 0))

        self.section(outer, "2. Plugin de telemetria ETS2")
        ttk.Checkbutton(
            outer,
            text="Instalar scs-telemetry.dll no ETS2 (solicita confirmação do Windows)",
            variable=self.install_plugin,
        ).pack(anchor="w", pady=(0, 8))
        game_row = tk.Frame(outer, bg="#101318")
        game_row.pack(fill="x", pady=(0, 5))
        tk.Entry(
            game_row, textvariable=self.game_directory, bg="#27272a",
            fg="#f4f4f5", insertbackground="#f4f4f5", relief="flat",
        ).pack(side="left", fill="x", expand=True, ipady=8)
        tk.Button(
            game_row, text="Localizar ETS2...", command=self.browse_game_directory,
            relief="flat", padx=12, pady=6,
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            outer,
            text="Destino exato do plugin:",
            bg="#101318",
            fg="#a1a1aa",
        ).pack(anchor="w", pady=(0, 2))
        tk.Label(
            outer,
            textvariable=self.plugin_destination,
            bg="#101318",
            fg="#38bdf8",
            wraplength=585,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))

        self.section(outer, "3. Opções")
        ttk.Checkbutton(
            outer, text="Criar atalho na Área de Trabalho",
            variable=self.create_shortcut,
        ).pack(anchor="w", pady=(0, 6))
        ttk.Checkbutton(
            outer, text="Executar RodoviariaETS2 ao concluir",
            variable=self.run_after_install,
        ).pack(anchor="w", pady=(0, 16))

        tk.Label(
            outer,
            text="O plugin será copiado para bin\\win_x64\\plugins do ETS2 selecionado. "
            "Uma DLL anterior com o mesmo nome será preservada como backup.",
            bg="#101318",
            fg="#a1a1aa",
            wraplength=585,
            justify="left",
        ).pack(anchor="w", pady=(0, 14))
        tk.Label(
            outer, textvariable=self.status, bg="#101318", fg="#38bdf8",
            wraplength=585, justify="left",
        ).pack(anchor="w", pady=(0, 12))

        buttons = tk.Frame(outer, bg="#101318")
        buttons.pack(fill="x", side="bottom")
        tk.Button(
            buttons, text="Cancelar", command=self.root.destroy,
            relief="flat", padx=18, pady=10,
        ).pack(side="right")
        self.install_button = tk.Button(
            buttons, text="Instalar", command=self.install,
            bg="#0369a1", fg="white", activebackground="#0284c7",
            activeforeground="white", relief="flat", padx=24, pady=10,
        )
        self.install_button.pack(side="right", padx=(0, 8))

    @staticmethod
    def section(parent: tk.Widget, text: str) -> None:
        tk.Label(
            parent, text=text, bg="#101318", fg="#f4f4f5",
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", pady=(0, 7))

    def browse_install_directory(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Escolha onde instalar o RodoviariaETS2",
            initialdir=self.install_directory.get(),
            mustexist=False,
        )
        if selected:
            self.install_directory.set(selected)

    def browse_game_directory(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            title="Selecione a pasta principal do Euro Truck Simulator 2",
            initialdir=self.game_directory.get() or str(Path.home()),
        )
        if selected:
            self.game_directory.set(selected)

    def update_plugin_destination(self, *_: object) -> None:
        game_directory = self.game_directory.get().strip()
        if game_directory:
            self.plugin_destination.set(
                str(Path(game_directory) / "bin" / "win_x64" / "plugins" / PLUGIN_NAME)
            )
        else:
            self.plugin_destination.set(
                r"C:\Program Files (x86)\Steam\steamapps\common"
                r"\Euro Truck Simulator 2\bin\win_x64\plugins\scs-telemetry.dll"
            )

    def set_status(self, text: str) -> None:
        self.status.set(text)
        self.root.update_idletasks()

    def install(self) -> None:
        install_directory = Path(self.install_directory.get()).expanduser()
        if not install_directory.is_absolute():
            messagebox.showerror("Pasta inválida", "Escolha um caminho absoluto.", parent=self.root)
            return
        if self.install_plugin.get():
            game_directory = Path(self.game_directory.get()).expanduser()
            if not validate_game_directory(game_directory):
                messagebox.showerror(
                    "ETS2 não encontrado",
                    "Selecione a pasta principal do ETS2, que contém bin\\win_x64\\eurotrucks2.exe.",
                    parent=self.root,
                )
                return

        self.install_button.config(state="disabled")
        try:
            install_directory.mkdir(parents=True, exist_ok=True)
            for filename in APP_FILES:
                source = resource_path(filename)
                if not source.is_file():
                    raise FileNotFoundError(f"Arquivo de instalação ausente: {filename}")
                self.set_status(f"Instalando {filename}...")
                shutil.copy2(source, install_directory / filename)

            config_path = install_directory / "config_rodoviaria.json"
            if not config_path.exists():
                config_path.write_text(
                    json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

            shortcut_path = None
            if self.create_shortcut.get():
                self.set_status("Criando atalho na Área de Trabalho...")
                shortcut_path = create_desktop_shortcut(install_directory)

            plugin_result: dict[str, str] | None = None
            plugin_error = ""
            if self.install_plugin.get():
                self.set_status(
                    "Solicitando permissão do Windows para instalar o plugin no ETS2..."
                )
                try:
                    plugin_result = elevated_plugin_install(
                        Path(self.game_directory.get()).expanduser()
                    )
                except Exception as error:
                    plugin_error = str(error)

            self.show_completion(
                install_directory, shortcut_path, plugin_result,
                plugin_error, self.run_after_install.get(),
            )
        except Exception as error:
            self.install_button.config(state="normal")
            self.set_status("A instalação não foi concluída.")
            messagebox.showerror(
                "Falha na instalação",
                f"{error}\n\nOs arquivos copiados até agora estão em:\n{install_directory}",
                parent=self.root,
            )

    def show_completion(
        self,
        install_directory: Path,
        shortcut_path: Path | None,
        plugin_result: dict[str, str] | None,
        plugin_error: str,
        run_after_install: bool,
    ) -> None:
        lines = [f"Aplicativo instalado em:\n{install_directory}"]
        if shortcut_path:
            lines.append(f"Atalho criado:\n{shortcut_path}")
        if plugin_result:
            plugin_status = (
                "Plugin já estava instalado."
                if plugin_result.get("status") == "already_installed"
                else "Plugin scs-telemetry.dll instalado no ETS2."
            )
            lines.append(
                f"{plugin_status}\n{plugin_result['plugin_path']}"
            )
            if plugin_result.get("backup_path"):
                lines.append(
                    f"A DLL anterior foi preservada em:\n{plugin_result['backup_path']}"
                )
        elif plugin_error:
            lines.append(
                "O aplicativo foi instalado, mas o plugin não foi confirmado:\n"
                f"{plugin_error}"
            )
        else:
            lines.append("Instalação do aplicativo concluída; plugin não selecionado.")

        self.set_status("\n\n".join(lines))
        self.install_button.config(text="Concluído", state="disabled")
        if plugin_error:
            messagebox.showwarning(
                "Aplicativo instalado; plugin pendente",
                "\n\n".join(lines),
                parent=self.root,
            )
        else:
            messagebox.showinfo("Instalação concluída", "\n\n".join(lines), parent=self.root)

        if run_after_install:
            try:
                os.startfile(install_directory / "RodoviariaETS2.exe")
            except OSError as error:
                messagebox.showerror(
                    "Não foi possível iniciar o aplicativo",
                    str(error),
                    parent=self.root,
                )


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--install-plugin")
    parser.add_argument("--result")
    args, _ = parser.parse_known_args()
    if args.install_plugin and args.result:
        raise SystemExit(run_plugin_helper(args.install_plugin, args.result))

    if not getattr(sys, "frozen", False):
        messagebox.showerror(
            "Instalador empacotado necessário",
            "Execute o arquivo RodoviariaETS2-Setup.exe criado pelo build.",
        )
        return
    root = tk.Tk()
    Installer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
