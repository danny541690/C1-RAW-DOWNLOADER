"""R3 NDC true original workbook vs independent archived 0.97 derived JSON check.

Real 10 frozen samples from preceding R3 first cert discovery. Reads the
published XLSX from original Drive file_id, confirms SHA and all 5 native
sheets/cells including blanks/dates. Does not assert historical publication
PIT or issue formal G2 without source-version official proof.
"""
from __future__ import annotations
import collections,decimal,hashlib,io,json,os,re,sys,xml.etree.ElementTree as ET,zipfile
from datetime import datetime,timedelta,timezone
from scripts.v097_bronze_autopilot import source_api
from scripts.v097_v3_preflight import read_baseline,assert_cohort
from scripts.v097_bronze_first_pipeline import put_once
from scripts.v097_r3_gate_core import digest
RUN=os.getenv("GITHUB_RUN_ID","manual")
QA="R3_G2_FIRST_REAL_CERT_PILOT_ISOLATED"
SOURCE_RUN="44256183662"
NS={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
def xml_workbook(raw):
    data={}
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        if z.testzip() is not None:raise RuntimeError("OFFICIAL_XLSX_CRC_FAILED")
        names=z.namelist()
        shared=ET.fromstring(z.read("xl/sharedStrings.xml"))
        strings=["".join(si.itertext()) for si in shared]
        workbook=ET.fromstring(z.read("xl/workbook.xml"))
        sheets=[s.attrib["name"] for s in workbook.find("m:sheets",NS)]
        if len(sheets)!=5:raise RuntimeError("NDC_EXPECTED_FIVE_SHEETS")
        for i,name in enumerate(sheets,1):
            tree=ET.fromstring(z.read("xl/worksheets/sheet"+str(i)+".xml"))
            records={}
            for row in tree.findall("m:sheetData/m:row",NS):
                vals={}
                for c in row.findall("m:c",NS):
                    node=c.find("m:v",NS)
                    if node is None:continue
                    val=node.text
                    if c.attrib.get("t")=="s":val=strings[int(val)]
                    col=re.match(r"[A-Z]+",c.attrib["r"])
                    if col:vals[col.group()]=val
                records[int(row.attrib["r"])]=vals
            data[name]=records
    return data

def check_one(doc,sheets):
    mismatches=[];count=0;blanks=0;markers=0
    for table in doc["tables"]:
        sheet=sheets.get(table["table"])
        if not sheet:
            mismatches.append("MISSING_WORKSHEET");continue
        try:row=sheet[int(table["source_row"])]
        except Exception:
            mismatches.append("MISSING_SHEET_ROW");continue
        head=sheet.get(1,{})
        raw_serial=row.get("A")
        try:
            dt=(datetime(1899,12,30)+timedelta(days=int(float(table["source_date_cell"])))).strftime("%Y-%m")
        except Exception:
            mismatches.append("INVALID_NATIVE_DATE");continue
        if str(raw_serial)!=str(table["source_date_cell"]) or dt!=doc.get("month"):
            mismatches.append("MONTH_OR_NATIVE_DATE_MISMATCH")
        for cell in table["cells"]:
            cols=[k for k,v in head.items() if v==str(cell["field"])]
            if len(cols)!=1:
                mismatches.append("NATIVE_HEADER_NOT_UNIQUE");continue
            native=row.get(cols[0]);trans=cell.get("native_value")
            if cell.get("status")!="VALUE_PRESENT":
                if native is None and trans is None:
                    blanks+=1
                elif (cell.get("status")=="SOURCE_MISSING_VALUE"
                      and str(native).strip()==str(trans).strip()=="…"
                      and {"table":table["table"],"field":cell["field"],
                           "status":"SOURCE_MISSING_VALUE"} in doc.get("gaps",[])):
                    # Excel itself contains the literal missing-value marker.
                    # This is not a missing sheet column nor numeric zero.
                    markers+=1
                else:
                    mismatches.append("DOCUMENTED_GAP_NOT_NATIVE")
            elif native is None:
                mismatches.append("MISSING_ORIGINAL_VALUE")
            else:
                try:equal=decimal.Decimal(str(native))==decimal.Decimal(str(trans))
                except decimal.InvalidOperation:equal=str(native).strip()==str(trans).strip()
                if equal:count+=1
                else:mismatches.append("NATIVE_CELL_VALUE_MISMATCH")
    return {"verified_cells":count,"documented_native_blanks":blanks,
            "native_source_missing_markers":markers,
            "mismatch_count":len(mismatches),"mismatches":dict(collections.Counter(mismatches)),
            "source_month":doc.get("month"),"table_count":len(doc.get("tables",[]))}

def main():
    api,control,quality,match,load,_,_,call=source_api()
    prior=match(api,quality,QA)
    if not prior:raise RuntimeError("PRIOR_FIRST_REAL_PILOT_FOLDER_NOT_FOUND")
    source=match(api,prior["id"],"r3_g2_first_real_cert_discovery_run_"+SOURCE_RUN+".json")
    if not source:raise RuntimeError("PRIOR_FIRST_REAL_RECEIPT_MISSING")
    orig=load(api,source["id"])
    ndc=next(s for s in orig["sources"] if s["source"]=="NDC")
    rows=read_baseline(api,quality,match,load,"NDC");assert_cohort(rows,"NDC")
    idx={r["source_id"]:r for r in rows}
    if len(ndc["records"])!=10:raise RuntimeError("NDC_10_SAMPLE_COHORT_CHANGED")
    original_archive=ndc["records"][0]["source_archive"]
    assert all(r["source_archive"]["sha256"]==original_archive["sha256"] and
               r["source_archive"]["file_id"]==original_archive["file_id"]
               for r in ndc["records"])
    archive=call(lambda:api.files().get_media(fileId=original_archive["file_id"]))
    if hashlib.sha256(archive).hexdigest()!=original_archive["sha256"]:
        raise RuntimeError("NDC_ARCHIVE_SHA_MISMATCH")
    sheets=xml_workbook(archive)
    result=[];counts=collections.Counter()
    for ref in ndc["records"]:
        r=idx[ref["source_id"]]
        content=call(lambda:api.files().get_media(fileId=r["destination_id"]))
        if hashlib.sha256(content).hexdigest()!=r["source_sha256"]:
            raise RuntimeError("NDC_JSON_FROZEN_SHA_MISMATCH")
        doc=json.loads(content.decode("utf-8-sig"))
        check=check_one(doc,sheets)
        counts["cells"]+=check["verified_cells"]
        counts["documented_blank"]+=check["documented_native_blanks"]
        counts["mismatches"]+=check["mismatch_count"]
        if check["mismatch_count"]:counts["failing_files"]+=1
        check.update({"source_id":r["source_id"],"source_sha256":r["source_sha256"],
                      "archive_sha256":original_archive["sha256"],
                      "g2_proof_status":"NATIVE_CROSSCHECK_OK_PIT_UNATTESTED" if not check["mismatch_count"] else "NATIVE_CROSSCHECK_FAILED"})
        result.append(check)
    report={"schema":"R3_NDC_XLSX_NATIVE_VS_BRONZE_G2_CROSSCHECK_V1",
            "run":RUN,"source":"NDC","sample_count":len(result),
            "published_archive_drive_id":original_archive["file_id"],
            "published_archive_sha256":original_archive["sha256"],
            "official_origin_url_candidate":original_archive["url"],
            "archive_captured_utc":original_archive["captured_utc"],
            "crosscheck_totals":dict(counts),"records":result,
            "review_status":"INDEPENDENT_BYTE_AND_CELL_CROSSCHECK_COMPLETED",
            "official_dataset_edition_pit_certified":False,
            "formal_g2_issued":0,"silver_gold_materialized":False,
            "warning":"NDC current workbook contains retrospective series. Matching original byte and cells is not contemporaneous publication PIT certification."}
    name="r3_ndc_xlsx_native_cell_crosscheck_run_"+RUN+".json"
    fid=put_once(api,prior["id"],name,report)
    if load(api,fid)!=report:raise RuntimeError("NDC_QA_REMOTE_READBACK_MISMATCH")
    if len(result)!=10 or counts["mismatches"] or counts["failing_files"] or counts["cells"]<=0:
        raise RuntimeError("NDC_NATIVE_CROSSCHECK_FAILED")
    print("R3_NDC_REAL_CROSSCHECK="+json.dumps({"run":RUN,"samples":10,
         "verified_values":counts["cells"],"documented_native_blanks":counts["documented_blank"],
         "mismatches":counts["mismatches"],"archive_sha256":original_archive["sha256"],
         "official_era_pit_certified":False,"g2_pass":0,"receipt_name":name,
         "receipt_id":fid,"readback":True},ensure_ascii=False,sort_keys=True),flush=True)
if __name__=="__main__":main()
