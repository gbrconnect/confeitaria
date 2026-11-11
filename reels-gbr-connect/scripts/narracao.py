"""Gera narracao.mp3 com edge-tts e tempos.json com o tempo de cada palavra.

Se a fala passar do tempo, sobe o rate de 5 em 5 % até caber.
"""
import asyncio
import json
import os
import re
import subprocess
import sys
import unicodedata

import edge_tts

PASTA = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = json.load(open(os.path.join(PASTA, "config.json"), encoding="utf-8"))
TMP = os.path.join(PASTA, "build")
os.makedirs(TMP, exist_ok=True)


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in s if unicodedata.category(c) != "Mn"))


async def falar(rate, destino):
    texto = " ".join(CFG["frases"])
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


def alinhar(palavras):
    """Associa cada palavra do TTS a (frase, índice da palavra na frase)."""
    alvo = []
    for fi, frase in enumerate(CFG["frases"]):
        for wi, w in enumerate(frase.split()):
            alvo.append((fi, wi, w))
    saida, j = [], 0
    for fi, wi, w in alvo:
        # procura a palavra no fluxo do TTS (tolerante a pontuação)
        k = j
        while k < len(palavras) and norm(palavras[k]["palavra"]) != norm(w):
            k += 1
        if k == len(palavras):
            raise SystemExit(f"Não achei a palavra '{w}' nos tempos do edge-tts")
        p = palavras[k]
        saida.append({"frase": fi, "indice": wi, "texto": w, "inicio": round(p["inicio"], 3), "fim": round(p["fim"], 3)})
        j = k + 1
    return saida


def duracao(arq):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", arq])
    return float(out)


def main():
    maxima = CFG["duracao_maxima"]
    rate = CFG["rate_inicial"]
    bruto = os.path.join(TMP, "narracao-bruta.mp3")
    while True:
        palavras = alinhar(asyncio.run(falar(rate, bruto)))
        fim_fala = palavras[-1]["fim"]
        inicio_final = min(p["inicio"] for p in palavras if p["frase"] == len(CFG["frases"]) - 1)
        # a fala termina com folga e a cena final tem pelo menos 2,6 s
        if fim_fala <= maxima - 0.4 and maxima - inicio_final >= 2.6:
            break
        if rate >= CFG["rate_maximo"]:
            sys.exit(f"Mesmo com rate {rate:+d}% a fala não coube em {maxima}s")
        print(f"rate {rate:+d}%: fala termina em {fim_fala:.2f}s, cena final começa em {inicio_final:.2f}s. Subindo o rate.")
        rate += 5

    # Normaliza o volume (EBU R128, padrão de redes sociais) e grava em 48 kHz
    final = os.path.join(PASTA, "narracao.mp3")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", bruto,
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-b:a", "192k", final], check=True)

    inicios = []
    for fi in range(len(CFG["frases"])):
        inicios.append(min(p["inicio"] for p in palavras if p["frase"] == fi))
    inicios[0] = 0.0  # o gancho aparece no primeiro frame
    tempos = {"rate": rate, "duracao_audio": round(duracao(final), 3), "fim_fala": fim_fala,
              "inicio_cenas": inicios, "palavras": palavras}
    json.dump(tempos, open(os.path.join(PASTA, "build", "tempos.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"Narração ok: rate {rate:+d}%, fala de 0 a {fim_fala:.2f}s, cenas em {[round(x, 2) for x in inicios]}")


if __name__ == "__main__":
    main()
