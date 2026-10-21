"""Refit the nine-cell combined score from all three worlds and write its outputs into the paper checkout:
combined_score.json/_table/_macros, the matched external panel, Starsim's fixed-state uncertainty table, the figure
and the rank tables. Propagates Starsim's replay bootstrap (data/starsim/fixed_state/) through the fit, keeps the
10,000-model bootstrap; its intervals go in combined_score.json (uncertainty) and combined_matched_panel.json.
    python refit_combined.py --paper-root PAPER --out SCRATCH
"""
import argparse,csv,json,sys,shutil,runpy
from pathlib import Path
import numpy as np
from scipy.stats import spearmanr
ap=argparse.ArgumentParser(); ap.add_argument('--paper-root',type=Path,required=True); ap.add_argument('--out',type=Path,required=True); args=ap.parse_args()
HERE=Path(__file__).resolve().parent
P=args.paper_root.resolve(); O=args.out.resolve(); O.mkdir(parents=True,exist_ok=True)
read=lambda p:list(csv.DictReader(open(p)))
def dump(p,x):p.write_text(json.dumps(x,indent=2,default=lambda v:v.item() if hasattr(v,'item') else str(v))+'\n')
cache=P/'data/starsim/fixed_state'
lookup={(r['group'],r['against']):r for r in read(cache/'associations.csv') if r['horizon']=='pooled'}
# Refit CURRENT combined definition: nine cells, full-precision excess nCRPS for FreeCiv.
sys.path.insert(0,str(HERE));sys.argv=['combined','--paper-root',str(P),'--out',str(O/'combined_score.json')]
g=runpy.run_path(str(HERE/'combined_score.py'),run_name='integration_import')
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
sys.argv=['plot','--paper-root',str(P),'--combined',str(P/'data/combined_score.json'),'--out-dir',str(P/'figures')];runpy.run_path(str(HERE/'plot_combined_score.py'),run_name='__main__')
sys.argv=['rank','--paper-root',str(P)];runpy.run_path(str(HERE/'make_rank_table.py'),run_name='__main__')
# Compact appendix table: separate uncertainty sources, no joint interval or effect-skill claim.
lines=[r'\begin{tabular}{llrrrr}',r'\toprule',r'Score & Comparator & $n$ & $\rho$ & Models, 95\% & Replays, 95\% \\',r'\midrule']
for group,label in [('cont_uncond','Continuous baseline'),('interventional_pooled','Interventional outcomes'),('combined_current','Combined nine cells')]:
 for against,pretty in [('eci','ECI'),('fb_overall','ForecastBench')]:
  if group=='combined_current':s=combined_unc[against];rho=s['rho'];n=s['n'];lo,hi=s['model_interval'];rl,rh=s['replay_interval']
  else:s=lookup[group,against];rho=float(s['new_skill_rho']);n=s['n'];lo,hi=float(s['new_panel_lo']),float(s['new_panel_hi']);rl,rh=float(s['new_replay_lo']),float(s['new_replay_hi'])
  lines.append(f'{label} & {pretty} & {n} & ${rho:.2f}$ & $[{lo:.2f}, {hi:.2f}]$ & $[{rl:.2f}, {rh:.2f}]$ '+r'\\')
lines += [r'\bottomrule',r'\end{tabular}'];(P/'data/starsim/fixed_state_uncertainty.tex').write_text('\n'.join(lines)+'\n')
print('PASS: current combined fit verified against direct least squares')
