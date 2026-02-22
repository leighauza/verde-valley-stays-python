"""
Document ingestion script.

Replaces the n8n Google Drive Trigger → Download → Chunk → Embed → Supabase pipeline.
Run this manually whenever you want to add or update documents in the knowledge base.

Usage:
    # Ingest a single file
    python ingestion/ingest.py path/to/document.pdf

    # Ingest all PDFs in a folder
    python ingestion/ingest.py path/to/folder/

    # Remove a document from the knowledge base by filename
    python ingestion/ingest.py --delete "Verde_Valley_Complete_Guest_Guide.pdf"
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Make sure project root is on the path when running this script directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import OpenAI
from supabase import create_client, Client
import fitz  # PyMuPDF

import config

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

CHUNK_SIZE = 250        # characters — matches n8n setting
CHUNK_OVERLAP = 30      # characters — matches n8n setting
TABLE_NAME = "guest_info"

# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

def _get_supabase() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)


def _get_openai() -> OpenAI:
    return OpenAI(api_key=config.OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: Path) -> str:
    """Extract all text from a PDF file using PyMuPDF."""
    doc = fitz.open(str(file_path))
    pages = [page.get_text() for page in doc]
    doc.close()
    return "\n".join(pages)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks.
    Mirrors n8n's Recursive Character Text Splitter settings.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------

def embed_chunks(chunks: list[str], openai: OpenAI) -> list[list[float]]:
    """Embed a list of text chunks using OpenAI."""
    logger.info(f"Embedding {len(chunks)} chunks...")
    response = openai.embeddings.create(
        model=config.EMBEDDING_MODEL,
        input=chunks,
    )
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# Supabase upsert
# ---------------------------------------------------------------------------

def upsert_chunks(
    chunks: list[str],
    embeddings: list[list[float]],
    file_name: str,
    db: Client,
) -> None:
    """Insert embedded chunks into the Supabase vector table."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()

    rows = [
        {
            "content": chunk,
            "embedding": embedding,
            "metadata": {"fileName": file_name, "date": now},
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]

    logger.info(f"Inserting {len(rows)} rows into '{TABLE_NAME}'...")
    # Insert in batches of 100 to stay within Supabase limits
    batch_size = 100
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        db.table(TABLE_NAME).insert(batch).execute()

    logger.info(f"Done — {len(rows)} chunks stored for '{file_name}'.")


def delete_document(file_name: str, db: Client) -> None:
    """Remove all chunks for a given file from the vector table."""
    logger.info(f"Deleting all chunks for '{file_name}' from '{TABLE_NAME}'...")
    db.table(TABLE_NAME).delete().like("metadata->>fileName", f"%{file_name}%").execute()
    logger.info("Deletion complete.")


# ---------------------------------------------------------------------------
# Main ingestion flow
# ---------------------------------------------------------------------------

def ingest_file(file_path: Path) -> None:
    config.validate()
    db = _get_supabase()
    openai = _get_openai()

    logger.info(f"Ingesting: {file_path.name}")
    text = extract_text_from_pdf(file_path)
    if not text.strip():
        logger.warning(f"No text extracted from {file_path.name}. Skipping.")
        return

    chunks = chunk_text(text)
    logger.info(f"Split into {len(chunks)} chunks.")

    embeddings = embed_chunks(chunks, openai)
    upsert_chunks(chunks, embeddings, file_path.name, db)


def ingest_folder(folder_path: Path) -> None:
    pdfs = list(folder_path.glob("*.pdf"))
    if not pdfs:
        logger.warning(f"No PDF files found in {folder_path}")
        return
    for pdf in pdfs:
        ingest_file(pdf)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest documents into Verde Valley knowledge base")
    parser.add_argument("path", nargs="?", help="Path to a PDF file or folder of PDFs")
    parser.add_argument("--delete", metavar="FILENAME", help="Delete a document from the knowledge base by filename")
    args = parser.parse_args()

    config.validate()

    if args.delete:
        db = _get_supabase()
        delete_document(args.delete, db)

    elif args.path:
        target = Path(args.path)
        if target.is_dir():
            ingest_folder(target)
        elif target.is_file() and target.suffix.lower() == ".pdf":
            ingest_file(target)
        else:
            logger.error(f"'{target}' is not a valid PDF file or directory.")
            sys.exit(1)

    else:
        parser.print_help()
