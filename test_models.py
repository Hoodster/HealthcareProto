#!/usr/bin/env python3
"""
Simple test script to verify the hybrid language model works.
"""

import os
from language_model import HybridLanguageModel, GenerationConfig

def test_hybrid_model():
    print("Testing HybridLanguageModel...")
    
    # Load environment variables if .env exists
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("Loaded .env file")
    except ImportError:
        print("python-dotenv not installed, reading env vars directly")
    
    # Initialize the model
    lm = HybridLanguageModel()
    
    print(f"OpenAI available: {lm.openai_available}")
    print(f"Local model available: {lm.local_available}")
    
    if not (lm.openai_available or lm.local_available):
        print("❌ No backends available!")
        return False
    
    # Test generation
    prompt = "Explain atrial fibrillation drug safety monitoring in one sentence."
    print(f"\nTesting prompt: {prompt}")
    
    try:
        config = GenerationConfig(max_new_tokens=50, temperature=0.7)
        outputs = lm.generate(prompt, provider="auto", config=config)
        
        for backend, generations in outputs.items():
            print(f"\n=== {backend.upper()} ===")
            for i, gen in enumerate(generations, 1):
                print(f"[{i}] {gen['text'][:200]}...")
        
        print("\n✅ Test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False

if __name__ == "__main__":
    test_hybrid_model()
