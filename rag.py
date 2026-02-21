"""
app/rag.py
──────────
Builds the LangChain RAG (Retrieval-Augmented Generation) chain.

Flow:
  User query → Embed → Retrieve top-K docs from vector store
            → Stuff into prompt → LLM → Answer

Supports both FAISS (local) and Pinecone (cloud).
"""

import os
from functools import lru_cache

from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import Config
from app.logger import logger

# ── System prompt that enforces safe medical responses ────────────────────────
SYSTEM_PROMPT = """You are MedAssist, an AI assistant specialised in medical \
information. Your knowledge comes exclusively from a curated medical document \
library that has been retrieved for you.

RULES YOU MUST ALWAYS FOLLOW:
1. Base every answer solely on the provided context documents.
2. If the answer is not in the context, say "I don't have enough information \
in my knowledge base to answer that reliably" — never fabricate facts.
3. Never recommend specific dosages, prescriptions, or diagnoses.
4. Always remind the user to consult a licensed healthcare professional for \
personal medical decisions.
5. Use plain, non-technical language unless the user is clearly a professional.
6. Be concise, structured, and factual.
7. If a question is outside medical topics, politely redirect.

Context documents:
──────────────────
{context}
──────────────────
"""

HUMAN_PROMPT = """{question}"""


def _build_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages(
        [
            SystemMessagePromptTemplate.from_template(SYSTEM_PROMPT),
            HumanMessagePromptTemplate.from_template(HUMAN_PROMPT),
        ]
    )


def _load_faiss_store(embeddings: OpenAIEmbeddings) -> FAISS:
    """Load a pre-built FAISS index from disk."""
    path = Config.VECTOR_STORE_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Vector store not found at '{path}'. "
            "Run `python scripts/ingest.py` first to build it."
        )
    logger.info("Loading FAISS vector store from '%s'", path)
    return FAISS.load_local(path, embeddings, allow_dangerous_deserialization=True)


def _load_pinecone_store(embeddings: OpenAIEmbeddings):
    """Load an existing Pinecone index (requires pinecone-client installed)."""
    try:
        from langchain_community.vectorstores import Pinecone as PineconeVS
        import pinecone  # type: ignore

        pinecone.init(api_key=Config.PINECONE_API_KEY, environment=Config.PINECONE_ENV)
        logger.info("Connecting to Pinecone index '%s'", Config.PINECONE_INDEX)
        return PineconeVS.from_existing_index(Config.PINECONE_INDEX, embeddings)
    except ImportError as exc:
        raise ImportError(
            "pinecone-client is not installed. "
            "Run: pip install pinecone-client"
        ) from exc


@lru_cache(maxsize=1)
def get_rag_chain() -> ConversationalRetrievalChain:
    """
    Build and cache the RAG chain.
    Called once at app startup; subsequent calls return the cached instance.
    """
    logger.info("Initialising RAG chain (model=%s)", Config.OPENAI_MODEL)

    embeddings = OpenAIEmbeddings(
        model=Config.OPENAI_EMBEDDING_MODEL,
        openai_api_key=Config.OPENAI_API_KEY,
    )

    # ── Choose vector store ────────────────────────────────────────────────────
    if Config.USE_PINECONE:
        vector_store = _load_pinecone_store(embeddings)
    else:
        vector_store = _load_faiss_store(embeddings)

    retriever = vector_store.as_retriever(
        search_type="similarity",
        search_kwargs={"k": Config.RETRIEVER_TOP_K},
    )

    llm = ChatOpenAI(
        model=Config.OPENAI_MODEL,
        temperature=0.2,          # low temperature → more factual
        openai_api_key=Config.OPENAI_API_KEY,
        request_timeout=30,
        max_retries=2,
    )

    # Keep a rolling window of the last 6 exchanges for multi-turn context
    memory = ConversationBufferWindowMemory(
        k=6,
        memory_key="chat_history",
        return_messages=True,
        output_key="answer",
    )

    chain = ConversationalRetrievalChain.from_llm(
        llm=llm,
        retriever=retriever,
        memory=memory,
        combine_docs_chain_kwargs={"prompt": _build_prompt()},
        return_source_documents=True,
        verbose=False,
    )

    logger.info("RAG chain ready.")
    return chain


def query_rag(question: str) -> dict:
    """
    Run a user question through the RAG chain.

    Returns a dict with:
        answer        (str)  — LLM answer
        sources       (list) — list of source document metadata dicts
    """
    chain = get_rag_chain()
    try:
        result = chain.invoke({"question": question})
    except Exception as exc:
        logger.error("RAG chain error: %s", exc, exc_info=True)
        raise

    sources = [
        {
            "source": doc.metadata.get("source", "unknown"),
            "page": doc.metadata.get("page", "—"),
        }
        for doc in result.get("source_documents", [])
    ]

    return {
        "answer": result["answer"],
        "sources": sources,
    }
