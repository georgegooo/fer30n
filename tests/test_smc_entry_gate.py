import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSMCEntryGate(unittest.TestCase):
    def test_grade_c_is_soft_pass(self):
        from core.smc_entry_engine import should_allow_smc_entry

        self.assertTrue(should_allow_smc_entry(False, "C"))

    def test_none_grade_is_soft_pass(self):
        from core.smc_entry_engine import should_allow_smc_entry

        self.assertTrue(should_allow_smc_entry(False, "NONE"))

    def test_lower_grade_still_blocks(self):
        from core.smc_entry_engine import should_allow_smc_entry

        self.assertFalse(should_allow_smc_entry(False, "B"))


if __name__ == "__main__":
    unittest.main()
