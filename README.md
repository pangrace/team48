# team48

Student feedback loop with:
- React frontend (`/app`)
- Python FastAPI backend (`/backend`)
- OCI integration (`/agent`)

## 1. Backend setup (Python)

```bash
cd /Users/pawarp/Library/CloudStorage/OneDrive-Umich/team48/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set OCI values in `/Users/pawarp/Library/CloudStorage/OneDrive-Umich/team48/backend/.env`:

```env
OCI_MODEL_ID=ocid1.generativeaimodel.oc1.us-chicago-1.example
OCI_COMPARTMENT_ID=ocid1.compartment.oc1..example
OCI_CONFIG_FILE=~/.oci/config
OCI_CONFIG_PROFILE=DEFAULT
```

Backend reads Oracle credentials from `~/.oci/config` and calls OCI Generative AI Inference with your model OCID.

Run backend:

```bash
uvicorn main:app --reload --port 8000
```

## 2. Frontend setup (React/Vite)

```bash
cd /Users/pawarp/Library/CloudStorage/OneDrive-Umich/team48/app
npm install
cp .env.example .env
npm run dev
```

Frontend sends PDF uploads to:
- `VITE_API_BASE_URL/api/initial-feedback` (student + instructor PDFs)
- `VITE_API_BASE_URL/api/practice-feedback` (student practice PDF + generated question context)

Default base URL is `http://localhost:8000`.
