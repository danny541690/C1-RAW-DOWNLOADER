"""JARVIS v0.95 ONE-SHOT FINAL PRELAUNCH ADJUDICATION.
Uses previous tests as evidence (NOT broadens PASS). No production publication.
Every gate records exact proof, missing proof, and next external requirement.
"""
import json,pathlib,hashlib,unittest
BASE=pathlib.Path("final_prelaunch_gate");BASE.mkdir(exist_ok=True)
def read(p):return json.loads(pathlib.Path(p).read_text(encoding="utf-8"))
def check(p):return pathlib.Path(p).exists()
def report():
    r22=read("r22_combined/R22_RELEASE_GATE.json")
    r24=read("r24_tdcc_numeric_gold_candidate/report.json")
    r25=read("r25_integrated_admission/R25_SIGNED_ADMISSION_GATE.json")
    r26=read("r26_evidence_register/R26_RECONCILED_GO_LIVE_GATE.json")
    r27=read("r27_official_security_master/R27_current_master_join_report.json")
    r28=read("r28_prelaunch/R28_GATE.json")
    seven=("TWSE","TPEx","MOPS","NDC","TAIFEX","TDCC","FinMind")
    if set(r22["sources"])!=set(seven):raise ValueError("SEVEN_SOURCE_INCOMPLETE")
    if not r27["current_market_snapshot_join_pass"]:raise ValueError("MARKET_MASTERS_UNAVAILABLE")
    if r24["security_date_groups"]!=r25["tdcc_groups"]!=r28["tdcc_rows_audited"]:
        raise ValueError("TDCC_COUNT_LINEAGE_MISMATCH")
    if sum(r28["historical_eligibility_counter"].values())!=2*r24["security_date_groups"]:
        raise ValueError("LOOKAHEAD_NEGATIVE_COVERAGE_MISMATCH")
    if r25["release_missing_control_rejections"]!=7:raise ValueError("PUBLISH_NEGATIVE_TEST_INCOMPLETE")
    if r28["local_single_writer_test"]["rollback_to_prior_pointer"]!="PASS":
        raise ValueError("ISOLATED_ROLLBACK_FAILED")
    gates=[]
    spec=[
      ("G0-01","安全隔離正式 main 及在線排程","主分支目前 SHA、全部正式工作流及執行紀錄逐項比對","未附正式在線排程清單"),
      ("G0-02","v0.93 七來源原始檔總盤點","2000–2026 完整檔案清單、來源月份與 SHA 經驗證","R17 僅測試 7 份副本"),
      ("G0-03","Drive 配額、權限與憑證","正式發布者的存取、配額、讀寫及恢復證據","隔離讀回不等同正式憑證驗收"),
      ("T01","完整 Bronze 不變與歷史涵蓋率","各來源 2000–2026 所有官方可得日/月均有 SHA 與缺件報表","R17/R20 為有限範圍"),
      ("T03","真實日更與歷史補抓競爭","在相同資料分區並行寫入時的防重複、防競寫與斷點續抓","只有隔離測試未有正式兩工作負載證據"),
      ("T05","Google Drive 分散式防競寫","真實互斥鎖／fencing token 或具條件更新語意的發布指標","跨 GitHub Runner SHA 通過；Drive CAS 尚無證據"),
      ("T08","七來源正式 Numeric + PIT","每一指標官方公告時刻、修訂生效時刻、歷史主檔按時點查核","R28 防前視測試通過但無完整 PIT"),
      ("T09","七來源 Bronze→Silver→正式 Gold","七來源全市日以上資料經驗證轉換且可重算實際選股指標","TDCC 全量 QA-only；MOPS/NDC 一筆；其餘有限 API"),
      ("T10","正式發布失敗與回滾","正式 Drive 候選版本 promote、故障注入與原版恢復","R28 只有本地單發布者模型"),
      ("T14","兩個有效市場交易日更新","兩個不相同交易日官方發布後各來源完整資料及差異報告","同一時段多次 API 查詢不能替代跨交易日"),
      ("T16","完整 v0.95 獨立還原","實際還原 v0.95 全部原始、Silver、Gold 與 Manifest SHA","R23 只還原 TDCC Artifact"),
    ]
    if {x["id"] for x in r26["checks"]}!={x[0] for x in spec}:raise ValueError("GATE_ID_DRIFT")
    evidence_links={
       "T01":["https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41820474732"],
       "T05":["https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41820474732"],
       "T08":["https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41838546663"],
       "T09":["https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41838546663"],
       "T10":["https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41838546663"],
       "T16":["https://github.com/danny541690/C1-RAW-DOWNLOADER/actions/runs/41820474732"],
    }
    for ident,name,required,missing in spec:
        gates.append({"id":ident,"title":name,"full_production_gate":"BLOCKED",
                      "exact_missing_evidence":missing,
                      "completion_condition":required,"limited_evidence_links":evidence_links.get(ident,[])})
    groups=[
      {"name":"A_數據品質","gate_ids":["G0-02","T01","T08","T09"],
       "status":"BLOCKED","must_verify":"完整歷史數據、公告 PIT、數值及主檔版本"},
      {"name":"B_發布安全","gate_ids":["G0-01","G0-03","T05","T10","T16"],
       "status":"BLOCKED","must_verify":"正式版本鎖、原子提交、隔離恢復及配額憑證"},
      {"name":"C_正式運作","gate_ids":["T03","T14"],
       "status":"BLOCKED","must_verify":"真實日更／補抓並行和兩個有效市場日"},
    ]
    result={"schema":"JARVIS_V095_FINAL_ONESHOT_PRELAUNCH_GATE_V1",
     "release_approved":False,"production_gate_pass":0,"production_gate_blocked":11,
     "isolated_executable_check":"PASS", "seven_source_candidate_status":{s:r22["sources"][s]["status"] for s in seven},
     "tdcc_groups_checked":r24["security_date_groups"],
     "historical_future_snapshot_negative_rejections":sum(r28["historical_eligibility_counter"].values()),
     "current_tse_otc_master_join_pass":r27["current_market_snapshot_join_pass"],
     "local_isolated_rollback_pass":True,
     "drive_atomic_cas_verified":False,"two_independent_market_sessions_verified":False,
     "full_historical_numeric_pit_verified":False,
     "final_three_groups":groups,"all_eleven_gates":gates,
     "production_main_modified":False,
     "conclusion":"No additional repetitions of this test provide missing long-horizon, authoritative PIT or production Drive CAS evidence."}
    return result
class Tests(unittest.TestCase):
    def test_gate_no_false_production_approval(self):
        r=report();self.assertFalse(r["release_approved"]);self.assertEqual(r["production_gate_blocked"],11)
    def test_groups_cover_each_gate_once(self):
        r=report()
        ids=[x for g in r["final_three_groups"] for x in g["gate_ids"]]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),{x["id"] for x in r["all_eleven_gates"]})
    def test_no_drive_cas_promotion(self):
        r=report();self.assertFalse(r["drive_atomic_cas_verified"])
        self.assertFalse(r["two_independent_market_sessions_verified"])
if __name__=="__main__":
    unittest.main(verbosity=2,exit=False)
    r=report()
    (BASE/"FINAL_PRELAUNCH_GATE.json").write_text(json.dumps(r,ensure_ascii=False,indent=2))
    print("FINAL_ONESHOT_EXECUTABLE_CHECK=PASS")
    print("FINAL_PRODUCTION_GATES_BLOCKED="+str(r["production_gate_blocked"]))
    print("FINAL_THREE_GROUPS="+",".join(x["name"] for x in r["final_three_groups"]))
    print("FINAL_RELEASE_APPROVED=false")
