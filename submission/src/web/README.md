# Web interface

A page for choosing what to anonymise in a PDF. Plain HTML, CSS and
JavaScript, with no build step and no external dependencies, plus a local
server (`../server.py`).

| File | What it holds |
| --- | --- |
| `index.html` | The application: landing page, workspace and report |
| `../server.py` | The HTTP server only: serves this folder and routes the requests |
| `../site_api.py` | Answers the requests with the backend used by `main.py`; keeps the uploaded PDFs and handles what only the site needs (page images, word positions, ZIP files) |
| `intro.css`, `intro.js` | The animated welcome screen |
| `detective.css`, `detective.js` | The detective that peeks in from the corners of the landing page |
| `lupa.js` | The logo's magnifying glass in SVG, used by the cursor and by the detective |
| `i18n.js` | Portuguese / English: translates the interface text on screen (`EXACT` table and `RULES`) |

## Running it

From the project root, with `GEMINI_API_KEY` in `submission/src/.env`:

```bash
python submission/src/server.py
```

Open <http://127.0.0.1:8765>. Dependencies: `pymupdf`, `requests` and
`python-dotenv` (the same as the rest of the project).

Without the server, `index.html` opens in **demo mode**: only the example
document works (with an analysis stored in the page), as plain text and with
no PDF export.

## Welcome screen

The first screen shows what the program does before a single word is read:

1. A lamp drops from the top, its rope stretches and it swings to a stop.
2. The light comes on and the text is typed out.
3. The sensitive words turn into `*`, one per word.
4. The cursor becomes the logo's magnifying glass: the lens shows the original
   word of the `*` underneath it. On touch screens, tapping the `*` does it.

Scrolling makes the magnifier disappear and undoes the scene as you scroll:
the text is deleted as if with backspace, the light goes out, the lamp rises
and the room blends into the landing page (`setupExit()` in `intro.js`; the
distance is `--exit` in `intro.css`). Scrolling back up plays it in reverse.
A click or a key press skips the animation, and with "reduce motion" enabled
in the system the screen appears directly in its final state.

**To change the text**, edit `index.html`, inside `#intro`. The words wrapped
in `<mark>` are the ones that turn into `*` (this also works in the title).
The English version of each element goes in `data-en`:

```html
<p class="intro-title" data-en="Anonymizator">Anonimizator</p>
<p class="intro-line" data-en="My name is …">Chamo-me <mark>Maria</mark> <mark>Santos</mark>, tenho <mark>47</mark> anos…</p>
```

The site name (Anonimizator; Anonymizator in English) lives in `.intro-title`,
in `.brand` (top bar), in `<title>` and in `i18n.js`.

## Landing page entrance

Each piece of the landing page waits off stage and enters when it reaches the
screen: the slogan is typed letter by letter like the welcome screen, the drop
zone fades in, and the folder slides in from the right while its cover falls
open and the sheets rise out of it. Scrolling back up to the welcome screen
resets everything, so the entrance plays again. Hovering the folder makes it
zoom slightly and fan its sheets out.

`setupEntrance()` in `index.html` only switches `data-enter` from `wait` to
`go` on each piece; the animations themselves are CSS keyframes (`enter-fade`,
`folder-in`, `cover-open`, `sheet-up`). With "reduce motion" enabled, nothing
waits. The slogan is the `<h1>` of `.hero`, with its English version in
`data-en`, like the welcome text.

The magnifier is drawn in SVG by `lupaRays()` in `lupa.js`, with measurements
taken from the original image (36 rays and the handle). The lamp's fall is the
function `lampAt(t)`, with its constants right above it.

## Detective

In the bottom corners of the landing page, a detective peeks in from the
side, enters, makes small gestures (raises the magnifier to his eye, looks
around, tips his hat), leaves and reappears in the opposite corner. He is
attached to the page (he scrolls with it) and does not intercept clicks. The
gestures and their durations are in `GESTURES` (`detective.js`); the poses are
in `detective.css`. His state is kept in `data-*` attributes rather than
classes, so that a gesture name can never clash with a class of the page.

## Flow

The page uses the same functions as `main.py` (`extrair_texto_pdf`,
`processar_com_gemini`, `FinalText`, `substituir_informacoes_sensiveis`),
called by `../site_api.py`.

1. **Upload** one PDF, several, or a ZIP of PDFs. Each document gets its own
   tab, with its own choices, and they are analysed one at a time; more can be
   added along the way. The page shows the PDF itself (each page is an image
   rendered by the server) with a clickable box over every word, in its real
   position. The ids are the positions in `texto.split()`. If the word order
   in the PDF does not match the text, or without the server, the plain text
   is shown instead of the PDF.
2. **Analyse**: `detector.py` sends the prompt from `submission/prompt.txt` to
   Gemini, which returns entries `[value, id, category, subcategory]`. The
   pipeline checks each one against the text, fixes shifted ids and drops the
   wrong ones.
3. **Choose**: the words are grouped by category and subcategory (free labels
   written by Gemini). A whole group or a single word can be switched on or
   off in the panel, or by clicking directly on the PDF to fix false positives
   and negatives. The "Anonymised" view shows the PDF already redacted by the
   pipeline, exactly as it will be exported.
4. **Export**: the PDF (`redact_pdf.py`), the `.txt` in the `submission.txt`
   format (`FinalText`, from `redact_text.py`) and a `.json` report, for the
   document on screen. With several documents, "Download all" bundles the
   redacted PDF and text of each one into a ZIP.

## About us and language

- **About us** (top bar): one paper folder per team member. The name and the
  description are censored (one `*` per word) and are typed out on hover,
  keyboard focus or tap. The data is in the `data-name`, `data-desc` and
  `data-github` attributes in `index.html`.
- **PT / EN** (top bar): switches the interface language and remembers the
  choice. All translations are in `i18n.js`; text added to the page shows in
  Portuguese in both languages until its translation is added there. Uploaded
  documents, Gemini's category names and server error messages are not
  translated.

## Server API

| Route | Request | Response |
| --- | --- | --- |
| `GET /api/health` | | `{ok, has_key, model}` |
| `POST /api/extract` | body = PDF (`application/pdf`) | `{doc_id, pages, masks, boxes, ratios, words}` |
| `POST /api/unzip` | body = ZIP (`application/zip`) | `{docs, skipped}`: the PDFs read and the files ignored |
| `GET /api/layout` | `?doc_id=` | the same as `/api/extract`, for a document already uploaded |
| `POST /api/analyze` | `{doc_id}` | `{pairs, model}` |
| `POST /api/redact` | `{doc_id, ids, format}` | the PDF, or the text with `format: "txt"` |
| `POST /api/redact-all` | `{docs: [{doc_id, name, ids}]}` | a ZIP with the PDF and the text of each document |
| `GET /api/page` | `?doc_id=&n=` | PNG of page `n` of the original |
| `POST /api/preview` | `{doc_id, ids, n}` | PNG of page `n` already redacted |

By default the server only listens on `127.0.0.1`, validates the `Host` header
and requires an explicit `Content-Type`, so that other websites cannot use the
key. `--lan` opens it to the local network (for example, for a phone) and
`--allow-host NAME` accepts one extra host name.

## Notes

- Like `main.py`, analysing a document on the site rewrites
  `submission/extracted_text.txt`, `gemini_responses.txt` and
  `sensitive_info.json` with that document's data. `submission.txt` ends up
  with the censored text of the last document analysed or exported (`.txt`,
  PDF or ZIP), with the words chosen on the page; the preview does not change
  it. Before committing, check with `git status` that those files are the ones
  meant for the submission.
- The example document uses a real analysis of the PDF in `raw_data/`, stored
  inside `index.html`; it does not call Gemini.
- Scanned PDFs (no text layer) need OCR and are rejected.
