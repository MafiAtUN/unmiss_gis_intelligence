"""LLM-based quality control analyzer for HRD reports."""

import json
import requests
from typing import Dict, List, Optional
from openai import AzureOpenAI
from app.core.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    ENABLE_OLLAMA,
    AZURE_FOUNDRY_ENDPOINT,
    AZURE_FOUNDRY_API_KEY,
    AZURE_OPENAI_DEPLOYMENT,
    AZURE_UNMISS_DEPLOYMENT_GPT41_MINI,
    AZURE_OPENAI_API_VERSION,
)
from app.utils.logging import log_error, log_structured


class LLMQCAnalyzer:
    """LLM-based quality control analyzer for HRD reports."""
    
    def __init__(self, mode: str = "ollama", model: Optional[str] = None):
        """
        Initialize LLM QC analyzer.
        
        Args:
            mode: Analysis mode - "ollama", "openai", or "regex"
            model: Model name (for Ollama) or deployment name (for OpenAI)
        """
        self.mode = mode
        self.model = model
        
        if mode == "ollama":
            self.base_url = OLLAMA_BASE_URL.rstrip("/")
            self.model = model or OLLAMA_MODEL or "llama3.2:3b"
            self.enabled = ENABLE_OLLAMA and self._check_ollama_availability()
        elif mode == "openai":
            self.enabled = bool(AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY)
            if self.enabled:
                self.client = AzureOpenAI(
                    api_key=AZURE_FOUNDRY_API_KEY,
                    api_version=AZURE_OPENAI_API_VERSION,
                    azure_endpoint=AZURE_FOUNDRY_ENDPOINT
                )
                self.deployment = model or AZURE_UNMISS_DEPLOYMENT_GPT41_MINI or "gpt-4.1-mini"
            else:
                self.client = None
                self.deployment = None
        else:
            self.enabled = False
    
    def _check_ollama_availability(self) -> bool:
        """Check if Ollama is available."""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except Exception:
            return False
    
    def analyze_report(
        self,
        report_text: str,
        settings: Dict
    ) -> List[Dict]:
        """
        Analyze report using LLM and return issues.
        
        Args:
            report_text: The report text to analyze.
            settings: QC settings dict.
            
        Returns:
            List of issue dicts.
        """
        if not self.enabled:
            return []
        
        if self.mode == "ollama":
            return self._analyze_with_ollama(report_text, settings)
        elif self.mode == "openai":
            return self._analyze_with_openai(report_text, settings)
        else:
            return []
    
    def _analyze_with_ollama(self, report_text: str, settings: Dict) -> List[Dict]:
        """Analyze report using Ollama."""
        system_prompt = """You are a UN Human Rights Officer providing supportive quality control feedback for HRD daily reports. 
Analyze the report and identify areas that could be improved. Focus on:
1. Missing or vague 5Ws (When, Where, Who, How, Why)
2. Mixing of facts with analysis/interpretation without attribution
3. Missing source framing for definitive statements
4. Missing follow-up or action items
5. Potential confidentiality issues (PII)

Return a JSON object with this structure:
{
  "issues": [
    {
      "key": "issue_key",
      "message": "supportive one-liner suggestion",
      "evidence": "excerpt from text (redacted if PII)",
      "location": {"start_char": 0, "end_char": 100},
      "severity": "attention" or "note"
    }
  ]
}

Use supportive, peer-like language. Avoid evaluative words like "poor", "weak", "insufficient". 
Use: "consider", "it may help", "optional refinement", "for clarity".

Severity levels:
- "attention": Issues that may require attention (facts/analysis mixing, missing attribution)
- "note": Optional refinements (vague terms, missing follow-up)

Return ONLY valid JSON, no other text."""

        # Limit text length for Ollama efficiency (keep first 8000 chars)
        text_to_analyze = report_text[:8000] if len(report_text) > 8000 else report_text
        
        user_prompt = f"""Analyze this HRD daily report for quality control:

{text_to_analyze}

Settings:
- Enable confidentiality scan: {settings.get('enable_confidentiality_scan', True)}
- Vague when terms: {settings.get('vague_when_terms', [])}
- Vague where terms: {settings.get('vague_where_terms', [])}
- Interpretive terms: {settings.get('interpretive_terms', [])}
"""

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": f"{system_prompt}\n\n{user_prompt}",
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.2,  # Low temperature for consistent analysis
                        "num_predict": 2000,  # Allow longer responses
                    }
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result.get("response", "").strip()
                
                # Parse JSON
                try:
                    parsed = json.loads(content)
                except json.JSONDecodeError:
                    # Try to extract JSON from markdown code blocks
                    if "```json" in content:
                        json_start = content.find("```json") + 7
                        json_end = content.find("```", json_start)
                        content = content[json_start:json_end].strip()
                        parsed = json.loads(content)
                    else:
                        return []
                
                issues = parsed.get("issues", [])
                # Validate and clean issues
                validated_issues = []
                for issue in issues:
                    if isinstance(issue, dict) and "key" in issue and "message" in issue:
                        validated_issues.append({
                            "key": issue.get("key", "unknown"),
                            "message": issue.get("message", ""),
                            "evidence": issue.get("evidence", ""),
                            "location": issue.get("location"),
                            "severity": issue.get("severity", "note")
                        })
                
                return validated_issues
        except Exception as e:
            log_error(e, {
                "module": "qc_support_notes.llm_analyzer",
                "function": "_analyze_with_ollama",
                "mode": "ollama"
            })
        
        return []
    
    def _analyze_with_openai(self, report_text: str, settings: Dict) -> List[Dict]:
        """Analyze report using OpenAI/Azure."""
        system_prompt = """You are a UN Human Rights Officer providing supportive quality control feedback for HRD daily reports. 
Analyze the report and identify areas that could be improved. Focus on:
1. Missing or vague 5Ws (When, Where, Who, How, Why)
2. Mixing of facts with analysis/interpretation without attribution
3. Missing source framing for definitive statements
4. Missing follow-up or action items
5. Potential confidentiality issues (PII)

Return a JSON object with this structure:
{
  "issues": [
    {
      "key": "issue_key",
      "message": "supportive one-liner suggestion",
      "evidence": "excerpt from text (redacted if PII)",
      "location": {"start_char": 0, "end_char": 100},
      "severity": "attention" or "note"
    }
  ]
}

Use supportive, peer-like language. Avoid evaluative words like "poor", "weak", "insufficient". 
Use: "consider", "it may help", "optional refinement", "for clarity".

Severity levels:
- "attention": Issues that may require attention (facts/analysis mixing, missing attribution)
- "note": Optional refinements (vague terms, missing follow-up)

Return ONLY valid JSON, no other text."""

        user_prompt = f"""Analyze this HRD daily report for quality control:

{report_text}

Settings:
- Enable confidentiality scan: {settings.get('enable_confidentiality_scan', True)}
- Vague when terms: {settings.get('vague_when_terms', [])}
- Vague where terms: {settings.get('vague_where_terms', [])}
- Interpretive terms: {settings.get('interpretive_terms', [])}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            
            content = response.choices[0].message.content
            parsed = json.loads(content)
            
            issues = parsed.get("issues", [])
            # Validate and clean issues
            validated_issues = []
            for issue in issues:
                if isinstance(issue, dict) and "key" in issue and "message" in issue:
                    validated_issues.append({
                        "key": issue.get("key", "unknown"),
                        "message": issue.get("message", ""),
                        "evidence": issue.get("evidence", ""),
                        "location": issue.get("location"),
                        "severity": issue.get("severity", "note")
                    })
            
            return validated_issues
        except Exception as e:
            log_error(e, {
                "module": "qc_support_notes.llm_analyzer",
                "function": "_analyze_with_openai",
                "mode": "openai"
            })
        
        return []

