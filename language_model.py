"""Hybrid language model utilities.

This module provides a simple interface to generate text using either:
1. A local / HF Hub transformers causal LM (e.g. Llama) loaded with `transformers`
2. An OpenAI chat/completions model via the `openai` package
3. Both backends, returning combined outputs for quick comparison

Environment variables:
  OPENAI_API_KEY  (required only if using the OpenAI backend)
  LOCAL_LLM_DIR   (optional path to a local model directory if you don't pass it programmatically)

Typical usage:
  from language_model import HybridLanguageModel
  lm = HybridLanguageModel(local_model_dir="/path/to/llama")
  out = lm.generate("Explain AF drug safety considerations", provider="both")
  print(out["local"][0]["text"])
  print(out["openai"][0]["text"])

The code tries to keep dependencies lazy: if a backend can't initialize, it is skipped with a warning.
"""

from __future__ import annotations

import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, cast

import torch
import transformers  # type: ignore
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline as hf_pipeline  # type: ignore
from openai import OpenAI  # type: ignore

logger = logging.getLogger(__name__)
logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))

@dataclass
class GenerationConfig:
	"""Unified generation parameters (subset mapped to each backend)."""
	max_new_tokens: int = 256
	temperature: float = 0.7
	top_p: float = 0.95
	top_k: int = 50  # (transformers only)
	n: int = 1       # number of completions (OpenAI) / sequences (transformers)
	stop: Optional[Union[str, List[str]]] = None
	presence_penalty: Optional[float] = None  # OpenAI only
	frequency_penalty: Optional[float] = None # OpenAI only


class HybridLanguageModel:
	"""Wrapper supporting local transformers + OpenAI generation.

	Parameters
	----------
	local_model_dir : str | None
		Path to local model directory (or HF Hub model id). If None, local backend is disabled.
	local_dtype : str
		Torch dtype to use ("auto", "float16", "bfloat16", etc.).
	device_map : str | Dict
		Passed to `from_pretrained` / pipeline for model placement.
	openai_model : str
		Name of OpenAI model (e.g. "gpt-4o-mini"). Used if OpenAI API key present.
	use_chat_completion : bool
		If True, uses chat.completions; otherwise (future) could toggle to responses.*
	"""

	def __init__(
		self,
		local_model_dir: Optional[str] = None,
		*,
		local_dtype: str = "auto",
		device_map: Union[str, Dict[str, int]] = "auto",
		openai_model: str = "gpt-4o-mini",
		use_chat_completion: bool = True,
		auto_load_hf_model: bool = True,
		default_hf_model_id: str = "distilgpt2",
	):
		self.local_model_dir = local_model_dir or os.getenv("LOCAL_LLM_DIR")
		self.openai_model = openai_model
		self.use_chat_completion = use_chat_completion
		self.device_map = device_map
		self.local_available = False
		self.openai_available = False
		self._local_pipeline = None

		# Try OpenAI client first (no exception if key missing)
		# Accept either OPENAI_API_KEY (preferred) or legacy OPEN_API_KEY
		api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPEN_API_KEY")
		if os.getenv("OPEN_API_KEY") and not os.getenv("OPENAI_API_KEY"):
			logger.warning("Environment variable 'OPEN_API_KEY' found. Prefer 'OPENAI_API_KEY'. Using it for now.")
		if api_key:
			try:
				self._openai_client = OpenAI(api_key=api_key)
				self.openai_available = True
				logger.info("OpenAI backend enabled (model=%s)", openai_model)
			except Exception as e:
				logger.warning("Failed to init OpenAI client: %s", e)
				self._openai_client = None
		else:
			logger.info("OPENAI_API_KEY not set – OpenAI backend disabled.")
			self._openai_client = None

		# Initialize local transformer model if directory provided
		if self.local_model_dir:
			try:
				logger.info("Loading local model from %s", self.local_model_dir)
				torch_dtype = None
				if local_dtype != "auto":
					torch_dtype = getattr(torch, local_dtype)
				model = AutoModelForCausalLM.from_pretrained(
					self.local_model_dir,
					torch_dtype=torch_dtype,
					device_map=self.device_map,
				)
				tokenizer = AutoTokenizer.from_pretrained(self.local_model_dir)
				if tokenizer.pad_token is None:
					tokenizer.pad_token = tokenizer.eos_token
				self._local_pipeline = hf_pipeline(
					"text-generation",
					model=model,
					tokenizer=tokenizer,
					device_map=self.device_map,
				)
				self.local_available = True
				logger.info("Local transformers backend enabled.")
			except Exception as e:
				logger.warning("Failed to load local model '%s': %s", self.local_model_dir, e)
		else:
			if auto_load_hf_model:
				try:
					logger.info("No local model dir provided – auto-loading default HF model '%s'", default_hf_model_id)
					model = AutoModelForCausalLM.from_pretrained(
						default_hf_model_id,
						device_map=self.device_map,
						torch_dtype=None if local_dtype == "auto" else getattr(torch, local_dtype),
					)
					tokenizer = AutoTokenizer.from_pretrained(default_hf_model_id)
					if tokenizer.pad_token is None:
						tokenizer.pad_token = tokenizer.eos_token
					self._local_pipeline = hf_pipeline(
						"text-generation",
						model=model,
						tokenizer=tokenizer,
						device_map=self.device_map,
					)
					self.local_available = True
					logger.info("Default HF model backend enabled.")
				except Exception as e:
					logger.warning("Failed to auto-load default HF model '%s': %s", default_hf_model_id, e)
			else:
				logger.info("No local model dir provided – local backend disabled.")

		if not (self.local_available or self.openai_available):
			logger.warning("No language model backend available. Provide LOCAL_LLM_DIR and/or OPENAI_API_KEY.")

	# ---------------------------------------------------------------------
	# Public API
	# ---------------------------------------------------------------------
	def generate(
		self,
		prompt: str,
		*,
		provider: str = "auto",
		config: Optional[GenerationConfig] = None,
		**overrides: Any,
	) -> Dict[str, List[Dict[str, Any]]]:
		"""Generate text.

		Parameters
		----------
		prompt : str
			Input prompt.
		provider : str
			'local' | 'openai' | 'both' | 'auto'.
			auto => prefer local if available else openai.
		config : GenerationConfig | None
			Shared generation config (can override with kwargs).
		overrides : Any
			Extra params overriding config attributes.

		Returns
		-------
		Dict mapping provider name to list of generations. Each generation dict contains:
		  {'text': str, 'raw': backend_raw_object}
		"""
		config = config or GenerationConfig()
		# apply overrides
		for k, v in overrides.items():
			if hasattr(config, k):
				setattr(config, k, v)

		if provider == "auto":
			if self.local_available:
				provider = "local"
			elif self.openai_available:
				provider = "openai"
			else:
				raise RuntimeError("No backend available for generation.")

		outputs: Dict[str, List[Dict[str, Any]]] = {}
		if provider in ("local", "both"):
			if not self.local_available:
				logger.warning("Local backend requested but not available.")
			else:
				outputs["local"] = self._generate_local(prompt, config)
		if provider in ("openai", "both"):
			if not self.openai_available:
				logger.warning("OpenAI backend requested but not available.")
			else:
				outputs["openai"] = self._generate_openai(prompt, config)
		if not outputs:
			raise RuntimeError("Requested providers not available.")
		return outputs

	# ------------------------------------------------------------------
	# Internal backend generation helpers
	# ------------------------------------------------------------------
	def _generate_local(self, prompt: str, config: GenerationConfig) -> List[Dict[str, Any]]:
		if self._local_pipeline is None:
			raise RuntimeError("Local pipeline not initialized.")
		gen_kwargs = dict(
			max_new_tokens=config.max_new_tokens,
			do_sample=True,
			temperature=config.temperature,
			top_p=config.top_p,
			top_k=config.top_k,
			num_return_sequences=config.n,
			pad_token_id=self._local_pipeline.tokenizer.eos_token_id,  # type: ignore[attr-defined]
		)
		if config.stop:
			# transformers doesn't have unified stop sequences prior to 4.46; simple substring trim here
			stop_strings = [config.stop] if isinstance(config.stop, str) else config.stop
		else:
			stop_strings = []
		sequences = self._local_pipeline(prompt, **gen_kwargs)  # type: ignore
		# Cast to expected structure (list of dicts with 'generated_text')
		seq_list = cast(List[Dict[str, Any]], sequences)
		processed: List[Dict[str, Any]] = []
		for seq in seq_list:
			text = str(seq.get("generated_text", ""))
			for s in stop_strings:
				if s in text:
					text = text.split(s)[0]
					break
			processed.append({"text": text, "raw": seq})
		return processed

	def _generate_openai(self, prompt: str, config: GenerationConfig) -> List[Dict[str, Any]]:
		client = self._openai_client
		if not client:
			raise RuntimeError("OpenAI client not initialized.")
		messages = [
			{"role": "system", "content": "You are a concise assistant."},
			{"role": "user", "content": prompt},
		]
		try:
			completion = client.chat.completions.create(  # type: ignore
				model=self.openai_model,
				messages=messages,  # type: ignore[arg-type]
				temperature=config.temperature,
				top_p=config.top_p,
				n=config.n,
				max_tokens=config.max_new_tokens,
				stop=config.stop,  # type: ignore[arg-type]
				presence_penalty=config.presence_penalty,
				frequency_penalty=config.frequency_penalty,
			)
		except Exception as e:
			logger.error("OpenAI generation failed: %s", e)
			raise
		results: List[Dict[str, Any]] = []
		for choice in completion.choices:
			text = choice.message.content or ""
			results.append({"text": text, "raw": choice})
		return results


# --------------------------------------------------------------------------
# Simple CLI demo when running this file directly
# --------------------------------------------------------------------------
def _demo_cli():
	import argparse

	parser = argparse.ArgumentParser(description="Hybrid LLM generation demo")
	parser.add_argument("prompt", nargs="?", default="Once upon a time", help="Prompt to generate from")
	parser.add_argument("--local-dir", dest="local_dir", default=None, help="Local / HF model directory")
	parser.add_argument("--provider", dest="provider", default="both", choices=["local", "openai", "both", "auto"], help="Provider to use")
	parser.add_argument("--max-new", dest="max_new", type=int, default=120, help="Max new tokens")
	parser.add_argument("--n", dest="n", type=int, default=1, help="Number of generations")
	args = parser.parse_args()

	lm = HybridLanguageModel(local_model_dir=args.local_dir)
	cfg = GenerationConfig(max_new_tokens=args.max_new, n=args.n)
	outputs = lm.generate(args.prompt, provider=args.provider, config=cfg)
	for backend, gens in outputs.items():
		print(f"\n=== {backend.upper()} OUTPUT ===")
		for i, g in enumerate(gens, 1):
			print(f"[{i}] {g['text']}\n")


if __name__ == "__main__":  # pragma: no cover
	_demo_cli()