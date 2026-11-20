#!/usr/bin/env python3
"""Read-only check that six parallel lanes did not create duplicate destination folders."""
import json
import sys
from collections import Counter
from v098_bronze_copy_only import client, children, TARGET, FOLDER_MIME, OFFICIAL_SOURCES

def check():
    api = client()
    roots = list(children(api, TARGET))
    years = [x for x in roots if x["mimeType"] == FOLDER_MIME and
             x["name"].isdigit() and len(x["name"]) == 4]
    roots_by_name = Counter(x["name"] for x in years)
    duplicates = sum(n - 1 for n in roots_by_name.values() if n > 1)
    inspected = 0
    for year in years:
        source_folders = [x for x in children(api, year["id"])
                          if x["mimeType"] == FOLDER_MIME and
                          x["name"] in OFFICIAL_SOURCES]
        cnt = Counter(x["name"] for x in source_folders)
        duplicates += sum(n - 1 for n in cnt.values() if n > 1)
        inspected += len(source_folders)
    print(json.dumps({"destination_year_folders":len(years),
                      "source_subfolders":inspected,
                      "duplicate_year_or_source_folders":duplicates,
                      "status":"PASS" if duplicates == 0 else "BLOCK"}))
    if duplicates: sys.exit(2)

if __name__ == "__main__":
    check()
