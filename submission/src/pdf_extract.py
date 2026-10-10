"""Extração do texto do PDF."""
from pathlib import Path

import fitz

from config import EXTRACTED_FILE, SUBMISSION_DIR


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
