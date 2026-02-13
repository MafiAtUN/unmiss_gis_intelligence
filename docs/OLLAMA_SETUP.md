# Ollama Setup Guide

This guide explains how to configure Ollama for the document location extraction learning system.

## Recommended Models for M4 MacBook Pro (24GB RAM)

Based on your hardware, here are the recommended models in order of preference:

### 1. **llama3.2:3b** (RECOMMENDED) ⭐
- **Size:** ~2GB
- **Speed:** Very fast
- **Quality:** Excellent for regex pattern generation
- **Memory usage:** ~4-6GB when running
- **Best for:** Perfect balance of speed and quality

```bash
ollama pull llama3.2:3b
```

### 2. **llama3.2:1b** (Fastest)
- **Size:** ~1.3GB
- **Speed:** Extremely fast
- **Quality:** Good for simple pattern generation
- **Memory usage:** ~2-3GB when running
- **Best for:** Maximum speed, simple tasks

```bash
ollama pull llama3.2:1b
```

### 3. **gemma2:2b** (Alternative)
- **Size:** ~1.6GB
- **Speed:** Very fast
- **Quality:** Good
- **Memory usage:** ~3-4GB when running
- **Best for:** Lightweight alternative

```bash
ollama pull gemma2:2b
```

### Models You Already Have

You currently have these models installed:

- **llama3:latest** (likely 8B, ~4.7GB) - Works but slower than needed
- **mistral:latest** (likely 7B, ~4.4GB) - Works but larger than needed

These will work fine, but they're overkill for regex pattern generation and will use more memory than necessary.

## Configuration

### Option 1: Use Environment Variables (Recommended)

Add to your `.env` file:

```env
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2:3b
ENABLE_OLLAMA=true
```

### Option 2: Use Existing Models

If you want to use your existing models without downloading new ones:

```env
OLLAMA_MODEL=llama3
# or
OLLAMA_MODEL=mistral
```

### Option 3: Update Config File Directly

Edit `app/core/config.py` and change the default:

```python
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
```

## Verifying Setup

1. **Check Ollama is running:**
   ```bash
   ollama list
   ```

2. **Test the connection:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

3. **Test a model:**
   ```bash
   ollama run llama3.2:3b "Hello, generate a regex pattern"
   ```

## Usage in the Application

Once configured, the Ollama helper will automatically:

1. Check if Ollama is available on startup
2. Use the configured model for pattern generation
3. Fall back gracefully if Ollama is unavailable

The learning system will use Ollama to:
- Generate new regex patterns from user feedback
- Analyze common mistakes in extractions
- Suggest improvements to existing patterns

## Performance Tips

- **For development/testing:** Use `llama3.2:1b` or `llama3.2:3b` for faster responses
- **For production:** Use `llama3.2:3b` for best balance
- **If you have multiple models:** The system will use whichever is specified in config

## Troubleshooting

**Issue:** Ollama not detected
- Make sure Ollama is running: `ollama serve` (usually runs automatically)
- Check the base URL in config matches your Ollama setup

**Issue:** Model not found
- Make sure you've pulled the model: `ollama pull llama3.2:3b`
- Check model name matches exactly (case-sensitive)

**Issue:** Slow responses
- Use a smaller model (3b or 1b instead of 8b/7b)
- Check system resources aren't constrained


