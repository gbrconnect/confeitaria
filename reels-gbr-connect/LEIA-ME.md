# Reels GBR Connect (15 s, 1080x1920, com narração)

## Arquivos que você precisa colocar nesta pasta
- `logo-gbr-connect.png`: logo com fundo transparente (vai no selo do canto). A versão atual foi gerada a partir da logo com fundo branco, removendo o branco.
- `animacao-gbr.mp4`: animação da logo (1920x1080)
- opcional: `print-1.png`, `print-2.png`, `print-3.png`: prints reais do sistema no computador (Clientes, Orçamentos, Financeiro), de preferência em 16:10 (ex.: 1440x900). Eles ocupam a tela inteira do notebook.

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
| Velocidade da voz | `"rate_inicial"` (+10% = natural). Se o texto não couber em 15 s, o script sobe no máximo até `"rate_maximo"` (15%) e depois pede para encurtar o texto |
| Pausa entre frases | `"pausa_entre_frases"` (segundos). Cada frase é gerada separada e unida com essa pausa |
| Texto falado | `"frases"` (uma frase por cena) e `"legendas_palavras_por_bloco"` (quantas palavras por legenda) |
| Palavras em verde | `"palavras_chave"` |
| Telas do computador | coloque `print-1.png`, `print-2.png`, `print-3.png` na pasta |
| Trecho da animação | `"animacao"` > `"inicio"` / `"fim"` (segundos do mp4) e `"logo_completa_em"` (quando a logo fica completa e parada) |
| Recorte da logo na animação | `"recorte": "auto"` ou `[largura, altura, x, y]` em pixels do vídeo original |
| Tamanho da logo na cena final | `"largura_na_tela"` e `"centro_y"` |
| Bordas da animação | `"esfumado"` (pixels de borda esfumada) e `"margem_recorte"` (folga em volta da logo). O fundo da animação é ajustado automaticamente para #E8EDF5 (`"igualar_fundo": false` desliga) |
| Visual das cenas | `cena.html` (CSS e função `setTime`) |

Mudou só a voz ou o texto? Rode `python3 gerar.py` (sem `--sem-voz`).
