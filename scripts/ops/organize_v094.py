"""Bounded, create-only organization of the authorized C1_0.94 tree.
Never updates, moves, deletes or changes permissions on any source artifact.
"""
import hashlib, io, json, os
from pathlib import Path
from datetime import datetime, timezone
from scripts.annual_actual_firstpass import service, Drive
from googleapiclient.http import MediaIoBaseUpload
ROOT='1plssBEo_-KPCUzO43s6znpj4dmMt7Dab'
SOURCE_ROOT='1Tnxlu3BVvzUV-yM2Fe0HbwPHvQaHdePC'
RAW='1hKq9jYgmM2oJa8GqWwTENKKayELg2yDn'
RULES='1U5VHn3iPxnGbm2baUf27qYqt0Cq8wvBA'
FOLDER='application/vnd.google-apps.folder'; SHORTCUT='application/vnd.google-apps.shortcut'
FIELDS='id,name,mimeType,parents,size,md5Checksum,modifiedTime,shortcutDetails,webViewLink'
TOP={
'00_System':'1lDih5fuCZv59X6nDiyrrNPaPaoIGv0FA','00_INBOX':'1EAkU4WThTqJuxw_LsEeHjeimFiSdJeVt',
'01_RAW':RAW,'02_STANDARD':'1I8urtTn5I2Ht71HXeabylFBlDJX3QZcx','03_FEATURES':'1PmjOpQOs51NOzohO0ut0PMQK7JSObvL3',
'04_RESEARCH':'1fRgGYbawb9o6gQfFWEZ6lz3L8wuWQXNx','05_CONTROL':'1KH1SJDU2Ujm1uZCyLNb8Ks8rAdrQpsX6',
'06_PORTFOLIO':'1BtBIjwJ32K43JJIqR6vRwTWm0esTXA_x','07_REPORTS':'1p3Ij6ZGL4htYhhGKtEytU2MVOXW-wAit','99_BACKUP':'1dHsl6IUtrsgne30MHu3Sl8Q9Cu6AreMP'}
PATHS=list(TOP)+['99_ARCHIVE','00_System/Architecture','00_System/Policies','00_System/Schemas','00_System/Knowledge','00_System/SOP','00_System/SOP/ChatGPT','00_System/SOP/GitHub','00_System/SOP/Google_Drive','00_System/Legacy_0.93','00_System/Legacy_0.93/Policies','00_System/Legacy_0.93/Architecture','05_CONTROL/OPERATIONS','05_CONTROL/quality','05_CONTROL/tasks','05_CONTROL/manifests','05_CONTROL/folder_registry','05_CONTROL/releases','05_CONTROL/config','05_CONTROL/下載紀錄與缺口','07_REPORTS/整理驗收','07_REPORTS/Legacy_0.93','99_ARCHIVE/歷史測試']
STATIC_RULES=['1UXyDqJNU8sV_NIPObCrTFrND6pqw8vN9','1oyqkqFUWWIx3dmfUV68KuzOWpgg3FFTW','1g9FxCFrp_fmc6wcpDH5jb-JC4wZATvLE','1_uI-saEZb8VlF3I_GmGCRFHqr4qBeUjG','1OGyjDeCLQEkDhnQ2C7DvEPzEHhe3etk1']

def run():
 api=service(); d=Drive(api); call=d.call
 def meta(fid):return call(lambda:api.files().get(fileId=fid,fields=FIELDS))
 def children(fid):
  out=[]; token=None
  while True:
   p=call(lambda:api.files().list(q=f"'{fid}' in parents and trashed=false",pageSize=1000,pageToken=token,fields='nextPageToken,files('+FIELDS+')'))
   out+=p.get('files',[]); token=p.get('nextPageToken')
   if len(out)>20000:raise ValueError('inventory safety cap')
   if not token:return out
 root=meta(ROOT)
 assert root['name']=='C1_0.94' and root['mimeType']==FOLDER
 assert root['parents']==['1V479Khem7p2ZOFwMPS8M2_svqOJYYUn8']
 observed={}; records=[]; dirs={'':ROOT}; inventories={}
 def remember(fid):
  if fid not in observed:observed[fid]=meta(fid)
  return observed[fid]
 for fid in [SOURCE_ROOT,*TOP.values(),RULES,*STATIC_RULES]:remember(fid)
 def folder(path):
  if path in dirs:return dirs[path]
  p,_,name=path.rpartition('/'); parent=folder(p)
  fid=d.folder(parent,name);dirs[path]=fid; return fid
 for path in PATHS:folder(path)
 def shortcut(target,path,name):
  src=remember(target); parent=folder(path); old=d.find(parent,name)
  if old:
   result=meta(old['id'])
   assert result['mimeType']==SHORTCUT and result['shortcutDetails']['targetId']==target
  else:
   result=call(lambda:api.files().create(body={'name':name,'mimeType':SHORTCUT,'parents':[parent],
    'shortcutDetails':{'targetId':target},'description':'C1 0.94 reference; original remains in 0.93. Do not edit original through this shortcut.'},fields=FIELDS))
  result=meta(result['id']);assert result['shortcutDetails']['targetId']==target
  records.append({'action':'shortcut','source':src,'destination':result,'path':path+'/'+name,'verification':'mimeType+targetId'})
 def copy(fid,path):
  src=remember(fid); assert src['mimeType'] not in (FOLDER,SHORTCUT)
  parent=folder(path); name=src['name']; old=d.find(parent,name)
  if old:
   result=meta(old['id'])
  else:
   result=call(lambda:api.files().copy(fileId=fid,body={'name':name,'parents':[parent],
    'description':'Historical 0.93 snapshot, not live state; source='+fid+'; observed='+src.get('modifiedTime',''),
    'appProperties':{'v094SourceId':fid}},fields=FIELDS))
  result=meta(result['id']);assert result.get('parents')==[parent]
  props=call(lambda:api.files().get(fileId=result['id'],fields='appProperties')).get('appProperties',{})
  assert props.get('v094SourceId')==fid, 'copy source provenance mismatch'
  verification='native-copy+provenance+metadata'
  if src.get('md5Checksum'):
   assert result.get('md5Checksum')==src['md5Checksum'] and result.get('size')==src.get('size')
   verification='MD5+size+provenance'
  records.append({'action':'copy','source':src,'destination':result,'path':path+'/'+name,'verification':verification})
 def list_source(fid):
  if fid not in inventories:inventories[fid]=children(fid)
  return inventories[fid]
 # Every old non-RAW top folder remains reachable; no data payload is copied.
 for name,fid in TOP.items():
  if name=='00_System':dest='00_System/Legacy_0.93'
  elif name=='05_CONTROL':dest='05_CONTROL/OPERATIONS'
  else:dest=name
  shortcut(fid,dest,'線上原位_'+name+'_0.93')
 shortcut(RULES,'05_CONTROL/下載紀錄與缺口','線上_下載規則與問題清單_持續更新')
 shortcut('1P_pohL-y_w9PzokprBenTOl66jXPMAKs','07_REPORTS/Legacy_0.93','下載修復報告歷史入口')
 # Classify stable System documents, preserving original titles and provenance.
 for f in list_source(TOP['00_System']):
  if f['mimeType']==FOLDER:
   if f['name'] in ('Policies','Architecture','Schemas'):
    dest='00_System/Legacy_0.93/'+f['name'];folder(dest)
    for sub in list_source(f['id']):
     if sub['mimeType']==FOLDER:shortcut(sub['id'],'99_ARCHIVE/歷史測試',sub['name'])
     elif sub['mimeType']==SHORTCUT:shortcut(sub['shortcutDetails']['targetId'],dest,sub['name'])
     else:copy(sub['id'],dest)
   else:shortcut(f['id'],'99_ARCHIVE/歷史測試',f['name'])
  elif f['mimeType']==SHORTCUT:shortcut(f['shortcutDetails']['targetId'],'00_System/Legacy_0.93',f['name'])
  else:
   dest='99_ARCHIVE/歷史測試' if ('STAGE06' in f['name'] or 'TEST' in f['name']) else '00_System/Legacy_0.93'
   copy(f['id'],dest)
 for f in list_source(SOURCE_ROOT):
  if f['mimeType'] not in (FOLDER,SHORTCUT):copy(f['id'],'00_System/Legacy_0.93')
 # Operational subfolders are live references, not frozen duplicate ledgers.
 for f in list_source(TOP['05_CONTROL']):
  if f['mimeType']==FOLDER:
   if f['name'] in ('tasks','manifests','folder_registry','releases','quality','OPERATIONS'):dest='05_CONTROL/'+f['name']
   elif 'QA' in f['name'] or f['name']=='quality':dest='05_CONTROL/quality'
   else:dest='05_CONTROL/OPERATIONS'
   shortcut(f['id'],dest,'線上原位_'+f['name'])
  elif f['mimeType']==SHORTCUT:shortcut(f['shortcutDetails']['targetId'],'05_CONTROL/OPERATIONS',f['name'])
  else:copy(f['id'],'07_REPORTS/Legacy_0.93')
 for f in list_source(TOP['07_REPORTS']):
  if f['mimeType']==FOLDER:shortcut(f['id'],'07_REPORTS/Legacy_0.93',f['name'])
  elif f['mimeType']==SHORTCUT:shortcut(f['shortcutDetails']['targetId'],'07_REPORTS/Legacy_0.93',f['name'])
  else:copy(f['id'],'07_REPORTS/Legacy_0.93')
 for fid in STATIC_RULES:copy(fid,'00_System/Legacy_0.93/Policies')
 # Authored documents are immutable on retries; differing bytes cause a stop.
 authored=[]
 def put(path,raw,mime='text/markdown'):
  parent_path,_,name=path.rpartition('/');parent=folder(parent_path)
  d.put(parent,name,raw,mime=mime,overwrite=False)
  result=meta(d.find(parent,name)['id'])
  readback=call(lambda:api.files().get_media(fileId=result['id']))
  assert hashlib.sha256(readback).digest()==hashlib.sha256(raw).digest()
  entry={'path':path,'id':result['id'],'sha256':hashlib.sha256(raw).hexdigest(),'url':result.get('webViewLink')}
  authored.append(entry);return result
 for p in sorted(Path('docs/v094').rglob('*.md')):put(p.relative_to('docs/v094').as_posix(),p.read_bytes())
 # Verify target source identities still have their original parents. Contents of
 # live logs may legitimately change; we never write to any original ID.
 parent_checks=[]
 for fid,before in observed.items():
  after=meta(fid);assert after.get('parents',[])==before.get('parents',[]),fid
  parent_checks.append({'id':fid,'parents':after.get('parents',[]),'unchanged':True})
 quota=call(lambda:api.about().get(fields='storageQuota')).get('storageQuota',{})
 stamp=datetime.now(timezone.utc).isoformat()
 manifest={'version':'0.94-R1','observed_at':stamp,'root_id':ROOT,'production_baseline':'fe9737de6b5b166de50b1bafc4e6a4caa4fab358','runtime_changed':False,'raw_payloads_copied':0,
  'folders':dirs,'actions':records,'authored_documents':authored.copy(),'source_parent_checks':parent_checks,'source_inventory':inventories,'storageQuota':quota,
  'limitations':['No full-market completeness certification','No new analytics/news/bond production deployment','Three SOPs reconstructed, not verbatim originals','Live folders referenced by native shortcuts; contents not duplicated','Native document copies lack binary MD5 comparison']}
 raw=json.dumps(manifest,ensure_ascii=False,indent=2).encode()
 put('05_CONTROL/folder_registry/C1_0.94_整理清冊_R1.json',raw,'application/json')
 count=lambda a:sum(x['action']==a for x in records)
 lines=['# 0.94 整理驗收 R1',f'完成時間（UTC）：{stamp}',f'根目錄：https://drive.google.com/drive/folders/{ROOT}',
 f'新目錄（不含根）：{len(dirs)-1}；文件快照副本：{count("copy")}；原生捷徑：{count("shortcut")}；新撰文件：{len(manifest["authored_documents"])}。',
 f'來源父目錄核對：{len(parent_checks)}/{len(parent_checks)}未變；RAW市場檔案搬移／複製：0；既有runtime／12槽設定變更：0。',
 '每個捷徑均讀回確認mimeType及targetId；一般副本以MD5+size+來源ID驗證，原生文件以copy操作+來源ID+父目錄驗證，未宣稱逐byte；新撰文件均SHA256遠端回讀一致。',
 '活動紀錄以捷徑保持即時；舊穩定文件放Legacy_0.93，歷史測試索引放99_ARCHIVE。原資料與權限未改動。',
 '本次是目錄／治理發布，不是全庫數值與PIT驗證，也不是新的每日報告、新聞或債券策略程式上線。',
 '三份SOP為依可追溯對話摘要與現行規則重整，非舊稿逐字搬移。',
 '\n## Drive容量（API當次回覆，bytes）',json.dumps(quota,ensure_ascii=False),
 '\n## 新文件入口']
 for a in manifest['authored_documents']:lines.append(f'- [{a["path"]}]({a["url"] or "https://drive.google.com/file/d/"+a["id"]+"/view"})')
 lines+=['\n## 未完成的系統工作','全資料集官方可得母體核准、數值QA與PIT覆蓋、獨立備份還原、帳務用量、每日摘要與分析功能逐項驗收，見架構比較P0/P1/P2表。沒有虛構已完成。']
 report=put('07_REPORTS/整理驗收/C1_0.94_整理驗收_R1.md','\n\n'.join(lines).encode())
 Path('results/v094').mkdir(parents=True,exist_ok=True)
 Path('results/v094/manifest.json').write_bytes(raw)
 summary={'root':ROOT,'folders':len(dirs)-1,'copies':count('copy'),'shortcuts':count('shortcut'),'authored':len(manifest['authored_documents']),'parents_verified':len(parent_checks),'report':report,'quota':quota,'documents':manifest['authored_documents']}
 Path('results/v094/summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':run()
