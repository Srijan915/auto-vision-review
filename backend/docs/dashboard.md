# ClaimSense reviewer dashboard

The dashboard is a Streamlit client of the FastAPI service. It contains no
model, RAG, Gemini, coverage, payment, or claim-decision logic.

Start the API in one terminal:

```powershell
.\.venv\Scripts\uvicorn.exe src.api:app --reload
```

Start the dashboard in another terminal using the same environment:

```powershell
.\.venv\Scripts\streamlit.exe run src\dashboard.py
```

By default the dashboard calls `http://127.0.0.1:8000`; set
`CLAIMSENSE_API_URL` or use the sidebar control to select another API address.

The reviewer can create or reopen an assessment, compare the original image to
API-provided detection overlays, inspect detection confidence and source-cited
RAG/Gemini evidence, and submit or update an explicitly human-authored review.
When RAG is empty or Gemini is unavailable, the dashboard shows that state and
does not infer missing policy information. The dashboard never displays an
automatic insurance approval/rejection or a coverage, payout, liability, fraud,
cost, or legal conclusion.
