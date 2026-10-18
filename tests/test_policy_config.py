import tempfile
import unittest
from pathlib import Path

from rh_agent.agent import load_config


class ConfigPolicyTests(unittest.TestCase):
    def test_load_config_accepts_current_policy_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.toml"
            cfg.write_text(
                """
[policy]
dry_run = true
require_approval = true
approve_exits = false
approval_timeout_s = 60
max_order_notional = 50.0
max_orders_per_day = 20
max_daily_notional = 1000.0
max_symbol_notional_per_day = 150.0
count_exits = false
allow_options = false
allow_short_legs = false
entry_weekdays = [0, 1, 2, 3, 4]
allowed_symbols = []
tz = "America/New_York"
trade_window_start = "09:45"
trade_window_end = "15:30"
flatten_at = "15:45"
kill_switch_file = "STOP"
read_only_tools = []

[agent]
model = "claude-sonnet-5-5"
max_steps = 25
""".strip()
            )

            policy, _ = load_config(str(cfg))
            self.assertFalse(policy.approve_exits)
            self.assertEqual(policy.approval_timeout_s, 60)
            self.assertTrue(policy.dry_run)


if __name__ == "__main__":
    unittest.main()
