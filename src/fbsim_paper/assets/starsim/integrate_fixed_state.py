"""Install accepted fixed-state continuous results locally, using cached forecasts only.
No simulation, provider call, network operation, or modification of input runs.
Run with the existing paper environment; --audit-root points to production_v1.
Retains current nine-cell combined methodology and its 10,000-model bootstrap.
"""
import argparse,csv,json,sys,shutil,runpy,hashlib,os
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
ap=argparse.ArgumentParser(); ap.add_argument('--paper-root',type=Path,required=True); ap.add_argument('--analysis-root',type=Path,required=True); ap.add_argument('--audit-root',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); args=ap.parse_args()
HERE=Path(__file__).resolve().parent; COMBINED=HERE.parent/'combined'
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
be.fig_unconditional(long,O,C);be.fig_interventional(long,O);be.per_item_table(pi,O,C)
sys.argv=['extra','--analysis-root',str(A),'--out',str(O)];runpy.run_path(str(HERE/'build_excess_extra.py'),run_name='__main__')
for n,dest in {'starsim_excess_long.csv':'data/starsim/starsim_excess_long.csv','per_item_table.tex':'data/starsim/per_item_table.tex','per_item_table.json':'data/starsim/per_item_table.json',**{n+'.tex':'data/appendix_tables/'+n+'.tex' for n in ['starsim_models','starsim_horizon','starsim_rung_horizon']},**{n+'.'+ext:'figures/'+n+'.'+ext for n in ['fig_starsim_unconditional','fig_starsim_interventional','fig_starsim_horizon'] for ext in ['pdf','png']}}.items():shutil.copy2(O/n,P/dest)
for p in (P/'data/appendix_tables').glob('starsim*.tex'):
 t=p.read_text().replace('five elicited quantiles p10..p90 vs the matched replay seeds','five elicited quantiles p10..p90 vs fixed-state continuations').replace('(Nick, 2026-09-17)','via integrate_fixed_state.py (retrospective continuous rescore; binary unchanged)');p.write_text(t)
val=json.loads((O/'validation_rows.json').read_text())
for name,newrows in val['rows'].items():
 p=P/'data'/name
 if not p.is_file():continue  # the manuscript reads hand-frozen copies since the 2026-09-24 code freeze
 lines=p.read_text().splitlines()
 hits=[i for i,l in enumerate(lines) if ('multirow{3}{*}{StarSim}' in l or 'multirow{3}{*}{Starsim}' in l or 'multirow{2}{*}{Starsim}' in l)];assert len(hits)==1
 start=hits[0]; count=2 if 'multirow{2}' in lines[start] else 3
 fixed=[r.replace('StarSim','Starsim') for r in newrows if 'Excess bits, binary' not in r]
 assert len(fixed)==2
 fixed[0]=r'\multirow{2}{*}{Starsim}'+fixed[0].replace(r'\multirow{3}{*}{Starsim}','').lstrip()
 # Rows returned after the binary row start with an ampersand.
 lines[start:start+count]=fixed
 lines[0]='% Starsim: repaired continuous only, 2,000 model-panel resamples; binary appendix-only.'
 p.write_text('\n'.join(lines)+'\n')
# Suppress incomplete hold means in comparable full-set columns; preserve CSV values.
for filename,indices in [('starsim_models.tex',[9]),('starsim_horizon.tex',[10,11])]:
 p=P/'data/appendix_tables'/filename;lines=p.read_text().splitlines()
 for i,line in enumerate(lines):
  if line.startswith('DeepSeek V4 Flash'):
   parts=line.split(' & ')
   for col in indices:parts[col]='--' if col<len(parts)-1 else r'-- \\'
   lines[i]=' & '.join(parts)
 p.write_text('\n'.join(lines)+'\n')
# Refit CURRENT combined definition: nine cells, full-precision excess nCRPS for FreeCiv.
sys.path.insert(0,str(COMBINED));sys.argv=['combined','--paper-root',str(P),'--out',str(O/'combined_score.json')]
g=runpy.run_path(str(COMBINED/'combined_score.py'),run_name='integration_import')
S=g['starsim']('excess'); cells={}
for src in [g['MICRO'],S,g['FREE']]:
 for k in next(iter(src.values())):cells[k]={m:src[m][k] for m in g['MODELS']}
result=g['analyse'](cells,'current nine-cell rescore',False);g['write_outputs'](result,O)
labels=list(cells); models=g['MODELS'];L=np.array([[cells[c][m] if cells[c][m] is not None else np.nan for c in labels] for m in models]); mask=np.isfinite(L);coords=np.argwhere(mask)
D=np.zeros((len(coords),L.shape[1]+len(models)))
for row,(mi,col) in enumerate(coords):D[row,col]=1;D[row,L.shape[1]+mi]=-1
U,sv,Vt=np.linalg.svd(D,full_matrices=False)
inv=np.divide(1.,sv,out=np.zeros_like(sv),where=sv>sv.max()*1e-15)
T=np.einsum('ij,j,kj->ik',Vt.T,inv,U)[L.shape[1]:];T-=T.mean(axis=0)
calc=lambda x:np.einsum('...j,ij->...i',np.log(np.maximum(x[...,mask],1e-4)),T)
assert np.allclose(calc(L),[result['theta'][m] for m in models],atol=1e-10)
boot=np.load(cache/'bootstrap_arrays.npz')['scores'];tr=read(cache/'truths_quantiles_floors.csv');audit_roster=json.loads((cache/'roster.json').read_text());ids=[r['openrouter_id'] for r in audit_roster];short=g['SHORT']
BL=np.broadcast_to(L,(boot.shape[0],*L.shape)).copy()
for group,label in [('cont_uncond','Starsim continuous excess CRPS'),('interventional_pooled','Starsim interventional excess CRPS')]:
 js=[j for j,t in enumerate(tr) if (t['source']=='cont_uncond')==(group=='cont_uncond')]; bb=boot[:,js,:].mean(axis=1)
 for i,m in enumerate(ids):
  if np.isfinite(bb[:,i]).all():BL[:,models.index(short[m]),labels.index(label)]=bb[:,i]
btheta=calc(BL)
assert np.isfinite(btheta).all()
# Independent batched alternating fit checks every propagated replay result.
X=np.log(np.maximum(BL,1e-4));bt=np.zeros(btheta.shape)
for _ in range(500):
 delta=np.nanmean(X+bt[:,:,None],axis=1)
 bt=np.nanmean(delta[:,None,:]-X,axis=2);bt-=bt.mean(axis=1,keepdims=True)
assert np.allclose(bt,btheta,rtol=0,atol=1e-10)
eci=np.array([g['ECI'][m] for m in models]);theta=np.array([result['theta'][m] for m in models]);fbmap={short[m['openrouter_id']]:m['fb_overall'] for m in audit_roster}
ci=lambda x:list(map(float,np.nanquantile(x,[.025,.975])))
combined_unc={}
for against,x in [('eci',eci),('fb_overall',np.array([fbmap[m] if fbmap[m] is not None else np.nan for m in models]))]:
 ix=np.flatnonzero(np.isfinite(x)); xx=x[ix];yy=theta[ix];rho=float(spearmanr(xx,yy).statistic);rng=np.random.default_rng(2026);inds=rng.integers(0,len(ix),(10000,len(ix)))
 panel=ci([spearmanr(xx[j],yy[j]).statistic for j in inds]);replay=ci([spearmanr(xx,t[ix]).statistic for t in btheta])
 combined_unc[against]={'rho':rho,'n':len(ix),'model_interval':panel,'replay_interval':replay}
 if against=='eci':assert np.allclose(panel,[result['lo'],result['hi']])
# Matched external-comparator panel, shared resampling indices, fitted scores fixed.
fb=np.array([fbmap[m] if fbmap[m] is not None else np.nan for m in models]);ix=np.flatnonzero(np.isfinite(fb))
rr=np.random.default_rng(2026);ii=rr.integers(0,len(ix),(10000,len(ix)))
ex=eci[ix];fx=fb[ix];ty=theta[ix]
er=np.array([spearmanr(ex[j],ty[j]).statistic for j in ii]);fr=np.array([spearmanr(fx[j],ty[j]).statistic for j in ii])
matched={'n':len(ix),'eci_rho':float(spearmanr(ex,ty).statistic),'eci_interval':ci(er),'fb_rho':float(spearmanr(fx,ty).statistic),'fb_interval':ci(fr),'difference_interval':ci(er-fr)}
dump(P/'data/combined_matched_panel.json',matched)
lines=[r'\begin{tabular}{lrr}',r'\toprule',r'Comparator / contrast & $\rho$ or difference & Models, 95\% \\',r'\midrule']
for label,point,interval in [('ECI',matched['eci_rho'],matched['eci_interval']),('ForecastBench',matched['fb_rho'],matched['fb_interval']),('ECI minus ForecastBench',matched['eci_rho']-matched['fb_rho'],matched['difference_interval'])]:
 lines.append(f'{label} & ${point:.3f}$ & $[{interval[0]:.3f},{interval[1]:.3f}]$ '+r'\\')
lines += [r'\bottomrule',r'\end{tabular}'];(P/'data/combined_matched_panel.tex').write_text('\n'.join(lines)+'\n')
result.update(starsim='fixed-state continuous; binary excluded',uncertainty=combined_unc,method='current nine-cell definition; other simulations fixed; panel bootstrap does not refit theta; replay bootstrap refits fixed panel')
dump(O/'combined_score.json',result)
for n in ['combined_score.json','combined_score_table.tex','combined_score_macros.tex']:shutil.copy2(O/n,P/'data'/n)
sys.argv=['plot','--paper-root',str(P),'--combined',str(P/'data/combined_score.json'),'--out-dir',str(P/'figures')];runpy.run_path(str(COMBINED/'plot_combined_score.py'),run_name='__main__')
sys.argv=['rank','--paper-root',str(P)];runpy.run_path(str(COMBINED/'make_rank_table.py'),run_name='__main__')
# Compact appendix table: separate uncertainty sources, no joint interval or effect-skill claim.
lines=[r'\begin{tabular}{llrrrr}',r'\toprule',r'Score & Comparator & $n$ & $\rho$ & Models, 95\% & Replays, 95\% \\',r'\midrule']
for group,label in [('cont_uncond','Continuous baseline'),('interventional_pooled','Interventional outcomes'),('combined_current','Combined nine cells')]:
 for against,pretty in [('eci','ECI'),('fb_overall','ForecastBench')]:
  if group=='combined_current':s=combined_unc[against];rho=s['rho'];n=s['n'];lo,hi=s['model_interval'];rl,rh=s['replay_interval']
  else:s=lookup[group,against];rho=float(s['new_skill_rho']);n=s['n'];lo,hi=float(s['new_panel_lo']),float(s['new_panel_hi']);rl,rh=float(s['new_replay_lo']),float(s['new_replay_hi'])
  lines.append(f'{label} & {pretty} & {n} & ${rho:.2f}$ & $[{lo:.2f}, {hi:.2f}]$ & $[{rl:.2f}, {rh:.2f}]$ '+r'\\')
lines += [r'\bottomrule',r'\end{tabular}'];(P/'data/starsim/fixed_state_uncertainty.tex').write_text('\n'.join(lines)+'\n')
extra=json.loads((O/'numbers_extra.json').read_text());dump(P/'data/starsim/integration_numbers.json',{'current_combined':combined_unc,'matched_external_panel':matched,'starsim':extra,'inputs':manifest})
# Read-only source assertions and binary preservation.
installed={key(r):r for r in read(P/'data/starsim/starsim_excess_long.csv')}
for k,r in old.items():
 if r['question_type']=='binary':assert installed[k]==r
print('PASS: audit scores reproduced, original binary rows preserved, current combined fit verified against direct least squares')
