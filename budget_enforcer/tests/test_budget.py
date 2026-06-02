"""Tests for the Budget Enforcer.

Run with: python -m pytest budget_enforcer/tests/test_budget.py -v
"""

import tempfile
from pathlib import Path
from datetime import date
from unittest.mock import patch

from budget_enforcer import (
    BudgetConfig,
    BudgetEnforcer,
    load_spend_history,
    save_spend_history,
    calculate_phase,
    get_cheaper_model,
    get_spend_in_period,
    PHASE_OK,
    PHASE_WARNING,
    PHASE_DOWNGRADE_SUGGEST,
    PHASE_PAUSED,
    VERSION,
    get_spend_history_path,
)


class TestVersion:
    def test_version_exists(self):
        assert VERSION == "0.1.0"


class TestPhases:
    def test_ok_below_60(self):
        assert calculate_phase(0.0) == PHASE_OK
        assert calculate_phase(0.30) == PHASE_OK
        assert calculate_phase(0.59) == PHASE_OK

    def test_warning_at_60(self):
        assert calculate_phase(0.60) == PHASE_WARNING
        assert calculate_phase(0.75) == PHASE_WARNING
        assert calculate_phase(0.84) == PHASE_WARNING

    def test_suggest_at_85(self):
        assert calculate_phase(0.85) == PHASE_DOWNGRADE_SUGGEST
        assert calculate_phase(0.90) == PHASE_DOWNGRADE_SUGGEST
        assert calculate_phase(0.99) == PHASE_DOWNGRADE_SUGGEST

    def test_paused_at_100(self):
        assert calculate_phase(1.0) == PHASE_PAUSED
        assert calculate_phase(1.5) == PHASE_PAUSED

    def test_exact_threshold_boundaries(self):
        assert calculate_phase(0.599) == PHASE_OK
        assert calculate_phase(0.600) == PHASE_WARNING
        assert calculate_phase(0.850) == PHASE_DOWNGRADE_SUGGEST
        assert calculate_phase(1.000) == PHASE_PAUSED


class TestBudgetConfig:
    def test_empty_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            config = BudgetConfig(path)
            assert config.limits == {}
            assert not config.has_limits()

    def test_basic_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text("""
[default]
monthly = 50

[models."claude-sonnet-4-20250514"]
monthly = 30
daily = 5

[models."gpt-4o"]
monthly = 20
weekly = 10
""")
            config = BudgetConfig(path)
            assert config.has_limits()
            assert config.get_limit("claude-sonnet-4-20250514", "monthly") == 30
            assert config.get_limit("claude-sonnet-4-20250514", "daily") == 5
            assert config.get_limit("gpt-4o", "monthly") == 20
            assert config.get_limit("gpt-4o", "weekly") == 10

    def test_default_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text("[default]\nmonthly = 50\n")
            config = BudgetConfig(path)
            assert config.get_limit("some-other-model", "monthly") == 50

    def test_no_default_fallback_when_not_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text("""[models."gpt-4o"]\ndaily = 5\n""")
            config = BudgetConfig(path)
            assert config.get_limit("gpt-4o", "daily") == 5
            # No default, so other models get None
            assert config.get_limit("other", "daily") is None

    def test_toml_parsing_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text("""
# This is a comment
[default]
monthly = 50  # inline comment is ignored by our parser

[models."claude-opus-4-20250514"]
# Another comment
monthly = 200
daily = 25
""")
            config = BudgetConfig(path)
            assert config.limits["__default__"]["monthly"] == 50
            assert config.get_limit("claude-opus-4-20250514", "monthly") == 200
            assert config.get_limit("claude-opus-4-20250514", "daily") == 25


class TestSpendHistory:
    def test_spend_in_period_monthly(self):
        data = {
            "models": {
                "gpt-4o": {
                    "entries": [
                        {"date": "2026-06-01", "cost": 1.0},
                        {"date": "2026-06-02", "cost": 2.0},
                        {"date": "2026-05-30", "cost": 3.0},
                    ]
                }
            },
            "spends": [],
        }
        june_spend = get_spend_in_period(data, "gpt-4o", "monthly", date(2026, 6, 15))
        # 1.0 + 2.0 are in June, 3.0 is May
        assert june_spend == 3.0

    def test_spend_in_period_daily(self):
        data = {
            "models": {
                "gpt-4o": {
                    "entries": [
                        {"date": "2026-06-01", "cost": 1.0},
                        {"date": "2026-06-02", "cost": 2.0},
                    ]
                }
            },
            "spends": [],
        }
        daily_spend = get_spend_in_period(data, "gpt-4o", "daily", date(2026, 6, 1))
        assert daily_spend == 1.0

    def test_spend_in_period_weekly(self):
        data = {
            "models": {
                "gpt-4o": {
                    "entries": [
                        {"date": "2026-06-01", "cost": 5.0},  # Monday
                        {"date": "2026-06-02", "cost": 3.0},  # Tuesday
                        {"date": "2026-06-07", "cost": 1.0},  # Sunday
                    ]
                }
            },
            "spends": [],
        }
        # June 1 is Monday, so weekly range is June 1-7
        weekly_spend = get_spend_in_period(data, "gpt-4o", "weekly", date(2026, 6, 3))
        assert weekly_spend == 9.0  # 5.0 + 3.0 + 1.0

    def test_save_and_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            orig_path_fn = get_spend_history_path
            test_path = Path(tmp) / "test-spend.json"

            data = {
                "spends": [{"date": "2026-06-01", "model": "gpt-4o", "cost": 0.015}],
                "models": {
                    "gpt-4o": {
                        "entries": [
                            {"date": "2026-06-01", "model": "gpt-4o",
                             "input_tokens": 1000, "output_tokens": 200, "cost": 0.015}
                        ]
                    }
                },
            }
            save_spend_history(data)
            loaded = load_spend_history()
            assert "models" in loaded


class TestBudgetEnforcer:
    def test_no_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = BudgetConfig(Path(tmp) / ".aider.budget.toml")
            enforcer = BudgetEnforcer(config)
            result = enforcer.check_budget("gpt-4o")
            assert result["phase"] == PHASE_OK
            assert result["message"] == ""

    def test_within_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text("[default]\nmonthly = 100\n")
            config = BudgetConfig(path)
            enforcer = BudgetEnforcer(config)
            enforcer.spend_data = {"spends": [], "models": {}}
            result = enforcer.check_budget("gpt-4o")
            assert result["phase"] == PHASE_OK
            assert result["usage_pcts"]["monthly"] == 0.0

    def test_warning_phase(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text('''[models."gpt-4o"]\nmonthly = 10\n''')
            config = BudgetConfig(path)
            enforcer = BudgetEnforcer(config)
            enforcer.spend_data = {
                "models": {
                    "gpt-4o": {
                        "entries": [
                            {"date": date.today().isoformat(), "cost": 6.0},
                        ]
                    }
                },
                "spends": [],
            }
            result = enforcer.check_budget("gpt-4o")
            assert result["phase"] == PHASE_WARNING
            assert "remaining" in result["message"]

    def test_downgrade_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text('''[models."claude-opus-4-20250514"]\nmonthly = 200\n''')
            config = BudgetConfig(path)
            enforcer = BudgetEnforcer(config)
            enforcer.spend_data = {
                "models": {
                    "claude-opus-4-20250514": {
                        "entries": [
                            {"date": date.today().isoformat(), "cost": 170.0},
                        ]
                    }
                },
                "spends": [],
            }
            result = enforcer.check_budget("claude-opus-4-20250514")
            assert result["phase"] == PHASE_DOWNGRADE_SUGGEST
            assert result["suggestion"] is not None
            assert "sonnet" in result["suggestion"]["to"].lower()
            assert result["suggestion"]["savings"] > 0

    def test_paused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text('''[models."gpt-4o"]\nmonthly = 10\n''')
            config = BudgetConfig(path)
            enforcer = BudgetEnforcer(config)
            enforcer.spend_data = {
                "models": {
                    "gpt-4o": {
                        "entries": [
                            {"date": date.today().isoformat(), "cost": 10.0},
                        ]
                    }
                },
                "spends": [],
            }
            result = enforcer.check_budget("gpt-4o")
            assert result["phase"] == PHASE_PAUSED
            assert "exceeded" in result["message"].lower()

    def test_zero_limit_handling(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text('''[models."gpt-4o"]\nmonthly = 0\n''')
            config = BudgetConfig(path)
            enforcer = BudgetEnforcer(config)
            result = enforcer.check_budget("gpt-4o")
            # Zero limit — check should still run without error
            assert "phase" in result


class TestDowngradeSuggestions:
    def test_opus_to_sonnet(self):
        suggestion = get_cheaper_model(
            "claude-opus-4-20250514",
            pct=0.85,
            period="monthly",
            total_budget=200.0,
            spend_so_far=170.0,
        )
        assert suggestion is not None
        assert suggestion["from"] == "claude-opus-4-20250514"
        assert "sonnet" in suggestion["to"].lower()
        assert suggestion["savings"] > 0

    def test_gpt4o_to_mini(self):
        suggestion = get_cheaper_model(
            "gpt-4o",
            pct=0.85,
            period="monthly",
            total_budget=20.0,
            spend_so_far=17.0,
        )
        assert suggestion is not None
        assert "mini" in suggestion["to"].lower()

    def test_unknown_model(self):
        suggestion = get_cheaper_model(
            "unknown-model",
            pct=0.85,
            period="monthly",
            total_budget=100.0,
            spend_so_far=85.0,
        )
        assert suggestion is None


class TestIntegration:
    def test_end_to_end_lifecycle(self):
        """Simulate a complete budget lifecycle."""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text('''[models."gpt-4o"]\nmonthly = 10\n''')
            config = BudgetConfig(path)
            enforcer = BudgetEnforcer(config)

            # Initial: no spend yet
            result = enforcer.check_budget("gpt-4o")
            assert result["phase"] == PHASE_OK

            # Simulate hitting 85% of monthly budget
            enforcer.spend_data = {
                "models": {
                    "gpt-4o": {
                        "entries": [
                            {"date": date.today().isoformat(), "cost": 8.50},
                        ]
                    }
                },
                "spends": [],
            }
            result = enforcer.check_budget("gpt-4o")
            assert result["phase"] == PHASE_DOWNGRADE_SUGGEST
            assert result["suggestion"] is not None

            # Simulate hitting 100%
            enforcer.spend_data["models"]["gpt-4o"]["entries"][0]["cost"] = 10.0
            result = enforcer.check_budget("gpt-4o")
            assert result["phase"] == PHASE_PAUSED

    def test_claude_opus_85pct_scenario(self):
        """'You're at 85% of $200/month. Switch from Claude Opus to Sonnet to save $47.'"""
        config_data = '''[models."claude-opus-4-20250514"]\nmonthly = 200\n'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".aider.budget.toml"
            path.write_text(config_data)
            config = BudgetConfig(path)
            enforcer = BudgetEnforcer(config)
            enforcer.spend_data = {
                "models": {
                    "claude-opus-4-20250514": {
                        "entries": [
                            {"date": date.today().isoformat(), "cost": 170.0},
                        ]
                    }
                },
                "spends": [],
            }
            result = enforcer.check_budget("claude-opus-4-20250514")
            assert result["phase"] == PHASE_DOWNGRADE_SUGGEST
            assert result["suggestion"]["from"] == "claude-opus-4-20250514"
            assert "sonnet" in result["suggestion"]["to"].lower()
            # Verify the savings estimate is meaningful
            assert result["suggestion"]["savings"] >= 40.0
