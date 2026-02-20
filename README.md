# team48

Student feedback loop with:
- React frontend (`/app`)
- Python FastAPI backend (`/backend`)
- OCI Agent runtime integration (`/agent`)

## 1. Backend setup (Python)

```bash
cd /Users/gracepang/Documents/ai-hackathon/team48/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set OCI values in `/Users/gracepang/Documents/ai-hackathon/team48/backend/.env`:

```env
OCI_AGENT_ENDPOINT_ID=ocid1.genaiagentendpoint.oc1..<your_endpoint_id>
OCI_CONFIG_FILE=~/.oci/config
OCI_CONFIG_PROFILE=DEFAULT
OCI_AGENT_ENDPOINT_ID=ocid1.genaiagentendpoint.oc1.us-chicago-1.example
```

Backend reads Oracle credentials from `~/.oci/config` (profile `DEFAULT`) and sends extracted PDF text to your OCI Agent endpoint.

Run backend:

```bash
uvicorn main:app --reload --port 8000
```

## 2. Frontend setup (React/Vite)

```bash
cd /Users/gracepang/Documents/ai-hackathon/team48/app
npm install
cp .env.example .env
npm run dev
```

Frontend sends PDF uploads to:
- `VITE_API_BASE_URL/api/analyze-pdf`

Default base URL is `http://localhost:8000`.
