import json
import os
import re
import sys
import argparse
import textwrap
import time
from pathlib import Path

import fitz
import requests
from dotenv import load_dotenv


# ============================================================
# Configuração
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

SUBMISSION_DIR = BASE_DIR.parent
SUBMISSION_FILE = SUBMISSION_DIR / "submission.txt"      # resultado FINAL
EXTRACTED_FILE = SUBMISSION_DIR / "extracted_text.txt"   # texto original
RESPONSES_FILE = SUBMISSION_DIR / "gemini_responses.txt"
SENSITIVE_INFO_FILE = SUBMISSION_DIR / "sensitive_info.json"

LIMIAR_LINHA_CHEIA = 0.75  # linha >= 75% da largura => a frase continua

MAX_CHARS = 8000

MODEL = "gemini-3.5-flash-lite"

API_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{MODEL}:generateContent"
)

MAX_RETRIES = 4
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120

HTTP_RETRY_CODES = {429, 500, 502, 503, 504}


PROMPT_TEMPLATE = """
Read this document containing diverse information. Every word is preceded by
a numeric id in square brackets, like [12]word. The ids are not part of the
document; they only identify each word.

This information can be sensitive, personal, private, physical, mental,
political, religious, financial, health related, ethnic, among others. Your
task is to process all this information and abstract all the important or
sensitive topics that the user can choose to censor.

Create a JSON object containing all the sensitive data, organized as follows:
1. The primary keys are the most generic word for the topic (for example:
   Biometric Data, Personal Information, Health Data, Racial Ethnicity).
2. Inside each topic there is another object with more specific sub-topics
   (for example, in Health Data: Health Condition, Mental State, Medication,
   Family History).
3. Inside each sub-topic there is another object where each key is one
   sensitive word and its value is the list of ids where that word occurs.

Rules:
- Capture only the essential words, so the text stays comprehensible when
  those words are replaced with '*'. Never include labels or connecting words.
- Use one key per word. A value with several words gives several keys.
- Write each word exactly as it is in the document, character by character,
  without the id and without punctuation attached to its start or end. Do not
  translate, reformat or correct it.
- The ids must be integers copied exactly from the document.
- Each topic, sub-topic and word appears only once as a key. If a word occurs
  several times, put all its ids in the same list.
- Keep the original language of the document for the words.
- If there is no sensitive information, return {{}}.

Example document:
[0]A [1]paciente [2]Ana [3]Correia, [4]de [5]25 [6]anos [7]e [8]67kg, [9]veio
[10]à [11]consulta [12]por [13]depressão. [14]A [15]mãe [16]de [17]Ana
[18]também [19]tem [20]depressão.

Example output:
{{"Personal Information": {{"Name": {{"Ana": [2, 17], "Correia": [3]}}}},
 "Biometric Data": {{"Weight": {{"67kg": [8]}}}},
 "Health Data": {{"Mental State": {{"depressão": [13]}},
                 "Family History": {{"depressão": [20]}}}}}}
Return only the JSON object, with no explanation and no code fences.


Document part {i} of {n}:

--- DOCUMENT PART ---
{chunk}
"""



# ============================================================
# Extração do texto do PDF
# ============================================================

def extrair_texto_pdf(pdf_entrada):
    """Extrai o texto do PDF e guarda-o em extracted_text.txt."""
    caminho_pdf = Path(pdf_entrada).expanduser().resolve()

    if not caminho_pdf.is_file():
        raise FileNotFoundError(
            f"O ficheiro PDF não existe: {caminho_pdf}"
        )

    print("A abrir o PDF de entrada...", flush=True)

    paginas_texto = []

    with fitz.open(caminho_pdf) as doc:
        numero_paginas = len(doc)

        for numero, pagina in enumerate(doc, start=1):
            print(
                f"A extrair texto da página {numero}/{numero_paginas}...",
                flush=True,
            )

            paginas_texto.append(pagina.get_text())

    texto_completo = "\n".join(paginas_texto)

    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)

    EXTRACTED_FILE.write_text(texto_completo, encoding="utf-8")

    print(
        f"Texto extraído: {len(texto_completo)} caracteres.",
        flush=True,
    )
    print(f"Texto guardado em: {EXTRACTED_FILE}", flush=True)

    return texto_completo


# ============================================================
# Palavras numeradas e divisão em blocos
# ============================================================

PONTUACAO = re.compile(r"^(\W*)(.*?)(\W*)$", re.DOTALL)


def separar_token(token):
    """'Correia,' -> ('', 'Correia', ',')."""
    m = PONTUACAO.match(token)
    return m.group(1), m.group(2), m.group(3)


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


# ============================================================
# Comunicação com o Gemini
# ============================================================

def extrair_texto_resposta(data):
    """Extrai o texto da resposta da API generateContent."""
    candidatos = data.get("candidates") or []

    if not candidatos:
        feedback = data.get("promptFeedback") or {}
        raise RuntimeError(
            f"O Gemini não devolveu candidatos: {feedback or data}"
        )

    partes = candidatos[0].get("content", {}).get("parts", [])

    texto = "".join(
        parte.get("text", "")
        for parte in partes
    ).strip()

    if not texto:
        raise RuntimeError(
            "O Gemini devolveu uma resposta sem texto."
        )

    return texto.replace("\n", "")


def pedir_gemini(session, api_key, prompt):
    """Envia um pedido ao Gemini e repete erros temporários."""
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }

    corpo = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json"
        },
    }

    for tentativa in range(1, MAX_RETRIES + 1):
        try:
            resposta = session.post(
                API_URL,
                headers=headers,
                json=corpo,
                timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            )

        except (
            requests.Timeout,
            requests.ConnectionError,
        ) as erro:
            if tentativa == MAX_RETRIES:
                raise RuntimeError(
                    f"Falha de ligação após {MAX_RETRIES} tentativas: "
                    f"{erro}"
                ) from erro

            espera = 2 ** tentativa

            print(
                f"Erro de ligação: {erro}. "
                f"Nova tentativa em {espera}s "
                f"({tentativa}/{MAX_RETRIES})...",
                flush=True,
            )

            time.sleep(espera)
            continue

        if resposta.status_code in HTTP_RETRY_CODES:
            if tentativa == MAX_RETRIES:
                raise RuntimeError(
                    f"Falha após {MAX_RETRIES} tentativas. "
                    f"HTTP {resposta.status_code}: "
                    f"{resposta.text[:1000]}"
                )

            espera = 2 ** tentativa

            print(
                f"Erro HTTP {resposta.status_code}. "
                f"Nova tentativa em {espera}s "
                f"({tentativa}/{MAX_RETRIES})...",
                flush=True,
            )

            time.sleep(espera)
            continue

        if not resposta.ok:
            raise RuntimeError(
                f"Erro HTTP {resposta.status_code}: "
                f"{resposta.text[:2000]}"
            )

        try:
            data = resposta.json()
        except ValueError as erro:
            raise RuntimeError(
                "A API devolveu uma resposta que não é JSON válido."
            ) from erro

        return extrair_texto_resposta(data)

    raise RuntimeError("Não foi possível obter uma resposta do Gemini.")


# ============================================================
# Conversão da resposta do Gemini num dicionário Python
# ============================================================

def converter_resposta_em_dict(resposta):
    """
    Converte a resposta JSON do Gemini em
    {tópico: {subtópico: {palavra: set(ids)}}}.
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
        inicio = texto.find("{")

        if inicio == -1:
            raise RuntimeError(
                f"A resposta do Gemini não contém um objeto JSON válido: "
                f"{resposta[:500]}"
            )

        try:
            dados, _ = json.JSONDecoder().raw_decode(texto[inicio:])
        except json.JSONDecodeError as erro:
            raise RuntimeError(
                f"Não foi possível interpretar a resposta JSON: "
                f"{resposta[:500]}"
            ) from erro

    if not isinstance(dados, dict):
        raise RuntimeError("A resposta do Gemini não é um objeto JSON.")

    resultado = {}

    for topico, subtopicos in dados.items():
        if not isinstance(subtopicos, dict):
            print(
                f"Aviso: tópico '{topico}' ignorado (formato inesperado).",
                flush=True,
            )
            continue

        for subtopico, palavras in subtopicos.items():
            if not isinstance(palavras, dict):
                print(
                    f"Aviso: subtópico '{topico}/{subtopico}' ignorado "
                    "(formato inesperado).",
                    flush=True,
                )
                continue

            for palavra, ids in palavras.items():
                if isinstance(ids, (int, str)):
                    ids = [ids]

                if not isinstance(ids, list):
                    continue

                validos = set()

                for x in ids:
                    try:
                        validos.add(int(x))
                    except (TypeError, ValueError):
                        continue

                if validos and str(palavra).strip():
                    resultado.setdefault(topico, {}).setdefault(
                        subtopico, {}
                    ).setdefault(str(palavra).strip(), set()).update(validos)

    return resultado


def juntar_dicts(destino, parte):
    """Junta 'parte' em 'destino' (união dos ids)."""
    for topico, subtopicos in parte.items():
        for subtopico, palavras in subtopicos.items():
            for palavra, ids in palavras.items():
                destino.setdefault(topico, {}).setdefault(
                    subtopico, {}
                ).setdefault(palavra, set()).update(ids)


def dict_para_json(d):
    return {
        t: {
            s: {p: sorted(ids) for p, ids in ps.items()}
            for s, ps in ss.items()
        }
        for t, ss in d.items()
    }


def json_para_dict(dados):
    return {
        t: {
            s: {p: set(ids) for p, ids in ps.items()}
            for s, ps in ss.items()
        }
        for t, ss in dados.items()
    }


# ============================================================
# Identificação de informações sensíveis
# ============================================================

def processar_com_gemini(texto):
    """
    Envia o texto (palavras numeradas) ao Gemini e devolve
    {tópico: {subtópico: {palavra: set(ids)}}} já combinado.
    """
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não encontrada. "
            "Verifica o ficheiro .env."
        )

    chunks = dividir_em_blocos(texto.split())
    numero_chunks = len(chunks)

    if not chunks:
        print("Não existe texto para enviar ao Gemini.", flush=True)
        return {}

    print(f"Texto dividido em {numero_chunks} parte(s).", flush=True)

    respostas = []
    resultado = {}

    with requests.Session() as session:
        for i, chunk in enumerate(chunks, start=1):
            print(
                f"A analisar parte {i}/{numero_chunks} "
                f"({len(chunk)} caracteres)...",
                flush=True,
            )

            prompt = PROMPT_TEMPLATE.format(
                i=i, n=numero_chunks, chunk=chunk
            )

            inicio = time.monotonic()
            resposta = pedir_gemini(session, api_key, prompt)
            duracao = time.monotonic() - inicio

            respostas.append(resposta)

            parte = converter_resposta_em_dict(resposta)
            juntar_dicts(resultado, parte)

            n_palavras = sum(
                len(ps) for ss in parte.values() for ps in ss.values()
            )

            print(
                f"Parte {i}/{numero_chunks} concluída em {duracao:.1f}s. "
                f"{n_palavras} palavra(s) identificada(s).",
                flush=True,
            )

    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)

    with RESPONSES_FILE.open("w", encoding="utf-8") as ficheiro:
        for i, resposta in enumerate(respostas, start=1):
            ficheiro.write(
                f"===== Parte {i}/{numero_chunks} =====\n"
                f"{resposta}\n\n"
            )

    guardar_sensivel(resultado)

    print(f"Respostas guardadas em: {RESPONSES_FILE}", flush=True)

    return resultado


def guardar_sensivel(d):
    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)

    texto = json.dumps(dict_para_json(d), ensure_ascii=False, indent=2)

    # Listas de ids na mesma linha: "Ana": [2, 17]
    texto = re.sub(
        r"\[\s*(\d[\d,\s]*?)\s*\]",
        lambda m: "["
        + ", ".join(x.strip() for x in m.group(1).split(",") if x.strip())
        + "]",
        texto,
    )

    SENSITIVE_INFO_FILE.write_text(texto + "\n", encoding="utf-8")

    print(f"Lista guardada em: {SENSITIVE_INFO_FILE}", flush=True)


# ============================================================
# Filtragem por subtópicos
# ============================================================

def subtopicos_disponiveis(d):
    """Nomes de todos os subtópicos (atributos) do dicionário."""
    return sorted({sub for ss in d.values() for sub in ss})


def resolver_campos(d, pedidos):
    """Converte nomes pedidos (sem distinguir maiúsculas) em subtópicos."""
    if not pedidos:
        return None  # None = todos

    por_nome = {s.casefold(): s for s in subtopicos_disponiveis(d)}
    campos = set()

    for p in pedidos:
        nome = por_nome.get(p.strip().casefold())

        if nome is None:
            print(f"Aviso: subtópico desconhecido ignorado: {p}", flush=True)
        else:
            campos.add(nome)

    return campos


"""
Creates a flat dictionary from a nested dictionary, filtering by specific
attributes.

Args:
d (dict): Nested dictionary in the format
          {category: {attribute: {name: t, ...}, ...}, ...}.
fields (iterable | None): Names of the attributes to keep (None = all).

Returns:
dict: A flat dictionary {name: t}. If the same name appears under several
      attributes, the positions in `t` are merged.
"""
def createDict(d, fields):
    newDict = {}
    for categoria, subdict in d.items():
        for atributo, list_words in subdict.items():
            if fields is None or atributo in fields:
                for name, t in list_words.items():
                    newDict.setdefault(name, set()).update(t)
    return newDict


# ============================================================
# Redação do texto (submission.txt)
# ============================================================

def censurar_token(i, token, WordsSet):
    """Devolve (token_novo, foi_censurado). Mantém a pontuação à volta."""
    pre, core, suf = separar_token(token)

    if core and core in WordsSet and i in WordsSet[core]:
        return f"{pre}*{suf}", True

    if token in WordsSet and i in WordsSet[token]:
        return "*", True

    return token, False


def frases_sensiveis(Document, WordsSet):
    """
    Junta palavras censuradas consecutivas em frases ('Ana Correia'),
    para redigir também o PDF.
    """
    frases = []
    atual = []
    suf_anterior = ""

    for i, token in enumerate(Document.split()):
        _, censurado = censurar_token(i, token, WordsSet)
        pre, core, suf = separar_token(token)

        if not censurado:
            if atual:
                frases.append(" ".join(atual))
                atual = []
            suf_anterior = ""
            continue

        parte = core or token

        if atual and (pre or suf_anterior):
            frases.append(" ".join(atual))
            atual = []

        atual.append(parte)
        suf_anterior = suf

        if suf:
            frases.append(" ".join(atual))
            atual = []

    if atual:
        frases.append(" ".join(atual))

    return frases


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
def FinalText(Document, WordsSet):
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

        seguinte = linhas[bloco[pos + 1]].lstrip()

        # Nome partido entre duas linhas ("Maria" / "Clara"): continua.
        partido = ultima[k] and primeira[bloco[pos + 1]]

        # A frase só continua na linha seguinte se esta linha estiver
        # (quase) cheia E a seguinte não começar com maiúscula.
        # Linhas de campos ("Seguro de saúde: ...", "Rendimento: ...")
        # começam com maiúscula, por isso nunca são juntadas.
        cheia = len(linhas[k].rstrip()) >= limiar
        continua = cheia and not seguinte[:1].isupper()

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


# ============================================================
# Padrão de pesquisa (usado na redação do PDF)
# ============================================================

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


def asteriscos(match):
    """'Maria Clara' -> '* *' (um asterisco por palavra)."""
    return " ".join("*" for _ in match.group().split())


# ============================================================
# Substituição das informações sensíveis no PDF (opcional)
# ============================================================

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
            # desenho = (texto, x, y, fonte, tamanho, cor)
            trabalho = []

            if padrao is not None:
                for bloco in pagina.get_text("rawdict")["blocks"]:
                    for linha in bloco.get("lines", []):
                        chars = []

                        for span in linha["spans"]:
                            for c in span.get("chars", []):
                                chars.append((c, span))

                        if not chars:
                            continue

                        texto = "".join(c["c"] for c, _ in chars)
                        matches = list(padrao.finditer(texto))

                        if not matches:
                            continue

                        primeiro_c, primeiro_span = chars[matches[0].start()]
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
                        pos = matches[0].start()

                        for m in matches:
                            # Texto entre a ocorrência anterior e esta.
                            for k in range(pos, m.start()):
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

                            c_ini, span_ini = chars[m.start()]
                            c_fim, _ = chars[m.end() - 1]
                            fonte = _fonte(span_ini)
                            tam_m = span_ini["size"]
                            x_ini = c_ini["bbox"][0] + delta

                            ast = asteriscos(m)
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

                            delta = (
                                x_ini + largura_nova - c_fim["bbox"][2]
                            )
                            pos = m.end()

                        # Resto da linha depois da última ocorrência.
                        for k in range(pos, len(chars)):
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

                        trabalho.append((retangulo, desenhos))

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


# ============================================================
# Programa principal
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Censura informação sensível de um PDF."
    )
    parser.add_argument("entrada", help="PDF de entrada")
    parser.add_argument(
        "saida", nargs="?", default=None,
        help="PDF redigido (opcional)",
    )
    parser.add_argument(
        "--fields", default=None,
        help="Subtópicos a censurar, separados por vírgula "
             "(por defeito: todos). Ex.: --fields 'Name,Weight'",
    )
    parser.add_argument(
        "--reuse", action="store_true",
        help="Reutiliza sensitive_info.json em vez de chamar o Gemini.",
    )
    args = parser.parse_args()

    pdf_entrada = Path(args.entrada).expanduser().resolve()
    pdf_saida = (
        Path(args.saida).expanduser().resolve() if args.saida else None
    )

    try:
        # 1. Extrair texto do PDF original.
        texto = extrair_texto_pdf(pdf_entrada)

        if not texto.strip():
            raise RuntimeError(
                "O PDF não contém texto extraível. "
                "Se for um PDF digitalizado, será necessário OCR."
            )

        # 2. Obter o dicionário de informações sensíveis.
        if args.reuse and SENSITIVE_INFO_FILE.is_file():
            print("\nA reutilizar sensitive_info.json...", flush=True)
            d = json_para_dict(
                json.loads(SENSITIVE_INFO_FILE.read_text(encoding="utf-8"))
            )
        else:
            print(
                "\nA iniciar a identificação de informações sensíveis...",
                flush=True,
            )
            d = processar_com_gemini(texto)

        print(
            "Subtópicos encontrados: "
            + (", ".join(subtopicos_disponiveis(d)) or "(nenhum)"),
            flush=True,
        )

        # 3. Filtrar pelos subtópicos escolhidos e redigir o texto.
        pedidos = args.fields.split(",") if args.fields else None
        campos = resolver_campos(d, pedidos)
        palavras = createDict(d, campos)

        print("\nA redigir o texto...", flush=True)
        texto_final = FinalText(texto, palavras)

        SUBMISSION_FILE.write_text(texto_final, encoding="utf-8")
        print(
            f"Resultado final guardado em: {SUBMISSION_FILE}",
            flush=True,
        )

        # 4. (Opcional) Redigir também o PDF.
        if pdf_saida is not None:
            print("\nA iniciar a redação do PDF...", flush=True)
            substituir_informacoes_sensiveis(
                pdf_entrada,
                pdf_saida,
                frases_sensiveis(texto, palavras),
            )

        print("\nProcessamento concluído!", flush=True)
        return 0

    except KeyboardInterrupt:
        print(
            "\nProcessamento interrompido pelo utilizador.",
            file=sys.stderr, flush=True,
        )
        return 130

    except Exception as erro:
        print(f"\nERRO: {erro}", file=sys.stderr, flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())