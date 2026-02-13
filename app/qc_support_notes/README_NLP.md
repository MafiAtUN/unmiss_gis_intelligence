# NLP Analysis Mode for QC Support Notes

## Overview

The QC Support Notes module now includes an **NLP analysis mode** using spaCy for more sophisticated linguistic analysis compared to simple regex patterns.

## Installation

### 1. Install spaCy

```bash
pip install spacy>=3.7.0
```

### 2. Download spaCy Language Model

You need to download at least one English model:

```bash
# Small model (recommended for speed, ~12MB)
python -m spacy download en_core_web_sm

# Medium model (better accuracy, ~40MB)
python -m spacy download en_core_web_md

# Large model (best accuracy, ~560MB)
python -m spacy download en_core_web_lg
```

The small model (`en_core_web_sm`) is recommended as it provides a good balance between speed and accuracy.

## Features

### Advantages over Regex Mode

1. **Named Entity Recognition (NER)**
   - Detects dates, locations, persons, organizations automatically
   - Better identification of PII and geographic references
   - More accurate location detection

2. **Part-of-Speech Tagging**
   - Identifies verbs more accurately (including lemmatization)
   - Better detection of definitive verbs
   - Understands word forms (confirmed, confirms, confirming → confirm)

3. **Dependency Parsing**
   - Understands sentence structure
   - Better detection of attribution phrases
   - Identifies relationships between words (e.g., verbs and their subjects/objects)

4. **Sentence Segmentation**
   - Properly identifies sentence boundaries
   - More accurate context extraction
   - Better analysis of facts vs. analysis mixing

### What NLP Mode Checks

- **Vague "When"**: Uses NER to detect DATE entities and checks if they're specific dates or vague references
- **Vague "Where"**: Uses NER to detect GPE/LOC entities and checks for nearby administrative units
- **Vague "Who"**: Uses NER to detect PERSON/ORG entities and checks for generic actor descriptions
- **Facts vs Analysis**: Uses dependency parsing to detect attribution in sentences with interpretive terms
- **Corroboration**: Uses POS tagging and dependency parsing to identify definitive verbs and check for source framing

## Usage

1. In the QC Support Notes page, select **"NLP"** as the analysis mode
2. Choose a spaCy model (default: `en_core_web_sm`)
3. Run the analysis as usual

## Comparison: Regex vs NLP

| Feature | Regex Mode | NLP Mode |
|---------|-----------|----------|
| Speed | ⚡⚡⚡ Very Fast | ⚡⚡ Fast |
| Accuracy | ⚡⚡ Good | ⚡⚡⚡ Better |
| Resource Usage | Low | Medium |
| Installation | Simple | Requires model download |
| Understanding | Pattern matching | Linguistic understanding |
| PII Detection | Basic patterns | Advanced NER |
| Sentence Structure | Limited | Full parsing |

## Hybrid Mode

You can enable **Hybrid Mode** to combine NLP and Regex results:
- NLP provides sophisticated linguistic analysis
- Regex catches edge cases and provides fallback
- Results are merged, avoiding duplicates

## Troubleshooting

### Model Not Found Error

If you see "OSError: Can't find model 'en_core_web_sm'", download it:

```bash
python -m spacy download en_core_web_sm
```

### Performance Issues

- Use `en_core_web_sm` for fastest performance
- Use `en_core_web_md` for better accuracy
- Use `en_core_web_lg` only if you need the best accuracy and have sufficient memory

### Fallback Behavior

If spaCy is not available or model loading fails, the NLP analyzer will automatically fall back to regex mode.

