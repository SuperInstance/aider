# 💰 Budget Enforcer — Token Spending Limits for Aider

A [SuperInstance](https://github.com/SuperInstance) enhancement to [Aider](https://github.com/Aider-AI/aider) (45K+ stars). Same Aider. With spending limits.

---

## The Scenario

You're pair-programming with Claude Opus via Aider. Three hours deep in a refactor. You check your API dashboard: **$89 spent today.** The refactor isn't done.

You could power through and let the meter run. Or you could let the Budget Enforcer catch you before that happens.

## Setup

Create `.aider.budget.toml` in your project root:

```toml
[default]
monthly = 50  # $50/month default for any model

[models."claude-sonnet-4-20250514"]
monthly = 30
daily = 5

[models."gpt-4o"]
monthly = 20
weekly = 10
```

Run with:

```bash
pip install -e /path/to/budget_enforcer
./scripts/aider-budget
```

You'll see:

```
📊 Budget Enforcer active — limits from .aider.budget.toml
   [default] monthly=50
   [claude-sonnet-4-20250514] monthly=30, daily=5
   [gpt-4o] monthly=20, weekly=10
```

## What Happens Next

### Phase 1 — Under 60%

Nothing. Aider works as usual. The enforcer tracks spend in `~/.aider/budget-spend.json` but stays quiet.

### Phase 2 — 60-85%

```
⚡ Budget notice: claude-opus-4-20250514 at 68% of $200/month. $64.00 remaining.
```

### Phase 3 — 85% → The Downgrade Chain

```
⚠️ Budget warning: claude-opus-4-20250514 at 85% of $200/month.
   Switch from claude-opus-4-20250514 to claude-sonnet-4-20250514
   to save $23.00 (switch from Opus to Sonnet, ~67% lower cost).
```

One `Ctrl+C`, then restart aider with `--model claude-sonnet-4-20250514`. The enforcer keeps tracking.

### Phase 4 — Hard Pause

```
⛔ Budget paused: claude-opus-4-20250514 has exceeded its limit.
   Try a cheaper model or wait for the next period.
```

## The Result

You finished the refactor at **$31** instead of $89. The last 40% of edits used Sonnet — you couldn't tell the difference.

## How It Works

Three things under the hood:

1. **Per-model spend tracking** — Each API call records input/output tokens, cost, and model to a JSON history
2. **Periodic budget check** — Every call checks daily/weekly/monthly spend against configured limits
3. **Phase-based response** — `ok` (≤60%) → `warning` (60-85%) → `suggest` (85-100%) → `paused` (≥100%)

The downgrade suggestions are hardcoded to known model pricing tiers:

| If you're on... | Suggests... | Savings |
|---|---|---|
| `claude-opus-4-20250514` | `claude-sonnet-4-20250514` | ~67% |
| `gpt-4o` | `gpt-4o-mini` | ~90% |
| `o1` | `gpt-4o` | ~85% |

## Config Reference

`.aider.budget.toml` supports three sections:

- `[default]` — fallback limits for any model not explicitly listed
- `[models."model-name"]` — per-model limits that override defaults

Each section accepts `daily`, `weekly`, and `monthly` as dollar values.

## The Tests

```bash
pytest budget_enforcer/tests/test_budget.py -v
```

26 tests covering phase threshold boundaries, TOML parsing with inline comments, spend history persistence, downgrade suggestions per model, and end-to-end lifecycle scenarios.

## License

Apache 2.0 (same as Aider)
