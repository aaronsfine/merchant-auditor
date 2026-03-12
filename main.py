from fastapi import FastAPI, UploadFile, File, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
import csv
import io
import secrets
import string
import traceback
from typing import List, Dict, Any, Optional

from mock_data import generate_mock_transactions
from auditor import calculate_leak
from database import init_db, log_processing_error
from notifications import send_processing_error_alert


def _generate_session_id() -> str:
    """Short, unique session ID (6 alphanumeric) for this upload attempt."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(6))


class SanitizedProcessingError(Exception):
    """Raised when CSV parsing fails; carries only row number and error type (no PII/CSV data)."""
    def __init__(self, row_number: int, error_type: str):
        self.row_number = row_number
        self.error_type = error_type
        super().__init__(f"Row {row_number}: {error_type}")


app = FastAPI(
    title="Merchant Statement Auditor API",
    version="0.4.0",
    description="Prototype API for auditing merchant card transactions.",
)


@app.on_event("startup")
def startup():
    init_db()


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
    # Row 1 = header; first data row = 2
    for row_index, row in enumerate(reader):
        row_number = row_index + 2
        try:
            raw_amount = (row.get(amount_header) or "").replace(",", "").strip()
            if not raw_amount:
                continue
            amount = float(raw_amount)

            interchange_code = (row.get(interchange_header) or "").strip()
            if not interchange_code:
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
        except (ValueError, TypeError) as e:
            raise SanitizedProcessingError(row_number, type(e).__name__)
        except Exception as e:
            raise SanitizedProcessingError(row_number, type(e).__name__)

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
    Ingest a CSV entirely in memory (no disk write). Fuzzy column mapping,
    then leakage summary. Session ID returned for every attempt (success or error).
    """
    session_id = _generate_session_id()

    # In-memory only: read into bytes, then decode — file is never written to disk
    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    try:
        # Process from memory only (BytesIO -> decode -> StringIO for csv)
        text = contents.decode("utf-8-sig", errors="ignore")
        transactions = _transactions_from_csv(text)
        summary = calculate_leak(transactions)
        summary["session_id"] = session_id
        return summary
    except HTTPException:
        raise
    except SanitizedProcessingError as e:
        error_message = f"Row {e.row_number}: {e.error_type}"
        stack_trace = traceback.format_exc()
        log_processing_error(session_id, error_message, stack_trace)
        send_processing_error_alert(
            session_id,
            error_message,
            __timestamp_for_logs(),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Processing failed. Please try again or contact support with your Session ID.",
                "session_id": session_id,
            },
            headers={"X-Session-Id": session_id},
        )
    except Exception as e:
        error_message = f"{type(e).__name__}: processing error"
        stack_trace = traceback.format_exc()
        log_processing_error(session_id, error_message, stack_trace)
        send_processing_error_alert(
            session_id,
            error_message,
            __timestamp_for_logs(),
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Processing failed. Please try again or contact support with your Session ID.",
                "session_id": session_id,
            },
            headers={"X-Session-Id": session_id},
        )


def __timestamp_for_logs() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@app.get("/health")
def health_check():
    return {"status": "ok"}


if __name__ == "__main__":
    # Enables `python main.py` for quick testing
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

