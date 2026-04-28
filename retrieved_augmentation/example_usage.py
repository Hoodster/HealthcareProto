"""
Example usage of the RAG abstracts for healthcare application.

This demonstrates how to implement and use a complete RAG pipeline.
"""

from typing import List, Dict, Any, Optional, Tuple
from retrieved_augmentation.abstract import (
    Document,
    DocumentChunk,
    Embedder,
    VectorStore,
    Retriever,
    ContextAugmentor,
    RAGPipeline,
    RetrievalResult,
    RAGContext,
    DocumentProcessor
)
from retrieved_augmentation.embedder import OpenAIEmbedder
from retrieved_augmentation.document_processor import HealthcareDocumentProcessor
from retrieved_augmentation.augmentor import HealthcareContextAugmentor


# Example: Simple in-memory vector store implementation
class InMemoryVectorStore(VectorStore):
    """Simple in-memory vector store for demonstration."""
    
    def __init__(self):
        self.chunks: Dict[str, DocumentChunk] = {}
        self.doc_chunks: Dict[str, List[str]] = {}  # doc_id -> chunk_ids
    
    def add(self, chunks: List[DocumentChunk]) -> None:
        for chunk in chunks:
            self.chunks[chunk.chunk_id] = chunk
            
            if chunk.doc_id not in self.doc_chunks:
                self.doc_chunks[chunk.doc_id] = []
            self.doc_chunks[chunk.doc_id].append(chunk.chunk_id)
    
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        """Cosine similarity search."""
        results = []
        
        for chunk_id, chunk in self.chunks.items():
            if not chunk.embedding:
                continue
            
            # Apply filters
            if filters:
                if not self._matches_filters(chunk, filters):
                    continue
            
            # Calculate cosine similarity
            score = self._cosine_similarity(query_embedding, chunk.embedding)
            results.append(RetrievalResult(chunk=chunk, score=score, rank=0))
        
        # Sort by score and assign ranks
        results.sort(key=lambda x: x.score, reverse=True)
        for i, result in enumerate(results[:top_k]):
            result.rank = i + 1
        
        return results[:top_k]
    
    def delete(self, doc_id: str) -> None:
        if doc_id in self.doc_chunks:
            chunk_ids = self.doc_chunks[doc_id]
            for chunk_id in chunk_ids:
                del self.chunks[chunk_id]
            del self.doc_chunks[doc_id]
    
    def update(self, chunk: DocumentChunk) -> None:
        self.chunks[chunk.chunk_id] = chunk
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            'total_chunks': len(self.chunks),
            'total_documents': len(self.doc_chunks)
        }
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a * a for a in vec1) ** 0.5
        magnitude2 = sum(b * b for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def _matches_filters(self, chunk: DocumentChunk, filters: Dict[str, Any]) -> bool:
        """Check if chunk matches all filters."""
        for key, value in filters.items():
            if key not in chunk.metadata:
                return False
            if chunk.metadata[key] != value:
                return False
        return True


# Example: Simple retriever implementation
class SimpleRetriever(Retriever):
    """Simple retriever using embedding-based search."""
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[RetrievalResult]:
        # Embed the query
        query_embedding = self.embedder.embed(query)
        
        # Search vector store
        results = self.vector_store.search(query_embedding, top_k, filters)
        
        return results
    
    def rerank(
        self,
        query: str,
        results: List[RetrievalResult]
    ) -> List[RetrievalResult]:
        """Simple reranking based on keyword matching."""
        query_terms = set(query.lower().split())
        
        for result in results:
            chunk_terms = set(result.chunk.content.lower().split())
            keyword_overlap = len(query_terms & chunk_terms) / len(query_terms)
            
            # Boost score based on keyword overlap
            result.score = result.score * 0.7 + keyword_overlap * 0.3
        
        # Re-sort and update ranks
        results.sort(key=lambda x: x.score, reverse=True)
        for i, result in enumerate(results):
            result.rank = i + 1
        
        return results


# Example: Complete RAG pipeline implementation
class HealthcareRAGPipeline(RAGPipeline):
    """Complete RAG pipeline for healthcare documents."""
    
    def index_document(self, document: Document) -> str:
        """Index a document into the RAG system."""
        # Process document into chunks
        chunks = self.document_processor.process(document)
        
        # Generate embeddings for chunks
        texts = [chunk.content for chunk in chunks]
        embeddings = self.embedder.embed_batch(texts)
        
        # Attach embeddings to chunks
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding
        
        # Add to vector store
        self.vector_store.add(chunks)
        
        return chunks[0].doc_id if chunks else ""
    
    def query(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        return_context: bool = False
    ) -> Tuple[str, Optional[RAGContext]]:
        """Execute a complete RAG query."""
        # Retrieve relevant chunks
        results = self.retriever.retrieve(query, top_k, filters)
        
        # Optionally rerank
        results = self.retriever.rerank(query, results)
        
        # Augment with context
        rag_context = self.augmentor.augment(query, results)
        
        # Format context
        formatted_context = self.augmentor.format_context(rag_context)
        
        if return_context:
            return formatted_context, rag_context
        else:
            return formatted_context, None
    
    def update_document(self, document: Document) -> None:
        """Update an existing document in the index."""
        # Delete old version
        if document.doc_id:
            self.delete_document(document.doc_id)
        
        # Index new version
        self.index_document(document)
    
    def delete_document(self, doc_id: str) -> None:
        """Delete a document from the index."""
        self.vector_store.delete(doc_id)


# Example usage
def example_usage():
    """Demonstrate how to use the RAG pipeline."""
    
    # 1. Initialize components
    embedder = OpenAIEmbedder(model="text-embedding-3-small")
    document_processor = HealthcareDocumentProcessor(
        default_chunk_size=500,
        default_overlap=50
    )
    vector_store = InMemoryVectorStore()
    retriever = SimpleRetriever(embedder, vector_store)
    augmentor = HealthcareContextAugmentor(max_context_tokens=2000)
    
    # 2. Create RAG pipeline
    rag_pipeline = HealthcareRAGPipeline(
        document_processor=document_processor,
        embedder=embedder,
        vector_store=vector_store,
        retriever=retriever,
        augmentor=augmentor
    )
    
    # 3. Index documents
    sample_document = Document(
        content="""
        Patient: John Doe, Age: 65, MRN: 123456
        
        Chief Complaint: Chest pain and shortness of breath
        
        History of Present Illness:
        Patient presents with substernal chest pain radiating to left arm.
        Pain started 2 hours ago while at rest. Associated with diaphoresis
        and nausea. Patient has history of hypertension and hyperlipidemia.
        
        Current Medications:
        - Lisinopril 10mg daily
        - Atorvastatin 40mg daily
        - Aspirin 81mg daily
        
        Assessment:
        Acute coronary syndrome, rule out myocardial infarction.
        QTc: 450ms, eGFR: 75 mL/min/1.73m²
        
        Plan:
        1. Serial troponins
        2. ECG monitoring
        3. Cardiology consultation
        """,
        metadata={
            'patient_id': '123456',
            'date': '2026-04-14',
            'provider': 'Dr. Smith'
        },
        doc_type='clinical_note'
    )
    
    doc_id = rag_pipeline.index_document(sample_document)
    print(f"Indexed document: {doc_id}")
    
    # 4. Query the RAG system
    query = "What are the patient's cardiac risk factors?"
    context, rag_context = rag_pipeline.query(
        query,
        top_k=3,
        return_context=True
    )
    
    print(f"\nQuery: {query}")
    print(f"\nRetrieved Context:\n{context}")
    
    if rag_context:
        print(f"\nMetadata: {rag_context.metadata}")
        print(f"Total tokens: {rag_context.total_tokens}")
    
    # 5. Get stats
    stats = vector_store.get_stats()
    print(f"\nVector Store Stats: {stats}")


if __name__ == "__main__":
    example_usage()
