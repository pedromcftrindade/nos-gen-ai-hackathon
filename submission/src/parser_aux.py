"""Auxiliares: palavras numeradas, parsing e validação da resposta."""
import json
import re

from config import MAX_CHARS
from erros import RespostaInvalida

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

def palavras_do_valor(valor):
    """'Rua das Flores, 12' -> ['Rua', 'das', 'Flores', '12']
    (cada palavra sem a pontuação colada às pontas)."""
    return [
        p
        for p in (w.strip(PONT_SEP) for w in valor.split())
        if p
    ]

def _etiqueta(valor):
    """Etiqueta tal como o Gemini a escreveu ('' se faltar)."""
    return valor.strip() if isinstance(valor, str) else ""

def converter_resposta_em_lista(resposta):
    """
    Converte a resposta JSON do Gemini numa lista de tuplos
    (palavra, id, categoria, subcategoria). Aceita entradas de 2
    elementos (sem etiquetas) ou de 4. Entradas mal formadas são
    ignoradas com um aviso.
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
            raise RespostaInvalida(
                f"A resposta do Gemini não contém um array JSON válido: "
                f"{resposta[:500]}"
            )

        try:
            dados, _ = json.JSONDecoder().raw_decode(texto[inicio:])
        except json.JSONDecodeError as erro:
            raise RespostaInvalida(
                f"Não foi possível interpretar a resposta JSON: "
                f"{resposta[:500]}"
            ) from erro

    if not isinstance(dados, list):
        raise RespostaInvalida("A resposta do Gemini não é uma lista JSON.")

    pares = []
    ignorados = 0

    for item in dados:
        if (
            isinstance(item, (list, tuple))
            and len(item) in (2, 4)
            and isinstance(item[0], str)
        ):
            # Valor com várias palavras: normaliza espaços e retira a
            # pontuação colada a cada palavra ("Flores," -> "Flores").
            palavra = " ".join(palavras_do_valor(item[0]))

            cat = _etiqueta(item[2]) if len(item) == 4 else ""
            sub = _etiqueta(item[3]) if len(item) == 4 else ""

            try:
                if palavra:
                    pares.append((palavra, int(item[1]), cat, sub))
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
    Só aceita (valor, id) se as palavras do valor estiverem mesmo nas
    posições id, id+1, id+2... (ignorando pontuação colada). Se o id vier
    deslocado até 'janela' posições, corrige-o para a posição certa mais
    próxima (o valor inteiro desloca-se). As etiquetas acompanham cada par.
    Devolve (válidos, corrigidos, descartados), onde os válidos são
    tuplos (valor, id, categoria, subcategoria).
    """

    def casa(palavras, j):
        return (
            j >= 0
            and j + len(palavras) <= len(tokens)
            and all(
                any(
                    chave and palavra == chave
                    for chave, _, _ in variantes_token(tokens[j + k])
                )
                for k, palavra in enumerate(palavras)
            )
        )

    validos = []
    corrigidos = []
    descartados = []

    for valor, i, cat, sub in pares:
        palavras = palavras_do_valor(valor)

        if casa(palavras, i):
            validos.append((valor, i, cat, sub))
            continue

        for d in range(1, janela + 1):
            achado = next(
                (j for j in (i - d, i + d) if casa(palavras, j)), None
            )

            if achado is not None:
                validos.append((valor, achado, cat, sub))
                corrigidos.append((valor, i, achado))
                break
        else:
            descartados.append((valor, i))

    return validos, corrigidos, descartados

def lista_para_dict(pares):
    """
    [(valor, id, ...), ...] -> {palavra: {ids}} (usado por FinalText).
    Um valor com várias palavras é expandido: a palavra k do valor fica
    na posição id + k, e cada uma vira um '*'.
    """
    d = {}

    for valor, i, *_ in pares:
        for k, palavra in enumerate(palavras_do_valor(valor)):
            d.setdefault(palavra, set()).add(i + k)

    return d