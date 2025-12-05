# A11y Check

PDF accessibility and formatting checker for dissertations, built for the CUNY Graduate Center.

## Overview

A11y Check analyzes PDF documents for:
- **WCAG 2.1 Level AA accessibility compliance** - heading hierarchy, alt text, table headers, reading order
- **CUNY Graduate Center formatting requirements** - margins, typography, page numbering, front matter

Uses [Docling](https://github.com/DS4SD/docling) for PDF structure extraction and Claude for analysis.

## Architecture

```
PDF Upload → Docling (structure extraction) → Claude Agent (analysis) → Report
```

- **Frontend**: SvelteKit 2 + Svelte 5 with SSE streaming
- **Backend**: FastAPI with Claude Agent SDK
- **PDF Processing**: Docling for layout analysis and structure extraction

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- Anthropic API key (set as `ANTHROPIC_API_KEY` environment variable)

### Backend

```bash
cd backend

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Copy environment template (optional)
cp .env.example .env

# Run dev server
npm run dev
```

The app will be available at http://localhost:5173

## Configuration

### Frontend Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend API URL |

### Backend Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |

## API Endpoints

### `POST /analyze`

Analyze a PDF document for accessibility and/or formatting compliance.

**Request:**
- Content-Type: `multipart/form-data`
- `file`: PDF file (max 25MB)
- `check_type`: `accessibility`, `formatting`, or `both`

**Response:**
- Content-Type: `text/event-stream`
- Server-Sent Events with analysis results

### `GET /health`

Health check endpoint.

## How It Works

1. **Upload**: User uploads a PDF document
2. **Extraction**: Docling extracts document structure (headings, tables, images, reading order)
3. **Analysis**: Claude Agent analyzes the structure for accessibility/formatting issues
4. **Report**: Streaming results with specific issues, locations, and fix guidance

### What Docling Provides

- Heading hierarchy with levels
- Table structure with header detection
- Image detection with caption/alt text status
- Document reading order
- Text content extraction

### What Claude Analyzes

- Heading hierarchy correctness (H1 → H2 → H3)
- Missing alt text on images
- Table header markup
- Reading order issues
- Formatting compliance with GC requirements

## Development

### Project Structure

```
a11y-check/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── pdf_structure.py     # Docling extraction
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── routes/
│   │   │   └── +page.svelte # Main application
│   │   └── app.css          # Design system
│   └── package.json         # Node dependencies
└── README.md
```

### Running Tests

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm run check
```

## License

MIT
