"""Substituição das informações sensíveis no PDF (por id de palavra).

Suporta texto horizontal e texto em qualquer ângulo (diagonal, vertical,
de cabeça para baixo), usando a direção de cada linha (linha["dir"]).
Em linhas inclinadas só se apagam os caracteres censurados (sem tocar nas
letras vizinhas).
"""
import math
from difflib import SequenceMatcher
from pathlib import Path

import fitz

# Linhas com |sin| abaixo disto (e a ler da esquerda para a direita) são
# tratadas como horizontais.
TOLERANCIA_HORIZONTAL = 0.02


def _fonte(span):
    """
    Escolhe a fonte base-14 equivalente: família (Helvetica, Courier,
    Times) pelo nome da fonte, e negrito/itálico pelas flags ou pelo nome.
    """
    nome = str(span.get("font", "")).lower()
    flags = span.get("flags", 0)

    bold = bool(flags & 16) or "bold" in nome or "black" in nome
    italic = bool(flags & 2) or "italic" in nome or "oblique" in nome

    if any(k in nome for k in ("courier", "mono", "consolas", "typewriter")):
        familia = ("cour", "cobo", "coit", "cobi")
    elif any(k in nome for k in ("times", "serif", "georgia", "garamond")):
        familia = ("tiro", "tibo", "tiit", "tibi")
    else:
        familia = ("helv", "hebo", "heit", "hebi")

    if bold and italic:
        return familia[3]
    if bold:
        return familia[1]
    if italic:
        return familia[2]
    return familia[0]


def _cor(cor_int):
    return (
        ((cor_int >> 16) & 255) / 255,
        ((cor_int >> 8) & 255) / 255,
        (cor_int & 255) / 255,
    )


def _linhas_da_pagina(pagina):
    """Devolve [(linha, [(char, span), ...]), ...] por ordem de leitura."""
    linhas = []

    for bloco in pagina.get_text("rawdict")["blocks"]:
        for linha in bloco.get("lines", []):
            chars = [
                (c, span)
                for span in linha["spans"]
                for c in span.get("chars", [])
            ]

            if chars:
                linhas.append((linha, chars))

    return linhas


def _palavras_da_linha(chars):
    """[(ini, fim), ...]: índices em chars de cada palavra da linha."""
    palavras = []
    ini = None

    for k, (c, _) in enumerate(chars):
        if c["c"].isspace():
            if ini is not None:
                palavras.append((ini, k))
                ini = None
        elif ini is None:
            ini = k

    if ini is not None:
        palavras.append((ini, len(chars)))

    return palavras


def _alinhar(palavras_texto, palavras_pdf):
    """
    Liga cada palavra de pagina.get_text().split() (as que têm os ids)
    à palavra correspondente no rawdict. Normalmente é 1 para 1; se
    as duas listas diferirem, alinha-as por sequência.
    Devolve mapa[t] = índice no rawdict (ou None).
    """
    if palavras_texto == palavras_pdf:
        return list(range(len(palavras_texto)))

    mapa = [None] * len(palavras_texto)
    sm = SequenceMatcher(None, palavras_texto, palavras_pdf, autojunk=False)

    for a, b, n in sm.get_matching_blocks():
        for d in range(n):
            mapa[a + d] = b + d

    return mapa


def _trocas_da_pagina(linhas, palavras_texto, offset, substituicoes):
    """
    Para cada linha, [(ini, fim, token_novo), ...] (índices em chars),
    com base nos ids globais das palavras censuradas.
    Devolve (trocas_por_linha, nao_mapeadas).
    """
    # Palavras do rawdict, pela mesma ordem do texto.
    refs = []        # (índice da linha, ini, fim)
    palavras_pdf = []

    for li, (_, chars) in enumerate(linhas):
        for ini, fim in _palavras_da_linha(chars):
            refs.append((li, ini, fim))
            palavras_pdf.append("".join(c["c"] for c, _ in chars[ini:fim]))

    mapa = _alinhar(palavras_texto, palavras_pdf)

    trocas = [[] for _ in linhas]
    nao_mapeadas = 0

    for t in range(len(palavras_texto)):
        novo = substituicoes.get(offset + t)

        if novo is None:
            continue

        if mapa[t] is None:
            nao_mapeadas += 1
            continue

        li, ini, fim = refs[mapa[t]]
        trocas[li].append((ini, fim, novo))

    for lista in trocas:
        lista.sort()

    return trocas, nao_mapeadas


# ============================================================
# Geometria
# ============================================================

def _direcao(linha):
    """Vetor unitário (dx, dy) em que a linha é lida (y para baixo)."""
    dx, dy = linha.get("dir", (1.0, 0.0))
    norma = math.hypot(dx, dy)

    if norma == 0:
        return 1.0, 0.0

    return dx / norma, dy / norma


def _e_horizontal(dx, dy):
    return dx > 0 and abs(dy) < TOLERANCIA_HORIZONTAL


def _largura_char(chars, k):
    """Avanço do char k ao longo da linha."""
    c, span = chars[k]

    if k + 1 < len(chars):
        o = c["origin"]
        n = chars[k + 1][0]["origin"]
        return math.hypot(n[0] - o[0], n[1] - o[1])

    return fitz.get_text_length(
        c["c"], fontname=_fonte(span), fontsize=span["size"]
    )


# ============================================================
# Linhas horizontais: fecha o espaço (um '*' por palavra)
# ============================================================

def _preparar_linha_horizontal(linha, chars, trocas):
    """
    Calcula o retângulo a apagar e os desenhos a fazer numa linha
    horizontal. O resto da linha é redesenhado caractere a caractere,
    deslocado para a esquerda, sem espaços a mais nem sobreposições.
    desenho = (texto, x, y, fonte, tamanho, cor, morph)
    """
    a0 = trocas[0][0]
    primeiro_c, primeiro_span = chars[a0]
    x0 = primeiro_c["bbox"][0]
    oy = primeiro_c["origin"][1]
    tam = primeiro_span["size"]

    retangulo = fitz.Rect(
        x0 - 0.5,
        oy - tam * 0.8,
        linha["bbox"][2] + 1,
        oy + tam * 0.25,
    )

    desenhos = []
    delta = 0.0
    pos = a0

    def copiar(de, ate):
        for k in range(de, ate):
            c, span = chars[k]
            if c["c"].isspace():
                continue
            desenhos.append((
                c["c"],
                c["origin"][0] + delta,
                c["origin"][1],
                _fonte(span),
                span["size"],
                _cor(span["color"]),
                None,
            ))

    for ini, fim, novo in trocas:
        # Texto entre a troca anterior e esta.
        copiar(pos, ini)

        c_ini, span_ini = chars[ini]
        c_fim, _ = chars[fim - 1]
        fonte = _fonte(span_ini)
        tam_m = span_ini["size"]
        x_ini = c_ini["bbox"][0] + delta

        largura_nova = fitz.get_text_length(
            novo, fontname=fonte, fontsize=tam_m
        )

        desenhos.append((
            novo,
            x_ini,
            c_ini["origin"][1],
            fonte,
            tam_m,
            _cor(span_ini["color"]),
            None,
        ))

        delta = x_ini + largura_nova - c_fim["bbox"][2]
        pos = fim

    # Resto da linha depois da última troca.
    copiar(pos, len(chars))

    return [retangulo], desenhos


# ============================================================
# Linhas em qualquer outro ângulo: troca no próprio sítio
# ============================================================

def _preparar_linha_rotacionada(linha, chars, trocas):
    """
    Para texto na diagonal (ou vertical / invertido) a remoção do PDF
    usa o retângulo ENVOLVENTE de cada área, e numa linha inclinada esse
    retângulo apanha letras das linhas vizinhas. Por isso apaga-se
    caractere a caractere, com dois quadradinhos no centro de cada
    caractere censurado (um a meio da altura-x, outro junto da linha de
    base, para apanhar '.' e ','), que só tocam no próprio caractere.
    O '*' é escrito no início da palavra, na mesma posição e inclinação.
    Não se fecha o espaço.
    """
    dx, dy = _direcao(linha)
    px, py = -dy, dx   # perpendicular, "para baixo" na linha

    # Roda o texto horizontal para a direção da linha.
    matriz = fitz.Matrix(dx, dy, -dy, dx, 0, 0)

    retangulos = []
    desenhos = []

    for ini, fim, novo in trocas:
        c_ini, span_ini = chars[ini]
        ox, oy = c_ini["origin"]

        for k in range(ini, fim):
            c, span = chars[k]

            if c["c"].isspace():
                continue

            cx, cy = c["origin"]
            tam = span["size"]
            meio = _largura_char(chars, k) / 2
            meia_aresta = max(0.8, tam * 0.08)

            for h in (-tam * 0.3, -tam * 0.05):
                x = cx + meio * dx + h * px
                y = cy + meio * dy + h * py

                retangulos.append(fitz.Rect(
                    x - meia_aresta, y - meia_aresta,
                    x + meia_aresta, y + meia_aresta,
                ))

        desenhos.append((
            novo,
            ox,
            oy,
            _fonte(span_ini),
            span_ini["size"],
            _cor(span_ini["color"]),
            (fitz.Point(ox, oy), matriz),
        ))

    return retangulos, desenhos


def _preparar_linha(linha, chars, trocas):
    """Escolhe a estratégia pela direção da linha."""
    dx, dy = _direcao(linha)

    if _e_horizontal(dx, dy):
        return _preparar_linha_horizontal(linha, chars, trocas)

    return _preparar_linha_rotacionada(linha, chars, trocas)


# ============================================================
# Função principal
# ============================================================

def substituir_informacoes_sensiveis(
    pdf_entrada,
    pdf_saida,
    substituicoes,
):
    """
    Troca no PDF exatamente as palavras que o submission.txt troca.

    substituicoes: {id_global_da_palavra: token_novo}, ex.: {5: '*', 12: '(*)'}
    (ver redact_text.substituicoes_por_id). Os ids contam as palavras de
    pagina.get_text().split() ao longo de todas as páginas, como no prompt.
    """
    caminho_entrada = Path(pdf_entrada).expanduser().resolve()
    caminho_saida = Path(pdf_saida).expanduser().resolve()

    if not caminho_entrada.is_file():
        raise FileNotFoundError(
            f"O PDF de entrada não existe: {caminho_entrada}"
        )

    if caminho_entrada == caminho_saida:
        raise ValueError(
            "O PDF de saída tem de ter um caminho diferente "
            "do PDF de entrada."
        )

    caminho_saida.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    palavras_trocadas = 0
    linhas_rotacionadas = 0
    por_mapear = 0
    offset = 0

    print(
        "A abrir o PDF para substituir as informações sensíveis...",
        flush=True,
    )

    with fitz.open(caminho_entrada) as doc:
        numero_paginas = len(doc)

        for numero, pagina in enumerate(doc, start=1):
            print(
                f"A analisar página {numero}/{numero_paginas}...",
                flush=True,
            )

            palavras_texto = pagina.get_text().split()

            # Cada elemento: (lista de áreas a apagar, lista de desenhos)
            trabalho = []

            if substituicoes:
                linhas = _linhas_da_pagina(pagina)
                trocas, nao_mapeadas = _trocas_da_pagina(
                    linhas, palavras_texto, offset, substituicoes
                )
                por_mapear += nao_mapeadas

                for (linha, chars), tr in zip(linhas, trocas):
                    if not tr:
                        continue

                    palavras_trocadas += len(tr)

                    if not _e_horizontal(*_direcao(linha)):
                        linhas_rotacionadas += 1

                    trabalho.append(_preparar_linha(linha, chars, tr))

            offset += len(palavras_texto)

            for areas, _ in trabalho:
                for area in areas:
                    pagina.add_redact_annot(
                        area,
                        fill=None,
                        cross_out=False,
                    )

            if trabalho:
                pagina.apply_redactions(
                    images=0,
                    graphics=0,
                )

                for _, desenhos in trabalho:
                    for texto_d, x, y, fonte, tam_d, cor, morph in desenhos:
                        pagina.insert_text(
                            fitz.Point(x, y),
                            texto_d,
                            fontname=fonte,
                            fontsize=tam_d,
                            color=cor,
                            morph=morph,
                            overlay=True,
                        )

            total += len(trabalho)

        print("A guardar o PDF de saída...", flush=True)

        doc.save(
            caminho_saida,
            garbage=4,
            deflate=True,
        )

    if por_mapear:
        print(
            f"Aviso: {por_mapear} palavra(s) censurada(s) no texto não "
            f"foram encontradas no PDF e ficaram por censurar.",
            flush=True,
        )

    print(
        f"Palavras censuradas no PDF: {palavras_trocadas} "
        f"(em {total} linha(s), {linhas_rotacionadas} em ângulo).",
        flush=True,
    )
    print(
        f"PDF resultante guardado em: {caminho_saida}",
        flush=True,
    )

    return total
