# 🏆 SuperInstance Enhancement: Budget Enforcer

> Aider with token spending limits. Same Aider. **Affordable Aider.**

_This is a SuperInstance fork of [Aider-AI/aider](https://github.com/Aider-AI/aider) (45K+ stars) — Aider with budget enforcement built in._

The Budget Enforcer wraps Aider's token tracking with configurable budget limits per model. Set daily, weekly, or monthly caps and get proactive warnings before you blow your API budget.

## Features

- **📊 Real-time budget tracking** — Know exactly what each model costs per session
- **🔔 Phase detection** — 60% warning, 85% smart downgrade suggestion, 100% hard pause
- **🔄 Auto-downgrade suggestions** — "You're at 85% of $200/month. Switch from Claude Opus to Sonnet to save $47."
- **📝 Historical spend log** — JSON-based with per-model, per-period aggregation
- **🎯 Configurable limits** — Per-model daily/weekly/monthly caps via `.aider.budget.toml`

## Quick Start

```bash
# Install the budget enforcer
pip install -e /path/to/budget_enforcer

# Run aider with budget enforcement
./scripts/aider-budget
```

## Configuration

Create `.aider.budget.toml` in your project root:

```toml
[default]
monthly = 50        # $50/month for all models combined

[models."claude-sonnet-4-20250514"]
monthly = 30        # $30/month cap for Claude Sonnet
daily = 5           # $5/day cap

[models."gpt-4o"]
monthly = 20
weekly = 10
```

## How It Works

1. The wrapper intercepts API calls and tracks token usage per model
2. It uses litellm's pricing data to calculate real-time costs
3. Before each API call, it checks the current phase against configured limits
4. At 60%: console warning with remaining budget
5. At 85%: suggests a cheaper model alternative with savings calculation
6. At 100%: pauses execution until the next period

## License

Same as Aider — Apache 2.0

---

🏆 **SuperInstance Enhancement: Budget Enforcer — Aider with token spending limits. Same Aider. Affordable Aider.**


---

## 🏆 SuperInstance Enhancement: Budget Enforcer

> Aider with token spending limits. Same Aider. **Affordable Aider.**

The Budget Enforcer wraps Aider's token tracking with configurable budget limits per model. Set daily, weekly, or monthly caps and get proactive warnings before you blow your API budget.

### Features

- **📊 Real-time budget tracking** — Know exactly what each model costs per session
- **🔔 Phase detection** — 60% warning, 85% smart downgrade suggestion, 100% hard pause
- **🔄 Auto-downgrade suggestions** — "You're at 85% of $200/month. Switch from Claude Opus to Sonnet to save $47."
- **📝 Historical spend log** — JSON-based with per-model, per-period aggregation
- **🎯 Configurable limits** — Per-model daily/weekly/monthly caps via `.aider.budget.toml`

### Quick Start

```bash
# Install the budget enforcer
pip install -e /path/to/budget_enforcer

# Run aider with budget enforcement
./scripts/aider-budget
```

### Configuration

Create `.aider.budget.toml` in your project root:

```toml
[default]
monthly = 50        # $50/month for all models combined

[models."claude-sonnet-4-20250514"]
monthly = 30        # $30/month cap for Claude Sonnet
daily = 5           # $5/day cap

[models."gpt-4o"]
monthly = 20
weekly = 10
```

### How It Works

1. The wrapper intercepts API calls and tracks token usage per model
2. It uses litellm's pricing data to calculate real-time costs
3. Before each API call, it checks the current phase against configured limits
4. At 60%: console warning with remaining budget
5. At 85%: suggests a cheaper model alternative with savings calculation
6. At 100%: pauses execution until the next period
