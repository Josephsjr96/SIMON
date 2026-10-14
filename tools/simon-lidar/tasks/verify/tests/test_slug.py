import unittest
from slug import slugify


class TestSlug(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_extra_spaces(self):
        self.assertEqual(slugify("  Hello   World "), "hello-world")


if __name__ == "__main__":
    unittest.main()
