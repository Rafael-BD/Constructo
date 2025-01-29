PERSPECTIVE_ANALYSIS_PROMPT = """Analyze the following pentesting situation from a {perspective} perspective:

Situation: {situation}
Context: {context}

Format your response EXACTLY as:

{{
    "analysis": "your detailed analysis",
    "risks": ["list", "of", "identified", "risks"],
    "opportunities": ["list", "of", "opportunities"],
    "recommended_actions": ["prioritized", "action", "list"],
    "confidence_level": 0-100
}}

Important:
1. Maintain valid JSON syntax
2. Escape quotes properly
3. Use double quotes for all strings
4. Keep arrays simple with string items
5. Never add commentary outside the JSON"""

SYNTHESIS_PROMPT = """Analyze and synthesize these perspectives:

Situation: {situation}
Perspectives: {perspectives}

Respond STRICTLY in this format:
{{
    "final_analysis": "combined analysis summary",
    "selected_approach": "chosen methodology",
    "action_plan": ["step1", "step2", "step3"],
    "risk_assessment": "final risk evaluation",
    "confidence_score": 0-100
}}

Rules:
1. Keep JSON valid above all else
2. Use only double quotes
3. No markdown formatting
4. Escape special characters
5. No comments outside JSON"""
