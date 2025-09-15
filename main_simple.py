#!/usr/bin/env python3
"""
AF Guidelines Drug Safety QA System - OpenAI Only Version
Simplified version using only OpenAI GPT for medical questions.
"""

import os
from openai import OpenAI

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class AFGuidelinesQA:
    """Simple AF Guidelines QA using only OpenAI"""
    
    def __init__(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Please set it in your .env file.")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        print("✅ OpenAI AF Guidelines QA System initialized")
    
    def answer_query(self, query: str) -> str:
        """Answer AF drug safety questions using OpenAI"""
        try:
            system_prompt = """You are an expert cardiologist specializing in atrial fibrillation (AF) drug safety and guidelines. 
Provide evidence-based, clinically accurate answers focusing on:
- Drug safety considerations and monitoring
- Contraindications and warnings  
- Drug interactions
- Dosing recommendations
- Current clinical guidelines (ESC, AHA/ACC/HRS)

Be specific and emphasize safety considerations."""

            user_prompt = f"""Question about AF drug safety: {query}

Please provide a detailed answer covering safety considerations, monitoring requirements, contraindications, and current clinical recommendations."""

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            return response.choices[0].message.content or "No response generated."
            
        except Exception as e:
            return f"❌ Error: {str(e)}"

def main():
    """Main interactive loop"""
    print("\n🏥 AF Guidelines Drug Safety QA System (OpenAI-powered)")
    print("=" * 60)
    print("Ask questions about atrial fibrillation drug safety")
    print("Type 'exit' to quit\n")
    
    try:
        qa_system = AFGuidelinesQA()
    except Exception as e:
        print(f"❌ Failed to initialize: {e}")
        return
    
    while True:
        query = input("❓ Enter your AF drug safety question: ").strip()
        
        if query.lower() in ['exit', 'quit', 'q']:
            print("👋 Goodbye!")
            break
        
        if not query:
            continue
        
        print("\n🤖 GPT is thinking...")
        answer = qa_system.answer_query(query)
        print(f"\n📚 **Answer:**\n{answer}")
        print("\n" + "-" * 60)

if __name__ == "__main__":
    main()
