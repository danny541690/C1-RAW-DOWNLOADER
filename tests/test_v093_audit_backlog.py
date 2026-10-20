import json,unittest
from scripts.v093_audit_backlog import summarize,report_specs,R3,R4

class AuditInventoryTests(unittest.TestCase):
    def payload(self,version,source,**extra):
        return json.dumps(dict(period='2025-01',version=version,status='STAGING_NOT_APPROVED',archives=[dict(source=source,name='raw.zip',cells=10,**extra)])).encode()
    def test_source_precedence_does_not_double_count_or_reuse_stale_financial(self):
        specs=report_specs('2025-01')
        old=json.loads(self.payload(R3,'MOPS',status='INPUT_ERROR'))
        old['archives'].append(dict(source='TWSE',name='twse',cells=7))
        out=summarize('2025-01',{specs[0][0]:json.dumps(old).encode(),specs[1][0]:self.payload(R4,'MOPS',status='STRUCTURAL_READBACK_PASS')})
        self.assertEqual(out['sources']['MOPS']['staged_cells'],10)
        self.assertEqual(out['sources']['MOPS']['input_errors'],[])
        self.assertEqual(out['sources']['TWSE']['staged_cells'],7)
        self.assertFalse(out['approved'])
        self.assertEqual(out['coverage'],'NOT_VERIFIED')
    def test_absent_report_waits_and_incomplete_report_is_not_accepted(self):
        out=summarize('2024-12',{})
        self.assertEqual(out['sources']['TWSE']['status'],'WAITING_FOR_AUDIT_REPORT')
        name=report_specs('2025-01')[1][0]
        raw=json.loads(self.payload(R4,'MOPS'));raw['status']='CHECKPOINTED_TIME_BUDGET'
        out=summarize('2025-01',{name:json.dumps(raw).encode()})
        self.assertEqual(out['sources']['MOPS']['status'],'WAITING_FOR_STABLE_CONVERSION')
    def test_wrong_period_rejected(self):
        with self.assertRaisesRegex(ValueError,'PERIOD'):
            summarize('2024-12',{report_specs('2024-12')[0][0]:self.payload(R4,'MOPS')})
