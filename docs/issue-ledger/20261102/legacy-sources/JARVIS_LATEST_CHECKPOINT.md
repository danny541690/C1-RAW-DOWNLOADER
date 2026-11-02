# Latest: v0.93 complementary capture R1 (2026-10-16)

Original planned acquisition 749/749 after recovering all 10 TPEx daily units. Daily cutoff remains 2026-10-15. Revenue 8908 August/September supplemented. 10 TDCC historical archive weeks captured separately; latest official CSV exact-byte match. 20 historical samples / 980 cells: 970 match, 10 level-16 adjustment sign differences remain HOLD. FinMind 39 price-code queries produced 1,706 rows: 1,633 numeric OHLC match, 73 official-null/FinMind-zero excluded from fill; no additional rows for 283 absent security/date candidates. All 1,487 native file paths SHA256 verified; 12 supplement archives remote SHA256 + CRC verified. Full-market field completeness UNKNOWN; Production BLOCKED; no legacy imports.

Report: docs/registry/capture/V093_20260801_20261016_COMPLEMENT_R1_REPORT.md
Registry: docs/registry/capture/V093_COMPLEMENT_20261016_R1.json
Drive report: https://drive.google.com/file/d/1DOHS439BYMy3lwTmJsSTpAuU0rg3jl5o/view
Daily automation remains undeployed. Use original plus complement manifests and fulfilled_by; do not refetch recovered successful units.

---

# 0.93 新批次完成（2026-10-16，保留缺漏）

批次 V093_FRESH_20260801_20261016 已完成有界抓取；明列清單 749/749 執行，739/749（98.66%）通過日期／格式基本檢查。8月302/307、9月288/293、10月至15日149/149。仍有10個TPEx價格／法人日期單元未取得，不反覆重試。10月16日完整盤後資料另列待補。
新原始回應241,443,392 bytes；16份資料封存已雲端逐位元組回讀一致、ZIP CRC通過。1,268個原檔／分片路徑雜湊檢查無不一致；329,602列OHLC範圍檢查無違反，這不是全部數值驗收。
第二季財報為6月期末基礎資料，另存來源/2026-06。現金流：目前名錄1989代碼，官方1937有數字、FinMind另40，聯集1977（99.4%）；仍12代碼無數字，兩來源科目單位未核准等價。
四核心來源TWSE/TPEx/MOPS/FinMind全新抓取，舊版Raw匯入0。分點/主力、集保持股分散、完整歷史名單及公告PIT等仍未齊或未驗收。Production BLOCKED；每日自動排程尚未部署。
主入口：docs/registry/capture/V093_FRESH_20260801_20261016.json；報告 docs/registry/capture/V093_20260801_20261016_CAPTURE_REPORT.md。
Google Drive報告：https://drive.google.com/file/d/1uGc1fmacgC254WoOOnx6Nj-9LZuMlwjX/view?usp=drivesdk
成功單元依manifest/hash接續，不重抓；完成本批不等於全部市場所有欄位100%完整或正確。

---
以下為先前規則／歷史紀錄，遇進度衝突以上述批次入口為準。

# 0.93 按月抓取接續規則（2026-10-16）

最新採納：MONTHLY_CONTENT_DATE_V1_20261016 / CLEAN-REBUILD-R4。
讀取順序：docs/registry/v093_latest.json → docs/registry/policies/monthly_capture_v093.json → docs/policies/JARVIS_V093_MONTHLY_CAPTURE_v1_20261016.md。
資料根目錄：我的雲端硬碟/ChatGPT資料存取/C1_0.93。
主控Drive ID：1SHo4ci4Vm7deIpRGzxbACom7oqIe-PPz；原檔名維持C1_0.93_MASTER_CLEAN_20261016.xlsx。

一次下半年任務，必須按一月至六月建立月份子任務，每完成一段即存01_RAW/{YYYY}/{source}/{YYYY-MM}/。不足一月也存實際月份。跨月回應按契約指定的內容日期分月；保留完整parent bytes於00_INBOX/source_responses，分片保留hash/血緣，不能把資料全放結束月。未知日期隔離。中斷只接續未完成單元。

禁止舊C1_Stock/R7原始資料、標準資料或指標結果遷入0.93；舊資料進度不代表新庫進度。現有51張主控表與月份空目錄保留，採納規則不等於已部署抓取器。
目前0.93抓取/合併/永久上傳管線尚未部署，本次未啟動抓取，Production BLOCKED。原有每月10日起合併上月Standard政策不變。

這是可跨對話讀回的接續文件，不代表已寫入ChatGPT永久記憶或自訂GPT設定。

---
以下為舊R7歷史接續資料，不是0.93新庫狀態。

## 2026-10-15 MAINLINE-031/032 completed continuation — ACQUISITION FIRST

User 11:19 asks resume interrupted acquisition and report raw progress/completeness. Maintain prior explicit directive: NO SQLite/retryframework/oldnumeric-conflict detours; collect remaining free sources, stats bydataset/period, never samplesasallmarket.
029broad run38662479392 success/art11939469864;cashflow run38662858471 success/art11940556859. Notwholejobinterrupted;original18missingbatches180codes mainlyDNS/timeouts,notdatasizeproof.
Originalcashflow1988currentcatalogcodes/199batches+2catalogqueries ->1798headers/1796numericcompanies/99302numericcells. Firstresume38675828410/art11946591344 had FORM SERIALIZATION BUG beforeeffectiveHTTP,18captureinvocations but0validsourcecalls;preserved. CorrectJSONpairs->tuples, run38676000088/art11945543412 acquired17/18batches170numericcompanies. Originalsuccessesnotrefetched. Officialunion1968headers/1966numericcompanies/108485numericcells.
Remaining10(4568,4569,4571,4572,4576,4577,4580,4581,4582,4583)+2empty(1589,3718) acquiredthroughseparateFinMindfree no-token12queries, run38676289883/art11945952718 ALLHTTP/app200,10nonempty230nativeaccountrows dated2026-06-30;1589/3718emptyagain. Union1976differentcodeswithcashflowdata/1988querycatalog=99.4%CATALOG_DATA_AVAILABILITY_ONLY. NOTallfields,notcertifiedhistoricalordinaryuniverse. NativeFinMindtypes21-26/company NOTequivalentfullMOPSreport;neveroverwriteorapprovefieldunit/basis. Other10noreportcatalogcodes9103,910322,9105,910861,9110,911608,911622,911868,912000,9136 unapprovedrole/nodata;don'tfill0orclaimpaidcure.
NEW032TWSEQ3events run38676585881/art11945559052 actualTWT49U726rows666codes, TWTAUU8rows8codes, officialtitlesJuly1-Sept30,ALLactualdateswithinquarter. Localpreviousnondataresponsesremainpreserved;cloudacquisitionworked,notrootcauseinvestigation.
Previously029newTDCC13/13officiallistedQ3weeks891191rows fromPINNEDthirdpartypublicarchive(notdirectofficialhistory/numericGolden);TPEXmarketcap63/63days56027securitydays;TPEXQ3exdiv584/reductionresume6/parchange2/delisted3;TWSESeptdirector1081companies27387rows(11509),priorAugseparate,Julmissing;TPEXdirectorcurrentbodyincompleteNOTcountedcomplete.
LATESTREPORT docs/registry/delivery/wp00/MAINLINE_031_ACQUISITION_PROGRESS_20261015.md includes032 andwholeinventory. Original029report nowlinks latest. Machine031_FREE_CASHFLOW_UNION,030_OFFICIAL_CASHFLOW_UNION,029_TPEX_ACQUISITION,032_TWSE_EVENTS_COUNTS dated20261015.
Archives downloaded-byte/CRC/memberSHA verified:
TDCC https://drive.google.com/file/d/1AOyJDs9ei7QJIWUW4SAsFOXjzZrM7Cdd/view 20members SHA50137c8935c3dda1bdb469bc52594ea008d8bd9147ec506a06b02460084b4c83.
029officialcompletebatch https://drive.google.com/file/d/1YzL2aRnQTp8o8Fr-H7I9bmeGu56OkseW/view 351members SHA4f5cbd1872d734b7a0408613ed0a31f4efdb259cdd96dd0bd83839bf6010937c.
030/031resume https://drive.google.com/file/d/1M3DoZfgoqfp8BD6rHUuW66FifpNFczLo/view 44members SHA5bf642e598aa93c7ed87cc2d9a7ddfa1bbaf3da1ab4d7592502d0987fbff8f89.
032events https://drive.google.com/file/d/1RIs6vqSv7eK0LVgAluPFmqaD2lJ7Cicx/view ZIP SHA65d83fd6d63275346e983af04746eae062ef44ce5148031212ed7a5306b9a5c9,2rawmanifestSHAchecked.
NOactivecapturejobsremainingforthesecompletedbatches. DatafilenameCOMPLETE_BATCH ispackagecompletenessNOTallrequirementscomplete. ExistingdailycountsfromsavedreportsNOTfreshcoreSQLrecount;oldSQLiteHOLDunresolved/norepair.
REMAININGACQUISITION: complete7-9director/pledgehistorybothmarkets;fullhalt/resume/listing/historicaluniverse/sectorconstituents;TWSEnativehistoricalmarketcap/capitalchanges;brokerallbranchesandbuy/sellbranchcountsfreesustainablehistoricalaccessunproven. Monthlyrevenue15company-marketone-monthgapsretained;nozerofill. Don'tpromiseeveryfreesiteexhausted/uncollectedmeanspaidonly. ToAlphaMCPbulkexportnotpermittedbyitsdocumentedterms(notused).
Continuefree-sourceunioninventoryandacquisitionfirst;doNOTreturntostoragecontrolrounds. No paidaccess,newindicators,SQLiteupdates,dailyschedule,formalPIT/signalapproval. Productionlegacyholdsnotclosedbyrawacquisition.

## 2026-10-15 MAINLINE-029 ACQUISITION IN PROGRESS — user explicitly forbids further error-remediation detours

User requests promptly collect all obtainable free public data for full TWSE+TPEx July1-Sept30, quantify actual coverage and payment residuals. Pause SQLite/retry/corruption/numeric-conflict repair; no sampling-as-completion.
NEW acquired: TDCC third-party public archival mirror wirelessr/tdcc-opendata-archive pinned tree eb8ac98e566fe344c5b7a3c25c48a81fddcd7d52,13Q3weeklyCSVs,891191levelrows,4001-4068securitycodes/week. ActualCSV dates equal all13dates in officialTDCCqryStock form. NOT officialdirecthistoricaldownload; notnumericGolden. Localmainline029_tdcc;frozen tree/form/README+CSV archived Drive https://drive.google.com/file/d/1AOyJDs9ei7QJIWUW4SAsFOXjzZrM7Cdd/view SHA50137c8935c3dda1bdb469bc52594ea008d8bd9147ec506a06b02460084b4c83;20members/19SHA exactbyte readbackCRC. RepoTDCCsummary+collectorcreated.
LIVE runs inprogress:38662479392 .github/workflows/mainline-029-free-capture.yml dynamic officialspecselectedwhole-tablecapture(nohistoryparamsinvented);38662858471 .github/workflows/mainline-029-cashflow.yml officialMOPSfin cashflow across currentofficialcompanycatalog in10companybatches. Getartifactsaftercomplete, not fullrepair. Firstlocal10companyofficialMOPSfin /compare/report POST verified returns2026Q2 CashflowStatement10reportNames/nativecells223809bytes;params from actualhomepageJS/mainline029_mopsfin/homepage.raw. Q2latest ordinarily availableinquarter,NOTclaimedQ3financialreport. Localreadonly numericcounts stillpending, don't countheadersasfullnumericdata.
LOCAL active session51099 pythonmainline029_tpex_history_collect.py;all63TPExdailyMarktVal captures+6eventsresources, incrementalmanifestmainline029_tpex_history/manifest.json. Officialpages inmainline029_tpex_pages linkactions /www/zh-tw/bulletin/exDailyQ,revivt,pvChgRslt withstartDate/endDate2026/07/01..09/30 =>584exdividend,6reductionresume,2parvaluechangerows alreadyacquired. decap/sprc areCURRENTnotQ3history;company/deListed date2026 gets6yearrows notquartercountyet. Marketcapdaily rows~890. Dates reused63verifiedTWSEholdingsdates. Script/sourcepage manifests notyetuploaded. Needfinish+archive+report+checkpoint actualcounts.
TWSEevents oldexchangeReportTWT49U/TWTAUU GETquarterbounds yielded307nondata784bytes locally, savedmainline029_twse_events;NOrepairperformed/noquartereventsclaimed. Coulduseobservedofficialfrontend/rwd route foracquisition ifneeded, notdiveolderrors.
ToAlpha MOPSdoc reviewed publicfree but terms expressly disallowbulkexportdatabase/mirroring;notusedforbulk. Insiderholdingslatestonly nothistory. Recordaccesslimitation, don'ttreatfreewebsiteasbulkAPI entitlement.
No marketDBmodified/no newindicators/no paidlogin/FinMindnewcalls sofar. All-marketfreeunion stillNOTcertified;mustfinish acquisitions notreturntostoragetests. Need final acquisitioninventory not fabricatedoverallpercentage.

## 2026-10-15 08:47 Taipei USER PRIORITY RESET — acquisition inventory first

User explicitly says STOP focusing on errors; pause SQLite/retry/recovery/individual-conflict work. First count 2026-07-01..09-30 full TWSE+TPEx dataset acquisition, distinguish all-market returned tables from sampled FinMind, latest snapshots from historical periods, captured from QA. Objective is free-source union coverage for JARVIS and exact residual gaps to decide payment. Do not require collecting every redundant website/provider. Do not claim uncollected means paid-only.
Inventory reread GitHub MAINLINE001coverage/publishedtables,005financial,006chip,007coverage,018options and022-026evidence. Daily source tables cover63dates each for prices,market/indices,institutions,margin,valuation,lending;not proof ordinary-stock historical universe100%. Prices754183security-days include ETFs/warrants. Monthly5925company-monthrows;1965market/companykeys3months present,15keys missingone. Q2income+balance1976companieseach,notcashflow/fullhistory. TWSEdirector27475person/companyrecords only11508;TPEXdirector incomplete. TDCC latest20261008 only,69496rows4088codes17levels,notQ3weeklyhistory. Q3foreign+mainlandholdings126market-dates141690rows;Octincrement18/20309 separate notgeneralallmoduleupdate. FinMind sevenfamily sampled19stocks(3+16),notallmarket.
Main missing acquisition:fullmarketcashflow,TDCCQ3weekly,director/pledgehistorybothmarkets,corporateactions/historicaluniverse/sectorconstituents,capital/marketcapcompletehistory,brokerallbranches/buy-sellbranchcounts. Paidneed unproven exceptbroker is primaryaccess/automationcandidate;do notquoteoldpricesascurrentwithoutbrowsing.
Stats are archived acquisition-report counts, NOT new live database recount. Incidental read-only core001SQLite schema read returned malformed thisturn; no repair/retry performed peruserpriority;do notclaim freshDBintegrity. Existing archive/reports retained. No new marketfetch, no data changes thisinventoryturn.

## 2026-10-15 MAINLINE-028 actual incremental interruption and writer lock

Finite local controls PASS; source unchanged SHA68ddca96d0eb330c4e483c08f4c1ea93333be42fbf7e97251f7a802524009ad3;externalrequests0.
Disposable copy committed baseline removesTWSE2026-10-14 ->143batches/160636rows. Actual026parse/ingest invoked viaAST;connection proxy exits74 afterbatchinsert+100of1363rows beforecommit. Reopen restores exact baseline, all-column logicalSHAca3aa62e55b0be28d4a5ba6738ab883522a43048f9306f43e0daf7afcb0472a0.
Separatewriter BEGIN IMMEDIATE blocks childactualingest(timeout0.2s), SQLITE_BUSY5/databaseislocked/exit75, no baseline changes. Release then explicit freshprocess rerun imports1363rows,144batches/161999rows. Allcolumn logicalSHA2506ede89d7c5c148cc6d1f32befc9dd816c6fbd61603da8c0d7f1ba81aeb621 identicalfullsource. integrityok/FKempty/viewrowsmatch. NextreplaywholeDBSHAunchanged.
IMPORTANTGAP: retryafterlock/backoff/durablefailedtask/unattendedrecovery notimplemented. Testharness explicitly reruns afterrelease;notautonomousdailycompletion. Onlysinglelockconflict,nocommit-midpoint/powerfailure/multi-host/longrunvalidation.
026corruptionrootcause remainsUNDETERMINED/open;Production/PIT/formalsignals BLOCKED,otherholdsunchanged.
Report docs/registry/delivery/wp00/MAINLINE_028_INCREMENT_INTERRUPTION_20261015.md;machine MAINLINE_028_INCREMENT_SUMMARY_20261015.json;script scripts/experimental/mainline_028_ingest_recovery.py. All3GitHubreadbackexact. Nextworthwhilework:boundedSQLiteBUSYretry +durabletaskreceipts and restart recovery againstrealraw,retainconflictholds.

## 2026-10-15 MAINLINE-027 storage recovery controls

Finite local controls PASS; no external source requests. Accepted026source unchanged SHA68ddca96d0eb330c4e483c08f4c1ea93333be42fbf7e97251f7a802524009ad3.
SQLite backup API verified;5independent read-only reopen processes PASS. Disposable copy real TWSE10-14 deletions inside uncommitted transaction then os._exit(73): reopen rollback restores144batches/161999native andview rows, integrity ok, FK empty, both tables all-column logical SHA2506ede89d7c5c148cc6d1f32befc9dd816c6fbd61603da8c0d7f1ba81aeb621 identical tosource. Strengthened all-column checks reran full control.
Actual026parse/ingest functions tested:1363row TWSE10-14 identical replay no write;whitespace-only JSON byte revision (same market values, CONTROL NOT LIVE REVISION) triggers SOURCE_REVISION_HOLD_NO_OVERWRITE, whole DB SHA unchanged.
Report docs/registry/delivery/wp00/MAINLINE_027_STORAGE_RECOVERY_20261015.md;machine result MAINLINE_027_STORAGE_SUMMARY_20261015.json;script scripts/experimental/mainline_027_storage_test.py.
026corruption root cause stillUNDETERMINED/open. No commit-midpoint crash/powerfailure/concurrentwriters/long-run storage validation.Production/PIT/formalsignals BLOCKED;other semantic holds unchanged;no daily deployment.

## 2026-10-15 MAINLINE-026 actual holdings increment and SQLite integrity incident

Official calendars2 + live data17 requests=19, all first attempts succeeded; FinMind0. Oct1-14 nine planned trading days each market,18batches/20309new rows; TWSE9fresh,TPEX8fresh+Oct14full894-row official app raw reused. Prior126batches/141690rows ->144batches/161999rows. Run38655650290/artifact11936641528 capture success only.
Native raw values/types/headers/SHA retained, no derived indicator or percentage rewriting; unsupported TPEx fields NULL.18batch replay compares all rows, no write, DB SHA unchanged; prior rows unchanged.
MATERIAL OPEN INCIDENT: earlier holdings_native.sqlite passed in-process check but independent reopen malformed (135batches), quarantined with full diagnostics and bytes. Root cause UNDETERMINED; cannot claim storage reliability solved. Prior no-view DB still readable, raw sources unchanged. Fresh unique native_inputs_v2.sqlite rebuilt with FULL synchronous, closed then independently checked, and Drive downloaded archive restored independently: integrity ok, FK empty,144batches,161999table/view rows. Accepted DB SHA68ddca96d0eb330c4e483c08f4c1ea93333be42fbf7e97251f7a802524009ad3. Quarantined file is NOT usable.
Archived real520->200 offline transport control passed; actual source requests0, no live outage or retry SLA claim. Source revision conflict/concurrency/power failure not exercised.
Report docs/registry/delivery/wp00/MAINLINE_026_HOLDINGS_INCREMENT_20261015.md. Archive https://drive.google.com/file/d/13jE9-CK5HAFcf6qztNAZ7IWSaIycZHJ6/view; SHA62a907367f7d834267630783515513a50ca918499c0ab6f0ca6003737994ea25;176members/175SHAchecks/CRC/download-byte-match PASS. Restore verification docs/registry/delivery/wp00/MAINLINE_026_ARCHIVE_VERIFICATION_20261015.json.
No daily schedule deployed; formal signals/PIT/production BLOCKED. Existing revenue/institutional/schema/formula/percentage holds remain open. This is native input pilot, not daily production pipeline.

## 2026-10-15 MAINLINE-025 expanded holdings/masks and ratio hypothesis

Run38653434838/artifact11935886901 capture success,16newfreequeries(allHTTP/application200,63rowseach),officialAPI0.16newcodes(TWSE10/TPEX6),1008security-days,8946fieldcomparisons:8780exact/166TPEXremaining-ratioofficial+0.01pp. TWSE6300/6300;TPEX2480/2646;notallPASS. Other6TPEXfieldsall378match. Official126tables/141690rows reused/bound.
Per-dataset/market/code/date/field researchmasks persisted;8780matched/166hold/2142unsupported-role records.1008uniquecases/16complete63dates/conflictmasksexactlymatchdiffs;formal_signal_allowed andhistory_pit_allowedallfalse. NotformalDailygate.2881revenue/5274institutionalholdsnottransferredtoallholdingsorclosedbythisresult.
19code/1197uniquestock-day QAcombinesprior3withnew16:TWSE756provider+officialremainingpercentmatchesfloor2;TPEX441providerfloor2/officialROUND_HALF_UP2 allmatch,195rawconflicts(29prior+166new). Heldpercentall1197matchesfloor2. Observedpresentationhypothesis,notapprovedall-marketprovidercontract;rawunchanged/noderivedindicatorengine/no arbitrarytolerance.
Report docs/registry/delivery/wp00/MAINLINE_025_HOLDINGS_EXPANDED_AND_MASKS_20261015.md;summaryMAINLINE_025_SUMMARY_20261015.json;ratioauditMAINLINE_025_RATIO_CONVENTION_AUDIT_20261015.json;maskverificationadjacent.
Drive https://drive.google.com/file/d/1tP-7RqsNHgLmksnPVjBqzBExgiTOjSQb/view ;exactbytes/163membersCRC/162memberSHApass;archiveSHA3074e3b49cb470ae781fa6f21cfba4a35882f47f19eadc82de41341162e68aab.
Originalfamilyholds/PIT/ordinaryhistoricalUniverse/financialsemantics/companyactions/Dailydeploymentremainunaccepted,ProductionBLOCKED. Nextreusableofficialholdingsrawinputlayer andnew-dateincremental/failed-gaprecovery withmarket-specificroles;notmore frozenresearchpacketframeworkrounds.

## 2026-10-15 MAINLINE-024 TPEx historical holdings acquired with ratio conflicts

Officialglobal.js observedmenu/data/menu/zh-tw/menu.json -> stock-ocfi.html(dateinput,insti/qfii) -> /www/zh-tw/insti/qfii dated queries verified topGregorian/tableROC requested dates. Historyroutefound;do notkeepclaimingTPExhistoryunavailable justbecauseOpenAPIcurrentonly.
63tables/56178security-days capturedJul-Sept.6488=63rows*7=441fields;412exactmatches/29ForeignInvestmentRemainRatio differences(allofficial+0.01percentagepoint). Other6fieldsall63match inclshares/holdingratio/cap/name. No roundingtoleranceoverride;29ratiofieldHOLD. Local325checksPASS/1all-fields-equalFAIL;outcomeCAPTURE_COMPLETE_WITH_SOURCE_CONFLICTS,notallPASS.
69newrequests/FinMind0:4docs(1sitemap520)+63datefirstrequests(2source520)+2targetedretry.7/7,7/24recoveredonly;allsuccessfuldatesreused.Failures3bodiesretained. InitialvalidatorJSONdecodeabort andpartial3/61dateresults preserved;nonHTTP200dataisolatedbeforecomparisons.FormalDailyfailurehandlingnotdeployed.
Runs/artifacts:38649363693/11933338478;38649476505/11934331274;38649725410/11934401657;38649944907/11933672664.4captureworkflowssuccess!=sourceallPASS.
Report docs/registry/delivery/wp00/MAINLINE_024_TPEX_HISTORICAL_HOLDINGS_20261015.md;summaryMAINLINE_024_SUMMARY_20261015.json;4experimental024scripts.
Drive https://drive.google.com/file/d/1h2cXWqp5sMbdiRXNHpfXhWN-XDLXYQbg/view ;exactbytes/87membersCRC/86memberSHApass;archiveSHA248033a7a7088653ea37d8375c4b28096344051435d04af1ae293f650ddd17fb.
BothmarketsquarterRaw126market-dateholdingstables nowavailable,notfullcompanycross-check/PITapproved. ExtraFinMindISIN/ChineseLimit/declaration/note rolesunverified;allold2881/5274/metadata/formulaholdsremain,ProductionBLOCKED.
NextunifyTWSE/TPExholding inputmasks andwidercompanycross-check/dailyincrementalupdate;retainrawsource percentagesandrecomputedratios asseparateversionedroles.

## 2026-10-15 MAINLINE-023 TPEx current holdings source QA

Discoveryrun38648621798/artifact11934210236;currentrun38648769577/artifact11933169060 bothcapture success.7requests=4officialdocs/assets+2officialcurrentdata+1freeFinMind6488. Local15checksPASS;formula/source-roleholdsremain.
TPExOpenAPI /tpex_3insti_qfii=current1151014;officialapp/data/23.json=20261014.894rows/6258fields same-source representationagreement;6488same-day6numeric+name7fields FinMindmatch. Notindependentprovider6258comparisons or63historicaldates. No documenteddateparameterinthisschema;otherhistoryroutesnotprovenabsent.
Appdisplaytruncates tothousandshares;rawsharesusedexactly. Officialschemaobjectpropertiesvsactualarraywrapperseparatelylimited.
UniversalB+C=A rejected(13nonmatches). NativeB=A*F-C has12residuals:6禁止投資,1floor-compatible candidate8450/notapprovedroundingrule,5unexplained3227/6538/6840/6548/8121.2caps49.99%. Rawunchanged;remaining-share-dependentinputHOLD,notallsourcefailure.
OfficialtabledoesnotprovideISIN/separateChinese-limit/RecentlyDeclareDate. CurrentproviderISINempty,ChineseLimit100,RecentlyDeclareDate10/14,note literalNone;source-roleunverified. Prior6488Jul-Septdate05/12notproofnewactualfiling. Do notuseasAvailableAt.
Report docs/registry/delivery/wp00/MAINLINE_023_TPEX_HOLDINGS_20261015.md;summaryMAINLINE_023_SUMMARY_20261015.json;3experimental023scripts.
Drive https://drive.google.com/file/d/1rbVk7z6nWN-3iAbSmCcCAzsv9j7EK_q8/view ;exactbytes/15membersCRC/14memberSHApass;SHA5898fc4866bc9d35122c9fd8d2f29551b81c2f6ab631c75022cfa878f6527566.
NextdocumentedTPExhistoricalholdingroute then63datecomparison;conditionalshareconstraints/source-fieldroles needinputsafety. Alloldholds/ProductionBLOCKED/PIT/Universe/DAILYunaccepted remain.

## 2026-10-15 MAINLINE-022 TWSE official holdings quarter cross-check

Two livecaptures:run38647828201/artifact11931984873(doc+3dates),run38648026555/artifact11932354780(remaining60dates,2workers,no repeatdates). Bothsuccessful;actual64requests=1officialdoc+63dailyall-ex-warrants tables,newFinMind0.
OfficialselectorALLBUT0999 verifiedliteral全部(不含權證);63exactrequested dates/12fields/rowshape/uniquecodes/totalmetadata pass;85512source security-days captured,not85512companies orapprovedordinaryUniverse.
2330/1709 each63dates:126rows,882numeric+378name/ISIN/ROC-declaration-date=1260exactmatches/0differences vsfrozenFinMind. Local383checksPASS,not383GitHubtests.
Rawunitshares;officialholdingsforeign+Mainland,notpureforeign. Notesretain non-marketcorporate/declarationchanges;holdingsdelta notsimply institutionalflow. note-field equivalence/PITunverified. 6488TPExexternalverificationstillpending;donotgeneralizeTWSEapproval.
Report docs/registry/delivery/wp00/MAINLINE_022_SHAREHOLDING_OFFICIAL_20261015.md;summaryMAINLINE_022_SUMMARY_20261015.json;3experimental022scripts.
Drive https://drive.google.com/file/d/18EL8wtCFaIa9S4xY5Ne83zU89-xF2LWp/view ;exactbytes/77membersCRC/76memberSHAverified;archiveSHA80306fe2383752e15de93bfd432946add2f21e8489049af10f4d7eeed1b8242d.
2881/5274/TPExcolumnmetadataholdsremain;ProductionBLOCKED/fullhistoricalUniverse/companyactions/financialsemantics/PIT/DAILYnotapproved. NextTPExofficialsame-dateholdingscontract andcross-check,thenwidercompanycoverage/dailyincrementalworkflow.

## 2026-10-15 MAINLINE-021 valuation and shareholding input QA

Offline actual018freeRaw vs001officialSQLite;marketAPI0/newActions0. Local399checksPASS. 2330/1709/6488 each63dates:189valuationrows*3(PER/PBR/yield)=567exactnumericmatches,0differences. SixRawSHA/bytespass;officialfullrawnotreread,sourceconsolidatedDBSHAverifiedbefore/afterunchanged.
Allcapturedofficialvaluation124030rows(TWSE68084/TPEx55946),unique/date/shapechecked;notcertifiedhistoricalordinaryUniverse. PER95032positive/28998nonnumeric(-14316,N/A14682). PBR124029positive/1missing(TWSE7835/2026-07-24). Yield32165zero retained;neverconvertmissingPEto0forPE<40screen.
Shareholding189rowsinternaldate/identity/sharepartition/integer/range/datechecksPASS;externalofficialcomparisonNOTDONE. Ratioabsoluteerror<0.01percentagepointobserved,roundingpolicyunapproved.
Report docs/registry/delivery/wp00/MAINLINE_021_VALUATION_SHAREHOLDING_20261015.md;summaryMAINLINE_021_SUMMARY_20261015.json;scriptdaily_mainline_021_valuation_shareholding.py.
CoreZIP101397015bytes/SHAad4bd4e903e3ea106bfe59de2be2ed802c7cdff49ea4176b2c541d9f72d42daa/CRCchecked,SQLiteec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438. CoreDBreusednotduplicatedinnewsmallarchive.
Drive https://drive.google.com/file/d/1a0li1qlTFUbZ8s4oy-8vV1t2mQjl-zGy/view ;exactbyte/14membersCRC/13listedmemberSHApass;archiveSHA5ebfac26bdd3353989703c0265112cdf397808d39b62e87ed30d8febfcf6353d.
2881/5274/TPExmetadataholdsunchanged;ProductionBLOCKED. Nextexternalshareholdingofficialsame-datecomparison andremainingrawcoverage,not moreholdreprobes. Noformalsignals/dailydeployment/PITapproval.

## 2026-10-15 MAINLINE-020 offline scope/net-conflict audit

Real018/019Raw+savedofficialFinMinddoc reused;marketAPI0/newActions0. Local17/17 checksPASS after preservedinitial16/17failure(wrongassumptioncolumnNum25).
MOPSSeptfinancialsection actually23companies incl2886;2881absent. Excludes blanketfinancial-sectoromission,doesnotprove reason/nootherfiling.
5274TrustTPEx buy17000/sell0/net17000 vsFinMind6000/0/6000:netdifference11000. Cannot explain solely same-categoryequal-buy-sell補計describedinFinMinddocs;othercausesunknown,exactupstreamendpointnotproven. KeepSOURCE_CONFLICT and revenueMISSING holds.
TPExcolumnNum25 vsactualfields24/targetcells24. PreserveMETADATA_COLUMN_COUNT_MISMATCH_REQUIRES_CONTRACT_REVIEW;do not insertcells/shiftraw. Correctpriorreport25-column wording;indexedTrustvaluesunchanged.
Report docs/registry/delivery/wp00/MAINLINE_020_SCOPE_AND_NET_CONFLICT_20261015.md;summaryMAINLINE_020_SUMMARY_20261015.json;scriptdaily_mainline_020_scope_audit.py.
Drive https://drive.google.com/file/d/1hagEkIfc-Aj2RZ25M8hjeN0wc71UbTJC/view ;exactbyte readback+12membersCRC verified,SHA256cb131d1b56c027a8c353ecff68801a1f735666e73833fa7c9e888f8e379d65e6.
Production BLOCKED/fulluniverse/PIT/financialsemantics/DAILY notaccepted. Do not repeatedlyfetchsameholdqueries;next othercompany/modulecoverage and precise sourcecontracts,retainfieldlevelquarantine.

## 2026-10-15 MAINLINE-019 targeted source holds tested

Run38594768713/commit73dc4a13cc9fe9703499bac49a1a31a95cdc854f capture success;4 actual requests:2MOPS Septsii0/1,1freeFinMind2881revenue,1TPExscope doc. AllHTTP200;4rawSHA/length verified;artifact11909876140 ZIP7members/CRC PASS/SHA ac00423b09109dbbbabd2dbcb2d6b18cc4923cab51157329f29de727f3996d30.
MOPSstrictCP950/title115Sept/unitthousandpass,2881rowabsent onbothpages;FinMindenddate10/15 returnsJuly/Aug2rows only. MISSING_REPRODUCED_CURRENT_SOURCES,notpaid-plan restriction proof. Scope limited specificpages/API;AvailableAtunknown.
TPExofficialdoc says originalsamedaytrades,noterror/account-correctedfigures. DoesnotproveFinMindusesadjusteddata;5274Trust17000vs6000shares unresolved. Keep field/dependents quarantined,nozerofill/silentmix.
Report docs/registry/delivery/wp00/MAINLINE_019_TARGETED_HOLDS_20261015.md. Rawarchive Drive https://drive.google.com/file/d/1WJOdBIWNmKdWZR9CBB9lQjSn_FyRjxE2/view . All-market/Daily/PIT/financialsemantics Production BLOCKED. Next exactfinancialindustryfiling scope andFinMindinstitution upstream contract,not repeat same4requests.

## 2026-10-14 C 0.92-3 resume: MAINLINE-018 evidence integrity audited

Latest verified source work MAINLINE-018, not017/B67. Runs38587593229/38588609756 capture successful;QA552pass/2holds;all-market incomplete;Production BLOCKED.
Resume independently verifies both artifacts ZIP SHA/CRC(133+3 members),133 manifest-listed files SHA/length;TDCC69496rows/4088securitycodes/20261008/17levels and observed share+holder equations pass. Not4088ordinary stocks or quarterly weeklyhistory.
5274/2026-07-31 Investment_Trust buy TPEx17000 vs FinMind6000 shares reproduced;quarantine affected field/dependentmetrics.2881Sept revenue absent despite queryend2026-10-14;existingMOPS also absent,causeunknown. No zero-fill or paid-plan cureclaim.
New marketAPIcalls0;existing30240comparisons not independently rerun withoutMAINLINE001SQLite.Fullchat transcript/attachments not certified. This repairs missing018handoff,not allMaster/Drivecopies.
Report docs/registry/delivery/wp00/C0923_RESUME_INTEGRITY_AUDIT_20261014.md.
Next exactofficial2881Sept filing and5274scope review;then full ordinary-stock universecoverage/dailyincremental pipeline. FormalDaily/persistentDriveauth/mobileE2E/financialsemantics/PIT unaccepted. Avoid unrelated frozen-packetframework rounds.

## 2026-10-14 MAINLINE-017 completed: free single-stock raw coverage

- 3 stocks 2330/1709(和益)/6488; 21 initial unauthenticated queries all returned rows plus one targeted 1709 revenue correction. Four full official FinMind document HTML snapshots saved. Both Actions runs successful 38582279284/38583164513; artifact digests and ZIP CRC verified.
- Daily price/institutions/margin each63dates perstock; 5670 native cross-source field comparisons against TWSE/TPEx PASS, no differences. 111 raw QA checks PASS; not indicator E2E.
- Original revenue query July-Sept returned reportJune-Aug, preserved as scope-failure evidence. Reused two prior corrected2330/6488 responses, fetched1709only, reportJuly/Aug/Sept9values match MOPS thousands×1000. No zero fill; provider create_time not officialAvailableAt.
- Financial9responses402fields fiscalJune30; Q2 lookback, fiscaldate not announcement. Fullstatement, cashflow single/cumulative basis, historicalPIT remainUNVERIFIED. FinMind EPS docs do not certify MOPS EPS basis.
- Drive healthy archive https://drive.google.com/file/d/1DukrdhbNIBCLGiVVaW1c5KRIk2IBU6tJ/view :231060bytes SHA2565c694b41b9ca4dc1714707ca1675a8b1a04b57b1b857fab7e20c89a54a926d1d, fullreadback39members/38listedmemberSHA/CRC PASS. Report docs/registry/delivery/wp00/MAINLINE_017_FINMIND_FREE_20261014.md; QA and Driveverification adjacent.
- FinMind allmarket NOTCOMPLETE. Next mainline: bounded perstock missing-source batches with no paid endpoint or token, reuse successful responses, reportmonth-aware queries. Historical expected universe not certified; current catalog cannot substitute. Stop adding frozen6packet infrastructure rounds. Master443 definition/formalDAILY/longhistory/PIT/CA gates unchanged; Production BLOCKED.

## 2026-10-14 MAINLINE-016 completed: reusable frozen-input research CLI

- Singleentrypoint scripts/experimental/jarvis_research_packet_cli.py committed86effbd253fc5bbf219cf6d3c4a6e1a2ce94bd4a. StandardPythononly, --input frozen_batch.json --state-dir mandatory. No marketdownloader, newindicatorcalculator orproductionDailyservice. Only fixed2experimentalformulas/currentperiod supported;batchinput immutablebinding, changeddata needsnewbatchstate. Scopefrozenresearch ratherthanall443.
-8checksPASS:normal9entries(6realNew/2syntheticRejected/1Repeat),fullreplay9cached/stateSHAunchanged,controlledexit73afterordinal4publishbeforereceipt/resumeexit0,changedfrozeninputblocked,corruptreceiptchecksumblocked,rehash-but-semanticallywrongreceiptblocked,corruptsnapshotblocked,missingheadblocked. Allblockedrunsstatebyteunchanged;healthyrootunchanged. CLI preflightsALL existinghead/snapshot/version/packetvalidation andreceipts.EntryDigest/ordinal/caseID/checksum/actualstatus/reason/headlinks beforewriting. Checksumsalone notapproval.
- Resumeactions3cached/2identical/3new/1reject;previousinterruptedfiles unchanged. No arbitraryOScrash/powerfailure/concurrencyapproval. No silentcorruptstate repair. Errors exit2 BLOCKED_INPUT_OR_STATE;success COMPLETED_WITH_REJECTIONS orCOMPLETED_RESEARCH_ONLY,run_actions separateoriginalreceiptstatuses.
- Retains3normalinput+3partialinputrealpackets, priceJul7 vsrevReportSept separatetime,AvailableAtunknown. Allacceptedstoredformal_signal_allowed=false/historical_daily_join_allowed=false;realgapsnotclosed;Master443pendingdefinitions/roles/PIT/fullfour-sourcecompleteness/productiongateunchanged. Pythonrecords/QAonly,newindicatorvalues0,newAPI/FinMindcalls0.
- Report docs/registry/delivery/wp00/MAINLINE_016_RESEARCH_CLI_20261014.md commite8008c688afc89d87ea8015102078cd59d6c6eb2;test0e777f27d199caee5a822081aad752c9b9efd044;summaryc25fad39e8db7139e57332282d4ee0b58b6aef28;GitHubexactreadbacksPASS.
- Drive https://drive.google.com/file/d/1qBwc4yby-5jpG-LQu517Qlo8Dkd69Byx/view ;137408bytesSHA25695dfce45a82c81d940d0e47599b861eb088c08c9f2f2f3b55c9516240c42bea1. FullZIPdirectory/CRC+139memberhashes+12healthyhead/versionchecks+8testcountsPASS. Deliberatelycorruptisolatedstatecopiesincluded asfailurefixtures, explicitlyNOThealthy backups. normal/resumehealthyroots separated.
- This small6packet storage/control sequence is now sufficient for authorizedcurrentresearchscope. Do NOT keep inventingadditionalcache/interruptionframeworkrounds;mainline-firstuserpreference. Nextmainline returnto actual daily rawsource/fieldcoverage andsource-to-model input gaps, ideally address concrete actionabledata-source gap (FinMind currentlymarket-level/calendar vsrequestedall-marketper-securitycoverage, orpublishedfinancial/cashflow fieldscope) usingexistingofficialdocs andfreecapabilities, no paidtoken/login. Preserveknownlongwarmups andscopedpartialanalysis ratherthanblockeverything, avoid8105/5236/±1仟元branches. Do not imply datafullycaptured justbecauseCLIpassed. Readcurrentauthoritativecontract docs before livecapture changes;GitHubActions forpublicnetwork whenneeded, immutable rawDrivearchive/readbackrequired.

## 2026-10-14 MAINLINE-015 completed: controlled fresh-process batch interruption/recovery

- Same9frozen MAIN014 entries, freshMAIN015store/receipts,3separate childprocesses. Phaseinterrupt os._exit(73) atordinal4 AFTER publish committedTPEX6488 snapshot/head BEFORE writingreceipt004. Not arbitraryOScrash/powerfault/concurrency test andnotrootcauseproof ofoldconversationinterruptions.
- Atstop3heads/3snapshots/3receipts;receipts1/2accepted,3rejectedwrongidentity;head3includesordinal4committed6488withoutreceipt. interruption_point.json recordsEntryDigest/DataVersion/location,interrupted_manifest hashespersistedfiles.
- Freshresumeprocess exit0 reusedreceipts1–3 byEntryDigest,ordinal4returnedIDENTICAL_REPLAYfromcommittedhead andwrotemissingreceipt withrecovered_committed_head_without_receipt=true;later3validrealpacketsfinished,duplicateandbadgate stillreceipted.
- Final6heads/6immutable snapshots/9orderedreceipts. Finalstatus5NEW_VERSION,2IDENTICAL_REPLAY,2REJECTED_PACKET (ordinal4 originallynewcommittedbeforeexit thenrecoveredasreplay,so6distinctrealpacketswereactuallystoredonce,not5). AllinterruptedfilesSHAunchangedincludingrejectreceipt.
- Thirdfreshprocess wholebatch replay reused9receipts,store+receiptmanifestunchanged. Everyhead→snapshotSHA/inputDataVersion/outputPacketVersion verified. Sourcehelper andrealMAIN012input/packetSHAsunchanged,no newindicatorvalues/API/FinMindcalls.
- Allformal_signal_allowed=false,historical_daily_join_allowed=false;priceJul7 vsrevSeptperiods preserved;actualgapclosuresfalse,full443/historicroles/PIT/allfour-sourcecompleteness/productionDailyE2Eapprovalnone.
- Report docs/registry/delivery/wp00/MAINLINE_015_INTERRUPTED_BATCH_RECOVERY_20261014.md commit2dfac02ceb2587c36ed2de90a41392e169ed0e4d;codea0e443b3a71c480f828ac6769af3937488b371ee;point43d9928d78eb95fe5456eee7dd6706f4c9c02faa;finalreceipts9e92c34f2537e78094a8d1a7bfafec9efb301022;exactreadbacksPASS.
- Drive https://drive.google.com/file/d/1XOKAdJVRESQjujpxyQrUVtBT3lbEifag/view ;35133bytes SHA256324ac15c00f0e3b7e87459abfbfe37fc60545ccf63d7fc26d3023ce183130b52. FullZIPdirectory/CRC+32memberSHA+6head/versionchecks+9receiptcounts+recoveredordinal4+interruptedmanifestunchanged PASS.
- Nextmainline: consolidate reviewed smallresearchpacket batch delivery/receipts/resume into single reusable researchCLI entrypoint (frozeninput/outputJSON, notmarket downloader orindicatorcalculator);runnormal,replay,resume atbounded existing cases andreturnexplicitpartial/reject/batchstatus. Avoidmoreseparateframeworkbranches and don'trepeatwholemarkettransport. PureversionhelpersavailableMAIN014dependencies/versioned_packet_test.py. Keepreceiptfingerprint/headvalidation strong:reusableCLIshouldrefusechangedinputs/invalidexistingreceipts ratherthansilentcache reuse. Noproductiondailydeployclaim.

## 2026-10-14 MAINLINE-014 completed: sequential batch delivery and rejection isolation

- Used6real frozen MAIN012 packets/inputs, fresh MAIN014store; reused MAIN013pure versionhelpers via AST, never ran its top-level syntheticupgrade test or used its upgradedheadstore. No new indicator values/API/FinMindcalls, originalinput/packet/helperSHA unchanged.
-9batchentries:6real packets+1identical realduplicate+2isolatedsynthetic invalidpackets (wrongcodeinmiddle,unapprovedformalgateatend). Firststatuses6NEW_VERSION,1IDENTICAL_REPLAY,2REJECTED_PACKET,0SYSTEM_ERROR. Newpackets3NORMAL_INPUT_TWO_EXPERIMENTS/3PARTIAL_INPUT_TWO_EXPERIMENTS. Missingfeature notpacketfailure;price2816/6785 andrev2035retainusablevalue.
- Wrongcodeentryordinal3 rejected,subsequent4validrealpackets allfinished. Everyentry receipts ordinal/caseID/inputidentity/claimedidentity/status/reason/version/masks. Storemanifest unchangedbeforeaftereachreject. Batchoverall COMPLETED_WITH_EXPECTED_REJECTIONS, not all-sourcePASS.
- Whole9entrybatchreplay7IDENTICAL_REPLAY,2REJECTED_PACKET,0NEW_VERSION;unchangedwholestoreSHAmanifest,6heads/6immutable snapshots.7replays includesduplicateitem,not7uniquestocks.6head snapshotSHA/inputDataVersion/outputPacketVersion exactreadbackPASS.
- PricesJul7 vsrevenueReportSeptperiods preserved;allstoredformal_signal_allowed=false,historical_daily_join_allowed=false,AvailableAtunknown. No full443/historicPIT/roles/currency/corpaction/fullmarketfour-source/productionDAILYapproval. Systemfaultclassifier exists but no OS/diskfault injected,testedsequentialonly,no concurrency/crash claim. Same-sourceexistinganswers reused, no independentmarketGolden.
- Report docs/registry/delivery/wp00/MAINLINE_014_BATCH_DELIVERY_20261014.md commit040b43c1b33fe4be0726eadb12caf4a68f965d18;codeb0b1e5e9d05dbaa7c7a49be8dd211dc2e9bdf4dc;firstreceiptsf515bcdd9d38a1950730b84a4261cbead297a201;replay442762da55be38d1e0cadd337586c3669e112c2d. ExactGitHubreadbacksPASS.
- Drive https://drive.google.com/file/d/1F9phkfWCHsYFF1JIXzXNxCBo2qMb2IUX/view ;28688bytesSHA2569db00071fbcc37b8becc95a7c72679cfce74bb8a386bb51695c28a4cb35dd097. FullZIPdirectory/CRC+20memberSHA+6head/snapshot/version checks+18batchreceipts/countsPASS. Frozen referencedMAIN013helperincluded asdependency.
- Nextmainline: controlled interruption ofthissmallbatch at concreteboundary (e.g.afterordinal4 publish or afterheadwritebeforereceipt), restartfresh process usingpersistedheads;completedpackets reused,unfinishedcomplete,invalidpacketsstillreceipted,fullcountsreconcile. Call injected interruption CONTROLLED_TEST not arbitraryOScrash. Useexisting9frozenentries, noallmarketreplay/branchlookup/extraDerivedengine. Preserveinterruptedreport andfinalreceipts withSHA,avoidclaimingformaldailypipeline deployed.

## 2026-10-14 MAINLINE-013 completed: sequential immutable research-packet versions and replay

-6real MAIN012 baseline packets written,6identical replays no newversions.3synthetic supplemental versions (2816/6785revenue,2035price),3identical supplemental replaysPASS.6currentheads,9immutable snapshots. Composite key:kind,market,code,priceDate,revReportMonth,price/revFormulaVersions,schema,model. DataVersionSHA canonicalfullinput,PacketVersionSHA canonicalfulloutput. expected_previous_version required for current-head update, sequential only.
- Supplements explicitlySYNTHETIC_NOT_OFFICIAL, not realgapclosures.2816fakeSeptYoY10.78 withnative-24.38/19.60→fakeavg2%;6785fake1/2/3→fakeavg2%;2035fake2missingcloses27.90→fakeMA27.91. ChatGPT fixtureanswers;Pythonvalidates invariant andrecordsversions only. UnaffectedMA2816/6785 andrev2035 byte-equivalent. Original realinput/packetSHAunchanged. NeverfillL0/claimofficialnewrow;fixture raw_file/SHA pointersNULL,priceQAflagexplicitlyfixture-supplied.
-13rejectionchecksPASS:3staleoldversions,wrongidentity,unapprovedgatepromotion,formula drift,grade mismatch,price/reportperiodlabeldrift,nonpositiveclose,NaNrate,nonBooleanmask,sameinputchangedoutput. Date/reportlabels checked against actualrows, no stale versions overwriting newest. input_ready fields strictBool.
- Initialreplayfailed becausekeyreturnedPython tuple butJSON readbacklist;canonicalJSONequal,serializeddatahealthy. initial_representation_failure.json andinitial6baselinehead/snapshotstore preserved. Fixedkey JSONnative list, successfulreplay. Earlierpassingpre-hardeningstores remain scratchonly;archive contains finalstore+initialfailurestore, no needuseoldpassingstores.
- No concurrency/multi-writer/arbitraryOScrash durability approval. fsyncfiles/temp-headrename used but this sequential researchtest is NOT production CAS or deployed DAILY pipeline. Same-source arithmetic only,allformal_signal_allowed=false/historical_daily_join_allowed=false, Master443definitionsunchanged,real_data_gaps_closed=false.
- Report docs/registry/delivery/wp00/MAINLINE_013_VERSIONED_PACKET_REPLAY_20261014.md commitcda4b6100f3646c077a099601cc4efdc4e0ec658;code scripts/experimental/daily_mainline_013_versioned_packet_test.py commitdc722d3f45e747aeba202c059907a3f91eff02be;initialfailuread95cb5c3eb6e7a82369aa501f630ad7d719bd82;exactreadbacksPASS.
- Drive https://drive.google.com/file/d/122Xq9GUQZeBgkDt4PMhppg-L-uDDOJdz/view ;46973bytes SHA256e024912f2dd2b4063150ad8704c3155aaff72ebfbca65a67c75ca935926b3336. CompleteZIPdirectory/CRC+36memberhashes+6head/snapshotSHA/inputDataVersion/outputPacketVersion/9snapshot/13rejectcountsPASS.9finalsnapshotsplus6initialfailure-snapshots inarchive.
- Nextmainline: batch delivery with onebadpacket isolated whileallothervalid packetsfinish, including validpartial packets (onefeaturemissing is not packetfailure), identicalreplays and explicit completion/partial/reject receipts. Usefreshisolatedstore andfrozenMAIN012realinputs/results, notsynthetic-upgradedheadstores as realdata. Pureversionfunctions may be reused without executingtop-levelMAIN013test that requiresfreshstore. No newPythonDerivedengine, no allmarketcalculation orbranchlookup;phasecoverage/report datespreserved. Scopefuturetemplate/CSV/Excelnotuserrequested yet.

## 2026-10-14 MAINLINE-012 completed: per-feature price/revenue research-packet integration

- Sixreal researchpackets;priceDate2026-07-07,REVENUEreportMonth2026-09. Separateperiods only, NOTJulydecisionknownincome;allAvailableAtNULL,historical_daily_join_allowed=false,formal_signal_allowed=false. Notfull443orDailyE2E/PIT/role/currency/corporateactionapproval.
-3NORMAL_INPUT_TWO_EXPERIMENTS:2330MA2463/rev50.88%;1709MA23.93/rev17255/300%;6488MA1221/rev4.69%.3PARTIAL_INPUT_TWO_EXPERIMENTS:TWSE2816MA34.5/revNULLmissingSept;TPEX6785MA122.5/revNULLmissingpublishedYoY;TPEX2035MA NULL(native ---onJul2/Jul7),rev-337/60%. Onefeaturegap doesn't eraseotherusablefeature. Grades ONLYtwo experiments, neverfullnormal-analysispromotion.
-9actualnumericoutputs checked,6reused prior+3newChatGPT authored(2816MA,6785MA,2035revmean).Python composition/provenance/invariant QA only,noPythonDerivedengine. Frozen priceFormula MAIN0090.1 andrevFormula MAIN0110.1 retained.
-7controlsPASS:unknownAvailableAt,futureannouncement,futureSeptreportwithfakeJulyavailability,missingtimezoneallfalse;synthetictimingpositivecasevalidatesonlychronology(no realPITproof);bothblockedsyntheticcopyNO_CALCULATION_TWO_EXPERIMENTS withNULLs;cross-securityanswer rejected bymarket/code keys.
-30realprice rows matchedSQL/nativeofficialclose;17realmonthlyrows matchedMOPS HTMLcode/YoY;16rawSHAfilesPASS. SourceDB unchanged ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438 andrevenuestagingunchanged2342be32b542a55af9c1ba1a28cafef60aa8e6caea6c0ae29eebd978f04f329a. Raw NULL/zero semantics retained, nofill/crossvenuejoin.
- Report docs/registry/delivery/wp00/MAINLINE_012_FEATURE_GRADED_PACKETS_20261014.md commit11e9a4269a542c3ca0969e0b7b046600942a142e;composer d08392e9945e11b656f4e954999452e318d88d09;researchpackets95a293c364e3ed4e0434aec36e947ef3de2f3bde;authoredanswersda7a11e9cda498e37f35fa21ebd8c7d0b38eb8b8. ExactGitHubreadbacksPASS.
- Drive https://drive.google.com/file/d/1x7O90vowG5McI2aJ0VuhIHzDK2QyMBmf/view ;13410bytes SHA2562f09a9cd495423fb75027f28a3e95c6c27a220ac6dfaf59d16a896509dd4742b. FullZIPdirectory/CRC+9memberhashes+6realpacket/7control/blockallhistoricaldailyjoins readbackPASS.
- No newAPI/paid/FinMindcalls. Same-source arithmetic/provenance is notindependentmarketGolden. Master443pendingdefinitionsunchanged;allfour-sourcefull-marketcompletenessstillnotapproved. Originalactivity/nativefieldsremainupstream;these2featurepacketsdon'tcoverallfields.
- Nextmainline: define stable composite researchpacket key+DataVersion+price/revFormulaVersions;test identicalreplay and isolated supplemental-data transitions (onlymissingfeature upgrades, existingvalidoutputunchanged), stale-version/identity rejection. Allsupplemental fixtures must remain explicitlySYNTHETIC, don'tclaimreal2816/6785/2035gapsclosed. Persistor archive onlyderivedresearchpackets notmutateL0. Do notcollapseJulypricedate+Septreport intoonehistoricalAsOfDate. Keep8105/5236/±1仟元/139absencecausebranchesdeferred.

## 2026-10-14 MAINLINE-011 completed: small native revenue3monthYoY trial and parser fix

- CandidateFormulaVersion C1-MAIN011-REVENUE-3M-YOY-EXPERIMENT-0.1, IndicatorREVENUE_3M_YOY_AVG. Equal arithmetic mean of SOURCE-PUBLISHED Jul/Aug/Sep2026 YoY percent numbers, reportmonthanchorSept2026 only. Notquarter-totalYoY or revenue-weighted, no recomputation of published rates. AvailableAtNULL, no historicaldailyjoin, allformal_signal_allowed=false, Masterpendingstatusesunchanged.
- ChatGPT6exact averages authored; PythonQAonly verifies3*answer=sum(source rates), sourceHTML/metadata andguards. TWSE2330(44.68,53.32,54.64)sum152.64→50.88%;TWSE1709(83.29,82.66,6.60)sum172.55→17255/300%;TPEX6488(19.59,7.60,-13.12)sum14.07→4.69%;TPEX6846(-16.48,-11.28,30.99)sum3.23→323/300%;TPEX6198all0→0%;TPEX7743(-29.47,-16.55,-24.23)sum-70.25→-281/12%. Negative and zero retained valid.
-2realheld cases: TPEX6785 publishedYoYblank3months →MISSING_PUBLISHED_YOY;TWSE2816Septrowabsent →MISSING_MONTH. NULL, nozero/no2monthfallback. Causeofnativeabsenceunverified.
- Meaningful verifier defect discovered and preserved: initialDecimalparser didn't remove native thousands commas, falsemissing28source/companypairs;initialready1928,missingYoY37,missingmonths15 vsprior1956ready. initial_parser_failure.json saved FAIL_VERIFIER_NUMERIC_PARSER. Fixed numericQA .replace(',',''), native strings/source notmodified; actualnative1,096,390.56 parsing exactFraction109639056/100 regressionPASS. No extreme-ratecapping/sourcecorrection.
- Full1980rawinputpresence audit afterfix:1956threeYoYvalues ready,15missingmonths,9missingpublishedrates. This is inputreadinessONLY;only6trial averages computed, no1956fullcomputedaverages.
-7syntheticnegativechecksPASSreject:percentagefactor100,duplicatemonth,wrongyear,crossmarket,NaN,missingratefalse0,missingmonth2monthfallback. Theseisolatedcopies notvendorerrors.
-23realHTMLrows/6rawHTML SHAfiles exactcode/YoYcolumnmatchPASS,CP950sourcepreserved. Native MAIN005stagingSHA unchanged2342be32b542a55af9c1ba1a28cafef60aa8e6caea6c0ae29eebd978f04f329a. Same-sourcearithmetic notindependentmarketGolden. No deployed dailycalculator/443/E2E/role/PIT/allfour-sourcecompletenessapproval;no newpaid/FinMindcalls.
- Report docs/registry/delivery/wp00/MAINLINE_011_REVENUE_YOY_TRIAL_20261014.md commitecb1054a58b44aa314f8ac5ae5888d7285617047;verifier7c0049c9070802926ddebeded9fb09fdabb21e2a;answers e89b015d2fc68236a79a0ccd9e1b062337d7e6bd;initialfailure1d59d6aa0428cb555fc36796f9423002df32f5b7. ExactGitHubreadbacksPASS.
- Drive https://drive.google.com/file/d/1AS1ltNSaTiMh3-zBfcSMpNIo9ckfXeCs/view ;19047bytes SHA256b41b414e14eedba35146ad0d5457fb77e7151ebce927cae729a48bdf2f107eb4. FullZIPdirectory/CRC+10memberhashes+6numeric/2held/7rejection/1980rawreadinesscount readbackPASS.
- Nextmainline: merge price+revenue input/result packets into feature-level normal-input/partial-input/no-calculation research delivery cases so one missingfeaturedoesn't block others. Keep explicit separate priceAsOfDate vsrevenueReportMonth/AvailableAt; never sneakSeptincome intoJulydecision. Useexistingsmallauthoranswers andrawqualitymasks; noextraallmarketMAcomputations orPythonDerivedengine. Tryrealheldrevenuecodes2816/6785 with usablepricewindows and actualpriceNULLwithusablemonthlyrate, whilehistoricalrole/PIT gates stayblocked. Keepprior8105/5236/±1仟元/139absencecausebranchesdeferred.

## 2026-10-14 MAINLINE-010 completed: small rolling-date and strict-comparison experiment

- Same MAIN009 candidate FormulaVersion C1-MAIN009-SMALL-PRICE-EXPERIMENT-0.1 unchanged. ChatGPT authored exact trial answers; Python QA only verifies provenance and invariants, no deployed derived-indicator engine.
- Newreal datesJul8/Jul9 ×TWSE2330,TWSE1709,TPEX6488 ×MA5/strict-above/BIAS5 =18outputsPASS. Jul8windowJul2,3,6,7,8;Jul9windowJul3,6,7,8,9. Correct moving source-calendar window, no weekends or future rows.
- Jul8MA5 2330=2455 aboveTrue BIAS200/491%;1709=24.08 aboveFalse BIAS-325/602%;6488=1246 aboveFalse BIAS-800/623%.Jul9MA5 2330=2445 aboveFalse BIAS-200/163%;1709=24.28 aboveTrue BIAS300/607%;6488=1275 aboveTrue BIAS100/17%.
- PriorJul7 3real cases/9outputs regress unchangedPASS. 9boundary/rejectionchecksPASS:futuredate,duplicate,wrongsecurity,staleMA,NULL,wrongBIAS rejected;synthetic equality100 MA100 strictFalse+BIAS0;synthetic near-rounded collision last100.004 vsMA100.0008 strictTrue;roundedFalse rejected. Syntheticcopies are math fixtures, not sourceerrors/tick-validity claims.
-45raw row comparison occurrences (30new+15prior, NOT45unique stockdates),14raw SHA filesPASS;SQL and officialnative close columns matched. SourceDB unchanged ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438.
- Report docs/registry/delivery/wp00/MAINLINE_010_ROLLING_DATE_TRIAL_20261014.md commitd9d349a46de56161a1750e97db07b79444fa350c;verifier993bce8b6245776cf79e55db0352ff4209bcd560;answers1c42a8dee7e19b9cb70a6976050e8b6ec234dc03;exactreadbackPASS.
- Drive https://drive.google.com/file/d/14L4nNSQI-V2lcHk5yhwkgq_ewb6nEFXd/view ;9335bytes SHA2565c61be73f87f57ebd7ae9770d284fffe7edc7683e9239d7662cb3f4a225b39dc. FullZIPdirectory/CRC+9member hashes+18new/9prior/9boundarycountsPASS. Allraw inputs/answers/formula/summary inarchive.
- formal_signal_allowed=false, Master443 statusesunchanged. Same-source arithmetic verification is NOT independent market Golden. No historicalrole/PIT/currency/corporateaction/allfour-source completeness/443formula/full DAILY E2E approval, no paid/newFinMind calls.
- Nextmainline: small native revenue3monthYoY arithmetic-mean trial with explicit report-month Sept2026anchor, raw percentage-unit handling, negative/zero/missingmonth cases; no historicaldaily PITjoin whileAvailableAt unknown. MAIN008 source/main005/revenue_expanded_native_fields.json is verified archived input, recoverfromMAIN005Drive1XoDzuFBu0eGQWDVmFHOhLGOS-xdwHCSl if scratch missing. ChatGPT exactsmall answers, Python arithmeticQAonly. Keep previouslyisolatedexceptionsdeferred and avoid anotherwholemarkettransportrepeat.

## 2026-10-14 MAINLINE-009 completed: first small real-data arithmetic trial

- Moved beyond input mapping into3actual trial metrics (MA5,CLOSE_GT_MA5,BIAS5) ×3real securities =9results (6numeric,3Boolean), authored by ChatGPT as exact values. Python only verifies invariants/provenance/guards, no deployed Python investment-derived calculator.
- FormulaVersion C1-MAIN009-SMALL-PRICE-EXPERIMENT-0.1 experimental: unadjusted native close mean over5consecutive source/calendar dates INCLUDING target; strict close>unroundedMA;BIAS=(close/MA-1)*100 exact percent-number rational. Formal currency/corp-action/identity/PIT and full release warmup not lifted, Master443 statuses unchanged.
- Target2026-07-07 datesJul1/2/3/6/7. TWSE2330 closes2505,2465,2445,2460,2440,sum12315,MA2463,abovefalse,BIAS=-2300/2463%.TWSE1709 native NAME和益 (do not overwrite with chat-memory different issuer),closes23.20,23.40,23.70,24.85,24.50,sum119.65,MA23.93,abovetrue,BIAS5700/2393%.TPEX6488 closes1105,1205,1255,1335,1205,sum6105,MA1221,abovefalse,BIAS-1600/1221%.
- Exact identities allPASS:5*MA=source sum,strict comparison,BIAS rational cross multiplication. This is independent arithmetic verification of SAME native source data, NOT independent market source Golden. Human-authored static trial outputs do not establish deployed daily calculation.
-9guard/sensitivity casesPASS: real4bars short;real00625Knative --missing;syntheticNULL/dategap/duplicate/nonpositiveprice on isolated copies;providedRAW_ONLYrole on real1101Brows (not historic role proof);actualfull2330quarter63bars targetSep30 insufficient240;wrongBIASanswer numerator-2301 rejected. No zero-fill/forward-fill/crossmarketjoin/sourceoverwrite.
-25native sample rows (3trial+2controlgroups) SQL+official raw close field comparisonsPASS;10related raw SHA manifest checksPASS. SourceDB unchanged ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438.
- Report docs/registry/delivery/wp00/MAINLINE_009_SMALL_INDICATOR_TRIAL_20261014.md commita622f1c08b409de30ed7040610f8f7f85963b9cd. Trial answers f4b563ff13287bc8203cd1b5c29d9018f7219601; verifier e2de5c76c5c27196077222f2524d04ffb0d4e4c9. Inputcases/candidateformulas/summary committed and exact readbackPASS.
- Drive https://drive.google.com/file/d/16wVVa7cZ_F8b21jRMd2RK_G7IjbmevfY/view ;10219bytes SHA25653ab9f745f48950366649734d5c7577822224ebb1231bd51ee44902881ac66a0. FullZIPdirectory/CRC+9member hashes+3trial/9output/9guardcount readbackPASS.
- formal_signal_allowed=false; no normal-analysis/ordinary-role/PIT/443/full-marketfour-source completeness or formal DAILY E2E approval. No new market API/paid/FinMind calls.
- Next mainline: reuse frozen small price experiment on additional real target dates (e.g.Jul8/Jul9) and equality/denominator/window boundary fixtures, or add a clearly defined small native revenue three-month trial after report-month semantics. Do not repeat whole-quarter data transport or pursue8105/5236/±1仟元branches. Keep data/derived boundary: ChatGPT fixed answers or authorized fixed ChatGPT computation, Python QA only. Never present one arithmetic verification as all indicators implemented.

## 2026-10-14 MAINLINE-008 completed: current Master443 candidate input mapping

- Current Library Master C1_JARVIS_R7_MASTER_AUDITED_20261012.xlsx libfile_6b50900d9ea88191a3070f42a1059d35 materialized latest version2; SHA256f573316ec84363a824151a10f61e660c1101e593712019fd0890f567f8548027. All443 rows in32_443_Metric_Audit retain DEFINITION_PENDING/BLOCKED_DEFINITION_PENDING. Master unchanged; no status writeback.
-443 unique IDs mapped to candidate sources, status and specific holds. Mapping only, no actual443 derived values calculated, no formal DAILY E2E/PIT/source-contract/model approval.
-754183 price input staging rows compared one-for-one to SQL. OPEN/HIGH/LOW/CLOSE each419050 present (group OHLC QA conservative mask); TURNOVER754183 native amounts exactly scaled to 億元.334185 native zero-volume rows preserved. VOLUME modelunit張 remainsNULL; native shares retained separately pending instrument unit/historical identity, do not convert entire market by1000. Currency remains unapproved for all instruments.
-1980 MOPS company/market pairs staged9 report-period fields (M0=Sept,M1=Aug,M2=July), every value checked against recovered verified MAIN005 archive; amountscaling exact, native percentage numbers kept. Native revenue counts1966/1980/1979;YoY1960/1974/1973;MoM1960/1971/1973. All AvailableAtNULL; reportmonthanchor must NOT be joined as historical daily latest-known value.
-57 main-force/broker/concentration metrics require uncaptured broker inputs; general INST_DAILY cannot substitute MAIN_FORCE. Financial snapshots have basicEPS and balance inputs but quarter/cumulative basis unverified, CFO/FCF notcaptured. Sector indices present but member/PIT/benchmark alignment pending. Longwindows scoped, no all-market zero-filling.
- SourceDB SHA unchanged ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438. Reused MAIN004 window masks are metadata, NOT indicator results. No new paid/FinMind/API calls.
- Code scripts/experimental/daily_mainline_008_map_inputs.py commitb4bedc4f815d5ed72ba281509a8dfc328b614a8b;verifier1b33df6db639d7c1bed0d56489ca97a0436ef8e5. Report docs/registry/delivery/wp00/MAINLINE_008_MASTER_INPUT_MAPPING_20261014.md commit2d9b57e6c6df16f57f7acdd185b09a40b10d16d4.
- Full443mapping JSON and1980revenueinput JSON plus3monthly price JSONL are in Drive https://drive.google.com/file/d/1l-DcLy4C9ssholV4ILd08JIg-YAd7GgM/view .14095633bytes SHA256a732860529bb8b7c8b582c8b4b774ba5e06df61e46ebb91e4b8399ee58756ad9. Complete readback ZIP directory/CRC,10member hashes,3gzip CRC/all754183JSON parses,443mapping/1980revenuecountsPASS.
- formal_signal_allowed=false throughout. Full four-source expected-universe completeness remains false. Python outputs are raw conversion andQA only; no MA/derived investment calculations.
- Next mainline: select a small concrete subset of mapped inputs for the authorized fixed ChatGPT computation handoff, freeze candidate formulas/units/windows with independent comparison fixtures and retain experimental/production gates separately. Do not spend another round repeating completed raw coverage/transport; do not treat all443definitionpending as reason to halt usable small experimental cases. Respect existing Data/Derived agent boundary in source contracts, and avoid an unapproved Python investment-indicator implementation. Keep prior8105/5236/±1仟元 and139absence causes deferred unless they affect chosen cases.

## 2026-10-14 MAINLINE-007 completed: captured daily coverage and unresolved universe gaps

- Mainline-first continuation. Existing readonly data only; no new paid/FinMind calls, no 8105/5236 or aggregate ±1 仟元 branch investigation.
- 20 daily source/family groups ×63 captured trading dates =1260 nonempty cells, independently recounted with SQL. TWSE/TPEx price calendars agree with captured FinMind calendar; no new independent official holiday-calendar audit.
- 754183 unique price output rows; 16681 source/code observed pairs, includes ETFs/warrants etc. Not ordinary-company counts. Price raw grades unchanged:419050 normal-input /335133 partial-input, not full-system analysis approval.
- 139 observed source/code pairs have1070 internal absent pair-dates. Causes unverified: no zero fill/carry-forward, dependent consecutive-window features blocked.5334 pairs start after period first date,3527 end before period last; overlap possible and not listing/delisting counts. Current stock_info not used as historic daily universe.
- 9 per-security family/date scope comparisons retained; absent family row means input absent IF feature depends, not source acquisition failure or zero flow. TWSE SHORT_SALE_ACTIVITY combined code/name parsed for83587 security rows;63 totals excluded, leading zeros preserved, native DB unchanged.
- MOPS revenue1965 source/company pairs have all3 monthly rows; distinguish MAIN0051956 pairs with all3 YoY values.15 pairs missing one observed month (14TWSE Sept,1TPEX July), cause unverified, lists saved.
- 887 relevant daily raw SHA checks PASS; source DB SHA unchanged ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438.
- FinMind captured calendar/market-level data does NOT certify all-market per-security raw datasets. Historical expected universe and all-four-source completeness remain explicitly false. formal_signal_allowed=false; no indicator calculation/PIT/corporate-action/historical-role or443/Master14/formal DAILY E2E approval.
- Report docs/registry/delivery/wp00/MAINLINE_007_DAILY_COVERAGE_20261014.md commit5e1133d4df8cd9306bc25bbfc6dc170bdb588f29. Code016a8a5358ec7da8226ace5930f725e7003c8673; verifier060a6235d05cca78dffa0ce70491678d4b2c1995.
- Drive https://drive.google.com/file/d/1u33cWq2Im_J9rhdi9tsVEFEvsTmOEOcf/view ;2385876bytes SHA256fa0c06a82345004545cde828779557ac7a58a9b2ff876a4b18e5a9ef2c9620fb. Full readback ZIP directory/CRC,13member hashes,3gzip CRC/full754183JSON parses PASS. Native bodies remain earlier archives.
- Next mainline: use current authoritative C1_JARVIS_R7_MASTER_AUDITED_20261012.xlsx (Library libfile_6b50900d9ea88191a3070f42a1059d35; read current version before judging) and repository source contracts to assemble concrete field-to-model input mapping and feature-level normal/partial/blocked dry-run. Keep240-day insufficiency and isolated exceptions scoped; do not silently promote missing family rows or assume indicators computed. Do not repeat finished MAINLINE001–007 absent new changes/failures.

## 2026-10-14 MAINLINE-006 completed: native institutional and margin field QA

- Mainline-first. Existing 2026-07-01–09-30 raw rows only, no new FinMind/API calls, no paid access.
- 541,070 rows across 6 TWSE/TPEx families, all 63 trading dates each; 5,303,784 native arithmetic checks. These are rows/checks, not companies, indicators, or formal DAILY E2E cases.
- Institutional detail 400,911 rows; institutional market amounts 882 rows; margin 139,277 rows including TWSE market aggregates. All institutional relations and individual margin same-day relations PASS.
- TPEx total uses FN+ST+DL, not FD+ST+DL, preventing foreign dealer double counting. Native duplicate field arrays/positions preserved. Positional aliases experimental, formal source contract pending.
- Two scoped flags: TWSE aggregate financing amount 2026-08-21 and 2026-08-26 each expected-minus-native balance +1 仟元. Cause unverified; no source correction, no rounding assumption. HOLD_FEATURE only on affected balance identity, no branch investigation.
- 378 raw file SHA checks PASS; source SQLite unchanged ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438. 541,070 output locators unique, 462,628 negative institutional net groups retained. Native zero retained, no missing-input substitution.
- All formal_signal_allowed=false; raw arithmetic PASS is not normal-analysis/model approval. No derived rolling chip indicator, historic role/PIT or 443/Master14 integration claim. All-market expected-universe completeness not certified.
- Report: docs/registry/delivery/wp00/MAINLINE_006_CHIP_FIELD_QA_20261014.md (ff3068539515eef095691cae3e73fda9637d77d8).
- Drive archive: https://drive.google.com/file/d/1ML1QsVZ2i8agSGkxyf5eriQorJKAxgxZ/view , 22,890,236 bytes, SHA256 5cba1dc8776327d113d622537c0e02fd8a50010f0d4b2ec6a611cbf072ae3e14. Complete readback ZIP central directory/CRC, 12 member hashes, 3 gzip CRC/JSON parses and 541,070 row counts PASS. Original raw bodies remain in existing archives.
- Next mainline: daily source/date coverage and expected-universe gap manifest, distinguishing no trading/no eligibility from genuinely missing files/rows; keep isolated ±1 仟元 and prior 8105/5236 exceptions deferred. Do not repeat these finished field tests without new changes/failures.

# MAINLINE-005 完成月營收比較欄位擴充與財報前提QA｜2026-10-14 Asia/Taipei

- 主線續測5925公司月營收、3952財報列（1976來源／公司組合各損益與資產負債），無新市場／FinMind呼叫、無YoY/MoM/TTM指標運算、原兩庫與12營收原頁不改。
- 先查舊庫只有當月营收導致YoY重算前提全缺、MoM3931ready；完整HTML已有上月／去年同月及官方MoM/YoY，故不能把尚未轉入當來源缺失。**final以revenue_expansion_summary及revenue_expanded_native_fields為準**，舊summary revenue_prerequisites是初始窄欄位階段，不再代表最後缺口。
- 12頁CP950／SHA核對，5925當月原值與舊庫全同，轉入比較金额／累計與官方百分比。MoM原值5904有值／21缺（分母0）；YoY5907有值／18缺（分母0）；1956來源／公司组合三個月官方YoY齊全。沒有重算比較率／三月平均，24月新高仍不分析。仟元原值留存、金額顯示除100000為億元，百分比不換。
- 初次HTML假定4位代碼漏912000等，記FAIL；改保留4–6位來源碼後5925逐值／唯一鍵一致。長碼資料未提升普通股候選，角色仍独立；反例留存。
- 金融兩源中文／英文Code/Year/Season核對ROC115→2026、ROC出表日→ISO、不填AvailableAt。有效1976損益／1976資產負債皆2026Q2，主鍵唯一；1976資產＝負債＋權益原同單位恆等式全PASS，依各業總計／總額欄名映射。
- EPS1976皆numeric，448負／5零有效保留、元/股不乘1000／不改億元；其他財報貨幣單位契約未證實保留native。單季/累計逐表口徑待，Q2不自動当單季、不直接EPS累計相減，不偽造QoQ/TTM/8季新高。原庫SHA不變（price ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438；published7998d01a14042064d127367296d4095691c8f9bdf2ccbe8da58c8b3d29d4a9ae）。
- code e1a5c9fa068621afb3bb5f3c2125669e4dbb4334、revenue parser0da6fd62abcdd9f313f24086a9d6aa024263183e；report docs/registry/delivery/wp00/MAINLINE_005_FUNDAMENTAL_FIELD_READINESS_20261014.md commitbe74ede1299b03ec54e728cfbb017f1ed69e8168；financialsummary0ae54f98d892df443c4c29d9485d6f4f4b8d1bdd；revenueexpansionf76f90faf0e3f28680b5835ee90ebb1b2e35351b。
- Drive https://drive.google.com/file/d/1XoDzuFBu0eGQWDVmFHOhLGOS-xdwHCSl/view?usp=drivesdk；879749bytes／12成員，SHA50a882f0a0e52043701b4d87c9b3f8875b362198578c00aef3ca83d982dfc528。完整回讀壓縮目錄/CRC／11成員SHA與5925營收＋3952財報列數通過。封存包含兩階段、長碼失敗、全欄位與來源定位、1976恆等式；重跑需MAINLINE001兩庫與最初12原MOPS頁。
- 缺史／口徑只限制該項；四來源尚待補、443指標／Master14／正式日更E2E未整合。Production BLOCKED、興櫃RAW_ONLY、原價格419050正常335133部分／MA240不分析不改、B115934/934與38候選9OPEN不提升，正式訊號0。

---

# MAINLINE-004 完成全市場依視窗資料前提QA｜2026-10-14 Asia/Taipei

- 主線續測754183證券日／16681來源與代碼組合／63交易日，5/10/20/60/120/240窗口，收盤／OHLC／量／非零量分母四組，18100392欄位窗口判定。不是1810萬指標／股票／E2E情境；ETF／權證保留RAW_ONLY，歷史普通股與PIT未核准，未計算MA或策略訊號。
- 收盤與OHLC本批ready列相等：5日250127、10日181228、20日118741、60日8679；量資料ready688190/610048/467274/32043；分母非零前提ready521623/511497/424908/31512。120/240全不足0ready。335133部分價列中305467仍有5日量視窗資料，不因OHLC缺整列阻擋。
- 5/10/20/60零量分母阻擋166567/98551/42366/531；零成交量原值有效保留，可做量資料檢查，不補0，僅量倍分母前提不可用。窗口截至目標日含當日N日；N日報酬通常需N+1、排除當日窗口／RS／調整價等不能直接用這個N欄位旗標核准。
- 原2330 close63日，5/10/20/60可用59/54/44/4；5236按來源切段，TWSE7/16前TPEx不混暖機，TWSE前4日不滿5日。所有754183輸出唯一來源／代碼／日期、6窗口ready/block互斥分割、3欄位窗口巢狀、分母ready+zero=量ready、正式訊號false核對通過；原庫SHA不變ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438。
- 檢查規則初次誤要求分母正值也長ready→短ready，真020001 7/31五日零量但10/20非零量反例，記verification rule FAIL並修正，只對欄位完整性套巢狀，不對分母正值套；原反例／三組第一版皆留存，來源資料不改，不合併兩版重跑當新正式驗收數。
- code f18d29b5338d9257ff799a07bc4b7ed683b03499；report docs/registry/delivery/wp00/MAINLINE_004_FEATURE_WINDOW_READINESS_20261014.md commit659f2d9769925a2bf4ebf03b4fb6fb75725dce21；summary9beb1bfb9bd75cb568d8d9149572b47cabc74db3；counts2ea35d9bfe017f4187010dc5c7aea2284f32f6be；verification175f13844a38e82c52b22825afdab07920dcab91；initialfail5f45c1ffb7dcababf54bceccdf5054d6fef99165。
- Drive https://drive.google.com/file/d/1yfassxh9IModzFLlnCF_cyKm06r4PHdk/view?usp=drivesdk；23348160bytes／17成員，SHA 7110c04e20a5c04ca31e6d47d1cf7151b5920c54f317414ec6634de2e43fe88c。完整回讀 ZIP壓縮目錄／CRC、16逐成員SHA、3月gzip CRC與754183記錄JSON/false訊號驗證PASS。封存含全市場逐日視窗旗標、兩版本、反例、計數／樣本與腳本；完整重跑需MAINLINE001相對路徑原庫。
- 443指標／Master14／正式日更／回測與發布仍未整合，四來源待補不100%齊全；Production BLOCKED、興櫃RAW_ONLY、B115934/934與38候選9OPEN不提升。原價格分級419050正常／335133部分保持不變，MA120/240不分析，市場請求0、FinMind0、訊號0。

---

# MAINLINE-003 完成每日接續窗口／衝突保護測試｜2026-10-14 Asia/Taipei

- 主線續測，不重抓市場、不追查支線、不製Excel。63日gzip收據1666918記錄的SHA／gzip可讀／JSON列數與批次摘要全通過，原63收據執行前後無變。
- 重現002舊函式缺口：資料落地但標記未寫會assert停止（隔離真實日副本，legacy FAIL）。新receipt_store只在完整內容與當次輸入一致時補標記，資料檔SHA不改；不相同則拒絕而非覆寫。
- 七項新檢查7/7PASS：7/1寫100筆後中止→25823整日接續；8/3完整暫存未落地中止→25469；9/1落地未標記中止→27485只補標記；各再重播新增0。另提交後内容不同、孤檔內容不同、標記無檔、標記列數錯誤皆阻擋、原檔不改。後四為隔離副本，不是真供應商修訂、未填改原始OHLC。
- 新引擎 ca6e06a8b8588196bc024fe4c3bec72dd8238cae；tests3242fff3cd8cf32b7c965ba7f0d20d1c56fcd37a；報告 docs/registry/delivery/wp00/MAINLINE_003_RESUME_AND_CONFLICT_CHECKS_20261014.md commita26368ca8e545d36be6c0a5215ceddb2ea08d7ed；summaryae670b45903d84e6060c0eb279f8e04a24edea1b；legacy599068abf70bbea43324456b64841e31ed7bca1e。引擎為離線參考，未接正式日更。
- Drive https://drive.google.com/file/d/1sZp9Cd_I-O7l6ZaepqQilRx-JFGi3wW_/view?usp=drivesdk；8452973bytes／19成員，SHA69d860eeadc9a3162878adbdc44cd7807091dd391a72b29d74e57e6721ec02f1。完整下載後ZIP壓縮目錄／CRC、18成員SHA、整檔SHA/size全PASS。包內cases故意存在無marker或缺data的測試副本，勿當實际資料缺失；完整重跑需要002的63日收據及全新cases目录，import receipt_store須兩腳本放同目錄。
- 七項為主線接續／衝突檢查，不提升完整E2E數。OS任意崩潰／多writer／實際修訂／429／443指標、Master14、正式管線未验收；價格419050正常／335133部分分級及MA240不分析不變。四來源待補未100%齊全，Production BLOCKED、興櫃RAW_ONLY、B115934/934與38候選9OPEN不提升，市場請求0、FinMind0、訊號0。

---

# MAINLINE-002 中斷後恢復完成與完整性複核｜2026-10-14 Asia/Taipei

- 原中斷點在002封存驗收；原Drive1cmBRFC0foAgknWq6kYnZ6hqKCylG0_F9完整下載後BadZipFile，本機原收據SQLite malformed，舊封存FAILED不可使用。大小／SHA相同不足以證明ZIP可讀。保留失敗，不刪除／不改寫歷史為全部PASS。
- 原始主線900檔逐SHA全部相符、缺檔0／變更0；主庫完整性PASS、價格754183列，公開財報庫完整性PASS、33415列。問題觀察在測試收據／封存，不是原行情缺失；根因未證實，不歸因工作量大。
- 單庫及分月SQLite收據重建後重開仍malformed，兩方案FAIL。改逐日gzip JSONL完成標記方式，重建63日1666918記錄，再逐筆重播1666918：新增0、衝突0、63邏輯摘要與中斷前全部一致、來源庫SHA仍ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438。新收據格式PASS，舊SQLite收據實作未核准。
- 100筆受控中止沒有提交任何日收據；隔離壓縮副本翻CRC被BadGzipFile拒絕，真收據不改。不是OS任意崩潰／網路429／正式日更E2E验收，沒有根因結案。
- 900raw無改、來源主庫無改，價格分級419050正常／335133部分，OHLC缺失不阻擋活動；借券依賴只2列部分，MA240不分析。五項遮罩／限制檢查保留，三級升級是隔離旗標副本，不是供應商實補，訊號0。
- 新封存分月完整回讀驗 ZIP壓縮目錄／CRC、所有成員SHA、63gzip CRC／JSON解析／每日期列數與邏輯摘要。7月22日560565列、8月21日552868、9月20日553485，總63日1666918；另報告包ZIP與整檔SHA通過。
- 2026-07: https://drive.google.com/file/d/1KVIs1hpr9uqmikgN4cH6yh-ORTQOZZS5/view?usp=drivesdk；25589245bytes／45成員／SHA 5f84e846fd8008f1c4247ea8219bc5ee9e8f34135b5c4a67321e06d5f6741d74。
- 2026-08: https://drive.google.com/file/d/1m5tHigzqvjz0cKghhB3av9x5ZyJ1uP3v/view?usp=drivesdk；25234410bytes／43成員／SHA b8a979b69617bba1b00a79708c3481eb3464e869b22fbfd6851e7147905cb46f。
- 2026-09: https://drive.google.com/file/d/1QSjhsMQpaAjAPsERN3L_8RCZSteFLMcm/view?usp=drivesdk；25250740bytes／41成員／SHA 21e388561772f3d133cee9a7a2f26c44dee12de8b4acfc98f63d61f251a20fd2。
- reports: https://drive.google.com/file/d/103Gxg2MKjzUMTrhI6oJFUQ99N6NftcHD/view?usp=drivesdk；14824bytes／10成員／SHA 79a3d9db2cc4c22b9bcdc103ccb2b1d9ce287e6c0e782ef3ceb61402aee2aefd。
- 報告 docs/registry/delivery/wp00/MAINLINE_002_RECOVERY_INTEGRITY_20261014.md commitaa449fefc5e5e1cb5cd474670ef78d0acc19fee0；summary1edf8af999dff52a718bf20945f85af4fde003af；incident31dcb728d3405ca65a6809b9bc85eac17a0840f4；atomic recovery codee199682aaffcdeefd5775b2944476c14deba14fa；readback驗證JSON MAINLINE_002_RECOVERY_DRIVE_VERIFICATION_20261014.json。完整重跑需MAINLINE001 source庫的相對路徑，分級檢查另需007 policy1.0.2，來源不再下載。
- 四來源必需資料仍有待補，443指標／Master14／即時抓取至發布E2E未整合；Production BLOCKED、興櫃RAW_ONLY、B115934/934與38候選9OPEN不提升。保持主線優先，待補不逐筆追查阻擋主線。

---

# MAINLINE-001 完成可取得主線資料整併、分級與批次增補｜2026-10-14 Asia/Taipei

- 依使用者14:47指示主線优先、其他支線／需補充後續做；暫停逐筆5236/8105追查，建立可查詢資料庫與正常／部分／不分析清單。**四來源全部必需歷史資料未100%齊全、尚未執行443正式指標或正式日更E2E**；缺項按功能不分析，其他原始資料檢查繼續。
- SQLite prices754183證券日：TWSE86674／TPEX667509（包含ETF／權證）。正常資料419050＝TWSE85955＋TPEX333095；部分335133＝TWSE719＋TPEX334414（OHLC不分析、活動可用）；兩核心都不可用0。不是419050家公司／股票訊號，商品角色／歷史身分未知RAW_ONLY。金額原值保留另附億元。
- 原核心family_rows923944、revenues5925，12MOPS本外國原頁＋其他原檔900 SHA核對；13官方每日族群各63日。TWSE估值7/17 supplement正確納入68084列。familyrows包括FinMind當前目錄／多年交易日，不能總數冒稱季度股數。原始值不覆寫、未知AvailableAt不補。
- batch official run38524480746 success／art11875785394 digest b86d499c0d36f0711b897d3dc12da703702dbc9b1d47a776620c36b323033d09：30請求、29完整（2schema／27表）、1TPEx董監IncompleteRead列待補、無FinMind新增呼叫。現公司基本資料TWSE1095／TPEX893；2026Q2損益／資產負債3952列、TWSE8月董監27475明細；8空代碼占位列未當公司。新published_fundamentals.sqlite33415有效原始列、403485逐欄存在性分級，缺值／不適用待判不補0，當前快照不當歷史公告資料。
- 8105借券股日及市場合計依賴欄位恰2列部分；其他欄位繼續。MA240／長暖機／現金流／其他持股月份／集保與分點／FinMind免費全市場個股／公告時點及歷史角色列deferred_gaps；不做支線追查，不阻擋其他資料。有值／结构可用不等同產業指標、單位和正式股票分析核准。
- 核心DB ZIP https://drive.google.com/file/d/1dxCdFpOy4p-iJovQrAjoI8BxW92ARTlg/view?usp=drivesdk：101397015bytes，SHA ad4bd4e903e3ea106bfe59de2be2ed802c7cdff49ea4176b2c541d9f72d42daa；Drive整檔回讀／CRC／內部908636160bytes SQLite SHA ec1eb2b6764cb135eee8edb836eae77a54b49e1bc402b9d47243cca9c3c1a438通過。
- 補充分級／new raw／新公開表DB封存 https://drive.google.com/file/d/1kXOIJxHzY346YhYh5nyZzYF3tKXRGAhF/view?usp=drivesdk：10759890bytes、48成員、47成員SHA／CRC／Drive回讀一致 SHA fce4b6a0d21c0ad023e51f06f0bc182ab33e79b12b2aa8a177bfbf50b5f7e447。核心兩庫SQLite integrity PASS、價格唯一主鍵、營收6市場月列數、raw SHA／日期覆蓋驗證。原各輪raw沿用已封存Drive，脚本需README所列相對路徑輸入；不是新ZIP單獨含全部900原報。
- report docs/registry/delivery/wp00/MAINLINE_001_THREE_MONTH_DATA_AND_GRADES_20261014.md commit84b344dbc3c502f387635a973c2ffff7e717067d；coverage0a4d19b930820ab4e760969a17597ef18b473c39；feature428902cdcf88fde9333e3278a9259ad5b12c1382；gaps7752dd7a941dd42d4a1c31df9aaef7fc8dc0402f；published2bddbedd4ade8792b7bdaa0e6dfdd7a26461af63；verification26a87384ffa4361d5d8c9e4998b5399d0a6e4cca。collector a9f01f4bd4ab1ef16f877cd3e479e6f3cceea78e（pin詳workflow／provenance）；build84ba69d9984acc5191602e9b2d794526a55478a6、extendbcde8e8ad8e2864c9a7f04098359aea0636e2c35、import64f8086bc1331624ce20d40b61a62ce6a6ab5e6b。
- 下一步依使用者主線需求整合賈維斯正式指標／Master14／日更資料流程，再依deferred清單補資料提升等級；勿回到逐筆支線反覆測試。Production BLOCKED、興櫃RAW_ONLY、B115934/934、候選38/9OPEN不提升，正式訊號0。

---

# DAILY-REAL-010 完成5236市場轉換日期回歸｜2026-10-14 Asia/Taipei

- 接009新輪，TWSE官方最近上市公司表確認5236凌陽創新7/16股票上市買賣／櫃轉市。TPEx原公告搜尋有同日期摘要但開啟全文Internal Error，未冒充取得全文，以TWSE主證據和實際價格raw核對。
- 重驗原TWSE／TPEX價格126檔SHA，63交易日126市場存在性檢查：7/1–7/15 10日只有TPEx、7/16–9/30 53日只有TWSE，63日期PASS、雙市場同現0／兩邊缺席0。僅5236事件核對，不提升全市場歷史身分名單。AvailableAt保持未知，原値未改。
- 反例回歸故意把TWT93U首次7/15出現當TWSE上市日，精确捕獲7/15誤判；7/16正確規則63日PASS。離線參考測試，未串賈維斯正式日更／歷史身分管線。5236提前列入借券表時點契約仍待，8105 8/19借券公式7982000股差異仍隔離。
- report docs/registry/delivery/wp00/DAILY_REAL_010_MARKET_TRANSFER_DATE_REGRESSION_20261014.md commite4e611dc2c5d2be7efa036f131f431760d89425d；summarye44dde6ff0c39f9174bf220bb77a8c79ed37f581；counterexample52e9a0f2886cd41b9c171f4c79bca20213a3c29b；script2a3cffd4ea91dd221bcad4b0bbc604e744501ff2。
- Drive https://drive.google.com/file/d/1t3JnfE0YF1VNly7couZo36rrKT2_zzZF/view?usp=drivesdk，1634665bytes／18成員／17逐SHA及ZIP CRC／Drive全檔回讀一致，SHA 64bb73cc0f32400b69da55b149b17e2c8b7511e077c82f39ba60d830fcb85d0c。精簡ZIP含7/14–7/17兩市場8完整raw、126來源SHA路徑、63ledger、列摘要、反例、官方參考摘要；完整63日重跑需既有DAILY002原封存全部126原價檔，不冒充精簡ZIP單獨可重現全部原價輸入。
- 下一步繼續借券表記錄日與次一日名單／狀態語義，或補其他必需族群。四來源完整性、歷史身分／單位／PIT、MA240暖機、Master14及正式日更E2E仍待，Production BLOCKED、興櫃RAW_ONLY、訊號0，B115934/934及候選38/9OPEN不提升。FinMind呼叫0，市場下載0。

---

# DAILY-REAL-009 完成官方交叉報表與調帳語義核對｜2026-10-14 Asia/Taipei

- 接008新輪，重用三個月TWSE MI_MARGN／TWT93U各63日，126raw SHA重驗，無新增市場抓取／FinMind呼叫。共同代碼五融券欄406735數值，觀察1000交易單位換股數後全相同；不是全局歷史單位核准、不是獨立來源Golden，兩表皆TWSE且名單不同。
- 008 11證券日期前後22值均另官方表相符。官方MI_MARGN公開說明：授信機構成交次日持續調帳，最終數字揭露於前日餘額，前日餘額優先於今日餘額。分類為兩表一致／符合容許調帳模式，不能以跨日不相等直接判漏抓或硬性FAIL；每筆調帳實際機構原因未取得、歷史AvailableAt不推定。官方目前說明並非歷史修訂ledger。
- 市場合計315值直接2差异，7/15前日／當日融券各2000股；TWT93U有5236，MI_MARGN無列，差額全對應。依各表專有代碼調整後315全相符。官方7/15新聞確認5236 7/16轉上市，TWT93U7/15提前列入時點規則仍待查，不能改歷史身份成7/15已上市。另所有63日不共有代碼已列冊。
- 007 8105 8/19借券賣出當日公式差7982000股仍隔離，融券次日調帳說明不能解除同日借券公式異常。四來源完整性／來源、單位、身分、PIT／Master14／正式日更E2E仍未完成，Production BLOCKED、興櫃RAW_ONLY、訊號0、B115934/934及38/9OPEN不提升。
- 報告 docs/registry/delivery/wp00/DAILY_REAL_009_OFFICIAL_REPORT_CORROBORATION_20261014.md commitd43d6803266854acc1d981ce77cf8398875c8192；summary4ca7236d35afd0437b75be9b4b4bf24304f2ff3e；resolutionea02d48cadc710118b5a52bd08d5d710aba37f69；script a7a1ae1bdef5828b400112cfa8ddc14f662d7dab。封存含126raw／manifest／008輸入，腳本從封存同目錄重跑，本機完成不冒充雲端日更測試。
- Drive https://drive.google.com/file/d/1G7UMvNaS2Ggx-6vmwZSu0Yzl4D0-IWhH/view?usp=drivesdk；5555461bytes、140成員、139逐檔SHA／CRC及整檔Drive回讀通過，SHA 387cb87833576423bee98394bd72c7b82f0a9be31d5a2ed6729871328b567cd6。官方參考保存URL／摘要，未冒充完整HTTP文件。下一步查5236報表提前列入／歷史身分時點及8105借券重置契約，繼續其他必需資料族群。

---

# DAILY-REAL-008 完成本輪跨日餘額診斷｜2026-10-14 Asia/Taipei

- 已核對007完成接續點，沒有遺留執行中工作，進入008新輪。重用63份TWSE融券借券賣出餘額原始日報，全市場2026/7/1–9/30，不新增市场下载／FinMind呼叫。
- 63 SHA、62日期轉換、160808跨日數值、252表内個股加總／總計、124跨日合計分解完成。總計與分解均PASS；7/1前六月邊界未測。沒有正式E2E驗收／訊號發布。
- 17差異欄位＝11證券日期融券差異＋6市場合計。7/15兩項合計差（2000/408000股）精確對應新增5236前日餘額，數值可解釋但名單進入事件原因未驗證。其餘同證券：7/24 3669 -1000；8/6 2302/2342/2409/2484/2485/4564/6456/6533 合-19000；9/17 00673R +300000；9/21 2426 -2000，四合計同差。原因INCONCLUSIVE，不直接判官方錯誤或漏抓；離線dependency hold plan，未串正式管線，原值不補不改。
- 原007 8105 8/19公式內部差7982000股仍隔離，本輪沒有其額外跨日差异不能解除。官方文件搜尋未找到足以認證歸零／11跨日差異的契約。先查歷史融資融券／報表修訂與事件時點，不重抓全季度。
- report docs/registry/delivery/wp00/DAILY_REAL_008_CROSS_DAY_BALANCE_AUDIT_20261014.md commit69529c785b11e6b9e47645e9c5f7f743f776af04；summary ee52c5d2b878275af7cd7f0dc0339e0e92743e32；audit script89a8d2f71a3faa9dc1d77b0b23e8147ae9711427。腳本需同目錄selected manifest/raw，封存已完整含輸入可重現；本機跑完，不冒充GitHub日更E2E。
- Drive https://drive.google.com/file/d/1M52ZgtXLhZE6iwQt_scs4YxFtaXKnNdJ/view?usp=drivesdk；3009392bytes、73成員、72逐成員SHA／CRC與完整回讀核對：5546ebd8536b07ea3956079a728f7e1b274dc6ecc35166b30593445107698d86。保留63份raw、選用manifest、輸入SHA、17差異與名單出入／合計分解／依賴暫停計畫。
- 四來源全必需族群完整性、歷史身分／單位／PIT、MA240暖機、Master14／正式每日更新E2E仍待；Production BLOCKED、興櫃RAW_ONLY、B115934/934、候選38/9OPEN不提升。008結論INCONCLUSIVE_WITH_RECORDED_DIFFERENCES。

---

# DAILY-REAL-007 完成本輪測試及全程複核｜2026-10-14 Asia/Taipei

- 本段取代下方007執行中狀態。結論 RAW診斷PASS_WITH_SCOPED_WARNINGS，非四來源整體完整、非正式E2E／Production驗收。三個月2026/7/1–9/30新增TWSE三族群均63/63：法人總額378列、借券餘額81707列、融券／借券賣出83650列，合計165735原表列（含總計，不是股票數），189選用日報。
- 8/6法人總額原HTTP200維護HTML不算成功，只補缺日一次成功；原失敗與舊62日摘要保留。207捕獲body SHA、四capture ZIP digest／CRC及日期／欄寬／可用total／重複核對通過。法人買卖756數值與既有免費FinMind全相同，新FinMind呼叫0，未核准来源獨立性。
- 借券8/19 8105凌巨一個根差異影響個股＋合計兩列：7,982,000股餘額無流量歸零，隔離股日依賴欄位與該日市場合計，原值不改。官方115/8/17臺證上一字第11518032112號確認8/19起停牌；8/18報表已X!，不能把備註視當日交易狀態。歸零原因／旗標時點仍INCONCLUSIVE，非自動解釋成功。
- 全程複核保留初次總計重複加總失敗與曾提前寫9PASS的checkpoint誤報，修正只排明列總計後9組鉅額對帳PASS。舊1.0.1另發現list/dict QA與PASS unused None白名單TypeError，參考政策修1.0.2（515763e640f4e142f6430a1e62fe4f044e2b518f），18/18同套單元測試本機／固定GitHub run38517976275通過，不是36新項目／18類E2E。Combined QA38517927504成功、publish-raw skipped，未部署。
- 凍結948筆、120 L0 SHA、8附加版本證據，1.0.2四恢復回歸PASS；945顯式活動筆數、TWSE3筆proxy pending，OHLC代填0／訊號0。舊政策與重播結果保留，非自動恢復管線已串接。
- Drive archive https://drive.google.com/file/d/1Sk_aRgAY4MZg6Gt430E27u4Kyww5R0JI/view；4722787bytes、260成員、259逐檔SHA／ZIP CRC與完整Drive回讀一致：c2f7aec6e082b43254244de0311b928b7d6da3d62fcdd3ed846a5398798276a0。捕獲4runs38516872600/38517267305/38518123357/38518748370，各實際RunID／artifact／digest詳provenance。
- 最終報告 docs/registry/delivery/wp00/DAILY_REAL_007_FULL_MARKET_RECOVERY_PROCESS_REVIEW_20261014.md commit239ba53b453c77bdfa3d6d2df5adda1ae9e02214；coverage569600f9782e4bb93a1311e9e936e547f8d2cfd1；assessment17cd93183005d89cf23bd85ce083fe5226384fb2；quarantine9c2d03c71a9c5a8bebb4a576d44a9f76977099e5；provenancea24e5e1c0293eaa70e390d5499055b899b3c3154。報告／政策已GitHub讀回確認。
- 尚待：借券統計例外契約、TWSE三筆count契約、歷史身分／單位／來源／PIT、台產缺列原因、四来源其他必需族群與免費FinMind全市場個股、正式日更／429恢復／18類E2E及Master14_Test_History。未知AvailableAt与暖機MA240保持null。Production BLOCKED、興櫃RAW_ONLY、B115934/934、候選38/9OPEN不提升。中斷原因未有足夠證據歸因工作負載。

---

# DAILY-REAL-007 執行中接續點｜2026-10-14 Asia/Taipei

- 已完成count-contract run38516872600/art11872411027，8資源完整HTTP200，digest fe083efb755e918a9129a39ce7a7b32534d0d931db68c338f5e7e2913a83d34b與body SHA通過。TWSE日成交量值統計實際回整月，兩月表無成交筆數；年表只單一證券、無筆數，不能把1423/1541缺股票組合當無成交。FinMind BlockTrade官方doc為Sponsor，未呼叫付費data。
- 已驗948真實決策、120 L0檔SHA、8版本化附加證據；4項回補回歸全通過，0訊號釋放/0OHLC代填/948仍QUARANTINE。945明列成交筆數、TWSE3筆仍count-proxy HOLD。另9組鉅額單一/組合明細/市場總額對照正在檢查；初次assert未通過，尚未取得PASS，需檢查表內總計列與不同統計範圍。
- 新全市場三個月TWSE未取得族群正在run38517267305，script fb7455bc50485793b23523199eb3672e0f14cd10；INSTITUTION_SUMMARY/LENDING_BALANCES/SHORT_SALE_ACTIVITY，每類63日；官方頁表單導出、最多一次傳輸重試、月分worker各自atomic manifest、不可變body、實際RunID與完成取得時間、AvailableAt未知，FinMind0。
- 待接續：驗新artifact digest與rawbody；檢日期/total/欄寬/原表行數及適用借券/法人加減關係，缺失僅補缺；新資料不自動核准PIT/units/universe。完成後一起Drive封存、回讀SHA及正式報告/coverage。尚未有63日期結果不可宣稱全family取得。
- 本輪local files daily-real-007/，recovery script262760d58d5c47cbcf92434a3c82f55c1a2b41a7。Production BLOCKED、興櫃RAW_ONLY、master14登錄/live E2E待完成；維持B115934/934與原候選38/9OPEN。

---

# DAILY-REAL-006 完成新版 DAILY DQ 重播｜2026-10-14 Asia/Taipei

- 採用新SOP C1-DAILY-DQ-1.0-20261014（da409307b5caa9fefe4ef74812d1e8bbf6ce81ad）；原13項單元測試通過，另3類邊界發現空特徵集合誤判FULL及None輸入拋錯。參考函式修為1.0.1（dbd8fbd953cab008deca24644dd15af43cd1a55d），測試ebc2cb8cb81c73781976a7cf831f6187704f0c8f，SOP補充9e2a98de2ffe340f02899fe9d1fb5ecc4e0673c7；16/16本機與GitHub通過，run38515962732。尚未串接正式管線，也未聲稱18類E2E全通過。
- 754183證券日／126原始價格檔的SHA均核對原manifest，1.0及1.0.1重播存獨立版本。歷史來源契約、身分、AvailableAt尚未核准，正式訊號全QUARANTINE、batch BLOCK、釋放0；Raw檢查與數值對帳繼續。34份早期TPEx檔未記錄RetrievedAt，保持null，不用今日重播時間補舊取得時間。
- 前輪948筆正成交量缺OHLC中940筆零股三項相符；本輪8筆差額在官方鉅額／股票組合中找到，948筆股數及金額全相符。5筆TPEx有明列成交筆數，合計945筆三項顯式證據；TWSE1312A/1423/1541以命中明細紀錄數對應也吻合，但保留TRADE_COUNT_CONTRACT_PENDING，不冒充官方明列欄位。948筆OHLC仍null，不用零股／鉅額成交價代填。
- TPEx年度date=20260101，依列內1150918與五目標代碼筛選；TWSE7/22單一證券含1312A、9/16股票組合sub3含1423/1541，其餘三個組合明細亦保存。15資源由官頁表單/radio/detail資料導出，均首次HTTP200完整取得；FinMind0、付費0、帳號0。
- 抓取runs38515227819/art11871725781、38515511002/art11872050827、38515756467/art11871174073皆success，3ZIP digest及所有有body SHA通過。原manifest RunID為測試標籤，capture_context補實際GitHubRunID，不重寫原檔。新Raw保留DQ1.0批次標記，1.0.1决策另存版本。
- Drive10DEWuz0Mgfz6gHnQ6Q2ORqZ9CXp102Kf；319797bytes、48成員。47檔逐SHA核對與完整Drive回讀一致：ca1ab82658a39a3772652dc24415584534cedc123e28ace76088b4a30b5f8cc3。含兩版政策、13/16測試log、原失敗反例、15raw、版本化948決策及SOP未測清單。
- 報告 docs/registry/delivery/wp00/DAILY_REAL_006_DQ_V1_REPLAY_BLOCK_RECONCILIATION_20261014.md（d94b1f2a53772cca49fc4eb29e459781e0c37b69）；block summary a2cfbab9b16d1b24da9bc6b5784461bd8179cd19；test coverage94a717746d3a5638d80f2f4e3aa4231783df7d14。Replayer d724799cf5a700324185e2941ce0037c4ba8dbe2；block reconcile79bfee932d76c07894fd0a9a4eb2c7c5f725d6ba。
- 下一步為TWSE三筆成交筆數契約、歷史普通股名單／單位／PIT、台產分發缺列原因及四來源其他必需資料。持股UI、TDCC、公告前財報、歷史版本重播、實際429恢復與自動日更E2E未驗收；master14_Test_History未登錄。Production BLOCKED、興櫃RAW_ONLY、B115934/934、原候選38/9OPEN不變。

---

# DAILY-REAL-005 完成｜2026-10-14 Asia/Taipei（取代下方執行中狀態）

- 四全市場每日零股場次報表2026/7/1–9/30均63/63：TWSE盤中85792列/盤後85792列；TPEx盤中63422列/盤後63422列，無同日同表重複代碼；日期/欄宽/total(totalCount)核對通過。
- 原948個正量缺OHLC列：TWSE176＋TPEx764＝940列的成交股數/金額/筆數與盤中＋盤後零股完全相等；剩TWSE3、TPEx5共8差額待查。OHLC仍null，零股價格不代填普通OHLC。940是活動對帳通過，不是全部投資/價格品質gate解除。
- 剩8：7/22 TWSE1312A；9/16 TWSE1423/1541；9/18 TPEx1240/2751/5601/6680/8342。另取TPEx9/18盤後定價11481列，5目標成交筆/張/金额均0，未解釋差額；鉅額/議價/官方修訂仍待證。
- 東訊官方公告115/8/26臺證上一字第1150016913號正文確認9/10–9/18減資換股停牌、9/21開始新股買賣。63日期逐查，7停牌日官方無列、其餘56官方有列；FinMind恰56日期相同。東訊七日預期缺席已結案，不是漏抓；只適用2321，不代表歷史全市場universe通過。
- TWSE stat大寫OK先被只收ok錯誤拒絕，36回應嘗試/18個family-date保留；官網loader /^ok$/i支持casefold修正。恢復18既有資料，只补108未捕捉family-date，118次嘗試，不重抓成功TPEx或恢復18份。269個有body場次嘗試SHA通過；無body傳輸失敗只有manifest，沒有假稱全失敗body保存。
- 五Actions皆success：38509469601/38509674911/38509875743/38510415449/38510487947。五artifact ZIP SHA、所有有body原始檔manifest SHA通過。291總請求（場次279嘗試＋control1＋公告1＋頁/JS8＋定價頁/資料2）；FinMind0、付費/token/API帳號0。
- Drive封存1Sz42fQYCFrxITWAjyQnrGCiJ9pgmBTaw；11110050bytes、316成員（315files＋manifest），逐檔SHA和整包Drive回讀完全一致：b69621c875bcbba6b73ed5132d2713aec58d65c01e8aa07525cd369365d383f7。
- 報告 docs/registry/delivery/wp00/DAILY_REAL_005_SESSION_RECONCILIATION_20261014.md（f2a6114f4187e1933048f07d8a8589d65d56ec5d）；summary JSON e02eef0ecdc878af9910fa35c38ae94856b0d8ac；東訊eligibility JSON3dd01824c35ff907dc08cdcfa4da7ee4044c5e4e；reconciliation code ce12edf79c42c1797701ca5c7dc1f4d81cc29d31。
- 下一步優先8場次差額，台產九月分發缺列根因（數字已與MOPS/FinMind三月核對，未證缺列原因），TWSE借券/法人彙總、其他歷史公司事件/商品分類與四來源全必需資料。正式master14_Test_History/live每日更新未完成。Production BLOCKED；興櫃RAW_ONLY；B115934/934、原候選38/9OPEN不變。

---

# DAILY-REAL-005 執行中接續點｜2026-10-14 Asia/Taipei

- 已完成官方頁面契約發現38509469601/artifact11869436012及38509674911/artifact11869850545，兩artifact與9原始回應SHA通過。
- 四每日場次報表由官方form/JS導出：TWSE afterTrading/TWTC7U、TWT53U；TPEx afterTrading/oddQuote、odd type=Daily。Weekly頁預設Weekly未冒充日資料，沿頁內day.html鏈接取得Daily表單。
- 全三個月場次表批次正在run38509875743、job115675683332（code3bd753e2f1ce9d42f2f28123ac20fd03d949505a），251個未擷取family-date＋1則東訊官方公告JSON；TPEx盤中7/1已在control取得不重抓；FinMind0。
- 續接：等待artifact、驗SHA、檢日期/原表列/欄位，再與948正量缺OHLC股數/金額/筆數逐筆合計；本地daily-real-005/analyze.py已準備。尚無batch完成結果，不宣稱948已結案。
- 東訊公告入口5B699D4CA13211F19A80005056BE3760由官方頁form公告detail及onload id導出JSON；官方搜尋已指出9/21新股上市，待完整正文確認9/10停止買賣。原TWSE9/9有、9/10至18無、9/21有已觀察。
- local exec曾回報exec-server transport disconnected，後一次pwd重試恢復；不是GitHub工作中斷，不能據此推論兩次對話中斷根因或工作量過大。
- Production BLOCKED；全四來源仍未完成、興櫃RAW_ONLY。既有DAILY-REAL-004及003證據保留。

---

# DAILY-REAL-004 限定異常追查完成｜2026-10-14 Asia/Taipei

- Actions38507985163成功；9資源HTTP200完整捕捉，3官方頁面＋MOPS/TWSE營收重取＋4FinMind免費查詢；不代表全市場FinMind收齊。artifact11868976257 SHA b880086f930a1f0e18babc1f4fe8873bc1268309444ae02576a5880b9e034732。
- 1538/2321/1796共45列：官方OHLC--/---，FinMind四價0.0、股數/金額/筆數相等；存候選四價null並保留provider_raw0.0。不得全資料直接0→null，也不把0當有效OHLC。948列成交場次原因仍未全部確認。
- 東訊FinMind56列，其9/10至9/18七市場日官方原表也無2321；停復牌/公司事件原因未證實，勿判FinMind七日漏抓。
- 上市MOPS九月1073唯一代碼，TWSE分發1072，唯一缺2832；共同1072當月原數字一致。重取分發仍出表1151013缺2832，MOPS重取有868102千元＝8.68102億元。FinMind台產7/8/9月數字×1000全部一致，9月provider create_time2026-10-14不是官方公告日；缺列原因未結案。
- TPEx直接加總全商品不等市場總計；以代碼形態诊斷分區可重現63天189值，0差異。regex不是核准商品分類/歷史universe，不能刪全商品原列或據此promote。
- Drive封存1ELrHUuIeJaVH-ke8IOsHv4glD0QTk2Mw，222867bytes、23成員，SHA10b40d017f5bd45b7c915504e247fcba2ae9bec3451bfa48bb9984b929e5a631；Drive完整回讀完全一致。原始/診斷/45候選及報告保存。
- GitHub報告 docs/registry/delivery/wp00/DAILY_REAL_004_MISSING_PRICE_REVENUE_TRIAGE_20261014.md（a822e3e3613e6370de77d54c70acb4c5bf86a764）；JSON daily_real_004_issue_analysis.json（4af343ded876c6086f90ef6e576beaaf786e9440）。程式3859a058ffeef0515f6351cd95c394e19ff2e32d。
- 下一步：官方零股場次報表定位948缺價、東訊缺席期公司公告、TWSE借券/法人市場總計及歷史universe。全部必需資料仍未完成；正式master14_Test_History登錄/live updater仍待完成。Production BLOCKED；興櫃RAW_ONLY；B115934/934、原候選38/9OPEN不變。

---

# DAILY-REAL-003 完成續測｜2026-10-14 Asia/Taipei

- TPEx 六類報表均63/63日期（2026-07-01至09-30）：法人明細316880、融資融券57740、估值55946、價格/報酬指數4656、信用/借券餘額58521、法人彙總504原表列。
- 初始解析器把法人彙總 totalCount: [] 誤判；保留原9天，僅補54天，58次嘗試全部補齊。兩個Actions run成功：38498175491、38499491506。對話中斷根因未確定，不能歸因工作量。
- 五類493743候選原始列欄位/表內key/適用加減關係零警示；候選JSONL存檔回讀重播493743相同、0新增、0衝突。沒有證明經濟分類/歷史證券universe完整。
- 原行情754183證券日列未見重複key/型別/完整非零OHLC順序問題；948正成交量缺OHLC列保留追查，不補0。MOPS9月2832分發缺列仍待查。
- Drive新增封存145F8PWBOqyhoI7D21eVfXkKqMjrPKiRV，28142092bytes，425成員。424個檔案manifest SHA逐項通過；整包Drive回讀SHA `3dd325f3beb04380f8978e638d82e199510605eaa14a4e5c7906cda5621fec8e`完全一致。
- 報告 docs/registry/delivery/wp00/DAILY_REAL_003_WHOLE_MARKET_INTEGRITY_20261014.md（6102b44df88e1a6f725b61e8ff00c12027bdc8cb）；coverage daily_real_003_full_market_coverage.json（597885005f0a77f862242bf13d5289a27cd874dc）。ZIP中report保留封存前DELIVERY_PENDING，GitHub報告及本checkpoint為最新交付狀態。
- FinMind本續測0次、仍免費；四來源全部必需資料未完成。下一步以TWSE借券/市場法人彙總、歷史證券名單/商品類型、缺價948列及MOPS2832差異優先。財報/股本/持股/公司事件及FinMind全市場逐證券比較待完成。正式master14_Test_History未登錄，live daily updater未部署。
- Production BLOCKED；興櫃RAW_ONLY；B115934/934、原候選38/9OPEN不變。

---

# 最新續接：DAILY-REAL-002 三個月全市場原始資料（2026-10-14）

使用者09:18明確更正：小量=三個月時間，範圍仍全市場大盤/類股/全部個股，不准兩股抽樣当完成；FinMind免費，240日等缺歷史不擋短視窗流程。暫緩B72小合成輪，持續按全市場Raw族群補齊。
報告 docs/registry/delivery/wp00/DAILY_REAL_002_THREE_MONTH_WHOLE_MARKET_20261014.md，commit c985d4ff58f541278e6da0c56545e24bf141c447。
Drive folder18FVyvRFj1_ltpJAWGTiIznsw3UthyPDO；包1CeL3d3oxcA6MP9Myjw3YKMXwIrJyPk3G，38709448bytes/SHA d0299357cb58fb1414b1cdf1046c8e38393dfc37bb8f73acd40746dd55fee564，371檔。
TWSE63/63日行情86674證券日、1384跨日代碼、每日1368～1382；六组價格/報酬/大盤官方類股16959指數日，欄位shape0錯，原selectorALLBUT0999排權證但含ETF。TPEx63/63日667509原表列、15297跨日證券（含大量權證，不可說股票數），全63每table.totalCount==data長度；股別/當期名冊仍未正式核。
TWSE法人63日84031、融資券63日81537、估值原62日67005+7/17補1079=>63日68084。MOPS本外國頁12共5925公司月：上市7/8/9=1087/1087/1073，上櫃892/893/893；9月TWSE發布少2832仍待查。FinMindfree目錄4336、calendar窗口63、TAIEX/TPEx報酬指數各63、整體融資券189/法人378各63日；不混價格與報酬指數。
全取得不是全Golden。前批2330/本批6488各63日期252OHLC值同provider，原始抓取範圍仍整表；未核全市場每值/单位/角色/PIT。主表17候選转换不覆Raw；长期不足INSUFFICIENT_HISTORY，未實算全市场Derived。
TPExfirstglobal.js無constant，保留failedrun；改main.js得到/www/{LANG}/{ACTION}+pricing頁dailyQuotes，GET date yyyy/mm/dd正向控制及63history。首次34日成功、12IncompleteRead/Timeout导致漏/跳过共29日期；31次最多兩attempt補齐29。新driver64KiB讀取保partial/headers/逐日manifest，早期drivererror丟partial已記限制。TWSE估值單日補齐；不再重抓成功日期。
runs/artifacts：38495403325/11863314339；38495873543/11863344923（global無常數）；38496032654/11863846685（34日）；38496201874/11864545844（TWSE3families）；38496726610/11863852763（29日补）；38496923996/11864616637（估值+2FM总表）。六ZIPhash同GitHub digest；本機解析counts/6488對照未cloud replay。349requests=344market+5网页JS；本轮FM6数据calls、无token/付费/帐号，無daily部署。
全需求16族群在full_market_coverage.json；all_required_datasets_complete=false。待補：TPEx官方類股/法人/融資券/估值/借券；全公司三表/EPS/股本市值/董監質押/公司異動/除權息；FinMind逐檔全市場副本；集保持股級距與主力分點（FM官方付費限制，查官方替代）。原四來源不能保证免费包含全部字段，先把能取得項目補齊，缺口不可当0。
FinMindfree未登入300/h、注册600/h；不要并行绕限额。队列当前2767商品仅探索估算，含ETF/停更，不是有效歷史名册，未执行8301项。
下一批先補上述未取Raw，對固定三個月全市場Corpus做欄位/单位/短視窗處理、差異追查與日更复原；不退回少股取樣。主表/14_TestHistory未覆寫需后续统一登錄。Production BLOCKED，興櫃RAW_ONLY，B115934/934、38候選/9OPEN不變。

---

# 最新續接：DAILY-REAL-001 免費來源真實日更小樣本（2026-10-14）

使用者2026-10-14 09:03/09:13明確改優先順序：FinMind免費，先抓四來源三個月真實資料配官方文件與Jarvis表格試跑日更；240日缺資料不擋流程；問題按實際差異查官方。暫緩原B72合成batch，不重啟長歷史PIT工程作為本輪前置。
報告：docs/registry/delivery/wp00/DAILY_REAL_001_FREE_DAILY_UPDATE_PILOT_20261014.md
Drive folder 1v75Y9O00zojFVVlQEZ9khKPr9D3HIq_9；bundle file1YaV4Q05o-dGPYTYcBjYHdSNpGuRj6TRX，18648765bytes，SHAbb8b00049bc9bc53a860f39b979753905c2601bffab9e2653e68ef269f91efec。22raw含3官方API文件，附MOPS既有PDF及離線結果。
run38493865367/job115625064487 success，artifact11863561067；補期run38494358210/artifact11863541652。Actions收集成功非全部資料QA；本機分析未cloud replay。FinMind cloud6資料calls+1doc，local另1price timeout；無token/付費/帳戶；四來源cloud市場19calls，docs3。
2330 TWSE7～9月63日與FinMind重疊252OHLC全同；6488 FinMind另63日。MOPS六selected_0 HTML解析5553列，strictBig5失敗/CP950成功須記fallback。Finminddate7～9實際營收6～8，保留並補date8～10確認report7～9兩股六筆數值倍率×1000全同。日期非公告；currency/PIT未批准。
9月MOPS上市979 vs TWSE1072：978數值同，2832無列（原因未解）；上櫃863 vs TPEx893：863數值同，其他scope93/30非自動判缺漏。TPExcurrentprices1818217bytes JSON截尾HOLD未補括號/採前半截。價格候選1571依主表17欄名，離線重播0新增1571相同0conflict，非跨日schedule。
未抓財報/法人/融資券/集保全資料集或TPEx歷史全市場；未寫主表/14_Test_History，需後續統一登錄；主表version2讀過治理與443metric候選，未批准全部指標。Daily schedule未部署，興櫃RAW_ONLY，Production BLOCKED，B115934/934、38候選/9OPEN不变。
下一批先查TPEx截尾（headers/完整讀取/有限重取）、2832缺席（官方版本scope）、CP950契約，再擴範圍與每日增量/故障復原。固定raw可批次重跑，不再以小輪合成PASS當資料建庫成果。

---

# 最新續接：WP00 B71 row schema guard 30/30

報告：docs/registry/delivery/wp00/WP00_B71_ROW_SCHEMA_GUARD_20261014.md
code4c4dfcc7b1d961477616c1870314baaf22aa1dea；run38492506528/job115620781405 success；artifact11862710459下載JSON位元組及三hash同本機。30新合成例，7局部match/23HOLD，不是60新例。
固定B69 selected SHA17f38e37e952585c02139a88d319994ef68bdf0327be08b3022225800ad89ec9；六required/type與可選create_time。declared/local分開；整數值float符合schema integer但local exactint HOLD；month1–12/year1900–2200為本地防護非官方range。缺create_time不補default；有值不充AvailableAt；不禁止額外欄位/負營收/未格式化string，但局部match非金融資格。
所有資格false，currency/scale/AvailableAt unknown，未接B66/B68/nativeHTTP/Raw/Runtime；nativecontainer仍OPEN，市場/帳戶API0。
下一輪B72合成batch串rowguard，每列錯誤/原列保留，成功列與empty不可掩蓋錯列；不以實驗envelope代官方契約。
B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B70官方helper邊界/schema歧義9/9

報告：docs/registry/delivery/wp00/WP00_B70_NATIVE_SCHEMA_HOLD_AUDIT_20261014.md
codee79a17437abd98a2da9616968536b74d5bf9b6c3；run38491970411/job115619026556 success，下載9JSON/四hash同本機，非18新例。固定providercommit8b42547c1e34f77823dd8d3836c1fc1388bc5678與testblob0ad15d0945b3402fc671365fc3dbd0e2a2b03265，ASThelper無fixture/市場calls。
原helper只exact欄序/nonempty，三反例（month13/revenueNone/stockint）也接受，非provider已返回錯資料/全部tests無驗。五object/null/HTTPerror歧義HOLD，一合成status200array可decode非完整row驗收。官方tests不解決B69container/unit差異，未跑upstreamlive/帳戶tests，未改SDK。
下一輪B69月營收六required/type rowguard與非法年月HOLD，日期角色分離；只schema、不轉unit或批准currency/PIT。nativeenvelope仍OPEN。
市場/帳戶API0，B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY，Runtime未整合。

---

# 最新續接：WP00 B69官方native envelope差異PARTIAL

報告：docs/registry/delivery/wp00/WP00_B69_FINMIND_NATIVE_ENVELOPE_DIVERGENCE_20261014.md
服務端https://api.finmindtrade.com/openapi.json完整93651bytes/SHA80a80baf549c6a3b60f59df757d473a00b64d7d0c977b1e9a8c62aa34550a5bd，保存libfile_7325caf5e1208191ac8f5ec8ed27dc06，hash不變；GitHubYAML blob仍同B27。不同官方文件非同URLdrift。
YAMLmsg/status/data array；服務端schema只列data且required data，anyOf各datasetrow/genericobject/null，与SDK array用法有描述差異，不能斷言真實容器或放寬B66。月營收row有6required/int欄位/create_time default空字串，仍缺unit/currency/dateformat/來源版本。info.version1.1.1非資料snapshot版本，B68LAB標籤不認證server。
官方quota402/ip403 msg/status錯誤無data，不能當成功空；政策4xx先修正/5xx有限退避，未證明429即時或3次是正式政策。
下一輪spec歧異HOLD案例與官方SDKtest/API輸出實作核容器/狀態，未知不猜、unit/currency/PIT仍OPEN。Actions0/正式新測試0/市場帳戶API0，B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B68本機period/version18/18＋B67回歸17/17

報告：docs/registry/delivery/wp00/WP00_B68_PERIOD_VERSION_CONTEXT_VALIDATION_20261014.md
code8ae3c9f2efc70e8ea06a8a0d10a385cadef8fb2f；run38490842545/job115615392261 success，下載兩JSON/四hash同本機。35項含17既有非35/70新例。
3合成通過/15HOLD，LAB_MONTH_REVENUE context綁request/company/dataset/localversion/年月、packet與row年月exacttype一致，跨月或版本錯停止retry、duplicate scope零transport。空array只能說合成明示empty，無row可核月份；LAB版本一致非server認證，server_version_authenticated=false。
B68 exception本輪合併TRANSPORT_NONE，未保B67細分；B67回歸原driver，非B68全分支。未接nativeHTTP/Raw/Runtime。下一輪官方nativeenvelope/sourceversion角色明示、可信取得證據，unknownHOLD，不以自訂label代契約，串接再補exception/scopebytes回歸。
市場/帳戶API0，raw_saved/sourcecontract/eligible/PIT/serverversion=false；B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B67 context/有限attempt17/17＋B66回歸16/16

報告：docs/registry/delivery/wp00/WP00_B67_ATTEMPT_ACCOUNTING_VALIDATION_20261014.md
code2a990329e1d244d0658a2f256a98f7831e072700；run38488499612/job115607846979 success，下載兩JSON/三hash同本機。33項含16既有回歸非33/66新例。
五合成通過/十二HOLD。整批context/type/duplicate/max_attempts守門前置零transport；deepcopy防transport改帳務身份。None/exception/429/502/503/504合成有限最多3attempt、history保留早先失敗，錯公司/JSON/400不重試，另一request成功不能替代。未改B65/B66或provider。
只綁request_id/stock_id，尚未dataset/年月/source版本；無RetryAfter/backoff/timeout/nativeHTTP/asynccancel、history非durablejournal。下一輪dataset/報告期/version綁context、成功列月份匹配，不能跨月/版本重試掩蓋。
市場/帳戶API0、raw_saved/sourcecontract/eligible/PIT=false，B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY，Runtime未整合。

---

# 最新續接：WP00 B66 context/bytes解碼16/16＋B65回歸18/18

報告：docs/registry/delivery/wp00/WP00_B66_RESPONSE_CONTEXT_DECODE_VALIDATION_20261014.md
code0e19017cb19360fd6452f435cfc0ba1dd577234b；run38485874351/job115599271409 success，兩JSON/兩hash同本機，34含18既有回歸非34/68新例。
有效caller context下每request保留None/exception/HTTP/body/JSON失敗item，Response bool拋錯也完成、無依truthiness略過。raw長度/hash只是inmemory非保存；16KiB decoded試驗，msg可選但native契約未驗，wrongcompany經B65整批HOLD。2正常/14HOLD合成。
壞context前置守門未做、attempt固定1非重試；headers/url/time/原bytes正式保存未驗、未接真HTTP或Runtime。下一輪context驗證+multiattempt保留過去失敗/錯request不得替代、官方envelope文件。
市場/帳戶API0、raw_saved/sourcecontract/eligible/PIT=false，B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B65逐請求accounting18/18

報告：docs/registry/delivery/wp00/WP00_B65_BATCH_ACCOUNTING_VALIDATION_20261014.md
code140ad4ae199aa3bacb62db71d3d41cb80d9a25f4；run38480081741/job115580238010 success，下載18項JSON/hash同本機。同18案例兩環境非36新例。
3合成通過/15HOLD。可可靠關聯的descriptor逐request列missing/status/null/wrongstock；亂序對應、明示empty另分類，bool/float/error/duplicate/unknownHOLD。結構性identity错误直接HOLD items空，尚非所有壞descriptor逐項紀錄。合成body僅status/data，非nativeFinMind規格，未修SDK或Runtime，不稱正式修復。
下一輪request context+nativeHTTP回應離線decode串接、每attempt/錯誤保留，勿靠response bool；unit/date/版本契約仍OPEN。
市場/帳戶API0、raw_saved/sourcecontract/eligible/PIT=false，B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B64批次/錯誤稽核9/9（5限制未修）

報告：docs/registry/delivery/wp00/WP00_B64_SDK_ASYNC_ERROR_AUDIT_20261014.md
code25fbcb614cba69c6d9da3f28ea327d8193e6d0f3；run38478178647/job115573980905 success，下載9項JSON及兩hash同本機；同9案例兩環境非18新例。
固定provider commit8b42547c1e34f77823dd8d3836c1fc1388bc5678/hash978b9678071d7dab151d268c3d6d885be2b0aa7559d2527283c0e25e718afff3。AST真聚合方法/fake transport非真asyncexecutor。falsey503略過、response短缺/allNone、JSON錯status有data[]、syncnull->empty五限制重現，未修SDK。不宣稱真實provider會如此回應。
下一輪adapter逐請求identity/status/缺件與整批accounting，null/errorHOLD、明示成功empty另類；先離線控測，sourcecurrency/scale/date/PIT仍OPEN。市場/帳戶API0，Runtime未改；B115934/934、38候選/9OPEN不變、Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B63 SDK同步回應日期9/9

報告：docs/registry/delivery/wp00/WP00_B63_SDK_RESPONSE_DATE_CHAIN_20261014.md
code465708b4582c4639d837259a81cfe45b4e2891c7；成功run38477759531/job115572572923，下載JSON同本機9/9。初次run38477549250 hash失敗（本機副本多結尾LF），未跑案例。B62舊hash是多LF副本非exact LF，此輪更正。provider同commit8b42547c1e34f77823dd8d3836c1fc1388bc5678，exact LF loader185b18d74996fbf6a1a9afba42662b3d80b789c3a0494b0f0ac222d6efe0dc6c、api978b9678071d7dab151d268c3d6d885be2b0aa7559d2527283c0e25e718afff3。
AST真同步methodchain+fake request_get、pandas2.2.3。request bounds移位，fake response date原樣保留；docstringreturned normalized不能當client實測。response date再當報告期確實二次移位，v3只改querykey。不是API實際日期合法性/async/完整初始化。
下一輪REST日期明示/unit證據與async/錯誤回應邊界；currency-scale-null/修訂仍OPEN。市場/帳戶API0，同9案例兩環境非18新例；B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B62 SDK報告期離線6/6

報告：docs/registry/delivery/wp00/WP00_B62_FINMIND_SDK_MONTH_BOUNDS_20261014.md
FinMind/FinMind固定commit8b42547c1e34f77823dd8d3836c1fc1388bc5678、data_loader.py blob2fdaba05bb2b661515a5a5627673d6925cc440b3。CRLF→LF hashdb9cdef7465c645629f6b5fa3d3a035a2dbd40173b1f88d8554ef0da20b1734b。AST真method/get_data Spy/pandas2.2.3，6案例start/end月日期/1M/閏年/跨年送次月1日均PASS。不是API回傳或inclusive實測，未跑完整SDK初始化/Actions。
SDK docstring date非公告，reportingmonth與date分離，不二次位移；不跨套原生REST。MCP固定commiteae5b2a0779a33882e6efbc47ad4ec03265ffdb6月營收文件仍无currency/scale明示。code/results Git保存，provider source只固定ref未repo副本。
下一輪get_data returned date路徑與REST明示對照、官方test/unit字典。來源PARTIAL、新離線6案例但正式source驗收0/API0/Actions0，B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B61官方CSV連結/provider倍率PARTIAL

報告：docs/registry/delivery/wp00/WP00_B61_CSV_LINK_PROVIDER_SCALE_REVIEW_20261014.md
官方目錄CSV link確定https://mopsfin.twse.com.tw/opendata/t187ap05_L.csv與t187ap05_O.csv。兩次點擊回工具Unsupported text/csv，未取得可讀Raw/hash；2CSV讀取嘗試不能報完全無市場資源請求，營收API0/成功Raw0。
FinMind primary dashboard例TaiwanStockMonthRevenue revenue*1e-8標億、年月用revenue_year/month；倍率佐證非完整unit/currency批准，不跨套TWSE/TPEx。create_time入庫日非公告、2026-04-21初始值與更新公告2026-05-22角色分離；全市場會員限制不能当免費方案。FinMindAPI/帳戶0，興櫃RAW_ONLY。
下一輪FinMind官方repo dataset/SDK具體欄位明示unit/currency/date，來源仍OPEN。Actions0/正式新驗收0，B115934/934、38候選/9OPEN不變，Production BLOCKED。

---

# 最新續接：WP00 B60完整申報PDF取得/metadata PARTIAL

報告：docs/registry/delivery/wp00/WP00_B60_FILING_PDF_RESOURCE_METADATA_REVIEW_20261014.md
官方ff80808167ee6fdf0169be45cf9309da.pdf完整19091965bytes/61頁/SHAfeae392ab45b7634e766335665ebafbde473953a6e89a1312da13b1bb849482f，持久保存libfile_e3d1df2f58608191a82f6acdb057bf2b，保存後hash不變。PDF44（印刷43）仟元申報欄位視覺核對；製作metadata2019-03-27非生效/最新版證明；optional content group警告保留，非全册驗收。
data.gov目錄可web讀，但本機兩目錄403、候選metadata API不可讀，精確href/encoding等未核定。第三方CSV/UTF8不代官方。沒有CSV或市場API，不能歷史申報畫面跨接口批准倍率。
下一輪精確官方resource href/MOPS輸出說明；無明示就保留OPEN並轉其他有精確字典候選，避免重讀相同文檔。Actions0/正式新測試0/市場API0；B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B59營收media/schema文件PARTIAL（2026-10-14）

報告：docs/registry/delivery/wp00/WP00_B59_REVENUE_MEDIA_SCHEMA_REVIEW_20261014.md
本機完整取得TWSE309960bytes/TPEx476923bytes，原SHA256均同B34；web TPEx Internal Error不混當本機取得失敗。選定operation/resolvedschema與原hash保存JSON，未另持久保存完整raw。本輪TPEx初次誤用Swagger2 schema解析KeyError，修正OAS3 content/components後成功。
JSON/textcsv兩媒體宣告，14string但required/date参数/format/pattern未列；不當CSV等價、缺欄合法/補零、歷史query支持或原生currency-scale-date批准。媒體同schema仍缺CSV序列化/null/completeness。
下一輪官方dataset resource/detail metadata與MOPS輸出说明；不重跑相同Swagger猜單位，契約OPEN。
Actions0/正式新測試0/市場API0/protocol0，本機文件HTTP2（非全部瀏覽工具HTTP總量）。B115934/934、38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B58月營收申報/更正時間文件PARTIAL

報告：docs/registry/delivery/wp00/WP00_B58_REVENUE_FILING_CORRECTION_TIME_REVIEW_20261013.md
TWSE操作說明69頁歷史申報畫面含仟元線索、非免費JSON等價；2019-03注意事項50頁說明更正訊息/重新開放申報/再申報。選頁截圖2頁取得、注意事項PDF14截圖回HTML不當視覺PASS；無原PDF bytes/hash/Git封存。
官方FL007250頁修正2026-09-30、第3條第1項第5款營業額期限與特殊適用範圍例外，修正日期不直接等實施日/全歷史算法，上櫃現行等價未驗。期限不當AvailableAt；原值與修正值/發布時間應分版本，不能同公司月份直接覆寫。
精確免費currency/scale/date/null/completeness與CSV/JSON明示對照未補足。下一輪官方接口字典/檔案說明與原bytes完整取得，不以示例或申報畫面猜接口。
本輪Actions0/正式新測試0/市場API0/protocol0；B115934/934及38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B57營收歷史口徑文件PARTIAL

報告：docs/registry/delivery/wp00/WP00_B57_REVENUE_HISTORICAL_BASIS_CONTRACT_REVIEW_20261013.md
讀B24與官方目錄18420/56510，14欄維持，精確currency/scale/date/null/completeness未補足。查TWSE event_download_201310111115_04.pdf，封面102年12月，61頁、選定封面/PDF14/15頁截圖核對；未取得原bytes hash或Git原PDF封存，非全冊驗收。
2013IFRS月營收以合併為主、無子公司個別、金融淨收益；比較2012重算，形成歷史口徑/重編版本風險。歷史教材不當2026免費API字典，重編2012數不當2012已知值，需首次發布證據。
下一輪官方月營收申報操作手冊/現行資訊申報規範，找單位/date/修正/首次公布與精確接口明示對照。不用其他公司仟元簡報批准營收API。
本輪文件查核PARTIAL，Actions0/正式新測試0/市場API0/protocol0；B115934/934、38候選/9OPEN不變、Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B56嚴格引擎流程21/21＋JSON回歸19/19

報告：docs/registry/delivery/wp00/WP00_B56_STRICT_PROCESS_ARCHIVE_REPLAY_20261013.md
code commitaa382df22290612ca715648b00ca2be9fb030219；run38421641971/job115380205931 success。下載後兩JSON及五程式hash同本機。40項全既有重播，非40/80新例。
B54的21項改測B55 operation：實際三窗口子程序退出/鎖釋放恢復、錯紀錄HOLD/stage不認領、B43原DOCX185781bytes/hash一致讀回不重寫，同長度壞候選HOLD；DOCXafter_data是注入而非程序終止。B55 JSON19項含3舊B53缺口重現、14HOLD、2正常。
B55嚴格解析與已測恢復鏈相容，Runtime未部署；stage清理/惡意寫權程序競爭/斷電/root登錄未驗。市場API0/protocol0，全raw_saved/storage/eligible/PIT/currentness=false，B115934/934及38候選/9OPEN不變；Production BLOCKED、興櫃RAW_ONLY。
下一輪回官方來源契約，先讀registry選定免費介面的native currency/scale/date/null/completeness精確證據；不以增加合成storage例代替來源資格，原生wire/免費等價待官方依據。

---

# 最新續接：WP00 B55嚴格JSON19/19＋恢復回歸23/23

報告：docs/registry/delivery/wp00/WP00_B55_STRICT_RECEIPT_JSON_VALIDATION_20261013.md
code commit1ccff3be483bd35b64cab04ff46098becb8d3e7d；run38419727142/job115373552153 success。本機/雲端19項＋23項JSON及四hash一致。42項含23既有回歸，非42新例/84。
3原B53缺口重現（float3.0/duplicate state/超16KiB）；14反例嚴格HOLD、2正常REPLAY。B55 exact_types/全object拒重複key/非標準數字/strictUTF8/深度錯誤HOLD；receipt fstat+有界讀取16385bytes，上限16384。回歸是執行B55 operation，包含真實兩程序鎖競爭。獨立prototype、未改B53、schema53正常紀錄相容，未整合Runtime。
下一輪B55嚴格版實際程序退出與官方封存DOCX讀回；再回官方來源契約阻礙，不以增加合成測試替代來源驗收。stage清理/斷電/不協作程序競爭未驗。
市場API0/protocol0，全raw_saved/storage/eligible/PIT/currentness=false，B115934/934及38候選/9OPEN不變；Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B54程序退出21/21＋B53回歸23/23

報告：docs/registry/delivery/wp00/WP00_B54_PROCESS_EXIT_ARCHIVE_VALIDATION_20261013.md
code commit742d0a82f33db46b1d71b082b65b8c93045a2df7；run38418271008/job115368424973 success。本機/雲端21項B54與23項B53 JSON及四hash一致，44執行含23既有回歸，不算44新例或88。
3BUSY/3NEW/6REPLAY/8HOLD/1PENDING。三窗口實際終止自己建立的子程序，核心釋放鎖後恢復；窗口由hook控制，非主機重啟/斷電。錯schema/bool/state/hash/reference/extra HOLD、verified缺data不補建、stage不認領不刪。
B43原DOCX固定commit ff349855f1e0b7d7f0a99582dbf12322c30a12e6封存副本185781bytes/hash一致，描述符pending恢復REPLAY不重寫；同長度壞候選HOLD。不是官方重新抓取/市場樣本。
下一輪嚴格JSON型別/重複key/非標準數字/大小上限稽核與修補；stage清理未實作，不自動刪。B54未改B53、Runtime未部署。
市場API0/protocol0，全raw_saved/storage/eligible/PIT/currentness=false，B115934/934及38候選/9OPEN不變；Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B53原子描述符紀錄23/23＋B52回歸19/19

報告：docs/registry/delivery/wp00/WP00_B53_ATOMIC_DESCRIPTOR_RECOVERY_20261013.md
code commitc780b16a468ea999ad16159bf5ac17b8efbfbf76；run38417126859/job115364422019 success。下載artifact後23項B53/19項B52 JSON及三程式hash與本機一致；42執行中19既有回歸，不算42新例或84兩環境新例。
3NEW/6REPLAY/5PENDING/8HOLD/1BUSY。固定key/no-follow/dir_fd、schema53先原子發布WRITE_PENDING，再data讀回hash與原子VERIFIED；5注入窗口恢復。真實兩程序同key BUSY/釋放/重跑不覆寫。partial及無receipt孤立data HOLD，null receipt與symlink/hardlink拒絕。
合成abc，故障是注入例外而非kill/重啟/斷電。未改B50/B52、未整合Runtime。單檔原子非跨檔transaction；有目錄寫權不協作程序的check/replace競爭等未驗。市場API0/protocol0，全raw_saved/storage/eligible/PIT/currentness=false；B115934/934及38候選/9OPEN不變、Production BLOCKED、興櫃RAW_ONLY。
下一輪實際程序退出後pending恢復、schema/未知state/殘留stage，封存官方bytes描述符讀回；正式source wire/currency/scale/date仍待證據。

---

# 最新續接：WP00 B52固定鍵與descriptor原型19/19

報告：docs/registry/delivery/wp00/WP00_B52_DESCRIPTOR_STORE_VALIDATION_20261013.md
code commitf9ca192a3eff1daad73ce3c08392a1730afc143d；run38415242988/job115357831202 success。本機/雲端同19案例JSON與B52/B48 hash一致，非38新案例。3NEW/1REPLAY/13HOLD/1BUSY/1PENDING。
固定anchor鍵、逐component no-follow目錄fd、相對開檔fstat regular/nlink1擋symlink/hardlink；root改名替換後仍寫原fd目錄。獨立原型未改B50，schema52不遷移；同程序hook flock重入BUSY非兩程序測試。中斷孤立data HOLD不認領；receipt直接exclusive建立尚非完整後原子發布。惡意有目錄寫權程序的inode替換/增hardlink競爭未驗，斷電未驗。
下一輪descriptor-relative receipt原子發布/pending恢復及兩程序；不能直接當正式store驗收。
市場API0/protocol0、Runtime未整合，全raw_saved/storage/eligible/PIT/currentness=false；B115934/934及38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B51路徑別名稽核10/10（限制尚未修復）

報告：docs/registry/delivery/wp00/WP00_B51_PATH_ALIAS_BOUNDARY_AUDIT_20261013.md
code commit4c21c2de84e466fe3d1334df700487839bd8d268；run38412888303/job115349547967 success。下载artifact完整10項JSON及B51/B50/B48 hash與本機一致。同10案例兩環境非20新案例。
6限制成功重現：不同receipt使用不同lock key；data/receipt/lock/父目錄symlink與data硬連結未拒絕。10/10是稽核重現不是缺口修復；B50程式未改。既有data不覆寫及獨立hash重驗仍有效。不同key交錯由同程序hook實際flock重入，非兩平行程序；symlink/hardlink均實際自建臨時檔。
下一輪固定anchor唯一data/receipt/lock key及descriptor/no-follow守門；不可用單純lstat前置檢查宣稱TOCTOU已解決。
市場API0/protocol0，無新官方文件或市場資料，正式Runtime未整合。raw_saved/storage/eligible/PIT/currentness=false，B115934/934及38候選/9OPEN不變；Production BLOCKED、興櫃RAW_ONLY。

---

# 最新續接：WP00 B50原子紀錄與協作鎖24/24

報告：docs/registry/delivery/wp00/WP00_B50_ATOMIC_RECEIPT_LOCK_VALIDATION_20261013.md
code commit c8bc903e66b8a70ae0c7eedb009e2cf9915bc30d，run38408383117/job115333904723 success。雲端與本機完整24項JSON及兩程式SHA256一致，同案例兩環境不算48新案例。
4NEW/7REPLAY/4PENDING/8HOLD/1BUSY；schema2同目錄暫存/fsync/replace/父目錄fsync；既有verified仍hash重驗。實際兩程序競爭BUSY、重跑不覆寫及自己建立的程序退出釋放鎖通過。其他故障窗口是注入，斷電/OS重啟耐久性未驗；跨檔非原子、schema1不自動升級。
同lock key協作限制，路徑別名/不同receipt key/symlink尚待下一輪。TemporaryDirectory非正式倉庫，市場API0/protocol0；全raw_saved/production_storage/eligible/PIT/currentness=false，Production BLOCKED、興櫃RAW_ONLY。B115934/934及38候選/9OPEN不變。
下一步固定資料/紀錄鍵與路徑別名邊界；原生wire及免費currency/scale/date契約仍待正式來源證據。

---

# 最新續接：WP00 B49回復紀錄與安全重跑25/25

報告：docs/registry/delivery/wp00/WP00_B49_RECOVERY_RECEIPT_REPLAY_VALIDATION_20261013.md
程式scripts/experimental/wp00_b49_recovery_receipts.py，固定commit8331974d82c8388fb788f03deeb9dadf018bf317；B48依賴hash固定。
run38401761003/job115310885248 success，雲端25項JSON與兩程式hash同本機。同25案例兩環境非50新案例。
2新保存驗證/5既有資料重驗不重寫/1Pending/17HOLD反例；用inode/mtime/size/hash及寫入計數交叉查replay data無改動。
有receipt的I/O或Pending可重驗恢復；無receipt孤立data維持HOLD，不认領/覆寫/刪除；已verified標籤仍需hash重驗。錯版本/path/anchor/schema及損壞都擋下。
中斷均注入、同程序重入，非OS重啟/斷電/真實服務故障；TemporaryDirectory不是正式倉庫。receipt更新非原子，併發/fsync尚未驗。
市場API0/protocol0；B115934/934與38候選/9OPEN不變。全raw_saved/production_storage/eligible/PIT/currentness=false，Production BLOCKED、興櫃RAW_ONLY。
下一步receipt原子更新、兩寫入者競爭/故障窗口；正式原生wire/免費currency-scale-date契約仍待來源證據。

---

# 最新續接：WP00 B48獨立anchor與讀回24/24

報告：docs/registry/delivery/wp00/WP00_B48_INDEPENDENT_ANCHOR_READBACK_VALIDATION_20261013.md
程式scripts/experimental/wp00_b48_anchor_readback.py，固定commit07e8d45c40cd34d83fd898e3d309abf8b64e47be。run38398644472/job115300242228 success；雲端24項JSON與程式hash同本機。
20反例HOLD、2預期bytes比對/2臨時寫入讀回成功；同24案例兩環境不算48新案例。獨立事前anchor可擋B47同長度改動，候選hash/sidecar不得替換預期值。
真實B43原DOCX指定commit ff349855f1e0b7d7f0a99582dbf12322c30a12e6讀回185781bytes/hashfd573c117099f042d9892a5e32fde4b8d196f4496186da545f360ed41142e94b一致；是舊封存文件，非本輪重抓最新市場數據。
TemporaryDirectory讀回不是正式Raw store；全部raw_saved/production_storage/eligible/PIT/currentness=false。來源reference信任需另有實際取得證據，hash一致不證明單位或資料真實性。
市場API0/protocol0，B115934/934及38候選/9OPEN不變，Production BLOCKED、興櫃RAW_ONLY。
下一步保存後讀回中斷的恢復/重跑不覆寫與版本參照一致性；原生wire/免費currency-scale-date契約仍須正式文件證據。

---

# 最新續接：WP00 B47合成ASCII byte鏈31/31

報告：docs/registry/delivery/wp00/WP00_B47_LAB_BYTE_FRAME_CHAIN_VALIDATION_20261013.md
程式scripts/experimental/wp00_b47_lab_byte_frames.py，固定commit4100bf6ef5e5925ce7c860ccdc66ba8b19f0131a，B46依賴hash強制核對。
run38393730224/job115283589383 success；雲端artifact下載後31項JSON及兩程式hash同本機。4正常byte鏈、26HOLD反例、1同長度改動限制示範，31/31；不算62新案例。
ASCII編碼/一bytes物件一frame/26byteheader等為實驗假設，非原生wire/TCP批准；raw F060未支持則HOLD。opaque DATA不解碼、保留FF/00/FE/CR/LF。每案native_wire/eligible/PIT=false、raw_saved=false。
同長度payload改動能通過長度/EOF但hash變化；不得宣稱內容正確性已驗收。
市場API0/protocol0/B115934/934不變，38候選/9OPEN維持，Production BLOCKED、興櫃RAW_ONLY。
下一步獨立預期hash與保存讀回反例控測，補同長度內容改動缺口；原生編碼/frame/免費currency-scale-date契約仍須來源證據。

---

# 最新續接：WP00 B46離線傳輸描述控制22/22

報告：docs/registry/delivery/wp00/WP00_B46_OFFLINE_TRANSFER_DESCRIPTOR_CONTROLS_20261013.md
程式scripts/experimental/wp00_b46_transport_guard.py，固定commit ed9a68acf0baf67d295f1203fec6d4c503021bc8。run38391874164/job115277384230 success；雲端artifact下載後程式hash/22項結果與本機逐項一致。
3正常合成byte重組hash一致，17反例HOLD，14未就緒與17明示空檔各1分類通過；同22案例兩環境重播，不算44新案例。
這是已解碼描述欄位/序列檢查，非原始wire parser/市場來源/真實protocol或Runtime。F06014/17為合成分類，未驗实际線上空檔編碼。全案例eligible/PIT false、raw_saved false、Production BLOCKED。
市場API0/protocol0，B115934/934不加計，38候選/9OPEN維持，興櫃RAW_ONLY。
下一步原始byte frame與descriptor串接反例，未知/重複/亂序/壞輸入安全HOLD；繼續補免費來源native currency/scale/date契約。

---

# 最新續接：WP00 B45共用傳輸完整性文件

報告：docs/registry/delivery/wp00/WP00_B45_HOST_TRANSPORT_COMPLETENESS_REVIEW_20261013.md
run38386587822官方主機連線DOC完整2330112bytes/hash6528d9231052acb14a5a8a91e4a2060a57415597ddf0da0c854804c104211275；原bytes持久保存後hash不變。V1.3/2026-03-12修改/2026-06-15R1/R2/R6實施。
完整NotoTC字型下7個相關PDF頁（3/99/115/117/126/128/129）視覺核對；非全冊/市場驗收。
FILE-SIZE為byte、EOF1末筆；14未就緒、17來源明示空檔、12長度不符。TPEX→券商F090/F110與券商回覆F100/F120；反向F010等不混用。T32資料日期/缺列預設/免費API等價仍未核定；17不當1000股/TWD證明。
市場API0/protocol0/B115934/934不變，38候選/9OPEN維持，Production BLOCKED、興櫃RAW_ONLY。
下一步依官方byte/EOF/status做隔離離線反例控測（合成非市場），並補免費来源native currency/scale/date字典，不能以傳輸控制提升來源或PIT資格。

---

# 最新續接：WP00 B44新版中文視覺與T32傳輸邊界

報告：docs/registry/delivery/wp00/WP00_B44_CHINESE_VISUAL_TRANSPORT_BOUNDARY_20261013.md
Run38385579214字型準備成功；本機共用NotoTC字型修复中文渲染，PDF頁6/8/24/47/48（印刷5/7/23/46/47）選定頁視覺核對PASS，非全手冊。原DOCXhash不變。6/6本機文件/視覺控制PASS，不增加市場驗收。
T32屬broker報表檔案傳輸；F050列券商ID/T30/T31/T32，不代表免費OpenAPI等價。T32四欄无日期，MESSAGE-TIME不回填歷史有效日期；缺列不補1000股/TWD，其他檔案T42/T49/T78規則不跨檔套用。
38候選/9OPEN/B115934/934不變，市場API0、Production BLOCKED、興櫃RAW_ONLY。
下一步查官方共用檔案傳輸/主機連線文件及免費接口精確date/completeness/currency/scale契約，再判斷正式parser/pilot。

---

# 最新續接：WP00 B43官方目錄V6.3與T32版本比對

報告：docs/registry/delivery/wp00/WP00_B43_CURRENT_MANUAL_T32_VERSION_REVIEW_20261013.md
兩次Actions run38384506959/38384667051成功，9次官方文件HTTP（市場API0）；完整DOCX185781bytes/hash fd573c117099f042d9892a5e32fde4b8d196f4496186da545f360ed41142e94b，原bytes base64已Git封存並指定commit讀回一致。
目錄更新2026-09-21，文件末列V6.3；T32四欄/50bytes/非外幣非千股幣別空白註解與2023一致，本機10/10離線文件結構檢查PASS，非市場/parser測試。
V6.3 T78修改預定2026-11-09生效，今天不可提前套用；不同章節生效日分離。新版DOCX渲染缺中文字型，中文視覺验收未通過；原XML語意核對不當視覺PASS。免費OpenAPI等價/缺列/日期契約未批准。
38候選/9OPEN/B115934/934不變，Production BLOCKED、興櫃RAW_ONLY。
下一步補字型重做新版相關頁視覺核對，完成T32傳輸/日期/缺列與選定免費來源幣別單位精確等價證據。

---

# 最新續接：WP00 B41重跑官方T32完整取得

報告：docs/registry/delivery/wp00/WP00_B41_RERUN_T32_DOCUMENT_RETRIEVED_20261013.md
Run38382590315/job115246423859 success；官方PDF740683/740683bytes、39頁，原始SHA256606c2b8074ef7a53741de80179a1635a57cf49ff725c6eac695391d8b8def5e7；artifact下載後原hash一致，PDF9/10頁（印刷40/41）視覺核對完成。
T32字段及註2確認：非外幣計價的其他非千股證券幣別欄空白；不泛化所有空白=TWD，不以缺列推1000股/TWD。文件取得及局部視覺查核PASS，現行版本/免費接口等價/實際T32/parser未核准。保留原B41失敗及B42文件複核歷史。
市場API0；B115934/934未重跑、38候選/9OPEN維持、Production BLOCKED、興櫃RAW_ONLY。
下一步核對官方附件現行版本及選定接口等價、缺列語義；再設計parser。

---

# 最新續接：WP00 B42 MOPS營收目錄契約複核

報告：docs/registry/delivery/wp00/WP00_B42_MOPS_CATALOG_CONTRACT_RECHECK_20261013.md
報告commit：29482446645dc22f272b989b5cd8c170e48f4f2c（指定commit讀回一致）。
接續B41，重新讀上市/上櫃官方營收目錄；14欄及更新頻率與B24一致，尚無精確幣別/倍率/年月語法/合併口徑/修訂可用時間證據。文件查核PARTIAL，QA NOT_RUN、正式新檢查0、市場API0；B115 934/934未重跑、38候選/9OPEN不變、Production BLOCKED、興櫃RAW_ONLY。
下一步讀既有MOPS/XBRL taxonomy/linkbase之context/unit/ownership/dimension依據，尋找精確接口字典；T32仍待可完整讀取官方檔，未批准source/parser/pilot。本輪無Actions執行。

---

# 最新續接：WP00 B41 T32讀取阻礙

報告：docs/registry/delivery/wp00/WP00_B41_T32_RETRIEVAL_IDENTITY_BOUNDARY_20261013.md
事件：WP00-B41-20261013-T32-RETRIEVAL-IDENTITY
T32完整官方文件未取得：2截斷+1逾時，目錄502；web初次局部T30後續403，無PDF視覺驗證。T32 offset僅搜尋候選未批准；S26空白=TWD不得跨檔套用，缺列不代表1000股/TWD。局部歷史T30文字說明產業欄不證明普通股身分。市場API0，B115934/934、38候選、9OPEN不變，Production BLOCKED；興櫃RAW_ONLY。
下一步：Resume independent MOPS unit/date/reporting-basis blockers; revisit T32 only with a working complete official document link; no source or pilot approval。

---

# 最新續接：WP00 B40 EDIS日行情/幣別/特殊值

報告：docs/registry/delivery/wp00/WP00_B40_TPEX_EDIS_DAILY_CURRENCY_SENTINEL_REVIEW_20261013.md
事件：WP00-B40-20261013-TPEX-EDIS-DAILY-CURRENCY
S26交易幣別空白=TWD僅該格式；halt空白含恢復及未停無法分辨，非權證settlement0非股票close。S37/S38多商品非普通股universe；S38含盤後/S37session不完整；S37volume-unit空白、header X164/197矛盾保留。T32只讀到字典指引。市场API0，B115934/934、38候選、9OPEN不變，Production BLOCKED；興櫃RAW_ONLY。
下一步：Resolve free OpenAPI session/null/currency contracts, T32 full dictionary and EDIS header inconsistencies before approving any parser or market pilot。

---

# 最新續接：WP00 B39 EDIS格式原生單位

報告：docs/registry/delivery/wp00/WP00_B39_TPEX_EDIS_UNIT_SECTOR_REVIEW_20261013.md
事件：WP00-B39-20261013-TPEX-EDIS-UNIT-SECTOR
完整PDF2285876bytes/SHA已記；封面1.33/2025-10-20，metadata1.32保留，不稱2026最新版。選讀153頁中的相關章節，視覺核對PDF10/11/15/153。S01股/元、S02仟股/萬元、S07週行情仟股/仟元，股本為股；附錄31native碼含80管理股票。非OpenAPI等價、非實際資料測試。市場API0，B115934/934、38候選、9OPEN不變；Production BLOCKED，興櫃RAW_ONLY。
下一步：Verify current EDIS version/session/currency/null contracts and exact free OpenAPI equivalence; retain per-file scales and versioned industry intervals。

---

# 最新續接：WP00 B38 上櫃類股生效日

報告：docs/registry/delivery/wp00/WP00_B38_TPEX_SECTOR_EFFECTIVE_DATE_REVIEW_20261013.md
事件：WP00-B38-20261013-TPEX-SECTOR-EFFECTIVE-DOC
兩官方靜態公告標準HTTP200，13家公司2026-05-19公告/2026-06-01生效，非完整歷史區間或數值代碼批准。B37的5.4l為歷史文件；較新目錄版本僅搜尋線索，目錄HTTP404/web403保留。市場API0，B115934/934、38候選、9OPEN組不變，Production BLOCKED、興櫃RAW_ONLY。
下一步：Obtain current TPEx protocol and exact OpenAPI sector/date/currency dictionaries; build versioned industry intervals without current-snapshot historical overwrite。

---

# 最新續接：WP00 B37 TPEx IP格式範圍

報告：docs/registry/delivery/wp00/WP00_B37_TPEX_IP_FORMAT_SCOPE_REVIEW_20261013.md
事件：WP00-B37-20261013-TPEX-IP-FORMAT-SCOPE
官方規格書5.4l/2025-05-13選讀；E04成交量股、金額元/幣別另列、首日興櫃參考/前日均價0。類股表屬興櫃，不可套上櫃OpenAPI。興櫃RAW_ONLY，市場API0，B115934/934、38候選、9OPEN組不變，Production BLOCKED。下一步：查當前上櫃類股/date/currency精確字典及歷史效期。

---

# 最新續接：WP00 B36 TPEx參考價及生效依據

報告：docs/registry/delivery/wp00/WP00_B36_TPEX_RULE57_EFFECTIVE_NOTICE_REVIEW_20261013.md
事件：WP00-B36-20261013-RULE57-EFFECTIVE-DOC
第57條缺價參考順序已讀；2025-10-27公告及同日生效確認B35指數修改。非實際OHLC/歷史全版本批准。市場API0、B115934/934與38候選不變、Production BLOCKED，興櫃RAW_ONLY。使用者正詢問模型額度，無法查看其帳戶倒數；下次續接完成來源原生單位/日期契約。

---

# 最新續接：WP00 B35 TPEx官方方法/公司行動

報告：docs/registry/delivery/wp00/WP00_B35_TPEX_METHOD_ACTION_DOCUMENT_REVIEW_20261013.md
事件：WP00-B35-20261013-TPEX-METHOD-ACTION-DOC
3官方URL標準HTTP200，先前web403歷史保留；讀method4頁和兩說明頁，無市場API/JS報表請求。上櫃新掛牌第6交易日、類股新增20家/停編5家等已記，歷史生效/ratio/Rule57仍待確定。B115934/934與38候選不變、Production BLOCKED、興櫃RAW_ONLY。下一步：Review TPEx businessrule57 prior-price fallback, official method-effective notice and native share-ratio/currency fields before source contract approval。

---

# 最新續接：WP00 B34 官方Swagger漂移比對

報告：docs/registry/delivery/wp00/WP00_B34_OFFICIAL_SWAGGER_DRIFT_REVIEW_20261013.md
事件：WP00-B34-20261013-SWAGGER-DRIFT
重新讀2官方文件，TWSE143/TPEx225路徑及規範化全文結構一致，0新增刪除/定義改動；非全功能/市場驗收。缺單位/date/null/session仍待官方精確字典。市場API0、B115934/934與38候選不變、Production BLOCKED、興櫃RAW_ONLY。下一步：Obtain detailed primary field dictionaries for unit/date/null/session definitions missing from unchanged Swagger; source document gate remainsblocked。

---

# 最新續接：WP00 B33 股票scope離線串接

報告：docs/registry/delivery/wp00/WP00_B33_OFFLINE_SCOPE_CHAIN_VALIDATION_20261013.md
事件：WP00-B33-20261013-OFFLINE-SCOPE-CHAIN
10/10合成案例：興櫃/ETFRAW_ONLY、identity未知QUARANTINE、停牌/暖機HOLD，不進金額轉換。preserve_raw為旗標非實際保存驗收；未驗轉板歷史也未整合LegacyRuntime。市場API0、B115934/934與38候選不變、Production BLOCKED。下一步：Resolve exact source unit/date/scope contracts; validate actual issuer historical identity, warmup and storage after approved minimum pilot。

---

# 最新續接：WP00 B32 離線契約串接

報告：docs/registry/delivery/wp00/WP00_B32_OFFLINE_CONTRACT_CHAIN_VALIDATION_20261013.md
事件：WP00-B32-20261013-OFFLINE-CONTRACT-CHAIN
B26+B29+B31離線鏈8/8合成案例，真實38registry在文件階段阻擋；假signoff不是正式核准。未接正式Runtime/Actions、市場API0、source新增0、B115934/934不變、Production BLOCKED、興櫃RAW_ONLY。下一步：Complete exact source date/unit/scope contracts; offline chain is ready for future approved pilot integration but source gate remainsblocked。

---

# 最新續接：WP00 B31 金額呈現離線邊界

報告：docs/registry/delivery/wp00/WP00_B31_AMOUNT_DISPLAY_BOUNDARY_VALIDATION_20261013.md
事件：WP00-B31-20261013-AMOUNT-DISPLAY
純函數18/18假案例，確認TWD元/千元且flagboolTrue才轉億元，未知幣别/倍率/EPS等HOLD。精度保留；caller核定不自動驗文件。未整合runtime、未換算任何市場數據。市場API0、正式新增0、B115934/934與38候選不變、Production BLOCKED、興櫃RAW_ONLY。下一步：Complete exact source date/currency/scale/null/scope contracts before approved pilot; then integrate accounting and amount display with source adapters。

---

# 最新續接：WP00 B30 文件證據讀回

報告：docs/registry/delivery/wp00/WP00_B30_EVIDENCE_REFERENCE_READBACK_20261013.md
事件：WP00-B30-20261013-EVIDENCE-READBACK
38候選紀錄的42個唯一文件頂層參照42可讀0失效；非遞迴/外部URL/語意驗收。各blob保存，不宣称同commit snapshot或原來源SHA256。正式新增驗收0、市場API0、B115934/934不變、Production BLOCKED、興櫃RAW_ONLY。下一步：Resolve exact native date/currency/scale/session contract blockers with more detailed primary specifications; evidence paths readable but no source gate approval。

---

# 最新續接：WP00 B29 回應與批次完整性

報告：docs/registry/delivery/wp00/WP00_B29_RESPONSE_ACCOUNTING_VALIDATION_20261013.md
事件：WP00-B29-20261013-RESPONSE-ACCOUNTING
新增離線helper：錯誤/缺件/重複HOLD，空data不當0；12/12假案例，非市場驗收。尚未Runtime整合，B115934/934與38候選不變，市場API0、Production BLOCKED，興櫃RAW_ONLY。下一步補官方精確單位/日期契約再整合批准試跑。

---

# 最新續接：WP00 B28 SDK錯誤/批次完整性

報告：docs/registry/delivery/wp00/WP00_B28_FINMIND_SDK_ERROR_BOUNDARY_REVIEW_20261013.md
事件：WP00-B28-20261013-SDK-ERROR-BOUNDARY
request_get假Session5/5重現：402/403/504可返回falseyResponse，傳輸全失敗None；必須顯式查status。async靜態路徑有略過失敗task風險，未跑實際async。僅離線測試非來源驗收，Runtime整合未做。B115934/934與38候選不變、市場/帳戶API0、Production BLOCKED、興櫃RAW_ONLY。下一步：Complete per-request completeness/error contract and exact date/unit definitions; do not count SDK surviving DataFrame rows as all-batch success。

---

# 最新續接：WP00 B27 FinMindOpenAPI外層

報告：docs/registry/delivery/wp00/WP00_B27_FINMIND_OPENAPI_ENVELOPE_REVIEW_20261013.md
事件：WP00-B27-20261013-FINMIND-OAS-DOC
OAS msg/status/data.array與402已讀共同文件；Bearer/tokenless及日期可選語意需釐清，泛用items.object非營收unit批准。14既有FinMind候選補文件参照，38閘門未變。市場/帳戶API0，B115934/934不變，Production BLOCKED，興櫃RAW_ONLY。下一步：Resolve exact FinMind auth/date semantics and dataset-specific native revenue units; complete transport/error/completeness topic evidence without market probes。

---

# 最新續接：WP00 B26 離線文件就緒檢查

報告：docs/registry/delivery/wp00/WP00_B26_OFFLINE_DOC_READINESS_VALIDATION_20261013.md
事件：WP00-B26-20261013-OFFLINE-DOC-READINESS
新增read-only checker，38候選BLOCKED、10/10離線案例，非市場驗收；1064診斷是狀態/新证據宣告項，非1064測試。尚未接GitHub Actions/抓取入口。B115934/934不變、市場API0、Production BLOCKED、興櫃RAW_ONLY。下一步：Complete exact date/currency/scale contracts and per-topic document evidence; integrate offline readiness into future sample entrypoint only after reviewed document closure。

---

# 最新續接：WP00 B25 營收紀錄同步修正

報告：docs/registry/delivery/wp00/WP00_B25_REVENUE_MAPPING_CONSISTENCY_20261013.md
事件：WP00-B25-20261013-MAPPING-CONSISTENCY
已同步59列總表/21列財務矩陣與B24原始需求的六個營收字段。registry一致性5/5，不增加正式source checks；B115934/934不變。精確日期語法/幣別倍率未取得官方契約，38候選9組OPEN，市場API0、Production BLOCKED、興櫃RAW_ONLY。下一步：Resolve authoritative selected-endpoint revenue date/unit grammar; keep unknown contracts explicitly blocked instead of repetitive live tests。

---

# 最新續接：WP00 B24 精確營收接口/日期

報告：docs/registry/delivery/wp00/WP00_B24_REVENUE_ENDPOINT_PERIOD_MAPPING_20261013.md
事件：WP00-B24-20261013-REVENUE-ENDPOINT-DOC
上櫃API /mopsfin_t187ap05_O，t187ap05_O維持CSV/registry alias；興櫃 /t187ap05_R不抓取分析。14string字段資料年月與出表日期分開，曆制/幣別倍率仍未確認。38閘門，B115934/934不變，市場API0、Production BLOCKED。下一步：Resolve selected revenue CSV/JSON native currency/scale/date grammar and revision contract; do not infer from sample values。

---

# 最新續接：WP00 B23 營收申報單位與例外

報告：docs/registry/delivery/wp00/WP00_B23_REVENUE_FILING_UNIT_SCHEDULE_REVIEW_20261013.md
事件：WP00-B23-20261013-REVENUE-FILING-DOC
旧申報表單仟元僅文件證據，非現行CSV/JSON倍率核准。上市10日期限有特殊例外；2026保險相關條件可延15日，第二上市櫃可免每月營運申報；逐公司資格未验证。38候選、B115934/934不變，市場API0、Production BLOCKED；興櫃RAW_ONLY。下一步：Complete exact public CSV/JSON revenue currency/scale/period contracts and issuer filing-obligation/exception date mapping; keep SOURCE_DOC_GATE and numerical probes blocked。

---

# 最新續接：WP00 B22 原生單位與估算角色

報告：docs/registry/delivery/wp00/WP00_B22_NATIVE_UNIT_BOUNDARY_REVIEW_20261013.md
事件：WP00-B22-20261013-NATIVE-UNIT-DOC
融資買進/餘額相關章節張的證據僅PARTIAL，不推整表或融券。成本線/維持率是provider estimate，不加入首版Raw。營收原生幣別倍率仍PENDING。38候選、B115934/934不變，市場API0、Production BLOCKED；興櫃RAW_ONLY。下一步：Review MOPS official revenue reporting/export definitions for exact native currency/scale and selected endpoint equivalence; keep per-field margin/short-sale conversion incomplete。

---

# 最新續接：WP00 B21 部分類股代碼與版本

報告：docs/registry/delivery/wp00/WP00_B21_SECTOR_CODE_CHANGE_REVIEW_20261013.md
事件：WP00-B21-20261013-SECTOR-CODE-DOC
TWSE2023-05-30公告：2023-07-03生效35–38與16改名、各指數代號；5文件映射不是5測試，不是完整33類。TPEx完整dictionary403、公司分類歷史未核准。市場API0、B115934/934與38候選未變、Production BLOCKED，興櫃RAW_ONLY。下一步：Close selected D02/D03/D04 native units and format contracts using precise endpoint documentation; keep full dictionaries and issuer historical intervals HOLD。

---

# 最新續接：WP00 B20 類股/指數與缺口收斂

報告：docs/registry/delivery/wp00/WP00_B20_SECTOR_INDEX_CLOSURE_REVIEW_20261013.md
事件：WP00-B20-20261013-SECTOR-INDEX-CLOSURE
TWSE分類33類與舊mopsfin31分類版本分開；TAIEX成分規則非交易Universe。原生dictionary/歷史生效仍待確認，TPEx方法403。9組結案工作集中於：docs/registry/delivery/wp00/source_doc_minimum_closure_tasks_20261013.json。59需求列/6輔助契約/38候選閘門，不是已完成驗收。市場API0、B115934/934不變，Production BLOCKED；興櫃RAW_ONLY。下一步：Resolve first-release exact industry-code dictionaries and source/market native-unit contracts; attach per-topic closure evidence, retain inaccessible-source HOLD。

---

# 最新續接：WP00 B19 上櫃參考價分支

報告：docs/registry/delivery/wp00/WP00_B19_TPEX_REFERENCE_FORMULA_REVIEW_20261013.md
事件：WP00-B19-20261013-TPEX-REFERENCE-DOC
TPExFAQ成功讀A/B公式與現增分支，減資專頁403未結案；原生倍率與tick/Historical仍HOLD。38候選閘門、B115934/934不變，市場API0、Production BLOCKED。興櫃RAW_ONLY。下一步：Review full benchmark/industry methodology and code dictionaries; consolidate D01-D09 minimum contract closure tasks while keeping inaccessible TPEx reduction and native ratio mappings HOLD。

---

# 最新續接：WP00 B18 公司行動倍率與日期

報告：docs/registry/delivery/wp00/WP00_B18_CORPORATE_ACTION_RATIO_REVIEW_20261013.md
事件：WP00-B18-20261013-ACTION-RATIO-DOC
5新候選後共38個未完成文件閘門。FinMind分類float/文字衝突、參考價vs成交價未確認；股數比例r=new/old只作契約草稿不批准EPS還原。市場API0、B115934/934維持、Production BLOCKED；興櫃RAW_ONLY。下一步：Resolve official cash-distribution/share-exchange native scales and TPEx event formulas; preserve FinMind category/reference-price conflicts and pending historical industry intervals。

---

# 最新續接：WP00 B17 公司行動與benchmark契約

報告：docs/registry/delivery/wp00/WP00_B17_ACTION_BENCHMARK_CONTRACT_REVIEW_20261013.md
事件：WP00-B17-20261013-ACTION-BENCHMARK-DOC
8新候選、總33閘門皆未完成；非8測試。TPEx CashDividend息值與CashDivdend現金股利分開；Capitals發行仟股數不是資本額。價格/報酬指數口徑分開。市場API0，B115934/934不變，Production BLOCKED，興櫃RAW_ONLY。下一步：Review company-action native ratios/capital refunds/splits/par-value and complete benchmark methodology/industry dictionaries before source-contract approval。

---

# 最新續接：WP00 B16 首版59項映射檢討

報告：docs/registry/delivery/wp00/WP00_B16_FIRST_RELEASE_MAPPING_AUDIT_20261013.md
事件：WP00-B16-20261013-FIRST-RELEASE-MAPPING
59/59盤點列、0重複、0批准來源契約；另列6輔助契約群，不是65項完成。市場API0，B115934/934維持、Production BLOCKED。一個月試跑不代替241交易日/24月/8季暖機。興櫃RAW_ONLY。下一步：Resolve D06 corporate-action and D07 benchmark/sector exact dataset contracts, then update all59 selectors; keep existing D01-D05/D08 gaps explicit。

---

# 最新續接：WP00 B15 來源使用與接口審查

報告：docs/registry/delivery/wp00/WP00_B15_SOURCE_ACCESS_TRANSPORT_REVIEW_20261013.md
事件：WP00-B15-20261013-SOURCE-ACCESS-DOC
本批市場及帳戶API皆0，驗收測試0；B115934/934不變、Production BLOCKED。限流/錯誤/授權規則僅文件草稿尚未Runtime整合；FinMind權限與超額錯誤不得無限重試，壓测不是配額。興櫃RAW_ONLY不變。下一步：Complete D09 first-release59 requirement mapping with mandatory/deferred/N_A decisions, exact native type/unit/date contracts and consolidated unresolved blockers; no market/account probes before SOURCE_DOC_GATE_PASS。

---

# 最新續接：WP00 B14 免費價量欄位對照

報告：docs/registry/delivery/wp00/WP00_B14_FREE_QUOTE_MATRIX_20261013.md
事件：WP00-B14-20261013-FREE-QUOTE-MATRIX
本批市場資料API 0、驗收測試0；文件閘門未通過。B115 934/934 未變，Production BLOCKED。上櫃行情包含ETF/ETN，須先判定普通股；興櫃只保存不分析。下一步：Review D08 official authentication/limits/terms/transport and complete D09 first-release mapping; keep unresolved free quote scope/currency/null contracts explicit HOLD until primary evidence。

---

# 最新接續：WP00-B13（2026-10-13，PARTIAL）

核對官方A05商品14:00/15:30/17:30交易範圍，115/8/31生效格式與legacy index停用/原幣匯總差異；沒有將付費格式當免費API契約。B115數值相等但scope宣告不同HOLD不解除。Word原文hash與格式事實已保存；render中文缺字，中文notes採OOXML核對，不宣稱全文視覺通過。

報告：docs/registry/delivery/wp00/WP00_B13_QUOTE_SCOPE_FORMAT_REVIEW_20261013.md。來源資料API0、新Actions0，B115/934不變，25候選dataset未結案、興櫃RAW_ONLY、Production BLOCKED。下一步：Resolve exact free TWSE/TPEx/FinMind quote session/unit/null contracts and build field-by-scope/currency matrix; do not infer equivalence from paid A05 format or equal values。

---

# 最新接續：WP00-B12（2026-10-13，PARTIAL）

重用官方Swagger，分清TWSE終止上市日期、TPEx歷史暫停/恢復日期時刻与資料日期，以及變更/分盤/管理/停止交易狀態。有效區間、旗標、timezone与歷史coverage仍未認證；沒有查詢任何股票實際事件或identity提升。

報告：docs/registry/delivery/wp00/WP00_B12_IDENTITY_EVENT_REVIEW_20261013.md；機讀事件日期草案：docs/registry/delivery/wp00/identity_event_date_roles_draft_20261013.json。候選dataset25（不是來源/通過數），興櫃RAW_ONLY、資料API0、新Actions0、B115/934不變，Production BLOCKED。下一步：D02: complete quote transaction scope/native units/null documents; D01 event flag/timezone and listing/transfer/end effective evidence remain HOLD。

---

# 最新接續：WP00-B11（2026-10-13，PARTIAL）

已確認ANNA→SIX現行CFI維護入口並核對公開碼表結構；官方文件hash/選定碼值及cell定位保存在cfi_current_docs_20261013。2021公開標準、碼表元素Version2019與股票生效日期不可混用。D01台灣掛牌/轉板/終止有效日期仍OPEN，沒有歷史identity/PIT提升。

報告：docs/registry/delivery/wp00/WP00_B11_CURRENT_CFI_DOCUMENT_REVIEW_20261013.md。來源資料API0、新Actions0；B115/934不變，21 scope及8ISIN本機檢查沒有與934累加。興櫃RAW_ONLY、22候選閘門未完整通過、Production BLOCKED。下一步：Complete Taiwan issuer/product-section and listing/transfer/end effective-date documents, then D02 quote scope/unit/null; no current CFI snapshot backfill into historical identity。

---

# 最新接續：WP00-B10（2026-10-13，PARTIAL）

核對證交所歷史CFI文章，目視確認分類/屬性與改版；不以歷史表認證現行普通股。新增ISIN格式/檢查碼helper，8本機文件範例/變異檢查通過，identity提升0；舊join及全runtime整合待做。TPEx靜態頁403不當定義已讀；TWSE股價頁起日只屬該頁。

報告：docs/registry/delivery/wp00/WP00_B10_IDENTITY_FORMAT_REVIEW_20261013.md。資料API0、新Actions0，B115/934基線不變；22候選閘門仍未通過，興櫃RAW_ONLY、Production BLOCKED。下一步：Complete D01 current instrument/CFI version and effective-date documents plus D02 quote scope/unit/null; integrate ISIN integrity helper into WP10 without promoting unknown identities。

---

# 最新接續：WP00-B9（2026-10-13，PARTIAL）

興櫃RAW_ONLY固定規則不變。範圍閘門修正false字串與非法JSON型別隔離；21本機合成案例（14重查+7新邊界）通過，不增加B115/934。精確TPEx /mopsfin_t187ap03_O契約已解析；候選dataset閘門22項仍未通過。舊scope腳本原已有歷史身分HOLD；不能宣稱新module已全部接入。

報告：docs/registry/delivery/wp00/WP00_B9_SCOPE_AND_DOC_CLOSURE_20261013.md；9組文件缺口清單：docs/registry/delivery/wp00/source_doc_closure_checklist_20261013.json，9不是剩餘來源/測試數。下一步：D01/D02: complete issuer instrument/effective-date definitions and price scope/unit/null documents; preserve emerging RAW_ONLY and source gate before sample probes。市場資料API0、新Actions0，Production BLOCKED。

---

# 最新固定規則：WP00-B8（2026-10-13）

使用者明確要求：興櫃只保存不分析；首版上市/上櫃普通股經所需來源/資料/暖機驗收才分析。不得用目前上市身分回填興櫃歷史，轉板價格/籌碼窗口不串興櫃。ETF/TDR等不進普通股選股，benchmark另走契約。未知身分隔離，停止交易/暖機不足/資料不合格HOLD。

標準：docs/policies/JARVIS_STOCK_SCOPE_V1_20261013.md；機讀政策：docs/registry/policies/analysis_scope_v1.json；模組：scripts/jarvis_analysis_scope.py。14本機合成規則案例通過，不是市場/Actions驗收。尚未接全部舊workflow，WP10/WP80/WP90列必要整合驗收。專案永久紀錄可接續；ChatGPT個人記憶設定寫入未確認。

來源資料API0、新Actions0；B115/934基線不變，文件閘門與Production仍BLOCKED。下一步：Apply fixed emerging RAW_ONLY/ordinary-stock scope to the first-release missing-document checklist; integrate scope module into WP10/WP80/WP90 before E2E acceptance; data probes remain paused until SOURCE_DOC_GATE PASS。

---

# 最新文件審閱：WP00-B7（2026-10-13，PARTIAL）

確認FinMind原始OHLC0可能代表無公告價格且可有量；興櫃open為前日均價；Adj可沿用昨日OHLC，不能替代Raw缺價狀態。Info轉板多列取最新僅屬目前市場，不認證歷史identity。已抽取官方quote/issuer schema並記錄PriceAdj方案與anchor待釐清項。

報告：docs/registry/delivery/wp00/WP00_B7_PRICE_IDENTITY_REVIEW_20261013.md。候選閘門21項，不是來源/通過數。市場API0、新Actions0，B115/934基線不變，Production BLOCKED。下一步：Build a first-release missing-document checklist; resolve precise TPEx identity dataset, price session/unit/null rules and adjustment permissions/anchor semantics before sample probes。

---

# 最新文件審閱：WP00-B6（2026-10-13，PARTIAL）

確認FinMind法人歷史分類與零值/缺列差異、TWSE不含/含鉅額商品口徑、TPEx法人股數及精確空白key；餘額不可替代當日融資買進。保存官方TWSE商品與TPEx Swagger，未訂購/未取市場資料。融券及全欄位單位、Note日期、交易範圍與實際修訂仍待確認。

候選閘門增列TPEx兩dataset至19項，不是來源數/測試通過數。報告：docs/registry/delivery/wp00/WP00_B6_CHIP_REVIEW_20261013.md。市場API0、新Actions0，B115/934基線不變，Production BLOCKED。下一步：Complete chip official trade scope/unit/Note definitions and price/security identity documentation; retain unresolved historical regimes and revision gaps before any sample data probes。

---

# 最新文件審閱：WP00-B5（2026-10-13，PARTIAL）

建立15財報+6營收需求的四來源候選矩陣；不是21項測試通過。FinMind GrossProfit範例為毛利淨額，FinancialStatements中的EquityAttributableToOwnersOfParent為綜合損益歸屬，不是權益餘額。保存provider datasets/examples文件；few-shot範例不可當raw單位契約/Golden。原生unit、selector、期間、口徑、公告修訂仍待證明。

報告：docs/registry/delivery/wp00/WP00_B5_FUNDAMENTAL_MATRIX_REVIEW_20261013.md；矩陣：docs/registry/delivery/wp00/fundamental_source_matrix_draft_20261013.json。資料API0、新Actions0，B115/934基線不變，Production BLOCKED。下一步：Review remaining required chip/price/identity official contracts while carrying fundamental unit/type/report-basis gaps; source-data probes remain paused before SOURCE_DOC_GATE PASS。

---

# 最新文件審閱：WP00-B4（2026-10-13，PARTIAL）

已保存5份2026一般業linkbase，20段遠端讀回一致；156條目標相關原始關係及32條ES_CR定義arc不是實測通過數。確認營收中文同名不同QName、本期淨利/歸屬母公司淨利分開，以及毛利原始計算arc含生物資產損益。有效DTS、維度/context、FinMind等價及營收單位仍待確認。

報告：docs/registry/delivery/wp00/WP00_B4_XBRL_LINKBASE_REVIEW_20261013.md。市場資料API0、新Actions0，B115/934基線不變，SOURCE_DOC_GATE未通過，Production BLOCKED。下一步：Complete first-release financial role/dimension selector matrix and official monthly revenue unit/basis documents; then remaining required source docs before sample probes。

---

# 最新文件審閱：WP00-B3（2026-10-13，PARTIAL）

官方2026 XBRL ZIP下載成功（SHA256 4e44e67647b1a5a575d416ef44614d9c5651bb0d895621e12f6b6ca64a457869）。保存248個檔案hash及4份選定schema原文；11個分段遠端讀回一致。不是完整DTS或實際公司資料驗收。CashAndCashEquivalents跨namespace有金額時點/文字期間差異；decimals是準確度不是倍率；22+5候選宣告不可當27欄驗收。

報告：docs/registry/delivery/wp00/WP00_B3_XBRL_REVIEW_20261013.md；下一步：Review taxonomy linkbases and dimensions plus revenue official unit/basis documents; complete source gates before market data probes。市場資料API0、新Actions0，B115/934基線不變。文件閘門與Production仍BLOCKED，營收CSV單位待官方文件證明。

---

# 最新文件審閱：WP00-B2（2026-10-13，PARTIAL）

已保存5份MOPS相關官方文件。確認上市/上櫃月營收分開與14個文件欄位、損益/現金流累計與單季差異，以及財務比較站較MOPS申報慢一天；原生單位、精確XBRL分類/維度/修訂仍未完整核准。目錄更新頻率不一致須釐清。MOPS混合占位拆5項，候選文件閘門共17項，不是新增來源或通過數。

報告：docs/registry/delivery/wp00/WP00_B2_MOPS_REVIEW_20261013.md。市場資料API0、新Actions0；最後實測B115、934/934。SOURCE_DOC_GATE尚未通過，Production BLOCKED。下一步：Review official taxonomy files and revenue filing definitions/units; no market data probes before SOURCE_DOC_GATE PASS。

---

# 最新文件審閱：WP00-B1（2026-10-13，PARTIAL）

FinMind月營收與三張財報已完成本次章節審閱。create_time草稿修正為入庫日期，不是公告timestamp；EPS跨季股數基準及不同歷史起日已記錄。尚待MOPS精確來源/單位/口徑/公告修訂與完整文件閘門。來源資料API0，新Actions0；實測維持B115、934/934，Production BLOCKED。

報告：docs/registry/delivery/wp00/WP00_B1_FUNDAMENTAL_REVIEW_20261013.md；不可把文件審閱當資料驗收。下一步：Review MOPS official monthly revenue and financial definitions before data probes。

---

# 最新工作包：WP00-A（2026-10-13，PARTIAL）

已建立59項首版需求草稿、保存3份FinMind官方文件與9個範例表。來源/data API測試0、沒有新Actions run；最後實測仍B115/934檢查。不可把文件範例或需求列數當實測通過。

使用者新增固定要求：第一件事先完整審阅賈維斯會用到的每個來源dataset官方文件與定義、原始格式、單位、時點、coverage、修訂與權限。SOURCE_DOC_GATE通過才做最小樣本API/數值測試；遇文件與回應不同退回契約審閱。

必讀docs/registry/delivery/wp00/WP00_A_RESULT_20261013.md及source_document_gates.json；13候選dataset×13審閱主題目前均未完整通過。財報科學記號/負數、EPS股數基準、營收date/create_time日期意義、財報type selectors、權限与更新限制待驗。下一步WP00-B完成官方文件審閱，不優先做來源取數探測。結果已登錄events/WP00-A-20261013-DOC-REVIEW.json。

---

# JARVIS 最新接續入口：來源 × 功能交付計畫（2026-10-13）

最新已驗證：B線115，run38271015489，934/934合併控制PASS；交易範圍/PIT/付款與來源核准仍HOLD，Production BLOCKED。934不是新增市場樣本或整體完成率。每日自動Raw管線尚未部署。

使用者最新指示：按照來源與功能有效結案並規劃上線，同時固定記錄結果避免遺忘。停止以新增輪數作為目標。

必讀順序：
1. docs/registry/latest.json
2. docs/roadmap/JARVIS_SOURCE_FUNCTION_DELIVERY_PLAN_20261013.md
3. docs/registry/delivery/work_packages.json與events/
4. 受影響來源契約及實際Raw/Actions證據

下一工作：WP00 首版必需Raw/來源/權限/覆蓋與證據重用盤點。之後按WP10–WP100相依關係補資料、固定計算、每日管線及5–10實際交易日影子運行；WP200完整歷史/進階另驗。首版策略排名未驗不得正式推薦；資料欄位每項僅一個核准正式來源；不靜默fallback或補值。

固定結果工具：scripts/jarvis_record_acceptance.py。每工作包保留新event ID、來源/dataset/市場/資料日期/欄位、QA與資料status分開、commit/run/manifest/report、blocker、下一步。舊事件不可覆寫；QA PASS不會自動關包或上Production。Seed BASELINE-B115-20261013已登錄。工具已完成6項本機控制；尚未接入全部舊workflow自動登錄，這列入WP90，不可宣稱每日記錄已全自動化。

逐輪76–115最新證據在docs/audit/R7_BLINE_ROUND<round>_RESULT_20261012.md。早期aggregate計數只涵蓋當時快照，未重建所有後續Actions總數；不可將舊135當最新總數。主控Excel仍較早稽核快照，本次未更新或宣稱跨載體同步。

## 歷史接續快照（保留，不作最新進度）

# JARVIS 最新接續入口：R7.1 Audit 2026-10-12

正式狀態BLOCKED；GitHub每天自動Raw→永久保存→ChatGPT固定計算尚未部署。先讀docs/audit/R7_CROSS_SYSTEM_AUDIT_20261012.md與docs/registry/latest.json，再讀所需Raw，不以對話記憶替代原始證據。

## 最新狀態：B線第75輪完成

GitHub run38201141048 success，238項合併檢查PASS（131程式＋107階段），4官方來源完整擷取、5份gzip遠端讀回一致。累計135次Actions：113成功／22失敗／9無job；本輪4次失敗與最後成功均歸檔。13601行情列，1920當前股票候選、11626非普通股身分一致、55身分差異HOLD；當前主檔另10代號未見於10/08行情。行情10/08、公司主檔10/11、ISIN10/12分開保留，歷史PIT提升0。上市ISIN實測下載567.229秒，HTTP1.1／IPv4／完整期限控制已通過一次擷取，未驗收每日SLA。

下一輪76：交易單位／NULL與OHLC／交易範圍，查55筆身分差異及10筆未匹配。Production BLOCKED、每日排程未部署、11驗收群組未完整通過。Master仍114次稽核快照；永久ChatGPT記憶寫入未確認，以GitHub registry及此檢查點續接。

## 以下為各輪歷史紀錄（舊進度以本頁最新狀態為準）

基準歷史run113：96Actions success、17failure、8no-job；不同run非不同獨立sample。全run ledger/docs/audit/cross_system_20261012/all_runs.csv，原始輸出摘要all_run_reports.json。B線1–63表已整理，Round63 run38153650023；Round64本機8/8與4反例已驗，GitHub尚待執行。R7.1新contract本機30/30，不是PIT或資料全域PASS。

年鑑2012–2020候選264，231現行OTC掛牌日一致/10現上市/23未在現況名單；歷史PIT0/264。39原異常仍需逐日有效市場/證券類型證據。興櫃Raw only；停止交易/權證暫停不等於股票終止；RetrievedAt非AvailableAt。

最新Master ID=1k-GqpB7X-JIBD_pfiIeQILB-R4KIDzEI；原R7與R5同SHA已發現，本次保留26歷史頁、追加7稽核頁为最新判定。Architecture ID=1cCbmeNuV1cgQjuwPJsttLVFnXDM4kdyVwulBaDx6aug。舊root Master/R5留作歷史，不把舊PASS升級。

CaseRegistry ID=1Vg5NJHHnqwXPK1qZf6Y4VDUGFG5fQvSaGy1NdSkLbAM：443/443 DEFINITION_PENDING、8417/8417空白NOT_CALCULATED。沒有完成指標引擎。修改公式/模型用新版本，Canonical不依Case_ID變值。

FinMind精確大小寫Trading_Volume/Trading_money/Trading_turnover，後者交易筆數，不是周轉率。沒有新FinMind data API呼叫。本次7官方有限probe HTTP200，其中4數據JSON+1Swagger+2文件；不當作全歷史覆蓋。TWSE OpenAPI Date=1151008要ROC轉換；TWT53U rwd歷史20261007已可讀1366列，QA006/014交易口徑未解。

最低12验收群組（非12次執行）見remaining_gates.csv，24問題見issues.csv。尚無可確認ChatGPT系統長期記憶寫入；此checkpoint是可讀的持久接續文件。


## 最終同步與雲端核驗

已提交稽核commit f20b02cdcef243b2e3dee36c0390e0f32cb2980b，139個提交檔案已核對Git blob SHA：0差異（7個CSV僅CRLF→LF標準化，原始response bytes與113份run evidence原樣保留）。新增GitHub run [38157923800](https://github.com/danny541690/C1-JARVIS/actions/runs/38157923800)實際日誌為Ran 30 tests / OK，Actions success、契約QA PASS；正式Production與歷史PIT仍BLOCKED。最新總執行114次＝原113＋新增1，97 success / 17 failure；8 no-job仍單獨登錄。G01 GitHub/Drive版本同步已通過，12個驗收群組中其餘11群組未完整驗收；Round64雲端仍待手動執行，不將30項回歸當作Round64或來源核准。


## B線第64輪：GitHub已執行（2026-10-12）

Run38182814904，commit c184c50b2f60a31e56941ee03acd54a4dc6831fe；Actions success，官方live Swagger語意檢查8/8 PASS，4候選非股票終止（2權證），FinMind calls0、endpoint reprobes0、歷史PIT0、promoted0，Production BLOCKED。已啟用先前同意的commit自動触發並保留手動Run入口。原115次總表含此新run；98success/17failure，8no-job。Master仍是114次全稽核snapshot，最新逐輪結果讀latest.json及Round64報告。下一輪應找真正終止上櫃生效日的官方來源契約，不能繼續拿停買或權證日期替代。


## B線第65輪：官方終止公告（2026-10-12）

Run38183335135，6/6公告檢查＋7/7反例PASS，兩原始公告hash已核對並永久歸檔。8420明揚終止日候選2024-11-29（停止日11-21）；6457紘康名義2025-01-01與假日順延01-02並存，EffectiveDate=NULL/HOLD。兩個known controls不是全Universe，公告發文日非PIT證明，PIT0/promoted0，Production BLOCKED。最新116runs/99success/17failure（8no-job）；Master仍為114次snapshot。下一輪讀官方終止表company/deListed前端契約，核對假日有效日，尚未宣稱API可用。


## 合併測試模式（2026-10-12）

使用者要求加快測試；已集中三類自動QA至單一batch workflow，單項保留手動。run38184030986驗合併器、run38184114833驗中央触發，兩次均37+8+6檢查PASS、API0，不新增獨立資料/PIT覆蓋。後續預設共用Raw批次，保留每階段QA/錯誤，失敗只修影響範圍。總run118，101success/17failure；原Master仍114次snapshot。B線65已完成，下一研究仍66官方終止表/假日交叉核對，Production BLOCKED。


## B線第66輪已完成（2026-10-12）

查輪次：未找到第68輪證據；此前B線65＋兩次批次初始化不另編輪。本次66 run38184716535合併45+8+6+8檢查PASS，新增API2，兩官方JSON/名義日期與公告一致；6457表1/1與公告順延1/2語意仍HOLD，PIT0/promoted0，Production BLOCKED。首跑38184626171為YAML設定錯、jobs0，已修同一輪並留證。總120runs/102success/18failure，9no-job。下一B線研究67：法律名義日/實際生效日/假日營業日定義核對；不可跳68。Master仍114次全稽核snapshot。


## B線第67輪完成（2026-10-12）

run38186925749，合併53+8+6+8+8檢查PASS，新API1、FinMind0。官方2025開休市1/1休市、1/2新年開始交易；與6457公告順延候選一致，名義1/1、停止12/26、順延營業候選1/2分欄。單案語意可分開，但Canonical日期仍NULL、MappingReview/PIT未核准，歷史日曆修訂版本未驗；不推廣至全歷史。最新121runs/103success/18failure（9no-job），Master仍114次snapshot。下一輪68：PIT可知時間、資料修訂與版本追溯Gate核對，不能僅用發文日/今日下載日期放行。


## B線第68輪完成（2026-10-12）

GitHub Actions run 38188515340：success。合併 63 項程式回歸及 8+6+8+8+10 項階段檢查，全部通過；共103項檢查，不代表103筆新市場樣本。本輪API呼叫0，使用已保存官方Raw，未重新驗證即時來源存取。

五份實際Raw（兩份公告、兩份終止上櫃表、一份2025交易日曆）全部SHA256吻合，歷史PIT證據仍為0/5：下載時間為2026年，缺少經審核的歷史快照、當時版本及可知時間證明。公告發文日不是下載版本的歷史可用證明；日曆可能含後續修訂。

新增歷史證據綁定驗證器，拒絕僅靠KnowledgeEvidenceVerified=True，並檢查實際Raw雜湊、來源URL、來源修訂版本、含時區的快照與修訂可用時間。10項合成控制測試只驗證程式規則。信任登錄表須由獨立審核流程提供；目前尚未部署，驗證器也不會自行認證時間證明的真實性。舊require_pit仍保留相容性，不能單獨作為正式上線放行依據。

本輪QA PASS表示正確保留封鎖。Production BLOCKED，CanonicalTerminationEffectiveDate與HistoricalPIT未放行，未提升任何Eligible資料。每日Raw管線與永久儲存仍未部署。

累計122次Actions（104成功、18失敗；其中9次無job）。Master仍是114次執行的稽核快照，最新狀態以registry與checkpoint為準。11個驗收群組未完成。

下一輪69：建立可審核的歷史快照／時間證明來源與信任登錄規格；取得真實證據後才能放行PIT。不能用更多合成測試取代歷史資料證明。

證據：docs/audit/evidence/round68_cloud_20261012/（含雲端輸出與完整job logs）。


## B線第69輪完成（2026-10-12）

兩次GitHub執行均success：首跑38188769476為實際來源探測，修正後38188915437為保存證據重播。每次71+8+6+8+8+10+11，共122項檢查PASS；重播不新增獨立市場樣本。首跑API3，重播API0，FinMind0。

## 真實來源结果

| 查詢 | HTTP | 結果 |
|---|---|---|
| 紘康6457官方公告目前內容 | 200 | 目前可存取，不能證明2024年的版本 |
| 公告11300095221精確網址CDX索引 | 200 | 指定截止日前空索引 |
| 公告11300110841精確網址CDX索引 | 200 | 指定截止日前空索引 |

截止2025-01-02 23:59:59台灣時間（UTC 20250102155959）。每查詢最多20列；這是兩個精確URL的結果，不能推論全網站、其他URL變體或其他來源沒有快照。沒有候選可進入capture下載與實際內容比對。官方POST終止表與交易日曆仍缺歷史回應版本；一般GET頁面不能代替POST資料證明。

## 修正與界線

新增verify_bundle，要求時間證明檔實際bytes、有效SHA256及與已審核信任登錄一致；補上第68輪只有時間證明雜湊欄位、沒有核對證明原始檔的缺口。8項新增合成控制只驗規則，不能當作市場證據。已保存規格與空白正式登錄（docs/contracts/），目前沒有核准任何真實歷史proof。

首跑合併器對新階段保留了舊REGRESSION_REUSED_EVIDENCE scope，雖然source_mode=LIVE_SOURCE_DISCOVERY與api_calls=3已如實保存，但scope不精確，已修正為THREE_LIVE_DISCOVERY_QUERIES_NO_PIT_PROMOTION。API有呼叫的總狀態改名PASS_QA_WITH_LIVE_PROBES，避免把探測當作資料放行。後續默认重用本輪封存結果，腳本變更或明確指定live才重新查詢；雲端重播確認API0。首跑原始報表保留，不覆寫歷史。

五份既有Raw仍缺時間證明原始檔與經核准歷史版本，真實PIT 0/5，Eligible提升0、Production BLOCKED。登錄及驗證器僅檢查已核准證據的綁定，不能自行認證偽造證明或代替獨立審核。舊require_pit與Round68單獨verify不得作正式放行依據。

累計124次Actions：106成功、18失敗（9次無job）。本輪有2次執行，仍只算第69輪。Master仍是114次稽核快照，11個驗收群組未完成。每日與永久Raw管線尚未部署；未確認ChatGPT永久記憶寫入。

下一輪70：查公告URL變體與其他可追溯官方歷史附件，繼續尋找實際capture；若仍缺證據，維持PIT封鎖並明列範圍，不用合成測試湊放行。

證據：docs/audit/evidence/round69_cloud_20261012/，docs/audit/evidence/round69_replay_20261012/；含來源Raw、查詢參數、雲端輸出與job logs。重播manifest的ARCHIVED時間是處理時間，來源首次取得時間以live manifest為準。


## B線第70輪完成（2026-10-12）

GitHub run38189386111 success。合併77+8+6+8+8+10+11+6，共134項檢查PASS；API6、FinMind0，僅查兩個已知公告，不代表全历史資料已建構。

## 真實來源成果

官方公告下載頁https://dsp.tpex.org.tw/web/announcement/download.php ，原始表單使用POST inputY=2024、inputM=10/12。依實際回應連結下載：

| 股票 | 公告文號 | 原始官方每日ZIP | 對應member |
|---|---|---|---|
| 8420 明揚 | 11300095221 | https://dsp.tpex.org.tw/storage/eb_data/11310/1131030.zip | 11300095221.html |
| 6457 紘康 | 11300110841 | https://dsp.tpex.org.tw/storage/eb_data/11312/1131202.zip | 11300110841.html |

兩ZIP均HTTP200，ZIP內對應公告與第65輪公告网页的股票、Market、Instrument、發文日、停牌日、名義終止日、假日順延候選及DateStatus完全一致。6457仍保留名義2025-01-01、順延候選2025-01-02、Canonical未核准。ZIP內其他文號及附件未當作本輪已驗證事件。原ZIP與member bytes、SHA256、請求參數、時間及雲端logs均保存。

CDX查詢將精確URL擴展到官方announcement_detail.php路徑prefix，依文號Base64 token篩選，並逐列解碼身份。兩個查詢均HTTP200，截止UTC20250102155959（台灣2025-01-02 23:59:59）無符合capture。每次最多20列，不能推論其他網域、遷站網址或官方ZIP本身沒有歷史capture。

## 邏輯修正及驗證

官方ZIP公告在主旨前有「附件：」欄位。原第65輪parser會在首個附件標籤截断內容，因此解析這種原始公告失敗；已改為只檢查主旨之後的附件結尾。新增真實member fixtures與6項控制，77項程式回歸全過。每日ZIP只从main區域的实际href挑選指定日期，不能使用導覽連結或猜檔名代替。

已下載雲端artifact並用同一Raw進行本機合併重播，134項再次PASS、API0。後續預設重用封存，來源腳本有改動或指定live才重新查詢；本輪不另觸發第二次GitHub重播。

## 仍缺的證據

現在取得的是官方歷史日期包內的實際公告內容，足以增加來源內容與事件語意佐證；目前下載時間仍是2026年。ZIP檔名、文件發文日不能證明這份bytes於2024年已可取得、亦不能證明之後未修訂。兩個新ZIP控制的歷史PIT0/2；原五份Raw PIT仍0/5，Eligible提升0、Production BLOCKED。沒有正式核准proof登錄；每日排程與永久Raw管線未部署。

累計125次Actions：107成功、18失敗（9次無job）；Master仍是114次稽核快照，11個驗收群組未完成。下一輪71：以已發現的官方每日ZIP網址，查歷史capture、版本與當時可知時間證明；找到候選須取capture原始bytes核對。ChatGPT永久記憶寫入未確認，GitHub與Drive為持久檢查點。

證據：docs/audit/evidence/round70_cloud_20261012/，包括兩份原ZIP（二進位保存）及完整job logs。


## B線第71輪完成（2026-10-12）

GitHub run38189858710 success。合併84+8+6+8+8+10+11+6+6，共147項檢查PASS，API4、FinMind0。已下載雲端artifact，再以保存Raw本機合併重播147項PASS、API0；重播不另算GitHub執行或新增市場樣本。

## 真實查詢結果

| 公告 | ZIP HEAD | Last-Modified（UTC） | ETag | ZIP member時間（無時區） | 精確ZIP網址CDX |
|---|---|---|---|---|---|
| 11300095221／8420 | HTTP200 | 2024-10-30 13:37:25Z | 未提供 | 2024-10-30 15:48:26 | HTTP200，空索引 |
| 11300110841／6457 | HTTP200 | 2024-12-02 09:44:34Z | 未提供 | 2024-12-02 17:33:08 | HTTP200，空索引 |

HEAD Content-Length分別59690、11603，符合保存ZIP長度，但HEAD沒有下載內容，不能證明当前bytes未變。Last-Modified為今天伺服器回報的修改時間；ZIP central directory時間不含時區。兩者不能互換為KnowledgeDate/AvailableAt，也不能證明當時公開、未修改或不可竄改。

CDX沒有限制查詢截止時間，逐列分類是否早於台灣2025-01-02 23:59:59（UTC20250102155959）；每精確URL最多20列。兩個本次查詢空索引，沒有候選可實際下載capture。不能推論其他網址、鏡像或封存服務也沒有資料。

## 驗證器與邏輯防護

新增capture驗證流程：核對歷史timestamp、原來源URL、CDX Base32 SHA1、保存ZIP SHA256、指定公告member及事件語意。下載若转址，實際final_url須維持指定時間及原始id_回應，否則標記CAPTURE_REDIRECT_VERSION_UNVERIFIED。這能避免封存服務轉到新版本後誤當舊快照。即使全部吻合也只標記REVIEW_REQUIRED，不能自動核准PIT。

7項新增合成控制驗證這些規則；合成capture不是市場證據。本輪沒有真實capture bytes，沒有新增正式proof。原ZIP在第70輪GitHub二進位證據保存，本輪再次核對其SHA256，並保存HTTP標頭、索引原始回應、manifest及完整雲端logs。

真實歷史PIT：兩ZIP控制0/2，原五Raw仍0/5，Eligible提升0、Production BLOCKED。Canonical日期未核准；每日Raw自動排程、永久管線與三裝置E2E仍未部署／驗收。累計126次Actions：108成功、18失敗（9次無job）。Master仍114次稽核快照，11個驗收群組未完成。

## 下一輪72

將這兩ZIP的歷史PIT缺口保留為HOLD，重播已保存查詢，不重複把空索引當新測試成果。接續每日Raw快照的單次保存、SHA256、版本與讀回驗證測試，為每天更新管線建立可實際驗收的基礎；不能用今天的快照回填2024年的可知時間。通過單次流程後才處理排程與交易日／新鮮度。

規格來源：Python ZipInfo.date_time文件 https://docs.python.org/3/library/zipfile.html ，Internet Archive CDX官方規格 https://github.com/internetarchive/wayback/blob/master/wayback-cdx-server/README.md 。本輪測得結果以docs/audit/evidence/round71_cloud_20261012/為準。

ChatGPT永久記憶寫入未確認；GitHub與Drive保存持久檢查點。


## B線第72輪完成（2026-10-12）

GitHub run38190423865 success。合併95+8+6+8+8+10+11+6+6+14，共172項檢查PASS；官方來源API0、FinMind0，重用已保存的官方Raw，不新增市場或歷史PIT覆蓋。

## 實際完成

七份官方原始回應：兩份公告HTML、兩份終止上櫃表JSON、一份交易日曆JSON、兩份每日公告ZIP。雲端store實際寫入7個Raw objects與7個快照manifest，每份原始內容讀回一致且重複寫入不建立新物件／清單（14個階段檢查）。來源取得時間、URL、HTTP方法、參數與原SHA256完整保留，source_data_date未知則NULL，不能把公告日期或保存日期冒充資料AsOfDate。

新增jarvis_raw_store：先將完整Raw寫入同一檔案系統暫存檔並fsync，再以不覆寫的原子發布建立object，最後發布manifest。讀取必須提供外部保存的manifest SHA256，並同時驗證snapshot identity、版本、原始檔長度與SHA256。來源／請求／原取得時間／Raw共同決定SnapshotID，ArchivedAt獨立保存；同一快照重試保持原manifest，Raw變更建立新版本、舊版本仍可讀。

11項新增程式控制涵蓋CRLF／NULL原始bytes、重試、舊新版本共存、並行寫入、Raw與manifest損壞、缺檔、缺manifest、時間時區／未來取得時間及路徑守門。加上既有控制共95項程式回歸PASS。API不覆寫不是WORM權限；由可信descriptor及Git版本紀錄核對內容，未部署獨立備援儲存或防管理者刪改政策。

## 真實GitHub保存及讀回

在commit 4fc7be0848d74b916e8e729c5d049cc8ee4780b0發布完整store bundle。所有Raw以實際Git blobs保存，ZIP保留二進位，不轉成文字或重新壓縮。使用GitHub fetch_file encoding=base64從該commit直接讀回7個Raw及7個manifest，驗證Git blob identity、原始bytes、manifest SHA256及來源取得時間。7/7 Raw及7/7 manifest一致，包括2/2 ZIP。

這些14次遠端檔案讀回獨立於172項Actions檢查，沒有混算為新市場樣本。完整結果remote_readback.json包含commit、每份SnapshotID、長度與SHA256。本輪文件／data提交沒有再觸發測試，所以僅新增1次Actions執行。

## 界線及下一輪

已完成單次快照雲端保存pilot；執行方式仍由ChatGPT提交，Actions本身尚未自動上傳bundle。每日排程、全來源更新、新鮮度與交易日判斷、授權續期／限流補抓、Drive原始資料同步及三裝置E2E未驗收。歷史PIT仍未核准，Eligible提升0、Production BLOCKED。今天保存的歷史文件不能回填2024年的KnowledgeDate。

累計127次Actions：109成功、18失敗（9次無job）；Master仍114次稽核快照，11個驗收群組未完成。下一輪73：串接一次自動Raw取得／快照發布／讀回，測試重試與失敗復原；單次自動流程確認後再處理每日排程。不能把手動pilot當作每日服務已部署。

結果及store：docs/audit/evidence/round72_cloud_20261012/；包含store/objects、store/manifests、snapshot_descriptors.json、remote_readback.json與完整雲端job logs。GitHub與Drive為持久檢查點，ChatGPT永久記憶寫入未確認。


## B線第73輪完成（2026-10-12）

使用者要求以資料正確性為第一，批次只用來減少重複工作。兩次雲端執行皆success：初次run38191611876共188項檢查；補強恢復紀錄後run38191963763共189項檢查（106+8+6+8+8+10+11+6+6+14+6）。每次官方來源POST2次、FinMind0，兩次來源呼叫合計4；每次發布job另外使用17次GitHub API。這些重跑不是新增市場樣本，本輪仍算第73輪。

## 真正完成的自動流程

合併QA與發布兩個job均通過。來源使用已核准格式的TPEX company/deListed POST，控制6457/year2025、8420/year2024。每次請求取得實際Raw後，先驗證HTTP200及來源host、JSON完整性、精確欄位、code/year/單列與totalCount、ROC日期，以及公告名義日期／停止日／假日順延語意。兩個控制都通過後才建立可發布handoff；source_data_date保留NULL，查詢年度不能當作當日AsOfDate。

發布job只有main且整批PASS、live控制handoff完整時才執行。QA job維持contents read；發布job使用contents write且只寫data/raw/pilot73/。Raw與manifest依內容hash／SnapshotID保存，run/attempt索引指向精確manifest digest；不使用force，main有變動就停止，不覆蓋其他提交。

初次自動發布commit96af7a8e0e2c5dd48c2325246ce1cfc9c0ee1867；補強後自動發布commit3a3a99a7c7695ff768ca8030c55faa48e08e68f7，source commit51281d2af28ebd27f3d9762611ecc9a6dcec1571。這些data commits由Actions發布job建立，不是ChatGPT手動上傳Raw。

發布job從固定publication commit讀回2 Raw、2 manifests及1索引，比對exact bytes／Git blob identity，並重新read_snapshot驗manifest及原檔SHA256。ChatGPT又從GitHub獨立取回相同5個檔案，兩份Raw、兩份manifest及索引全部一致；independent_remote_readback.json保存明確commit、runID、時間及hash。資料本輪只涵蓋兩個已知歷史事件控制，不能稱全市場每日行情更新已完成。

## 失敗與恢復驗證

來源429/暫時5xx/網路逾時最多3次有限重試；404不重試；HTTP200但JSON、身份或年度錯誤立即停止，不改用替代來源補過關。失敗請求次數會如實記錄，不能因最後失敗把API呼叫報為0。格式／語意未過就不建立publishable handoff，發布job不會執行。

讀回檢查發現原報告在發布後才最後記錄commit：若branch已更新但讀回失敗，會缺少恢復線索。已修正發布後立刻記錄publication_commit與PUBLISHED_READBACK_PENDING；讀回全部通過才改REMOTE_READBACK_VERIFIED。另強制handoff scope與BLOCKED旗標，不能自行擴大資料範圍。

新增模擬測試：Git寫入完成後注入讀回故障，確認FAIL報告保留commit；恢復讀回再跑相同handoff/run/attempt，確認只讀回、不建立第二個commit，舊資料保留。暫時來源錯誤及故障恢復是模擬控制；真實GitHub兩次發布／讀回是實際驗證，兩者分開，不宣稱經歷真實服務中斷。106項程式控制及所有階段共189項PASS。

內容版本由RawSHA256決定；取得時間不同可以形成新的SnapshotID，不能把新取得紀錄誤當內容有修改。歷史日期語意仍保留6457假日HOLD，HistoricalPIT未核准、Eligible提升0、Production BLOCKED。

## 剩餘範圍與接續

已完成控制查詢的單次自動GitHub保存／讀回pilot；每日排程、當日／最近交易日行情來源、全市場覆蓋、資料新鮮度、Drive原始資料自動備援與三裝置E2E未完成。G10有自動GitHubpilot，仍未整體驗收；G09仍NOT_DEPLOYED。11個驗收群組未完整通過。

累計129次Actions：111成功、18失敗（9次無job）；本輪2次執行，每次2個job。Master仍114次稽核快照。下一輪74優先驗每日行情來源的精確欄位、資料日期及新鮮度，確認後才擴充每日排程。歷史PIT缺口繼續HOLD，不用今日下載日期回填過往AvailableAt。

證據：docs/audit/evidence/round73_initial_20261012/及round73_cloud_20261012/；自動資料：data/raw/pilot73/store/，最新本輪索引data/raw/pilot73/runs/38191963763_1.json。GitHub與Drive是持久檢查點，ChatGPT永久記憶寫入未確認。


## B線第74輪完成（2026-10-12）

GitHub run38193853524 success，119項程式控制及96項階段檢查，共215項PASS；官方來源API4（上市行情、上櫃行情、兩個市場日曆各一次），FinMind0。本輪只有合併QA實際執行，publish-raw job因第73輪控制為archived而正常skipped；未自動發布每日行情或啟用排程。

## 真實來源成果

| 來源 | 行情筆數 | 原始日期 | 轉換後日期 | 本輪判定 |
|---|---:|---|---|---|
| TWSE STOCK_DAY_ALL | 1380 | 1151008 | 2026-10-08 | 符合最近已完成普通交易日 |
| TPEX daily_close_quotes | 12221 | 1151008 | 2026-10-08 | 符合最近已完成普通交易日 |

官方年度日曆分市場取得，2026年10月9日、10日、25日、26日為明列休市日期。驗證範圍只限2026年10月；普通交易週一至週五／13:30的判斷不能代替盤後資料發布SLA或非年度臨時休市公告。

本輪擷取及評估時間為台灣2026-10-12 09:57:06，尚未完成當日普通交易；排除10/9補假及10/10–11週末，最近已完成普通交易日為10/8。因此不能把1151008直接當作資料過舊，也不能把今天盤中的同日資料當已完成EOD。若未來在13:30後取得當日行情，仍標記HOLD_PUBLISHING_WINDOW_UNVERIFIED，直到發布時間／盤後交易涵蓋口徑經驗收。異常臨時停市feed尚未驗證，不能套用為全球／全歷史calendar。

## 格式與邏輯防護

逐列驗證官方row properties與實際array：TWSE12欄、TPEX18欄，全欄位為來源字串，證券代號不轉整數、保留00400A／00411A等前導零及字母；拒絕JSON重複鍵、重複代號、混合資料日期、欄位漂移／改名。日期編碼由契約明訂ROC_COMPACT，取回時間與資料日期分開。官方schema以object描述每列，實際回應是array；契約明列這個wrapper差異，只驗row properties，不宣稱完整官方JSON schema無差異。

櫃買Capitals官方description是「發行股數」，不可誤當股本金額／億元；LatesAskPrice是官方原始鍵名，不能自動改成LatestAskPrice後查欄位。成交股數、成交金額、成交筆數也須分開，不以名稱相似混用。Raw不改名、不重新序列化、不填補OHLC或把NULL／缺值換零。

重要：1380+12221共13601筆是來源證券行情，不是已確認普通股股票數。來源包含不同證券種類；本輪所有列InstrumentStatus=UNCLASSIFIED_RAW_SECURITIES，CanonicalEligible=false。普通股／ETF／權證等分類與全市場股票覆蓋尚未驗收，不能把資料全部送進股票模型。

## 完整原始資料與保存驗證

本機前置探測發現上櫃完整回應4782391 bytes，原4MB讀取上限會截斷JSON；前置截斷檔不算正式有效Raw。新擷取器設定20MB明確上限，讀limit+1判斷超限，不能把被截斷內容當合法JSON。以gzip mtime=0無損保存完整來源bytes，保留原SHA256、compressed SHA256及長度，不修改價格或JSON。兩行情、兩日曆與原始TWSE schema證據均保存GitHub。

bundle commit b8b3e9bfe382b4195e402af6360fc28f3e5021d3：從該commit直接讀回5份gzip，驗證Git blob identity、壓縮bytes及解壓後原SHA256。兩個完整行情陣列及兩個市場日曆均一致，含4.78MB上櫃Raw；不是只保存樣本列。另以下載的雲端證據合併重播215項PASS、來源API0。離線重播使用原evaluated_at，不冒充今天重新查詢的新鮮度。

## 界線與接續

來源欄位及本輪普通交易日匹配PASS；尚無全日盤後資料發布SLA、完整交易量涵蓋口徑／單位對照、證券類型與普通股主檔join、全股票覆蓋、歷史PIT核准。Eligible提升0、Production BLOCKED、每日排程未部署。本輪Raw保存由ChatGPT提交稽核bundle，不宣稱已接入每日行情自動發布。

累計130次Actions：112成功、18失敗（9次無job）；本輪job metadata2個，其中實際執行1個、正常skipped1個。Master仍114次稽核快照，11個驗收群組未完整通過。下一輪75優先做證券類型及普通股主檔對照，區分普通股、ETF、權證等，並核對股數／金額／筆數口徑；不能靠代號長度認定股票。

契約docs/contracts/QUOTE_ROW_CONTRACT_74.json；完整證據docs/audit/evidence/round74_cloud_20261012/與round74_spec_20261012/。交易制度來源：https://www.twse.com.tw/zh/products/system/trading.html 、https://www.tpex.org.tw/zh-tw/mainboard/trading/rules/system.html 。GitHub與Drive是持久檢查點，ChatGPT永久記憶寫入未確認。


# B線第75輪：官方當前證券分類與公司主檔交叉比對（2026-10-12）

GitHub修正後run 38201141048 success，共238項PASS（131程式控制＋107階段檢查）；新來源呼叫4、FinMind0。第75輪本身11個完整資料控制，12個新增程式反例／防護；不能把238項當238個新市場樣本。初次run38200198122 failure：前227項PASS，第75輪下載超过90秒遭中止，沒有完整來源證據，未冒充成功。第二趟延至300秒仍timeout；第三趟独立60秒追查：上櫃主檔PASS，其餘3源超時；第四趟curl IPv4：上市主檔PASS，上櫃HTTP/2失敗，兩個ISIN45秒只收到部分bytes。最終使用HTTP/1.1、IPv4、ISIN全傳輸600秒上限／其他45秒／低速30秒中止，父程序650秒與workflow14分鐘上限。沒有放寬schema／完整Raw檢查，部分下載不發布為有效Raw。

| 市場 | 行情列 | 官方股票＋創新板分類列 | 當前股票身分一致 | 非普通股且身分一致 | HOLD身分差異 |
|---|---:|---:|---:|---:|---:|
| TWSE | 1380 | 1082 | 1067 | 295 | 18 |
| TPEX | 12221 | 886 | 853 | 11331 | 37 |

本次上櫃行情含11210筆權證，上市行情沒有匹配權證；兩個來源的觀測收錄範圍不同，不能用原始列數直接比較普通股覆蓋率，也不宣稱上市所有權證皆無成交。

逐筆left join共13601列，無遺失、重複或代號整數化。分類依官方ISIN區段，不以代號長度、名稱關鍵字認定股票。創新板市場原文為「上市臺灣創新板」，獨立處理；ETF／ETN／TDR／特別股／受益證券與權證保留來源種類。股票CFI的ES前綴僅為本輪觀測控制，不單靠CFI推導完整金融商品分類。

來源：上市公司主檔t187ap03_L、上櫃主檔mopsfin_t187ap03_O、ISIN C_public strMode=2/4；4份Raw完整保存gzip，原始SHA256與compressed SHA256雙重驗證。官方HTML以CP950嚴格解碼，原Big5不足以解碼全部字元，沒有用errors=ignore/replacement吞掉錯誤。各市場官方區段／欄位／市場文字、代號唯一性、ISIN/CFI形狀、公司主檔資料日均嚴格驗證。

55筆HOLD：48筆股票主檔身分差異，7筆ETF行情名稱差異。主檔差異包含37筆掛牌日期、11筆簡稱不一致，不能直接宣稱官方資料錯誤或股票代碼不正確；可能是簡稱規格、轉板／重新上市／組織重整等日期角色差異，需正式公告確認。保留兩份來源值於identity_conflicts.json，未自動改名或用一份日期覆蓋另一份。

當前主檔有10個代號未見於10/08行情：TWSE1589/2323/4155；TPEX2067/3085/3625/3632/4804/6167/6173。記錄為目前主檔對舊行情的未匹配，不直接當抓取缺失或補造零成交／OHLC。

日期分離：行情2026-10-08、公司主檔出表2026-10-11、ISIN頁面更新2026-10-12，另保留真實source_retrieved_at。同日頁面更新日期不代表快照不再變動，原始hash才識別實際觀測內容。全部DateRole=CURRENT_REFERENCE_NOT_HISTORICAL_PIT，CanonicalEligible=false，eligible提升0，Production BLOCKED。1968筆官方股票區段列並非1968筆已驗收的歷史可回測普通股；1920筆當前股票候選也不獲歷史PIT核准。

股數／金額／成交筆數、OHLC價格容許值、零成交／暫停交易範圍、盤後口徑與發布SLA未在第75輪完整驗收。下一輪76優先核對交易單位／NULL與OHLC／成交口徑，並查上述55筆差異及10筆未匹配的正式證據。每日Raw排程未部署，Drive Raw自動備援與三裝置E2E尚未完成；仍11個驗收群組未完整通過。

本輪每次執行均2個job metadata，QA執行1個、發布job正常skipped1個。累計135次Actions：113成功、22失敗（其中9次無job）；所有前置失敗與成功執行證據均保存；不要把下載環境差異當來源原始資料錯誤。早期timeout總api_calls=0是階段未回報，不能用來聲稱沒有發送請求。一次完整取得並不代表每日排程、重試SLA或長期穩定性已驗收。Master仍114次稽核快照，最新狀態以registry/checkpoint為準；ChatGPT永久記憶寫入未確認。

本輪實際雲端快照離線重播238項PASS/API0；上市ISIN完整下載567.229秒，上櫃201.931秒。之後預設archived回歸，source/parser異動才live；這是單次完整取得，未驗收每日SLA。

雲端Raw bundle ec737394b7422a7d96f2aa1b392f49232d498e96：從指定commit直接讀回5份gzip，4來源（含9144363 bytes上市ISIN）及13601列衍生比對檔的原始SHA256／compressed SHA256／Git blob SHA均一致。完整遠端保存與讀回PASS；沒有把截斷下載當證據。

