import unittest
import ast, pathlib, calendar, datetime, urllib.parse, urllib
from scripts.bulk_monthly_capture import url_for
import sys,types
# Optional Google SDK is irrelevant for offline schedule checks.
# Extract candidates without importing its Drive client.
source_candidates=pathlib.Path("scripts/annual_actual_firstpass.py").read_text()
candidate_node=next(n for n in ast.parse(source_candidates).body if isinstance(n,ast.FunctionDef) and n.name=="candidates")
candidate_scope={"date":datetime.date,"urllib":urllib}
exec(compile(ast.Module(body=[candidate_node],type_ignores=[]),"<source-candidates>","exec"),candidate_scope)
candidates=candidate_scope["candidates"]
source=pathlib.Path("scripts/unified_annual_downloader.py").read_text()
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=="plan")
scope={"calendar":calendar,"datetime":datetime,"url_for":url_for,"candidates":candidates}
exec(compile(ast.Module(body=[node],type_ignores=[]),"<annual-plan>","exec"),scope)
plan=scope["plan"]
class ProductionBoundaries(unittest.TestCase):
    def test_all_months_four_sources(self):
        for month in range(1,13):
            units=plan(2024,month)
            self.assertEqual({u["source"] for u in units},{"TWSE","TPEx","MOPS","FinMind"})
            self.assertEqual(len(units),len({u["key"] for u in units}))
    def test_finmind_is_sample_not_full_market(self):
        for month in range(1,13):
            u=[x for x in plan(2024,month) if x["source"]=="FinMind"]
            self.assertEqual(len(u),1)
            self.assertIn("data_id=2330",u[0]["url"])
    def test_mops_is_revenue_only(self):
        for month in range(1,13):
            u=[x for x in plan(2024,month) if x["source"]=="MOPS"]
            self.assertEqual(len(u),2)
            self.assertTrue(all("t21sc03" in x["url"] for x in u))
    def test_non2024_mops_finmind_not_silent_full_year(self):
        self.assertFalse(any(x["source"] in ("MOPS","FinMind") for x in plan(2025,1)))
if __name__=="__main__":unittest.main()
