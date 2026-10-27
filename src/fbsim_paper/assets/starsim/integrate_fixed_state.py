"""Install accepted fixed-state continuous results locally, using cached forecasts only.
No simulation, provider call, network operation, or modification of input runs.
Run with the existing paper environment; --audit-root points to production_v1.
Writes the Starsim tables, figures and data files; the combined step (combined/refit_combined.py) refits the
nine-cell combined score from them.
"""
import argparse,csv,json,sys,shutil,runpy,hashlib
from pathlib import Path
import numpy as np
ap=argparse.ArgumentParser(); ap.add_argument('--paper-root',type=Path,required=True); ap.add_argument('--analysis-root',type=Path,required=True); ap.add_argument('--audit-root',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); args=ap.parse_args()
HERE=Path(__file__).resolve().parent
P=args.paper_root.resolve(); A=args.analysis_root.resolve(); R=args.audit_root.resolve()/'rescore'; O=args.out.resolve(); O.mkdir(parents=True,exist_ok=True)
read=lambda p:list(csv.DictReader(open(p)))
def dump(p,x):p.write_text(json.dumps(x,indent=2,default=lambda v:v.item() if hasattr(v,'item') else str(v))+'\n')
def key(r):return tuple(str(r[k]) for k in ('model','question_type','condition','rung','horizon'))
assert json.loads((R/'SUCCESS.json').read_text())['status']=='PASS'
# Keep original paper inputs and accepted audit artifacts with explicit provenance.
cache=P/'data/starsim/fixed_state'; cache.mkdir(exist_ok=True)
original=cache/'original_paper_long.csv'
if not original.exists():shutil.copy2(P/'data/starsim/starsim_excess_long.csv',original)
for name in ['paper_fixed_state_long.csv','associations.csv','model_scores_ranks.csv','truths_quantiles_floors.csv','item_scores.csv','forecast_coverage.csv','coverage_summary.csv','panels.json','roster.json','bootstrap_arrays.npz','SUCCESS.json']+[s+'_worlds.json' for s in ['cont_uncond','cont_int_c25','cont_int_c50','cont_int_c90']]:shutil.copy2(R/name,cache/name)
manifest={str(p.relative_to(cache)):hashlib.sha256(p.read_bytes()).hexdigest() for p in cache.iterdir() if p.is_file() and p.name not in {'input_manifest.json','HISTORICAL_README.md'}}
dump(cache/'input_manifest.json',manifest)
# Current scorer, with only continuous truth paths replaced; fixed historical scales.
sys.argv=['integration','--analysis-root',str(A)]; sys.path.insert(0,str(HERE))
import build_excess as be
be.use_cached_runs(be.bt,A/'results/causal/rerun_lowest')
for s,src in list(be.bt.SOURCES.items()):
 if s.startswith('cont_'):be.bt.SOURCES[s]=(*src[:4],cache/(s+'_worlds.json'),*src[5:])
C={40:200.,60:300.}; long,pi=be.score_all(C); expected={key(r):r for r in read(cache/'paper_fixed_state_long.csv')}; old={key(r):r for r in read(original)}
for r in long:
 for k in ('excess','crps','floor','excess_raw'):
  if k in r:assert np.isclose(r[k],float(expected[key(r)][k]),rtol=0,atol=1e-10),(key(r),k)
# Preserve original binary serialization, not just its numeric interpretation.
rows=[old[key(r)] if r['question_type']=='binary' else r for r in long]
with (O/'starsim_excess_long.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(next(iter(old.values()))));w.writeheader();w.writerows(rows)
# Display the audit's model-panel intervals for continuous panels, not newly sampled variants.
ass=read(cache/'associations.csv'); lookup={(r['group'],r['against']):r for r in ass if r['horizon']=='pooled'}; saved_rho=be.fg.rho_ci
roster=be.bt.load_roster(); external={m.openrouter_id:m for m in roster}
groups={'cont_uncond':('continuous','unconditional','-'),'interventional_pooled':('continuous','interventional','pooled(c25,c50,c90)'),**{'cont_int_'+c:('continuous','interventional',c) for c in ['c25','c50','c90']}}
def audit_rho(pts,*a,**kw):
 full=[x for x in pts if x[3]]
 for group,(typ,cond,rung) in groups.items():
  target={r['model']:r['excess'] for r in long if (r['question_type'],r['condition'],r['rung'],r['horizon'])==(typ,cond,rung,'pooled') and r['complete']}
  if all(m in target and np.isclose(y,target[m],rtol=1e-5,atol=1e-9) for m,x,y,_ in full):
   against='eci' if all(np.isclose(x,external[m].eci) for m,x,y,_ in full) else 'fb_overall'
   s=lookup[group,against]; assert len(full)==int(s['n'])
   return -float(s['new_skill_rho']),-float(s['new_panel_hi']),-float(s['new_panel_lo']),len(full)
 return saved_rho(pts,*a,**kw)
be.fg.rho_ci=audit_rho
base=P/'data/starsim/starsim_baselines.json'; refs=json.loads(base.read_text()) if base.exists() else None
be.fig_unconditional(long,O,C,refs);be.fig_interventional(long,O,refs);be.per_item_table(pi,O,C)
sys.argv=['extra','--analysis-root',str(A),'--out',str(O)]+(['--baselines',str(base)] if base.exists() else []);runpy.run_path(str(HERE/'build_excess_extra.py'),run_name='__main__')
for n,dest in {'starsim_excess_long.csv':'data/starsim/starsim_excess_long.csv','per_item_table.tex':'data/starsim/per_item_table.tex','per_item_table.json':'data/starsim/per_item_table.json',**{n+'.tex':'data/appendix_tables/'+n+'.tex' for n in ['starsim_models','starsim_horizon','starsim_rung_horizon']},**{n+'.'+ext:'figures/'+n+'.'+ext for n in ['fig_starsim_unconditional','fig_starsim_interventional','fig_starsim_horizon'] for ext in ['pdf','png']}}.items():shutil.copy2(O/n,P/dest)
extra=json.loads((O/'numbers_extra.json').read_text());dump(P/'data/starsim/integration_numbers.json',{'starsim':extra,'inputs':manifest})
# Read-only source assertions and binary preservation.
installed={key(r):r for r in read(P/'data/starsim/starsim_excess_long.csv')}
for k,r in old.items():
 if r['question_type']=='binary':assert installed[k]==r
print('PASS: audit scores reproduced, original binary rows preserved')
