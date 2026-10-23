import ast
import json
import pathlib
import unittest
import urllib.parse

# Exercise the production encoder without importing cloud credentials/dependencies.
tree=ast.parse(pathlib.Path('scripts/v093_three_year_repair.py').read_text())
ns={'urllib':__import__('urllib')}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='request_data'],type_ignores=[]),'encoder','exec'),ns)

class RequestEncodingTests(unittest.TestCase):
    def test_json_roundtrip_preserves_repeated_company_ids_and_unicode(self):
        params=[('compareItem','CashflowStatement'),('ylabel','現金流量表(累計)'),('ys','20262'),('companyId','8421'),('companyId','8422')]
        encoded=ns['request_data'](json.loads(json.dumps(params)))
        self.assertEqual(urllib.parse.parse_qsl(encoded.decode()),params)
    def test_mapping_and_none(self):
        self.assertEqual(ns['request_data']({'a':'b'}),b'a=b')
        self.assertIsNone(ns['request_data'](None))
    def test_invalid_pairs_rejected_before_network(self):
        for value in ['a=b',[['only-one']],[['a','b','c']]]:
            with self.assertRaises(ValueError):ns['request_data'](value)
