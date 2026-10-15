from django.test import TestCase

from app.services.cafe import rainforest


class CafeTest(TestCase):
    def test_rainforest(self):
        self.assertEqual(rainforest(60, 1400, False)["ganho_vs_sequeiro"], 42000)
