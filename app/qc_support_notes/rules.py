"""Quality check rules for HRD daily reports."""

import re
from typing import List, Dict, Optional
from datetime import datetime


# Default terms for various checks (can be overridden by settings)
DEFAULT_VAGUE_WHEN_TERMS = [
    "recently", "earlier this week", "last week", "this week", "earlier", 
    "sometime", "previously", "in the past", "earlier in the week",
    "recent days", "in recent days", "over the past week"
]

DEFAULT_VAGUE_WHERE_TERMS = [
    "near", "around", "in the area", "in the vicinity", "close to",
    "somewhere", "in the region", "in the general area", "approximate",
    "approximately"
]

DEFAULT_INTERPRETIVE_TERMS = [
    "arbitrary", "unlawful", "illegal", "intimidation", "targeted",
    "deliberate", "systematic", "retaliation", "collective punishment",
    "discriminatory", "excessive", "disproportionate", "violation"
]

DEFAULT_DEFINITIVE_VERBS = [
    "confirmed", "established", "proved", "verified", "determined",
    "ascertained", "validated"
]

DEFAULT_FOLLOW_UP_INDICATORS = [
    "monitoring", "follow-up", "follow up", "verification", "engagement",
    "referral", "escalation", "investigation", "will monitor", "will follow",
    "continue to monitor", "further investigation"
]


def check_missing_when(text: str, vague_when_terms: List[str]) -> List[Dict]:
    """Check for vague temporal references without specific dates.
    
    Args:
        text: The report text to check.
        vague_when_terms: List of vague temporal terms to flag.
        
    Returns:
        List of issue dicts.
    """
    issues = []
    text_lower = text.lower()
    
    for term in vague_when_terms:
        pattern = rf'\b{re.escape(term)}\b'
        for match in re.finditer(pattern, text_lower):
            # Check if there's a date nearby (within 50 chars)
            start_pos = max(0, match.start() - 50)
            end_pos = min(len(text), match.end() + 50)
            context = text[start_pos:end_pos]
            
            # Look for date patterns
            date_patterns = [
                r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',  # DD/MM/YYYY
                r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',  # YYYY-MM-DD
                r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}',  # Month Day
            ]
            
            has_date = any(re.search(pattern, context, re.IGNORECASE) for pattern in date_patterns)
            
            if not has_date:
                # Find the actual match in original text (case-sensitive)
                orig_match = re.search(re.escape(term), text[start_pos:end_pos], re.IGNORECASE)
                if orig_match:
                    actual_start = start_pos + orig_match.start()
                    actual_end = start_pos + orig_match.end()
                    evidence = text[max(0, actual_start-30):min(len(text), actual_end+30)]
                    
                    issues.append({
                        "key": "missing_when",
                        "message": "Consider adding a specific date to clarify when this occurred.",
                        "evidence": evidence.strip(),
                        "location": {"start_char": actual_start, "end_char": actual_end},
                        "severity": "note"
                    })
    
    return issues


def check_vague_where(text: str, vague_where_terms: List[str]) -> List[Dict]:
    """Check for vague geographic references without administrative units.
    
    Args:
        text: The report text to check.
        vague_where_terms: List of vague geographic terms to flag.
        
    Returns:
        List of issue dicts.
    """
    issues = []
    text_lower = text.lower()
    
    # Common admin unit indicators
    admin_indicators = [
        "county", "payam", "boma", "state", "village", "town", "city",
        "administrative area", "admin unit"
    ]
    
    for term in vague_where_terms:
        pattern = rf'\b{re.escape(term)}\b'
        for match in re.finditer(pattern, text_lower):
            # Check if there's an admin unit mentioned nearby (within 100 chars)
            start_pos = max(0, match.start() - 100)
            end_pos = min(len(text), match.end() + 100)
            context = text_lower[start_pos:end_pos]
            
            has_admin_unit = any(indicator in context for indicator in admin_indicators)
            
            if not has_admin_unit:
                # match.start() and match.end() are positions in text_lower, which should match original text
                actual_start = match.start()
                actual_end = match.end()
                evidence = text[max(0, actual_start-40):min(len(text), actual_end+40)]
                
                issues.append({
                    "key": "where_vague",
                    "message": "It may help to specify the administrative unit (County, Payam, Boma) for clarity.",
                    "evidence": evidence.strip(),
                    "location": {"start_char": actual_start, "end_char": actual_end},
                    "severity": "note"
                })
    
    return issues


def check_vague_who(text: str) -> List[Dict]:
    """Check for overly generic actor descriptions.
    
    Args:
        text: The report text to check.
        
    Returns:
        List of issue dicts.
    """
    issues = []
    
    # Generic actor patterns that might need more specificity
    generic_patterns = [
        (r'\barmed\s+men\b', 'Consider specifying the group or institution level if safe to do so.'),
        (r'\bunknown\s+(?:assailants?|attackers?|perpetrators?)\b', 'If possible, add any identifying information available.'),
        (r'\bunidentified\s+(?:individuals?|persons?|people)\b', 'Consider adding any available descriptive details.'),
    ]
    
    for pattern, message in generic_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            evidence = text[max(0, match.start()-40):min(len(text), match.end()+40)]
            
            issues.append({
                "key": "who_vague",
                "message": message,
                "evidence": evidence.strip(),
                "location": {"start_char": match.start(), "end_char": match.end()},
                "severity": "note"
            })
    
    return issues


def check_facts_analysis_mixing(text: str, interpretive_terms: List[str]) -> List[Dict]:
    """Check for sentences mixing factual narration with interpretive conclusions.
    
    Args:
        text: The report text to check.
        interpretive_terms: List of interpretive/legal conclusion terms to flag.
        
    Returns:
        List of issue dicts.
    """
    issues = []
    text_lower = text.lower()
    
    # Split into sentences
    sentences = re.split(r'[.!?]+', text)
    sentence_starts = []
    current_pos = 0
    for sent in sentences:
        if sent.strip():
            sentence_starts.append(current_pos)
            current_pos += len(sent) + 1
    
    for i, sentence in enumerate(sentences):
        sentence_lower = sentence.lower()
        
        # Check if sentence contains interpretive terms
        found_terms = []
        for term in interpretive_terms:
            if re.search(rf'\b{re.escape(term)}\b', sentence_lower):
                found_terms.append(term)
        
        if found_terms:
            # Check if sentence has attribution (according to, reportedly, sources indicate)
            attribution_patterns = [
                r'according\s+to',
                r'reportedly',
                r'sources?\s+(?:indicate|report|state|say)',
                r'witnesses?\s+(?:report|indicate|state)',
                r'information\s+(?:indicates|suggests)',
            ]
            
            has_attribution = any(re.search(pattern, sentence_lower) for pattern in attribution_patterns)
            
            if not has_attribution:
                start_pos = sentence_starts[i] if i < len(sentence_starts) else 0
                end_pos = start_pos + len(sentence)
                evidence = sentence.strip()
                
                issues.append({
                    "key": "facts_analysis_mix",
                    "message": "Consider separating factual narrative from assessment, or attributing the assessment to sources.",
                    "evidence": evidence,
                    "location": {"start_char": start_pos, "end_char": end_pos},
                    "severity": "attention"
                })
    
    return issues


def check_corroboration_language(text: str, definitive_verbs: List[str]) -> List[Dict]:
    """Check for definitive verbs without source framing.
    
    Args:
        text: The report text to check.
        definitive_verbs: List of definitive verbs to flag.
        
    Returns:
        List of issue dicts.
    """
    issues = []
    text_lower = text.lower()
    
    for verb in definitive_verbs:
        pattern = rf'\b{re.escape(verb)}\b'
        for match in re.finditer(pattern, text_lower):
            # Check for source framing within 100 chars before
            start_check = max(0, match.start() - 100)
            context_before = text_lower[start_check:match.start()]
            
            attribution_patterns = [
                r'according\s+to',
                r'reportedly',
                r'sources?\s+(?:indicate|report|state|say)',
                r'information\s+(?:indicates|suggests)',
            ]
            
            has_attribution = any(re.search(pattern, context_before) for pattern in attribution_patterns)
            
            if not has_attribution:
                # Find original match in the original text (case-sensitive)
                actual_start = match.start()  # match.start() is relative to text_lower
                actual_end = match.end()  # match.end() is relative to text_lower
                
                # Get evidence context
                evidence_start = max(0, actual_start - 50)
                evidence_end = min(len(text), actual_end + 50)
                evidence = text[evidence_start:evidence_end]
                
                issues.append({
                    "key": "corroboration_language",
                    "message": "For clarity, consider adding light qualifiers such as 'according to sources' or 'reportedly'.",
                    "evidence": evidence.strip(),
                    "location": {"start_char": actual_start, "end_char": actual_end},
                    "severity": "note"
                })
    
    return issues


def check_action_follow_up(text: str, follow_up_indicators: List[str]) -> List[Dict]:
    """Check if report mentions follow-up or actions taken.
    
    Args:
        text: The report text to check.
        follow_up_indicators: List of phrases that indicate follow-up.
        
    Returns:
        List of issue dicts (empty list if follow-up is found, one issue if not).
    """
    text_lower = text.lower()
    
    # Check for any follow-up indicators
    for indicator in follow_up_indicators:
        if re.search(rf'\b{re.escape(indicator)}\b', text_lower):
            return []  # Follow-up found, no issue
    
    # No follow-up found
    return [{
        "key": "missing_follow_up",
        "message": "Optional refinement: consider adding a short line indicating monitoring, verification, engagement, referral, or escalation.",
        "evidence": "",  # No specific location
        "location": None,
        "severity": "note"
    }]


def detect_header_info(text: str, metadata: Optional[Dict]) -> Dict:
    """Detect field office and report date from text if not in metadata.
    
    Args:
        text: The report text.
        metadata: Optional metadata dict that may already contain field_office, report_date.
        
    Returns:
        Dict with detected_header info.
    """
    detected = {}
    
    if metadata:
        if "field_office" in metadata:
            detected["field_office"] = metadata["field_office"]
        if "report_date" in metadata:
            detected["report_date"] = metadata["report_date"]
    
    # Try to detect from text if not in metadata
    if "field_office" not in detected:
        field_offices = [
            "Bor", "Bentiu", "Rumbek", "Yei", "Yambio", "Aweil",
            "FOT", "Juba", "Torit", "Wau", "Malakal"
        ]
        for office in field_offices:
            if re.search(rf'\b{re.escape(office)}\b', text, re.IGNORECASE):
                detected["field_office"] = office
                break
    
    if "report_date" not in detected:
        # Try to find date patterns in first 500 chars (header area)
        header_text = text[:500]
        date_patterns = [
            (r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}', '%d/%m/%Y'),
            (r'\d{4}[/-]\d{1,2}[/-]\d{1,2}', '%Y-%m-%d'),
            (r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}', None),
        ]
        
        for pattern, _ in date_patterns:
            match = re.search(pattern, header_text, re.IGNORECASE)
            if match:
                # Just extract the matched string, don't try to parse
                detected["report_date"] = match.group(0)
                break
    
    return detected if detected else None


def run_all_checks(
    text: str,
    settings: Dict
) -> List[Dict]:
    """Run all quality checks on the report text.
    
    Args:
        text: The report text to check.
        settings: Settings dict with configuration options.
            - check_missing_when: bool (default True)
            - check_vague_where: bool (default True)
            - check_vague_who: bool (default True)
            - check_facts_analysis: bool (default True)
            - check_corroboration: bool (default True)
            - check_follow_up: bool (default True)
            - vague_when_terms: list[str] (optional)
            - vague_where_terms: list[str] (optional)
            - interpretive_terms: list[str] (optional)
            - definitive_verbs: list[str] (optional)
            - follow_up_indicators: list[str] (optional)
        
    Returns:
        List of all issues found.
    """
    vague_when_terms = settings.get("vague_when_terms", DEFAULT_VAGUE_WHEN_TERMS)
    vague_where_terms = settings.get("vague_where_terms", DEFAULT_VAGUE_WHERE_TERMS)
    interpretive_terms = settings.get("interpretive_terms", DEFAULT_INTERPRETIVE_TERMS)
    definitive_verbs = settings.get("definitive_verbs", DEFAULT_DEFINITIVE_VERBS)
    follow_up_indicators = settings.get("follow_up_indicators", DEFAULT_FOLLOW_UP_INDICATORS)
    
    all_issues = []
    
    if settings.get("check_missing_when", True):
        all_issues.extend(check_missing_when(text, vague_when_terms))
    
    if settings.get("check_vague_where", True):
        all_issues.extend(check_vague_where(text, vague_where_terms))
    
    if settings.get("check_vague_who", True):
        all_issues.extend(check_vague_who(text))
    
    if settings.get("check_facts_analysis", True):
        all_issues.extend(check_facts_analysis_mixing(text, interpretive_terms))
    
    if settings.get("check_corroboration", True):
        all_issues.extend(check_corroboration_language(text, definitive_verbs))
    
    if settings.get("check_follow_up", True):
        all_issues.extend(check_action_follow_up(text, follow_up_indicators))
    
    return all_issues

