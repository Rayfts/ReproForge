import unittest

from calc import inclusive_count


class InclusiveCountTest(unittest.TestCase):
    def test_includes_both_endpoints(self) -> None:
        self.assertEqual(inclusive_count(1, 5), 5)


if __name__ == "__main__":
    unittest.main()
