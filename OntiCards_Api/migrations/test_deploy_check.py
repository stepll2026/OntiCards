import runpy
import unittest
from pathlib import Path


class ChainTests(unittest.TestCase):
    def setUp(self):
        self.module = runpy.run_path(str(Path(__file__).with_name("deploy_check.py")))

    def check(self, downs):
        return self.module["check_chain"]({r: {"down": d} for r, d in downs.items()})

    def failed(self):
        return any(r[0] == "FAIL" for r in self.module["results"])

    def test_disconnected_cycles(self):
        for cycle in ({"a": "b", "b": "a"}, {"a": "a"},
                      {"tail": "a", "a": "b", "b": "a"}):
            with self.subTest(cycle=cycle):
                self.module["results"].clear()
                self.check({"base": None, **cycle})
                self.assertTrue(self.failed())

    def test_valid_chains(self):
        for downs, head in (({"base": None}, "base"),
                            ({"base": None, "next": "base"}, "next"),
                            ({str(i): str(i - 1) if i else None
                              for i in range(2000)}, "1999")):
            with self.subTest(head=head):
                self.module["results"].clear()
                self.assertEqual(self.check(downs), (head, head))
                self.assertFalse(self.failed())

    def test_existing_invalid_inputs(self):
        for downs in ({}, {"a": "b", "b": "a"}, {"a": "missing"},
                      {"a": None, "b": None}):
            with self.subTest(downs=downs):
                self.module["results"].clear()
                self.check(downs)
                self.assertTrue(self.failed())

    def test_repository_baseline(self):
        revs = self.module["collect_revisions"]()
        self.module["check_chain"](revs)
        self.assertFalse(self.failed())


if __name__ == "__main__":
    unittest.main()
