"""Identificação de informações sensíveis com o Gemini."""
import json
import os
import time

import requests

from api_call import pedir_gemini
from config import (
    PROMPT_TEMPLATE,
    RESPONSES_FILE,
    SENSITIVE_INFO_FILE,
    SUBMISSION_DIR,
)
from parser_aux import (
    converter_resposta_em_lista,
    dividir_em_blocos,
    validar_pares,
)


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


def carregar_sensivel():
    """Lê sensitive_info.json -> [(palavra, id), ...] (opção --reuse)."""
    return [
        (palavra, int(i))
        for palavra, i in json.loads(
            SENSITIVE_INFO_FILE.read_text(encoding="utf-8")
        )
    ]


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
