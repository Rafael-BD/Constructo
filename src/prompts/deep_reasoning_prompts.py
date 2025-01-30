from typing import List, Dict

PERSPECTIVE_ANALYSIS_PROMPT = """Analyze this pentesting situation from a {perspective} perspective:

Situation: {situation}
Context: {context}

Consider:
1. Key risks and immediate concerns
2. Most promising opportunities
3. Most effective actions
4. Critical context implications
5. Priority recommendations

Be concise and focus on the most important points. Limit your response to 14 lines.
Express your thoughts naturally, but be direct and specific.

Important: Provide your analysis in {language}."""

SYNTHESIS_PROMPT = """Let's synthesize these different perspectives into a unified analysis:

Situation: {situation}

I've analyzed this from multiple angles. Let me think through what we've learned...

Consider:
1. What common themes emerge from these perspectives?
2. Where do the approaches differ and why?
3. What's the most logical path forward?
4. What risks need special attention?
5. What should be our immediate next steps?

Perspectives to consider:
{perspectives}

Think through this carefully and provide a comprehensive analysis, focusing on:
- Key insights from each perspective
- Most important risks and opportunities
- Concrete action steps
- Critical considerations

Express your thoughts naturally, as if working through the problem step by step.
Do not use any special formatting or markdown in your response.
Keep the text clean and simple.

Important: Provide your synthesis in {language}."""

def _format_perspectives(self, perspectives_results: List[Dict]) -> str:
    """
    Formats the perspectives for inclusion in the synthesis prompt
    """
    formatted = []
    for p in perspectives_results:
        formatted.append(f"From {p['perspective']} viewpoint:\n{p['analysis']}\n")
    return "\n".join(formatted)

def get_perspective_prompt(language: str) -> str:
    """Returns the perspective prompt with language instruction"""
    return PERSPECTIVE_ANALYSIS_PROMPT

def get_synthesis_prompt(language: str) -> str:
    """Returns the synthesis prompt with language instruction"""
    return SYNTHESIS_PROMPT
