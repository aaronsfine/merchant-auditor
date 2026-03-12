from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import csv
import io
from typing import List, Dict, Any, Optional

from mock_data import generate_mock_transactions
from auditor import calculate_leak


app = FastAPI(
    title="Merchant Statement Auditor API",
    version="0.4.0",
    description="Prototype API for auditing merchant card transactions.",
)

# For local development; tighten this later as needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    """
    Serve the static dashboard UI.
    """
    return FileResponse("static/index.html")


def _find_header(headers: List[str], candidates: List[str]) -> Optional[str]:
    """
    Try to find a header name matching any of the candidate labels.
    Comparison is case-insensitive and allows partial matches.
    """
    lowered = [h.strip().lower() for h in headers]
    for cand in candidates:
        c = cand.strip().lower()
        # Exact match
        if c in lowered:
            return headers[lowered.index(c)]
    # fallback: partial contains match
    for cand in candidates:
        c = cand.strip().lower()
        for original, h in zip(headers, lowered):
            if c in h or h in c:
                return original
    return None


def _transactions_from_csv(text: str) -> List[Dict[str, Any]]:
    """
    Parse CSV text and map likely headers into the structure expected
    by the leakage calculator.
    """
    stream = io.StringIO(text)
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded CSV has no header row.",
        )

    headers = reader.fieldnames

    amount_header = _find_header(
        headers,
        ["Amount", "Total", "Auth_Amount", "Auth Amount", "Transaction Amount"],
    )
    interchange_header = _find_header(
        headers,
        ["Interchange", "Qual Code", "Reason Code", "Category", "Interchange Code"],
    )
    date_header = _find_header(headers, ["Date", "Settlement Date", "Txn Date"])
    card_type_header = _find_header(headers, ["Card Type", "Card", "Brand", "Network"])

    if not amount_header or not interchange_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Unable to identify required columns. "
                "Need at least an amount and interchange-related column."
            ),
        )

    transactions: List[Dict[str, Any]] = []

    for row in reader:
        raw_amount = (row.get(amount_header) or "").replace(",", "").strip()
        if not raw_amount:
            continue
        try:
            amount = float(raw_amount)
        except ValueError:
            # Skip rows with non-numeric amounts
            continue

        interchange_code = (row.get(interchange_header) or "").strip()
        if not interchange_code:
            # If we can't see any interchange code, skip: nothing to audit
            continue

        date = (row.get(date_header) or "").strip() if date_header else ""
        card_type = (row.get(card_type_header) or "").strip() if card_type_header else ""

        transactions.append(
            {
                "date": date,
                "amount": amount,
                "card_type": card_type or "UNKNOWN",
                "interchange_code": interchange_code,
            }
        )

    if not transactions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid transactions could be parsed from the uploaded CSV.",
        )

    return transactions


@app.get("/api/audit")
def audit_transactions():
    """
    Run the mock transactions through the leakage calculator
    and return an aggregate summary.
    """
    transactions = generate_mock_transactions()
    summary = calculate_leak(transactions)
    return summary


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    Ingest a CSV of real transactions, perform fuzzy column mapping,
    and return the same leakage summary structure as the mock audit.
    """
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # Decode as UTF-8; tolerate BOM and minor encoding issues
    text = contents.decode("utf-8-sig", errors="ignore")

    transactions = _transactions_from_csv(text)
    summary = calculate_leak(transactions)
    return summary


@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    # Enables `python main.py` for quick testing
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

