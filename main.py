import pymupdf as fitz
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
from typing import List, Dict, Tuple
import re
import os
from tqdm import tqdm
import json
from language_model import HybridLanguageModel, GenerationConfig
import glob
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed


class AFGuidelinesProcessor:
    def __init__(self, model_name='sentence-transformers/all-mpnet-base-v2'):
        """Initialize with a more powerful transformer model for medical text"""

        self.efficiency_keywords = [
        "recurrence", "sinus rhythm", "rhythm restoration", "cardioversion",
        "AF burden", "AF-free survival", "LVEF", "ejection fraction",
        "quality of life", "AFEQT", "PROM", "symptom relief"]

        self.safety_keywords = [
            "QT", "QTc", "torsades de pointes", "proarrhythmia",
            "ALT", "AST", "bilirubin", "Hy's Law", "hepatotoxicity",
            "troponin", "creatinine", "eGFR", "bleeding", "INR", "PT", "aPTT",
            "safety", "monitoring", "adverse", "side effect", "complication",
            "contraindication", "caution", "warning", "interaction", "toxicity",
            "dose adjustment", "renal function", "hepatic function", "bleeding",
            "anticoagulant", "antiarrhythmic", "follow-up", "surveillance"
        ]

        self.ai_keywords = [
            "adverse drug reaction", "ADR", "risk stratification", "supervised learning",
            "machine learning", "predictive model", "classification", "causal inference",
            "safety signal", "clinical endpoint"
        ]

        self.model = SentenceTransformer(model_name)
        self.index = None
        self.chunks = []
        self.metadata = []

    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF with better handling of sections and headings"""
        print(f"Extracting text from {pdf_path}...")
        doc = fitz.open(pdf_path)
        full_text = ""

        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()  # type: ignore[attr-defined]
            # Add page metadata to help with context
            full_text += f"\n--- Page {page_num + 1} ---\n{text}\n"

        doc.close()
        return full_text

    def clean_text(self, text: str) -> str:
        """Clean the extracted text to improve quality"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Keep page markers
        text = re.sub(r'--- Page \d+ ---', lambda m: f"\n{m.group(0)}\n", text)
        return text.strip()

    def split_text_by_sections(self, text: str, max_chunk_size: int = 600) -> List[Dict]:
        """Split text by section headings with metadata"""
        print("Splitting text into sections...")

        # Common section heading patterns in medical guidelines
        section_pattern = re.compile(r'(\d{1,2}(?:\.\d+)+)\.\s+([^\n]+)', re.MULTILINE)

        # Find all section headings
        section_matches = list(section_pattern.finditer(text))

        chunks_with_metadata = []

        # If no sections found, fallback to simple chunking
        if not section_matches:
            print("No section headings found. Falling back to simple chunking.")
            simple_chunks = self.split_text(text, max_chunk_size)
            for i, chunk in enumerate(simple_chunks):
                chunks_with_metadata.append({
                    "text": chunk,
                    "section": f"Chunk {i + 1}",
                    "chunk_id": f"chunk-{i + 1}"
                })
            return chunks_with_metadata

        # Process each section
        for i, match in enumerate(section_matches):
            start_pos = match.start()
            # Determine end position (either next section or end of text)
            end_pos = section_matches[i + 1].start() if i < len(section_matches) - 1 else len(text)

            section_title = match.group(1).strip()
            section_text = text[start_pos:end_pos].strip()

            # Get page number if available
            page_match = re.search(r'--- Page (\d+) ---', section_text)
            page_num = int(page_match.group(1)) if page_match else None

            # Further split large sections
            if len(section_text) > max_chunk_size:
                sentences = re.split(r'(?<=[.!?])\s+', section_text)
                current_chunk = ""
                current_chunk_id = 0

                for sentence in sentences:
                    if len(current_chunk) + len(sentence) <= max_chunk_size:
                        current_chunk += sentence + " "
                    else:
                        # Store the current chunk
                        if current_chunk:
                            chunks_with_metadata.append({
                                "text": current_chunk.strip(),
                                "section": section_title,
                                "page": page_num,
                                "chunk_id": f"{section_title}-{current_chunk_id}"
                            })
                            current_chunk_id += 1
                        # Start a new chunk
                        current_chunk = sentence + " "

                # Add the last chunk
                if current_chunk:
                    chunks_with_metadata.append({
                        "text": current_chunk.strip(),
                        "section": section_title,
                        "page": page_num,
                        "chunk_id": f"{section_title}-{current_chunk_id}"
                    })
            else:
                # Add the entire section as one chunk
                chunks_with_metadata.append({
                    "text": section_text,
                    "section": section_title,
                    "page": page_num,
                    "chunk_id": section_title
                })

        return chunks_with_metadata

    def split_text(self, text, chunk_size=600, overlap=100):
        """Simple text splitting function as fallback"""
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    def identify_drug_safety_sections(self, chunks_with_metadata: List[Dict]) -> List[Dict]:
        """Tag sections likely to contain drug safety information"""
        print("Identifying drug safety related sections...")

        # Keywords related to drug safety in AF
        keywords = self.safety_keywords

        # Regex pattern for matching drug safety content
        safety_pattern = re.compile(r'\b(' + '|'.join(keywords) + r')\b', re.IGNORECASE)

        # Score and tag each chunk
        for chunk in chunks_with_metadata:
            # Count safety keyword matches
            matches = safety_pattern.findall(chunk["text"])
            safety_score = len(matches)

            # Add safety score and tag
            chunk["safety_score"] = safety_score
            chunk["is_safety_related"] = safety_score > 0
            chunk["matched_keywords"] = list(set([m.lower() for m in matches]))

        return chunks_with_metadata

    def process_pdf(self, pdf_path: str, output_dir: str = "./processed_data"):
        """Process PDF and create vector store"""
        # Create output directory if needed
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        # Extract and clean text
        raw_text = self.extract_text_from_pdf(pdf_path)
        cleaned_text = self.clean_text(raw_text)

        # Split into chunks with metadata
        chunks_with_metadata = self.split_text_by_sections(cleaned_text)

        # Identify safety-related sections
        chunks_with_metadata = self.identify_drug_safety_sections(chunks_with_metadata)

        # Generate embeddings
        print("Generating embeddings...")
        texts = [chunk["text"] for chunk in chunks_with_metadata]
        embeddings = self.model.encode(texts, show_progress_bar=True)

        # Create FAISS index
        print("Creating vector index...")
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings).astype('float32'))  # type: ignore[arg-type]

        # Store chunks and metadata
        self.chunks = texts
        self.metadata = chunks_with_metadata

        # Save data if output directory is provided
        if output_dir:
            index_path = os.path.join(output_dir, "af_guidelines.faiss")
            chunks_path = os.path.join(output_dir, "chunks.json")

            print(f"Saving index to {index_path}")
            faiss.write_index(self.index, index_path)

            print(f"Saving chunks to {chunks_path}")
            with open(chunks_path, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)

            print(f"Saved processed data to {output_dir}")

        return self.index, self.chunks, self.metadata

    def load_from_disk(self, index_path: str, chunks_path: str):
        """Load previously processed data"""
        if not os.path.exists(index_path):
            raise FileNotFoundError(f"Index file not found: {index_path}")

        if not os.path.exists(chunks_path):
            raise FileNotFoundError(f"Chunks file not found: {chunks_path}")

        print(f"Loading index from {index_path}")
        self.index = faiss.read_index(index_path)

        print(f"Loading chunks from {chunks_path}")
        with open(chunks_path, "r", encoding="utf-8") as f:
            self.metadata = json.load(f)

        self.chunks = [item["text"] for item in self.metadata]
        print(f"Loaded {len(self.chunks)} chunks from disk")
        return self.index, self.chunks, self.metadata

    def search(self, query: str, k: int = 5, safety_only: bool = True) -> List[Dict]:
        """Search for relevant chunks and return with metadata"""
        if not self.index:
            raise ValueError("No index loaded. Process a PDF or load from disk first.")

        # Encode the query
        query_embedding = self.model.encode([query])

        # Search
        distances, indices = self.index.search(np.array(query_embedding).astype('float32'), k * 2 if safety_only else k)  # type: ignore[arg-type]

        # Get results with metadata
        results = []

        for i, idx in enumerate(indices[0]):
            if idx >= len(self.metadata):
                continue

            result = self.metadata[idx].copy()
            result["distance"] = float(distances[0][i])
            results.append(result)

        # Filter for safety-related results if requested
        if safety_only:
            safety_results = [r for r in results if r.get("is_safety_related", False)]
            # If we don't have enough safety results, include some non-safety ones
            if len(safety_results) < k:
                non_safety = [r for r in results if not r.get("is_safety_related", False)]
                results = safety_results + non_safety[:k - len(safety_results)]
            else:
                results = safety_results[:k]
        else:
            results = results[:k]

        return results

    def extract_safety_guidelines(self, top_k: int = 20) -> Dict:
        """Extract structured drug safety guidelines from the document"""
        if not self.metadata:
            raise ValueError("No document processed. Process a PDF first.")

        # Find sections with highest safety scores
        safety_sections = sorted(
            [s for s in self.metadata if s.get("safety_score", 0) > 0],
            key=lambda x: x.get("safety_score", 0),
            reverse=True
        )[:top_k]

        # Group by safety category
        safety_categories = {
            "anticoagulation": [],
            "antiarrhythmic": [],
            "rate_control": [],
            "monitoring_protocols": [],
            "adverse_events": [],
            "drug_interactions": [],
            "special_populations": [],
            "general": []
        }

        # Categorize sections
        for section in safety_sections:
            text = section["text"].lower()
            matched = set(section.get("matched_keywords", []))

            # Categorize based on content and keywords
            if any(kw in matched for kw in ["anticoagulant", "bleeding", "hemorrhage"]) or any(word in text for word in
                                                                                               ["warfarin", "doac",
                                                                                                "noac", "apixaban",
                                                                                                "rivaroxaban",
                                                                                                "dabigatran",
                                                                                                "edoxaban"]):
                safety_categories["anticoagulation"].append(section)
            elif any(kw in matched for kw in ["antiarrhythmic", "rhythm control"]) or any(
                    word in text for word in ["amiodarone", "flecainide", "propafenone", "sotalol"]):
                safety_categories["antiarrhythmic"].append(section)
            elif any(kw in matched for kw in ["rate control"]) or any(
                    word in text for word in ["beta-blocker", "digoxin", "calcium channel"]):
                safety_categories["rate_control"].append(section)
            elif any(kw in matched for kw in ["monitoring", "follow-up", "surveillance"]):
                safety_categories["monitoring_protocols"].append(section)
            elif any(kw in matched for kw in ["adverse", "side effect", "complication", "toxicity"]):
                safety_categories["adverse_events"].append(section)
            elif any(kw in matched for kw in ["interaction", "concomitant"]):
                safety_categories["drug_interactions"].append(section)
            elif any(kw in matched for kw in ["elderly", "renal", "hepatic", "pregnancy", "age"]):
                safety_categories["special_populations"].append(section)
            else:
                safety_categories["general"].append(section)

        return safety_categories

    def generate_safety_report(self) -> str:
        """Generate a formatted safety monitoring report"""
        safety_data = self.extract_safety_guidelines()

        report = "# AF Drug Safety and Monitoring Guidelines\n\n"
        report += "_Extracted from ESC AF Guidelines_\n\n"

        # Add each section
        for category, sections in safety_data.items():
            if not sections:
                continue

            category_title = category.replace("_", " ").title()
            report += f"## {category_title}\n\n"

            for section in sections:
                # Extract key sentences related to safety
                sentences = re.split(r'(?<=[.!?])\s+', section["text"])
                safety_sentences = [
                    s for s in sentences
                    if any(kw in s.lower() for kw in ["safety", "monitor", "caution", "recommend",
                                                      "adverse", "effect", "risk", "contraindic",
                                                      "dose", "adjust"])
                ]

                # Add section title if available
             #   if "section" in section:
             #       report += f"### {section['section']}\n\n"

                # Add bullet points for key safety information
                if safety_sentences:
                    for sentence in safety_sentences:
                        report += f"- {sentence.strip()}\n"
                else:
                    # If no specific safety sentences found, include the first part of the section
                    summary = " ".join(sentences[:3]) if len(sentences) > 3 else section["text"]
                    report += f"- {summary.strip()}\n"

                report += "\n"

        return report


def choose_pdf_files():
    """Interactive function to choose PDF files or directories to process"""
    print("\n📁 Choose PDF files to process:")
    print("1. Enter a specific PDF file path")
    print("2. Enter a directory path (will process all PDFs in directory)")
    print("3. Use default path (/Users/kuba/Downloads/2024_AF.pdf)")
    print("4. Browse current directory for PDFs")
    
    choice = input("\nEnter your choice (1-4): ").strip()
    
    if choice == "1":
        file_path = input("Enter PDF file path: ").strip()
        if file_path.startswith('"') and file_path.endswith('"'):
            file_path = file_path[1:-1]  # Remove quotes
        if os.path.exists(file_path) and file_path.lower().endswith('.pdf'):
            return [file_path]
        else:
            print(f"❌ File not found or not a PDF: {file_path}")
            return []
    
    elif choice == "2":
        dir_path = input("Enter directory path: ").strip()
        if dir_path.startswith('"') and dir_path.endswith('"'):
            dir_path = dir_path[1:-1]  # Remove quotes
        if os.path.exists(dir_path) and os.path.isdir(dir_path):
            pdf_files = glob.glob(os.path.join(dir_path, "*.pdf"))
            if pdf_files:
                print(f"Found {len(pdf_files)} PDF files:")
                for i, pdf in enumerate(pdf_files, 1):
                    print(f"  {i}. {os.path.basename(pdf)}")
                return pdf_files
            else:
                print(f"❌ No PDF files found in directory: {dir_path}")
                return []
        else:
            print(f"❌ Directory not found: {dir_path}")
            return []
    
    elif choice == "3":
        default_path = "/Users/kuba/Downloads/2024_AF.pdf"
        if os.path.exists(default_path):
            return [default_path]
        else:
            print(f"❌ Default file not found: {default_path}")
            return []
    
    elif choice == "4":
        current_dir = os.getcwd()
        pdf_files = glob.glob(os.path.join(current_dir, "*.pdf"))
        if pdf_files:
            print(f"Found {len(pdf_files)} PDF files in current directory:")
            for i, pdf in enumerate(pdf_files, 1):
                print(f"  {i}. {os.path.basename(pdf)}")
            
            try:
                selected = input("Enter file numbers to process (e.g., 1,3,5 or 'all'): ").strip()
                if selected.lower() == 'all':
                    return pdf_files
                else:
                    indices = [int(x.strip()) - 1 for x in selected.split(',')]
                    return [pdf_files[i] for i in indices if 0 <= i < len(pdf_files)]
            except (ValueError, IndexError):
                print("❌ Invalid selection")
                return []
        else:
            print(f"❌ No PDF files found in current directory: {current_dir}")
            return []
    
    else:
        print("❌ Invalid choice")
        return []


def process_multiple_pdfs(processor: AFGuidelinesProcessor, pdf_files: List[str], output_dir: str):
    """Process multiple PDF files and combine their embeddings"""
    if not pdf_files:
        print("❌ No PDF files to process")
        return False
    
    print(f"\n🔄 Processing {len(pdf_files)} PDF file(s)...")
    
    all_chunks_with_metadata = []
    
    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n📄 Processing file {i}/{len(pdf_files)}: {os.path.basename(pdf_path)}")
        
        try:
            # Extract and clean text
            raw_text = processor.extract_text_from_pdf(pdf_path)
            cleaned_text = processor.clean_text(raw_text)
            
            # Split into chunks with metadata
            chunks_with_metadata = processor.split_text_by_sections(cleaned_text)
            
            # Add source file information to each chunk
            for chunk in chunks_with_metadata:
                chunk["source_file"] = os.path.basename(pdf_path)
                chunk["source_path"] = pdf_path
            
            # Identify safety-related sections
            chunks_with_metadata = processor.identify_drug_safety_sections(chunks_with_metadata)
            
            all_chunks_with_metadata.extend(chunks_with_metadata)
            
        except Exception as e:
            print(f"❌ Error processing {pdf_path}: {e}")
            continue
    
    if not all_chunks_with_metadata:
        print("❌ No content extracted from any PDF files")
        return False
    
    # Generate embeddings for all chunks
    print(f"\n🧠 Generating embeddings for {len(all_chunks_with_metadata)} chunks...")
    texts = [chunk["text"] for chunk in all_chunks_with_metadata]
    embeddings = processor.model.encode(texts, show_progress_bar=True)
    
    # Create FAISS index
    print("🔍 Creating vector index...")
    dimension = embeddings.shape[1]
    processor.index = faiss.IndexFlatL2(dimension)
    processor.index.add(np.array(embeddings).astype('float32'))  # type: ignore[arg-type]
    
    # Store chunks and metadata
    processor.chunks = texts
    processor.metadata = all_chunks_with_metadata
    
    # Create output directory if needed
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"📁 Created output directory: {output_dir}")
    
    # Save data
    if output_dir:
        index_path = os.path.join(output_dir, "af_guidelines.faiss")
        chunks_path = os.path.join(output_dir, "chunks.json")
        
        print(f"💾 Saving index to {index_path}")
        faiss.write_index(processor.index, index_path)
        
        print(f"💾 Saving chunks to {chunks_path}")
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(processor.metadata, f, indent=2, ensure_ascii=False)
        
        # Save processing summary
        summary_path = os.path.join(output_dir, "processing_summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(f"Processing Summary\n")
            f.write(f"================\n\n")
            f.write(f"Processed files: {len(pdf_files)}\n")
            f.write(f"Total chunks: {len(all_chunks_with_metadata)}\n")
            f.write(f"Safety-related chunks: {len([c for c in all_chunks_with_metadata if c.get('is_safety_related', False)])}\n\n")
            f.write(f"Source files:\n")
            for pdf in pdf_files:
                f.write(f"  - {pdf}\n")
        
        print(f"📋 Saved processing summary to {summary_path}")
        print(f"✅ Saved processed data to {output_dir}")
    
    return True


class AFGuidelinesQA:
    def __init__(self, processor: AFGuidelinesProcessor):
        self.processor = processor
        self.current_provider = "openai"  # Default to OpenAI/GPT
        # Lazy init HybridLanguageModel; user can set env vars for models
        try:
            self.lm = HybridLanguageModel()
        except Exception:
            self.lm = None

    def answer_query(self, query: str, k: int = 5) -> str:
        """Generate an answer for a drug safety query"""
        # Get relevant chunks
        results = self.processor.search(query, k=k, safety_only=True)

        if not results:
            return "I couldn't find specific information about that in the AF guidelines."

        # Prepare context for answering
        context = "\n\n".join([res["text"] for res in results])
        # If hybrid LM available, create a focused prompt and try both providers (auto fallbacks)
        if self.lm:
            prompt = (
                "You are an assistant summarizing AF (atrial fibrillation) drug safety guidelines.\n"
                f"Question: {query}\n"
                "Use ONLY the provided context. Be concise (<=180 words).\n"
                "Context:\n" + context + "\n---\nAnswer:" )
            try:
                gens = self.lm.generate(prompt, provider=self.current_provider, config=GenerationConfig(max_new_tokens=220, temperature=0.4))
                # Pick first generation from whichever provider responded
                provider = next(iter(gens))
                model_answer = gens[provider][0]["text"].strip()
                answer = self._format_answer(query, results)
                answer = answer + "\n\n### Synthesized Answer (" + provider + ")\n\n" + model_answer
                return answer
            except Exception as e:
                # Fall back to simple reference answer
                return self._format_answer(query, results) + f"\n\n*LLM synthesis unavailable: {e}*"
        else:
            # Fallback: return formatted context
            return self._format_answer(query, results)

    def _format_answer(self, query: str, results: List[Dict]) -> str:
        """Format the answer based on retrieved chunks"""
        answer = f"Based on the loaded guidelines, here's information about '{query}':\n\n"

        for i, res in enumerate(results):
            section_title = res.get("section", f"Section {i + 1}")
            source_file = res.get("source_file", "Unknown source")
            
            answer += f"### {section_title}\n"
            answer += f"*Source: {source_file}*"

            # Include page number if available
            if res.get("page"):
                answer += f" | *Page {res['page']}*"
            answer += "\n\n"

            # Add the text content with some formatting
            answer += f"{res['text'][:1200]}{'...' if len(res['text']) > 1200 else ''}\n\n"

            # Add safety score information if available
            if "safety_score" in res and res["safety_score"] > 0:
                answer += f"*This section contains {res['safety_score']} safety-related references*\n\n"

        answer += "---\n"
        answer += "Note: This information is extracted directly from the processed guidelines. Always consult the full guidelines and a healthcare professional for complete information."

        return answer


# Usage example
def demo():
    output_dir = "./processed_data"
    processor = AFGuidelinesProcessor()

    # Check if processed data exists
    index_path = os.path.join(output_dir, "af_guidelines.faiss")
    chunks_path = os.path.join(output_dir, "chunks.json")

    try:
        # Try to load existing data
        if os.path.exists(index_path) and os.path.exists(chunks_path):
            print("Found existing processed data. Loading...")
            processor.load_from_disk(index_path, chunks_path)
            
            # Show summary of loaded data
            if processor.metadata:
                source_files = set(chunk.get("source_file", "Unknown") for chunk in processor.metadata)
                print(f"📊 Loaded {len(processor.chunks)} chunks from {len(source_files)} file(s)")
                if len(source_files) <= 5:  # Don't spam if too many files
                    for file in sorted(source_files):
                        print(f"   - {file}")
        else:
            print("No existing processed data found.")
            print("Use the 'embed' command to process PDF files.")
    except Exception as e:
        print(f"Error during initialization: {str(e)}")

    # Create QA system
    qa_system = AFGuidelinesQA(processor)

    # Interactive query loop
    print("\n=== AF Guidelines Drug Safety Information System ===")
    print("Type 'report' to generate a safety monitoring report")
    print("Type 'embed' to process PDF files (choose files/directories interactively)")
    print("Type 'status' to show current data status")
    print("Type 'provider' to switch between openai/local/auto language models")
    print("Type 'exit' to quit")

    while True:
        query = input("\n❓ Enter your query about AF drug safety: ")

        if query.lower() in ["exit", "quit"]:
            break
        elif query.lower() == "report":
            if not processor.metadata:
                print("❌ No data loaded. Use 'embed' command first to process PDF files.")
                continue
            try:
                report = processor.generate_safety_report()
                print("\n📋 Drug Safety Monitoring Report:\n")
                print(report)
                # Save report
                with open("af_safety_report.md", "w", encoding="utf-8") as f:
                    f.write(report)
                print("\nReport saved to af_safety_report.md")
            except Exception as e:
                print(f"Error generating report: {str(e)}")
        elif query.lower() == "embed":
            try:
                pdf_files = choose_pdf_files()
                if pdf_files:
                    success = process_multiple_pdfs(processor, pdf_files, output_dir)
                    if success:
                        print("✅ Embeddings updated successfully!")
                        # Update QA system with new processor
                        qa_system = AFGuidelinesQA(processor)
                    else:
                        print("❌ Failed to process PDF files.")
                else:
                    print("❌ No PDF files selected.")
            except Exception as e:
                print(f"Error during embedding: {e}")
        elif query.lower() == "status":
            if processor.metadata:
                source_files = set(chunk.get("source_file", "Unknown") for chunk in processor.metadata)
                safety_chunks = len([c for c in processor.metadata if c.get("is_safety_related", False)])
                print(f"\n📊 Current Data Status:")
                print(f"   Total chunks: {len(processor.chunks)}")
                print(f"   Safety-related chunks: {safety_chunks}")
                print(f"   Source files ({len(source_files)}):")
                for file in sorted(source_files):
                    file_chunks = len([c for c in processor.metadata if c.get("source_file") == file])
                    print(f"     - {file}: {file_chunks} chunks")
                print(f"   Index available: {'Yes' if processor.index else 'No'}")
            else:
                print("❌ No data loaded. Use 'embed' command to process PDF files.")
        elif query.lower() == "provider":
            # Provider switching command
            print("\n🔧 Language Model Provider Options:")
            print("1. openai - Use GPT (OpenAI) models")
            print("2. local - Use local/HuggingFace models")  
            print("3. auto - Auto-select (prefers local first)")
            print("4. both - Compare both providers side-by-side")
            
            choice = input("Choose provider (1-4): ").strip()
            if choice == "1":
                qa_system.current_provider = "openai"
                print("✅ Switched to OpenAI (GPT) provider")
            elif choice == "2":
                qa_system.current_provider = "local"
                print("✅ Switched to local model provider")
            elif choice == "3":
                qa_system.current_provider = "auto"
                print("✅ Switched to auto-select provider")
            elif choice == "4":
                qa_system.current_provider = "both"
                print("✅ Switched to both providers (comparison mode)")
            else:
                print("❌ Invalid choice. Current provider unchanged.")
        else:
            if not processor.metadata:
                print("❌ No data loaded. Use 'embed' command first to process PDF files.")
                continue
            try:
                answer = qa_system.answer_query(query)
                print("\n📚 Answer:\n")
                print(answer)
            except Exception as e:
                print(f"Error answering query: {str(e)}")


if __name__ == "__main__":
    demo()