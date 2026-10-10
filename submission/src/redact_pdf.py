"""Substituição das informações sensíveis no PDF (por id de palavra)."""
from difflib import SequenceMatcher
from pathlib import Path

import fitz


def _fonte(span):
    """Escolhe a fonte base-14 equivalente (negrito/itálico)."""
    flags = span.get("flags", 0)
    bold = bool(flags & 16)
    italic = bool(flags & 2)
    if bold and italic:
        return "hebi"
    if bold:
        return "hebo"
    if italic:
        return "heit"
    return "helv"


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


def _preparar_linha(linha, chars, trocas):
    """
    Calcula o retângulo a apagar e os desenhos a fazer numa linha.
    desenho = (texto, x, y, fonte, tamanho, cor)
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
        ))

        delta = x_ini + largura_nova - c_fim["bbox"][2]
        pos = fim

    # Resto da linha depois da última troca.
    copiar(pos, len(chars))

    return retangulo, desenhos


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

    O resto da linha é redesenhado caractere a caractere, nas posições
    originais deslocadas para a esquerda, por isso não há espaços a mais
    nem sobreposições.
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

            # Cada elemento: (retângulo a apagar, lista de desenhos)
            trabalho = []

            if substituicoes:
                linhas = _linhas_da_pagina(pagina)
                trocas, nao_mapeadas = _trocas_da_pagina(
                    linhas, palavras_texto, offset, substituicoes
                )
                por_mapear += nao_mapeadas

                for (linha, chars), tr in zip(linhas, trocas):
                    if tr:
                        palavras_trocadas += len(tr)
                        trabalho.append(_preparar_linha(linha, chars, tr))

            offset += len(palavras_texto)

            for retangulo, _ in trabalho:
                pagina.add_redact_annot(
                    retangulo,
                    fill=None,
                    cross_out=False,
                )

            if trabalho:
                pagina.apply_redactions(
                    images=0,
                    graphics=0,
                )

                for _, desenhos in trabalho:
                    for texto_d, x, y, fonte, tam_d, cor in desenhos:
                        pagina.insert_text(
                            fitz.Point(x, y),
                            texto_d,
                            fontname=fonte,
                            fontsize=tam_d,
                            color=cor,
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
        f"(em {total} linha(s)).",
        flush=True,
    )
    print(
        f"PDF resultante guardado em: {caminho_saida}",
        flush=True,
    )

    return total
