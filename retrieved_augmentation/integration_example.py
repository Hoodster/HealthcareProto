"""
Integration example: RAG with existing AI service.

This demonstrates how to integrate the RAG system with the existing
AIModelService in the healthcare application.
"""

import sys
from pathlib import Path

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from typing import Optional, Dict, Any
from retrieved_augmentation import (
    Document,
    OpenAIEmbedder,
    HealthcareDocumentProcessor,
    HealthcareContextAugmentor,
)
from example_usage import (
    InMemoryVectorStore,
    SimpleRetriever,
    HealthcareRAGPipeline,
)
from api.services.ai_service import AIModelService
from models.ai_model import PatientReferenceData


class RAGEnhancedAIService:
    """
    AI service enhanced with RAG capabilities for clinical decision support.
    
    This service combines:
    - Document retrieval (RAG)
    - Expert system rules
    - LLM reasoning (GPT-4)
    """
    
    def __init__(
        self,
        ai_model: str = 'gpt-4o',
        enable_rag: bool = True,
        max_context_tokens: int = 2000
    ):
        """
        Initialize the RAG-enhanced AI service.
        
        Args:
            ai_model: OpenAI model to use
            enable_rag: Whether to enable RAG retrieval
            max_context_tokens: Maximum tokens for RAG context
        """
        # Initialize base AI service
        self.ai_service = AIModelService(ai_provider='ChatGPT', model=ai_model)
        
        # Initialize RAG components
        self.enable_rag = enable_rag
        if enable_rag:
            embedder = OpenAIEmbedder(model="text-embedding-3-small")
            processor = HealthcareDocumentProcessor(
                default_chunk_size=500,
                default_overlap=50
            )
            store = InMemoryVectorStore()
            retriever = SimpleRetriever(embedder, store)
            augmentor = HealthcareContextAugmentor(
                max_context_tokens=max_context_tokens
            )
            
            self.rag_pipeline = HealthcareRAGPipeline(
                document_processor=processor,
                embedder=embedder,
                vector_store=store,
                retriever=retriever,
                augmentor=augmentor
            )
    
    def index_patient_document(
        self,
        content: str,
        patient_id: str,
        doc_type: str = 'clinical_note',
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Index a patient document for RAG retrieval.
        
        Args:
            content: Document content
            patient_id: Patient identifier
            doc_type: Type of document
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        if not self.enable_rag:
            raise RuntimeError("RAG is not enabled")
        
        meta = metadata or {}
        meta['patient_id'] = patient_id
        
        doc = Document(
            content=content,
            metadata=meta,
            doc_type=doc_type
        )
        
        return self.rag_pipeline.index_document(doc)
    
    def index_knowledge_base(
        self,
        content: str,
        category: str,
        topic: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Index knowledge base content (guidelines, drug info, etc.).
        
        Args:
            content: Knowledge base content
            category: Category (e.g., 'cardiology', 'pharmacology')
            topic: Specific topic
            metadata: Additional metadata
            
        Returns:
            Document ID
        """
        if not self.enable_rag:
            raise RuntimeError("RAG is not enabled")
        
        meta = metadata or {}
        meta.update({'category': category, 'topic': topic})
        
        doc = Document(
            content=content,
            metadata=meta,
            doc_type='knowledge_base'
        )
        
        return self.rag_pipeline.index_document(doc)
    
    def chat_with_context(
        self,
        query: str,
        patient_data: Optional[PatientReferenceData] = None,
        patient_id: Optional[str] = None,
        include_knowledge_base: bool = True,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Chat with AI using RAG-retrieved context.
        
        Args:
            query: User question
            patient_data: Optional patient data for context
            patient_id: Optional patient ID for filtering
            include_knowledge_base: Whether to search knowledge base
            top_k: Number of chunks to retrieve
            
        Returns:
            Dictionary with answer, sources, and metadata
        """
        rag_context_str = ""
        sources = []
        
        # Retrieve relevant context if RAG is enabled
        if self.enable_rag:
            # Build filters
            filters = {}
            if patient_id:
                filters['patient_id'] = patient_id
            
            # Search patient records
            patient_context = ""
            if patient_id:
                context, rag_context = self.rag_pipeline.query(
                    query,
                    top_k=top_k // 2,
                    filters=filters,
                    return_context=True
                )
                patient_context = context
                if rag_context:
                    sources.extend(rag_context.metadata.get('sources', []))
            
            # Search knowledge base
            kb_context = ""
            if include_knowledge_base:
                context, rag_context = self.rag_pipeline.query(
                    query,
                    top_k=top_k // 2,
                    filters={'doc_type': 'knowledge_base'},
                    return_context=True
                )
                if rag_context:
                    kb_context = context
                    sources.extend(rag_context.metadata.get('sources', []))
            
            # Combine contexts
            if patient_context or kb_context:
                rag_context_str = f"""
=== CLINICAL CONTEXT FROM RECORDS ===
{patient_context}

=== RELEVANT GUIDELINES AND KNOWLEDGE ===
{kb_context}
"""
        
        # Build full prompt
        full_prompt = self._build_prompt(
            query=query,
            patient_data=patient_data,
            rag_context=rag_context_str
        )
        
        # Get AI response
        response = self.ai_service.chat(full_prompt)
        
        return {
            'answer': response,
            'sources': list(set(sources)),  # Deduplicate
            'rag_enabled': self.enable_rag,
            'context_used': bool(rag_context_str)
        }
    
    def summarize_with_context(
        self,
        text: str,
        patient_id: Optional[str] = None,
        retrieve_history: bool = True
    ) -> Dict[str, Any]:
        """
        Summarize text with additional context from patient history.
        
        Args:
            text: Text to summarize
            patient_id: Patient ID for retrieving history
            retrieve_history: Whether to retrieve historical context
            
        Returns:
            Dictionary with summary and metadata
        """
        context_str = ""
        sources = []
        
        # Retrieve historical context
        if self.enable_rag and retrieve_history and patient_id:
            context, rag_context = self.rag_pipeline.query(
                "relevant patient history and conditions",
                top_k=3,
                filters={'patient_id': patient_id},
                return_context=True
            )
            if rag_context:
                context_str = f"\n\nPatient History Context:\n{context}\n\n"
                sources = rag_context.metadata.get('sources', [])
        
        # Combine text with context
        full_text = f"{context_str}Current Note:\n{text}"
        
        # Generate summary
        summary = self.ai_service.summarize(full_text)
        
        return {
            'summary': summary,
            'sources': sources,
            'context_used': bool(context_str)
        }
    
    def _build_prompt(
        self,
        query: str,
        patient_data: Optional[PatientReferenceData],
        rag_context: str
    ) -> str:
        """Build complete prompt with all context."""
        
        prompt_parts = []
        
        # Add RAG context if available
        if rag_context:
            prompt_parts.append(rag_context)
        
        # Add patient data if available
        if patient_data:
            patient_context = f"""
=== CURRENT PATIENT DATA ===
Age: {patient_data.age}
Gender: {patient_data.gender}
QTc: {patient_data.qtc} ms
eGFR: {patient_data.egfr} mL/min/1.73m²
Medications: {', '.join(patient_data.medications) if patient_data.medications else 'None'}
Conditions: {', '.join(patient_data.conditions) if patient_data.conditions else 'None'}
"""
            prompt_parts.append(patient_context)
        
        # Add the actual question
        prompt_parts.append(f"""
=== QUESTION ===
{query}

Please provide a clear, evidence-based answer considering all the clinical context above.
If the information is insufficient, clearly state what additional information is needed.
""")
        
        return "\n".join(prompt_parts)
    
    def get_rag_statistics(self) -> Dict[str, Any]:
        """Get RAG system statistics."""
        if not self.enable_rag:
            return {'rag_enabled': False}
        
        return {
            'rag_enabled': True,
            **self.rag_pipeline.vector_store.get_stats()
        }


# Example usage functions

def example_basic_chat():
    """Example: Basic chat with RAG."""
    
    # Initialize service
    rag_ai = RAGEnhancedAIService(enable_rag=True)
    
    # Index some knowledge
    rag_ai.index_knowledge_base(
        content="""
        QTc Prolongation Management:
        - QTc > 500ms requires immediate attention
        - Discontinue QT-prolonging medications
        - Check and correct electrolytes (K, Mg, Ca)
        - Consider cardiology consultation
        - Monitor ECG regularly
        """,
        category='cardiology',
        topic='qtc_prolongation'
    )
    
    # Index patient record
    rag_ai.index_patient_document(
        content="Patient has QTc of 520ms. Currently on amiodarone for atrial fibrillation.",
        patient_id='12345',
        doc_type='clinical_note'
    )
    
    # Query with context
    result = rag_ai.chat_with_context(
        query="What should I do about this patient's prolonged QTc?",
        patient_id='12345',
        include_knowledge_base=True
    )
    
    print(f"Answer: {result['answer']}")
    print(f"Sources: {result['sources']}")
    print(f"Context used: {result['context_used']}")


def example_with_patient_data():
    """Example: ai_model import PatientReferenceData"""
    
    rag_ai = RAGEnhancedAIService(enable_rag=True)
    patient = PatientReferenceData(
        age=65,
        gender='male',
        qtc=480,
        egfr=55,
        medications=['metformin', 'lisinopril', 'atorvastatin'],
        conditions=['diabetes', 'hypertension', 'hyperlipidemia']
    )
    
    # Query with both patient data and RAG
    result = rag_ai.chat_with_context(
        query="What are the renal considerations for this patient's medications?",
        patient_data=patient,
        include_knowledge_base=True
    )
    
    print(f"Answer: {result['answer']}")


def example_summarization():
    """Example: Summarize with historical context."""
    
    rag_ai = RAGEnhancedAIService(enable_rag=True)
    
    # Index historical notes
    rag_ai.index_patient_document(
        content="Patient diagnosed with CHF 2 years ago. LVEF 35%.",
        patient_id='12345',
        doc_type='clinical_note',
        metadata={'date': '2024-01-15'}
    )
    
    rag_ai.index_patient_document(
        content="Recent admission for decompensated CHF. Increased diuretics.",
        patient_id='12345',
        doc_type='clinical_note',
        metadata={'date': '2025-06-20'}
    )
    
    # Summarize new note with historical context
    new_note = """
    Patient presents with shortness of breath and lower extremity edema.
    Weight increased 5 lbs in past week. Mild crackles on lung exam.
    """
    
    result = rag_ai.summarize_with_context(
        text=new_note,
        patient_id='12345',
        retrieve_history=True
    )
    
    print(f"Summary: {result['summary']}")
    print(f"Historical sources: {result['sources']}")



if __name__ == "__main__":
    print("=== Example 1: Basic Chat with RAG ===")
    example_basic_chat()
    
    print("\n=== Example 2: Chat with Patient Data ===")
    example_with_patient_data()
    
    print("\n=== Example 3: Summarization with History ===")
    example_summarization()
