#!/usr/bin/env python3
"""Gera reels-gbr-connect.mp4 do começo ao fim.

    python3 gerar.py            # gera voz + cenas + vídeo
    python3 gerar.py --sem-voz  # reaproveita narracao.mp3 e build/tempos.json

Etapas: narração (edge-tts) > cenas em HTML (Playwright, quadro a quadro)
> composição com ffmpeg (trecho da animação da logo + áudio).
"""
import glob
import json
import os
import shutil
import subprocess
import sys

from PIL import Image, ImageChops, ImageFilter

PASTA = os.path.dirname(os.path.abspath(__file__))
BUILD = os.path.join(PASTA, "build")
CFG = json.load(open(os.path.join(PASTA, "config.json"), encoding="utf-8"))
FPS = 30
SAIDA = os.path.join(PASTA, "reels-gbr-connect.mp4")


def rodar(cmd, **kw):
    print("  $", " ".join(cmd) if len(" ".join(cmd)) < 160 else " ".join(cmd)[:160] + " ...")
    subprocess.run(cmd, check=True, cwd=PASTA, **kw)


def p(*partes):
    return os.path.join(PASTA, *partes)


def limpar(pasta):
    shutil.rmtree(pasta, ignore_errors=True)
    os.makedirs(pasta)


# ---------------------------------------------------------------- arquivos
def garantir_logo():
    if os.path.exists(p(CFG["logo"])):
        return CFG["logo"], False
    print("! logo-gbr-connect.png não encontrada: usando logo PROVISÓRIA")
    pasta = p("build", "logo-prov")
    limpar(pasta)
    json.dump({"modo": "logo", "tamanho": 120}, open(p("build", "prov-logo.json"), "w"))
    rodar(["node", "scripts/render.js", "scripts/provisorio.html", "900", "400", "1", "1", pasta, "build/prov-logo.json", "transparente"])
    img = Image.open(os.path.join(pasta, "00000.png"))
    img.crop(img.getbbox()).save(p("build", "logo-provisoria.png"))
    return "build/logo-provisoria.png", True


def garantir_animacao():
    a = CFG["animacao"]
    if os.path.exists(p(a["arquivo"])):
        return p(a["arquivo"]), False
    print("! animacao-gbr.mp4 não encontrada: usando animação PROVISÓRIA")
    destino = p("build", "animacao-provisoria.mp4")
    if not os.path.exists(destino):
        pasta = p("build", "anim-prov")
        limpar(pasta)
        json.dump({"modo": "anim", "tamanho": 150}, open(p("build", "prov-anim.json"), "w"))
        rodar(["node", "scripts/render.js", "scripts/provisorio.html", "1920", "1080", str(FPS), "10", pasta, "build/prov-anim.json"])
        rodar(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", os.path.join(pasta, "%05d.png"),
               "-f", "lavfi", "-i", "sine=f=440:d=10", "-shortest",
               "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", destino])
    return destino, True


def info_video(arq):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height:format=duration", "-of", "json", arq])
    j = json.loads(out)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def recorte_auto(anim, ini, fim, largura, altura):
    """Acha a caixa da logo comparando quadros do trecho com a cor do fundo."""
    a = CFG["animacao"]
    if a["recorte"] != "auto":
        return [int(v) for v in a["recorte"]]
    pasta = p("build", "recorte")
    limpar(pasta)
    caixa = None
    n = 8
    for i in range(n):
        t = ini + (fim - ini - 0.05) * i / (n - 1)
        arq = os.path.join(pasta, f"{i}.png")
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", anim, "-frames:v", "1", arq], check=True)
        img = Image.open(arq).convert("RGB")
        fundo = img.getpixel((5, 5))
        dif = ImageChops.difference(img, Image.new("RGB", img.size, fundo)).convert("L")
        dif = dif.point(lambda v: 255 if v > 28 else 0).filter(ImageFilter.MinFilter(5))  # ignora ruído
        bb = dif.getbbox()
        if bb:
            caixa = bb if caixa is None else (min(caixa[0], bb[0]), min(caixa[1], bb[1]), max(caixa[2], bb[2]), max(caixa[3], bb[3]))
    if caixa is None:
        return [0, 0, largura, altura]
    m = a["margem_recorte"]
    x0, y0 = max(0, caixa[0] - m), max(0, caixa[1] - m)
    x1, y1 = min(largura, caixa[2] + m), min(altura, caixa[3] + m)
    w, h = (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2
    return [w, h, x0, y0]


def mascara(w, h, esfumado):
    """Máscara com bordas esfumadas: funde a animação com o fundo #E8EDF5."""
    img = Image.new("L", (w, h), 0)
    borda = esfumado
    img.paste(255, (borda, borda, w - borda, h - borda))
    img = img.filter(ImageFilter.GaussianBlur(borda / 2.2))
    arq = p("build", "mascara.png")
    img.save(arq)
    return arq


# ---------------------------------------------------------------- principal
def main():
    os.makedirs(BUILD, exist_ok=True)
    if "--sem-voz" not in sys.argv or not os.path.exists(p("build", "tempos.json")):
        print("1) Narração")
        rodar([sys.executable, "scripts/narracao.py"])
    tempos = json.load(open(p("build", "tempos.json"), encoding="utf-8"))

    print("2) Arquivos")
    logo, logo_prov = garantir_logo()
    anim, anim_prov = garantir_animacao()
    prints = [f if os.path.exists(p(f)) else None for f in CFG["telas_celular"]]

    # ---- tempos da cena final
    a = CFG["animacao"]
    T5 = tempos["inicio_cenas"][-1]
    entra = T5 + 0.12                     # a animação entra junto com a troca de fundo
    ini, fim = a["inicio"], a["fim"]
    trecho = fim - ini
    parada = a["logo_parada_minimo"]
    dur = min(CFG["duracao_maxima"], max(tempos["fim_fala"] + 0.6, entra + trecho + parada + 0.2))
    dur = round(dur * FPS) / FPS
    disponivel = dur - entra - parada     # tempo para tocar o trecho
    velocidade = 1.0
    if trecho > disponivel:
        velocidade = min(a["aceleracao_maxima"], trecho / disponivel)
        if trecho / velocidade > disponivel:   # ainda não cabe: corta o começo
            ini = fim - disponivel * velocidade
    tocado = (fim - ini) / velocidade
    print(f"   vídeo {dur:.2f}s | cena final em {T5:.2f}s | animação {ini:.2f}s a {fim:.2f}s, "
          f"velocidade {velocidade:.2f}x, toca {tocado:.2f}s e fica parada {dur - entra - tocado:.2f}s")

    W, H, _ = info_video(anim)
    cw, ch, cx, cy = recorte_auto(anim, ini, fim, W, H)
    larg = a["largura_na_tela"]
    alt = round(ch * larg / cw / 2) * 2
    if alt > 700:                         # logo muito alta: limita para não invadir o texto
        alt = 700
        larg = round(cw * alt / ch / 2) * 2
    ox, oy = (1080 - larg) // 2, max(210, a["centro_y"] - alt // 2)
    print(f"   recorte {cw}x{ch} em ({cx},{cy}) > {larg}x{alt} em ({ox},{oy})")
    mask = mascara(larg, alt, a["esfumado"])

    # ---- cenas em HTML
    print("3) Cenas (Playwright)")
    dados = {"tempos": tempos, "cfg": CFG, "duracao": dur, "logo": logo, "prints": prints}
    json.dump(dados, open(p("build", "dados.json"), "w", encoding="utf-8"), ensure_ascii=False)
    frames = p("build", "frames")
    limpar(frames)
    rodar(["node", "scripts/render.js", "cena.html", "1080", "1920", str(FPS), f"{dur}", frames, "build/dados.json"])

    # ---- composição
    print("4) Composição (ffmpeg)")
    sobra = dur - entra - tocado + 1
    filtro = (
        f"[1:v]trim=start={ini:.3f}:end={fim:.3f},setpts=(PTS-STARTPTS)/{velocidade:.4f},fps={FPS},"
        f"crop={cw}:{ch}:{cx}:{cy},scale={larg}:{alt}:flags=lanczos,"
        f"tpad=stop_mode=clone:stop_duration={sobra:.3f},format=rgba[an];"
        f"[2:v]format=gray,scale={larg}:{alt}[mk];"
        f"[an][mk]alphamerge,fade=in:st=0:d=0.22:alpha=1,setpts=PTS+{entra:.3f}/TB[anim];"
        f"[0:v][anim]overlay={ox}:{oy}:eof_action=pass:enable='gte(t,{entra:.3f})',format=yuv420p[v];"
        f"[3:a]apad,atrim=0:{dur:.3f}[a]"
    )
    rodar(["ffmpeg", "-y", "-v", "error",
           "-framerate", str(FPS), "-i", os.path.join(frames, "%05d.png"),
           "-i", anim,
           "-loop", "1", "-framerate", str(FPS), "-i", mask,
           "-i", p("narracao.mp3"),
           "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
           "-t", f"{dur:.3f}", "-r", str(FPS),
           "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", SAIDA])

    print(f"\nPronto: {SAIDA} ({dur:.2f}s)")
    if logo_prov or anim_prov:
        print("ATENÇÃO: foram usados arquivos PROVISÓRIOS. Coloque logo-gbr-connect.png e animacao-gbr.mp4 "
              "nesta pasta e rode de novo: python3 gerar.py --sem-voz")


if __name__ == "__main__":
    main()
