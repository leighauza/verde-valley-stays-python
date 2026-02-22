"""
RAG retrieval from Supabase using OpenAI embeddings.

Mirrors the n8n setup:
  - Embedding model : text-embedding-3-small (OpenAI)
  - Vector table    : guest_info
  - Match function  : match_documents (standard Supabase pgvector RPC)
"""

import logging

from openai import OpenAI
from supabase import create_client, Client
import config

logger = logging.getLogger(__name__)

_supabase: Client | None = None
_openai: OpenAI | None = None


def _get_supabase() -> Client:
    global _supabase
    if _supabase is None:
        _supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)
    return _supabase


def _get_openai() -> OpenAI:
    global _openai
    if _openai is None:
        _openai = OpenAI(api_key=config.OPENAI_API_KEY)
    return _openai


def search_knowledge_base(query: str, match_count: int = 5) -> str:
    """
    Embed the query with OpenAI, then run a vector similarity search
    against the guest_info table. Returns a formatted string of results
    ready to be passed back to the agent.
    """
    try:
        # 1. Embed the query
        openai = _get_openai()
        embedding_response = openai.embeddings.create(
            model=config.EMBEDDING_MODEL,
            input=query,
        )
        query_vector = embedding_response.data[0].embedding

        # 2. Run similarity search via Supabase RPC
        db = _get_supabase()
        result = db.rpc(
            "match_documents",
            {
                "query_embedding": query_vector,
                "match_count": match_count,
                "filter": {"table": "guest_info"},
            },
        ).execute()

        if not result.data:
            return "No relevant information found in the knowledge base."

        # 3. Format results for the agent
        chunks = [row.get("content", "") for row in result.data if row.get("content")]
        return "\n\n---\n\n".join(chunks)

    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        return "Unable to search the knowledge base right now."
