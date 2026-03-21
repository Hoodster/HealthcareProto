class Chunker:
    chunked_text: str
    
    def _init__(self, text: str, chunk_size: int = 500, overlap: int = 50):
        self.text = text
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.chunked_text = self._chunk_text()

    def _chunk_text(self) -> str:
        for i in range(0, len(self.text), self.chunk_size - self.overlap)
        for i in range(0, len(self.text), self.chunk_size - self.overlap):
            chunk = self.text[i:i + self.chunk_size]
            self.chunked_text += chunk + "\n"
        return self.chunked_text
