import unittest
from noc_bot.dm_session import clear_selected_unit, clear_session, get_selected_unit, set_selected_unit

class SelectedUnitSessionTests(unittest.TestCase):
    def setUp(self):
        clear_session(123)

    def test_set_and_get_selected_unit(self):
        set_selected_unit(123, "un2")
        self.assertEqual(get_selected_unit(123), "UN2")

    def test_clear_selected_unit(self):
        set_selected_unit(123, "UN3")
        clear_selected_unit(123)
        self.assertEqual(get_selected_unit(123), None)
