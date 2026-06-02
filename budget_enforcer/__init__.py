"""Budget Enforcer — Token spending limits for Aider.

Intercepts Aider's token tracking and enforces configurable budget limits
per model, with phase-based warnings and auto-downgrade suggestions.
"""

from pathlib import Path
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any
import json
import os


VERSION = "0.1.0"

# Phases
PHASE_OK = "ok"                        # < 60%
PHASE_WARNING = "warning"              # 60-85%
PHASE_DOWNGRADE_SUGGEST = "suggest"    # 85-100%
PHASE_PAUSED = "paused"                # >= 100%

# Phase thresholds
THRESHOLD_WARNING = 0.60
THRESHOLD_SUGGEST = 0.85
THRESHOLD_PAUSED = 1.0


def get_spend_history_path() -> Path:
    """Return path to the historical spend log."""
    return Path.home() / ".aider" / "budget-spend.json"


def load_spend_history() -> dict:
    """Load historical spend data from JSON."""
    path = get_spend_history_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return {"spends": [], "models": {}}
    return {"spends": [], "models": {}}


def save_spend_history(data: dict):
    """Save spend history to JSON."""
    path = get_spend_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _get_period_range(period: str, reference: Optional[date] = None) -> tuple[date, date]:
    """Get (start, end) date range for a period relative to reference date."""
    ref = reference or date.today()

    if period == "daily":
        return ref, ref
    elif period == "weekly":
        start = ref - timedelta(days=ref.weekday())
        return start, start + timedelta(days=6)
    elif period == "monthly":
        start = ref.replace(day=1)
        if ref.month == 12:
            end = ref.replace(year=ref.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end = ref.replace(month=ref.month + 1, day=1) - timedelta(days=1)
        return start, end
    else:
        raise ValueError(f"Unknown period: {period}")


def get_spend_in_period(data: dict, model: str, period: str, ref: Optional[date] = None) -> float:
    """Get total spend for a model in a given period."""
    period_start, period_end = _get_period_range(period, ref)
    period_start_str = period_start.isoformat()
    period_end_str = period_end.isoformat()

    total = 0.0
    models_data = data.get("models", {}).get(model, {})
    for entry in models_data.get("entries", []):
        entry_date = entry.get("date", "")
        if period_start_str <= entry_date <= period_end_str:
            total += entry.get("cost", 0.0)
    return total


def record_spend(model: str, input_tokens: int, output_tokens: int,
                 input_cost_per_token: float, output_cost_per_token: float,
                 caching_discount: float = 1.0):
    """Record a spend event to the history log."""
    cost = (input_tokens * input_cost_per_token +
            output_tokens * output_cost_per_token) * caching_discount

    data = load_spend_history()
    today = date.today().isoformat()

    entry = {
        "date": today,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": round(cost, 6),
    }

    if model not in data.get("models", {}):
        if "models" not in data:
            data["models"] = {}
        data["models"][model] = {"entries": []}

    data["models"][model]["entries"].append(entry)
    data["spends"].append(entry)

    # Trim old entries (keep last 90 days for monthly tracking)
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    data["models"][model]["entries"] = [
        e for e in data["models"][model]["entries"]
        if e.get("date", "") >= cutoff
    ]

    save_spend_history(data)


class BudgetConfig:
    """Parsed budget configuration from .aider.budget.toml."""

    def __init__(self, path: Optional[Path] = None):
        self.path = path or Path.cwd() / ".aider.budget.toml"
        self.limits: Dict[str, Dict[str, float]] = {}
        self._load()

    def _load(self):
        """Load and parse .aider.budget.toml."""
        if not self.path.exists():
            return

        text = self.path.read_text()
        self._parse_toml(text)

    def _parse_toml(self, text: str):
        """Simple TOML parser (handles our limited schema)."""
        current_section = None
        current_model = None

        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Section header: [default] or [models."claude-sonnet-4-20250514"]
            if line.startswith("[") and line.endswith("]"):
                section = line[1:-1].strip()
                if section == "default":
                    current_section = "__default__"
                    current_model = "__default__"
                elif section.startswith("models."):
                    # Extract model name from quotes
                    model_name = section.split('"')[1] if '"' in section else section.split(".")[1]
                    current_section = "models"
                    current_model = model_name
                else:
                    current_section = None
                    current_model = None
                continue

            # Key = value
            if "=" in line and current_model:
                key, val = line.split("=", 1)
                key = key.strip()
                try:
                    val = float(val.strip().strip('"').strip("'"))
                except ValueError:
                    continue

                if current_model not in self.limits:
                    self.limits[current_model] = {}
                self.limits[current_model][key] = val

    def get_limit(self, model: str, period: str) -> Optional[float]:
        """Get budget limit for a model in a given period (daily/weekly/monthly)."""
        # Check model-specific limit first
        if model in self.limits:
            val = self.limits[model].get(period)
            if val is not None:
                return val

        # Fall back to default
        if "__default__" in self.limits:
            return self.limits["__default__"].get(period)

        return None

    def has_limits(self) -> bool:
        """Check if any limits are configured."""
        return len(self.limits) > 0


def calculate_phase(pct: float) -> str:
    """Determine the budget phase given a usage percentage (0.0 to inf)."""
    if pct >= THRESHOLD_PAUSED:
        return PHASE_PAUSED
    elif pct >= THRESHOLD_SUGGEST:
        return PHASE_DOWNGRADE_SUGGEST
    elif pct >= THRESHOLD_WARNING:
        return PHASE_WARNING
    return PHASE_OK


def get_cheaper_model(model: str, pct: float, period: str, total_budget: float,
                       spend_so_far: float) -> Optional[dict]:
    """Suggest a cheaper model alternative when approaching budget limits.

    Returns dict with model name, savings estimate, or None if no downgrade path.
    """
    # Mapping of expensive models to cheaper alternatives
    DOWNGRADES = {
        "claude-sonnet-4-20250514": {
            "cheaper": "claude-sonnet-4-5-20250929",
            "savings_description": "similar capability, ~20% lower cost",
            "cost_multiplier": 0.80,
        },
        "claude-opus-4-20250514": {
            "cheaper": "claude-sonnet-4-20250514",
            "savings_description": "switch from Opus to Sonnet, ~67% lower cost",
            "cost_multiplier": 0.33,
        },
        "claude-opus-4-1-20250805": {
            "cheaper": "claude-sonnet-4-20250514",
            "savings_description": "switch from Opus 4.1 to Sonnet 4, ~67% lower cost",
            "cost_multiplier": 0.33,
        },
        "claude-opus-4-6-20260205": {
            "cheaper": "claude-sonnet-4-5-20250929",
            "savings_description": "switch from Opus 4.6 to Sonnet 4.5, ~67% lower cost",
            "cost_multiplier": 0.33,
        },
        "gpt-4o": {
            "cheaper": "gpt-4o-mini",
            "savings_description": "switch from GPT-4o to GPT-4o-mini, ~90% lower cost",
            "cost_multiplier": 0.10,
        },
        "o1": {
            "cheaper": "gpt-4o",
            "savings_description": "switch from o1 to GPT-4o, ~85% lower cost",
            "cost_multiplier": 0.15,
        },
        "o1-preview": {
            "cheaper": "gpt-4o",
            "savings_description": "switch from o1-preview to GPT-4o, ~80% lower cost",
            "cost_multiplier": 0.20,
        },
        "o3-mini": {
            "cheaper": "gpt-4o-mini",
            "savings_description": "switch from o3-mini to GPT-4o-mini, ~90% lower cost",
            "cost_multiplier": 0.10,
        },
    }

    if model in DOWNGRADES:
        d = DOWNGRADES[model]
        projected = total_budget * pct * d["cost_multiplier"]
        savings = round(spend_so_far - (spend_so_far * d["cost_multiplier"]), 2)
        return {
            "from": model,
            "to": d["cheaper"],
            "savings": max(savings, 0.01),
            "description": d["savings_description"],
        }

    return None


class BudgetEnforcer:
    """Main budget enforcer that integrates with Aider's model system."""

    def __init__(self, config: Optional[BudgetConfig] = None):
        self.config = config or BudgetConfig()
        self.spend_data = load_spend_history()

    def check_budget(self, model: str) -> dict:
        """Check budget status for a given model.

        Returns:
            {
                "phase": "ok" | "warning" | "suggest" | "paused",
                "usage_pcts": {"daily": 0.0, "weekly": 0.0, "monthly": 0.0},
                "spends": {"daily": 0.0, "weekly": 0.0, "monthly": 0.0},
                "limits": {"daily": 0.0, "weekly": 0.0, "monthly": 0.0},
                "suggestion": None | {...},
                "message": "..."
            }
        """
        ref = date.today()
        result = {
            "phase": PHASE_OK,
            "usage_pcts": {},
            "spends": {},
            "limits": {},
            "suggestion": None,
            "message": "",
        }

        max_pct = 0.0
        any_limit = False

        for period in ("daily", "weekly", "monthly"):
            limit = self.config.get_limit(model, period)
            if limit is None or limit == 0:
                continue
            any_limit = True

            spend = get_spend_in_period(self.spend_data, model, period, ref)
            pct = spend / limit if limit > 0 else 0.0

            result["usage_pcts"][period] = round(pct, 4)
            result["spends"][period] = round(spend, 2)
            result["limits"][period] = limit

            max_pct = max(max_pct, pct)

        if not any_limit:
            return result

        phase = calculate_phase(max_pct)
        result["phase"] = phase

        if phase == PHASE_PAUSED:
            result["message"] = (
                f"⛔ Budget paused: {model} has exceeded its limit. "
                f"Try a cheaper model or wait for the next period."
            )
        elif phase == PHASE_DOWNGRADE_SUGGEST:
            suggestion = get_cheaper_model(model, max_pct, period, limit, spend)
            result["suggestion"] = suggestion
            if suggestion:
                result["message"] = (
                    f"⚠️ Budget warning: {model} at {max_pct:.0%} of ${limit}/{period}. "
                    f"Switch from {suggestion['from']} to {suggestion['to']} "
                    f"to save ${suggestion['savings']:.2f} "
                    f"({suggestion['description']})."
                )
            else:
                result["message"] = (
                    f"⚠️ Budget warning: {model} at {max_pct:.0%} of ${limit}/{period}."
                )
        elif phase == PHASE_WARNING:
            remaining = limit - spend
            result["message"] = (
                f"⚡ Budget notice: {model} at {max_pct:.0%} of ${limit}/{period}. "
                f"${remaining:.2f} remaining."
            )

        return result

    def record_and_check(self, model: str, input_tokens: int, output_tokens: int,
                         input_cost_per_token: float, output_cost_per_token: float,
                         caching_discount: float = 1.0) -> dict:
        """Record a spend event and return the resulting budget check."""
        record_spend(model, input_tokens, output_tokens,
                     input_cost_per_token, output_cost_per_token,
                     caching_discount)
        return self.check_budget(model)
