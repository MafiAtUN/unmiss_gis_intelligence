# Cascading Location Extraction Flow

## Overview

The document location extraction system now uses a **cascading approach** to optimize cost and performance:

**Regex → Ollama → Azure AI**

This ensures we use the most cost-effective method first, only escalating to more expensive options when needed.

## Flow Architecture

```
Document Text
    │
    ├─→ Step 1: Regex Extraction (FREE, FAST)
    │   └─→ Extract all location strings
    │       └─→ Geocode each → Get confidence scores
    │
    ├─→ Step 2: Identify Gaps
    │   ├─→ Regions with no regex matches
    │   └─→ Regex matches with low geocoding confidence (< 0.7)
    │
    ├─→ Step 3: Ollama Extraction (LOCAL, FREE)
    │   └─→ Extract locations from gap regions only
    │       └─→ Geocode each → Get confidence scores
    │
    ├─→ Step 4: Identify Remaining Gaps
    │   └─→ Areas still not covered after Ollama
    │
    ├─→ Step 5: Azure AI Extraction (COST, LAST RESORT)
    │   └─→ Extract remaining missed locations
    │       └─→ Geocode each
    │
    └─→ Step 6: Background Learning (ASYNC)
        ├─→ Analyze regex successes/failures
        ├─→ Process user feedback
        └─→ Improve patterns over time
```

## How It Works

### 1. Regex Extraction (First)

- **Cost**: FREE
- **Speed**: Very fast (milliseconds)
- **Method**: Pattern matching with regex patterns
- **Use case**: Handles common location formats like:
  - "X Town, Y County, Z State"
  - "X in Y Town"
  - "X area, Y Town"
  - "X (State)"

All regex matches are geocoded immediately. Locations with:
- High confidence (score ≥ 0.7) and valid coordinates → **SUCCESS**
- Low confidence or no coordinates → **NEEDS HELP** (marked as gap)

### 2. Gap Identification

The system identifies regions that need additional extraction:

- **No matches**: Areas of document where regex found nothing
- **Low confidence**: Regex found something but geocoding failed or scored < 0.7
- **Too coarse**: Found county/state only (no coordinates)

These gap regions are passed to the next stage.

### 3. Ollama Extraction (Second)

- **Cost**: FREE (local LLM)
- **Speed**: Fast (2-5 seconds per region)
- **Method**: Local LLM inference
- **Focus**: Only processes gap regions identified in Step 2

Ollama extracts location strings from the gap regions and geocodes them. This catches patterns that regex missed.

### 4. Azure AI Extraction (Last Resort)

- **Cost**: PAID (Azure API calls)
- **Speed**: Moderate (5-10 seconds)
- **Method**: Cloud-based LLM (GPT-4.1-mini)
- **Use case**: Only when regex AND Ollama both failed

Azure AI processes remaining gaps and is filtered to avoid duplicates with regex/Ollama results.

### 5. Background Learning

While extraction happens, the system collects data for pattern improvement:

- **Regex successes**: What worked well → reinforce patterns
- **Regex failures**: What was missed → identify new patterns needed
- **Ollama successes**: What Ollama caught that regex missed → learn from this
- **User feedback**: Corrections and validations → improve accuracy

This data feeds into the learning mechanism to gradually improve regex patterns.

## Configuration

### Confidence Threshold

The system uses `FUZZY_THRESHOLD` (default: 0.7) to determine if geocoding was successful:

- Score ≥ 0.7 → High confidence → Keep result
- Score < 0.7 → Low confidence → Try next method
- No coordinates → Try next method

### Enabling/Disabling Methods

In `app/core/config.py`:

```python
ENABLE_OLLAMA: bool = True  # Enable Ollama extraction
ENABLE_AI_EXTRACTION: bool = True  # Enable Azure AI (last resort)
```

### Ollama Model Selection

Recommended model for M4 MacBook Pro (24GB RAM): **llama3.2:3b**

Set in `.env`:
```env
OLLAMA_MODEL=llama3.2:3b
```

Or use existing models:
```env
OLLAMA_MODEL=llama3  # Uses llama3:latest
```

## Results Structure

The `ExtractionResult` now includes:

- `regex_locations`: Locations found by regex
- `ollama_locations`: Locations found by Ollama
- `ai_locations`: Locations found by Azure AI (last resort)

All locations are tracked with their extraction method, so you can see which method succeeded for each location.

## Benefits

1. **Cost Optimization**: Azure AI only used when absolutely necessary
2. **Speed**: Regex handles most cases instantly
3. **Learning**: Ollama catches what regex misses, feeding into pattern improvement
4. **Reliability**: Multiple fallbacks ensure nothing is missed
5. **Transparency**: Clear tracking of which method found each location

## Future Enhancements

The learning mechanism will:

1. **Analyze patterns**: Use Ollama to analyze feedback and identify common mistakes
2. **Generate new patterns**: Create improved regex patterns based on failures
3. **Update patterns**: Dynamically add new patterns to the regex extractor
4. **Track performance**: Monitor which patterns work best

This creates a self-improving system that gets better over time without manual intervention.


