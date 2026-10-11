# Anonymizator: the code

Takes a PDF, asks Gemini to identify the personal data and returns the same
document with every sensitive word replaced by `*`, as text and as a PDF. It
can be used from the command line (`main.py`) or through the website
(`server.py`).

## Installation

From the repository root:

```bash
python -m venv .venv
```

```bash
.venv/bin/pip install pymupdf requests python-dotenv
```

Create the file `submission/src/.env` with the Gemini key (it is not committed
to git):

```
GEMINI_API_KEY=your_key
```

## Usage

### Command line

```bash
.venv/bin/python submission/src/main.py raw_data/document_to_anonymize.pdf
```

| Argument | What it does |
| --- | --- |
| `entrada` | The PDF to anonymise |
| `saida` (optional) | Where to save the censored PDF; by default, `submission/submission.pdf` |
| `--reuse` | Reuses the `sensitive_info.json` from the last analysis instead of calling Gemini |

### Website

```bash
.venv/bin/python submission/src/server.py
```

Open <http://127.0.0.1:8765>. On the site you upload one or several PDFs (or a
ZIP), see what Gemini detected on top of the PDF itself, choose what stays
hidden and export the result. `Ctrl+C` in the terminal stops the server. The
details are in [`web/README.md`](web/README.md).

## How it works

1. **Extract.** The text of the PDF is read with PyMuPDF and every word gets
   an id: its position in `texto.split()`, counting from 0.
2. **Detect.** The text goes to Gemini with the words numbered
   (`[0]Relatório [1]de ...`), in blocks of up to 4000 characters, with the
   prompt in `submission/prompt.txt`. Gemini returns a list of entries
   `[value, id, category, subcategory]`.
3. **Validate.** An entry is only accepted if the words of the value really
   are at that id. An id that is off by up to 3 positions is corrected; the
   others are dropped. If more than half come back wrong, the request is
   repeated (up to 3 times).
4. **Censor the text.** Every accepted word becomes `*`, keeping the
   punctuation around it (`Santos,` becomes `*,`). Lines that get shorter are
   re-wrapped to the original width.
5. **Censor the PDF.** The same words, by the same ids, are erased from the
   PDF and replaced by `*`, including in slanted or vertical text.

## Files

### The program

| File | What it does |
| --- | --- |
| `main.py` | Command-line entry point: runs the five steps above |
| `config.py` | Paths, Gemini model, limits and the prompt (read from `prompt.txt`) |
| `pdf_extract.py` | Extracts the text from the PDF |
| `detector.py` | Sends the text to Gemini block by block, validates and merges the answers |
| `api_call.py` | The HTTP request to the Gemini API, retrying on temporary errors |
| `parser_aux.py` | Numbers the words, parses the JSON answer and validates the ids |
| `redact_text.py` | Produces the censored text (`FinalText`) and the replacements to apply to the PDF |
| `redact_pdf.py` | Applies the replacements to the PDF, in horizontal or slanted text |
| `erros.py` | The `RespostaInvalida` exception, for unusable answers from Gemini |

### The website

| File | What it does |
| --- | --- |
| `server.py` | The HTTP server only: serves the `web/` folder and routes the requests |
| `site_api.py` | Answers the page's requests by calling the program's functions |
| `web/` | The page: HTML, CSS and JavaScript, with no build step |

The website has no anonymisation logic of its own: everything goes through the
functions in the files above.

## What gets written

Both `main.py` and the website write to `submission/`:

| File | Contents |
| --- | --- |
| `submission.txt` | The censored text: the result evaluated in the hackathon |
| `submission.pdf` | The censored PDF (`main.py` only; the site delivers it as a download) |
| `extracted_text.txt` | The original text extracted from the PDF |
| `gemini_responses.txt` | Gemini's answers, exactly as they arrived |
| `sensitive_info.json` | The accepted entries: `[value, id, category, subcategory]` |

Each run replaces the files of the previous one. On the site, `submission.txt`
ends up with the last document analysed or exported, with the words chosen on
the page.

## Configuration

In `config.py`:

| Constant | Value | What it is for |
| --- | --- | --- |
| `MODEL` | `gemini-3.5-flash-lite` | The model used |
| `MAX_CHARS` | 4000 | Maximum size of each block sent |
| `MAX_RETRIES` | 4 | Attempts on network or temporary HTTP errors |
| `MAX_TENTATIVAS_RESPOSTA` | 3 | Attempts when the answer is unusable |
| `LIMITE_DESCARTADOS` | 0.5 | Share of wrong ids above which the request is repeated |

The prompt is edited in `submission/prompt.txt`.

## Limitations

- Scanned PDFs (image only) have no text to extract: OCR would be needed.
- The result depends on the model and varies from run to run; it should be
  reviewed before sharing, which is what the website is for.
- The categories are free text written by Gemini, so their names can change
  between analyses.

## Libraries

[PyMuPDF](https://pymupdf.readthedocs.io) (reading and writing PDFs),
[Requests](https://requests.readthedocs.io) (HTTP requests) and
[python-dotenv](https://github.com/theskumar/python-dotenv) (reading the
`.env` file).
