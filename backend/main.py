"""
A11y Check - PDF Accessibility & Formatting Checker
FastAPI backend using Claude Agent SDK with streaming responses
"""

import os
import json
import tempfile
import logging
from typing import Literal
from dataclasses import asdict, is_dataclass
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from claude_agent_sdk import query, ClaudeAgentOptions
from pdf_structure import extract_pdf_structure, format_structure_for_agent

# Reduce noise from Docling
logging.getLogger("docling").setLevel(logging.WARNING)
logging.getLogger("rapidocr").setLevel(logging.WARNING)


def serialize_event(event):
    """Serialize SDK event objects to JSON-compatible dicts."""
    if is_dataclass(event) and not isinstance(event, type):
        return asdict(event)
    elif hasattr(event, '__dict__'):
        return event.__dict__
    else:
        return str(event)

app = FastAPI(
    title="A11y Check API",
    description="PDF Accessibility and Formatting Analysis",
    version="1.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173", "http://localhost:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# SYSTEM PROMPTS
# ============================================================================

ACCESSIBILITY_SYSTEM_PROMPT = """You are an accessibility expert helping students prepare their dissertations for submission to Academic Works.

# Output Format

This is a ONE-TIME REPORT. The user cannot respond or ask follow-up questions. Your output must be a complete, self-contained accessibility report that the student can use to fix their document independently.

Do NOT include an analysis date or timestamp - just provide the report content.

# Your Role

Review PDF documents for WCAG 2.1 Level AA accessibility compliance. New federal accessibility requirements go into effect April 24, 2026.

# Key Areas to Check

## Document Structure
- Heading hierarchy (H1 > H2 > H3, logical flow)
- Reading order (content flows logically when read linearly)
- Tagged structure

## Images and Visuals
- Alt text on ALL images, figures, charts, diagrams
- Complex graphics have detailed descriptions
- No text presented as images/screenshots

## Color and Contrast
- Sufficient text contrast (4.5:1 for normal text, 3:1 for large)
- Information not conveyed by color alone

## Links
- Descriptive link text (not "click here" or "read more")
- Clear link destinations

## Tables
- Properly marked header rows/columns
- Captions or summaries
- Simple structure (avoid complex nesting)

## Document Metadata
- Title set in document properties
- Language specified
- Bookmarks for navigation (long documents)

## Text
- Real text, not images of text
- Readable embedded fonts

# How to Work

You will receive comprehensive structural analysis from Docling, which provides:
- Complete heading hierarchy with levels
- All tables with header row detection
- All images with caption/alt text detection
- Document reading order
- Text content in markdown format

This extracted data tells you DEFINITIVELY:
- What elements are tagged as headings vs body text
- The reading order of elements
- Whether tables have header rows marked
- Whether images have captions/alt text
- The document's logical structure

Analyze this structural data to identify accessibility issues. You do NOT need to read the PDF file directly - all relevant information is provided in the analysis.

Report findings clearly with specific locations (page numbers when available) and provide actionable fix guidance.

# Fix Guidance

When explaining how to fix issues, provide TOOL-AGNOSTIC instructions that work across different software. Students may be using:
- Google Docs (most common)
- Microsoft Word
- LibreOffice Writer
- LaTeX
- Other tools

Do NOT assume the user has Adobe Acrobat Pro. Instead:
- Explain fixes using the word processor (Google Docs, Word, etc.) rather than PDF editing tools
- Explain the general principle (e.g., "use heading styles instead of bold text")
- For Google Docs specifically: Accessibility settings are under Tools > Accessibility

# Severity Levels

- **CRITICAL**: Makes content inaccessible (missing alt text, no heading structure, color-only information)
- **WARNING**: Significantly impacts accessibility (poor contrast, vague links, missing table headers)
- **SUGGESTION**: Recommendations for improvement (add bookmarks, simplify tables)

Be helpful and encouraging. Students need to understand what to fix and how to fix it."""

FORMATTING_SYSTEM_PROMPT = """You are a dissertation formatting expert helping students prepare their work for submission to the CUNY Graduate Center.

# Output Format

This is a ONE-TIME REPORT. The user cannot respond or ask follow-up questions. Your output must be a complete, self-contained formatting report that the student can use to fix their document independently.

Do NOT include an analysis date or timestamp - just provide the report content.

# Your Role

Review PDF documents for compliance with Graduate Center dissertation formatting requirements.

# Key Areas to Check

## Page Layout
- Margins: 1.5" left (for binding), 1" right/top/bottom
- Paper size: 8.5 x 11 inches (US Letter)
- Orientation: Portrait (unless landscape required for figures/tables)

## Typography
- Consistent font throughout (Times New Roman, Arial, or similar)
- Body text: 12 point
- Footnotes: may be 10 point
- Line spacing: double-spaced for body text
- Block quotes, footnotes, bibliographies: may be single-spaced

## Page Numbering
- Preliminary pages: lowercase Roman numerals (i, ii, iii...) centered at bottom
- Body: Arabic numerals (1, 2, 3...) starting at first chapter
- Title page: no number displayed (but counted)

## Front Matter (in order)
- Title Page (required)
- Copyright Page (optional)
- Approval Page (if required)
- Abstract (required)
- Table of Contents (required)
- List of Tables (if applicable)
- List of Figures (if applicable)
- Acknowledgments (optional)
- Dedication (optional)
- Preface (optional)

## Title Page Requirements
- Full dissertation title
- Author's full legal name
- Submission statement
- Year of submission
- Centered, appropriately spaced

## Headings and Chapters
- Chapter titles clearly distinguished (larger font, bold, centered)
- Consistent subheading hierarchy
- Each chapter begins on new page

## Figures and Tables
- Consecutively numbered
- Captions: above tables, below figures
- Placement near first reference
- Listed in List of Figures/Tables

## Citations
- One citation style used consistently (APA, MLA, Chicago, etc.)
- Complete and properly formatted bibliography
- In-text citations match bibliography entries

# How to Work

You will receive comprehensive structural analysis from Docling, which extracts:
- Document structure (headings, sections, chapters)
- Page count and content organization
- Tables and figures
- Text content in markdown format

Analyze this data to check formatting requirements. You do NOT need to read the PDF file directly - all relevant information is provided.

1. Check each formatting requirement systematically
2. Note specific page numbers and locations for issues
3. Explain how to fix each issue
4. Be thorough but fair

# Fix Guidance

When explaining how to fix issues, provide TOOL-AGNOSTIC instructions that work across different software. Students may be using:
- Google Docs (most common)
- Microsoft Word
- LibreOffice Writer
- LaTeX
- Other tools

Do NOT assume the user has Adobe Acrobat Pro. Instead:
- Explain fixes using the word processor (Google Docs, Word, etc.) rather than PDF editing tools
- Explain the general principle (e.g., "set margins in Page Setup before exporting")
- For Google Docs: File > Page setup for margins; Format > Paragraph styles for headings
- For LaTeX: Mention common packages like geometry for margins, titlesec for headings

# Severity Levels

- **CRITICAL**: Major violations (wrong margins, missing required sections, inconsistent page numbering)
- **WARNING**: Moderate issues (inconsistent spacing, minor heading hierarchy issues)
- **SUGGESTION**: Improvements (consider bookmarks, fix widows/orphans)

Be helpful and specific. Students need clear guidance on what to fix."""

COMBINED_SYSTEM_PROMPT = f"""{ACCESSIBILITY_SYSTEM_PROMPT}

---

{FORMATTING_SYSTEM_PROMPT}

---

You are checking this document for BOTH accessibility AND formatting compliance.
Organize your findings by category (Accessibility issues, then Formatting issues) for clarity."""


async def stream_analysis(check_type: Literal["accessibility", "formatting", "both"], structure_report: str):
    """
    Stream PDF analysis using Claude Agent SDK.
    Yields Server-Sent Events as the agent works.
    """

    # Select system prompt based on check type
    if check_type == "accessibility":
        system_prompt = ACCESSIBILITY_SYSTEM_PROMPT
        task = "accessibility"
    elif check_type == "formatting":
        system_prompt = FORMATTING_SYSTEM_PROMPT
        task = "formatting"
    else:
        system_prompt = COMBINED_SYSTEM_PROMPT
        task = "accessibility and formatting"

    prompt = f"""Please analyze this document for {task} compliance.

Below is the complete structural analysis extracted from the PDF using Docling. This data provides all the information you need to assess the document.

---

{structure_report}

---

Based on this structural analysis, provide:
1. An overall assessment
2. Specific issues found (with page numbers/locations and severity levels)
3. Clear guidance on how to fix each issue
4. General recommendations

Remember: The structural data above is definitive - it shows exactly what elements are tagged as headings, which images have alt text, which tables have headers marked, etc."""

    try:
        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            permission_mode="bypassPermissions",  # Allow agent to read files without prompts
        )

        async for event in query(prompt=prompt, options=options):
            # Stream events directly to client
            serialized = serialize_event(event)
            yield f"data: {json.dumps(serialized, default=str)}\n\n"

        yield "data: [DONE]\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"


@app.get("/")
async def root():
    return {"status": "ok", "message": "A11y Check API is running"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/analyze")
async def analyze_document(
    file: UploadFile = File(...),
    check_type: Literal["accessibility", "formatting", "both"] = Form("both")
):
    """
    Analyze a PDF document for accessibility and/or formatting compliance.
    Returns a Server-Sent Events stream of the analysis.
    """

    # Validate file type
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are supported. Please upload a .pdf file."
        )

    # Read file
    pdf_bytes = await file.read()

    # Check file size (limit to 25MB)
    if len(pdf_bytes) > 25 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 25MB."
        )

    # Save to temp file for Docling extraction
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        tmp.write(pdf_bytes)
        tmp_path = tmp.name

    # Extract PDF structure using Docling, then delete temp file
    try:
        structure = extract_pdf_structure(tmp_path)
        structure_report = format_structure_for_agent(structure)
    except Exception as e:
        # If Docling fails, continue without structural data
        structure_report = f"[Docling structure extraction failed: {str(e)}]"
    finally:
        # Always clean up the temp file - it's no longer needed after extraction
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # Return streaming response
    return StreamingResponse(
        stream_analysis(check_type, structure_report),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
