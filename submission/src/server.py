"""Servidor local da interface web.

Só abre o servidor: serve a pasta web/ e encaminha os pedidos da página
para site_api.py, que os responde com o backend (o mesmo de main.py).

Utilização (a partir da raiz do projeto)::

    python submission/src/server.py [--port 8765] [--lan] [--allow-host NOME]

Depois abre http://127.0.0.1:8765 no browser.

Rotas:
    GET  /api/health      estado do servidor e da chave do Gemini
    POST /api/extract     corpo = PDF; carrega-o e descreve-o
    POST /api/unzip       corpo = ZIP; carrega todos os PDFs lá dentro
    GET  /api/layout      ?doc_id=; descreve um documento já carregado
    POST /api/analyze     {"doc_id"}; as palavras a censurar
    POST /api/redact      {"doc_id", "ids", "format"}; o PDF ou o texto
    POST /api/redact-all  {"docs": [...]}; ZIP com todos os documentos
    GET  /api/page        ?doc_id=&n=; imagem da página n do original
    POST /api/preview     {"doc_id", "ids", "n"}; imagem da página n redigida

Por omissão só escuta em 127.0.0.1.
"""
import argparse
import json
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import site_api
from site_api import ErroApi

WEB_DIR = Path(__file__).resolve().parent / "web"

# Nomes aceites no cabeçalho Host; --allow-host acrescenta mais.
HOSTS_PERMITIDOS = {"localhost", "127.0.0.1"}
ACEITAR_IPS = False

PDF = "application/pdf"
ZIP = "application/zip"
PNG = "image/png"
TXT = "text/plain; charset=utf-8"


def responder_get(rota, q):
    """Devolve (corpo, tipo) de uma rota GET da API, ou None."""
    if rota == "/api/health":
        return {
            "ok": True,
            "has_key": site_api.tem_chave(),
            "model": site_api.modelo(),
        }, None

    if rota == "/api/layout":
        return site_api.descrever(q.get("doc_id")), None

    if rota == "/api/page":
        imagem = site_api.imagem_original(q.get("doc_id"), int(q.get("n", 0)))
        return imagem, PNG

    return None


def responder_post(rota, ler):
    """Devolve (corpo, tipo, nome do ficheiro) de uma rota POST da API."""
    if rota == "/api/extract":
        return site_api.descrever(site_api.carregar(ler(PDF))), None, None

    if rota == "/api/unzip":
        return site_api.abrir_zip(ler(ZIP)), None, None

    pedido = json.loads(ler("application/json"))
    doc_id = pedido.get("doc_id")
    ids = pedido.get("ids") or []

    if rota == "/api/analyze":
        return site_api.analisar(doc_id), None, None

    if rota == "/api/redact" and pedido.get("format") == "txt":
        return site_api.redigir_texto(doc_id, ids), TXT, "anonimizado.txt"

    if rota == "/api/redact":
        return site_api.redigir_pdf(doc_id, ids), PDF, "anonimizado.pdf"

    if rota == "/api/redact-all":
        docs = pedido.get("docs") or []
        return site_api.redigir_tudo(docs), ZIP, "anonimizados.zip"

    if rota == "/api/preview":
        n = int(pedido.get("n", 0))
        return site_api.imagem_redigida(doc_id, ids, n), PNG, None

    raise ErroApi(404, "Rota desconhecida.")


class Manipulador(SimpleHTTPRequestHandler):
    """Serve a pasta web/ e a API em /api/."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _anfitriao_valido(self):
        # Protege contra DNS rebinding: só aceita nomes conhecidos. Com
        # --lan aceita também endereços IP, que não são vulneráveis a isso.
        anfitriao = self.headers.get("Host", "").rsplit(":", 1)[0]
        if anfitriao.lower() in HOSTS_PERMITIDOS:
            return True
        ip = re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", anfitriao)
        return bool(ACEITAR_IPS and ip)

    def _responder(self, estado, corpo, tipo=None, nome=None):
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo, ensure_ascii=False).encode("utf-8")

        self.send_response(estado)
        self.send_header("Content-Type", tipo or "application/json")
        self.send_header("Content-Length", str(len(corpo)))

        if nome:
            self.send_header(
                "Content-Disposition", f'attachment; filename="{nome}"'
            )

        self.end_headers()
        self.wfile.write(corpo)

    def _ler_corpo(self, tipo):
        # Exigir o Content-Type obriga a um preflight CORS, pelo que
        # outros sites não conseguem chamar a API.
        if self.headers.get_content_type() != tipo:
            raise ErroApi(415, f"Content-Type esperado: {tipo}")

        tamanho = int(self.headers.get("Content-Length") or 0)

        if tamanho <= 0:
            raise ErroApi(400, "Pedido sem conteúdo.")

        if tamanho > site_api.MAX_UPLOAD:
            raise ErroApi(413, "O ficheiro excede o limite de 25 MB.")

        return self.rfile.read(tamanho)

    def _api(self, atender):
        """Corre um pedido da API e transforma os erros em JSON."""
        if not self._anfitriao_valido():
            return self._responder(403, {"error": "Anfitrião inválido."})

        try:
            return self._responder(200, *atender())
        except ErroApi as erro:
            return self._responder(erro.estado, {"error": str(erro)})
        except (ValueError, AttributeError):
            return self._responder(400, {"error": "Pedido inválido."})
        except Exception as erro:
            return self._responder(500, {"error": f"Erro interno: {erro}"})

    def do_GET(self):
        url = urlsplit(self.path)

        if not url.path.startswith("/api/"):
            if not self._anfitriao_valido():
                return self._responder(403, {"error": "Anfitrião inválido."})
            return super().do_GET()

        consulta = {k: v[0] for k, v in parse_qs(url.query).items()}

        def atender():
            resposta = responder_get(url.path, consulta)
            if resposta is None:
                raise ErroApi(404, "Rota desconhecida.")
            return resposta

        return self._api(atender)

    def do_POST(self):
        rota = urlsplit(self.path).path
        return self._api(lambda: responder_post(rota, self._ler_corpo))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--allow-host",
        action="append",
        default=[],
        metavar="NOME",
        help="aceitar também este nome no cabeçalho Host (por exemplo, "
        "o nome do Tailscale, usado com 'tailscale serve')",
    )
    parser.add_argument(
        "--lan",
        action="store_true",
        help="escutar na rede local (acessível por IP:porta, por exemplo "
        "a partir do telemóvel). Qualquer pessoa na rede pode usar a "
        "chave do Gemini enquanto estiver ligado.",
    )
    args = parser.parse_args()
    global ACEITAR_IPS
    ACEITAR_IPS = args.lan
    HOSTS_PERMITIDOS.update(h.lower().rstrip(".") for h in args.allow_host)

    servidor = ThreadingHTTPServer(
        ("0.0.0.0" if args.lan else "127.0.0.1", args.port), Manipulador
    )
    print(f"Interface web em http://127.0.0.1:{args.port}", flush=True)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor terminado.", flush=True)
    finally:
        servidor.server_close()


if __name__ == "__main__":
    main()
