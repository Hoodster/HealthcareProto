#!/usr/bin/env python3
"""
Simplified AF Guidelines QA System - OpenAI Only Version
This version skips local models and embedding to focus on GPT functionality
"""
import os
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class SimpleGPTQA:
    def __init__(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Please set it in your .env file.")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        print("✅ GPT-powered AF Guidelines QA System initialized")

    def answer_query(self, query: str) -> str:
        """Answer a query using GPT"""
        try:
            # Create a focused prompt for AF drug safety
            prompt = f"""You are an expert in atrial fibrillation (AF) drug safety and guidelines. 
            
Question: {query}

Please provide a detailed, clinically accurate answer focusing on:
- Drug safety considerations
- Monitoring requirements  
- Contraindications and warnings
- Drug interactions
- Current clinical guidelines

Keep your response evidence-based and clinically relevant."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert cardiologist specializing in atrial fibrillation drug safety."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,
                temperature=0.3  # Lower temperature for more consistent medical advice
            )
            
            return response.choices[0].message.content or "No response generated."
            
        except Exception as e:
            return f"Error generating response: {str(e)}"

def main():
    """Main interactive loop"""
    print("\n🏥 AF Guidelines Drug Safety QA System (GPT-Powered)")
    print("=" * 60)
    print("This simplified version uses GPT-4o-mini for AF drug safety questions.")
    print("Type 'exit' to quit\n")
    
    try:
        qa_system = SimpleGPTQA()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    while True:
        query = input("❓ Enter your AF drug safety question: ").strip()
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("Goodbye!")
            break
            
        if not query:
            continue
            
        print("\n🤖 GPT is thinking...")
        answer = qa_system.answer_query(query)
        print(f"\n📚 GPT Response:\n{answer}\n")
        print("-" * 60)

if __name__ == "__main__":
    main()
