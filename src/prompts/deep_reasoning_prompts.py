from typing import List, Dict

PERSPECTIVE_ANALYSIS_PROMPT = """Analyze the following pentesting situation from a {perspective} perspective:

Situation: {situation}
Context: {context}

Think through the following aspects:
1. What is the current situation telling us?
2. What potential risks should we be concerned about?
3. What opportunities can we identify?
4. What actions would be most effective?
5. How does the historical context influence our analysis?

Express your thoughts naturally, as if you're thinking out loud. Consider both immediate and long-term implications.

Important:
1. Stay focused on actionable insights
2. Be specific and avoid assumptions
3. Consider all angles of the situation
4. Think through consequences
5. Prioritize based on impact and feasibility
"""

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
Keep the text clean and simple."""

def _format_perspectives(self, perspectives_results: List[Dict]) -> str:
    """
    Formats the perspectives for inclusion in the synthesis prompt
    """
    formatted = []
    for p in perspectives_results:
        formatted.append(f"From {p['perspective']} viewpoint:\n{p['analysis']}\n")
    return "\n".join(formatted)

def get_perspective_prompt(language: str) -> str:
    """Returns the perspective prompt in the configured language"""
    if language.startswith('pt'):
        return """Analyze the following pentesting situation from a {perspective} perspective:

Situation: {situation}
Context: {context}

Think through the following aspects:
1. What is the current situation telling us?
2. What potential risks should we be concerned about?
3. What opportunities can we identify?
4. What actions would be most effective?
5. How does the historical context influence our analysis?

Express your thoughts naturally, as if you're thinking out loud. Consider both immediate and long-term implications.

Important:
1. Stay focused on actionable insights
2. Be specific and avoid assumptions
3. Consider all angles of the situation
4. Think through consequences
5. Prioritize based on impact and feasibility"""
    else:
        return PERSPECTIVE_ANALYSIS_PROMPT  # Default to English version

def get_synthesis_prompt(language: str) -> str:
    """Returns the synthesis prompt in the configured language"""
    if language.startswith('pt'):
        return """Let's synthesize these different perspectives into a unified analysis:

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
Do not use JSON format in your response."""
    else:
        return SYNTHESIS_PROMPT  # Default to English version
