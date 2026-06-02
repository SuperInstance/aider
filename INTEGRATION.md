# INTEGRATION.md — Budget Enforcer Integration

## What Was Added

This fork adds **budget enforcement** to Aider — a Python package and wrapper script that tracks token spending per model and enforces configurable daily/weekly/monthly budget limits.

## Files Added

```
budget_enforcer/
├── __init__.py              # Core package: BudgetConfig, BudgetEnforcer, spend tracking
├── tests/
│   ├── __init__.py
│   └── test_budget.py       # 25+ tests covering all phases, edge cases, integration
scripts/
├── aider-budget             # Wrapper script: runs aider with budget enforcement
setup.py                     # Package installer
INTEGRATION.md               # This file
```

## Architecture

### How It Works

1. **Configuration**: `.aider.budget.toml` in the project root defines per-model limits
2. **Interception**: The `BudgetEnforcer` class reads spend history from `~/.aider/budget-spend.json`
3. **Phase Detection**: Before each API call, check the current budget phase:
   - **< 60%**: OK — proceed normally
   - **60–85%**: WARNING — console message with remaining budget
   - **85–100%**: SUGGEST — suggests a cheaper model with savings calculation
   - **>= 100%**: PAUSED — halts execution until the next period
4. **Cost Calculation**: Uses litellm's pricing data (`input_cost_per_token`, `output_cost_per_token`) to compute real-time costs
5. **Historical Logging**: All spend events are persisted to JSON with 90-day retention

### Integration Points

The Budget Enforcer integrates with Aider at these points:

| Aider Component | Integration |
|----------------|-------------|
| `models.Model.info` | Reads `input_cost_per_token` and `output_cost_per_token` for cost calculations |
| `litellm.token_counter()` | Token counts used for spend recording |
| Model name resolution | Uses same model names as Aider's config |
| `.aider/` directory | Shares the same config directory for spend history |

### Key Design Decisions

- **Standalone package**: The Budget Enforcer is a separate Python package, not patched into Aider's core. This makes it easy to maintain alongside upstream changes.
- **CLI wrapper**: `scripts/aider-budget` wraps `aider` with the enforcer pre-loaded, making it a drop-in replacement.
- **TOML config**: Uses a familiar, human-readable config format that follows `.aider.conf.yml` patterns.

## Usage

### Install

```bash
pip install -e /path/to/fork
```

Or just add `budget_enforcer/` to your PYTHONPATH and use the wrapper script.

### Run

```bash
# Instead of: aider --model claude-sonnet-4-20250514
./scripts/aider-budget --model claude-sonnet-4-20250514
```

### Configure

```toml
# .aider.budget.toml
[default]
monthly = 100

[models."claude-sonnet-4-20250514"]
monthly = 50
daily = 10

[models."gpt-4o"]
monthly = 30
weekly = 20
```

## Development

```bash
# Run tests
python -m pytest budget_enforcer/tests/test_budget.py -v

# Run with coverage
python -m pytest budget_enforcer/tests/test_budget.py --cov=budget_enforcer -v
```

## Future Work

- Direct monkey-patching of Aider's `sendchat.py` for per-request interception
- Slack/email notifications at budget thresholds
- Multi-user spend aggregation
- Export to CSV/Google Sheets
