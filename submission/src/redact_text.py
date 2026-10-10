"""Redação do texto extraído (submission.txt) e frases para o PDF."""
import re
import textwrap

from config import LIMIAR_LINHA_CHEIA
from parser_aux import variantes_token


def censurar_token(i, token, WordsSet):
    """Devolve (token_novo, foi_censurado). Mantém a pontuação à volta."""
    for chave, pre, suf in variantes_token(token):
        if chave and chave in WordsSet and i in WordsSet[chave]:
            return f"{pre}*{suf}", True

    return token, False


def substituicoes_por_id(Document, WordsSet):
    """
    {id: token_novo} para cada palavra censurada (ex.: 5 -> '*',
    12 -> '(*)', 7 -> '*,'). Usa os MESMOS ids e a mesma regra que o
    FinalText, por isso o PDF fica igual ao submission.txt.
    """
    trocas = {}

    for i, token in enumerate(Document.split()):
        novo, censurado = censurar_token(i, token, WordsSet)

        if censurado:
            trocas[i] = novo

    return trocas


def FinalText(Document, WordsSet):
    """
    Replaces specific word occurrences in a document with asterisks (*),
    based on a dictionary of words and positions (0-based indices, the same
    ids used in the prompt). Line breaks and paragraphs are preserved: lines
    that become shorter are re-wrapped to the original width.

    Args:
        Document (str): The full text of the document to be processed.
        WordsSet (dict): {word: {0, 3, 11}} positions where the replacement
                         should occur.

    Returns:
        str: The modified text.
    """
    linhas = Document.splitlines()

    novas = []      # tokens novos de cada linha
    alterada = []   # a linha tem pelo menos uma palavra censurada
    primeira = []   # a primeira palavra da linha foi censurada
    ultima = []     # a última palavra da linha foi censurada
    i = 0

    for linha in linhas:
        tokens = []
        flags = []

        for token in linha.split():
            novo, c = censurar_token(i, token, WordsSet)
            tokens.append(novo)
            flags.append(c)
            i += 1

        novas.append(tokens)
        alterada.append(any(flags))
        primeira.append(bool(flags) and flags[0])
        ultima.append(bool(flags) and flags[-1])

    saida = []
    bloco = []

    def fechar_bloco():
        if bloco:
            saida.extend(
                _redigir_bloco(linhas, novas, alterada,
                               primeira, ultima, bloco)
            )
            bloco.clear()

    for k, linha in enumerate(linhas):
        if linha.strip():
            bloco.append(k)
        else:
            fechar_bloco()
            saida.append(linha)

    fechar_bloco()

    return "\n".join(saida) + "\n"


def _redigir_bloco(linhas, novas, alterada, primeira, ultima, bloco):
    """Divide o bloco em parágrafos e volta a quebrar os alterados."""
    larg_bloco = max(len(linhas[k].rstrip()) for k in bloco)
    limiar = larg_bloco * LIMIAR_LINHA_CHEIA

    paragrafos = []
    atual = []

    for pos, k in enumerate(bloco):
        atual.append(k)

        if pos + 1 == len(bloco):
            break

        proxima = bloco[pos + 1]
        seguinte = linhas[proxima].lstrip()

        # Nome partido entre duas linhas ("Maria" / "Clara"): continua.
        partido = ultima[k] and primeira[proxima]

        # A frase só continua na linha seguinte se esta linha estiver
        # (quase) cheia E a seguinte não começar com maiúscula.
        # Linhas de campos ("Seguro de saúde: ...", "Rendimento: ...")
        # começam com maiúscula, por isso nunca são juntadas.
        # Se a primeira palavra da linha seguinte foi censurada, a
        # maiúscula é de um valor sensível (ex.: "HIV", um nome) e não
        # de um campo novo: a frase continua.
        cheia = len(linhas[k].rstrip()) >= limiar
        maiuscula = seguinte[:1].isupper() and not primeira[proxima]
        continua = cheia and not maiuscula

        if not (partido or continua):
            paragrafos.append(atual)
            atual = []

    if atual:
        paragrafos.append(atual)

    resultado = []

    for par in paragrafos:
        if not any(alterada[k] for k in par):
            resultado.extend(linhas[k] for k in par)
            continue

        idx = next(n for n, k in enumerate(par) if alterada[k])
        cabeca = [linhas[k] for k in par[:idx]]

        tokens = [t for k in par[idx:] for t in novas[k]]
        larg_par = max(len(linhas[k].rstrip()) for k in par)

        indent_1 = re.match(r"\s*", linhas[par[idx]]).group()
        indent_n = re.match(
            r"\s*",
            linhas[par[idx + 1]] if idx + 1 < len(par) else linhas[par[idx]],
        ).group()

        resultado.extend(cabeca)
        resultado.extend(
            textwrap.wrap(
                " ".join(tokens),
                width=larg_par,
                initial_indent=indent_1,
                subsequent_indent=indent_n,
                break_long_words=False,
                break_on_hyphens=False,
            )
        )

    return resultado
