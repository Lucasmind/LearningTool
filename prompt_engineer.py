"""
Prompt engineering templates for the three follow-up modes.
Builds lineage context by walking the parent chain.
"""


def build_lineage_context(session_data: dict, node_id: str) -> str:
    """Walk parent chain from node_id to root, collecting prompt+response pairs."""
    if not session_data or not node_id:
        return ""

    nodes = session_data.get("nodes", {})
    parts = []
    current_id = node_id

    while current_id and current_id in nodes:
        node = nodes[current_id]
        prompt = node.get("prompt_text", "")
        response = node.get("response_text", "")
        # Truncate long responses to avoid prompt bloat
        if len(response) > 1500:
            response = response[:1500] + "..."
        parts.append(f"User asked: {prompt}\nAI responded: {response}")
        current_id = node.get("parent_id")

    parts.reverse()  # Root first
    return "\n\n---\n\n".join(parts)


def build_prompt(
    mode: str,
    prompt_text: str,
    highlighted_text: str | None = None,
    user_question: str | None = None,
    session_data: dict | None = None,
    parent_node_id: str | None = None,
) -> str:
    """Build the engineered prompt based on mode."""

    if mode == "initial":
        return prompt_text

    lineage = build_lineage_context(session_data, parent_node_id)

    if mode == "explain":
        return _build_explain(lineage, highlighted_text or "")

    if mode == "deeper":
        return _build_deeper(highlighted_text or "")

    if mode == "question":
        return _build_question(lineage, highlighted_text or "", user_question or prompt_text)

    # Fallback
    return prompt_text


def _build_explain(lineage: str, highlighted_text: str) -> str:
    ctx = f"\n\nHere is the conversation so far:\n\n{lineage}" if lineage else ""
    return f"""You are a knowledgeable tutor. The user has been exploring a topic through a series of questions and answers.{ctx}

The user has highlighted the following text and wants to understand it better in context:
"{highlighted_text}"

Explain what this means in the context of the conversation above. Be clear and concise. Use examples if helpful. Format your response with clear headers and structure. Use markdown formatting with headers (##), bullet points, and bold text for emphasis."""


def _build_deeper(highlighted_text: str) -> str:
    return f"""You are a knowledgeable tutor explaining a concept from first principles.

Explain the concept: "{highlighted_text}"

Start from the fundamentals and build up. Assume the reader is intelligent but may not have background in this specific area. Cover:
1. What it is (clear definition)
2. Why it matters
3. How it works (key mechanisms or principles)
4. Real-world examples or analogies
5. Common misconceptions

Be thorough but clear. Format your response with clear headers and structure. Use markdown formatting with headers (##), bullet points, and bold text for emphasis."""


def _build_question(lineage: str, highlighted_text: str, question: str) -> str:
    ctx = f"\n\nHere is the conversation so far:\n\n{lineage}" if lineage else ""
    return f"""You are a knowledgeable tutor. The user has been exploring a topic through a series of questions and answers.{ctx}

The user highlighted the following text:
"{highlighted_text}"

And asks this question about it:
"{question}"

Answer the question clearly and concisely, drawing on the conversation context where relevant. Format your response with clear headers and structure. Use markdown formatting with headers (##), bullet points, and bold text for emphasis."""
