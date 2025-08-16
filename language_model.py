import PyPDF2
import torch
from transformers import LlamaForCausalLM, LlamaTokenizer
import re
from typing import List, Dict
import json


class PDFSummarizer:
    def __init__(self, model_dir: str):
        """Initialize with your Llama model"""
        print("Loading model...")
        self.model = LlamaForCausalLM.from_pretrained(
            model_dir,
            torch_dtype=torch.float16,
            device_map="auto"
        )
        self.tokenizer = LlamaTokenizer.from_pretrained(model_dir)

        # Set pad token if not exists
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        print("Model loaded successfully!")

    def extract_pdf_text(self, pdf_path: str) -> str:
        """Extract text from PDF"""
        text = ""
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            print(f"Error reading PDF: {e}")
            return ""

    def clean_text(self, text: str) -> str:
        """Clean the extracted text"""
        # Remove excessive whitespace
        text = re.sub(r'\n+', '\n', text)
        text = re.sub(r' +', ' ', text)

        # Remove obvious page artifacts
        lines = []
        for line in text.split('\n'):
            line = line.strip()
            # Skip page numbers, short lines, headers
            if (len(line) > 10 and
                    not re.match(r'^\d+$', line) and
                    not re.match(r'^page \d+', line, re.IGNORECASE)):
                lines.append(line)

        return '\n'.join(lines)

    def chunk_text(self, text: str, max_tokens: int = 1500) -> List[str]:
        """Split text into chunks that fit in model context"""
        # Split by paragraphs first
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            # Rough token estimation (1 token ≈ 4 characters)
            para_tokens = len(para) // 4
            current_tokens = len(current_chunk) // 4

            if current_tokens + para_tokens > max_tokens and current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def summarize_chunk(self, text: str) -> str:
        """Generate summary for a text chunk using Llama"""
        prompt = f"""Summarize the following text in 2-3 clear sentences. Focus on the main points and key information:

{text}

Summary:"""

        try:
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)

            with torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    max_new_tokens=150,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.eos_token_id
                )

            # Decode and extract summary
            full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            # Extract just the summary part
            if "Summary:" in full_response:
                summary = full_response.split("Summary:")[-1].strip()
            else:
                summary = full_response[len(prompt):].strip()

            # Clean up the summary
            summary = re.sub(r'\n+', ' ', summary)
            summary = re.sub(r'\s+', ' ', summary)

            # Stop at first complete sentence set if too long
            if len(summary) > 300:
                sentences = re.split(r'(?<=[.!?])\s+', summary)
                summary = '. '.join(sentences[:3]) + '.'

            return summary if summary else "Could not generate summary for this section."

        except Exception as e:
            print(f"Error generating summary: {e}")
            return "Summary generation failed."

    def extract_references(self, text: str) -> List[str]:
        """Find references and citations in the text"""
        refs = set()

        # Numbered citations [1], [2-5], etc.
        numbered = re.findall(r'\[\d+(?:-\d+)?(?:,\s*\d+)*\]', text)
        refs.update(numbered)

        # Author-year citations (Smith, 2023), (Jones et al., 2022)
        author_year = re.findall(r'\([A-Z][a-z]+(?:\s+et\s+al\.?)?,\s*\d{4}\)', text)
        refs.update(author_year)

        # DOIs
        dois = re.findall(r'doi:\s*[\w\./:-]+', text, re.IGNORECASE)
        refs.update(dois)

        # URLs
        urls = re.findall(r'https?://[^\s\)\]]+', text)
        refs.update(urls)

        # Reference list entries (lines that look like full citations)
        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            # Look for lines that contain year, author patterns, and are substantial
            if (len(line) > 50 and
                    re.search(r'\b(19|20)\d{2}\b', line) and
                    (re.search(r'[A-Z][a-z]+,?\s+[A-Z]\.', line) or
                     'et al' in line.lower() or
                     'journal' in line.lower())):
                refs.add(line)

        return sorted(list(refs))

    def generate_overall_summary(self, chunk_summaries: List[str]) -> str:
        """Create overall document summary from chunk summaries"""
        combined = " ".join(chunk_summaries)

        prompt = f"""Based on these section summaries, write a comprehensive 4-5 sentence overview of the entire document:

{combined}

Overall Summary:"""

        try:
            inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=2048)

            with torch.no_grad():
                outputs = self.model.generate(
                    inputs.input_ids,
                    max_new_tokens=200,
                    temperature=0.7,
                    do_sample=True,
                    top_p=0.9,
                    pad_token_id=self.tokenizer.eos_token_id
                )

            full_response = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            if "Overall Summary:" in full_response:
                summary = full_response.split("Overall Summary:")[-1].strip()
            else:
                summary = full_response[len(prompt):].strip()

            summary = re.sub(r'\n+', ' ', summary)
            summary = re.sub(r'\s+', ' ', summary)

            return summary if summary else "Could not generate overall summary."

        except Exception as e:
            print(f"Error generating overall summary: {e}")
            return "Overall summary generation failed."

    def process_pdf(self, pdf_path: str) -> Dict:
        """Main function to process PDF and generate summaries"""
        print(f"Processing PDF: {pdf_path}")

        # Extract and clean text
        raw_text = self.extract_pdf_text(pdf_path)
        if not raw_text:
            return {"error": "Could not extract text from PDF"}

        clean_text = self.clean_text(raw_text)
        print(f"Extracted {len(clean_text)} characters of text")

        # Create chunks
        chunks = self.chunk_text(clean_text)
        print(f"Split into {len(chunks)} chunks")

        # Generate summaries for each chunk
        print("Generating summaries...")
        chunk_summaries = []
        summary_texts = []

        for i, chunk in enumerate(chunks):
            print(f"Summarizing chunk {i + 1}/{len(chunks)}")
            summary = self.summarize_chunk(chunk)
            chunk_summaries.append({
                'chunk_number': i + 1,
                'summary': summary,
                'original_length': len(chunk),
                'chunk_preview': chunk[:200] + "..." if len(chunk) > 200 else chunk
            })
            summary_texts.append(summary)

        # Generate overall summary
        print("Generating overall summary...")
        overall_summary = self.generate_overall_summary(summary_texts)

        # Extract references
        references = self.extract_references(clean_text)

        result = {
            'pdf_file': pdf_path,
            'overall_summary': overall_summary,
            'chunk_summaries': chunk_summaries,
            'references': references,
            'stats': {
                'total_chunks': len(chunks),
                'total_references': len(references),
                'original_text_length': len(clean_text),
                'average_chunk_size': len(clean_text) // len(chunks) if chunks else 0
            }
        }

        return result


def main():
    # CHANGE THESE PATHS:
    model_dir = "/path/to/your/llama/model"  # Put your model path here
    pdf_path = "your_document.pdf"  # Put your PDF path here

    try:
        summarizer = PDFSummarizer(model_dir)
        results = summarizer.process_pdf(pdf_path)

        if "error" in results:
            print(f"Error: {results['error']}")
            return

        # Print results
        print("\n" + "=" * 60)
        print("PDF SUMMARY REPORT")
        print("=" * 60)

        print(f"\nDocument Statistics:")
        print(f"• Total chunks processed: {results['stats']['total_chunks']}")
        print(f"• References found: {results['stats']['total_references']}")
        print(f"• Original text length: {results['stats']['original_text_length']:,} characters")

        print(f"\nOVERALL SUMMARY:")
        print(f"{results['overall_summary']}")

        print(f"\nCHUNK SUMMARIES:")
        for chunk_sum in results['chunk_summaries']:
            print(f"\n--- Chunk {chunk_sum['chunk_number']} ---")
            print(f"Summary: {chunk_sum['summary']}")
            print(f"Original length: {chunk_sum['original_length']} chars")

        print(f"\nREFERENCES:")
        for i, ref in enumerate(results['references'], 1):
            print(f"{i}. {ref}")

        # Save to file
        output_file = "pdf_summary_report.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"\nDetailed results saved to: {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()