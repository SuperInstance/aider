# SuperInstance Changes — Aider Fork

> This document tracks all modifications made to the [Aider-AI/aider](https://github.com/Aider-AI/aider) fork maintained by [SuperInstance](https://github.com/SuperInstance).

## What We Changed

### 1. Default Model: z.ai GLM-5.1

The default model is now `openai/zai/glm-5.1` (previously `gpt-4o`). When `ZAI_API_KEY` is set in the environment, aider automatically configures litellm to route requests to z.ai's OpenAI-compatible API.

### 2. Provider Configuration (z.ai primary, DeepInfra fallback, NO OpenAI)

| Provider | Endpoint | API Key Env Var | Role |
|----------|----------|-----------------|------|
| **z.ai** | `https://api.z.ai/v1` | `ZAI_API_KEY` | Primary (default) |
| **DeepInfra** | `https://api.deepinfra.com/v1/openai` | `DEEPINFRA_API_KEY` | Fallback |

The configuration is handled in `aider/llm.py`:
- If `ZAI_API_KEY` is set and `OPENAI_API_KEY` is not, z.ai is automatically configured as the default provider
- `OPENAI_API_BASE` is set to `https://api.z.ai/v1` unless already specified

### 3. Model Aliases

New model aliases added to `aider/models.py`:

| Alias | Model | Provider |
|-------|-------|----------|
| `glm` | `openai/zai/glm-5.1` | z.ai |
| `glm-5.1` | `openai/zai/glm-5.1` | z.ai |
| `zai` | `openai/zai/glm-5.1` | z.ai |
| `deepinfra` | `openai/Qwen/Qwen2.5-72B-Instruct` | DeepInfra |
| `deepinfra-glm` | `openai/zai/glm-5.1` | DeepInfra |

Usage:
```bash
aider --model glm          # Uses z.ai GLM-5.1
aider --model deepinfra    # Uses DeepInfra Qwen 2.5 72B
```

### 4. Budget Enforcer

The Budget Enforcer (pre-existing SuperInstance addition) remains unchanged — it enforces spending limits and can suggest model downgrades.

## Configuration Guide

### Quick Start (z.ai as primary)

```bash
# Set your z.ai API key
export ZAI_API_KEY="your-zai-api-key"

# Run aider — it will automatically use z.ai GLM-5.1
aider
```

### Using DeepInfra as fallback

```bash
export ZAI_API_KEY="your-zai-key"
export DEEPINFRA_API_KEY="your-deepinfra-key"

# Primary: z.ai GLM-5.1
aider --model glm

# Fallback: switch to DeepInfra when needed
aider --model deepinfra
```

### Using DeepInfra as primary

```bash
export DEEPINFRA_API_KEY="your-deepinfra-key"
export OPENAI_API_KEY=$DEEPINFRA_API_KEY
export OPENAI_API_BASE="https://api.deepinfra.com/v1/openai"

aider --model "openai/Qwen/Qwen2.5-72B-Instruct"
```

### Budget Enforcer with SuperInstance providers

```toml
# .aider.budget.toml
[default]
monthly = 50

[models."openai/zai/glm-5.1"]
monthly = 30
daily = 5

[models."openai/Qwen/Qwen2.5-72B-Instruct"]
monthly = 10
```

## Files Modified

| File | Change |
|------|--------|
| `aider/llm.py` | Added z.ai/DeepInfra auto-configuration from env vars |
| `aider/models.py` | Changed default model to `openai/zai/glm-5.1`, added SuperInstance aliases |
| `SUPERINSTANCE_CHANGES.md` | This document |
| `README.md` | Added fork notice with provider info |

## Files NOT Modified

- `aider/` core logic (coders, commands, etc.) — unchanged
- `budget_enforcer/` — unchanged, works with all providers
- Test suite — unchanged, existing tests still pass

## Model Roster

| Name | Model ID | Provider | Cost Tier | Use Case |
|------|----------|----------|-----------|----------|
| GLM-5.1 | `zai/glm-5.1` | z.ai | Primary | General coding, default |
| Qwen 2.5 72B | `Qwen/Qwen2.5-72B-Instruct` | DeepInfra | Budget | Cost-optimized fallback |

## Why This Approach

litellm (which aider uses for all LLM calls) supports any OpenAI-compatible API through the `openai/` prefix. Both z.ai and DeepInfra expose OpenAI-compatible chat completion endpoints, so:

- **No code changes to the completion path** — litellm handles routing
- **Environment-driven configuration** — set `ZAI_API_KEY` and you're done
- **Budget Enforcer still works** — tracks spend per model regardless of provider
- **Fallback is manual** — switch models with `--model` flag (or use budget enforcer's auto-downgrade)

---

*Last updated: 2026-06-07*
*Fork maintained by [SuperInstance](https://github.com/SuperInstance)*
