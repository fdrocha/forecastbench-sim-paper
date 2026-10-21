"""Offline cached-paper reproduction. Production and provider code are never executed."""
from pathlib import Path
import argparse,json,hashlib,subprocess,os,sys,shutil,time
from fbsim_benchmark.scoring import pandemic
ASSETS=Path(__file__).parent/'assets'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(data):
 manifest=data/'manifests/homes-inputs-20260924.json'
 if not manifest.is_file():raise ValueError('Missing data manifest: '+str(manifest)+'; set --data-root or FBSIM_DATA_ROOT to the versioned private data home. Public synthetic smoke needs no private data.')
 m=json.loads(manifest.read_text())
 for row in m['files']:
  p=(data/row['path']).resolve()
  if not p.is_relative_to(data.resolve()):raise ValueError('Input escapes data root')
  if sha(p)!=row['sha256']:raise ValueError('Input hash mismatch: '+row['path'])
 pin=json.loads((ASSETS/'benchmark-pin.json').read_text());assert sha(Path(pandemic.__file__))==pin['pandemic_scoring_sha256'],'Benchmark scoring pin mismatch'
 for filename,h in pin['scoring_hashes'].items():
  if sha(Path(pandemic.__file__).parent/filename)!=h:raise ValueError('Benchmark scoring pin mismatch: '+filename)
 return dict(status='PASS',files_verified=len(m['files']),analysis_baseline=m['analysis_baseline'],latest_manuscript=m['latest_manuscript'],benchmark_pin=pin)
def analysis_root(data,analysis):
 """Assemble the Starsim analysis checkout from assets and the archive's cached calls."""
 shutil.copytree(ASSETS/'analysis',analysis)
 old=data/'datasets/analysis-original/results/causal';dst=analysis/'results/causal'
 # Exact cached call files and required historical reference distributions, no launchers.
 for rel in ['rerun_lowest','data/worlds']:
  shutil.copytree(old/rel,dst/rel,dirs_exist_ok=True)
 for name in ['worlds.json','worlds_hold.json','models.csv']:
  shutil.copyfile(old/'starsim_causal'/name,dst/'starsim_causal'/name)
 return analysis
def reproduce(data,out):
 checks=validate(data)
 if out.exists():raise ValueError('Output must be a new directory')
 out.mkdir(parents=True);start=time.monotonic();paper=out/'paper';ref=data/'datasets/paper-f214afe3';shutil.copytree(ref,paper)
 for p in paper.rglob('*'):
  if p.is_file():p.chmod(p.stat().st_mode|0o200)
 before={str(p.relative_to(paper)):(sha(p),p.stat().st_mtime_ns) for p in paper.rglob('*') if p.is_file()}
 analysis=analysis_root(data,out/'analysis')
 guard=str(ASSETS/'offline');env=dict(os.environ);env.update(PYTHONDONTWRITEBYTECODE='1',MPLCONFIGDIR=str(out/'mpl'),MPLBACKEND='Agg',PYTHONPATH=guard+os.pathsep+os.pathsep.join(sys.path))
 probe=subprocess.run([sys.executable,'-c',"import socket;socket.create_connection(('127.0.0.1',9))"],env=env,capture_output=True,text=True)
 assert probe.returncode and 'offline reproduction guard' in probe.stderr
 cmd=[sys.executable,str(ASSETS/'starsim/integrate_fixed_state.py'),'--paper-root',str(paper),'--analysis-root',str(analysis),'--audit-root',str(data/'datasets/starsim-audit/production_v1'),'--out',str(out/'generated')]
 with (out/'reproduction.log').open('w') as f:subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,check=True)
 # Run every check, so one mismatch does not hide the others; main fails afterwards if any did.
 failures=[]
 def check(name,ok):
  if not ok:failures.append(name)
  return ok
 byte=[dict(path=rel,sha256=sha(paper/rel),byte_equal=check(rel,sha(paper/rel)==sha(ref/rel))) for rel in ['data/starsim/starsim_excess_long.csv','data/combined_score.json','data/combined_matched_panel.json','data/starsim/integration_numbers.json','data/validation_table_main.tex','data/validation_table_forecastbench.tex','figures/fig_starsim_unconditional.png','figures/fig_starsim_interventional.png','figures/fig_starsim_horizon.png','figures/fig_combined_score.png']]
 text=lambda p:subprocess.check_output(['pdftotext','-layout',str(p),'-'])
 pdf=[dict(path=rel,pdf_text_equal=check(rel,text(paper/rel)==text(ref/rel))) for rel in [f'figures/{n}.pdf' for n in ['fig_starsim_unconditional','fig_starsim_interventional','fig_starsim_horizon','fig_combined_score']]]
 result=json.loads((paper/'data/combined_score.json').read_text());check('nine-cell rho',len(result['single'])==9 and result['rho']==0.8626086956521738)
 checks.update(byte_checks=byte,pdf_text_checks=pdf,nine_cell_rho=result['rho'],checks_run=len(byte)+len(pdf)+1,failures=failures,elapsed_seconds=time.monotonic()-start,network_guard_probe='PASS',simulations=0,model_calls=0,scope='Cached Starsim/combined reproduction; frozen Micropolis/FreeCiv inputs, not full replay regeneration')
 from .cached import _compare
 checks['all_generated_comparisons']=_compare(ref,paper,before)
 (out/'verification.json').write_text(json.dumps(checks,indent=2)+'\n');return checks

def load_env():
 """Fill unset variables from .env in this checkout, else the current directory; shell and flags win."""
 from dotenv import load_dotenv
 for d in (Path(__file__).resolve().parents[2],Path.cwd()):
  if (d/'.env').is_file():load_dotenv(d/'.env',override=False);return

def main():
 load_env()
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True);s.add_parser('smoke')
 for name in ['validate','reproduce','reproduce-freeciv','reproduce-micropolis']:
  q=s.add_parser(name);q.add_argument('--data-root',type=Path,default=os.environ.get('FBSIM_DATA_ROOT'))
  if name.startswith('reproduce'):q.add_argument('--output',type=Path,required=True)
 q=s.add_parser('build',help='Regenerate the manuscript checkout\'s generated files in place')
 q.add_argument('steps',nargs='*',help='Any of micropolis, freeciv, starsim (default: all, in that order)')
 q.add_argument('--data-root',type=Path,default=os.environ.get('FBSIM_DATA_ROOT'))
 q.add_argument('--paper-root',type=Path,default=os.environ.get('FBSIM_PAPER_ROOT'))
 q.add_argument('--allow-dirty',action='store_true',help='Run even if the manuscript has uncommitted changes under data/ or figures/')
 a=p.parse_args()
 if a.command=='smoke':
  assert pandemic.crps5([1,1,1,1,1],[1])==0;print(json.dumps(dict(status='PASS',scope='import and synthetic scoring only; no paper inputs')))
 else:
  if a.data_root is None:p.error('Pass --data-root DIR or set FBSIM_DATA_ROOT (in the shell or .env); no default private path is assumed.')
  a.data_root=Path(a.data_root).expanduser()
  if a.command=='build':
   if a.paper_root is None:p.error('Pass --paper-root DIR or set FBSIM_PAPER_ROOT (in the shell or .env).')
   from .build import run
   try:run(a.steps,a.data_root.resolve(),Path(a.paper_root).expanduser().resolve(),a.allow_dirty)
   except ValueError as e:p.error(str(e))
   except subprocess.CalledProcessError as e:sys.exit(f'build failed: {e.cmd[1]} exited with status {e.returncode}')
   return
  try:
   if a.command.startswith('reproduce-'):
    from .cached import run
    result=run(a.command.removeprefix('reproduce-'),Path(a.data_root).resolve(),a.output.resolve())
   else:result=validate(Path(a.data_root).resolve()) if a.command=='validate' else reproduce(Path(a.data_root).resolve(),a.output.resolve())
  except (ValueError,FileNotFoundError) as e:p.error(str(e))
  print(json.dumps(result,indent=2))
  if result.get('failures'):sys.exit(f"{len(result['failures'])} of {result['checks_run']} checks failed: "+', '.join(result['failures']))
