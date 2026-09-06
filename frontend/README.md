# EduRAG frontend

React + TypeScript frontend for EduRAG. The existing FastAPI, RAG, ChromaDB and Ollama services remain unchanged.

## Run locally

```powershell
cd frontend
Copy-Item .env.example .env
npm install
npm run dev
```

Open `http://localhost:3000`. Keep the backend running at `http://localhost:8000`.

## Production container

From the project root:

```powershell
docker compose up --build
```

The frontend is available on port 3000 and the API is available on port 8000.
