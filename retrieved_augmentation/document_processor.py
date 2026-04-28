"""
Document processor implementation for healthcare documents.
"""

import re
from typing import Dict, List, Any
from uuid import uuid4

from retrieved_augmentation.abstract import (
    Document,
    DocumentChunk,
    DocumentProcessor,
    ChunkingStrategy
)


class HealthcareDocumentProcessor(DocumentProcessor):
    """Document processor optimized for healthcare/clinical documents."""
    
    def __init__(
        self,
        default_chunk_size: int = 500,
        default_overlap: int = 50
    ):
        """
        Initialize the healthcare document processor.
        
        Args:
            default_chunk_size: Default chunk size in characters
            default_overlap: Default overlap between chunks in characters
        """
        self.default_chunk_size = default_chunk_size
        self.default_overlap = default_overlap
    
    def process(self, document: Document) -> List[DocumentChunk]:
        """
        Process a document and split it into chunks.
        
        Args:
            document: The document to process
            
        Returns:
            List of document chunks
        """
        # Clean the document text
        cleaned_text = self.clean(document.content)
        
        # Extract metadata
        metadata = self.extract_metadata(document)
        
        # Chunk the text
        text_chunks = self.chunk(
            cleaned_text,
            strategy=ChunkingStrategy.SLIDING_WINDOW,
            chunk_size=self.default_chunk_size,
            overlap=self.default_overlap
        )
        
        # Create DocumentChunk objects
        doc_id = document.doc_id or str(uuid4())
        chunks = []
        
        for idx, chunk_text in enumerate(text_chunks):
            chunk = DocumentChunk(
                content=chunk_text,
                metadata={**metadata, **document.metadata},
                chunk_id=f"{doc_id}_chunk_{idx}",
                doc_id=doc_id,
                chunk_index=idx
            )
            chunks.append(chunk)
        
        return chunks
    
    def chunk(
        self,
        text: str,
        strategy: ChunkingStrategy = ChunkingStrategy.PARAGRAPH,
        chunk_size: int = 500,
        overlap: int = 50
    ) -> List[str]:
        """
        Chunk text using the specified strategy.
        
        Args:
            text: The text to chunk
            strategy: The chunking strategy to use
            chunk_size: Target size for each chunk (characters)
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of text chunks
        """
        if not text:
            return []
        
        if strategy == ChunkingStrategy.SENTENCE:
            return self._chunk_by_sentence(text, chunk_size)
        elif strategy == ChunkingStrategy.SLIDING_WINDOW:
            return self._chunk_sliding_window(text, chunk_size, overlap)
        else:
            return self._chunk_by_paragraph(text, chunk_size)
    def clean(self, text: str) -> str:
        """
        Clean and normalize text for healthcare documents.
        
        Args:
            text: The text to clean
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters but keep medical notation
        # Keep: numbers, letters, common punctuation, medical symbols
        text = re.sub(r'[^\w\s.,;:()\-/\[\]<>%°+=]', '', text)
        
        # Normalize line breaks
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove multiple consecutive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        return text.strip()
    
    def extract_metadata(self, document: Document) -> Dict[str, Any]:
        """
        Extract metadata from a healthcare document.
        
        Args:
            document: The document to extract metadata from
            
        Returns:
            Dictionary of metadata
        """
        metadata = {
            'doc_type': document.doc_type or 'unknown',
            'length': len(document.content),
            'word_count': len(document.content.split()),
        }
        
        # Attempt to extract patient ID from content if not in metadata
        if 'patient_id' not in document.metadata:
            patient_id_match = re.search(
                r'Patient\s+ID[:\s]+(\w+)',
                document.content,
                re.IGNORECASE
            )
            if patient_id_match:
                metadata['patient_id'] = patient_id_match.group(1)
        
        # Attempt to extract MRN (Medical Record Number)
        mrn_match = re.search(
            r'MRN[:\s]+(\w+)',
            document.content,
            re.IGNORECASE
        )
        if mrn_match:
            metadata['mrn'] = mrn_match.group(1)
        
        return metadata
    
    def _chunk_fixed_size(self, text: str, chunk_size: int) -> List[str]:
        """Chunk text into fixed-size pieces."""
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunks.append(text[i:i + chunk_size])
        return chunks
    
    def _chunk_sliding_window(
        self,
        text: str,
        chunk_size: int,
        overlap: int
    ) -> List[str]:
        """Chunk text using sliding window with overlap."""
        chunks = []
        start = 0
        text_length = len(text)
        
        while start < text_length:
            end = min(start + chunk_size, text_length)
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < text_length:
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > chunk_size * 0.5:  # Don't break too early
                    end = start + break_point + 1
                    chunk = text[start:end]
            
            chunks.append(chunk.strip())
            start = end - overlap if end < text_length else text_length
        
        return [c for c in chunks if c]  # Remove empty chunks
    
    def _chunk_by_sentence(self, text: str, max_chunk_size: int) -> List[str]:
        """Chunk text by sentences, combining until max size."""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_chunk_size:
                current_chunk += (" " if current_chunk else "") + sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _chunk_by_paragraph(self, text: str, max_chunk_size: int) -> List[str]:
        """Chunk text by paragraphs, combining until max size."""
        paragraphs = text.split('\n\n')
        
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(current_chunk) + len(para) <= max_chunk_size:
                current_chunk += ("\n\n" if current_chunk else "") + para
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # If single paragraph exceeds max size, chunk it
                if len(para) > max_chunk_size:
                    chunks.extend(self._chunk_fixed_size(para, max_chunk_size))
                    current_chunk = ""
                else:
                    current_chunk = para
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
