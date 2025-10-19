from v010.abstraction.retriever_service import RetrieverService
from v010.utils.embedding.formatter import format_answer


class BasicRetrieverService(RetrieverService):

    def __init__(self, model_name: str, api_key: str, **kwargs):
        super().__init__(model_name, api_key, **kwargs)

    def retrieve(self, query: str) -> str:
        # Basic retrieval logic (placeholder)
        return f"Retrieved results for query: {query}"
    
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
                answer = format_answer(query, results)
                answer = answer + "\n\n### Synthesized Answer (" + provider + ")\n\n" + model_answer
                return answer
            except Exception as e:
                # Fall back to simple reference answer
                return format_answer(query, results) + f"\n\n*LLM synthesis unavailable: {e}*"
        else:
            # Fallback: return formatted context
            return format_answer(query, results)
        