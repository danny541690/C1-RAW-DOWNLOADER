"""Route only observed native monthly schemas to the existing TAIFEX checker."""
import csv
import datetime
import io
from scripts.v093_taifex_independent import csv_evidence, native_text

GROUP = ['組合式序號', '日期', '契約數', '交易時段']
LARGE = ['日期', '商品(契約)', '商品名稱(契約名稱)', '到期月份(週別)', '交易人類別',
         '前五大交易人買方', '前五大交易人賣方', '前十大交易人買方', '前十大交易人賣方', '全市場未沖銷部位數']
FUTURES = ['交易日期', '契約', '到期月份(週別)', '開盤價', '最高價', '最低價', '收盤價', '漲跌價', '漲跌%',
           '成交量', '結算價', '未沖銷契約數', '最後最佳買價', '最後最佳賣價', '歷史最高價', '歷史最低價',
           '是否因訊息面暫停交易', '交易時段', '價差對單式委託成交量']
SCHEMAS = {'futDataDown': FUTURES, 'dlBargainOrderDown': GROUP, 'combinationOrderDown': GROUP,
           'largeTraderFutDown': LARGE,
           'dlLargeTraderOptDown': LARGE[:3] + ['買賣權'] + LARGE[3:]}


def inspect_month_csv(raw, row):
    dataset = row['資料集']
    if dataset not in SCHEMAS:
        raise ValueError('UNMAPPED_TAIFEX_DATASET')
    header = next(csv.reader(io.StringIO(native_text(raw))), [])
    if header != SCHEMAS[dataset]:
        raise ValueError('TAIFEX_DATASET_SCHEMA_MISMATCH')
    start = datetime.date.fromisoformat(row['期間'][:7] + '-01')
    end = datetime.date(start.year + int(start.month == 12), start.month % 12 + 1, 1) - datetime.timedelta(days=1)
    evidence = csv_evidence(raw, start, end)
    evidence.update(validation='NATIVE_MONTH_CSV_PARTIAL_ONLY', full_numeric_certification=False,
                    source_coverage_verified=False, pit_verified=False, analysis_release_approved=False,
                    unverified=['COMPLETE_CONTRACT_KEYS', 'ALL_DATASET_SPECIFIC_NUMERIC_RULES', 'HISTORICAL_UNIVERSE', 'PIT'])
    return evidence
