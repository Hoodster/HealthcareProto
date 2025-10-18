import dataclasses
from typing import List, Dict

def romat_query(self, query: str) -> str:
    return f"Retrieve sections related to '{query}' from the medical guidelines."


def format_answer(self, query: str, results: List[Dict]) -> str:
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