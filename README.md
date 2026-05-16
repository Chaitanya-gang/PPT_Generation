# newd2p — AI Document-to-Presentation Generator

> Turn dense documents into polished, presenter-ready PowerPoint slides — powered by local AI.

Upload a PDF, DOCX, or TXT file and get a themed, narrative-driven presentation with speaker notes, visual cues, and multiple export formats. Works fully offline with Ollama or gracefully falls back to rule-based generation.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Streamlit Frontend                          │
│   Upload · Preview · Generate · Download · Theme Presets           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ REST API (HTTP)
┌──────────────────────────────▼──────────────────────────────────────┐
│                        FastAPI Backend                              │
│                                                                     │
│  ┌───────────┐   ┌───────────┐   ┌────────────┐   ┌─────────────┐ │
│  │  Parsers   │──▶│  Chunking  │──▶│ Embeddings │──▶│ RAG + LLM   │ │
│  │ PDF/DOCX/  │   │ Recursive  │   │ MiniLM +   │   │ Ollama      │ │
│  │ TXT        │   │ Overlapping│   │ FAISS      │   │ (llama3)    │ │
│  └───────────┘   └───────────┘   └────────────┘   └──────┬──────┘ │
│                                                           │        │
│                    ┌──────────────────────────────────────▼──────┐ │
│                    │         Narrative Engine                     │ │
│                    │  Section Classifier · Slide Planner         │ │
│                    │  Speaker Notes · Visual Cues · Layouts      │ │
│                    └──────────────────────┬──────────────────────┘ │
│                                           │                        │
│  ┌────────────┐   ┌──────────┐   ┌───────▼───────┐                │
│  │   Charts    │──▶│ Diagrams  │──▶│  PPT Builder  │               │
│  │ matplotlib  │   │ graphviz  │   │  python-pptx  │               │
│  └────────────┘   └──────────┘   └───────┬───────┘                │
│                                           │                        │
│                    ┌──────────────────────▼──────────────────────┐ │
│                    │           Output & Export                    │ │
│                    │     PPTX · PDF · Markdown · JSON            │ │
│                    └─────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Features

- **Multi-format input** — PDF, DOCX, TXT
- **AI-powered narrative generation** — Ollama LLM with RAG context retrieval
- **Offline fallback** — Rule-based generation works without any LLM running
- **5 dark color palettes** — Vibrant, Ocean, Sunset, Forest, Royal
- **5 presentation styles** — TED Talk, Executive Summary, Training, Storytelling, Pitch Deck
- **6 slide types** — Title, Content, Chart, Transition, Big Number, Closing
- **3 layout modes** — Title + Bullets, Two Column, Visual Focus
- **Smart document detection** — Adapts slide flow for project reports, research papers, and general documents
- **Interactive slide editing** — Regenerate, improve, or simplify individual slides via LLM
- **Per-slide chat** — Ask questions about any slide
- **Speaker notes** — Auto-generated natural-speech presenter notes
- **Multi-format export** — PPTX, PDF, Markdown, JSON handover

---

## Tech Stack

| Category | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Frontend | Streamlit (custom CSS) |
| LLM | Ollama (llama3, configurable) |
| Embeddings | SentenceTransformers (`all-MiniLM-L6-v2`) |
| Vector Store | FAISS (CPU) |
| PDF Parsing | PyMuPDF + pdfplumber |
| DOCX Parsing | python-docx |
| PPT Generation | python-pptx |
| Charts | matplotlib + seaborn |
| Diagrams | graphviz |
| Config | pydantic-settings + dotenv |
| Logging | loguru |

---

## Project Structure

```
newd2p/
├── run.py                      # FastAPI entry point
├── streamlit_app.py            # Streamlit frontend
├── requirements.txt            # Python dependencies
├── .env / .env.example         # Environment configuration
│
├── src/                        # Core backend
│   ├── main.py                 # FastAPI app factory
│   ├── config.py               # Pydantic settings
│   ├── simple_generation.py    # Local fallback generator
│   │
│   ├── api/routes/             # REST endpoints
│   │   ├── upload.py           #   POST /api/upload
│   │   ├── generate.py         #   POST /api/generate, /outline, /slide_action, /chat_with_slide
│   │   └── download.py         #   GET  /api/download/{format}/{file_id}
│   │
│   ├── parsers/                # Document parsers
│   │   ├── pdf_parser.py       #   PyMuPDF + pdfplumber
│   │   ├── docx_parser.py      #   python-docx
│   │   └── txt_parser.py       #   Plain text
│   │
│   ├── chunking/               # Text chunking
│   │   └── recursive_chunker.py
│   │
│   ├── embeddings/             # Vector embeddings
│   │   ├── embedder.py         #   SentenceTransformer wrapper
│   │   └── vector_store.py     #   FAISS index
│   │
│   ├── rag/                    # RAG pipeline
│   │   └── pipeline.py         #   chunk → embed → retrieve → generate
│   │
│   ├── llm/                    # LLM providers
│   │   ├── ollama_provider.py  #   Ollama client
│   │   └── prompt_templates.py #   All prompt templates
│   │
│   ├── narrative/              # Slide narrative engine
│   │   └── section_classifier.py
│   │
│   ├── ppt/                    # PowerPoint builder
│   │   ├── builder.py          #   Main PPT builder (830 lines)
│   │   └── theme_manager.py    #   Color palettes
│   │
│   ├── charts/                 # Chart auto-generation
│   ├── diagrams/               # Graphviz diagrams
│   ├── images/                 # Image generation
│   ├── output/                 # JSON, Markdown, PDF exporters
│   └── utils/                  # Logger, file handler, validators
│
├── frontend/                   # Streamlit components
│   ├── api_client.py           #   Backend API wrapper
│   └── config.py               #   Theme presets, defaults
│
├── templates/                  # PPT template themes
├── prompts/                    # YAML prompt files
├── tests/                      # Test suites for all modules
├── docs/                       # Documentation
└── scripts/                    # Utility & benchmark scripts
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) (optional — for AI-powered generation)

### 1. Clone & Install

```bash
git clone https://github.com/Chaitanya-gang/PPT_Generation.git
cd PPT_Generation
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 3. (Optional) Start Ollama

```bash
ollama pull llama3
ollama serve
```

> Without Ollama, the system falls back to rule-based generation automatically.

### 4. Start the Backend

```bash
python run.py
# or
./start.bat          # Windows
./start.ps1          # PowerShell
```

API available at **http://localhost:8000** — Swagger docs at **http://localhost:8000/docs**

### 5. Start the Frontend

```bash
streamlit run streamlit_app.py
# or
./start_streamlit.bat
./start_streamlit.ps1
```

UI available at **http://localhost:8501**

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/upload` | Upload PDF/DOCX/TXT, returns `file_id` |
| `POST` | `/api/generate` | Full pipeline → parse → generate → build PPT |
| `POST` | `/api/outline` | Lightweight outline preview (no PPT built) |
| `POST` | `/api/generate_from_outline` | Build PPT from a pre-approved outline |
| `POST` | `/api/explain_slide` | LLM explains a specific slide in plain language |
| `POST` | `/api/slide_action` | Regenerate / improve / simplify a single slide |
| `POST` | `/api/chat_with_slide` | Ask questions about a slide's content |
| `GET` | `/api/download/ppt/{file_id}` | Download generated PPTX |
| `GET` | `/api/download/json/{file_id}` | Download handover JSON |
| `GET` | `/api/download/pdf/{file_id}` | Download PDF export |
| `GET` | `/api/download/markdown/{file_id}` | Download Markdown export |
| `GET` | `/api/styles` | List available themes, styles, and templates |
| `GET` | `/health` | Health check |

---

## Data Flow

```
  Upload Document          Parse & Extract         Chunk & Embed
 ┌──────────────┐      ┌──────────────────┐    ┌──────────────────┐
 │ PDF/DOCX/TXT │─────▶│ Text + Sections  │───▶│ TextChunks[]     │
 │              │      │ + Tables         │    │ + FAISS Index    │
 └──────────────┘      └──────────────────┘    └────────┬─────────┘
                                                        │
                  ┌─────────────────────────────────────┘
                  ▼
          ┌───────────────┐         ┌──────────────────────┐
          │ Ollama LLM    │────────▶│ Narrative JSON        │
          │ (or fallback) │         │ slides[], flow,       │
          └───────────────┘         │ speaker_notes, cues   │
                                    └──────────┬───────────┘
                                               │
                                    ┌──────────▼───────────┐
                                    │ PPT Builder           │
                                    │ 5 palettes × 6 types  │
                                    │ + charts + diagrams   │
                                    └──────────┬───────────┘
                                               │
                                    ┌──────────▼───────────┐
                                    │ Export                │
                                    │ PPTX · PDF · MD · JSON│
                                    └──────────────────────┘
```

---

## Configuration

All settings are managed via `.env` file (see `.env.example`):

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3.1:8b` | LLM model to use |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Embedding model |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `DEFAULT_SLIDE_COUNT` | `10` | Default number of slides |
| `MIN_SLIDE_COUNT` | `6` | Minimum slides allowed |
| `MAX_SLIDE_COUNT` | `15` | Maximum slides allowed |

---

## Presentation Styles

| Style | Tone | Best For |
|---|---|---|
| **TED Talk** | Inspiring, conversational | Engaging audience presentations |
| **Executive Summary** | Professional, direct | Leadership reviews |
| **Training** | Clear, instructional | Educational / academic |
| **Storytelling** | Warm, relatable | Narrative-driven talks |
| **Pitch Deck** | Confident, persuasive | Startup / business pitches |

## Color Themes

| Theme | Background | Accent Colors |
|---|---|---|
| **Vibrant** | Deep navy | Indigo, Rose, Cyan, Lime |
| **Ocean** | Near-black blue | Sky blue, Indigo, Emerald, Orange |
| **Sunset** | Dark zinc | Orange, Pink, Purple, Green |
| **Forest** | Dark green | Green, Yellow, Blue, Orange |
| **Royal** | Deep purple | Violet, Pink, Teal, Gold |

---

## License

See [LICENSE](LICENSE) for details.
