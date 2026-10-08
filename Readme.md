# ⚖️ NyayaGPT — Nyay Sahayak

### Your AI-Powered Guide to Indian Criminal Law

[![Live Demo](https://img.shields.io/badge/Live%20Demo-nyayagpt.in-brightgreen?style=flat-square)](https://nyayagpt.in)
[![API](https://img.shields.io/badge/API-api.nyayagpt.in-blue?style=flat-square)](https://api.nyayagpt.in/docs)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=flat-square)](./LICENSE)
[![BNS Updated](https://img.shields.io/badge/Law-BNS%202023%20Updated-orange?style=flat-square)](#)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square)](https://python.org)

**NyayaGPT (Nyay Sahayak)** is a free, intelligent legal assistant that bridges the gap between complex Indian criminal law and the common citizen. Built using **Retrieval-Augmented Generation (RAG)**, it instantly maps real-world crime descriptions to relevant sections of the **Bharatiya Nyaya Sanhita (BNS) 2023** — India's current criminal law — and helps users prepare a structured **First Information Report (FIR)**.

> **"We don't file your FIR — we make sure you know exactly what to say, which law was broken, and where to go. So police can't turn you away."**

---

## 🚀 Key Features

- **🔍 Instant Legal Analysis** — Describe a crime in plain English (e.g., *"A man broke into my house at night and stole jewellery"*) and the AI identifies applicable BNS 2023 sections with plain-language explanations.
- **🧠 RAG Architecture** — Unlike standard chatbots, NyayaGPT retrieves exact legal text from a verified knowledge base using **InLegalBERT** embeddings before generating answers — dramatically reducing hallucinations.
- **📝 Smart FIR Preparation Summary** — Generates a structured complaint document with correct BNS section references, validated fields, and a "Next Steps" block directing users to the correct e-FIR portal or police station.
- **⚖️ Rights Awareness** — Informs users that police cannot refuse a cognizable FIR under **BNSS Section 173**, and what to do if they try.
- **🗺️ Filing Route Guidance** — Determines whether the offence qualifies for e-FIR and provides a direct link, or directs to the nearest police station.
- **🆓 Zero Cost, Zero Login** — Fully free, accessible on any browser, no account required.

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **LLM** | Google Gemini API (`gemini-1.5-flash`) | Legal analysis & FIR generation |
| **Embeddings** | `law-ai/InLegalBERT` (local, offline) | Domain-specific legal vector embeddings |
| **Vector DB** | ChromaDB | BNS section retrieval |
| **Backend** | Python 3.12, FastAPI, Uvicorn | REST API & RAG pipeline |
| **Frontend** | HTML5, Tailwind CSS, Vanilla JavaScript | User interface |
| **Deployment** | AWS EC2 (t3.medium) + Nginx + Let's Encrypt | Backend hosting |
| **Frontend Hosting** | Vercel | Frontend CDN |
| **Domain** | GoDaddy — `nyayagpt.in` / `api.nyayagpt.in` | Custom domain |

---

## ⚙️ Architecture

NyayaGPT uses a **Retrieval-Augmented Generation (RAG)** pipeline:

```
English Query
      ↓
Validate (English-only check + normalize)
      ↓
Add retrieval prefix: "legal query: " + query
      ↓
InLegalBERT Embedding (mean pooling + L2 normalize)
      ↓
ChromaDB Vector Search → Top-K BNS Sections
      ↓
Google Gemini (grounded generation with retrieved context)
      ↓
Legal Analysis + Smart FIR Preparation Summary
```

**Why InLegalBERT?**
InLegalBERT is trained on 5.4 million Indian Supreme Court and High Court documents. It outperforms general-purpose models on Indian legal statute identification — the exact task NyayaGPT performs. It runs fully offline on the server, eliminating API dependency for retrieval.

**Production Deployment:**
```
User → nyayagpt.in (Vercel) → api.nyayagpt.in → Nginx (EC2) → FastAPI :8000 → ChromaDB + Gemini
```

---

## 🏃 Getting Started (Local Development)

### Prerequisites

- Python 3.10+
- A Google Gemini API Key ([get one free](https://aistudio.google.com))
- 2GB+ free disk space (for InLegalBERT model cache)

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/Naitik120gupta/nyayagpt.git
cd nyayagpt
```

**2. Set up virtual environment**
```bash
python -m venv venv

# Windows
.\venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

**3. Install dependencies**
```bash
pip install -r backend/requirements.txt
```

**4. Configure environment variables**

Create a `.env` file inside `backend/`:
```bash
# backend/.env
GEMINI_API_KEY="your_api_key_here"
```

**5. Prepare the BNS dataset**

Download the BNS dataset and place the CSV file at:
```
backend/data/bns_data.csv
```

**6. Build the knowledge base**

Run the ingestion script to embed the BNS corpus into ChromaDB:
```bash
cd backend
python scripts/ingest.py
```
> ⚠️ First run downloads InLegalBERT (~534MB). Ensure you have sufficient disk space and a stable internet connection. Use `tmux` if running on a remote server to prevent SSH disconnection from killing the process.

**7. Start the backend server**
```bash
cd /path/to/nyayagpt
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

**8. Open the frontend**

Open `frontend/index.html` in your browser, or serve it locally:
```bash
cd frontend
python -m http.server 5500
# Visit: http://localhost:5500
```

---

## 🚀 Production Deployment (AWS EC2)

The frontend is a static site on **Vercel**; the FastAPI backend runs on an **EC2** instance behind Nginx at `api.nyayagpt.in`.

### Infrastructure

| Component | Details |
|---|---|
| Instance | AWS EC2 t3.medium (2 vCPU, 4GB RAM) |
| OS | Ubuntu 22.04 LTS, Python 3.11 |
| App server | Uvicorn (1 worker), managed by systemd as `nyayagpt-backend` |
| Reverse proxy | Nginx → `127.0.0.1:8000` |
| SSL | Let's Encrypt via certbot (auto-renewing) |
| Frontend | Vercel (auto-deploys from `main`) |
| CI/CD | GitHub Actions: tests on every push, auto-deploy to EC2 on merge to `main` |

### First-time setup

**1. Install system packages and the app**
```bash
sudo apt update && sudo apt install -y python3.11-venv nginx certbot python3-certbot-nginx

git clone https://github.com/Naitik120gupta/nyayagpt.git
cd nyayagpt
python3.11 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt

cp backend/.env.example backend/.env   # then set GEMINI_API_KEY
```

The vector store ships with the repo, so ingestion is only needed after you change the dataset or the embedding model:
```bash
tmux new -s ingest                     # survives SSH disconnects
python backend/scripts/ingest.py       # Ctrl+B, then D to detach
```

**2. Run the backend as a service**
```bash
sudo cp deploy/nyayagpt-backend.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nyayagpt-backend
```

**3. Put Nginx and HTTPS in front of it**
```bash
sudo cp deploy/nginx-nyayagpt.conf /etc/nginx/sites-available/nyayagpt
sudo ln -s /etc/nginx/sites-available/nyayagpt /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d api.nyayagpt.in
```

**4. Point DNS at the server**: add an `A` record for `api` with the instance's public IP, then check:
```bash
curl -I https://api.nyayagpt.in/docs
```

> ⚠️ The first start downloads InLegalBERT (~450MB) and can take a few minutes. Keep one Uvicorn worker on a 4GB instance, because each worker loads its own copy of the model.

### Continuous deployment

After the one-time setup, every push to `main` that passes the test suite is deployed automatically by [`.github/workflows/ci-cd.yml`](./.github/workflows/ci-cd.yml): it pulls `main` on the server, reinstalls requirements, restarts `nyayagpt-backend` and runs a health check. This needs the `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_SSH_KEY` and `DEPLOY_PATH` repository secrets.

### Troubleshooting
```bash
sudo systemctl status nyayagpt-backend
sudo journalctl -u nyayagpt-backend -n 100 --no-pager
```

Full runbook (deploy keys, secrets, sudoers rule): [`deploy/DEPLOY.md`](./deploy/DEPLOY.md)

---

## 📁 Project Structure

```
nyayagpt/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, router
│   │   ├── api/
│   │   │   └── endpoints.py     # /analyze route
│   │   ├── services/
│   │   │   ├── rag_service.py   # End-to-end RAG pipeline
│   │   │   ├── retrieval.py     # InLegalBERT + ChromaDB retrieval
│   │   │   ├── embeddings.py    # Model loader (mean pool + normalize)
│   │   │   ├── gemini_service.py# Gemini API integration
│   │   │   └── ingestion.py     # Document ingestion helpers
│   │   └── core/
│   │       └── config.py        # Pydantic settings / env vars
│   ├── scripts/
│   │   └── ingest.py            # One-time BNS corpus ingestion
│   ├── data/
│   │   └── bns_data.csv         # BNS 2023 dataset (not committed)
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   └── assets/
│       ├── js/main.js           # Fetch → /analyze, FIR rendering
│       └── css/style.css
├── vercel.json                  # Vercel frontend config
└── README.md
```

---

## 🔌 API Reference

### `POST /analyze`

Analyzes a crime description and returns applicable BNS sections + FIR summary.

**Request**
```json
{
  "query": "A man broke into my house at night and stole jewellery worth 3 lakhs"
}
```

**Response**
```json
{
  "sections": [
    {
      "section": "BNS Section 303",
      "title": "Theft",
      "description": "...",
      "punishment": "..."
    }
  ],
  "fir_summary": "...",
  "rights": "...",
  "next_steps": "..."
}
```

**Health check**
```bash
GET /health     # → {"status": "ok"}
GET /docs       # → Swagger UI
```

---

## 🔮 Roadmap

### Phase 1 — Live Now ✅
- [x] BNS 2023 section identification from plain English
- [x] Smart FIR Preparation Summary
- [x] Rights briefing (BNSS Section 173)
- [x] e-FIR portal routing
- [x] InLegalBERT local embeddings (offline)
- [x] Production deployment on AWS EC2

### Phase 2 — 30 Days 🔄
- [ ] Voice input (Web Speech API / Whisper)
- [ ] Hindi language support
- [ ] Nearest police station locator
- [ ] Downloadable FIR PDF

### Phase 3 — 6–12 Months 📅
- [ ] WhatsApp bot integration
- [ ] NGO / legal aid organization dashboard
- [ ] BNSS + Bharatiya Sakshya Adhiniyam corpus
- [ ] Case law citation linking (Supreme Court / High Court)
- [ ] State government MoU pilot (UP / Delhi CCTNS)

### Phase 4 — Long Term 🏛️
- [ ] Direct CCTNS IIF-1 form integration
- [ ] Android app (offline-capable)
- [ ] Regional language support (Bengali, Tamil, Telugu, Marathi)
- [ ] FIR submission directly to state e-FIR portals via API

---

## ⚠️ Important Notes

**English Only (Current Version)**
NyayaGPT currently accepts English queries only. Hindi and multilingual support is planned for Phase 2.

**Not Legal Advice**
NyayaGPT provides legal information for educational and empowerment purposes only. It does not constitute professional legal advice. Always consult a qualified lawyer for your specific situation.

**BNS 2023 — Current Law**
This project uses the Bharatiya Nyaya Sanhita (BNS) 2023, which replaced the Indian Penal Code (IPC) effective July 2024. Old IPC section references are not used.

---

## 🤝 Contributing

Contributions are welcome for non-core modules. Please open an issue before submitting a pull request. See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for guidelines.

---

## 📄 License

© 2026 Naitik Gupta. All Rights Reserved.

This project is proprietary software. Unauthorized copying, modification, distribution, or use of this software, in whole or in part, without express written permission is strictly prohibited. See [`LICENSE`](./LICENSE) for full terms.

---

## 🙏 Acknowledgements

- [InLegalBERT](https://huggingface.co/law-ai/InLegalBERT) — IIT Kharagpur (law-ai) for the Indian legal domain embedding model
- [Google Gemini](https://ai.google.dev) — LLM powering the generation layer
- [ChromaDB](https://www.trychroma.com) — Open-source vector database
- [FastAPI](https://fastapi.tiangolo.com) — Modern Python web framework

---

<div align="center">
  <strong>nyayagpt.in</strong> &nbsp;·&nbsp; api.nyayagpt.in &nbsp;·&nbsp; github.com/Naitik120gupta/nyayagpt
  <br><br>
  <em>Built for every Indian citizen who deserves to know their rights.</em>
</div>
