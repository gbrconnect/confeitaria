#!/usr/bin/env python3
"""Servidor local para a animação Sweet Ka.

Uso:  python3 servidor.py [porta]   →  abra http://localhost:8765/

- Serve a página (index.html) e o mp4-muxer local.
- POST /save?name=arquivo   grava o corpo em ./saida/arquivo (quadros PNG de teste, MP4 do WebCodecs).
- POST /audio, /start, /frame, /end   recebem a trilha (WAV) e os quadros RGBA da página
  (?servidor) e codificam o MP4 com ffmpeg: H.264 60 fps ~22 Mbps + AAC 192 kbps.
"""
import http.server, os, subprocess, sys, urllib.parse

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, 'saida')
os.makedirs(SAIDA, exist_ok=True)
W, H, FPS = 1920, 1080, 60
estado = {'ff': None}


class H_(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=AQUI, **k)

    def log_message(self, *a):
        pass

    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        return self.rfile.read(n)

    def _ok(self, txt='ok'):
        b = txt.encode()
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == '/save':
            nome = os.path.basename(q.get('name', ['arquivo.bin'])[0])
            with open(os.path.join(SAIDA, nome), 'wb') as f:
                f.write(self._body())
            return self._ok(nome)
        if u.path == '/audio':
            with open(os.path.join(SAIDA, 'trilha.wav'), 'wb') as f:
                f.write(self._body())
            return self._ok()
        if u.path == '/start':
            self._body()
            saida = os.path.join(SAIDA, 'sweet-ka-logo.mp4')
            cmd = ['ffmpeg', '-y', '-loglevel', 'error',
                   '-f', 'rawvideo', '-pix_fmt', 'rgba', '-s', f'{W}x{H}', '-r', str(FPS), '-i', 'pipe:0',
                   '-i', os.path.join(SAIDA, 'trilha.wav'),
                   '-vf', 'scale=out_color_matrix=bt709:out_range=tv,format=yuv420p',
                   '-c:v', 'libx264', '-preset', 'slow', '-profile:v', 'high', '-level', '4.2', '-x264-params', 'aq-mode=3',
                   '-b:v', '22M', '-maxrate', '26M', '-bufsize', '44M', '-g', '60',
                   '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                   '-c:a', 'aac', '-b:a', '192k', '-ar', '48000',
                   '-movflags', '+faststart', '-shortest', saida]
            estado['ff'] = subprocess.Popen(cmd, stdin=subprocess.PIPE)
            return self._ok()
        if u.path == '/frame':
            estado['ff'].stdin.write(self._body())
            return self._ok()
        if u.path == '/end':
            self._body()
            ff = estado['ff']
            ff.stdin.close()
            ff.wait()
            return self._ok(f'ffmpeg terminou com código {ff.returncode}')
        self.send_error(404)


if __name__ == '__main__':
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f'Abra http://localhost:{porta}/  (Ctrl+C para sair)')
    http.server.ThreadingHTTPServer(('127.0.0.1', porta), H_).serve_forever()
