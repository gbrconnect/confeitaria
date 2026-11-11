# Reels GBR Connect (15 s, 1080x1920, com narração)

## Arquivos que você precisa colocar nesta pasta
- `logo-gbr-connect.png`: logo com fundo transparente (vai no selo do canto)
- `animacao-gbr.mp4`: animação da logo (1920x1080)
- opcional: `print-1.png`, `print-2.png`, `print-3.png`: telas reais (Clientes, Orçamentos, Financeiro)

Se algum faltar, o script usa uma versão PROVISÓRIA e avisa no final.

## Gerar
```bash
pip install edge-tts pillow
python3 gerar.py            # voz + cenas + vídeo
python3 gerar.py --sem-voz  # só refaz cenas e vídeo (mantém narracao.mp3)
```
Precisa de ffmpeg, Node e Playwright (Chromium).

## O que trocar
| Quero mudar | Onde |
|---|---|
| Voz | `config.json` > `"voz"` (ex.: `pt-BR-FranciscaNeural`, `pt-BR-ThalitaMultilingualNeural`). Liste as vozes com `edge-tts --list-voices \| grep pt-BR` |
| Velocidade da voz | `"rate_inicial"` (o script sobe de 5 em 5 até caber em 15 s) |
| Texto falado | `"frases"` (uma frase por cena) e `"legendas_palavras_por_bloco"` (quantas palavras por legenda) |
| Palavras em verde | `"palavras_chave"` |
| Telas do celular | coloque `print-1.png`, `print-2.png`, `print-3.png` na pasta |
| Trecho da animação | `"animacao"` > `"inicio"` / `"fim"` (segundos do mp4) |
| Recorte da logo na animação | `"recorte": "auto"` ou `[largura, altura, x, y]` em pixels do vídeo original |
| Tamanho da logo na cena final | `"largura_na_tela"` e `"centro_y"` |
| Bordas da animação | `"esfumado"` (pixels de borda esfumada) |
| Visual das cenas | `cena.html` (CSS e função `setTime`) |

Mudou só a voz ou o texto? Rode `python3 gerar.py` (sem `--sem-voz`).
