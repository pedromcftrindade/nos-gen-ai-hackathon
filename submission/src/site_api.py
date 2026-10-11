"""O que a página web pede ao backend.

Cada pedido da página é respondido com as mesmas funções que main.py usa:

    extrair    -> pdf_extract.extrair_texto_pdf
    analisar   -> detector.processar_com_gemini
    texto      -> redact_text.FinalText
    pdf        -> redact_text.substituicoes_por_id
                  + redact_pdf.substituir_informacoes_sensiveis

Tal como main.py, isto grava em submission/ o texto extraído, as respostas
do Gemini, o sensitive_info.json e o submission.txt. O submission.txt fica
com o texto censurado do último documento analisado ou exportado, com as
palavras escolhidas na página nesse momento.

O que fica aqui é só o que o site precisa e o backend não tem: guardar os
PDFs carregados, mostrar as páginas como imagem, dizer onde está cada
palavra na página e abrir/criar ficheiros ZIP.
"""
import hashlib
import io
import os
import tempfile
import threading
import zipfile
from pathlib import Path

import fitz
from dotenv import load_dotenv

from config import MODEL, SUBMISSION_FILE
from detector import processar_com_gemini
from parser_aux import lista_para_dict, palavras_do_valor, separar_token
from pdf_extract import extrair_texto_pdf
from redact_pdf import substituir_informacoes_sensiveis
from redact_text import FinalText, censurar_token, substituicoes_por_id

ROOT_DIR = Path(__file__).resolve().parents[2]
SAMPLE_PDF = ROOT_DIR / "raw_data" / "document_to_anonymize.pdf"

load_dotenv(ROOT_DIR / ".env")   # além do submission/src/.env que config.py lê

MAX_UPLOAD = 25 * 1024 * 1024
DPI_IMAGEM = 130   # resolução das páginas mostradas no browser
MAX_PDFS_ZIP = 30   # PDFs lidos de um ZIP; os restantes são ignorados

# doc_id -> {"pdf": bytes, "texto": str, "previa": (ids, pdf redigido)}
DOCUMENTOS = {}
# O backend escreve sempre nos mesmos ficheiros: um pedido de cada vez.
TRINCO = threading.Lock()


class ErroApi(Exception):
    """Erro que é devolvido ao browser como JSON."""

    def __init__(self, estado, mensagem):
        super().__init__(mensagem)
        self.estado = estado


def tem_chave():
    return bool(os.environ.get("GEMINI_API_KEY"))


def modelo():
    return MODEL


# ============================================================
# Documentos carregados
# ============================================================

def _com_ficheiro(pdf, funcao):
    """Chama funcao(caminho) com o PDF num ficheiro temporário (o backend
    trabalha com caminhos, a página envia bytes)."""
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / "entrada.pdf"
        caminho.write_bytes(pdf)
        return funcao(caminho, Path(pasta))


def carregar(pdf):
    """Regista um PDF e devolve o seu doc_id."""
    doc_id = hashlib.sha1(pdf).hexdigest()[:12]

    if doc_id not in DOCUMENTOS:
        try:
            with TRINCO:
                texto = _com_ficheiro(
                    pdf, lambda caminho, _: extrair_texto_pdf(caminho)
                )
        except Exception as erro:
            raise ErroApi(400, "Não foi possível abrir o PDF.") from erro

        if not texto.strip():
            raise ErroApi(
                422,
                "O PDF não contém texto extraível. "
                "Se for digitalizado, será necessário OCR.",
            )

        DOCUMENTOS[doc_id] = {"pdf": pdf, "texto": texto}

    return doc_id


def obter(doc_id):
    """Devolve um documento já carregado (ou o PDF de exemplo)."""
    if doc_id == "sample" and doc_id not in DOCUMENTOS:
        DOCUMENTOS[doc_id] = DOCUMENTOS[carregar(SAMPLE_PDF.read_bytes())]

    documento = DOCUMENTOS.get(doc_id)

    if documento is None:
        raise ErroApi(404, "Documento desconhecido. Volta a carregá-lo.")

    return documento


def descrever(doc_id):
    """O que a página precisa para mostrar um documento."""
    documento = obter(doc_id)
    texto = documento["texto"]
    tokens = texto.split()
    caixas, razoes = _localizar_palavras(documento["pdf"], tokens)

    return {
        "doc_id": doc_id,
        # Linhas de palavras, pela ordem de texto.split() (os ids).
        "pages": [[
            linha.split() for linha in texto.splitlines() if linha.strip()
        ]],
        # Como o backend escreve cada palavra quando a censura.
        "masks": [
            censurar_token(i, token, _palavras(tokens, [i]))[0]
            for i, token in enumerate(tokens)
        ],
        "boxes": caixas,
        "ratios": razoes,
        "words": len(tokens),
    }


def abrir_zip(dados):
    """Carrega os PDFs de um ZIP, sem escrever o ZIP em disco.

    Cada ficheiro é lido só até MAX_UPLOAD, para um ZIP malicioso não
    encher a memória. Devolve os documentos e os nomes ignorados.
    """
    try:
        arquivo = zipfile.ZipFile(io.BytesIO(dados))
    except zipfile.BadZipFile as erro:
        raise ErroApi(400, "O ficheiro ZIP não é válido.") from erro

    docs = []
    ignorados = []

    with arquivo:
        for info in arquivo.infolist():
            nome = Path(info.filename).name

            if (
                info.is_dir()
                or nome.startswith(".")
                or "__MACOSX" in info.filename
            ):
                continue

            if not nome.lower().endswith(".pdf"):
                ignorados.append(f"{nome} (não é PDF)")
                continue

            if len(docs) >= MAX_PDFS_ZIP:
                ignorados.append(f"{nome} (limite de {MAX_PDFS_ZIP})")
                continue

            try:
                with arquivo.open(info) as ficheiro:
                    pdf = ficheiro.read(MAX_UPLOAD + 1)

                if len(pdf) > MAX_UPLOAD:
                    raise ErroApi(413, "excede 25 MB")

                docs.append({"name": nome, **descrever(carregar(pdf))})
            except ErroApi as erro:
                ignorados.append(f"{nome} ({erro})")
            except (RuntimeError, zipfile.BadZipFile):
                ignorados.append(f"{nome} (protegido ou corrompido)")

    return {"docs": docs, "skipped": ignorados}


# ============================================================
# Análise e redação: o backend
# ============================================================

def analisar(doc_id):
    """Pede ao backend as palavras a censurar de um documento."""
    documento = obter(doc_id)

    if not tem_chave():
        raise ErroApi(
            400,
            "GEMINI_API_KEY não encontrada. "
            "Verifica o ficheiro submission/src/.env.",
        )

    try:
        with TRINCO:
            valores = processar_com_gemini(documento["texto"])
    except RuntimeError as erro:   # inclui RespostaInvalida
        raise ErroApi(502, str(erro)) from erro

    # Um valor pode ter várias palavras ("Rua das Flores"); a página
    # trabalha palavra a palavra, por isso a palavra k fica no id + k.
    pares = {}

    for valor, id_, cat, sub in valores:
        for k, palavra in enumerate(palavras_do_valor(valor)):
            pares.setdefault((palavra, id_ + k), (cat, sub))

    # Como main.py: o resultado com tudo o que foi detetado vai para o
    # submission.txt (as exportações atualizam-no com a escolha final).
    redigir_texto(doc_id, [id_ for _, id_ in pares])

    return {
        "pairs": [
            [palavra, id_, cat, sub]
            for (palavra, id_), (cat, sub) in sorted(
                pares.items(), key=lambda par: (par[0][1], par[0][0])
            )
        ],
        "model": MODEL,
    }


def _palavras(tokens, ids):
    """Os ids escolhidos na página, no formato que o backend usa
    ({palavra: {ids}}, feito por parser_aux.lista_para_dict)."""
    pares = []

    for i in {i for i in ids if isinstance(i, int)}:
        if not 0 <= i < len(tokens):
            raise ErroApi(400, f"Id fora do documento: {i}")

        pares.append((separar_token(tokens[i])[1] or tokens[i], i))

    return lista_para_dict(pares)


def redigir_texto(doc_id, ids):
    """O texto censurado; fica também gravado em submission.txt."""
    texto = obter(doc_id)["texto"]
    final = FinalText(texto, _palavras(texto.split(), ids))
    SUBMISSION_FILE.write_text(final, encoding="utf-8")
    return final.encode("utf-8")


def redigir_pdf(doc_id, ids, exportar=True):
    """O PDF censurado. Numa exportação, o submission.txt acompanha a
    mesma escolha; na pré-visualização (exportar=False) não se mexe nele."""
    if exportar:
        redigir_texto(doc_id, ids)

    documento = obter(doc_id)
    texto = documento["texto"]
    trocas = substituicoes_por_id(texto, _palavras(texto.split(), ids))

    def redigir(entrada, pasta):
        saida = pasta / "saida.pdf"
        substituir_informacoes_sensiveis(entrada, saida, trocas)
        return saida.read_bytes()

    return _com_ficheiro(documento["pdf"], redigir)


def redigir_tudo(pedidos):
    """ZIP com o PDF e o texto redigidos de cada documento pedido."""
    saida = io.BytesIO()
    usados = set()

    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as arquivo:
        for pedido in pedidos:
            doc_id = pedido.get("doc_id")
            ids = pedido.get("ids") or []
            base = Path(str(pedido.get("name") or doc_id)).stem or "doc"

            # Dois ficheiros com o mesmo nome não se sobrepõem.
            nome, n = base, 2
            while nome in usados:
                nome, n = f"{base} ({n})", n + 1
            usados.add(nome)

            arquivo.writestr(
                f"{nome}_anonimizado.pdf", redigir_pdf(doc_id, ids)
            )
            arquivo.writestr(
                f"{nome}_anonimizado.txt", redigir_texto(doc_id, ids)
            )

    return saida.getvalue()


# ============================================================
# Só para o ecrã: imagens das páginas e posição das palavras
# ============================================================

def _localizar_palavras(pdf, tokens):
    """Onde está cada palavra, para a página a sobrepor ao PDF.

    Devolve (caixas, razoes): caixas[id] = [página, x, y, largura, altura]
    em frações do tamanho da página, e razoes[página] = altura / largura.
    Se a ordem das palavras no PDF não coincidir com a de texto.split(),
    os ids não serviriam: caixas fica None e o browser mostra só o texto.
    """
    caixas = []
    palavras = []
    razoes = []

    with fitz.open(stream=pdf, filetype="pdf") as doc:
        for numero, pagina in enumerate(doc):
            larg, alt = pagina.rect.width, pagina.rect.height
            razoes.append(round(alt / larg, 5))

            for x0, y0, x1, y1, palavra, *_ in pagina.get_text("words"):
                palavras.append(palavra)
                caixas.append([
                    numero,
                    round(x0 / larg, 5),
                    round(y0 / alt, 5),
                    round((x1 - x0) / larg, 5),
                    round((y1 - y0) / alt, 5),
                ])

    return (caixas if palavras == tokens else None), razoes


def _imagem(pdf, numero):
    """A página 'numero' do PDF como PNG."""
    with fitz.open(stream=pdf, filetype="pdf") as doc:
        if not 0 <= numero < len(doc):
            raise ErroApi(404, "Página inexistente.")

        return doc[numero].get_pixmap(dpi=DPI_IMAGEM).tobytes("png")


def imagem_original(doc_id, numero):
    return _imagem(obter(doc_id)["pdf"], numero)


def imagem_redigida(doc_id, ids, numero):
    """Imagem da página 'numero' do PDF já redigido.

    As páginas de uma mesma escolha são pedidas de seguida, por isso o
    último PDF redigido fica guardado e só se redige uma vez.
    """
    documento = obter(doc_id)
    chave = frozenset(i for i in ids if isinstance(i, int))

    with TRINCO:
        guardada = documento.get("previa")

        if guardada is None or guardada[0] != chave:
            guardada = (chave, redigir_pdf(doc_id, chave, exportar=False))
            documento["previa"] = guardada

    return _imagem(guardada[1], numero)
