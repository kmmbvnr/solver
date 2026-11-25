"""Guard the common search entry point without installing competition checkers."""
import ast
from pathlib import Path
import unittest


class DemoEntrypointTests(unittest.TestCase):
    def test_benchmark_searches_use_the_shared_pipeline(self):
        demos = Path(__file__).resolve().parents[1] / "demos" / "roadef"
        searches = [(year / "solve.py", "solve") for year in demos.iterdir() if year.is_dir() and year.name.isdigit()]
        searches.extend([(demos / "2026/sparse_search.py", "solve"), (demos / "2026/refine.py", "refine")])
        for path, entry in searches:
            with self.subTest(path=path):
                tree = ast.parse(path.read_text())
                self.assertTrue(any(isinstance(node, ast.ImportFrom) and node.module == "shiftopt"
                                    and any(alias.name == "run_pipeline" for alias in node.names)
                                    for node in tree.body))
                function = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == entry)
                self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                                    and node.func.id == "run_pipeline" for node in ast.walk(function)))
