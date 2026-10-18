"""Offline testable unit orchestrator; no live market or Drive writes."""
import csv
import json
from pathlib import Path
import os

TRANSIENT = {"TIMEOUT", "HTTP_429", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_504"}
MAX_ATTEMPTS = 4

def execute_month(year, month, units, fetch, persist, root):
    """Fetch returns {ok:bool,error?:str,data?:bytes}; persist must verify durable save."""
    out = Path(root) / str(year) / f"{month:02d}"
    out.mkdir(parents=True, exist_ok=True)
    ledger_path = out / "checkpoint.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    def save_checkpoint():
        temp = ledger_path.with_suffix(".tmp")
        with temp.open("w", encoding="utf-8") as fh:
            json.dump(ledger, fh, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(temp, ledger_path)

    for unit in units:
        key = unit["key"]
        prior = ledger.get(key, {})
        if prior.get("status") in {"SAVED_BASIC_VALID", "SOURCE_HOLD", "FAILED_RETRY_LIMIT"}:
            continue
        attempts = prior.get("attempts", 0)
        while attempts < MAX_ATTEMPTS:
            attempts += 1
            try:
                response = fetch(unit)
                if response.get("ok"):
                    if persist(unit, response["data"]):
                        ledger[key] = {"status":"SAVED_BASIC_VALID","attempts":attempts}
                        save_checkpoint()
                        break
                    error = "NOT_PERSISTED"
                else:
                    error = response.get("error", "UNKNOWN")
            except Exception:
                error = "UNEXPECTED_EXCEPTION"
            ledger[key] = {"status": "FAILED_RETRY_LIMIT" if attempts >= MAX_ATTEMPTS else "FAILED_ATTEMPT",
                           "attempts": attempts, "last_error": error}
            save_checkpoint()
            if error not in TRANSIENT and error != "NOT_PERSISTED":
                ledger[key]["status"] = "SOURCE_HOLD"
                save_checkpoint()
                break
        save_checkpoint()
    scheduled = len(units)
    saved = sum(ledger.get(u["key"], {}).get("status") == "SAVED_BASIC_VALID" for u in units)
    missing = [dict(u, **ledger.get(u["key"], {"status":"PENDING","attempts":0})) for u in units
               if ledger.get(u["key"], {}).get("status") != "SAVED_BASIC_VALID"]
    report = {"year":year,"month":month,"scheduled":scheduled,"saved_basic_valid":saved,
              "missing":len(missing),"status":"DONE" if not missing else "FINISHED_WITH_GAPS",
              "drive_uploaded":False,"simulation_only":True}
    (out/"MONTHLY_PROGRESS.json").write_text(json.dumps(report,indent=2)+"\n")
    (out/"MONTHLY_PROGRESS.md").write_text(
        f"# {year}-{month:02d} simulated report\n\nSaved {saved}/{scheduled}; missing {len(missing)}.\n")
    with (out/"MISSING_UNITS.csv").open("w",newline="") as fh:
        writer=csv.DictWriter(fh,fieldnames=["key","source","status","attempts","last_error"],extrasaction="ignore")
        writer.writeheader()
        writer.writerows(missing)
    return report
