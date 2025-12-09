from dataclasses import dataclass
from typing import List, Dict


@dataclass
class SourceInfo:
    key: int
    section: str
    source_file: str
    source_website: str
    page: int

@dataclass
class FormattedMetaAnswer:
    answer_text: str
    sources: List[SourceInfo]

@dataclass
class Chunk:
    section: str
    source_file: str
    page: int
    text: str
    safety_score: int

def v010_format_answer(results: List[Chunk]) -> FormattedMetaAnswer:
    """Format the answer based on retrieved chunks"""
    answer = ""
    sources = []
    
    for i, res in enumerate(results):
        s_info = SourceInfo(
            key = i + 1,
            section=res.section if res.section else f"Unknown section {i + 1}",
            source_file=res.source_file if res.source_file else "Unknown source",
            source_website="https://www.google.com/",
            page=res.page
        )
        sources.append(s_info)
        
        answer += f"{res.text}. [{s_info.key}] "
        
        section_title = res.section if res.section else f"Unknown section {i + 1}"
        source_file = res.source_file if res.source_file else "Unknown source"

        answer += f"### {section_title}\n"
        answer += f"*Source: {source_file}*"

    answerFormat = FormattedMetaAnswer(
        answer_text=answer,
        sources=sources
    )
    return answerFormat


def format_answer(query: str, results: List[Dict]) -> str:
    """Format the answer based on retrieved chunks"""
    answer = ""

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
        # fall back to 'chunk' if 'text' not present
        content = res.get("text") or res.get("chunk") or ""
        answer += f"{content[:1200]}{'...' if len(content) > 1200 else ''}\n\n"

        # Add safety score information if available
        if "safety_score" in res and res["safety_score"] > 0:
            answer += f"*This section contains {res['safety_score']} safety-related references*\n\n"

    answer += "---\n"
    answer += "Note: This information is extracted directly from the processed guidelines. Always consult the full guidelines and a healthcare professional for complete information."

    return answer