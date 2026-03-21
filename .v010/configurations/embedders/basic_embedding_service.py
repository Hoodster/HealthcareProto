from typing import overload
from v010.abstraction.embedding_service import EmbeddingService
from pdfminer.high_level import extract_text

try:
    from pdf2image import convert_from_path  # type: ignore
except Exception:
    def convert_from_path(*args, **kwargs):
        raise RuntimeError(
            "pdf2image is required for PDF to image conversion; install it with "
            "'pip install pdf2image' and ensure Poppler is installed on your system."
        )


class BasicEmbeddingService(EmbeddingService):

    def __init__(self, model_name: str, api_key: str, **kwargs):
        self.documents = []
        super().__init__(model_name, api_key, **kwargs)

    def load_documents(self, file_paths: list[str] | None = None) -> dict[str, str]:
        """Load documents from given file paths and return their text content."""
        if file_paths is None:
            raise ValueError("file_paths cannot be None")
        
        for file_path in file_paths:
            image_export = convert_from_path(file_path)
            self.documents.append(image_export)
            if not file_path.lower().endswith('.pdf'):
                raise ValueError(f"Unsupported file type: {file_path}. Only PDF files are supported.")
            
        from v010.utils.pdf_io import get_multiple_pdfs_text
        return get_multiple_pdfs_text(file_paths)

