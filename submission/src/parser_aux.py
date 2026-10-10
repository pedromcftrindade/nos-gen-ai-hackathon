"""Auxiliares: palavras numeradas, parsing e validação da resposta."""
import json
import re

from config import MAX_CHARS

# Pontuação que nunca faz parte do valor (+, -, @, /, %, € ficam).
PONT_SEP = ".,;:!?()[]{}\"'«»“”‘’…"

PONTUACAO = re.compile(r"^(\W*)(.*?)(\W*)$", re.DOTALL)


def separar_token(token):
    """'Correia,' -> ('', 'Correia', ',')."""
    m = PONTUACAO.match(token)
    return m.group(1), m.group(2), m.group(3)


def variantes_token(token):
    """
    Formas como o Gemini pode escrever uma palavra, com o que deve ficar
    à volta quando é censurada: [(palavra, prefixo, sufixo), ...].
    Ex.: '+351,' -> ('351','+',','), ('+351','',','), ('351,','+',''),
         ('+351,','','').
    """
    pre, core, suf = separar_token(token)
    return [
        (core, pre, suf),
        (pre + core, "", suf),
        (core + suf, pre, ""),
        (token, "", ""),
    ]


def dividir_em_blocos(palavras, max_chars=MAX_CHARS):
    """
    Numera as palavras (ids globais a partir de 0, como no prompt) e
    agrupa-as em blocos '[id]palavra [id]palavra ...'.
    """
    chunks = []
    atual = []
    tamanho = 0

    for i, palavra in enumerate(palavras):
        peca = f"[{i}]{palavra}"

        if atual and tamanho + len(peca) + 1 > max_chars:
            chunks.append(" ".join(atual))
            atual = []
            tamanho = 0

        atual.append(peca)
        tamanho += len(peca) + 1

    if atual:
        chunks.append(" ".join(atual))

    return chunks


def converter_resposta_em_lista(resposta):
    """
    Converte a resposta JSON do Gemini numa lista de tuplos
    (palavra, id). Entradas mal formadas são ignoradas com um aviso.
    """
    texto = resposta.strip()

    # Tolerar blocos Markdown, caso o modelo os devolva.
    texto = re.sub(
        r"\A```(?:json)?\s*", "", texto, flags=re.IGNORECASE
    )
    texto = re.sub(r"\s*```\Z", "", texto)

    try:
        dados = json.loads(texto)

    except json.JSONDecodeError:
        inicio = texto.find("[")

        if inicio == -1:
            raise RuntimeError(
                f"A resposta do Gemini não contém um array JSON válido: "
                f"{resposta[:500]}"
            )

        try:
            dados, _ = json.JSONDecoder().raw_decode(texto[inicio:])
        except json.JSONDecodeError as erro:
            raise RuntimeError(
                f"Não foi possível interpretar a resposta JSON: "
                f"{resposta[:500]}"
            ) from erro

    if not isinstance(dados, list):
        raise RuntimeError("A resposta do Gemini não é uma lista JSON.")

    pares = []
    ignorados = 0

    for item in dados:
        if (
            isinstance(item, (list, tuple))
            and len(item) == 2
            and isinstance(item[0], str)
        ):
            # Se o Gemini incluir pontuação colada ("ansiedade)", "2x/dia,"),
            # retira-a para não ser apagada do texto.
            palavra = item[0].strip().strip(PONT_SEP).strip()

            try:
                if palavra:
                    pares.append((palavra, int(item[1])))
                    continue
            except (TypeError, ValueError):
                pass

        ignorados += 1

    if ignorados:
        print(
            f"Aviso: {ignorados} entrada(s) mal formada(s) ignorada(s).",
            flush=True,
        )

    return pares


def validar_pares(pares, tokens, janela=3):
    """
    Só aceita (palavra, id) se a palavra na posição 'id' for mesmo essa
    palavra (ignorando pontuação colada). Se o id vier deslocado até
    'janela' posições, corrige-o para a posição certa mais próxima.
    Devolve (válidos, corrigidos, descartados).
    """

    def casa(palavra, j):
        return 0 <= j < len(tokens) and any(
            chave and palavra == chave
            for chave, _, _ in variantes_token(tokens[j])
        )

    validos = []
    corrigidos = []
    descartados = []

    for palavra, i in pares:
        if casa(palavra, i):
            validos.append((palavra, i))
            continue

        for d in range(1, janela + 1):
            achado = next(
                (j for j in (i - d, i + d) if casa(palavra, j)), None
            )

            if achado is not None:
                validos.append((palavra, achado))
                corrigidos.append((palavra, i, achado))
                break
        else:
            descartados.append((palavra, i))

    return validos, corrigidos, descartados


def lista_para_dict(pares):
    """[(palavra, id), ...] -> {palavra: {ids}} (usado por FinalText)."""
    d = {}

    for palavra, i in pares:
        d.setdefault(palavra, set()).add(i)

    return d
