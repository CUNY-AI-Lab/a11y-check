"""
PDF Structure Extraction using Docling
Provides structural analysis data to enhance agent accessibility checking
"""

import json
import logging
from pathlib import Path
from typing import TypedDict, Optional
from docling.document_converter import DocumentConverter

logging.basicConfig(level=logging.WARNING)  # Reduce Docling noise
logger = logging.getLogger(__name__)


class StructureElement(TypedDict):
    type: str
    text: str
    level: int
    page: Optional[int]
    bbox: Optional[dict]


class PDFStructure(TypedDict):
    filename: str
    page_count: int
    headings: list[StructureElement]
    paragraphs: list[StructureElement]
    lists: list[StructureElement]
    tables: list[dict]
    images: list[dict]
    reading_order: list[str]
    markdown: str


# Singleton converter to avoid reinitializing models
_converter: Optional[DocumentConverter] = None


def get_converter() -> DocumentConverter:
    """Get or create the Docling converter (singleton)."""
    global _converter
    if _converter is None:
        logger.info("Initializing Docling converter...")
        _converter = DocumentConverter()
    return _converter


def extract_pdf_structure(pdf_path: str) -> PDFStructure:
    """
    Extract structural information from a PDF using Docling.

    Returns structured data about:
    - Headings (with hierarchy levels)
    - Paragraphs
    - Lists (with nesting)
    - Tables
    - Images
    - Reading order
    - Markdown representation
    """
    converter = get_converter()
    result = converter.convert(pdf_path)
    doc = result.document

    # Extract elements by type
    headings = []
    paragraphs = []
    lists = []
    reading_order = []

    for item, level in doc.iterate_items():
        item_type = type(item).__name__

        # Get text if available
        text = getattr(item, 'text', '') or ''

        # Get provenance (location) info
        prov = item.prov[0] if hasattr(item, 'prov') and item.prov else None
        page_no = prov.page_no if prov else None
        bbox = None
        if prov and hasattr(prov, 'bbox'):
            bbox = {
                'left': prov.bbox.l,
                'top': prov.bbox.t,
                'right': prov.bbox.r,
                'bottom': prov.bbox.b
            }

        element = StructureElement(
            type=item_type,
            text=text[:200] + '...' if len(text) > 200 else text,
            level=level,
            page=page_no,
            bbox=bbox
        )

        # Categorize by type
        if 'Header' in item_type or 'Title' in item_type:
            headings.append(element)
            reading_order.append(f"H{level}: {text[:50]}...")
        elif 'List' in item_type:
            lists.append(element)
            reading_order.append(f"LIST: {text[:50]}...")
        elif 'Text' in item_type:
            paragraphs.append(element)
            reading_order.append(f"P: {text[:50]}...")

    # Get tables
    doc_dict = doc.export_to_dict()
    tables = []
    for table in doc_dict.get('tables', []):
        tables.append({
            'num_rows': table.get('data', {}).get('num_rows', 0),
            'num_cols': table.get('data', {}).get('num_cols', 0),
            'has_header': bool(table.get('data', {}).get('table_cells', [])),
            'page': table.get('prov', [{}])[0].get('page_no')
        })

    # Get images/pictures
    images = []
    for pic in doc_dict.get('pictures', []):
        images.append({
            'page': pic.get('prov', [{}])[0].get('page_no'),
            'has_caption': bool(pic.get('caption')),
            'bbox': pic.get('prov', [{}])[0].get('bbox')
        })

    # Get page count
    page_count = len(doc_dict.get('pages', []))

    return PDFStructure(
        filename=Path(pdf_path).name,
        page_count=page_count,
        headings=headings,
        paragraphs=paragraphs,
        lists=lists,
        tables=tables,
        images=images,
        reading_order=reading_order,
        markdown=doc.export_to_markdown()
    )


def format_structure_for_agent(structure: PDFStructure) -> str:
    """
    Format the extracted structure as a prompt-friendly string
    for the agent to use in its analysis.
    """
    lines = [
        "# PDF STRUCTURAL ANALYSIS (via Docling)",
        "",
        f"**Filename:** {structure['filename']}",
        f"**Pages:** {structure['page_count']}",
        "",
        "## Document Structure Summary",
        "",
        f"- **Headings detected:** {len(structure['headings'])}",
        f"- **Paragraphs:** {len(structure['paragraphs'])}",
        f"- **List items:** {len(structure['lists'])}",
        f"- **Tables:** {len(structure['tables'])}",
        f"- **Images:** {len(structure['images'])}",
        "",
    ]

    # Heading hierarchy
    if structure['headings']:
        lines.append("## Heading Structure")
        lines.append("")
        for h in structure['headings']:
            indent = "  " * (h['level'] - 1)
            lines.append(f"{indent}- [{h['type']}] (level {h['level']}): \"{h['text']}\"")
        lines.append("")

    # Tables
    if structure['tables']:
        lines.append("## Tables")
        lines.append("")
        for i, t in enumerate(structure['tables'], 1):
            header_status = "has header row" if t['has_header'] else "NO HEADER ROW DETECTED"
            lines.append(f"- Table {i}: {t['num_rows']} rows x {t['num_cols']} cols, {header_status} (page {t['page']})")
        lines.append("")

    # Images
    if structure['images']:
        lines.append("## Images")
        lines.append("")
        for i, img in enumerate(structure['images'], 1):
            caption_status = "has caption" if img['has_caption'] else "NO CAPTION/ALT TEXT DETECTED"
            lines.append(f"- Image {i}: {caption_status} (page {img['page']})")
        lines.append("")

    # Reading order (expanded sample for better coverage)
    lines.append("## Reading Order (first 50 elements)")
    lines.append("")
    for i, elem in enumerate(structure['reading_order'][:50], 1):
        lines.append(f"{i}. {elem}")
    if len(structure['reading_order']) > 50:
        lines.append(f"... and {len(structure['reading_order']) - 50} more elements")
    lines.append("")

    # Document content (markdown) - include with smart truncation
    markdown = structure['markdown']
    MAX_CONTENT_CHARS = 15000  # ~4000 tokens, reasonable for context

    lines.append("## Document Content (Markdown)")
    lines.append("")
    if len(markdown) <= MAX_CONTENT_CHARS:
        lines.append(markdown)
    else:
        # For large documents, include beginning and note truncation
        lines.append(markdown[:MAX_CONTENT_CHARS])
        lines.append("")
        lines.append(f"... [Content truncated - showing first {MAX_CONTENT_CHARS:,} of {len(markdown):,} characters]")
        lines.append("*Note: The structural metadata above (headings, tables, images) covers the COMPLETE document.*")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test with sample PDF
    import sys
    pdf_path = sys.argv[1] if len(sys.argv) > 1 else "/mnt/c/Users/onepe/Downloads/Accessibility One Pager.pdf"

    print(f"Extracting structure from: {pdf_path}")
    structure = extract_pdf_structure(pdf_path)

    print("\n" + "="*60)
    print(format_structure_for_agent(structure))
