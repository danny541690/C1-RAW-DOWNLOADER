import unittest
from scripts.v093_legacy_calendar import parse,chinese_number

def fixture(year='九十一',other=None):
 return '<html><title>中華民國'+(other or year)+'年市場開休市日期</title><h2>中華民國'+year+'年市場開休市日期</h2><table><tr><th>名稱</th><th>日期</th><th>星期</th><th>說明</th></tr><tr><td>開國紀念日</td><td>一月一日</td><td>二</td><td>放假一日</td></tr><tr><td>國曆新年開始交易日</td><td>一月二日</td><td>三</td><td>放假說明另列</td></tr><tr><td>農曆春節</td><td>二月十一日至二月十三日</td><td></td><td>放假三日</td></tr><tr><td>其他說明</td><td>三月三日</td><td></td><td>尚未確認</td></tr></table></html>'

class LegacyCalendarTests(unittest.TestCase):
 def test_chinese_year_and_explicit_ranges_are_bound_to_requested_year(self):
  result=parse(fixture(),2002,'official');self.assertEqual(result['closed'],['2002-01-01','2002-02-11','2002-02-12','2002-02-13']);self.assertEqual(result['opened'],['2002-01-02']);self.assertEqual(result['unclassified'],['2002-03-03'])
 def test_conflicting_page_title_and_body_heading_are_rejected(self):
  with self.assertRaisesRegex(ValueError,'YEAR'):parse(fixture(other='九十'),2002,'official')
  with self.assertRaisesRegex(ValueError,'YEAR'):parse(fixture(),2003,'official')
 def test_an_error_page_is_not_calendar_evidence(self):
  with self.assertRaisesRegex(ValueError,'HEADERS'):parse('<html>無法存取</html>',2002,'official')
 def test_chinese_numeric_dates_are_not_gregorian_guesses(self):
  self.assertEqual(chinese_number('八十九'),89);self.assertEqual(chinese_number('一百零九'),109);self.assertEqual(chinese_number('廿一'),21)

if __name__=='__main__':unittest.main()
