"""Chat helper for interacting with daily reports using various LLM models."""

import json
import requests
from typing import Optional, List, Dict
from openai import AzureOpenAI
from app.core.config import (
    OLLAMA_BASE_URL,
    ENABLE_OLLAMA,
    AZURE_FOUNDRY_ENDPOINT,
    AZURE_FOUNDRY_API_KEY,
    AZURE_OPENAI_API_VERSION,
    UNMISS_DEPLOYMENTS,
)
from app.utils.logging import log_error


def get_available_ollama_models(base_url: str = None) -> List[str]:
    """
    Get list of available Ollama models.
    
    Args:
        base_url: Ollama base URL (defaults to config)
        
    Returns:
        List of model names.
    """
    if base_url is None:
        from app.core.config import OLLAMA_BASE_URL
        base_url = OLLAMA_BASE_URL.rstrip("/")
    
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=2)
        if response.status_code == 200:
            data = response.json()
            models = []
            for model_info in data.get("models", []):
                model_name = model_info.get("name", "")
                if model_name:
                    models.append(model_name)
            return sorted(models)
    except Exception:
        pass
    
    return []


def chat_with_report(
    report_text: str,
    user_question: str,
    model_type: str,
    model_name: str
) -> str:
    """
    Chat with the daily report using specified model.
    
    Args:
        report_text: The daily report text.
        user_question: User's question about the report.
        model_type: "ollama", "openai", or other.
        model_name: Name of the model to use.
        
    Returns:
        Model's response.
    """
    if model_type == "ollama":
        return _chat_with_ollama(report_text, user_question, model_name)
    elif model_type == "openai":
        return _chat_with_openai(report_text, user_question, model_name)
    else:
        return "Unknown model type"


def _chat_with_ollama(report_text: str, user_question: str, model_name: str) -> str:
    """Chat using Ollama."""
    from app.core.config import OLLAMA_BASE_URL
    base_url = OLLAMA_BASE_URL.rstrip("/")
    
    # Limit report text for efficiency
    text_to_use = report_text[:6000] if len(report_text) > 6000 else report_text
    
    system_prompt = """You are a UN Human Rights Officer assistant. Answer questions about HRD daily reports based on the provided report text. 
Be concise, accurate, and focus on facts from the report. If information is not in the report, say so."""

    user_prompt = f"""Daily Report:
{text_to_use}

Question: {user_question}

Answer the question based on the report above."""

    try:
        response = requests.post(
            f"{base_url}/api/generate",
            json={
                "model": model_name,
                "prompt": f"{system_prompt}\n\n{user_prompt}",
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 1000,
                }
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result.get("response", "No response from model").strip()
    except Exception as e:
        log_error(e, {
            "module": "qc_support_notes.chat_helper",
            "function": "_chat_with_ollama",
            "model": model_name
        })
        return f"Error: {str(e)}"
    
    return "Error: Could not connect to Ollama"


def _chat_with_openai(report_text: str, user_question: str, model_name: str) -> str:
    """Chat using OpenAI/Azure."""
    if not (AZURE_FOUNDRY_ENDPOINT and AZURE_FOUNDRY_API_KEY):
        return "Error: Azure OpenAI credentials not configured"
    
    # Get deployment name
    deployment = UNMISS_DEPLOYMENTS.get(model_name, model_name)
    
    client = AzureOpenAI(
        api_key=AZURE_FOUNDRY_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
        azure_endpoint=AZURE_FOUNDRY_ENDPOINT
    )
    
    # Limit report text
    text_to_use = report_text[:8000] if len(report_text) > 8000 else report_text
    
    system_prompt = """You are a UN Human Rights Officer assistant. Answer questions about HRD daily reports based on the provided report text. 
Be concise, accurate, and focus on facts from the report. If information is not in the report, say so."""

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Daily Report:\n{text_to_use}\n\nQuestion: {user_question}\n\nAnswer the question based on the report above."}
            ],
            temperature=0.3,
            max_tokens=1000
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        log_error(e, {
            "module": "qc_support_notes.chat_helper",
            "function": "_chat_with_openai",
            "model": model_name
        })
        return f"Error: {str(e)}"

