from PyPDF2 import PdfReader

def get_pdf_text(file_path: str) -> str:
    
    text = ""
    with open(file_path, "rb") as file:
        reader = PdfReader(file)
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text

def get_multiple_pdfs_text(file_paths: list[str]) -> dict[str, str]:
    texts = {}
    for path in file_paths:
        texts[path] = get_pdf_text(path)
    return texts