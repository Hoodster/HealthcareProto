"""
Context augmentor implementation for healthcare RAG.
"""

from typing import List, Optional
from retrieved_augmentation.abstract import (
    ContextAugmentor,
    RetrievalResult,
    RAGContext
)


class HealthcareContextAugmentor(ContextAugmentor):
    """Context augmentor optimized for healthcare queries."""
    
    def __init__(
        self,
        max_context_tokens: int = 2000,
        include_metadata: bool = True
    ):
        """
        Initialize the healthcare context augmentor.
        
        Args:
            max_context_tokens: Maximum number of tokens for context
            include_metadata: Whether to include metadata in formatted context
        """
        self.max_context_tokens = max_context_tokens
        self.include_metadata = include_metadata
    
    def augment(
        self,
        query: str,
        retrieved_results: List[RetrievalResult],
        max_tokens: Optional[int] = None
    ) -> RAGContext:
        """
        Augment a query with retrieved context.
        
        Args:
            query: The original query
            retrieved_results: Retrieved document chunks
            max_tokens: Maximum tokens to include in context
            
        Returns:
            RAG context with assembled information
        """
        max_tokens = max_tokens or self.max_context_tokens
        
        # Calculate approximate tokens (rough: 1 token ≈ 4 characters)
        total_chars = 0
        max_chars = max_tokens * 4
        
        filtered_results = []
        metadata_aggregated = {
            'sources': [],
            'doc_types': set(),
            'patient_ids': set()
        }
        
        for result in retrieved_results:
            chunk_chars = len(result.chunk.content)
            
            if total_chars + chunk_chars <= max_chars:
                filtered_results.append(result)
                total_chars += chunk_chars
                
                # Aggregate metadata
                if result.chunk.doc_id not in metadata_aggregated['sources']:
                    metadata_aggregated['sources'].append(result.chunk.doc_id)
                
                if 'doc_type' in result.chunk.metadata:
                    metadata_aggregated['doc_types'].add(
                        result.chunk.metadata['doc_type']
                    )
                
                if 'patient_id' in result.chunk.metadata:
                    metadata_aggregated['patient_ids'].add(
                        result.chunk.metadata['patient_id']
                    )
            else:
                # Try to compress and fit
                available_chars = max_chars - total_chars
                if available_chars > 100:  # Minimum useful chunk size
                    compressed = self.compress(
                        result.chunk.content,
                        available_chars // 4
                    )
                    if compressed:
                        # Create modified result
                        modified_chunk = result.chunk
                        modified_chunk.content = compressed
                        filtered_results.append(
                            RetrievalResult(
                                chunk=modified_chunk,
                                score=result.score,
                                rank=result.rank
                            )
                        )
                        total_chars += len(compressed)
                break
        
        # Convert sets to lists for JSON serialization
        metadata_aggregated['doc_types'] = list(metadata_aggregated['doc_types'])
        metadata_aggregated['patient_ids'] = list(metadata_aggregated['patient_ids'])
        
        return RAGContext(
            query=query,
            retrieved_chunks=filtered_results,
            metadata=metadata_aggregated,
            total_tokens=total_chars // 4
        )
    
    def format_context(self, rag_context: RAGContext) -> str:
        """
        Format the RAG context into a prompt-ready string.
        
        Args:
            rag_context: The RAG context to format
            
        Returns:
            Formatted context string
        """
        if not rag_context.retrieved_chunks:
            return ""
        
        context_parts = []
        
        # Add header
        context_parts.append("=== RETRIEVED CLINICAL CONTEXT ===\n")
        
        # Add metadata summary if enabled
        if self.include_metadata and rag_context.metadata:
            meta = rag_context.metadata
            context_parts.append("Sources:")
            if meta.get('doc_types'):
                context_parts.append(
                    f"  Document Types: {', '.join(meta['doc_types'])}"
                )
            if meta.get('patient_ids'):
                context_parts.append(
                    f"  Patient IDs: {', '.join(meta['patient_ids'])}"
                )
            context_parts.append(
                f"  Total Sources: {len(meta.get('sources', []))}\n"
            )
        
        # Add retrieved chunks
        for i, result in enumerate(rag_context.retrieved_chunks, 1):
            chunk = result.chunk
            context_parts.append(f"[Source {i}] (Relevance: {result.score:.3f})")
            
            # Add chunk metadata if available
            if self.include_metadata:
                chunk_meta = []
                if 'doc_type' in chunk.metadata:
                    chunk_meta.append(f"Type: {chunk.metadata['doc_type']}")
                if 'patient_id' in chunk.metadata:
                    chunk_meta.append(f"Patient: {chunk.metadata['patient_id']}")
                if chunk_meta:
                    context_parts.append(f"({', '.join(chunk_meta)})")
            
            context_parts.append(f"{chunk.content}\n")
        
        context_parts.append("=== END CLINICAL CONTEXT ===")
        
        return "\n".join(context_parts)
    
    def compress(self, text: str, max_tokens: int) -> str:
        """
        Compress text to fit within token limits.
        
        Uses simple truncation with sentence boundary awareness.
        
        Args:
            text: The text to compress
            max_tokens: Maximum number of tokens
            
        Returns:
            Compressed text
        """
        if not text:
            return ""
        
        # Approximate: 1 token ≈ 4 characters
        max_chars = max_tokens * 4
        
        if len(text) <= max_chars:
            return text
        
        # Try to break at sentence boundary
        truncated = text[:max_chars]
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        
        break_point = max(last_period, last_newline)
        
        if break_point > max_chars * 0.5:  # Don't cut too much
            return text[:break_point + 1].strip()
        else:
            return truncated.strip() + "..."
    
    def prioritize_by_recency(
        self,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """
        Re-prioritize results to favor more recent documents.
        
        Args:
            results: Original retrieval results
            
        Returns:
            Re-prioritized results
        """
        # Sort by score first, then by recency if available
        def sort_key(r: RetrievalResult):
            recency_bonus = 0
            if 'date' in r.chunk.metadata:
                # Implement date-based bonus
                pass
            return (-r.score, -recency_bonus)
        
        return sorted(results, key=sort_key)
