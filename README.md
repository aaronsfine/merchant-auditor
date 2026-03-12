## Merchant Statement Auditor (Prototype)

Backend prototype for a Merchant Statement Auditor application.

### Tech stack

- **Backend**: FastAPI (Python)
- **Frontend**: To be added later (served by FastAPI)

### Running the API locally

1. **Create and activate a virtual environment (recommended)**:

   ```bash
   cd "c:\Users\USER\Documents\Merchant Statement Audit"
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

3. **Start the server with uvicorn**:

   ```bash
   uvicorn main:app --reload
   ```

4. **Test endpoints**:

   - Health check: `http://127.0.0.1:8000/health`
   - Mock audit data: `http://127.0.0.1:8000/api/audit`

