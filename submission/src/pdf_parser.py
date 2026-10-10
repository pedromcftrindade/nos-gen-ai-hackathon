import json
import os
import re
import sys
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

LIMIAR_LINHA_CHEIA = 0.75  # linha >= 75% da largura => a frase continua

MAX_CHARS = 4000

MODEL = "gemini-3.5-flash-lite"

API_URL = (
    "https://generativelanguage.googleapis.com/"
    f"v1beta/models/{MODEL}:generateContent"
)

MAX_RETRIES = 4
CONNECT_TIMEOUT = 10
READ_TIMEOUT = 120

HTTP_RETRY_CODES = {429, 500, 502, 503, 504}


PROMPT_TEMPLATE = """You are an Elite Medical Privacy AI. Your ONLY mission is to perfectly redact Personal Identifiable Information (PII) and Protected Health Information (PHI) from a Portuguese clinical document. 

You receive text where every word has a numeric ID, like [12]word.

### THE CONTEXT TEST (ASK YOURSELF THIS):
Before extracting any word, ask: "Does this specific word help identify the patient, their family, or the doctor?"
- If YES (it's a name, trait, condition, or personal contact) -> CENSOR IT.
- If NO (it's a clinic name, a label, a generic verb, or standard text) -> IGNORE IT.

### 🔴 WHAT YOU MUST CENSOR (PERSONAL & SENSITIVE):
1. Demographics & Traits: Age, gender ("Feminino", "Masculino", "M", "F"), marital status ("Divorciada", "Solteiro", "Casado"), nationality, and professions/occupations ("Engenheira", "Professor").
2. Social & Family: Any mention of family members or companions (e.g., "Irmão", "Mãe", "Esposo").
3. Contacts & Identifiers: Personal addresses, phone numbers, NIF, CC, and ALL emails (including a doctor's email like "dr.silva@clinica.pt").
4. Specific Medical Data: The patient's personal diagnoses, diseases, symptoms, specific test results, biometrics (weight/height), and FULL PRESCRIPTIONS (medication name + dosage + frequency, e.g., "Metformina 850mg 2x/dia").
5. Life Dates: Birthdates, admission dates, diagnosis dates.

### 🟢 WHAT YOU MUST NEVER CENSOR (STRICTLY IGNORE):
1. Institutions: Names, addresses, or contacts of clinics, hospitals, and companies (e.g., "Consultório de Lisboa", "Hospital da Luz" are NEVER censored).
2. Labels & Keys: Words that introduce data, like "Nome:", "Idade:", "Sexo:", "Estado Civil:", "Prescrição:", "Morada:". (Only censor the value after them).
3. Generic Text & Grammar: Normal verbs, common nouns, pronouns, articles, and generic medical advice (e.g., "O doente deve descansar", "Apresentou melhorias").
4. Document Metadata: Headers, page numbers, reference codes (e.g., "Processo nº 1234"), and the document's print date.

### RULE: CENSOR COMPLETE EXPRESSIONS
When a personal value has multiple words, extract EVERY word, including connectors ("de", "da", "do", "e").
- Date: "25 de abril de 1978" -> extract all 5 words.
- Disease: "cancro da mama" -> extract all 3 words.

### EXACT FORMATTING
- Return the EXACT word without trailing/leading punctuation (e.g., [4]Lisboa, -> "Lisboa"; [12](ansiedade) -> "ansiedade"). Keep internal characters (e.g., "ana@mail.pt", "2x/dia").
- The ID must match the bracket number perfectly.
- Return ONLY a valid JSON array of `[string, integer]` pairs, ordered by id. NO Markdown, NO explanations.

### THE MASTER EXAMPLE (STUDY THIS CAREFULLY)
Input:
[0]Clínica [1]Médica [2]de [3]Lisboa [4]Email: [5]dr.rui@clinica.pt [6]Processo: [7]ADM-99 [8]Nome: [9]Ana [10]Sexo: [11]Feminino [12]Estado [13]Civil: [14]Divorciada [15]Profissão: [16]Bancária [17]Acompanhante: [18]Irmão [19](Carlos). [20]Histórico: [21]cancro [22]da [23]mama [24]Prescrição: [25]Ibuprofeno [26]600mg [27]2x/dia. [28]O [29]tratamento [30]deve [31]continuar [32]em [33]casa.

Output:
[["dr.rui@clinica.pt", 5], ["Ana", 9], ["Feminino", 11], ["Divorciada", 14], ["Bancária", 16], ["Irmão", 18], ["Carlos", 19], ["cancro", 21], ["da", 22], ["mama", 23], ["Ibuprofeno", 25], ["600mg", 26], ["2x/dia", 27]]

(Explanation for the AI: "Clínica de Lisboa" and "ADM-99" are ignored. Labels like "Sexo:" are ignored. The generic sentence "O tratamento deve continuar em casa." is ignored. But the doctor's email, all demographics, the family member, the full disease, and the full prescription are extracted perfectly.)
 
--- DOCUMENT PART {i} OF {n} ---
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
# Conversão da resposta do Gemini numa lista de pares
# ============================================================

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


def guardar_sensivel(pares):
    """Guarda a lista de pares em sensitive_info.json, um par por linha."""
    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)

    linhas = [
        "  " + json.dumps([palavra, i], ensure_ascii=False)
        for palavra, i in pares
    ]

    SENSITIVE_INFO_FILE.write_text(
        "[\n" + ",\n".join(linhas) + "\n]\n", encoding="utf-8"
    )

    print(f"Lista guardada em: {SENSITIVE_INFO_FILE}", flush=True)


# ============================================================
# Identificação de informações sensíveis
# ============================================================

def processar_com_gemini(texto):
    """
    Envia o texto (palavras numeradas) ao Gemini e devolve a lista
    ordenada de tuplos (palavra, id), sem duplicados e já validada
    contra o texto.
    """
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY não encontrada. "
            "Verifica o ficheiro .env."
        )

    tokens = texto.split()
    chunks = dividir_em_blocos(tokens)
    numero_chunks = len(chunks)

    if not chunks:
        print("Não existe texto para enviar ao Gemini.", flush=True)
        return []

    print(f"Texto dividido em {numero_chunks} parte(s).", flush=True)

    respostas = []
    resultado = set()

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

            pares = converter_resposta_em_lista(resposta)
            validos, corrigidos, descartados = validar_pares(pares, tokens)
            resultado.update(validos)

            if corrigidos:
                print(
                    f"Aviso: {len(corrigidos)} id(s) deslocado(s) "
                    f"corrigido(s) (palavra, id dado, id certo): "
                    f"{corrigidos[:10]}",
                    flush=True,
                )

            if descartados:
                print(
                    f"Aviso: {len(descartados)} par(es) descartado(s) "
                    f"(a palavra não está nesse id): {descartados[:10]}",
                    flush=True,
                )

            print(
                f"Parte {i}/{numero_chunks} concluída em {duracao:.1f}s. "
                f"{len(validos)} palavra(s) identificada(s).",
                flush=True,
            )

    SUBMISSION_DIR.mkdir(parents=True, exist_ok=True)

    with RESPONSES_FILE.open("w", encoding="utf-8") as ficheiro:
        for i, resposta in enumerate(respostas, start=1):
            ficheiro.write(
                f"===== Parte {i}/{numero_chunks} =====\n"
                f"{resposta}\n\n"
            )

    ordenado = sorted(resultado, key=lambda par: (par[1], par[0]))

    guardar_sensivel(ordenado)

    print(f"Respostas guardadas em: {RESPONSES_FILE}", flush=True)

    return ordenado


# ============================================================
# Redação do texto (submission.txt)
# ============================================================

def censurar_token(i, token, WordsSet):
    """Devolve (token_novo, foi_censurado). Mantém a pontuação à volta."""
    for chave, pre, suf in variantes_token(token):
        if chave and chave in WordsSet and i in WordsSet[chave]:
            return f"{pre}*{suf}", True

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

        # Ex.: '+351' (o '+' faz parte do valor)
        for chave, _, _ in variantes_token(token):
            if chave and chave in WordsSet and i in WordsSet[chave]:
                parte = chave
                break

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
# Substituição das informações sensíveis no PDF
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

                    x1_max_bloco = max(l["bbox"][2] for l in linhas)

                    for idx_linha, linha in enumerate(linhas):
                        spans = [
                            s for s in linha["spans"] if s.get("chars")
                        ]

                        novos_textos = []
                        primeiro_alterado = None

                        for idx, span in enumerate(spans):
                            original = "".join(
                                c["c"] for c in span["chars"]
                            )
                            novo = padrao.sub(asteriscos, original)
                            novos_textos.append(novo)

                            if (
                                novo != original
                                and primeiro_alterado is None
                            ):
                                primeiro_alterado = idx

                        if primeiro_alterado is None:
                            continue

                        primeiro = spans[primeiro_alterado]
                        x0 = primeiro["chars"][0]["bbox"][0]
                        bbox_linha = fitz.Rect(linha["bbox"])

                        retangulo = fitz.Rect(
                            x0,
                            bbox_linha.y0,
                            bbox_linha.x1,
                            bbox_linha.y1,
                        )

                        a_inserir = []

                        for idx in range(primeiro_alterado, len(spans)):
                            span = spans[idx]
                            a_inserir.append(
                                (
                                    novos_textos[idx],
                                    span["chars"][0]["origin"],
                                    span["size"],
                                    span["color"],
                                )
                            )

                        # Linha justificada: não é a última do bloco e
                        # chega à margem direita das restantes.
                        ultima_do_bloco = idx_linha == len(linhas) - 1
                        justificada = (
                            not ultima_do_bloco
                            and abs(bbox_linha.x1 - x1_max_bloco)
                            <= TOLERANCIA_JUSTIFICADO
                        )

                        alvo_x1 = bbox_linha.x1 if justificada else None

                        ocorrencias.append(
                            (retangulo, a_inserir, alvo_x1)
                        )

            for retangulo, _, _ in ocorrencias:
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
    if len(sys.argv) != 3:
        print(
            f"Utilização: python3 {Path(sys.argv[0]).name} "
            "entrada.pdf saida.pdf"
        )
        return 1

    pdf_entrada = Path(sys.argv[1]).expanduser().resolve()
    pdf_saida = Path(sys.argv[2]).expanduser().resolve()

    try:
        # 1. Extrair texto do PDF original.
        texto = extrair_texto_pdf(pdf_entrada)

        if not texto.strip():
            raise RuntimeError(
                "O PDF não contém texto extraível. "
                "Se for um PDF digitalizado, será necessário OCR."
            )

        # 2. Pedir ao Gemini a lista de informações sensíveis.
        print(
            "\nA iniciar a identificação de informações sensíveis...",
            flush=True,
        )

        informacoes_sensiveis = processar_com_gemini(texto)

        # 3. Substituir as informações encontradas por '*'.
        print(
            f"Resultado final guardado em: {SUBMISSION_FILE}",
            flush=True,
        )

        

        substituir_informacoes_sensiveis(
            pdf_entrada,
            pdf_saida,
            informacoes_sensiveis,
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