import unittest
from unittest.mock import patch

from noc_bot import sources


class SourcesUnitParamTests(unittest.TestCase):
    def test_get_latest_per_check_uses_explicit_unit(self):
        with patch.object(sources, "query_rows", return_value=[]), patch.object(sources, "_read_last_log_ts", return_value=None), patch.object(sources, "_file_mtime", return_value=None):
            sources.get_latest_per_check("UN2")

        calls = getattr(sources.query_rows, "call_args_list", [])
        unit_calls = [c for c in calls if len(c.args) >= 2 and c.args[1] == ("UN2",)]
        self.assertTrue(unit_calls)
