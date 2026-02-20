# team48

Student feedback loop with:
- React frontend (`/app`)
- Python FastAPI backend (`/backend`)

## 1. Backend setup (Python)

```bash
cd /Users/pawarp/Library/CloudStorage/OneDrive-Umich/team48/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Set your API key in `/Users/pawarp/Library/CloudStorage/OneDrive-Umich/team48/backend/.env`:

```env
OPENAI_API_KEY=your_real_key
OPENAI_MODEL=gpt-4.1-mini
```

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
- `VITE_API_BASE_URL/api/analyze-pdf`

Default base URL is `http://localhost:8000`.
help
