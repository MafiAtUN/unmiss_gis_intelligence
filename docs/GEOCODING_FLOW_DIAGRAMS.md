# Geocoding Process: Detailed Flow Diagrams

## Overview

This document provides detailed diagrams and explanations of the geocoding process for the address: **"Hai Masana area, Wau Town, Wau County"**.

---

## 1. High-Level Architecture

```mermaid
graph TB
    A[User Input:<br/>Hai Masana area, Wau Town, Wau County] --> B[Geocoder.geocode]
    B --> C[Text Normalization]
    C --> D[Cache Check]
    D --> E{Has Constraints?}
    E -->|Yes| F[Skip Cache]
    E -->|No| G{Cache Hit?}
    G -->|Yes| H[Return Cached Result]
    G -->|No| F
    F --> I[Parse Hierarchical Constraints]
    I --> J[Extract Candidates]
    J --> K[Load Admin Layers]
    K --> L[Hierarchical Resolution]
    L --> M[Cache Result]
    M --> N[Return GeocodeResult]
```

---

## 2. Main Geocoding Flow

```mermaid
flowchart TD
    Start([Start: geocode function]) --> Norm[normalize_text<br/>'hai masana area wau town wau county']
    Norm --> Parse[parse_hierarchical_constraints]
    Parse --> CheckCache{Has Constraints?}
    CheckCache -->|Yes| SkipCache[Skip Cache<br/>Avoid stale results]
    CheckCache -->|No| CacheLookup[Check geocode_cache table]
    CacheLookup --> CacheHit{Cache Found?}
    CacheHit -->|Yes| ReturnCache[Return Cached Result]
    CacheHit -->|No| SkipCache
    SkipCache --> LoadLayers[_load_admin_layers<br/>Load from DuckDB]
    LoadLayers --> ExtractCandidates[extract_candidates<br/>Generate n-grams]
    ExtractCandidates --> AIExtract{Azure AI Enabled?}
    AIExtract -->|Yes| AICall[Azure AI Extraction<br/>Merge with candidates]
    AIExtract -->|No| Resolve
    AICall --> Resolve[_resolve_hierarchical]
    Resolve --> TryVillage[_try_settlement_match]
    TryVillage --> VillageFound{Village Match?}
    VillageFound -->|Yes| ReturnVillage[Return Village Result]
    VillageFound -->|No| TryBoma[_try_polygon_match<br/>admin4_boma]
    TryBoma --> BomaFound{Boma Match?}
    BomaFound -->|Yes| ReturnBoma[Return Boma Result]
    BomaFound -->|No| TryPayam[_try_polygon_match<br/>admin3_payam]
    TryPayam --> PayamFound{Payam Match?}
    PayamFound -->|Yes| ReturnPayam[Return Payam Result]
    PayamFound -->|No| TryCounty[_try_polygon_match<br/>admin2_county]
    TryCounty --> CountyFound{County Match?}
    CountyFound -->|Yes| ReturnCounty[Return County<br/>resolution_too_coarse=True<br/>No coordinates]
    CountyFound -->|No| NoMatch[Return No Match<br/>score=0.0]
    ReturnVillage --> CacheResult[Cache Result]
    ReturnBoma --> CacheResult
    ReturnPayam --> CacheResult
    ReturnCounty --> CacheResult
    NoMatch --> CacheResult
    CacheResult --> End([End])
    ReturnCache --> End
```

---

## 3. Text Normalization Process

```mermaid
graph LR
    A["Input:<br/>'Hai Masana area, Wau Town, Wau County'"] --> B[Unicode Normalization<br/>NFD → Remove Diacritics]
    B --> C[Lowercase Conversion]
    C --> D[Handle Abbreviations<br/>c equatoria → central equatoria]
    D --> E[Handle Transliterations<br/>waw → wau]
    E --> F[Protect Preserve Words<br/>el, al, de, la]
    F --> G[Remove Punctuation]
    G --> H[Restore Preserve Words]
    H --> I[Collapse Whitespace]
    I --> J["Output:<br/>'hai masana area wau town wau county'"]
```

### Normalization Details

| Step | Input | Output | Description |
|------|-------|--------|-------------|
| 1. Unicode | `Hai Masana` | `Hai Masana` | Remove diacritics |
| 2. Lowercase | `Hai Masana` | `hai masana` | Convert to lowercase |
| 3. Abbreviations | `c equatoria` | `central equatoria` | Expand abbreviations |
| 4. Transliterations | `waw` | `wau` | Normalize spellings |
| 5. Remove Punctuation | `area, Wau` | `area wau` | Remove commas, periods |
| 6. Collapse Whitespace | `area  wau` | `area wau` | Single spaces |

---

## 4. Hierarchical Constraint Parsing

```mermaid
flowchart TD
    Input["Input:<br/>'Hai Masana area, Wau Town, Wau County'"] --> Split[Split by Delimiters<br/>comma, semicolon]
    Split --> Part1["Part 1:<br/>'Hai Masana area'"]
    Split --> Part2["Part 2:<br/>'Wau Town'"]
    Split --> Part3["Part 3:<br/>'Wau County'"]
    
    Part1 --> Check1{Contains Keywords?}
    Check1 -->|town, village, city| Village1[Set village = 'hai masana area']
    Check1 -->|No keywords| Infer1[Infer: First part = village]
    
    Part2 --> Check2{Contains Keywords?}
    Check2 -->|town| Village2[Set village = 'wau']
    Check2 -->|No| Infer2[Infer: Second part = village]
    
    Part3 --> Check3{Contains Keywords?}
    Check3 -->|county| County[Set county = 'wau']
    Check3 -->|No| Infer3[Infer: Last part = county]
    
    Village1 --> Merge[Merge Constraints]
    Village2 --> Merge
    Infer1 --> Merge
    Infer2 --> Merge
    County --> Merge
    Infer3 --> Merge
    
    Merge --> Result["Constraints:<br/>{<br/>  village: 'hai masana area',<br/>  county: 'wau',<br/>  state: None,<br/>  payam: None,<br/>  boma: None<br/>}"]
```

### Constraint Parsing Logic

```python
# Pseudo-code for parse_hierarchical_constraints()

parts = ["Hai Masana area", "Wau Town", "Wau County"]
constraints = {
    "state": None,
    "county": None,
    "payam": None,
    "boma": None,
    "village": None
}

for part in parts:
    normalized = normalize_text(part)
    
    if "county" in normalized:
        constraints["county"] = "wau"  # Remove "county" keyword
    
    if "town" in normalized:
        constraints["village"] = "wau"  # Remove "town" keyword
    
    if no_keywords and is_first_part:
        constraints["village"] = "hai masana area"

# Final constraints:
# {
#   "village": "hai masana area",  # From first part
#   "county": "wau",                # From "Wau County"
#   "state": None,
#   "payam": None,
#   "boma": None
# }
```

---

## 5. Candidate Extraction Process

```mermaid
graph TD
    A["Normalized Text:<br/>'hai masana area wau town wau county'"] --> B[Split into Words]
    B --> C["Words:<br/>['hai', 'masana', 'area', 'wau', 'town', 'wau', 'county']"]
    C --> D[Generate N-grams]
    
    D --> E[Single Words<br/>min_length >= 3]
    E --> E1["'hai'<br/>'masana'<br/>'area'<br/>'wau'<br/>'town'<br/>'county'"]
    
    D --> F[2-word N-grams]
    F --> F1["'hai masana'<br/>'masana area'<br/>'area wau'<br/>'wau town'<br/>'town wau'<br/>'wau county'"]
    
    D --> G[3-word N-grams]
    G --> G1["'hai masana area'<br/>'masana area wau'<br/>'area wau town'<br/>'wau town wau'<br/>'town wau county'"]
    
    D --> H[Full Text]
    H --> H1["'hai masana area wau town wau county'"]
    
    E1 --> Filter[Filter Stop Words]
    F1 --> Filter
    G1 --> Filter
    H1 --> Filter
    
    Filter --> Candidates["Candidates Set:<br/>{<br/>  'hai', 'masana', 'area',<br/>  'wau', 'town', 'county',<br/>  'hai masana', 'masana area',<br/>  'area wau', 'wau town',<br/>  'wau county',<br/>  'hai masana area',<br/>  'wau town',<br/>  ...<br/>}"]
```

### N-gram Generation Example

| Type | Examples | Count |
|------|----------|-------|
| 1-gram | `hai`, `masana`, `area`, `wau`, `town`, `county` | 6 |
| 2-gram | `hai masana`, `masana area`, `area wau`, `wau town`, `wau county` | 5 |
| 3-gram | `hai masana area`, `masana area wau`, `area wau town`, `wau town wau` | 4 |
| 4-gram | `hai masana area wau`, `masana area wau town` | 2 |
| Full | `hai masana area wau town wau county` | 1 |

**After filtering stop words** (`the`, `of`, `in`, `at`, `on`, `to`, `for`, `and`, `or`, `a`, `an`):
- `area` might be kept (could be part of place name)
- `town` might be kept (could be part of place name)

---

## 6. Hierarchical Resolution Decision Tree

```mermaid
flowchart TD
    Start([Start Resolution]) --> Village[_try_settlement_match]
    Village --> VSearch[Search villages table<br/>with constraints]
    VSearch --> VMatch{Village Match?}
    VMatch -->|Yes| VValidate[Validate Constraints<br/>Check state/county match]
    VValidate --> VPass{Constraints Pass?}
    VPass -->|Yes| VReturn[Return Village Result<br/>lon, lat, hierarchy]
    VPass -->|No| Boma
    VMatch -->|No| Boma[_try_polygon_match<br/>admin4_boma]
    
    Boma --> BSearch[Search name_index<br/>layer=admin4_boma]
    BSearch --> BMatch{Boma Match?}
    BMatch -->|Yes| BValidate[Validate Constraints<br/>Check spatial hierarchy]
    BValidate --> BPass{Constraints Pass?}
    BPass -->|Yes| BCentroid[Compute Centroid<br/>UTM Zone 36N → WGS84]
    BCentroid --> BReturn[Return Boma Result<br/>lon, lat, hierarchy]
    BPass -->|No| Payam
    BMatch -->|No| Payam[_try_polygon_match<br/>admin3_payam]
    
    Payam --> PSearch[Search name_index<br/>layer=admin3_payam]
    PSearch --> PMatch{Payam Match?}
    PMatch -->|Yes| PValidate[Validate Constraints]
    PValidate --> PPass{Constraints Pass?}
    PPass -->|Yes| PCentroid[Compute Centroid]
    PCentroid --> PReturn[Return Payam Result<br/>lon, lat, hierarchy]
    PPass -->|No| County
    PMatch -->|No| County[_try_polygon_match<br/>admin2_county<br/>return_coords=False]
    
    County --> CSearch[Search name_index<br/>layer=admin2_county]
    CSearch --> CMatch{County Match?}
    CMatch -->|Yes| CReturn[Return County Result<br/>resolution_too_coarse=True<br/>lon=None, lat=None]
    CMatch -->|No| NoMatch[Return No Match<br/>score=0.0]
    
    VReturn --> End([End])
    BReturn --> End
    PReturn --> End
    CReturn --> End
    NoMatch --> End
```

---

## 7. Village Search Process (Detailed)

```mermaid
flowchart TD
    Start([search_villages]) --> BuildQuery[Build SQL Query<br/>with Constraints]
    BuildQuery --> ConstraintSQL["WHERE LOWER(county) LIKE '%wau%'<br/>AND ..."]
    ConstraintSQL --> Execute[Execute Query<br/>Get villages in Wau County]
    Execute --> Results{Villages Found?}
    
    Results -->|No| Fallback1[Fallback: Exact County Match]
    Fallback1 --> Fallback2[Fallback: State Only]
    Fallback2 --> Fallback3[Fallback: All Villages]
    Fallback3 --> BuildSearch[Build Search Strings]
    
    Results -->|Yes| BuildSearch[Build Search Strings<br/>from village names]
    
    BuildSearch --> IncludeAlts{Include Alternates?}
    IncludeAlts -->|Yes| QueryAlts[Query village_alternate_names<br/>with constraints]
    QueryAlts --> MergeAlts[Merge with primary names]
    IncludeAlts -->|No| ExactMatch
    MergeAlts --> ExactMatch[Try Exact Match<br/>normalized_query == normalized_name]
    
    ExactMatch --> ExactFound{Exact Match?}
    ExactFound -->|Yes| ReturnExact[Return Exact Match<br/>score=1.0]
    ExactFound -->|No| SubstringMatch[Try Substring Match<br/>query in name or name in query]
    
    SubstringMatch --> SubFound{Good Substring?}
    SubFound -->|Yes| ReturnSub[Return Substring Match<br/>score=0.85-0.95]
    SubFound -->|No| FuzzyMatch[Progressive Fuzzy Match<br/>threshold=0.7]
    
    FuzzyMatch --> FuzzyResults[Get Fuzzy Matches<br/>with scores]
    FuzzyResults --> ContextBoost[Apply Context Boost<br/>+0.20 if county matches<br/>-0.30 if county wrong]
    ContextBoost --> Deduplicate[Deduplicate by village_id<br/>Keep highest score]
    Deduplicate --> Sort[Sort by Score Descending]
    Sort --> Limit[Limit to top N results]
    Limit --> Return[Return Results]
    
    ReturnExact --> End([End])
    ReturnSub --> End
    Return --> End
```

### Village Search SQL Query Example

```sql
-- Primary query with constraints
SELECT village_id, name, normalized_name, lon, lat,
       state, county, payam, boma, data_source, verified
FROM villages
WHERE LOWER(county) LIKE LOWER('%wau%')
-- Returns only villages in Wau County

-- If no results, fallback to exact match
SELECT village_id, name, normalized_name, lon, lat,
       state, county, payam, boma, data_source, verified
FROM villages
WHERE LOWER(county) = LOWER('wau')

-- If still no results, try state only
SELECT village_id, name, normalized_name, lon, lat,
       state, county, payam, boma, data_source, verified
FROM villages
WHERE LOWER(state) LIKE LOWER('%western bahr el ghazal%')
```

---

## 8. Fuzzy Matching Process

```mermaid
flowchart TD
    Start([progressive_fuzzy_match]) --> Normalize[Normalize Query<br/>'hai masana area']
    Normalize --> Stage1[Stage 1: Exact Match<br/>Check normalized_query == normalized_choice]
    Stage1 --> Exact{Exact Match?}
    Exact -->|Yes| ReturnExact[Return score=1.0]
    Exact -->|No| Stage2[Stage 2: High Confidence<br/>threshold=0.9]
    
    Stage2 --> Fuzzy1[fuzzy_match<br/>token_sort_ratio + partial_ratio]
    Fuzzy1 --> HighConf{Matches Found?}
    HighConf -->|Yes| LengthCheck[Check Length Ratio<br/>Penalize substring matches]
    LengthCheck --> ReturnHigh[Return High Confidence<br/>score=0.9+]
    HighConf -->|No| Stage3[Stage 3: Medium-High<br/>threshold=0.8]
    
    Stage3 --> Fuzzy2[fuzzy_match<br/>threshold=0.8]
    Fuzzy2 --> MedHigh{Matches Found?}
    MedHigh -->|Yes| ReturnMed[Return Medium-High<br/>score=0.8+]
    MedHigh -->|No| Stage4[Stage 4: Base Threshold<br/>threshold=0.7]
    
    Stage4 --> Fuzzy3[fuzzy_match<br/>threshold=0.7]
    Fuzzy3 --> Base{Matches Found?}
    Base -->|Yes| ReturnBase[Return Base<br/>score=0.7+]
    Base -->|No| Stage5{Query Short?<br/><=2 words or <=5 chars}
    
    Stage5 -->|Yes| Fuzzy4[fuzzy_match<br/>threshold=0.5]
    Stage5 -->|No| ReturnEmpty[Return Empty]
    Fuzzy4 --> Low{Matches Found?}
    Low -->|Yes| ReturnLow[Return Low Confidence<br/>score=0.5+]
    Low -->|No| ReturnEmpty
    
    ReturnExact --> End([End])
    ReturnHigh --> End
    ReturnMed --> End
    ReturnBase --> End
    ReturnLow --> End
    ReturnEmpty --> End
```

### Fuzzy Matching Algorithms

| Algorithm | Description | Use Case |
|-----------|-------------|----------|
| `token_sort_ratio` | Sorts tokens, then compares | "masana hai" vs "hai masana" |
| `partial_ratio` | Best substring match | "masana" in "hai masana area" |
| `WRatio` | Weighted combination | Overall best match |

### Scoring Example

```
Query: "hai masana"
Choice: "Hai Masana area"

1. Normalize both: "hai masana" vs "hai masana area"
2. token_sort_ratio: 85% (good match, order doesn't matter)
3. partial_ratio: 100% (query is substring of choice)
4. Length check: query_len=11, choice_len=18
   - ratio = 11/18 = 0.61 (acceptable, >0.6)
5. Final score: 0.85-0.95 (substring match with boost)
```

---

## 9. Context Boost Application

```mermaid
flowchart TD
    Start([apply_context_boost]) --> Init[Initialize boosted_score = base_score]
    Init --> CheckState{State Constraint?}
    CheckState -->|Yes| StateMatch{State Matches?}
    StateMatch -->|Yes| BoostState[+0.20 boost]
    StateMatch -->|No| PenalizeState[-0.50 penalty]
    StateMatch -->|No Match Info| CheckCounty
    BoostState --> CheckCounty
    PenalizeState --> CheckCounty
    CheckState -->|No| CheckCounty{County Constraint?}
    
    CheckCounty -->|Yes| CountyMatch{County Matches?}
    CountyMatch -->|Yes| BoostCounty[+0.20 boost]
    CountyMatch -->|No| PenalizeCounty[-0.30 penalty]
    CountyMatch -->|No Match Info| CheckPayam
    BoostCounty --> CheckPayam
    PenalizeCounty --> CheckPayam
    CheckCounty -->|No| CheckPayam{Payam Constraint?}
    
    CheckPayam -->|Yes| PayamMatch{Payam Matches?}
    PayamMatch -->|Yes| BoostPayam[+0.05 boost]
    PayamMatch -->|No| CheckBoma
    CheckPayam -->|No| CheckBoma{Boma Constraint?}
    
    CheckBoma -->|Yes| BomaMatch{Boma Matches?}
    BomaMatch -->|Yes| BoostBoma[+0.05 boost]
    BomaMatch -->|No| LayerBoost
    CheckBoma -->|No| LayerBoost[Layer Specificity Boost]
    
    LayerBoost --> VillageBoost{Is Village?}
    VillageBoost -->|Yes| +0.15
    VillageBoost -->|No| BomaBoost{Is Boma?}
    BomaBoost -->|Yes| +0.10
    BomaBoost -->|No| PayamBoost{Is Payam?}
    PayamBoost -->|Yes| +0.05
    PayamBoost -->|No| Clamp
    
    +0.15 --> Clamp[Clamp Score<br/>0.0 <= score <= 1.0]
    +0.10 --> Clamp
    +0.05 --> Clamp
    
    Clamp --> Sort[Sort by Boosted Score]
    Sort --> Return[Return Boosted Matches]
    Return --> End([End])
```

### Context Boost Example

```
Base Match:
  - Query: "hai masana"
  - Village: "Hai Masana"
  - County: "Wau County"
  - Base Score: 0.85

Constraints:
  - county: "wau"

Boost Calculation:
  - Base score: 0.85
  - County matches: +0.20
  - Layer (village): +0.15
  - Final score: 0.85 + 0.20 + 0.15 = 1.20 → clamped to 1.0

If county was wrong (e.g., "Juba County"):
  - Base score: 0.85
  - County wrong: -0.30
  - Final score: 0.85 - 0.30 = 0.55 (below threshold, rejected)
```

---

## 10. Complete Example: "Hai Masana area, Wau Town, Wau County"

### Step-by-Step Execution

```mermaid
sequenceDiagram
    participant User
    participant Geocoder
    participant Normalizer
    participant Parser
    participant DB
    participant FuzzyMatcher
    
    User->>Geocoder: geocode("Hai Masana area, Wau Town, Wau County")
    Geocoder->>Normalizer: normalize_text()
    Normalizer-->>Geocoder: "hai masana area wau town wau county"
    
    Geocoder->>Parser: parse_hierarchical_constraints()
    Parser-->>Geocoder: {village: "hai masana area", county: "wau"}
    
    Geocoder->>Geocoder: extract_candidates()
    Geocoder-->>Geocoder: {"hai", "masana", "hai masana", "wau", ...}
    
    Geocoder->>DB: Load admin layers
    DB-->>Geocoder: admin_layers loaded
    
    Geocoder->>Geocoder: _try_settlement_match()
    Geocoder->>DB: search_villages("hai masana area", county="wau")
    DB->>DB: WHERE LOWER(county) LIKE '%wau%'
    DB-->>Geocoder: [village1, village2, ...]
    
    Geocoder->>FuzzyMatcher: progressive_fuzzy_match()
    FuzzyMatcher->>FuzzyMatcher: Try exact match
    FuzzyMatcher->>FuzzyMatcher: Try substring match
    FuzzyMatcher->>FuzzyMatcher: Try fuzzy match (threshold=0.7)
    FuzzyMatcher-->>Geocoder: [(village_name, score, idx), ...]
    
    Geocoder->>Geocoder: apply_context_boost()
    Geocoder->>Geocoder: Verify constraints
    Geocoder->>DB: get_village(village_id)
    DB-->>Geocoder: {name, lon, lat, state, county, ...}
    
    Geocoder->>Geocoder: Validate county constraint
    Geocoder-->>User: GeocodeResult(village, lon, lat, hierarchy)
```

### Detailed Execution Trace

#### Step 1: Input Processing
```
Input: "Hai Masana area, Wau Town, Wau County"
↓
Normalized: "hai masana area wau town wau county"
```

#### Step 2: Constraint Parsing
```
Parts: ["Hai Masana area", "Wau Town", "Wau County"]
↓
Constraints:
  - village: "hai masana area" (from first part)
  - county: "wau" (from "Wau County")
  - state: None
  - payam: None
  - boma: None
```

#### Step 3: Candidate Extraction
```
Candidates: {
  "hai", "masana", "area", "wau", "town", "county",
  "hai masana", "masana area", "area wau", "wau town", "wau county",
  "hai masana area", "masana area wau", "area wau town", "wau town wau",
  ...
}
```

#### Step 4: Village Search
```sql
-- Query executed in DuckDB
SELECT village_id, name, normalized_name, lon, lat,
       state, county, payam, boma
FROM villages
WHERE LOWER(county) LIKE LOWER('%wau%')
-- Returns: [village1, village2, village3, ...]
```

#### Step 5: Fuzzy Matching
```
Query: "hai masana area"
Candidates from DB: ["Hai Masana", "Hai Masana area", "Wau Town", ...]

Matching Process:
1. Exact match: "hai masana area" == "hai masana area" → score=1.0 ✓
2. If not found, substring: "hai masana" in "hai masana area" → score=0.90
3. If not found, fuzzy: token_sort_ratio("hai masana area", "hai masana") → score=0.85
```

#### Step 6: Context Boost
```
Base match: "Hai Masana area"
  - Base score: 0.90
  - County constraint: "wau"
  - Village county: "Wau County" ✓
  - Boost: +0.20 (county matches)
  - Layer boost: +0.15 (village)
  - Final score: 1.0 (clamped)
```

#### Step 7: Constraint Validation
```
Matched village:
  - name: "Hai Masana area"
  - county: "Wau County"
  - state: "Western Bahr el Ghazal"

Constraints:
  - county: "wau"

Validation:
  - "wau" in "Wau County" → ✓ PASS
  - Return village result
```

#### Step 8: Result Construction
```python
GeocodeResult(
    input_text="Hai Masana area, Wau Town, Wau County",
    normalized_text="hai masana area wau town wau county",
    resolved_layer="villages",
    feature_id="abc123...",
    matched_name="Hai Masana area",
    score=1.0,
    lon=28.123456,
    lat=7.654321,
    state="Western Bahr el Ghazal",
    county="Wau County",
    payam="Wau Payam",
    boma="Hai Masana Boma",
    village="Hai Masana area",
    alternatives=[...]
)
```

---

## 11. Data Flow Diagram

```mermaid
graph TB
    subgraph "Input Layer"
        A[User Input String]
    end
    
    subgraph "Processing Layer"
        B[Text Normalization]
        C[Constraint Parsing]
        D[Candidate Extraction]
        E[AI Extraction<br/>Optional]
    end
    
    subgraph "Storage Layer"
        F[(DuckDB Database)]
        G[geocode_cache]
        H[villages]
        I[name_index]
        J[admin1_state]
        K[admin2_county]
        L[admin3_payam]
        M[admin4_boma]
    end
    
    subgraph "Matching Layer"
        N[Exact Match]
        O[Substring Match]
        P[Fuzzy Match]
        Q[Context Boost]
    end
    
    subgraph "Validation Layer"
        R[Constraint Validation]
        S[Spatial Validation]
        T[Hierarchy Lookup]
    end
    
    subgraph "Output Layer"
        U[GeocodeResult]
    end
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
    
    F --> G
    F --> H
    F --> I
    F --> J
    F --> K
    F --> L
    F --> M
    
    H --> N
    H --> O
    H --> P
    I --> N
    I --> O
    I --> P
    
    N --> Q
    O --> Q
    P --> Q
    
    Q --> R
    R --> S
    S --> T
    T --> U
    
    U --> G
```

---

## 12. Error Handling and Edge Cases

```mermaid
flowchart TD
    Start([Geocode Request]) --> CheckInput{Input Valid?}
    CheckInput -->|Empty| ReturnError[Return Error<br/>score=0.0]
    CheckInput -->|Valid| Normalize
    
    Normalize --> CheckCache{Cache Exists?}
    CheckCache -->|Yes| ValidateCache{Cache Valid?}
    ValidateCache -->|Yes| ReturnCache[Return Cached]
    ValidateCache -->|No| Continue
    CheckCache -->|No| Continue[Continue Processing]
    
    Continue --> SearchVillage[Search Villages]
    SearchVillage --> VillageError{Error?}
    VillageError -->|Yes| LogError[Log Error]
    VillageError -->|No| CheckResults{Results Found?}
    
    CheckResults -->|Yes| ValidateConstraints{Constraints Valid?}
    ValidateConstraints -->|No| TryBoma[Try Boma]
    ValidateConstraints -->|Yes| ReturnResult[Return Result]
    
    TryBoma --> BomaError{Error?}
    BomaError -->|Yes| LogError
    BomaError -->|No| BomaResults{Results Found?}
    BomaResults -->|Yes| ReturnResult
    BomaResults -->|No| TryPayam[Try Payam]
    
    TryPayam --> PayamError{Error?}
    PayamError -->|Yes| LogError
    PayamError -->|No| PayamResults{Results Found?}
    PayamResults -->|Yes| ReturnResult
    PayamResults -->|No| TryCounty[Try County]
    
    TryCounty --> CountyError{Error?}
    CountyError -->|Yes| LogError
    CountyError -->|No| CountyResults{Results Found?}
    CountyResults -->|Yes| ReturnCoarse[Return Coarse Result<br/>No coordinates]
    CountyResults -->|No| ReturnNoMatch[Return No Match]
    
    LogError --> ReturnNoMatch
    ReturnError --> End([End])
    ReturnCache --> End
    ReturnResult --> End
    ReturnCoarse --> End
    ReturnNoMatch --> End
```

---

## 13. Performance Considerations

### Caching Strategy

```mermaid
graph LR
    A[Geocode Request] --> B{Has Constraints?}
    B -->|No| C[Check Cache]
    B -->|Yes| D[Skip Cache]
    C --> E{Cache Hit?}
    E -->|Yes| F[Return Cached<br/>~1ms]
    E -->|No| D
    D --> G[Full Processing<br/>~50-200ms]
    G --> H[Cache Result]
    H --> I[Return Result]
    F --> J([End])
    I --> J
```

### Database Query Optimization

| Query Type | Index Used | Performance |
|------------|------------|-------------|
| Village search by county | `idx_villages_county` | Fast (indexed) |
| Village search by name | `idx_villages_name` | Fast (indexed) |
| Name index search | `idx_name_index_normalized` | Fast (indexed) |
| Spatial hierarchy lookup | Spatial index (GeoPandas) | Medium (in-memory) |

---

## 14. Summary

### Key Points

1. **Text Normalization**: Converts input to searchable format
2. **Constraint Parsing**: Extracts hierarchical information (state, county, etc.)
3. **Candidate Extraction**: Generates n-grams for matching
4. **Hierarchical Resolution**: Tries village → boma → payam → county
5. **Fuzzy Matching**: Uses progressive matching (exact → substring → fuzzy)
6. **Context Boost**: Increases scores for matches that align with constraints
7. **Constraint Validation**: Ensures results match specified boundaries
8. **Caching**: Speeds up repeated queries

### For "Hai Masana area, Wau Town, Wau County"

1. ✅ Identifies "Wau County" as constraint
2. ✅ Searches villages in Wau County only
3. ✅ Matches "Hai Masana area" or "Hai Masana"
4. ✅ Validates county constraint
5. ✅ Returns village coordinates with full hierarchy

---

## Appendix: Code References

### Key Functions

- `Geocoder.geocode()` - Main entry point
- `normalize_text()` - Text normalization
- `parse_hierarchical_constraints()` - Constraint extraction
- `extract_candidates()` - N-gram generation
- `_try_settlement_match()` - Village search
- `search_villages()` - Database village search
- `progressive_fuzzy_match()` - Fuzzy matching
- `apply_context_boost()` - Score boosting
- `_try_polygon_match()` - Polygon layer search

### Configuration

- `FUZZY_THRESHOLD = 0.7` - Minimum match score
- `LAYER_NAMES` - Admin layer names
- `CENTROID_CRS = "EPSG:32736"` - UTM Zone 36N for South Sudan


