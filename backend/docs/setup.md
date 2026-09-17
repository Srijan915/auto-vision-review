# ClaimSense demo setup

Use the repository's existing `.venv`; do not create a second environment.
Direct runtime dependencies are pinned in `requirements.txt`. Test-only HTTP
transport support is in `requirements-dev.txt`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m pip check
```

Start the API and dashboard in separate terminals:

```powershell
.\.venv\Scripts\uvicorn.exe src.api:app --reload
.\.venv\Scripts\streamlit.exe run src\dashboard.py
```

The application requires the verified local model checkpoint already referenced
by `configs/model_inference.yaml`. RAG remains safely unavailable until
approved UTF-8 `.txt`, `.md`, or `.json` documents are placed in
`data/documents/` and an index is explicitly built. Gemini remains optional and
uses `GEMINI_API_KEY` from `.env` only when grounded retrieval evidence exists.
