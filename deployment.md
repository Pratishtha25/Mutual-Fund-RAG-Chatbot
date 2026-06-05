# Deployment Guide: Groww FAQ Assistant (Mutual Fund & Stock Chatbot)

This document provides step-by-step instructions for deploying and running the RAG-based Groww FAQ Assistant both locally for development/testing and in a production environment.

---

## Prerequisites

Before starting, ensure your host machine has the following installed:
1. **Python 3.10+** (to run the FastAPI backend)
2. **Git** (for version control and repository updates)
3. **Ollama** (for local text embedding generation)
4. **Groq Cloud API Key** (for deterministic LLM query synthesis)
5. **Node.js / npm** (optional, if using static hosting servers)

---

## Environment Variables

The backend application requires the following environment variables. Set them in your shell session, terminal, or your deployment platform's dashboard:

| Variable Name | Description | Default Value |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | Your secret API key from Groq Console | *Required* |
| `GROQ_MODEL` | The LLM model to query on Groq Cloud | `llama-3.3-70b-versatile` |
| `OLLAMA_URL` | The endpoint address of the local Ollama instance | `http://localhost:11434` |

---

## Local Development Setup

### Step 1: Clone the Repository
Open a terminal and clone the repository:
```bash
git clone https://github.com/Pratishtha25/Mutual-Fund-RAG-Chatbot.git
cd Mutual-Fund-RAG-Chatbot
```

### Step 2: Install Python Dependencies
Create a virtual environment, activate it, and install required dependencies:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate

# Install requirements
pip install -r requirements.txt
```

### Step 3: Run and Configure Ollama
1. Download and run Ollama from [ollama.com](https://ollama.com).
2. Pull the embedding model `nomic-embed-text`:
   ```bash
   ollama pull nomic-embed-text
   ```
3. Keep the Ollama application running on port `11434` (default).

### Step 4: Run the Backend Server
Set your Groq API key and start the FastAPI backend:
```bash
# Windows (PowerShell)
$env:GROQ_API_KEY="your-api-key-here"
python backend/app/main.py

# macOS/Linux
export GROQ_API_KEY="your-api-key-here"
python backend/app/main.py
```
The backend server will launch on `http://localhost:8001`.

### Step 5: Launch the Frontend
The frontend consists of static assets (HTML, CSS, JS). You can run a lightweight HTTP server in the `frontend` directory:
```bash
cd frontend
# Using Python's built-in server:
python -m http.server 8000
```
Open your browser and navigate to `http://localhost:8000` to interact with the Chatbot dashboard.

---

## Production Deployment

### 1. Backend Deployment (e.g., Render, AWS EC2, or GCP)
You can deploy the FastAPI backend using standard cloud services or a Docker container.

#### Option A: Docker Deployment
A sample `Dockerfile` for the backend:
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend

EXPOSE 8001

ENV PORT=8001
ENV GROQ_MODEL=llama-3.3-70b-versatile
ENV OLLAMA_URL=http://ollama-service:11434

CMD ["python", "backend/app/main.py"]
```
Build and run the container:
```bash
docker build -t mutual-fund-rag-backend .
docker run -p 8001:8001 -e GROQ_API_KEY="your-api-key" mutual-fund-rag-backend
```

#### Option B: Deploying on Render
1. Create a new **Web Service** on Render connected to your GitHub repository.
2. Select **Python** as the environment.
3. Set **Start Command** to: `uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT` (modify `main.py` if needed or run using `python backend/app/main.py`).
4. In the **Environment** settings tab, add the environment variable `GROQ_API_KEY`.

### 2. Ollama in Production
For production deployments requiring local embeddings:
- You must run a persistent Ollama container alongside the backend. In cloud setups, it is often simpler to host Ollama on an EC2 instance with GPU support, or containerize it in a Docker Compose network:
```yaml
version: '3.8'
services:
  backend:
    build: .
    ports:
      - "8001:8001"
    environment:
      - GROQ_API_KEY=your-api-key
      - OLLAMA_URL=http://ollama:11434
    depends_on:
      - ollama

  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama

volumes:
  ollama-data:
```
*Note: Upon spawning the Ollama container, you must run an exec command to pull the embedding model: `docker exec -it <ollama-container-name> ollama pull nomic-embed-text`.*

### 3. Frontend Deployment (e.g., Vercel, Netlify, GitHub Pages)
Since the frontend is purely static, you can deploy it for free:
1. Connect your repository to **Vercel** or **Netlify**.
2. Set the build directory / root directory to `frontend`.
3. In `frontend/app.js`, update the `API_URL` constant from `http://localhost:8001/api/chat` to your deployed backend URL:
   ```javascript
   const API_URL = "https://your-backend-service.onrender.com/api/chat";
   ```

---

## Data Synchronization & Maintenance

### Background Scheduler (APScheduler)
The application utilizes `BackgroundScheduler` to automatically sync mutual fund SIDs and stock metrics:
- **Daily Sync**: Re-scrapes the 5 stock profiles and compiles the corpus daily at **18:30 IST** (after market closes).
- **Weekly Check**: Scans for new mutual fund PDFs and updates the corpus weekly on **Friday at 10:00 IST**.
- The in-memory similarity matrix cache will automatically hot-reload upon completion without interrupting active API connections.
