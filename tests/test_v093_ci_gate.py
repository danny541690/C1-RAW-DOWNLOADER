import unittest
from scripts.v093_ci_gate import execution_signature,approved_code

class ConsolidatedCodeAcceptance(unittest.TestCase):
    def tree(self,code='same',docs='doc'):
        return {'tree':[{'path':'scripts/main.py','sha':code,'mode':'100644','type':'blob'},{'path':'tests/test_main.py','sha':'test','mode':'100644','type':'blob'},{'path':'docs/report.md','sha':docs,'mode':'100644','type':'blob'}]}
    def workflow(self,head='old',success=True,branch='main'):
        return {'id':1,'head_sha':head,'head_branch':branch,'status':'completed','conclusion':'success' if success else 'failure'}
    def get(self,runs,current=None,previous=None):
        def fetch(path):
            if path.startswith('/actions/'):return {'workflow_runs':runs}
            if '/commits/' in path:return {'tree':{'sha':path.rsplit('/',1)[-1]}}
            if '/trees/new?' in path:return current or self.tree()
            if '/trees/old?' in path:return previous or self.tree()
            raise AssertionError(path)
        return fetch
    def test_exact_success_reused_without_tree_reads(self):
        result=approved_code(self.get([self.workflow('new')]),'new');self.assertTrue(result['ready']);self.assertEqual(result['reason'],'EXACT_COMMIT_TESTED')
    def test_failed_or_other_branch_cannot_authorize_work(self):
        for r in (self.workflow('new',False),self.workflow('new',branch='other')):
            self.assertFalse(approved_code(self.get([r]),'new')['ready'])
    def test_docs_only_change_reuses_same_executable_inputs(self):
        result=approved_code(self.get([self.workflow()],self.tree(docs='newdoc'),self.tree(docs='old')),'new')
        self.assertTrue(result['ready']);self.assertEqual(result['reason'],'IDENTICAL_EXECUTION_INPUTS_TESTED')
    def test_code_change_requires_new_acceptance(self):
        result=approved_code(self.get([self.workflow()],self.tree(code='newcode'),self.tree()),'new');self.assertFalse(result['ready'])
    def test_dependency_workflow_and_tests_are_bound(self):
        baseline=self.tree();before=execution_signature(baseline)
        for path in ('requirements-qa.lock','.github/workflows/worker.yml','tests/test_extra.py','config/v093_five_stage_policy.json'):
            tree=self.tree();tree['tree'].append({'path':path,'sha':'changed','mode':'100644','type':'blob'})
            self.assertNotEqual(execution_signature(tree),before)
    def test_partial_or_empty_tree_is_rejected(self):
        for tree in ({'tree':[]},{**self.tree(),'truncated':True}):
            with self.assertRaises(ValueError):execution_signature(tree)

if __name__=='__main__':unittest.main()
