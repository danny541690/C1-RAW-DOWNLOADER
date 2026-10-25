import pathlib, unittest
class TaifexWorkflowDirections(unittest.TestCase):
 def test_explicit_nonoverlapping_directions(self):
  root=pathlib.Path(__file__).resolve().parents[1]/'.github/workflows'
  for name,direction in [('v093-taifex-independent.yml','ASC'),('v093-taifex-independent-asc.yml','DESC')]:
   command=[l.strip() for l in (root/name).read_text().splitlines() if 'run: python -m scripts.v093_taifex_independent ' in l]
   self.assertEqual(len(command),1)
   self.assertIn('--direction '+direction,command[0])
