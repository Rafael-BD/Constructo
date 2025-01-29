PERSPECTIVE_ANALYSIS_PROMPT = """Analyze the following pentesting situation from a {perspective} perspective:

Situation: {situation}
Context: {context}

Consider the following aspects:
1. Risks and opportunities
2. Potential vulnerabilities
3. Exploitation strategies
4. Potential impact
5. Recommended next steps

Format your response in JSON:
{
    "analysis": "your detailed analysis",
    "risks": ["identified risks list"],
    "opportunities": ["opportunities list"],
    "recommended_actions": ["prioritized action list"],
    "confidence_level": "0-100"
}"""

SYNTHESIS_PROMPT = """Analyze and synthesize the following perspectives for the situation:

Situation: {situation}

Perspectives:
{perspectives}

Provide a final analysis that:
1. Combines the most valuable insights from each perspective
2. Identifies the best approach considering risk vs. benefit
3. Proposes a concrete action plan

Respond in JSON format:
{
    "final_analysis": "combined analysis",
    "selected_approach": "chosen approach",
    "action_plan": ["detailed steps"],
    "risk_assessment": "final risk assessment",
    "confidence_score": "0-100"
}""" 