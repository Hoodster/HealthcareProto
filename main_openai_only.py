#!/usr/bin/env python3
"""
AF Guidelines Drug Safety QA System - OpenAI Only Version
Simplified version using only OpenAI GPT for medical questions about AF drug safety.
"""

import os
import re
from typing import List, Dict
from pypdf import PdfReader

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

class SimpleAFQASystem:
    """Simple AF Guidelines QA System using only OpenAI"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found in environment. Please set it in your .env file.")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.pdf_content = ""
        self.pdf_files = []
        
        print("✅ AF Guidelines QA System (OpenAI-only) initialized")
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF file"""
        try:
            print(f"📄 Extracting text from {pdf_path}...")
            reader = PdfReader(pdf_path)
            full_text = ""
            
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text()
                full_text += f"\n--- Page {page_num + 1} ---\n{text}\n"
            
            # Clean up text
            full_text = re.sub(r'\s+', ' ', full_text)
            return full_text
            
        except Exception as e:
            print(f"❌ Error extracting text from {pdf_path}: {e}")
            return ""
    
    def load_pdf_files(self, pdf_paths: List[str]) -> bool:
        """Load and process PDF files"""
        all_content = ""
        successful_files = []
        
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                print(f"❌ File not found: {pdf_path}")
                continue
                
            content = self.extract_text_from_pdf(pdf_path)
            if content:
                all_content += f"\n\n=== Content from {os.path.basename(pdf_path)} ===\n{content}"
                successful_files.append(pdf_path)
            
        if successful_files:
            self.pdf_content = all_content
            self.pdf_files = successful_files
            print(f"✅ Successfully loaded {len(successful_files)} PDF file(s)")
            return True
        else:
            print("❌ No PDF files were successfully loaded")
            return False
    
    def answer_query(self, query: str) -> str:
        """Answer a query using OpenAI with PDF content as context"""
        try:
            # Prepare the context
            if self.pdf_content:
                # Truncate content if too long (OpenAI has token limits)
                max_context_length = 8000  # Conservative limit
                context = self.pdf_content[:max_context_length]
                if len(self.pdf_content) > max_context_length:
                    context += "\n\n[Content truncated due to length...]"
                
                system_prompt = """You are an expert cardiologist specializing in atrial fibrillation (AF) drug safety and guidelines. 
You have access to clinical guidelines and research papers. Provide evidence-based, clinically accurate answers focusing on:
- Drug safety considerations
- Monitoring requirements
- Contraindications and warnings  
- Drug interactions
- Dosing recommendations
- Current clinical guidelines

Be specific, cite relevant sections when possible, and emphasize safety considerations."""

                user_prompt = f"""Based on the following AF guidelines and research content:

{context}

Question: {query}

Please provide a comprehensive answer focusing on drug safety, monitoring, and clinical recommendations."""

            else:
                system_prompt = """You are an expert cardiologist specializing in atrial fibrillation (AF) drug safety. 
Provide evidence-based answers about AF medications, focusing on safety, monitoring, contraindications, and current guidelines."""
                
                user_prompt = f"""Question about AF drug safety: {query}

Please provide a detailed answer covering safety considerations, monitoring requirements, contraindications, and current clinical recommendations."""

            # Generate response
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=600,
                temperature=0.3  # Lower temperature for more consistent medical advice
            )
            
            answer = response.choices[0].message.content or "No response generated."
            
            # Add source information
            if self.pdf_files:
                source_info = f"\n\n📚 **Sources consulted:**\n"
                for pdf_file in self.pdf_files:
                    source_info += f"- {os.path.basename(pdf_file)}\n"
                answer += source_info
            
            return answer
            
        except Exception as e:
            return f"❌ Error generating response: {str(e)}"
    
    def get_status(self) -> str:
        """Get current system status"""
        status = "📊 **System Status:**\n"
        status += f"- Model: {self.model}\n"
        status += f"- PDF files loaded: {len(self.pdf_files)}\n"
        
        if self.pdf_files:
            status += "- Loaded files:\n"
            for pdf_file in self.pdf_files:
                status += f"  • {os.path.basename(pdf_file)}\n"
        else:
            status += "- No PDF files loaded (will use general medical knowledge)\n"
            
        content_length = len(self.pdf_content)
        if content_length > 0:
            status += f"- Content length: {content_length:,} characters\n"
            
        return status

def choose_pdf_files() -> List[str]:
    """Interactive PDF file selection"""
    print("\n📁 PDF File Selection:")
    print("1. Enter specific PDF file path")
    print("2. Enter directory path (scan for PDFs)")
    print("3. Use default path (/Users/kuba/Downloads/2024_AF.pdf)")
    print("4. Skip PDF loading (use general knowledge only)")
    
    choice = input("Choose option (1-4): ").strip()
    
    if choice == "1":
        path = input("Enter PDF file path: ").strip()
        if os.path.exists(path) and path.lower().endswith('.pdf'):
            return [path]
        else:
            print("❌ Invalid PDF file path")
            return []
    
    elif choice == "2":
        directory = input("Enter directory path: ").strip()
        if os.path.isdir(directory):
            pdf_files = []
            for file in os.listdir(directory):
                if file.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(directory, file))
            
            if pdf_files:
                print(f"Found {len(pdf_files)} PDF file(s):")
                for i, pdf_file in enumerate(pdf_files, 1):
                    print(f"  {i}. {os.path.basename(pdf_file)}")
                return pdf_files
            else:
                print("❌ No PDF files found in directory")
                return []
        else:
            print("❌ Invalid directory path")
            return []
    
    elif choice == "3":
        default_path = "/Users/kuba/Downloads/2024_AF.pdf"
        if os.path.exists(default_path):
            return [default_path]
        else:
            print(f"❌ Default file not found: {default_path}")
            return []
    
    elif choice == "4":
        print("✅ Skipping PDF loading - will use general medical knowledge")
        return []
    
    else:
        print("❌ Invalid choice")
        return []

def main():
    """Main interactive loop"""
    print("\n🏥 AF Guidelines Drug Safety QA System")
    print("=" * 60)
    print("OpenAI-powered medical question answering for AF drug safety")
    print("Type 'exit' to quit, 'load' to load PDFs, 'status' for system info\n")
    
    try:
        qa_system = SimpleAFQASystem()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    # Initial PDF loading
    print("\n📄 Would you like to load PDF files for context?")
    load_choice = input("Load PDFs? (y/n): ").strip().lower()
    
    if load_choice in ['y', 'yes']:
        pdf_files = choose_pdf_files()
        if pdf_files:
            qa_system.load_pdf_files(pdf_files)
    
    # Main interaction loop
    while True:
        query = input("\n❓ Enter your AF drug safety question: ").strip()
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("👋 Goodbye!")
            break
        
        elif query.lower() == 'load':
            pdf_files = choose_pdf_files()
            if pdf_files:
                qa_system.load_pdf_files(pdf_files)
        
        elif query.lower() == 'status':
            print(f"\n{qa_system.get_status()}")
        
        elif not query:
            continue
        
        else:
            print("\n🤖 GPT is analyzing your question...")
            answer = qa_system.answer_query(query)
            print(os.getenv("OPENAI_API_KEY"))
            print(f"\n📚 **Answer:**\n{answer}")
            print("\n" + "-" * 60)

if __name__ == "__main__":
    main()
