# RAG (Retrieval-Augmented Generation) System

This module provides a comprehensive RAG implementation for the healthcare application, with abstract base classes and concrete implementations for processing, embedding, storing, and retrieving clinical documents.

## Architecture

The RAG system is built on the following components:

```
┌─────────────────────────────────────────────────────────────┐
│                      RAG Pipeline                            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Document → Processor → Embedder → Vector Store             │
│                                         ↓                    │
│  Query → Embedder → Retriever → Augmentor → Context         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Core Abstracts

### 1. DocumentProcessor
Handles document cleaning, chunking, and metadata extraction.

**Strategies:**
- `FIXED_SIZE`: Fixed character/token chunks
- `SENTENCE`: Sentence-based chunking
- `PARAGRAPH`: Paragraph-based chunking
- `SLIDING_WINDOW`: Overlapping chunks for better context retention
- `SEMANTIC`: Smart chunking based on semantic boundaries

### 2. Embedder
Converts text into vector embeddings for semantic search.

**Implementations:**
- `OpenAIEmbedder`: Uses OpenAI's embedding models
  - `text-embedding-3-small`: 1536 dimensions, fast and cost-effective
  - `text-embedding-3-large`: 3072 dimensions, higher quality

### 3. VectorStore
Stores and retrieves document chunks using vector similarity.

**Features:**
- Add/update/delete chunks
- Similarity search with filters
- Metadata filtering (patient_id, doc_type, etc.)
- Statistics and monitoring

### 4. Retriever
Orchestrates the retrieval process.

**Features:**
- Semantic search using embeddings
- Reranking for improved relevance
- Filtering by metadata
- Configurable top-k results

### 5. ContextAugmentor
Assembles retrieved chunks into prompt-ready context.

**Features:**
- Token budget management
- Context compression
- Metadata aggregation
- Smart formatting for LLMs

### 6. RAGPipeline
Orchestrates the complete RAG workflow.

**Operations:**
- Index documents
- Execute queries
- Update/delete documents
- Full end-to-end RAG

## Data Models

### Document
```python
@dataclass
class Document:
    content: str
    metadata: Dict[str, Any]
    doc_id: Optional[str] = None
    doc_type: Optional[str] = None  # 'patient_record', 'knowledge_base', etc.
```

### DocumentChunk
```python
@dataclass
class DocumentChunk:
    content: str
    metadata: Dict[str, Any]
    chunk_id: str
    doc_id: str
    chunk_index: int
    embedding: Optional[List[float]] = None
```

### RetrievalResult
```python
@dataclass
class RetrievalResult:
    chunk: DocumentChunk
    score: float  # Similarity score (0-1)
    rank: int     # Result ranking
```

### RAGContext
```python
@dataclass
class RAGContext:
    query: str
    retrieved_chunks: List[RetrievalResult]
    metadata: Dict[str, Any]
    total_tokens: Optional[int] = None
```

## Usage Examples

### Basic Usage

```python
from retrieved_augumentation.embedder import OpenAIEmbedder
from retrieved_augumentation.document_processor import HealthcareDocumentProcessor
from retrieved_augumentation.augmentor import HealthcareContextAugmentor
from retrieved_augumentation.example_usage import (
    InMemoryVectorStore,
    SimpleRetriever,
    HealthcareRAGPipeline
)
from retrieved_augumentation.abstract import Document

# 1. Initialize components
embedder = OpenAIEmbedder(model="text-embedding-3-small")
processor = HealthcareDocumentProcessor(chunk_size=500, overlap=50)
vector_store = InMemoryVectorStore()
retriever = SimpleRetriever(embedder, vector_store)
augmentor = HealthcareContextAugmentor(max_context_tokens=2000)

# 2. Create pipeline
pipeline = HealthcareRAGPipeline(
    document_processor=processor,
    embedder=embedder,
    vector_store=vector_store,
    retriever=retriever,
    augmentor=augmentor
)

# 3. Index a document
doc = Document(
    content="Patient has history of hypertension and diabetes...",
    metadata={'patient_id': '12345', 'date': '2026-04-14'},
    doc_type='clinical_note'
)
doc_id = pipeline.index_document(doc)

# 4. Query
context, rag_context = pipeline.query(
    "What are the patient's chronic conditions?",
    top_k=5,
    return_context=True
)
print(context)
```

### With Metadata Filtering

```python
# Query with patient-specific filter
context, _ = pipeline.query(
    "Show recent lab results",
    top_k=3,
    filters={'patient_id': '12345', 'doc_type': 'lab_results'}
)
```

### Batch Document Indexing

```python
documents = [
    Document(content="...", metadata={...}),
    Document(content="...", metadata={...}),
    # ... more documents
]

for doc in documents:
    doc_id = pipeline.index_document(doc)
    print(f"Indexed: {doc_id}")
```

### Update Document

```python
updated_doc = Document(
    content="Updated patient information...",
    metadata={'patient_id': '12345'},
    doc_id=doc_id  # Same ID as original
)
pipeline.update_document(updated_doc)
```

## Implementation Guide

### Custom Vector Store

For production use, implement a persistent vector store:

```python
from retrieved_augumentation.abstract import VectorStore

class PostgresVectorStore(VectorStore):
    """Vector store using pgvector extension."""
    
    def __init__(self, connection_string: str):
        # Initialize database connection
        pass
    
    def add(self, chunks: List[DocumentChunk]) -> None:
        # INSERT INTO embeddings ...
        pass
    
    def search(self, query_embedding: List[float], top_k: int, filters) -> List[RetrievalResult]:
        # SELECT ... ORDER BY embedding <=> query_embedding LIMIT top_k
        pass
    
    # Implement other methods...
```

**Recommended vector databases:**
- **PostgreSQL + pgvector**: Good for existing PostgreSQL setups
- **Pinecone**: Managed, scalable, easy to use
- **Weaviate**: Open-source, feature-rich
- **Qdrant**: Fast, open-source, Python-friendly
- **Milvus**: Highly scalable, production-ready

### Custom Retriever

Implement advanced retrieval strategies:

```python
from retrieved_augumentation.abstract import Retriever

class HybridRetriever(Retriever):
    """Combines dense (embedding) and sparse (keyword) retrieval."""
    
    def retrieve(self, query: str, top_k: int, filters) -> List[RetrievalResult]:
        # 1. Dense retrieval (embeddings)
        dense_results = self.vector_store.search(...)
        
        # 2. Sparse retrieval (BM25, TF-IDF)
        sparse_results = self.keyword_search(query)
        
        # 3. Combine and rerank
        combined = self.hybrid_fusion(dense_results, sparse_results)
        return combined[:top_k]
```

## Healthcare-Specific Features

### Clinical Document Processing

The `HealthcareDocumentProcessor` includes:
- Medical terminology preservation
- Patient ID and MRN extraction
- Clinical notation support (vital signs, medications, etc.)
- HIPAA-compliant metadata handling

### Context Augmentation

The `HealthcareContextAugmentor` provides:
- Clinical context formatting
- Patient privacy considerations
- Relevance scoring for medical content
- Token budget management for long contexts

## Integration with Existing Services

### With AIModelService

```python
from api.services.ai_service import AIModelService

# After RAG retrieval
context, rag_context = pipeline.query("What medications is the patient on?")

# Use context with AI model
ai_service = AIModelService()
response = ai_service.chat(
    f"{context}\n\nBased on the above context, answer: {query}"
)
```

### With Document Service

```python
from api.services.document_service import upload

# Upload and index
doc_id = pipeline.index_document(document)
upload(
    file_name=f"patient/{patient_id}/record.txt",
    file_path=local_path,
    document_type='patient_file'
)
```

## Performance Considerations

### Embedding Costs
- `text-embedding-3-small`: ~$0.02 per 1M tokens
- `text-embedding-3-large`: ~$0.13 per 1M tokens
- Batch embeddings when possible to reduce API calls

### Chunking Strategy
- **Small chunks (200-300 tokens)**: Better precision, more chunks to store
- **Large chunks (800-1000 tokens)**: Better context, fewer chunks
- **Recommended for medical**: 400-600 tokens with 50-100 token overlap

### Retrieval Performance
- Use metadata filters to reduce search space
- Cache embeddings for frequently queried content
- Consider approximate nearest neighbor (ANN) for large datasets

## Testing

Run the example usage:

```bash
python -m retrieved_augumentation.example_usage
```

## Future Enhancements

- [ ] Add support for multi-modal RAG (images, PDFs)
- [ ] Implement hybrid search (dense + sparse)
- [ ] Add cross-encoder reranking
- [ ] Support for streaming responses
- [ ] Integration with knowledge graphs
- [ ] Privacy-preserving retrieval for PHI
- [ ] Evaluation metrics (precision, recall, MRR)

## References

- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [RAG Best Practices](https://www.pinecone.io/learn/retrieval-augmented-generation/)
- [Healthcare NLP](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC6371361/)
