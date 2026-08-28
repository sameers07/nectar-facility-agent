"""Loads and chunks the facility knowledge base (knowledge/*.md).

Chunked by '## ' section rather than a fixed token window -- each document
is short and already organized into self-contained topics, so splitting on
its own structure gives cleaner, more coherent chunks than an arbitrary
character-count split would.
"""
import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def load_chunks() -> list:
    chunks = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text()
        for section in re.split(r"\n(?=## )", text):
            section = section.strip()
            if not section.startswith("## "):
                continue
            heading = section.splitlines()[0].lstrip("# ").strip()
            chunks.append({"source": path.stem, "heading": heading, "text": section})
    return chunks
