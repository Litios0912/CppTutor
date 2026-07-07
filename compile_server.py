#!/data/data/com.termux/files/usr/bin/python3
import http.server
import json
import subprocess
import tempfile
import os
import signal
import sys

PORT = 8080
COMPILE_TIMEOUT = 15

def compile_code(code, lang):
    suffix = '.c' if lang == 'c' else '.cpp'
    compiler = 'clang' if lang == 'c' else 'clang++'
    flags = ['-Wall', '-Wextra', '-std=c11'] if lang == 'c' else ['-Wall', '-Wextra', '-std=c++17']

    tmpdir = tempfile.mkdtemp()
    src_path = os.path.join(tmpdir, 'program' + suffix)
    out_path = os.path.join(tmpdir, 'program')

    try:
        with open(src_path, 'w') as f:
            f.write(code)

        cmd = [compiler] + flags + [src_path, '-o', out_path]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT
        )

        if result.returncode != 0:
            return {'success': False, 'output': result.stderr or result.stdout}

        run_result = subprocess.run(
            [out_path],
            capture_output=True,
            text=True,
            timeout=5
        )

        output = run_result.stdout + run_result.stderr
        if not output:
            output = 'Programa compilado y ejecutado sin salida.'

        return {'success': True, 'output': output}

    except subprocess.TimeoutExpired:
        return {'success': False, 'output': 'Error: Tiempo de compilacion o ejecucion agotado (>{0}s)'.format(COMPILE_TIMEOUT)}
    except Exception as e:
        return {'success': False, 'output': 'Error: ' + str(e)}
    finally:
        try:
            for f in [src_path, out_path]:
                if os.path.exists(f):
                    os.remove(f)
            os.rmdir(tmpdir)
        except:
            pass

class CompileHandler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/compile':
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            try:
                data = json.loads(body)
                code = data.get('code', '')
                lang = data.get('lang', 'cpp')
                result = compile_code(code, lang)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'output': str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/ping':
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        print(f"[CompileServer] {args[0]} {args[1]} {args[2]}")

def main():
    server = http.server.HTTPServer(('127.0.0.1', PORT), CompileHandler)
    print(f"[CompileServer] Servidor iniciado en puerto {PORT}")
    print(f"[CompileServer] Escuchando en 127.0.0.1:{PORT}")
    server.serve_forever()

if __name__ == '__main__':
    main()
