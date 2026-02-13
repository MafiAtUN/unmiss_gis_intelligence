"""NLP-based quality control analyzer using spaCy."""

import re
from typing import List, Dict, Optional

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

from app.qc_support_notes import rules
from app.utils.logging import log_error, log_structured


class NLPAnalyzer:
    """NLP-based QC analyzer using spaCy for linguistic analysis."""
    
    def __init__(self, model_name: str = "en_core_web_sm"):
        """
        Initialize NLP analyzer.
        
        Args:
            model_name: spaCy model name (default: en_core_web_sm)
        """
        self.available = SPACY_AVAILABLE
        self.nlp = None
        self.model_name = model_name
        
        if SPACY_AVAILABLE:
            try:
                self.nlp = spacy.load(model_name)
                log_structured("info", f"Loaded spaCy model: {model_name}")
            except OSError:
                # Model not found, try to use blank English model as fallback
                try:
                    self.nlp = spacy.blank("en")
                    log_structured("warning", f"spaCy model {model_name} not found, using blank model")
                except Exception as e:
                    log_error(e, {"module": "qc_support_notes.nlp_analyzer", "function": "__init__"})
                    self.available = False
    
    def analyze_report(
        self,
        report_text: str,
        settings: Dict
    ) -> List[Dict]:
        """
        Analyze report using NLP techniques.
        
        Args:
            report_text: The report text to analyze.
            settings: QC settings dict.
            
        Returns:
            List of issue dicts.
        """
        if not self.available or not self.nlp:
            # Fallback to regex if NLP not available
            return rules.run_all_checks(report_text, settings)
        
        all_issues = []
        
        # Process text with spaCy
        doc = self.nlp(report_text)
        
        # Run NLP-enhanced checks
        if settings.get("check_missing_when", True):
            all_issues.extend(self._check_vague_when_nlp(doc, settings))
        
        if settings.get("check_vague_where", True):
            all_issues.extend(self._check_vague_where_nlp(doc, settings))
        
        if settings.get("check_vague_who", True):
            all_issues.extend(self._check_vague_who_nlp(doc))
        
        if settings.get("check_facts_analysis", True):
            all_issues.extend(self._check_facts_analysis_nlp(doc, settings))
        
        if settings.get("check_corroboration", True):
            all_issues.extend(self._check_corroboration_nlp(doc, settings))
        
        # Always check follow-up (doesn't benefit much from NLP, use regex)
        if settings.get("check_follow_up", True):
            follow_up_indicators = settings.get("follow_up_indicators", rules.DEFAULT_FOLLOW_UP_INDICATORS)
            all_issues.extend(rules.check_action_follow_up(doc.text, follow_up_indicators))
        
        return all_issues
    
    def _check_vague_when_nlp(self, doc, settings: Dict) -> List[Dict]:
        """Check for vague temporal references using NLP."""
        vague_when_terms = settings.get("vague_when_terms", rules.DEFAULT_VAGUE_WHEN_TERMS)
        issues = []
        text_lower = doc.text.lower()
        
        # Look for temporal expressions
        for ent in doc.ents:
            if ent.label_ == "DATE" and ent.start_char < len(doc.text):
                # Check if it's a vague date (like "last week" instead of specific date)
                ent_text = doc.text[ent.start_char:ent.end_char].lower()
                if any(term in ent_text for term in vague_when_terms):
                    # Check if there's a more specific date nearby
                    context_start = max(0, ent.start_char - 100)
                    context_end = min(len(doc.text), ent.end_char + 100)
                    context = doc.text[context_start:context_end]
                    
                    # Look for specific date patterns
                    specific_date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}'
                    if not re.search(specific_date_pattern, context):
                        evidence = context.strip()
                        issues.append({
                            "key": "missing_when",
                            "message": "Consider adding a specific date to clarify when this occurred.",
                            "evidence": evidence,
                            "location": {"start_char": ent.start_char, "end_char": ent.end_char},
                            "severity": "note"
                        })
        
        # Also check for vague temporal words using regex (for terms not caught by NER)
        for term in vague_when_terms:
            if term not in ["recently", "earlier", "previously"]:  # Already checked above
                pattern = rf'\b{re.escape(term)}\b'
                for match in re.finditer(pattern, text_lower):
                    start_pos = match.start()
                    end_pos = match.end()
                    context_start = max(0, start_pos - 50)
                    context_end = min(len(doc.text), end_pos + 50)
                    context = doc.text[context_start:context_end]
                    
                    # Check for dates nearby
                    date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}'
                    if not re.search(date_pattern, context):
                        issues.append({
                            "key": "missing_when",
                            "message": "Consider adding a specific date to clarify when this occurred.",
                            "evidence": context.strip(),
                            "location": {"start_char": start_pos, "end_char": end_pos},
                            "severity": "note"
                        })
        
        return issues
    
    def _check_vague_where_nlp(self, doc, settings: Dict) -> List[Dict]:
        """Check for vague geographic references using NLP."""
        vague_where_terms = settings.get("vague_where_terms", rules.DEFAULT_VAGUE_WHERE_TERMS)
        issues = []
        text_lower = doc.text.lower()
        
        # Look for location entities
        location_entities = []
        for ent in doc.ents:
            if ent.label_ in ["GPE", "LOC"]:  # Geopolitical entity or location
                location_entities.append((ent.start_char, ent.end_char, ent.text))
        
        # Check for vague location terms
        for term in vague_where_terms:
            pattern = rf'\b{re.escape(term)}\b'
            for match in re.finditer(pattern, text_lower):
                match_start = match.start()
                match_end = match.end()
                
                # Check if there's a specific location entity nearby
                context_start = max(0, match_start - 150)
                context_end = min(len(doc.text), match_end + 150)
                
                # Check if there's a location entity in context
                has_location = any(
                    context_start <= loc_start < context_end or context_start < loc_end <= context_end
                    for loc_start, loc_end, _ in location_entities
                )
                
                # Also check for admin unit keywords
                admin_keywords = ["county", "payam", "boma", "state", "village", "town"]
                context_text = doc.text[context_start:context_end].lower()
                has_admin_unit = any(keyword in context_text for keyword in admin_keywords)
                
                if not (has_location or has_admin_unit):
                    evidence = doc.text[context_start:context_end].strip()
                    issues.append({
                        "key": "where_vague",
                        "message": "It may help to specify the administrative unit (County, Payam, Boma) for clarity.",
                        "evidence": evidence,
                        "location": {"start_char": match_start, "end_char": match_end},
                        "severity": "note"
                    })
        
        return issues
    
    def _check_vague_who_nlp(self, doc) -> List[Dict]:
        """Check for vague actor descriptions using NLP."""
        issues = []
        
        # Look for person/organization entities
        person_org_entities = []
        for ent in doc.ents:
            if ent.label_ in ["PERSON", "ORG"]:
                person_org_entities.append((ent.start_char, ent.end_char))
        
        # Check for generic actor patterns
        generic_patterns = [
            (r'\barmed\s+men\b', 'Consider specifying the group or institution level if safe to do so.'),
            (r'\bunknown\s+(?:assailants?|attackers?|perpetrators?)\b', 'If possible, add any identifying information available.'),
        ]
        
        for pattern, message in generic_patterns:
            for match in re.finditer(pattern, doc.text, re.IGNORECASE):
                match_start = match.start()
                match_end = match.end()
                
                # Check if there's a specific entity nearby
                context_start = max(0, match_start - 100)
                context_end = min(len(doc.text), match_end + 100)
                
                has_specific_entity = any(
                    context_start <= ent_start < context_end or context_start < ent_end <= context_end
                    for ent_start, ent_end in person_org_entities
                )
                
                if not has_specific_entity:
                    evidence = doc.text[context_start:context_end].strip()
                    issues.append({
                        "key": "who_vague",
                        "message": message,
                        "evidence": evidence,
                        "location": {"start_char": match_start, "end_char": match_end},
                        "severity": "note"
                    })
        
        return issues
    
    def _check_facts_analysis_nlp(self, doc, settings: Dict) -> List[Dict]:
        """Check for facts vs analysis mixing using NLP."""
        interpretive_terms = settings.get("interpretive_terms", rules.DEFAULT_INTERPRETIVE_TERMS)
        issues = []
        
        # Analyze sentences
        for sent in doc.sents:
            sent_text = sent.text
            sent_lower = sent_text.lower()
            
            # Check for interpretive terms
            found_terms = []
            for term in interpretive_terms:
                if re.search(rf'\b{re.escape(term)}\b', sent_lower):
                    found_terms.append(term)
            
            if found_terms:
                # Check for attribution using dependency parsing
                has_attribution = False
                
                # Look for attribution patterns in the sentence
                attribution_patterns = [
                    r'according\s+to',
                    r'reportedly',
                    r'sources?\s+(?:indicate|report|state|say)',
                    r'witnesses?\s+(?:report|indicate|state)',
                ]
                
                if any(re.search(pattern, sent_lower) for pattern in attribution_patterns):
                    has_attribution = True
                else:
                    # Use dependency parsing to check for attribution
                    for token in sent:
                        # Check for reporting verbs with sources
                        if token.dep_ == "nsubj" and token.head.pos_ == "VERB":
                            # Look for source in the sentence
                            for child in token.head.children:
                                if child.dep_ == "nmod" and any(
                                    source_word in child.text.lower() 
                                    for source_word in ["source", "witness", "report", "according"]
                                ):
                                    has_attribution = True
                                    break
                
                if not has_attribution:
                    start_char = sent.start_char
                    end_char = sent.end_char
                    issues.append({
                        "key": "facts_analysis_mix",
                        "message": "Consider separating factual narrative from assessment, or attributing the assessment to sources.",
                        "evidence": sent_text.strip(),
                        "location": {"start_char": start_char, "end_char": end_char},
                        "severity": "attention"
                    })
        
        return issues
    
    def _check_corroboration_nlp(self, doc, settings: Dict) -> List[Dict]:
        """Check for definitive verbs without source framing using NLP."""
        definitive_verbs = settings.get("definitive_verbs", rules.DEFAULT_DEFINITIVE_VERBS)
        issues = []
        
        # Find all verbs
        for token in doc:
            if token.pos_ == "VERB":
                verb_text = token.lemma_.lower()  # Use lemma (root form)
                
                # Check if it's a definitive verb
                if verb_text in [v.lower() for v in definitive_verbs]:
                    # Check for attribution in the sentence
                    sent = token.sent
                    sent_lower = sent.text.lower()
                    
                    attribution_patterns = [
                        r'according\s+to',
                        r'reportedly',
                        r'sources?\s+(?:indicate|report|state|say)',
                        r'information\s+(?:indicates|suggests)',
                    ]
                    
                    has_attribution = any(re.search(pattern, sent_lower) for pattern in attribution_patterns)
                    
                    if not has_attribution:
                        # Check dependency tree for sources
                        for child in token.children:
                            if child.dep_ == "nmod" and any(
                                source_word in child.text.lower()
                                for source_word in ["source", "witness", "report"]
                            ):
                                has_attribution = True
                                break
                        
                        if not has_attribution:
                            # Get character position of token
                            try:
                                start_char = token.idx
                            except (AttributeError, TypeError):
                                # Fallback: use sentence start + token offset
                                sent = token.sent
                                sent_start = sent.start_char if hasattr(sent, 'start_char') else 0
                                # Calculate offset within sentence
                                token_offset = sum(len(doc[j].text_with_ws) for j in range(sent.start, token.i))
                                start_char = sent_start + token_offset
                            
                            end_char = start_char + len(token.text)
                            context_start = max(0, start_char - 50)
                            context_end = min(len(doc.text), end_char + 50)
                            evidence = doc.text[context_start:context_end].strip()
                            
                            issues.append({
                                "key": "corroboration_language",
                                "message": "For clarity, consider adding light qualifiers such as 'according to sources' or 'reportedly'.",
                                "evidence": evidence,
                                "location": {"start_char": start_char, "end_char": end_char},
                                "severity": "note"
                            })
        
        return issues

