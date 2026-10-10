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

LIMIAR_LINHA_CHEIA = 0.75  # linha >= 75% da largura => a frase continua

MAX_CHARS = 2000

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
