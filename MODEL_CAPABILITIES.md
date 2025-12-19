# Azure AI Foundry Model Capabilities & Cost Guide

## Overview
This document describes all available Azure AI Foundry deployments, their capabilities, costs, and recommended use cases for the South Sudan Geocoding application.

## Resource Summary

### 🎯 PRIMARY: UNMISS AI Foundry (East US 2) - **RECOMMENDED**
- **Endpoint**: `https://<your-endpoint>.cognitiveservices.azure.com/`
- **Location**: East US 2
- **Project**: unmiss / proj-default
- **Resource Group**: unmiss-hrd
- **Best For**: Primary resource with multiple model providers (OpenAI, Anthropic, xAI, Meta)
- **Total Deployments**: 9 active models

### Resource 2: openai-osaa (West Europe) - Fallback
- **Endpoint**: `https://<your-endpoint>.openai.azure.com/`
- **Location**: West Europe
- **Best For**: Cost-effective operations, European data residency

### Resource 3: unga-analysis (East US 2) - Fallback
- **Endpoint**: `https://<your-endpoint>.openai.azure.com/`
- **Location**: East US 2
- **Best For**: High-capability models, US-based operations

---

## Active Deployments - UNMISS AI Foundry (PRIMARY)

### 🟢 Cost-Effective Models (Recommended for Geocoding)

#### 1. gpt-4.1-mini ⭐ **BEST FOR GEOCODING**
- **Resource**: UNMISS AI Foundry
- **Model**: gpt-4.1-mini-2025-04-14 (OpenAI)
- **Status**: ✅ Succeeded
- **Rate Limits**: 250 req/min, 250,000 tokens/min
- **Capabilities**: 
  - Chat completion
  - Agents V2
  - Assistants
  - Structured responses
- **Cost**: ⭐⭐⭐⭐⭐ (Lowest)
- **Use Case**: **PRIMARY RECOMMENDATION for geocoding**
  - Structured place name extraction
  - JSON schema responses
  - General text parsing
  - Cost-optimized workflows
  - **Highest rate limits among cost-effective options**

#### 2. model-router
- **Resource**: UNMISS AI Foundry
- **Model**: model-router-2025-11-18 (OpenAI)
- **Status**: ✅ Succeeded
- **Rate Limits**: 100 req/min, 100,000 tokens/min
- **Capabilities**:
  - Intelligent routing
  - Chat completion
  - Agents V2
- **Cost**: ⭐⭐⭐⭐ (Very Low - automatic optimization)
- **Use Case**: **BEST for multi-model workflows**
  - Automatically selects optimal model
  - Cost optimization
  - Production environments

#### 3. grok-3-mini (xAI)
- **Resource**: UNMISS AI Foundry
- **Model**: grok-3-mini-1 (xAI)
- **Status**: ✅ Succeeded
- **Rate Limits**: 150 req/min, 150,000 tokens/min
- **Capabilities**: Chat completion, Agents V2
- **Cost**: ⭐⭐⭐⭐ (Low)
- **Use Case**: Cost-effective alternative from xAI provider

#### 4. claude-sonnet-4-5 (Anthropic)
- **Resource**: UNMISS AI Foundry
- **Model**: claude-sonnet-4-5-20250929 (Anthropic)
- **Status**: ✅ Succeeded
- **Rate Limits**: 150 req/min, 150,000 tokens/min
- **Capabilities**: Chat completion, Agents V2
- **Cost**: ⭐⭐⭐⭐ (Low-Medium)
- **Use Case**: Balanced Anthropic model, alternative to GPT

### 🟡 High Capability Models

#### 5. gpt-5.2-chat (Latest & Most Capable)
- **Resource**: UNMISS AI Foundry
- **Model**: gpt-5.2-chat-2025-12-11 (OpenAI)
- **Status**: ✅ Succeeded
- **Rate Limits**: 1,500 req/min, 150,000 tokens/min
- **Capabilities**:
  - Chat completion
  - Agents V2
  - Assistants
  - Latest features
- **Cost**: ⭐⭐ (Higher)
- **Use Case**: 
  - Most complex reasoning tasks
  - Latest model features needed
  - When other models fail
  - **Highest request rate limits**

#### 6. gpt-4.1
- **Resource**: UNMISS AI Foundry
- **Model**: gpt-4.1-2025-04-14 (OpenAI)
- **Status**: ✅ Succeeded
- **Rate Limits**: 150 req/min, 150,000 tokens/min
- **Capabilities**: Similar to gpt-4.1-mini with higher capability
- **Cost**: ⭐⭐⭐ (Medium)
- **Use Case**: 
  - Complex reasoning
  - When gpt-4.1-mini is insufficient

#### 7. claude-opus-4-1 (Anthropic - Highest Capability)
- **Resource**: UNMISS AI Foundry
- **Model**: claude-opus-4-1-20250805 (Anthropic)
- **Status**: ✅ Succeeded
- **Rate Limits**: 150 req/min, 150,000 tokens/min
- **Capabilities**: Chat completion, Agents V2
- **Cost**: ⭐⭐ (Higher)
- **Use Case**: Anthropic's most capable model, alternative to GPT-5

#### 8. Llama-4-Maverick-17B (Meta - Open Source)
- **Resource**: UNMISS AI Foundry
- **Model**: Llama-4-Maverick-17B-128E-Instruct-FP8 (Meta)
- **Status**: ✅ Succeeded
- **Rate Limits**: 100 req/min, 100,000 tokens/min
- **Capabilities**: Chat completion, Agents V2
- **Cost**: ⭐⭐⭐ (Medium)
- **Use Case**: Open-source alternative, Meta's Llama model

### 🔵 Specialized Models

#### 9. text-embedding-3-large (Embeddings)
- **Resource**: UNMISS AI Foundry
- **Model**: text-embedding-3-large (OpenAI)
- **Status**: ✅ Succeeded
- **Rate Limits**: 150 req/10sec, 150,000 tokens/min
- **Capabilities**:
  - Vector embeddings
  - Semantic search
  - Max 2048 inputs per request
- **Use Case**: 
  - Semantic similarity search
  - Vector database operations
  - Place name similarity matching

---

## Active Deployments - Other Resources (Fallback)

#### 1. OSAA (gpt-4.1-mini)
- **Resource**: openai-osaa
- **Model**: gpt-4.1-mini-2025-04-14
- **Status**: ✅ Succeeded
- **Rate Limits**: 1 req/min, 1000 tokens/min
- **Capabilities**: 
  - Chat completion
  - Agents V2
  - Assistants
  - Structured responses
- **Cost**: ⭐⭐⭐⭐⭐ (Lowest)
- **Use Case**: **RECOMMENDED for geocoding text extraction**
  - Structured place name extraction
  - JSON schema responses
  - General text parsing
  - Cost-optimized workflows

#### 2. model-router
- **Resource**: unga-analysis
- **Model**: model-router-2025-08-07
- **Status**: ✅ Succeeded
- **Rate Limits**: 230,000 req/min, 230,000 tokens/min
- **Capabilities**:
  - Intelligent routing
  - Chat completion
  - Agents V2
- **Cost**: ⭐⭐⭐⭐ (Very Low - automatic optimization)
- **Use Case**: **BEST for multi-model workflows**
  - Automatically selects optimal model
  - Cost optimization
  - High throughput scenarios

---

### 🟡 High Capability Models

#### 3. OSSAA (gpt-4o)
- **Resource**: openai-osaa
- **Model**: gpt-4o-2024-08-06
- **Status**: ✅ Succeeded
- **Rate Limits**: 100 req/min, 10,000 tokens/min
- **Capabilities**:
  - Chat completion
  - Agents V2
  - Assistants
  - JSON schema responses
  - Large context (128K tokens)
- **Cost**: ⭐⭐⭐ (Medium)
- **Use Case**: 
  - Complex reasoning
  - Large context requirements
  - JSON schema validation
  - When gpt-4.1-mini is insufficient

#### 4. gpt-4o-unga
- **Resource**: unga-analysis
- **Model**: gpt-4o-2024-11-20
- **Status**: ✅ Succeeded
- **Rate Limits**: 100 req/10sec, 100,000 tokens/min
- **Capabilities**: Similar to OSSAA with higher rate limits
- **Cost**: ⭐⭐⭐ (Medium)
- **Use Case**: 
  - High-throughput scenarios
  - When OSSAA rate limits are insufficient

#### 5. gpt-5-unga (Latest & Most Capable)
- **Resource**: unga-analysis
- **Model**: gpt-5-2025-08-07
- **Status**: ✅ Succeeded
- **Rate Limits**: 1,300 req/min, 130,000 tokens/min
- **Capabilities**:
  - Chat completion
  - Agents V2
  - Assistants
  - Latest features
- **Cost**: ⭐⭐ (Higher)
- **Use Case**: 
  - Most complex reasoning tasks
  - Latest model features needed
  - When other models fail

---

### 🔵 Specialized Models

#### 6. text-embedding-ada-002 (Embeddings)
- **Resources**: Both openai-osaa and unga-analysis
- **Model**: text-embedding-ada-002
- **Status**: ✅ Succeeded
- **Capabilities**:
  - Vector embeddings
  - Semantic search
  - Max 2048 inputs per request
- **Use Case**: 
  - Semantic similarity search
  - Vector database operations
  - Place name similarity matching

#### 7. whisper (Audio Transcription)
- **Resources**: Both openai-osaa and unga-analysis
- **Model**: whisper-001
- **Status**: ✅ Succeeded
- **Capabilities**:
  - Audio transcription
  - Audio translation
- **Use Case**: 
  - Speech-to-text
  - Audio file processing

#### 8. gpt-4o-transcribe-diarize (Advanced Audio)
- **Resource**: unga-analysis
- **Model**: gpt-4o-transcribe-diarize-2025-10-15
- **Status**: ✅ Succeeded
- **Rate Limits**: 10,000 req/min, 100,000 tokens/min
- **Capabilities**:
  - Advanced transcription
  - Speaker diarization
  - Large context (128K tokens)
- **Use Case**: 
  - Multi-speaker audio
  - Advanced transcription needs

---

## Cost & Efficiency Recommendations

### For Geocoding Text Extraction (Primary Use Case)

1. **Primary Choice**: `OSAA` (gpt-4.1-mini)
   - Most cost-effective
   - Sufficient for structured place name extraction
   - Good JSON schema support

2. **Fallback**: `OSSAA` (gpt-4o)
   - Use when OSAA fails or needs more capability
   - Better for complex/messy text
   - Larger context window

3. **Auto-Optimization**: `model-router`
   - Best for production with varying complexity
   - Automatically routes to optimal model
   - Highest throughput

### Cost Comparison (Approximate)

| Model | Relative Cost | Speed | Capability |
|-------|--------------|-------|------------|
| gpt-4.1-mini | ⭐⭐⭐⭐⭐ | Fast | Good |
| model-router | ⭐⭐⭐⭐ | Fast | Good (auto) |
| gpt-4o | ⭐⭐⭐ | Medium | Excellent |
| gpt-5 | ⭐⭐ | Medium | Best |

---

## Configuration in .env

The `.env` file contains all deployment configurations. Default settings use the most cost-effective option (OSAA) for geocoding.

To switch models, update:
```bash
AZURE_FOUNDRY_ENDPOINT=<endpoint>
AZURE_FOUNDRY_API_KEY=<key>
AZURE_OPENAI_DEPLOYMENT=<deployment-name>
```

---

## Rate Limits Summary

| Deployment | Requests | Tokens | Period |
|------------|----------|--------|--------|
| OSAA | 1 | 1,000 | 1 min |
| OSSAA | 100 | 10,000 | 1 min |
| model-router | 230,000 | 230,000 | 1 min |
| gpt-4o-unga | 100 | 100,000 | 10 sec |
| gpt-5-unga | 1,300 | 130,000 | 1 min |

---

## Best Practices

1. **Start with OSAA** (gpt-4.1-mini) for cost optimization
2. **Use model-router** for production with varying workloads
3. **Upgrade to gpt-4o** only when needed for complex cases
4. **Use gpt-5** sparingly for most complex scenarios
5. **Monitor costs** and adjust based on actual usage patterns

---

## Notes

- All active deployments have status "Succeeded"
- Disabled deployments (osaa-test, text-davinci-003) are not included
- Rate limits are per deployment, not shared across resources
- Consider data residency requirements (EU vs US) when selecting resource

