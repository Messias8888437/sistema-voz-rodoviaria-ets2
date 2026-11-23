import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from telemetria_ets2 import TelemetryReader, TelemetrySnapshot, detectar_modo, limpar_cidade

PASTA = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
CONFIG_PATH = PASTA / "config_rodoviaria.json"
ENGINE_PATH = PASTA / "falar_rodoviaria.py"
VOZES = {"Francisca (Feminina)": "pt-BR-FranciscaNeural", "Antonio (Masculino)": "pt-BR-AntonioNeural"}
VOZES_REVERSO = {valor: nome for nome, valor in VOZES.items()}
PERFIS = {
    "Automático (Detecta Passageiros / Leiteiro)": "automatico",
    "Forçar Modo Passageiros (Rodoviária)": "rodoviaria",
    "Forçar Modo Leiteiro (Coleta de Leite)": "leiteiro",
}
PERFIS_REVERSO = {valor: nome for nome, valor in PERFIS.items()}
CONFIG_PADRAO: dict[str, Any] = {
    "voice": "pt-BR-FranciscaNeural", "voice_volume": 1.75,
    "background_volume": 0.60, "bell_volume": 1.0, "echo": True,
    "profile": "automatico", "auto_announce": True,
}
BG = "#09090b"
PANEL = "#18181b"
FG = "#f4f4f5"
MUTED = "#a1a1aa"
ACCENT = "#38bdf8"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        save_config(CONFIG_PADRAO)
        return CONFIG_PADRAO.copy()
    with CONFIG_PATH.open("r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("config_rodoviaria.json deve conter um objeto JSON.")
    config = CONFIG_PADRAO.copy()
    config.update(data)
    if not isinstance(config["profile"], str) or config["profile"] not in PERFIS_REVERSO:
        raise ValueError("O perfil salvo na configuração não é suportado.")
    if not isinstance(config["auto_announce"], bool):
        raise ValueError("A opção auto_announce precisa ser true ou false.")
    if config["voice"] not in VOZES_REVERSO:
        raise ValueError("A voz salva na configuração não é suportada.")
    for key in ("voice_volume", "background_volume", "bell_volume"):
        value = config[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 2:
            raise ValueError(f"O volume {key} deve ser um número entre 0 e 2.")
    if not isinstance(config["echo"], bool):
        raise ValueError("A opção echo precisa ser true ou false.")
    return config


def save_config(config: dict[str, Any]) -> None:
    temp = CONFIG_PATH.with_suffix(".json.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(temp, CONFIG_PATH)


def background_path() -> Path | None:
    for name in ("fundo_rodoviaria.wav", "fundo_rodoviaria.mp3"):
        path = PASTA / name
        if path.is_file():
            return path
    return None


def python_command() -> list[str]:
    if not getattr(sys, "frozen", False):
        return [sys.executable]
    path = shutil.which("python.exe") or shutil.which("python")
    if path:
        return [path]
    launcher = shutil.which("py.exe") or shutil.which("py")
    if launcher:
        return [launcher, "-3.15"]
    raise FileNotFoundError("Python 3.15 não foi encontrado no PATH.")


class AppRodoviaria:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Central Rodoviária • ETS2 / Mapas Brasileiros")
        self.root.geometry("760x940")
        self.root.minsize(700, 860)
        self.root.configure(bg=BG)
        self.root.option_add("*Font", ("Segoe UI", 10))
        try:
            self.config = load_config()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            messagebox.showerror("Configuração inválida", str(error), parent=root)
            raise

        self.origin = tk.StringVar()
        self.destination = tk.StringVar()
        self.time = tk.StringVar(value="19 horas")
        self.platform = tk.StringVar(value="4")
        self.profile = tk.StringVar(value=PERFIS_REVERSO[self.config["profile"]])
        self.auto_announce = tk.BooleanVar(value=self.config["auto_announce"])
        self.voice = tk.StringVar(value=VOZES_REVERSO[self.config["voice"]])
        self.echo = tk.BooleanVar(value=self.config["echo"])
        self.status = tk.StringVar(value="PRONTO PARA ANUNCIAR")
        self.last_call = tk.StringVar(value="Nenhuma chamada realizada nesta sessão")
        self.audio_status = tk.StringVar()
        self.telemetry_status = tk.StringVar(value="PROCURANDO PLUGIN SCS...")
        self.telemetry_details = tk.StringVar(
            value="Abra o ETS2 com SHETS2Telemetry_x64.dll instalado."
        )
        self.telemetry_reader = TelemetryReader()
        self._telemetry_snapshot: TelemetrySnapshot | None = None
        self._last_job_active = False
        self._last_job_signature: tuple[str, str, str, int] | None = None
        self._last_job_start_time: int | None = None
        self._auto_announcement_pending = False
        self._auto_origin = ""
        self._auto_destination = ""
        self._auto_time = ""
        self._telemetry_after: str | None = None
        self.volume_vars = {
            key: tk.DoubleVar(value=self.config[key])
            for key in ("voice_volume", "background_volume", "bell_volume")
        }
        self.setup_styles()
        self.build_ui()
        self.update_audio_label()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._telemetry_after = self.root.after(500, self.poll_telemetry)

    def setup_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox", fieldbackground="#27272a", background="#27272a",
            foreground=FG, arrowcolor=FG, bordercolor="#3f3f46", padding=8,
        )
        style.map("Dark.TCombobox", fieldbackground=[("readonly", "#27272a")], foreground=[("readonly", FG)])
        style.configure("Dark.TCheckbutton", background=PANEL, foreground=FG, focuscolor=PANEL)
        style.map("Dark.TCheckbutton", background=[("active", PANEL)])

    def panel(self, parent: tk.Misc) -> tk.Frame:
        return tk.Frame(parent, bg=PANEL, padx=20, pady=15)

    def section_title(self, parent: tk.Widget, title: str, subtitle: str) -> None:
        tk.Label(parent, text=title, bg=PANEL, fg=FG, font=("Segoe UI", 12, "bold")).pack(anchor="w")
        tk.Label(parent, text=subtitle, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(2, 12))

    def build_ui(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(20, 14))
        tk.Label(header, text="CENTRAL DE EMBARQUE", bg=BG, fg=FG, font=("Segoe UI", 19, "bold")).pack(anchor="w")
        tk.Label(header, text="ETS2 1.62  •  MAPAS BRASILEIROS  •  SISTEMA DE VOZ", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w")
        profile_box = tk.Frame(header, bg=BG)
        profile_box.pack(side="right", anchor="e", padx=(12, 0))
        tk.Label(profile_box, text="PERFIL DE ANÚNCIO", bg=BG, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 5))
        profile_chooser = ttk.Combobox(
            profile_box, textvariable=self.profile, values=list(PERFIS),
            state="readonly", style="Dark.TCombobox", width=42,
        )
        profile_chooser.pack(anchor="e")
        profile_chooser.bind("<<ComboboxSelected>>", self.change_profile)

        led = self.panel(self.root)
        led.pack(fill="x", padx=28, pady=(0, 10))
        status_row = tk.Frame(led, bg=PANEL)
        status_row.pack(fill="x")
        tk.Label(status_row, text="●", bg=PANEL, fg="#4ade80", font=("Segoe UI", 16)).pack(side="left", padx=(0, 9))
        tk.Label(status_row, textvariable=self.status, bg=PANEL, fg="#4ade80", font=("Consolas", 12, "bold")).pack(side="left")
        tk.Label(led, textvariable=self.last_call, bg=PANEL, fg="#d4d4d8", font=("Consolas", 10), wraplength=660, justify="left").pack(anchor="w", pady=(8, 0))

        telemetry = self.panel(self.root)
        telemetry.pack(fill="x", padx=28, pady=6)
        self.section_title(
            telemetry, "Conexão direta com o ETS2",
            "Lê a memória compartilhada pelo plugin SCS, sem usar o SimHub.",
        )
        tk.Label(
            telemetry, textvariable=self.telemetry_status, bg=PANEL, fg=ACCENT,
            font=("Consolas", 10, "bold"),
        ).pack(anchor="w")
        tk.Label(
            telemetry, textvariable=self.telemetry_details, bg=PANEL, fg=MUTED,
            font=("Segoe UI", 9), wraplength=660, justify="left",
        ).pack(anchor="w", pady=(4, 5))
        ttk.Checkbutton(
            telemetry, text="Anunciar automaticamente ao iniciar um trabalho",
            variable=self.auto_announce, command=self.change_auto_announce,
            style="Dark.TCheckbutton",
        ).pack(anchor="w")

        manual = self.panel(self.root)
        manual.pack(fill="x", padx=28, pady=6)
        self.section_title(manual, "Teste manual", "Preencha os dados da viagem e dispare uma chamada de teste.")
        grid = tk.Frame(manual, bg=PANEL)
        grid.pack(fill="x")
        grid.columnconfigure((0, 1), weight=1, uniform="fields")
        self.add_field(grid, "Rodoviária de saída (origem)", self.origin, 0, 0)
        self.add_field(grid, "Destino", self.destination, 0, 1)
        self.add_field(grid, "Horário do jogo", self.time, 1, 0)
        self.add_field(grid, "Plataforma", self.platform, 1, 1)
        self.announce_button = tk.Button(
            manual, text="DISPARAR ANÚNCIO", command=self.start_announcement,
            font=("Segoe UI", 11, "bold"), bg="#0369a1", fg="white",
            activebackground="#0284c7", activeforeground="white", relief="flat",
            cursor="hand2", pady=12,
        )
        self.announce_button.pack(fill="x", pady=(12, 0))

        audio = self.panel(self.root)
        audio.pack(fill="x", padx=28, pady=6)
        self.section_title(audio, "Locutor e áudio", "Escolha a voz neural e o ambiente sonoro do terminal.")
        controls = tk.Frame(audio, bg=PANEL)
        controls.pack(fill="x")
        controls.columnconfigure(0, weight=1)
        tk.Label(controls, text="LOCUTOR", bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 5))
        chooser = ttk.Combobox(controls, textvariable=self.voice, values=list(VOZES), state="readonly", style="Dark.TCombobox")
        chooser.grid(row=1, column=0, sticky="ew", padx=(0, 14))
        chooser.bind("<<ComboboxSelected>>", self.change_voice)
        ttk.Checkbutton(controls, text="Eco de saguão", variable=self.echo, command=self.change_echo, style="Dark.TCheckbutton").grid(row=2, column=0, sticky="w", pady=(9, 0))
        tk.Button(
            controls, text="Trocar Áudio (.mp3/.wav)", command=self.import_audio,
            font=("Segoe UI", 9, "bold"), bg="#3f3f46", fg=FG,
            activebackground="#52525b", activeforeground=FG, relief="flat",
            cursor="hand2", padx=14, pady=10,
        ).grid(row=1, column=1, rowspan=2, sticky="e")
        tk.Label(audio, textvariable=self.audio_status, bg=PANEL, fg=MUTED, font=("Segoe UI", 9)).pack(anchor="w", pady=(10, 0))

        mixer = self.panel(self.root)
        mixer.pack(fill="x", padx=28, pady=6)
        self.section_title(mixer, "Mixer de volumes", "Ajustes salvos imediatamente para os anúncios.")
        self.add_slider(mixer, "Volume da voz", "voice_volume")
        self.add_slider(mixer, "Volume do som de ré / ônibus", "background_volume")
        self.add_slider(mixer, "Volume da campainha", "bell_volume")
        tk.Label(self.root, text="Configuração compartilhada com o motor de anúncios.", bg=BG, fg=MUTED, font=("Segoe UI", 8)).pack(pady=(7, 12))

    def add_field(self, parent: tk.Widget, title: str, variable: tk.StringVar, row: int, column: int) -> None:
        cell = tk.Frame(parent, bg=PANEL)
        cell.grid(row=row, column=column, sticky="ew", padx=(0, 12), pady=(0, 9))
        tk.Label(cell, text=title.upper(), bg=PANEL, fg=MUTED, font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Entry(cell, textvariable=variable, bg="#27272a", fg=FG, insertbackground=FG, relief="flat", font=("Segoe UI", 10)).pack(fill="x", ipady=8)

    def add_slider(self, parent: tk.Widget, title: str, key: str) -> None:
        row = tk.Frame(parent, bg=PANEL)
        row.pack(fill="x", pady=(0, 7))
        value_label = tk.Label(row, text=f"{self.volume_vars[key].get():.2f}", bg=PANEL, fg=ACCENT, font=("Consolas", 10, "bold"), width=5)
        tk.Label(row, text=title, bg=PANEL, fg=FG, font=("Segoe UI", 9)).pack(side="left")
        value_label.pack(side="right")
        def moved(value: str) -> None:
            value_label.config(text=f"{float(value):.2f}")
            self.config[key] = round(float(value), 2)
            self.save_settings()
        tk.Scale(
            row, from_=0, to=2, resolution=0.05, orient="horizontal", showvalue=False,
            variable=self.volume_vars[key], command=moved, bg=PANEL, fg=FG,
            troughcolor="#3f3f46", activebackground=ACCENT, highlightthickness=0,
            bd=0, length=210,
        ).pack(side="right", padx=(10, 8))

    def update_audio_label(self) -> None:
        path = background_path()
        self.audio_status.set(f"Áudio atual: {path.name}" if path else "Áudio de fundo ainda não importado.")

    def save_settings(self) -> None:
        try:
            save_config(self.config)
        except OSError as error:
            self.status.set(f"ERRO AO SALVAR CONFIGURAÇÃO: {error}")

    def change_voice(self, event: tk.Event | None = None) -> None:
        if event is None:
            return
        self.config["voice"] = VOZES[self.voice.get()]
        self.save_settings()

    def change_echo(self) -> None:
        self.config["echo"] = self.echo.get()
        self.save_settings()

    def change_profile(self, event: tk.Event | None = None) -> None:
        if event is None:
            return
        self.config["profile"] = PERFIS[self.profile.get()]
        self.save_settings()

    def change_auto_announce(self) -> None:
        self.config["auto_announce"] = self.auto_announce.get()
        self.save_settings()

    def poll_telemetry(self) -> None:
        try:
            snapshot = self.telemetry_reader.read()
        except (OSError, ValueError) as error:
            self.telemetry_reader.close()
            self._telemetry_snapshot = None
            self._last_job_active = False
            self._last_job_signature = None
            self._last_job_start_time = None
            self._auto_announcement_pending = False
            self.telemetry_status.set("ERRO NA CONEXÃO COM O PLUGIN")
            self.telemetry_details.set(str(error))
        else:
            if snapshot is None:
                self._telemetry_snapshot = None
                self._last_job_active = False
                self._last_job_signature = None
                self._last_job_start_time = None
                self._auto_announcement_pending = False
                self.telemetry_status.set("AGUARDANDO ETS2 E PLUGIN SCS")
                self.telemetry_details.set(
                    "Instale SHETS2Telemetry_x64.dll em "
                    "Euro Truck Simulator 2\\bin\\win_x64\\plugins e abra o jogo."
                )
            else:
                self.update_telemetry(snapshot)
        if self.root.winfo_exists():
            self._telemetry_after = self.root.after(1000, self.poll_telemetry)

    def update_telemetry(self, snapshot: TelemetrySnapshot) -> None:
        self._telemetry_snapshot = snapshot
        origem = limpar_cidade(snapshot.city_source)
        destino = limpar_cidade(snapshot.city_destination)
        modo = detectar_modo(snapshot.cargo)
        nome_modo = "Leiteiro (Coleta de Leite)" if modo == "leiteiro" else "Passageiros (Rodoviária)"
        situacao = "TRABALHO ATIVO" if snapshot.on_job else "CONECTADO, SEM TRABALHO ATIVO"
        self.telemetry_status.set(f"ETS2 CONECTADO • {situacao}")
        self.telemetry_details.set(
            f"{origem or 'Origem indisponível'} → {destino or 'Destino indisponível'}"
            f" • {snapshot.game_time} • {nome_modo}"
            f" • Carga: {snapshot.cargo or 'não informada'}"
        )

        assinatura = (
            origem, destino, snapshot.cargo, snapshot.job_start_time,
        )
        inicio_trabalho = snapshot.on_job and (
            not self._last_job_active
            or (
                self._last_job_start_time not in (None, 0)
                and snapshot.job_start_time not in (0, self._last_job_start_time)
            )
        )
        dados_trabalho_alterados = snapshot.on_job and assinatura != self._last_job_signature
        if snapshot.on_job and self.auto_announce.get() and inicio_trabalho:
            self._auto_announcement_pending = True
        elif not snapshot.on_job:
            self._auto_announcement_pending = False

        if snapshot.on_job:
            if inicio_trabalho or self.origin.get() in ("", self._auto_origin):
                self.origin.set(origem)
                self._auto_origin = origem
            if inicio_trabalho or self.destination.get() in ("", self._auto_destination):
                self.destination.set(destino)
                self._auto_destination = destino
            if inicio_trabalho or self.time.get() in ("", self._auto_time):
                self.time.set(snapshot.game_time)
                self._auto_time = snapshot.game_time
            elif dados_trabalho_alterados:
                self._auto_time = snapshot.game_time

        self._last_job_active = snapshot.on_job
        self._last_job_signature = assinatura if snapshot.on_job else None
        self._last_job_start_time = snapshot.job_start_time if snapshot.on_job else None
        if (
            self._auto_announcement_pending
            and (origem or destino)
            and self.announce_button["state"] != tk.DISABLED
        ):
            self.start_announcement(snapshot)
            self._auto_announcement_pending = False

    def close(self) -> None:
        if self._telemetry_after is not None:
            self.root.after_cancel(self._telemetry_after)
        self.telemetry_reader.close()
        self.root.destroy()

    def import_audio(self) -> None:
        source = filedialog.askopenfilename(
            parent=self.root, title="Escolha o áudio de fundo",
            filetypes=[("Áudio MP3 ou WAV", "*.mp3 *.wav"), ("Todos os arquivos", "*.*")],
        )
        if not source:
            return
        source_path = Path(source)
        suffix = source_path.suffix.lower()
        if suffix not in (".mp3", ".wav"):
            messagebox.showerror("Formato inválido", "Escolha um arquivo .mp3 ou .wav.", parent=self.root)
            return
        target = PASTA / f"fundo_rodoviaria{suffix}"
        other = PASTA / ("fundo_rodoviaria.wav" if suffix == ".mp3" else "fundo_rodoviaria.mp3")
        try:
            if source_path.resolve() != target.resolve():
                shutil.copy2(source_path, target)
            if other.exists():
                other.unlink()
        except OSError as error:
            messagebox.showerror("Falha ao importar áudio", str(error), parent=self.root)
            return
        self.update_audio_label()
        self.status.set("ÁUDIO DE FUNDO ATUALIZADO")

    def start_announcement(self, telemetry: TelemetrySnapshot | None = None) -> None:
        if not ENGINE_PATH.is_file():
            messagebox.showerror("Motor não encontrado", f"Arquivo ausente: {ENGINE_PATH}", parent=self.root)
            return
        if self.announce_button["state"] == tk.DISABLED:
            return
        data = {
            "origem": limpar_cidade(telemetry.city_source) if telemetry else self.origin.get().strip(),
            "destino": limpar_cidade(telemetry.city_destination) if telemetry else self.destination.get().strip(),
            "hora": telemetry.game_time if telemetry else self.time.get().strip(),
            "plataforma": self.platform.get().strip(),
            "voz": VOZES[self.voice.get()],
            "modo": PERFIS[self.profile.get()] if PERFIS[self.profile.get()] != "automatico" else "",
            "cargo": telemetry.cargo if telemetry else (
                self._telemetry_snapshot.cargo if self._telemetry_snapshot else ""
            ),
        }
        call = f"{data['origem'] or 'Origem não informada'} → {data['destino'] or 'Destino não informado'} · {data['hora'] or 'Agora'} · Plataforma {data['plataforma'] or '—'}"
        self.announce_button.config(state="disabled", text="GERANDO E REPRODUZINDO...")
        self.status.set("GERANDO VOZ E MIXANDO ÁUDIO")
        threading.Thread(target=self.run_announcement, args=(data, call), daemon=True).start()

    def run_announcement(self, data: dict[str, str], call: str) -> None:
        try:
            command = python_command() + [
                str(ENGINE_PATH), "--origem", data["origem"], "--destino", data["destino"],
                "--hora", data["hora"], "--plataforma", data["plataforma"],
                "--voz", data["voz"], "--cargo", data["cargo"],
            ]
            if data["modo"]:
                command.extend(["--modo", data["modo"]])
            result = subprocess.run(
                command, cwd=PASTA, capture_output=True, text=True, encoding="utf-8",
                errors="replace", check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            if result.returncode:
                detail = result.stderr.strip()[-1800:] or f"Motor encerrou com código {result.returncode}; consulte falar_rodoviaria.log."
                raise RuntimeError(detail)
        except (OSError, RuntimeError) as error:
            self.root.after(0, self.finish_announcement, False, str(error), call)
            return
        self.root.after(0, self.finish_announcement, True, "", call)

    def finish_announcement(self, success: bool, error: str, call: str) -> None:
        self.announce_button.config(state="normal", text="DISPARAR ANÚNCIO")
        if success:
            self.last_call.set(call)
            self.status.set("ANÚNCIO CONCLUÍDO")
        else:
            self.status.set("FALHA AO GERAR OU REPRODUZIR")
            messagebox.showerror("Falha no anúncio", error, parent=self.root)


def main() -> None:
    root = tk.Tk()
    AppRodoviaria(root)
    root.mainloop()


if __name__ == "__main__":
    main()
