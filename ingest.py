#!/usr/bin/env python3
"""
scripts/ingest.py
─────────────────
One-time (or on-demand) script to:
  1. Load all PDF files from data/pdfs/
  2. Split them into overlapping text chunks
  3. Embed each chunk with OpenAI embeddings
  4. Save a FAISS vector store to data/vector_store/

Run this before starting the Flask app.

Usage:
    python scripts/ingest.py
    python scripts/ingest.py --pdf-dir path/to/pdfs --out data/vector_store
"""

import argparse
import os
import sys
import time

from tqdm import tqdm

# ── Allow importing from project root ──────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings

from app.config import Config
from app.logger import logger


def load_pdfs(pdf_dir: str) -> list:
    """Recursively load all PDF files from a directory."""
    pdf_files = []
    for root, _, files in os.walk(pdf_dir):
        for fname in files:
            if fname.lower().endswith(".pdf"):
                pdf_files.append(os.path.join(root, fname))

    if not pdf_files:
        logger.error("No PDF files found in '%s'.", pdf_dir)
        sys.exit(1)

    logger.info("Found %d PDF file(s).", len(pdf_files))

    all_docs = []
    for pdf_path in tqdm(pdf_files, desc="Loading PDFs"):
        try:
            loader = PyPDFLoader(pdf_path)
            docs = loader.load()
            # Attach filename as metadata for source attribution
            for doc in docs:
                doc.metadata["source"] = os.path.basename(pdf_path)
            all_docs.extend(docs)
            logger.info("  Loaded %d pages from '%s'.", len(docs), pdf_path)
        except Exception as exc:
            logger.warning("  Skipping '%s' — %s", pdf_path, exc)

    return all_docs


def split_documents(docs: list, chunk_size: int, chunk_overlap: int) -> list:
    """Split raw document pages into smaller, overlapping chunks."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        # Prefer splitting on paragraph → sentence → word boundaries
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(docs)
    logger.info("Split %d pages → %d chunks.", len(docs), len(chunks))
    return chunks


def build_vector_store(chunks: list, output_path: str) -> None:
    """Embed chunks and save FAISS index to disk."""
    logger.info("Building embeddings (model=%s) …", Config.OPENAI_EMBEDDING_MODEL)

    embeddings = OpenAIEmbeddings(
        model=Config.OPENAI_EMBEDDING_MODEL,
        openai_api_key=Config.OPENAI_API_KEY,
    )

    t0 = time.perf_counter()
    vector_store = FAISS.from_documents(chunks, embeddings)
    elapsed = round(time.perf_counter() - t0, 1)
    logger.info("Embedded %d chunks in %.1fs.", len(chunks), elapsed)

    os.makedirs(output_path, exist_ok=True)
    vector_store.save_local(output_path)
    logger.info("FAISS index saved to '%s'.", output_path)


def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs into the vector store.")
    parser.add_argument(
        "--pdf-dir",
        default="data/pdfs",
        help="Directory containing medical PDF files (default: data/pdfs)",
    )
    parser.add_argument(
        "--out",
        default=Config.VECTOR_STORE_PATH,
        help=f"Output path for FAISS index (default: {Config.VECTOR_STORE_PATH})",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=Config.CHUNK_SIZE,
        help=f"Characters per chunk (default: {Config.CHUNK_SIZE})",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=Config.CHUNK_OVERLAP,
        help=f"Overlap between chunks (default: {Config.CHUNK_OVERLAP})",
    )
    args = parser.parse_args()

    logger.info("=== Medical Chatbot — PDF Ingestion ===")
    docs = load_pdfs(args.pdf_dir)
    chunks = split_documents(docs, args.chunk_size, args.chunk_overlap)
    build_vector_store(chunks, args.out)
    logger.info("=== Ingestion complete. You can now start the Flask app. ===")


if __name__ == "__main__":
    main()
