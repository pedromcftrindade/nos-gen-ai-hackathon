import json
import re

MAX_CHARS = 8000

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



# ============================================================
# Conversão da resposta do Gemini numa lista Python
# ============================================================

def converter_resposta_em_lista(resposta):
    """Converte uma resposta JSON do Gemini numa lista de strings."""
    texto = resposta.strip()

    # Tolerar blocos Markdown, caso o modelo os devolva.
    texto = re.sub(
        r"\A```(?:json)?\s*",
        "",
        texto,
        flags=re.IGNORECASE,
    )
    texto = re.sub(r"\s*```\Z", "", texto)

    try:
        dados = json.loads(texto)

    except json.JSONDecodeError:
        # Recuperação caso exista texto adicional antes do array JSON.
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
        raise RuntimeError(
            "A resposta do Gemini não é uma lista JSON."
        )

    resultado = []

    for item in dados:
        if not isinstance(item, str):
            raise RuntimeError(
                "O array JSON contém um elemento que não é uma string."
            )

        item = item.strip()

        if item:
            resultado.append(item)

    return resultado

def dividir_texto(texto, max_chars=MAX_CHARS):
    """Divide o texto em blocos, privilegiando limites naturais."""
    chunks = []
    restante = texto.strip()

    while len(restante) > max_chars:
        janela = restante[:max_chars]
        corte = -1

        for separador in ("\n\n", "\n", ". ", " "):
            pos = janela.rfind(separador)

            if pos > max_chars * 0.5:
                corte = pos + len(separador)
                break

        if corte == -1:
            corte = max_chars

        chunks.append(restante[:corte].strip())
        restante = restante[corte:].lstrip()

    if restante:
        chunks.append(restante)

    return chunks

def asteriscos(match):
    """'Maria do Santos' -> '* * *' (um asterisco por palavra)."""
    return " ".join("*" for _ in match.group().split())

