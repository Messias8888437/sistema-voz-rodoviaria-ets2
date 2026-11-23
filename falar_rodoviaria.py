import argparse
import asyncio
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import edge_tts
import static_ffmpeg
import winsound

PASTA = Path(__file__).resolve().parent
ARQUIVO_CONFIG = PASTA / "config_rodoviaria.json"
VOZES = ("pt-BR-FranciscaNeural", "pt-BR-AntonioNeural")
VELOCIDADE = "+0%"
CONFIG_PADRAO: dict[str, Any] = {
    "voice": "pt-BR-FranciscaNeural",
    "voice_volume": 1.75,
    "background_volume": 0.60,
    "bell_volume": 1.0,
    "echo": True,
}
logging.basicConfig(
    filename=PASTA / "falar_rodoviaria.log",
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
LOGGER = logging.getLogger("rodoviaria")


def carregar_configuracao() -> dict[str, Any]:
    if not ARQUIVO_CONFIG.is_file():
        salvar_configuracao(CONFIG_PADRAO)
        return CONFIG_PADRAO.copy()
    with ARQUIVO_CONFIG.open("r", encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    if not isinstance(dados, dict):
        raise ValueError("config_rodoviaria.json deve conter um objeto JSON.")
    config = CONFIG_PADRAO.copy()
    config.update(dados)
    if config["voice"] not in VOZES:
        raise ValueError(f"Voz não suportada na configuração: {config['voice']!r}.")
    for chave in ("voice_volume", "background_volume", "bell_volume"):
        valor = config[chave]
        if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
            raise ValueError(f"O volume {chave!r} precisa ser um número finito.")
        if not 0 <= valor <= 2:
            raise ValueError(f"O volume {chave!r} deve ficar entre 0 e 2.")
    if not isinstance(config["echo"], bool):
        raise ValueError("A configuração 'echo' precisa ser true ou false.")
    return config


def salvar_configuracao(config: dict[str, Any]) -> None:
    temporario = ARQUIVO_CONFIG.with_suffix(".json.tmp")
    with temporario.open("w", encoding="utf-8", newline="\n") as arquivo:
        json.dump(config, arquivo, ensure_ascii=False, indent=2)
        arquivo.write("\n")
    os.replace(temporario, ARQUIVO_CONFIG)


def localizar_fundo() -> Path:
    for nome in ("fundo_rodoviaria.wav", "fundo_rodoviaria.mp3"):
        arquivo = PASTA / nome
        if arquivo.is_file():
            return arquivo
    raise FileNotFoundError("Áudio de fundo ausente: importe um WAV ou MP3 pelo aplicativo.")


def montar_anuncio(origem: str, destino: str, hora: str, plataforma: str) -> str:
    origem = origem.strip()
    trecho_origem = f" na rodoviária de {origem}," if origem else ""
    destino = destino.strip() or "seu destino"
    hora = hora.strip() or "agora"
    plataforma = plataforma.strip() or "não informada"
    return (
        f"Atenção, senhores passageiros{trecho_origem} na plataforma {plataforma}, "
        f"para o destino {destino}, às {hora}. O embarque está disponível e aberto."
    )


def executar_ffmpeg(comando: list[str]) -> subprocess.CompletedProcess[str]:
    resultado = subprocess.run(
        comando,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if resultado.returncode:
        detalhe = resultado.stderr.strip()[-2000:] or "sem detalhes do FFmpeg"
        raise RuntimeError(f"Falha no FFmpeg: {detalhe}")
    return resultado


def duracao_audio(ffprobe: str, arquivo: Path) -> float:
    resultado = executar_ffmpeg([
        ffprobe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(arquivo),
    ])
    return float(resultado.stdout.strip())


async def gerar_voz(texto: str, voz: str, arquivo: Path) -> None:
    comunicador = edge_tts.Communicate(texto, voz, rate=VELOCIDADE)
    await comunicador.save(str(arquivo))


def mixar_audio(voz: Path, destino: Path, config: dict[str, Any], temporario: Path) -> None:
    static_ffmpeg.add_paths()
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError("FFmpeg/FFprobe do pacote static-ffmpeg não foram encontrados.")

    campainha = PASTA / "campainha.wav"
    fundo = localizar_fundo()
    if not campainha.is_file():
        raise FileNotFoundError("campainha.wav não encontrado; execute gerar_audios.py.")

    frente = temporario / "frente.wav"
    filtros_voz = "highpass=f=120"
    if config["echo"]:
        filtros_voz += ",aecho=0.8:0.88:85|170:0.16|0.07"
    filtro_frente = (
        f"[0:a]aresample=44100,aformat=channel_layouts=stereo,"
        f"volume={config['bell_volume']}[camp];"
        f"[1:a]aresample=44100,aformat=channel_layouts=stereo,"
        f"{filtros_voz},volume={config['voice_volume']}[voz];"
        "[camp][voz]concat=n=2:v=0:a=1[out]"
    )
    executar_ffmpeg([
        ffmpeg, "-y", "-i", str(campainha), "-i", str(voz),
        "-filter_complex", filtro_frente, "-map", "[out]",
        "-c:a", "pcm_s16le", str(frente),
    ])

    fim_fala = duracao_audio(ffprobe, campainha) + duracao_audio(ffprobe, voz)
    duracao_total = fim_fala + 1.5
    filtro_mix = (
        f"[0:a]apad=pad_dur=1.5,atrim=duration={duracao_total:.3f}[frente];"
        f"[1:a]aresample=44100,aformat=channel_layouts=stereo,"
        f"volume={config['background_volume']},"
        f"afade=t=out:st={fim_fala:.3f}:d=1.5[fundo];"
        "[frente][fundo]amix=inputs=2:duration=first:normalize=0,"
        "alimiter=limit=0.98[out]"
    )
    executar_ffmpeg([
        ffmpeg, "-y", "-i", str(frente), "-stream_loop", "-1", "-i", str(fundo),
        "-filter_complex", filtro_mix, "-map", "[out]", "-t", f"{duracao_total:.3f}",
        "-c:a", "pcm_s16le", str(destino),
    ])


def executar_anuncio(origem: str, destino: str, hora: str, plataforma: str, voz: str | None = None) -> None:
    config = carregar_configuracao()
    voz_final = voz or config["voice"]
    if voz_final not in VOZES:
        raise ValueError(f"Voz não suportada: {voz_final!r}.")
    frase = montar_anuncio(origem, destino, hora, plataforma)
    LOGGER.info("Gerando anúncio com %s: %s", voz_final, frase)
    with tempfile.TemporaryDirectory(prefix="rodoviaria_") as pasta:
        temporario = Path(pasta)
        arquivo_voz = temporario / "voz.mp3"
        arquivo_final = temporario / "anuncio.wav"
        asyncio.run(gerar_voz(frase, voz_final, arquivo_voz))
        mixar_audio(arquivo_voz, arquivo_final, config, temporario)
        winsound.PlaySound(str(arquivo_final), winsound.SND_FILENAME)
    LOGGER.info("Anúncio reproduzido com sucesso.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sistema de voz para ETS2 / Mapa EAA")
    parser.add_argument("--origem", default="")
    parser.add_argument("--destino", default="seu destino")
    parser.add_argument("--hora", default="agora")
    parser.add_argument("--plataforma", default="não informada")
    parser.add_argument("--voz", choices=VOZES)
    args = parser.parse_args()
    try:
        executar_anuncio(args.origem, args.destino, args.hora, args.plataforma, args.voz)
    except Exception as erro:
        LOGGER.exception("Falha ao gerar ou reproduzir o anúncio.")
        print(f"Erro no anúncio: {erro}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
