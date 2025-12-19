# Location Search Improvements

## Current State Analysis

The geocoding system currently uses:
- Basic text normalization (lowercase, remove punctuation)
- N-gram candidate extraction
- RapidFuzz fuzzy matching (token_sort_ratio + partial_ratio)
- Fixed threshold (0.7)
- Hierarchical constraint parsing (recently added)
- Name index for fast lookup

## Recommended Improvements (Prioritized)

### 🔴 HIGH PRIORITY - Critical for Accuracy

#### 1. **Multi-Stage Search Strategy**
**Problem**: Currently searches all candidates at once, may miss better matches
**Solution**: Implement progressive search with fallback levels
- **Exact match first**: Check for exact normalized matches (score = 1.0)
- **High confidence fuzzy**: Threshold 0.9+ for very similar names
- **Medium confidence fuzzy**: Threshold 0.7-0.9 (current)
- **Low confidence fuzzy**: Threshold 0.5-0.7 for partial matches
- **Phonetic matching**: For names that sound similar but spelled differently

**Implementation**:
```python
def progressive_search(query, candidates, constraints):
    # Stage 1: Exact match
    exact = exact_match(query, candidates, constraints)
    if exact: return exact
    
    # Stage 2: High confidence (0.9+)
    high_conf = fuzzy_match(query, candidates, 0.9, constraints)
    if high_conf: return high_conf
    
    # Stage 3: Medium confidence (0.7-0.9)
    medium_conf = fuzzy_match(query, candidates, 0.7, constraints)
    if medium_conf: return medium_conf
    
    # Stage 4: Phonetic matching
    phonetic = phonetic_match(query, candidates, constraints)
    return phonetic
```

#### 2. **Better Text Normalization for South Sudan**
**Problem**: Current normalization may not handle South Sudan-specific naming patterns
**Solution**: Enhanced normalization
- Handle common abbreviations (e.g., "C Equatoria" → "Central Equatoria")
- Handle transliterations (Arabic to English variations)
- Handle common misspellings (e.g., "Juba" vs "Jubba")
- Preserve important words (don't remove "el" in "Bahr el Ghazal")
- Handle diacritics better (é, è, etc.)

**Implementation**:
```python
SOUTH_SUDAN_ABBREVIATIONS = {
    "c equatoria": "central equatoria",
    "w equatoria": "western equatoria",
    "e equatoria": "eastern equatoria",
    "n bahr el ghazal": "northern bahr el ghazal",
    "w bahr el ghazal": "western bahr el ghazal",
}

def enhanced_normalize(text):
    # Apply abbreviations
    # Handle transliterations
    # Preserve important words
    # Better diacritic handling
```

#### 3. **Phonetic Matching (Soundex/Metaphone)**
**Problem**: Names that sound similar but spelled differently won't match
**Example**: "Juba" vs "Jubba", "Malakal" vs "Malakel"
**Solution**: Add phonetic matching using Soundex or Metaphone
- Use `fuzzywuzzy` or `rapidfuzz` with phonetic algorithms
- Create phonetic index alongside normalized index
- Match by sound, not just spelling

#### 4. **Context-Aware Scoring**
**Problem**: Current scoring doesn't consider administrative hierarchy context
**Solution**: Boost scores based on context
- Higher score if match is in the specified state/county
- Lower score if match is outside specified boundaries
- Consider distance from expected location
- Consider layer specificity (village > boma > payam > county > state)

**Implementation**:
```python
def context_aware_score(base_score, match, constraints):
    score = base_score
    
    # Boost if in correct state
    if constraints.get("state") and match.state == constraints["state"]:
        score += 0.1
    
    # Boost if in correct county
    if constraints.get("county") and match.county == constraints["county"]:
        score += 0.1
    
    # Boost for more specific layers
    layer_boost = {"villages": 0.15, "admin4_boma": 0.1, "admin3_payam": 0.05}
    score += layer_boost.get(match.layer, 0)
    
    return min(score, 1.0)
```

#### 5. **Better Candidate Extraction**
**Problem**: Current n-gram extraction may miss important combinations
**Solution**: Smarter candidate extraction
- Prioritize longer phrases (full location names)
- Extract hierarchical components separately
- Handle compound names better
- Consider word order variations

### 🟡 MEDIUM PRIORITY - Quality of Life

#### 6. **Adaptive Threshold**
**Problem**: Fixed 0.7 threshold may be too strict or too lenient
**Solution**: Dynamic threshold based on query characteristics
- Shorter queries: Lower threshold (more lenient)
- Longer queries: Higher threshold (more strict)
- Queries with constraints: Can be more lenient (context helps)
- Queries without constraints: Need higher threshold

#### 7. **Synonym/Alias Expansion**
**Problem**: May not find locations with different names
**Solution**: Expand search with synonyms
- Use alternate names more aggressively
- Build synonym dictionary for common variations
- Handle historical name changes
- Handle language variations (Arabic, English, local languages)

#### 8. **Partial Word Matching**
**Problem**: May miss matches when query is partial
**Example**: "Jub" should match "Juba"
**Solution**: 
- Use prefix/suffix matching for short queries
- Implement substring matching with scoring
- Handle abbreviations better

#### 9. **Multi-Language Support**
**Problem**: South Sudan has multiple languages
**Solution**:
- Normalize Arabic names
- Handle transliterations
- Support local language names
- Build language-specific normalization rules

#### 10. **Result Ranking Improvements**
**Problem**: Results may not be in optimal order
**Solution**: Better ranking algorithm
- Consider multiple factors: score, specificity, context match, data quality
- Use machine learning for ranking (optional)
- Consider user feedback/click-through rates
- Boost verified locations

### 🟢 LOW PRIORITY - Nice to Have

#### 11. **Search History & Learning**
- Track successful searches
- Learn from user corrections
- Suggest common queries
- Auto-complete based on history

#### 12. **Geographic Proximity**
- If multiple matches, rank by proximity to other known locations
- Use spatial indexing for faster proximity searches
- Consider clustering of results

#### 13. **Confidence Indicators**
- Show confidence level to users
- Explain why a match was chosen
- Show what factors contributed to the match

#### 14. **Batch Geocoding**
- Process multiple locations at once
- Show progress for large batches
- Export results in bulk

#### 15. **Search Suggestions**
- Auto-suggest as user types
- Show popular locations
- Suggest corrections for typos

## Implementation Priority

### Phase 1 (Immediate - High Impact)
1. Multi-stage search strategy
2. Enhanced normalization for South Sudan
3. Context-aware scoring
4. Better candidate extraction

### Phase 2 (Short-term - Medium Impact)
5. Phonetic matching
6. Adaptive threshold
7. Synonym/alias expansion
8. Partial word matching

### Phase 3 (Long-term - Polish)
9. Multi-language support
10. Result ranking improvements
11. Search history & learning
12. Geographic proximity
13. Confidence indicators
14. Batch geocoding
15. Search suggestions

## Testing Strategy

For each improvement:
1. Create test cases with known problematic queries
2. Measure accuracy before/after
3. Track false positives and false negatives
4. Get user feedback on results quality
5. Monitor performance impact

## Metrics to Track

- **Accuracy**: % of queries that return correct result
- **Precision**: % of returned results that are correct
- **Recall**: % of correct results that are found
- **Response Time**: Average geocoding time
- **User Satisfaction**: Feedback on result quality

