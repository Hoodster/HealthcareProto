from dataclasses import dataclass
from typing import Dict
from PyPDF2 import DocumentInformation, PdfReader

@dataclass
class DocumentInfo:
    name: str
    source: str
    text: str
    images: Dict[str, bytes]
    paged: list[str]
    meta = DocumentInformation

def load_pdf(file_path: str, file_name: str) -> DocumentInfo:
    reader = PdfReader(file_path)
    paged = []
    images: Dict[str, bytes] = {}

    for page in reader.pages:
        paged.append(page.extract_text() or "")

        for image in page.images:
            images[image.name] = image.data

    full_extracted_text = "\n".join(paged)

    return DocumentInfo(
        name=file_name,
        source=file_path,
        text=full_extracted_text,
        images=images,
        paged=paged,
        meta=reader.metadata
    )

