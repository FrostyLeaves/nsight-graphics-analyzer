"""Smoke tests for the nsight-graphics-analyzer skill.

Run all tests:
    python -m unittest discover -s tests

Sample data layout
------------------
- `data/BASE/` ships with the 4 small `.xls` files cherry-picked from a real
  Nsight Graphics capture; they're enough to exercise every parser and every
  builder.
- `GPUTRACE_REGIMES.xls` is too big to commit (~300+ MB on real captures).
  Tests that need it look at the env var `NSIGHT_SKILL_REGIMES_SAMPLE`
  (path to a real REGIMES file). When unset the test calls `self.skipTest()`.
"""
