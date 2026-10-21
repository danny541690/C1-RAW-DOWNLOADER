import unittest
from scripts.v093_isolated_repair_triage import classify,SOURCES

def fixture():
    months={}
    for year in range(2000,2027):
        for m in range(1,13):
            key=f"{year}-{m:02d}"
            if key>"2026-10":continue
            months[key]={s:{"status":"EMPTY_MONTH_FOLDER","file_count":0,"zip_count":0,"other_count":0,"zero_size":0,"duplicate_names":[]} for s in SOURCES}
    return [{"read_only":True,"certified":0,"months":months}]

class RepairTriageTests(unittest.TestCase):
    def test_complete_scope_and_noncertification(self):
        shards=fixture()
        row=shards[0]["months"]["2026-09"]["TWSE"]
        row.update(status="FILES_PRESENT_PENDING_QA",file_count=2,zip_count=1,other_count=1,duplicate_names=["same.zip"])
        report=classify(shards)
        self.assertEqual(report["source_month_pairs"],1288)
        self.assertEqual(report["queue_sizes"]["EMPTY_REVIEW"],1287)
        self.assertEqual(report["queue_sizes"]["PRESENT_PENDING_QA"],1)
        self.assertEqual(report["queue_sizes"]["DUPLICATE_NAME_QUARANTINE"],1)
        self.assertEqual(report["certified_months"],0)
    def test_rejects_missing_month(self):
        shards=fixture()
        del shards[0]["months"]["2000-01"]
        with self.assertRaisesRegex(ValueError,"INCOMPLETE_SCOPE"):classify(shards)
    def test_rejects_certified_shard(self):
        shards=fixture()
        shards[0]["certified"]=1
        with self.assertRaisesRegex(ValueError,"UNTRUSTED"):classify(shards)
    def test_rejects_duplicate_month(self):
        shards=fixture()
        shards.append({"read_only":True,"certified":0,"months":{"2000-01":shards[0]["months"]["2000-01"]}})
        with self.assertRaisesRegex(ValueError,"DUPLICATE_MONTH"):classify(shards)
if __name__=="__main__":unittest.main()
