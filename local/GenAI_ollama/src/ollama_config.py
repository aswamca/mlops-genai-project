"""Shared configuration and helpers for the local Ollama examples."""

from __future__ import annotations

import os
from collections.abc import Sequence


OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.2:1b")
OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")


def get_chat_model(*, temperature: float = 0.0):
	"""Return a LangChain chat model configured for the local Ollama server."""
	from langchain_ollama import ChatOllama

	return ChatOllama(
		model=OLLAMA_CHAT_MODEL,
		base_url=OLLAMA_BASE_URL,
		temperature=temperature,
	)


def get_embeddings():
	"""Return the local Ollama embedding model used by the RAG example."""
	from langchain_ollama import OllamaEmbeddings

	return OllamaEmbeddings(
		model=OLLAMA_EMBEDDING_MODEL,
		base_url=OLLAMA_BASE_URL,
	)


def messages_to_text(messages: Sequence[object]) -> str:
	"""Convert LangChain message objects into readable conversation text."""
	lines = []
	for message in messages:
		role = getattr(message, "type", "message")
		content = getattr(message, "content", str(message))
		lines.append(f"{role}: {content}")
	return "\n".join(lines)
