import unittest,subprocess,sys,tempfile
from pathlib import Path
class Entry(unittest.TestCase):
 def test_smoke(self):subprocess.run([sys.executable,'-m','fbsim_paper','smoke'],check=True,capture_output=True)
 def test_check_data_needs_sums(self):
  with tempfile.TemporaryDirectory() as d:
   r=subprocess.run([sys.executable,'-m','fbsim_paper','check-data','--data-root',d],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0);self.assertIn('SHA256SUMS.txt',r.stderr)
 def test_removed_commands_are_gone(self):
  for c in ['validate','reproduce','reproduce-freeciv','reproduce-micropolis','check-archive']:
   self.assertNotEqual(subprocess.run([sys.executable,'-m','fbsim_paper',c],capture_output=True).returncode,0)
 def test_build_requires_manuscript(self):
  with tempfile.TemporaryDirectory() as d:
   r=subprocess.run([sys.executable,'-m','fbsim_paper','build','--data-root',d,'--paper-root',d],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0);self.assertIn('no main.tex',r.stderr)
 def test_build_refuses_uncommitted_manuscript_changes(self):
  with tempfile.TemporaryDirectory() as d:
   (Path(d)/'main.tex').write_text('');(Path(d)/'datasets/paper-inputs').mkdir(parents=True);(Path(d)/'data').mkdir();(Path(d)/'data/x.tex').write_text('')
   subprocess.run(['git','init','-q',d],check=True)
   r=subprocess.run([sys.executable,'-m','fbsim_paper','build','--data-root',d,'--paper-root',d],capture_output=True,text=True)
   self.assertNotEqual(r.returncode,0);self.assertIn('uncommitted changes',r.stderr)
