"""Privacy and redaction helpers for local RAG workloads."""

from __future__ import annotations

import re


def redact_sensitive_text(text: str) -> str:
    """Mask common sensitive values before indexing or sending text to the model."""
    if not text:
        return text

    masked = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[EMAIL]",
        text,
        flags=re.IGNORECASE,
    )
    masked = re.sub(r"\b(?:\+?\d[\d\s()-]{8,}\d)\b", "[PHONE]", masked)
    masked = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]", masked)
    masked = re.sub(r"\b(?:AKIA|ASIA)[A-Z0-9]{12,}\b", "[ACCESS_KEY]", masked)
    masked = re.sub(
        r"\b(?:(?:sk|AIza|ghp|github_pat|xox[baprs]-)[A-Za-z0-9_\-]{10,})\b",
        "[SECRET]",
        masked,
    )
    return masked


def build_source_of_truth_map(text: str) -> dict[str, str]:
    """Map masked placeholders to the original sensitive values for authorized lookups."""
    source_map: dict[str, str] = {}
    patterns = [
        (r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[EMAIL]"),
        (r"\b(?:\+?\d[\d\s()-]{8,}\d)\b", "[PHONE]"),
        (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN]"),
    ]
    for regex, placeholder in patterns:
        for match in re.finditer(regex, text, flags=re.IGNORECASE):
            source_map[placeholder] = match.group(0)
    return source_map


def authorize_source_truth(context: str, source_of_truth: dict[str, str] | None, *, allow_real_values: bool) -> str:
    """Resolve masked placeholders to the original values only when explicitly authorized."""
    if not allow_real_values or not source_of_truth:
        return redact_sensitive_text(context)

    resolved = context
    for placeholder, real_value in source_of_truth.items():
        resolved = resolved.replace(placeholder, real_value)
    return resolved


def sanitize_output_for_user(text: str) -> str:
    """Redact sensitive values before returning model output to the user."""
    return redact_sensitive_text(text)


def filter_documents_for_user(documents: list[object], *, allowed_tags: set[str] | None = None) -> list[object]:
    """Filter documents by metadata tags when a user-scoped retrieval policy is in use."""
    if not allowed_tags:
        return documents

    filtered_documents = []
    for document in documents:
        metadata = getattr(document, "metadata", {}) or {}
        tags = set(metadata.get("tags", []))
        if not tags:
            filtered_documents.append(document)
            continue
        if tags & allowed_tags:
            filtered_documents.append(document)
    return filtered_documents


def redact_documents(documents: list[object]) -> list[object]:
    """Return a copy of documents with sensitive values redacted in their content."""
    redacted_documents = []
    for document in documents:
        page_content = getattr(document, "page_content", str(document))
        sanitized = redact_sensitive_text(page_content)
        if hasattr(document, "page_content"):
            document.page_content = sanitized
            redacted_documents.append(document)
        else:
            redacted_documents.append(sanitized)
    return redacted_documents
