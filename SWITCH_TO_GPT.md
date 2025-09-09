# How to Switch to GPT (OpenAI) 

## 🚀 Quick Answer: Already Done!

Your system is **already configured to use GPT by default**! 

## 🔧 Three Ways to Control Language Model

### **1. Automatic (Current Setup)**
- The system now defaults to **OpenAI GPT** (`gpt-4o-mini`)
- Just run your queries normally - they'll use GPT

### **2. Interactive Provider Switching**
While running the application:
```bash
python3 main.py
```
Then type: `provider`

You'll see:
```
🔧 Language Model Provider Options:
1. openai - Use GPT (OpenAI) models  ← **This is GPT!**
2. local - Use local/HuggingFace models
3. auto - Auto-select (prefers local first)
4. both - Compare both providers side-by-side
```

Choose option **1** for pure GPT responses.

### **3. Code Modification**
In `main.py`, line 579, the provider is set to use your `current_provider`:
```python
gens = self.lm.generate(prompt, provider=self.current_provider, ...)
```

The default is now `"openai"` (set in line 555).

## ✅ Current Status

- ✅ **OpenAI API Key**: Set in `.env` file  
- ✅ **Default Provider**: OpenAI (GPT)
- ✅ **Model**: `gpt-4o-mini` 
- ✅ **Interactive Switching**: Available via `provider` command

## 🧪 Test It

1. Run: `python3 main.py`
2. Type: `status` (to see if you have data)
3. If no data: type `embed` and load a PDF
4. Ask any question - it will use GPT by default!
5. Type: `provider` to see/change providers

## 🔄 Compare Models

For comparison, type `provider` → choose option `4` (both) to see GPT vs local model responses side-by-side.

**You're all set to use GPT! 🎉**
