"""Substituição das informações sensíveis no PDF."""
import re
from pathlib import Path

import fitz


def criar_padrao(informacoes_sensiveis):
    """Constrói uma expressão regular para encontrar os elementos."""
    informacoes = []
    vistas = set()

    for informacao in informacoes_sensiveis:
        informacao = informacao.strip()

        if not informacao:
            continue

        chave = re.sub(r"\s+", " ", informacao).casefold()

        if chave not in vistas:
            vistas.add(chave)
            informacoes.append(informacao)

    if not informacoes:
        return None

    # Procurar primeiro as expressões mais longas.
    informacoes.sort(key=len, reverse=True)

    alternativas = []

    for informacao in informacoes:
        # Espaços/quebras de linha entre palavras casam com qualquer \s+
        palavras = informacao.split()
        alternativa = r"\s+".join(re.escape(p) for p in palavras)

        # Evitar, por exemplo, encontrar "Ana" dentro de "Banana".
        if informacao[0].isalnum():
            alternativa = r"(?<!\w)" + alternativa

        if informacao[-1].isalnum():
            alternativa += r"(?!\w)"

        alternativas.append(alternativa)

    return re.compile(
        "|".join(alternativas),
        re.IGNORECASE,
    )


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


def _asteriscos_texto(texto):
    """'Maria Clara' -> '* *' (um asterisco por palavra)."""
    return " ".join("*" for _ in texto.split())


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


def _fragmentos_por_linha(linhas, padrao):
    """
    Procura o padrão no texto da PÁGINA INTEIRA (linhas unidas por '\\n',
    tal como no texto extraído) e reparte cada ocorrência pelas linhas
    que atravessa. Assim, valores partidos em várias linhas
    (ex.: "Manuel Almeida Machado" / "Morgado André") também são apanhados.

    Devolve, para cada linha, uma lista de (inicio, fim) em índices de chars.
    """
    textos = ["".join(c["c"] for c, _ in chars) for _, chars in linhas]

    offsets = []
    pos = 0
    for t in textos:
        offsets.append(pos)
        pos += len(t) + 1  # +1 pelo '\n'

    texto_pagina = "\n".join(textos)
    fragmentos = [[] for _ in linhas]

    for m in padrao.finditer(texto_pagina):
        for i, (off, t) in enumerate(zip(offsets, textos)):
            ini = max(m.start(), off)
            fim = min(m.end(), off + len(t))

            if ini >= fim:
                continue

            # Ignorar espaços nas pontas do fragmento.
            while ini < fim and texto_pagina[ini].isspace():
                ini += 1
            while fim > ini and texto_pagina[fim - 1].isspace():
                fim -= 1

            if ini < fim:
                fragmentos[i].append((ini - off, fim - off))

    return fragmentos


def _preparar_linha(linha, chars, fragmentos):
    """
    Calcula o retângulo a apagar e os desenhos a fazer numa linha.
    desenho = (texto, x, y, fonte, tamanho, cor)
    """
    a0 = fragmentos[0][0]
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

    for ini, fim in fragmentos:
        # Texto entre o fragmento anterior e este.
        copiar(pos, ini)

        c_ini, span_ini = chars[ini]
        c_fim, _ = chars[fim - 1]
        fonte = _fonte(span_ini)
        tam_m = span_ini["size"]
        x_ini = c_ini["bbox"][0] + delta

        texto_frag = "".join(c["c"] for c, _ in chars[ini:fim])
        ast = _asteriscos_texto(texto_frag)
        largura_nova = fitz.get_text_length(
            ast, fontname=fonte, fontsize=tam_m
        )

        desenhos.append((
            ast,
            x_ini,
            c_ini["origin"][1],
            fonte,
            tam_m,
            _cor(span_ini["color"]),
        ))

        delta = x_ini + largura_nova - c_fim["bbox"][2]
        pos = fim

    # Resto da linha depois do último fragmento.
    copiar(pos, len(chars))

    return retangulo, desenhos


def substituir_informacoes_sensiveis(
    pdf_entrada,
    pdf_saida,
    informacoes_sensiveis,
):
    """
    Troca cada palavra sensível por '*' (um asterisco por palavra, com
    um só espaço entre eles). O resto da linha é redesenhado caractere a
    caractere, nas posições originais deslocadas para a esquerda, por isso
    não há espaços a mais nem sobreposições.
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

    padrao = criar_padrao(informacoes_sensiveis)

    total = 0

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

            # Cada elemento: (retângulo a apagar, lista de desenhos)
            trabalho = []

            if padrao is not None:
                linhas = _linhas_da_pagina(pagina)
                fragmentos = _fragmentos_por_linha(linhas, padrao)

                for (linha, chars), frags in zip(linhas, fragmentos):
                    if frags:
                        trabalho.append(
                            _preparar_linha(linha, chars, frags)
                        )

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

    print(
        f"Total de linhas alteradas: {total}",
        flush=True,
    )
    print(
        f"PDF resultante guardado em: {caminho_saida}",
        flush=True,
    )

    return total
