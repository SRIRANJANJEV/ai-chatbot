# 🩺 MedAssist — AI Medical Information Chatbot

A production-ready RAG (Retrieval-Augmented Generation) chatbot that answers
medical questions from a custom PDF knowledge base.

```
User Query ──► Embed ──► FAISS Vector Store ──► Top-K Chunks
                                                      │
                                               LLM (GPT-4o-mini)
                                                      │
                                             Answer + Disclaimer
```

---

## 📁 Project Structure

```
medical-chatbot/
│
├── app/
│   ├── __init__.py       # Flask app factory, CORS, rate limiter
│   ├── config.py         # All config loaded from .env
│   ├── logger.py         # Rotating file + console logger
│   ├── rag.py            # LangChain RAG chain (FAISS / Pinecone)
│   ├── routes.py         # Flask blueprints, auth, API endpoints
│   └── security.py       # Input sanitisation, injection guards
│
├── scripts/
│   └── ingest.py         # PDF → chunks → embeddings → FAISS index
│
├── data/
│   ├── pdfs/             # 📥 Drop your medical PDF files here
│   └── vector_store/     # Auto-generated FAISS index (git-ignored)
│
├── templates/
│   └── index.html        # Chat UI (Jinja2 template)
│
├── static/
│   ├── css/style.css
│   └── js/chat.js
│
├── logs/                 # Auto-created; app.log, access.log, error.log
│
├── run.py                # Dev server entry point
├── requirements.txt
├── .env.example          # Copy → .env and fill in secrets
├── .gitignore
├── Dockerfile
└── docker-compose.yml
```

---

## ⚡ Quick Start (Local — Windows)

### Prerequisites
- Python 3.10+ installed  
- An OpenAI API key  
- Medical PDF files (place in `data/pdfs/`)

### Step 1 — Clone & set up environment

```cmd
git clone https://github.com/your-org/medical-chatbot.git
cd medical-chatbot

:: Create virtual environment
python -m venv venv
venv\Scripts\activate

:: Install dependencies
pip install -r requirements.txt
```

### Step 2 — Configure environment variables

```cmd
copy .env.example .env
notepad .env
```

Fill in at minimum:
```
OPENAI_API_KEY=sk-your-key-here
FLASK_SECRET_KEY=any-long-random-string
API_USERNAME=admin
API_PASSWORD=your-strong-password
```

### Step 3 — Add medical PDFs

Place your PDF files (medical textbooks, guidelines, references) into:
```
data\pdfs\
```

Free sources to get started:
- [WHO Medical Publications](https://www.who.int/publications)
- [NIH Free Bookshelf](https://www.ncbi.nlm.nih.gov/books/)
- [OpenStax Anatomy & Physiology](https://openstax.org/details/books/anatomy-and-physiology-2e)

### Step 4 — Build the vector store

```cmd
python scripts/ingest.py
```

This reads all PDFs, splits them into chunks, embeds them, and saves a FAISS
index to `data/vector_store/`. Run this only once (or whenever you add PDFs).

### Step 5 — Start the development server

```cmd
python run.py
```

Open your browser at **http://localhost:5000**

---

## ⚡ Quick Start (Local — macOS / Linux)

```bash
git clone https://github.com/your-org/medical-chatbot.git
cd medical-chatbot

python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
nano .env           # fill in your keys

# Add PDFs to data/pdfs/, then:
python scripts/ingest.py
python run.py
```

---

## 🐳 Docker (Recommended for Production)

```bash
# 1. Build and run
cp .env.example .env  # fill in your secrets first
docker-compose up --build

# 2. Ingest PDFs (first time only)
docker-compose exec medical-chatbot python scripts/ingest.py

# 3. Visit http://localhost:5000
```

---

## 🌐 Deploy on Render.com

1. Push your repo to GitHub (ensure `.env` is **not** committed).
2. Create a new **Web Service** on [render.com](https://render.com).
3. Settings:
   | Field | Value |
   |-------|-------|
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn --bind 0.0.0.0:$PORT --workers 2 run:app` |
   | Instance Type | Starter ($7/mo) or above |
4. Add all environment variables from `.env.example` in the Render dashboard.
5. In your Render Shell, run: `python scripts/ingest.py`

---

## ☁️ Deploy on AWS (EC2)

```bash
# 1. Launch Ubuntu 22.04 EC2 (t3.small or larger)
# 2. SSH in, then:

sudo apt update && sudo apt install -y python3-pip python3-venv nginx

git clone https://github.com/your-org/medical-chatbot.git
cd medical-chatbot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # edit with your values

# Ingest PDFs
python scripts/ingest.py

# Systemd service
sudo tee /etc/systemd/system/medchat.service << 'EOF'
[Unit]
Description=MedAssist Chatbot
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/medical-chatbot
ExecStart=/home/ubuntu/medical-chatbot/venv/bin/gunicorn \
          --workers 2 --bind 127.0.0.1:5000 run:app
Restart=always
EnvironmentFile=/home/ubuntu/medical-chatbot/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now medchat

# Nginx reverse proxy
sudo tee /etc/nginx/sites-available/medchat << 'EOF'
server {
    listen 80;
    server_name YOUR_DOMAIN_OR_IP;
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

sudo ln -s /etc/nginx/sites-available/medchat /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Add HTTPS via Certbot:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN
```

---

## 🔀 Switching to Pinecone (Cloud Vector DB)

1. Sign up at [pinecone.io](https://www.pinecone.io), create an index with
   **dimension=1536** (for `text-embedding-3-small`) and metric **cosine**.
2. In `.env`, set:
   ```
   PINECONE_API_KEY=your-key
   PINECONE_ENV=us-east-1-aws  
   PINECONE_INDEX=medical-index
   ```
3. Install: `pip install pinecone-client`
4. Modify `scripts/ingest.py` — swap FAISS save for:
   ```python
   from langchain_community.vectorstores import Pinecone as PineconeVS
   PineconeVS.from_documents(chunks, embeddings, index_name=Config.PINECONE_INDEX)
   ```

---

## 🔒 Security Features

| Feature | Implementation |
|---------|---------------|
| API Key management | `.env` + `python-dotenv`, never hardcoded |
| Authentication | HTTP Basic Auth (`flask-httpauth`) with hashed passwords |
| Rate limiting | `flask-limiter` — 30 req/min global, 10 req/min on /api/chat |
| Input sanitisation | `bleach` strips HTML/JS; max 2000 chars |
| Prompt injection | Regex pattern matching on 10+ attack patterns |
| Dangerous content | Regex detection + crisis resource response |
| CORS | Restricted to configured origins |
| Non-root Docker | `appuser` in container |
| Secrets in transit | HTTPS enforced via Nginx/Render |

---

## 🧪 Testing the API with curl

```bash
# Health check (no auth required)
curl http://localhost:5000/health

# Chat endpoint
curl -X POST http://localhost:5000/api/chat \
  -u admin:your-password \
  -H "Content-Type: application/json" \
  -d '{"query": "What are the symptoms of Type 2 Diabetes?"}'
```

---

## 🛠️ Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | ✅ | OpenAI API key |
| `FLASK_SECRET_KEY` | ✅ | Flask session secret (use random 32+ char string) |
| `API_USERNAME` | ✅ | Basic auth username |
| `API_PASSWORD` | ✅ | Basic auth password |
| `OPENAI_MODEL` | — | LLM model (default: `gpt-4o-mini`) |
| `OPENAI_EMBEDDING_MODEL` | — | Embedding model (default: `text-embedding-3-small`) |
| `VECTOR_STORE_PATH` | — | FAISS index path (default: `data/vector_store`) |
| `RETRIEVER_TOP_K` | — | Chunks retrieved per query (default: `4`) |
| `CHUNK_SIZE` | — | Characters per chunk (default: `800`) |
| `CHUNK_OVERLAP` | — | Overlap between chunks (default: `100`) |
| `RATE_LIMIT_DEFAULT` | — | Global rate limit (default: `30 per minute`) |
| `RATE_LIMIT_CHAT` | — | Chat endpoint limit (default: `10 per minute`) |

---

## ⚠️ Medical Disclaimer

This software is for **informational and educational purposes only**.  
It is **not** a substitute for professional medical advice, diagnosis, or treatment.  
Always consult a qualified healthcare professional for medical concerns.
