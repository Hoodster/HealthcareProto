import torch
import transformers
from transformers import LlamaForCausalLM, LlamaTokenizer

model_dir = 'PUTDIRHERE'
model = LlamaForCausalLM.from_pretrained(model_dir)
tokenizer = LlamaTokenizer.from_pretrained(model_dir)

pipeline = transformers.pipeline("text-generation", model=model, tokenizer=tokenizer, device_map="auto", max_length=512, torch_dtype= torch.float16)

sequences = pipeline("Once upon a time", max_length=50, do_sample=True, temperature=0.7, top_k=50, top_p=0.95, num_return_sequences=5)