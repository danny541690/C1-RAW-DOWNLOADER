import json
import unittest

from scripts.v093_independent_raw import classify_finmind_price_payload


def raw(rows):
    return json.dumps({'data': rows}).encode()


def price(date, open_, high, low, close, volume, money):
    return {'date': date, 'stock_id': '8488', 'open': open_, 'max': high,
            'min': low, 'close': close, 'Trading_Volume': volume,
            'Trading_money': money}


class TestFinMindNoTradeRows(unittest.TestCase):
    def test_zero_volume_zero_ohlc_preserved_as_unresolved_raw(self):
        payload = raw([price('2026-10-07', 9.6, 9.9, 9.5, 9.8, 100, 980),
                       price('2026-10-08', 0, 0, 0, 0, 0, 0)])
        result = classify_finmind_price_payload(payload)
        self.assertEqual(result['positive_price_rows'], 1)
        self.assertEqual(result['no_trade_zero_price_dates'], ['2026-10-08'])
        self.assertTrue(result['no_trade_prices_are_missing_not_valid'])

    def test_zero_ohlc_with_positive_volume_is_invalid(self):
        with self.assertRaisesRegex(ValueError, 'MISSING_OR_INVALID_PRICE'):
            classify_finmind_price_payload(raw([price('2026-10-08', 0, 0, 0, 0, 10, 100)]))

    def test_nonzero_volume_bad_ohlc_is_invalid(self):
        with self.assertRaisesRegex(ValueError, 'OHLC_RELATIONSHIP_VIOLATION'):
            classify_finmind_price_payload(raw([price('2026-10-08', 12, 11, 9, 10, 10, 100)]))

    def test_empty_rows_are_invalid(self):
        with self.assertRaisesRegex(ValueError, 'FINMIND_PRICE_ROWS_ABSENT'):
            classify_finmind_price_payload(raw([]))

    def test_zero_price_without_volume_evidence_is_invalid(self):
        item = price('2026-10-08', 0, 0, 0, 0, 0, 0)
        item.pop('Trading_Volume')
        with self.assertRaisesRegex(ValueError, 'MISSING_OR_INVALID_PRICE'):
            classify_finmind_price_payload(raw([item]))


if __name__ == '__main__':
    unittest.main()
