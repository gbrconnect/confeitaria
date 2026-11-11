"""Gera narracao.mp3 com edge-tts e build/tempos.json com o tempo de cada palavra.

Cada frase é sintetizada separadamente e as frases são unidas com uma pausa
curta e fixa (config "pausa_entre_frases"). Assim a voz fica no ritmo natural
e não perde tempo com os silêncios longos que o edge-tts coloca entre frases.
Se ainda assim não couber, sobe o rate de 5 em 5 % até "rate_maximo".
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import unicodedata
import wave

import edge_tts

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(PASTA, "config.json"), encoding="utf-8"))
TMP = os.path.join(PASTA, "build")
os.makedirs(TMP, exist_ok=True)
SR = 24000                      # taxa do edge-tts
ANTES, DEPOIS = 0.04, 0.16      # folga mantida antes da 1ª e depois da última palavra de cada frase


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


async def falar(texto, rate, destino):
    com = edge_tts.Communicate(
        texto, CFG["voz"], rate=f"{rate:+d}%", pitch=CFG.get("pitch", "+0Hz"),
        boundary="WordBoundary", proxy=os.environ.get("HTTPS_PROXY") or None,
    )
    palavras = []
    with open(destino, "wb") as f:
        async for c in com.stream():
            if c["type"] == "audio":
                f.write(c["data"])
            elif c["type"] == "WordBoundary":
                ini = c["offset"] / 1e7
                palavras.append({"palavra": c["text"], "inicio": ini, "fim": ini + c["duration"] / 1e7})
    return palavras


def pcm(arq):
    return subprocess.check_output(["ffmpeg", "-v", "error", "-i", arq, "-f", "s16le", "-ac", "1", "-ar", str(SR), "-"])


def alinhar(fi, frase, palavras, desloc):
    saida, j = [], 0
    for wi, w in enumerate(frase.split()):
        k = j
        while k < len(palavras) and norm(palavras[k]["palavra"]) != norm(w):
            k += 1
        if k == len(palavras):
            raise SystemExit(f"Não achei a palavra '{w}' nos tempos do edge-tts")
        p = palavras[k]
        saida.append({"frase": fi, "indice": wi, "texto": w,
                      "inicio": round(p["inicio"] + desloc, 3), "fim": round(p["fim"] + desloc, 3)})
        j = k + 1
    return saida


def gerar(rate):
    pausa = CFG.get("pausa_entre_frases", 0.3)
    audio, palavras, cursor = b"", [], 0.0
    for fi, frase in enumerate(CFG["frases"]):
        arq = os.path.join(TMP, f"frase-{fi + 1}.mp3")
        ws = asyncio.run(falar(frase, rate, arq))
        dados = pcm(arq)
        ini = max(0.0, ws[0]["inicio"] - ANTES)
        fim = min(len(dados) / 2 / SR, ws[-1]["fim"] + DEPOIS)
        trecho = dados[int(ini * SR) * 2:int(fim * SR) * 2]
        palavras += alinhar(fi, frase, ws, cursor - ini)
        audio += trecho
        cursor += len(trecho) / 2 / SR
        if fi < len(CFG["frases"]) - 1:
            silencio = max(0.0, pausa - DEPOIS)
            audio += b"\x00\x00" * int(silencio * SR)
            cursor += int(silencio * SR) / SR
    audio += b"\x00\x00" * int(0.3 * SR)   # respiro no fim
    bruto = os.path.join(TMP, "narracao-bruta.wav")
    with wave.open(bruto, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes(audio)
    return bruto, palavras


def main():
    maxima = CFG["duracao_maxima"]
    final_min = CFG.get("cena_final_minimo", 3.2)
    rate = CFG["rate_inicial"]
    while True:
        bruto, palavras = gerar(rate)
        fim_fala = palavras[-1]["fim"]
        inicio_final = min(p["inicio"] for p in palavras if p["frase"] == len(CFG["frases"]) - 1)
        if fim_fala <= maxima - 0.4 and maxima - inicio_final >= final_min:
            break
        if rate >= CFG["rate_maximo"]:
            sys.exit(f"A fala não coube em {maxima}s mesmo com rate {rate:+d}% (termina em {fim_fala:.2f}s, "
                     f"cena final em {inicio_final:.2f}s). Encurte o texto em config.json > frases.")
        print(f"rate {rate:+d}%: fala termina em {fim_fala:.2f}s. Subindo o rate.")
        rate += 5

    # Normaliza o volume (EBU R128, padrão de redes sociais) e grava em 48 kHz
    final = os.path.join(PASTA, "narracao.mp3")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", bruto,
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-b:a", "192k", final], check=True)

    inicios = [min(p["inicio"] for p in palavras if p["frase"] == fi) for fi in range(len(CFG["frases"]))]
    inicios[0] = 0.0  # o gancho aparece no primeiro frame
    tempos = {"rate": rate, "fim_fala": fim_fala, "inicio_cenas": inicios, "palavras": palavras}
    json.dump(tempos, open(os.path.join(TMP, "tempos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Narração ok: rate {rate:+d}%, fala de 0 a {fim_fala:.2f}s, cenas em {[round(x, 2) for x in inicios]}")


if __name__ == "__main__":
    main()
