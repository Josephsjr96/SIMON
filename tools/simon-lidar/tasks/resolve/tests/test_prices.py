import unittest
from prices import round_price


class TestPrices(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(round_price(1.234), 1.23)

    def test_half_up(self):
        self.assertEqual(round_price(2.675), 2.68)

    def test_half_up_small(self):
        self.assertEqual(round_price(1.005), 1.01)


if __name__ == "__main__":
    unittest.main()
