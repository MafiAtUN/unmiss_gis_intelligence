"""Core QC support notes generation logic."""

from typing import Dict, List, Optional
from app.qc_support_notes import rules
from app.qc_support_notes import redaction
from app.qc_support_notes.llm_analyzer import LLMQCAnalyzer
from app.qc_support_notes.nlp_analyzer import NLPAnalyzer


def generate_support_notes(
    issues: List[Dict],
    metadata: Optional[Dict] = None,
    detected_header: Optional[Dict] = None
) -> str:
    """Generate the formatted support notes text.
    
    Args:
        issues: List of issue dicts.
        metadata: Optional metadata dict.
        detected_header: Optional detected header info.
        
    Returns:
        Formatted support notes string.
    """
    lines = ["Methodology Support Notes"]
    lines.append("")  # Empty line
    
    # Add header info if available
    header_info = detected_header or metadata or {}
    field_office = header_info.get("field_office")
    report_date = header_info.get("report_date")
    
    if field_office or report_date:
        header_parts = []
        if field_office:
            header_parts.append(f"Field office: {field_office}")
        if report_date:
            header_parts.append(f"Report date: {report_date}")
        if header_parts:
            lines.append(" | ".join(header_parts))
            lines.append("")
    
    # Add issues
    if issues:
        for issue in issues:
            message = issue.get("message", "")
            lines.append(f"• {message}")
            # Optionally add second line if there's more detail needed
            if issue.get("severity") == "attention":
                lines.append("  (May require attention)")
    else:
        lines.append("No immediate refinements identified.")
    
    return "\n".join(lines)


def apply_redactions_to_evidence(issues: List[Dict], redactions: List[Dict]) -> List[Dict]:
    """Apply redactions to evidence in issues.
    
    Args:
        issues: List of issue dicts.
        redactions: List of redaction dicts.
        
    Returns:
        Issues with redacted evidence.
    """
    if not redactions:
        return issues
    
    processed_issues = []
    for issue in issues:
        evidence = issue.get("evidence", "")
        if not evidence:
            processed_issues.append(issue)
            continue
        
        # Apply redactions to evidence
        redacted_evidence = redaction.apply_redactions(evidence, redactions)
        
        issue_copy = issue.copy()
        issue_copy["evidence"] = redacted_evidence
        processed_issues.append(issue_copy)
    
    return processed_issues


def run_qc_support_notes(report_payload: Dict) -> Dict:
    """Main function to run QC support notes generation.
    
    Args:
        report_payload: Dict containing:
            - report_text: str (required) - The report text to analyze
            - metadata: dict (optional) - May include field_office, report_date, report_type
            - confidentiality_level: str (optional) - Default "CONFIDENTIAL"
            - settings: dict (optional) - Feature flags and thresholds
                - analysis_mode: str - "regex", "ollama", or "openai" (default: "regex")
                - llm_model: str (optional) - Model name for LLM modes
    
    Returns:
        Dict with:
            - support_notes: str - The formatted QC note
            - issues: list[dict] - List of issues found
            - redactions: list[dict] - Detected PII with type and masked form
            - detected_header: dict (optional) - Field office and report date if inferred
            - analysis_mode: str - The mode used for analysis
    """
    # Extract inputs
    report_text = report_payload.get("report_text", "")
    if not report_text:
        return {
            "support_notes": "Methodology Support Notes\n\nNo report text provided.",
            "issues": [],
            "redactions": [],
            "detected_header": None,
            "analysis_mode": "none"
        }
    
    metadata = report_payload.get("metadata", {})
    confidentiality_level = report_payload.get("confidentiality_level", "CONFIDENTIAL")
    settings = report_payload.get("settings", {})
    
    # Determine analysis mode
    analysis_mode = settings.get("analysis_mode", "regex")
    llm_model = settings.get("llm_model")
    
    # Set defaults for settings
    default_settings = {
        "enable_confidentiality_scan": True,
        "show_evidence_by_default": False,
        "vague_when_terms": rules.DEFAULT_VAGUE_WHEN_TERMS,
        "vague_where_terms": rules.DEFAULT_VAGUE_WHERE_TERMS,
        "interpretive_terms": rules.DEFAULT_INTERPRETIVE_TERMS,
        "check_missing_when": True,
        "check_vague_where": True,
        "check_vague_who": True,
        "check_facts_analysis": True,
        "check_corroboration": True,
        "check_follow_up": True,
    }
    merged_settings = {**default_settings, **settings}
    
    # Detect PII and create redactions
    enable_confidentiality = merged_settings.get("enable_confidentiality_scan", True)
    detected_redactions = redaction.detect_pii(report_text, enable_confidentiality)
    
    # Run quality checks based on mode
    all_issues = []
    
    if analysis_mode == "regex":
        # Use rule-based regex checks
        all_issues = rules.run_all_checks(report_text, merged_settings)
    elif analysis_mode == "nlp":
        # Use NLP-based analysis (spaCy)
        try:
            nlp_model = settings.get("nlp_model", "en_core_web_sm")
            nlp_analyzer = NLPAnalyzer(model_name=nlp_model)
            if nlp_analyzer.available:
                nlp_issues = nlp_analyzer.analyze_report(report_text, merged_settings)
            else:
                # Fallback to regex if NLP not available
                nlp_issues = rules.run_all_checks(report_text, merged_settings)
                analysis_mode = "regex"  # Note that we fell back
        except Exception as e:
            # Fallback to regex on error
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"NLP analysis failed, falling back to regex: {e}")
            nlp_issues = rules.run_all_checks(report_text, merged_settings)
            analysis_mode = "regex"
        
        # Also run regex checks if enabled (hybrid mode) and NLP was actually used
        if merged_settings.get("hybrid_mode", False) and analysis_mode == "nlp":
            regex_issues = rules.run_all_checks(report_text, merged_settings)
            # Merge issues, avoiding duplicates
            all_issues = nlp_issues.copy()
            for regex_issue in regex_issues:
                # Check if similar issue already exists
                is_duplicate = False
                for nlp_issue in nlp_issues:
                    if (regex_issue.get("key") == nlp_issue.get("key") and
                        abs(regex_issue.get("location", {}).get("start_char", 0) - 
                            nlp_issue.get("location", {}).get("start_char", 0)) < 50):
                        is_duplicate = True
                        break
                if not is_duplicate:
                    all_issues.append(regex_issue)
        else:
            all_issues = nlp_issues
    elif analysis_mode in ["ollama", "openai"]:
        # Use LLM-based analysis
        llm_issues = []
        try:
            llm_analyzer = LLMQCAnalyzer(mode=analysis_mode, model=llm_model)
            if llm_analyzer.enabled:
                llm_issues = llm_analyzer.analyze_report(report_text, merged_settings)
            else:
                # Fallback to regex if LLM not available
                llm_issues = rules.run_all_checks(report_text, merged_settings)
                analysis_mode = "regex"  # Note that we fell back
        except Exception as e:
            # Fallback to regex on error
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"LLM analysis failed, falling back to regex: {e}")
            llm_issues = rules.run_all_checks(report_text, merged_settings)
            analysis_mode = "regex"
        
        # Also run regex checks if enabled (hybrid mode) and LLM was actually used
        if merged_settings.get("hybrid_mode", False) and analysis_mode in ["ollama", "openai"]:
            regex_issues = rules.run_all_checks(report_text, merged_settings)
            # Merge issues, avoiding duplicates
            all_issues = llm_issues.copy()
            for regex_issue in regex_issues:
                # Check if similar issue already exists
                is_duplicate = False
                for llm_issue in llm_issues:
                    if (regex_issue.get("key") == llm_issue.get("key") and
                        abs(regex_issue.get("location", {}).get("start_char", 0) - 
                            llm_issue.get("location", {}).get("start_char", 0)) < 50):
                        is_duplicate = True
                        break
                if not is_duplicate:
                    all_issues.append(regex_issue)
        else:
            all_issues = llm_issues
    else:
        # Fallback to regex
        all_issues = rules.run_all_checks(report_text, merged_settings)
        analysis_mode = "regex"
    
    # Apply redactions to evidence in issues
    redacted_issues = apply_redactions_to_evidence(all_issues, detected_redactions)
    
    # Detect header info
    detected_header = rules.detect_header_info(report_text, metadata)
    
    # Generate support notes
    support_notes = generate_support_notes(redacted_issues, metadata, detected_header)
    
    # Format redactions for output (without start/end positions)
    formatted_redactions = [
        {
            "type": r["type"],
            "masked": r["masked"]
        }
        for r in detected_redactions
    ]
    
    return {
        "support_notes": support_notes,
        "issues": redacted_issues,
        "redactions": formatted_redactions,
        "detected_header": detected_header,
        "analysis_mode": analysis_mode
    }

