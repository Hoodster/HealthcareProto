#!/usr/bin/env python3
"""
Simple test to verify GPT/OpenAI functionality works
"""
import os
import sys
sys.path.append('/Users/kuba/Desktop/Studia/PythonProject1')

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI

def test_openai():
    """Test OpenAI connection and generation"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not found in environment")
        return False
        
    try:
        client = OpenAI(api_key=api_key)
        print("✅ OpenAI client created successfully")
        
        # Test a simple generation
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is atrial fibrillation? Answer in 1 sentence."}
            ],
            max_tokens=50,
            temperature=0.7
        )
        
        answer = response.choices[0].message.content
        print(f"✅ GPT Response: {answer}")
        return True
        
    except Exception as e:
        print(f"❌ OpenAI test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing GPT/OpenAI functionality...")
    success = test_openai()
    if success:
        print("\n🎉 GPT is working! You can now use OpenAI in your application.")
    else:
        print("\n❌ GPT test failed. Check your API key and connection.")
