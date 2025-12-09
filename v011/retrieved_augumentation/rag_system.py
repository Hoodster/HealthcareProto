from dataclasses import dataclass

@dataclass
class MedicalRagSystemOptions:
    

@dataclass
class MedicalRagSystemParams:
    """Parameters for Medical RAG System"""
    data_collection: str
    ai_model: str = 

class MedicalRAGSystem:
    def __init__(self, 
                 data_collection='./data/medical_articles'
                 ) -> None:
        self.data_collection = data_collection
    