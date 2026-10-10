"""Programa principal: orquestra o pipeline de redação."""
import argparse
import sys
from pathlib import Path

from config import SENSITIVE_INFO_FILE, SUBMISSION_FILE, SUBMISSION_PDF
from detector import carregar_sensivel, processar_com_gemini
from parser_aux import lista_para_dict
from pdf_extract import extrair_texto_pdf
from redact_pdf import substituir_informacoes_sensiveis
from redact_text import FinalText, frases_sensiveis


def main():
    parser = argparse.ArgumentParser(
        description="Censura informação sensível de um PDF."
    )
    parser.add_argument("entrada", help="PDF de entrada")
    parser.add_argument(
        "saida", nargs="?", default=None,
        help=f"PDF redigido (por omissão: {SUBMISSION_PDF})",
    )
    parser.add_argument(
        "--reuse", action="store_true",
        help="Reutiliza sensitive_info.json em vez de chamar o Gemini.",
    )
    args = parser.parse_args()

    pdf_entrada = Path(args.entrada).expanduser().resolve()
    # O PDF redigido é sempre guardado; sem 'saida', usa o caminho por omissão.
    pdf_saida = (
        Path(args.saida).expanduser().resolve()
        if args.saida else SUBMISSION_PDF
    )

    try:
        # 1. Extrair texto do PDF original.
        texto = extrair_texto_pdf(pdf_entrada)

        if not texto.strip():
            raise RuntimeError(
                "O PDF não contém texto extraível. "
                "Se for um PDF digitalizado, será necessário OCR."
            )

        # 2. Obter a lista de tuplos (palavra, id).
        if args.reuse and SENSITIVE_INFO_FILE.is_file():
            print("\nA reutilizar sensitive_info.json...", flush=True)
            pares = carregar_sensivel()
        else:
            print(
                "\nA iniciar a identificação de informações sensíveis...",
                flush=True,
            )
            pares = processar_com_gemini(texto)

        print(f"Total de palavras a censurar: {len(pares)}", flush=True)

        palavras = lista_para_dict(pares)

        # 3. Redigir o texto.
        print("\nA redigir o texto...", flush=True)
        texto_final = FinalText(texto, palavras)

        SUBMISSION_FILE.write_text(texto_final, encoding="utf-8")
        print(
            f"Resultado final guardado em: {SUBMISSION_FILE}",
            flush=True,
        )

        # 4. Redigir o PDF e guardá-lo.
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
