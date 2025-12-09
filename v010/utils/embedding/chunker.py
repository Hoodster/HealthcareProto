"""Utility functions for splitting long documents into overlapping chunks.

Chunking strategy:
 - Fixed token/character window (approx via character length)
 - Overlap to preserve context continuity
Output schema per chunk:
 {"id": <int>, "chunk": <str>, "start": <int>, "end": <int>}
"""

from typing import List


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[dict]:
	if chunk_size <= 0:
		raise ValueError("chunk_size must be > 0")
	if overlap >= chunk_size:
		overlap = max(0, chunk_size // 4)  # clamp to a sensible smaller value

	chunks: List[dict] = []
	start = 0
	idx = 0
	length = len(text)
	while start < length:
		end = min(length, start + chunk_size)
		segment = text[start:end]
		chunks.append({"id": idx, "chunk": segment, "start": start, "end": end})
		idx += 1
		if end == length:
			break
		start = end - overlap  # overlap backwards
	return chunks

