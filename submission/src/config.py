"""Configuração e constantes partilhadas."""
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

SUBMISSION_DIR = BASE_DIR.parent
SUBMISSION_FILE = SUBMISSION_DIR / "submission.txt"      # resultado FINAL
SUBMISSION_PDF = SUBMISSION_DIR / "submission.pdf"       # PDF redigido (por omissão)
EXTRACTED_FILE = SUBMISSION_DIR / "extracted_text.txt"   # texto original
RESPONSES_FILE = SUBMISSION_DIR / "gemini_responses.txt"
SENSITIVE_INFO_FILE = SUBMISSION_DIR / "sensitive_info.json"
PROMPT_FILE = SUBMISSION_DIR / "prompt.txt"

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

# Resposta inutilizável (JSON inválido, vazia, ids errados): voltar a pedir.
MAX_TENTATIVAS_RESPOSTA = 3
LIMITE_DESCARTADOS = 0.5   # > 50% dos pares sem a palavra no id => repetir


PROMPT_TEMPLATE = Path(PROMPT_FILE).read_text(encoding="utf-8")