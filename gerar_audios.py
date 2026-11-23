import math
import random
import struct
import wave
from pathlib import Path

PASTA = Path(__file__).resolve().parent
TAXA = 44100

def salvar_wav(caminho, amostras):
    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(1)
        arquivo.setsampwidth(2)
        arquivo.setframerate(TAXA)
        arquivo.writeframes(b"".join(struct.pack("<h", max(-32768, min(32767, int(x * 32767)))) for x in amostras))

def gerar_campainha():
    notas = (880.0, 659.25, 784.0, 523.25)
    som = []
    for frequencia in notas:
        n = int(TAXA * 0.27)
        for i in range(n):
            t = i / TAXA
            envelope = math.exp(-7.0 * t) * min(1.0, i / 300)
            onda = math.sin(2 * math.pi * frequencia * t) + 0.22 * math.sin(2 * math.pi * frequencia * 2.01 * t)
            som.append(0.52 * envelope * onda)
        som.extend([0.0] * int(TAXA * 0.07))
    eco = som + [0.0] * int(TAXA * 0.65)
    for atraso, ganho in ((0.13, 0.32), (0.27, 0.19), (0.43, 0.10), (0.58, 0.045)):
        deslocamento = int(TAXA * atraso)
        for i, valor in enumerate(som):
            eco[i + deslocamento] += valor * ganho
    salvar_wav(PASTA / "campainha.wav", eco)

def rpm_em(t):
    if t < 3.0:
        return 620.0
    if t < 8.0:
        return 620.0 + (t - 3.0) * 78.0
    if t < 10.0:
        return 1010.0
    if t < 14.0:
        return 1010.0 - (t - 10.0) * 97.5
    return 620.0

def gerar_fundo_onibus():
    segundos = 24.0
    total = int(TAXA * segundos)
    rng = random.Random(162)
    amostras = []
    fase = 0.0
    ruido_filtrado = 0.0
    picos_ar = (5.2, 11.6, 14.2, 22.8)
    for i in range(total):
        t = i / TAXA
        rpm = rpm_em(t)
        frequencia_disparos = rpm / 20.0
        fase += 2.0 * math.pi * frequencia_disparos / TAXA
        motor = (
            0.52 * math.sin(fase)
            + 0.28 * math.sin(2.0 * fase + 0.3)
            + 0.16 * math.sin(3.0 * fase + 0.7)
            + 0.10 * math.sin(4.0 * fase + 1.1)
            + 0.06 * math.sin(6.0 * fase)
        )
        ganho_motor = 0.25 + 0.07 * max(0.0, (rpm - 620.0) / 390.0)
        amostra = ganho_motor * motor + 0.045 * math.sin(2.0 * math.pi * 42.0 * t)

        ruido_filtrado += 0.12 * (rng.uniform(-1.0, 1.0) - ruido_filtrado)
        for inicio in picos_ar:
            duracao = 0.72 if inicio != 22.8 else 0.5
            posicao = t - inicio
            if 0.0 <= posicao < duracao:
                envelope = min(1.0, posicao / 0.035, (duracao - posicao) / 0.16)
                amostra += 0.60 * envelope * ruido_filtrado

        tempo_re = t - 15.0
        ciclo_re = tempo_re % 1.18
        if 0.0 <= tempo_re < 8.5 and ciclo_re < 0.48:
            envelope = min(1.0, ciclo_re / 0.025, (0.48 - ciclo_re) / 0.06)
            alarme = math.sin(2.0 * math.pi * 880.0 * t) + 0.28 * math.sin(2.0 * math.pi * 1175.0 * t)
            amostra += 0.40 * envelope * alarme

        amostras.append(amostra)

    pico = max(abs(x) for x in amostras) or 1.0
    escala = 0.88 / pico
    salvar_wav(PASTA / "fundo_rodoviaria.wav", [x * escala for x in amostras])

def main():
    gerar_campainha()
    gerar_fundo_onibus()
    print("Gerados campainha.wav e fundo_rodoviaria.wav com síntese nativa.")

if __name__ == "__main__":
    main()
