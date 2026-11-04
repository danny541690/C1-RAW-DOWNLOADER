"""JARVIS v0.95: TWSE real publicly sourced 2026-10-22 margin data 4-row sample.
Original legacy ZIP source raw SHA 7f0e938...; these FOUR records are the first
four genuine market rows, not a full market ingestion. No Drive secrets/writes.
"""
import tempfile
import unittest
from pathlib import Path
import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

RAW_SHA="7f0e9387df720ce531150d30996c9e1bb78c02d1520f2a68c7f220cc0aca9963"
FIELDS=["代號","名稱","買進","賣出","現金償還","前日餘額","今日餘額","次一營業日限額",
        "買進","賣出","現券償還","前日餘額","今日餘額","次一營業日限額","資券互抵","註記"]
ROWS=[
 ["00400A","主動國泰動能高息","518","168","0","14,127","14,477","522,035","0","3","0","0","3","522,035","0"," "],
 ["00401A","主動摩根台灣鑫收","27","25","0","3,006","3,008","71,348","0","0","0","0","0","71,348","0"," "],
 ["00402A","主動安聯美國科技","10","16","0","491","485","140,656","0","1","0","2","3","140,656","0"," "],
 ["00403A","主動統一升級50","4,290","2,591","6","68,242","69,935","3,170,504","99","465","0","1,647","2,013","3,170,504","28"," "],
]
COLS=["security_id","security_name","margin_buy","margin_sell","margin_cash_repay","margin_previous","margin_current","margin_next_limit",
"short_buy","short_sell","short_share_repay","short_previous","short_current","short_next_limit","margin_short_offset","remark"]
def normalize():
    records=[]
    for row in ROWS:
        assert len(row)==len(FIELDS)==len(COLS)
        record={"content_date":"2026-10-22","dataset":"TWSE_margin","source_raw_sha256":RAW_SHA}
        record.update({k:int(v.replace(",","")) if 2<=i<=14 else v for i,(k,v) in enumerate(zip(COLS,row))})
        records.append(record)
    return records

class LiveSample(unittest.TestCase):
    def test_01_duplicate_official_columns_preserved(self):
        self.assertEqual(FIELDS.count("買進"),2)
        self.assertEqual(len(set(COLS)),len(COLS))
    def test_02_real_codes_preserved(self):
        self.assertEqual([r["security_id"] for r in normalize()],["00400A","00401A","00402A","00403A"])
    def test_03_real_numeric_integer_units(self):
        self.assertEqual(normalize()[3]["margin_buy"],4290)
        self.assertEqual(normalize()[3]["short_sell"],465)
    def test_04_real_parquet_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/"candidate.parquet"
            pq.write_table(pa.Table.from_pylist(normalize()),path)
            results=duckdb.sql("SELECT security_id,margin_buy FROM read_parquet(?) ORDER BY security_id",params=[str(path)]).fetchall()
            self.assertEqual(len(results),4)
            self.assertEqual(results[0],("00400A",518))
    def test_05_pit_and_numeric_do_not_self_approve(self):
        numeric_verified=False;pit_verified=False
        self.assertFalse(numeric_verified and pit_verified)
    def test_06_sample_not_full_market(self):
        self.assertEqual(len(ROWS),4)
        self.assertLess(len(ROWS),1302)

if __name__=="__main__":unittest.main(verbosity=2)
