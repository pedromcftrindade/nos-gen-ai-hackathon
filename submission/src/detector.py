"""Identificação de informações sensíveis com o Gemini."""
import json
import os
import time

import requests

from api_call import pedir_gemini
from config import (
    LIMITE_DESCARTADOS,
    MAX_TENTATIVAS_RESPOSTA,
    PROMPT_TEMPLATE,
    RESPONSES_FILE,
    SENSITIVE_INFO_FILE,
    SUBMISSION_DIR,
)
from erros import RespostaInvalida
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


def _analisar_parte(session, api_key, prompt, tokens, i, n):
    """
    Pede ao Gemini uma parte e valida a resposta. Se a resposta for
    inutilizável (vazia, JSON inválido, ou a maioria das palavras não
    está no id indicado), volta a pedir, até MAX_TENTATIVAS_RESPOSTA.

    Devolve (resposta, válidos, corrigidos, descartados). Se todas as
    tentativas forem más mas alguma tiver dado resultados, usa a melhor.
    """
    melhor = None
    ultimo_erro = None

    for tentativa in range(1, MAX_TENTATIVAS_RESPOSTA + 1):
        try:
            resposta = pedir_gemini(session, api_key, prompt)
            pares = converter_resposta_em_lista(resposta)

        except RespostaInvalida as erro:
            ultimo_erro = erro
            print(
                f"Parte {i}/{n}: resposta inválida do Gemini "
                f"(tentativa {tentativa}/{MAX_TENTATIVAS_RESPOSTA}): "
                f"{str(erro)[:200]}",
                flush=True,
            )
            continue

        validos, corrigidos, descartados = validar_pares(pares, tokens)
        total = len(validos) + len(descartados)

        candidata = (resposta, validos, corrigidos, descartados)

        if melhor is None or len(validos) > len(melhor[1]):
            melhor = candidata

        if total and len(descartados) / total > LIMITE_DESCARTADOS:
            print(
                f"Parte {i}/{n}: {len(descartados)}/{total} pares com ids "
                f"errados (tentativa {tentativa}/{MAX_TENTATIVAS_RESPOSTA})"
                f". A voltar a pedir...",
                flush=True,
            )
            continue

        return candidata

    if melhor is None:
        raise RespostaInvalida(
            f"Parte {i}/{n}: o Gemini não deu uma resposta válida após "
            f"{MAX_TENTATIVAS_RESPOSTA} tentativas: {ultimo_erro}"
        )

    print(
        f"Aviso: parte {i}/{n}: nenhuma tentativa foi boa; "
        f"a usar a melhor ({len(melhor[1])} palavra(s) válida(s)).",
        flush=True,
    )

    return melhor


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
            resposta, validos, corrigidos, descartados = _analisar_parte(
                session, api_key, prompt, tokens, i, numero_chunks
            )
            duracao = time.monotonic() - inicio

            respostas.append(resposta)
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
