"""Offline, exploratory calibration diagnostics on retained FreeCiv and measles forecasts."""
import json, hashlib
import numpy as np
import pandas as pd



def load_freeciv(fc, out):
    sources = {}
    for path in [fc/'sets/draw_v1/continuous_300.json', fc/'results/run2_paper/results_v1/freeciv_results_wide.csv', *sorted((fc/'results/run2b_2026-09-20/batched').glob('*/results.jsonl'))]:
        sources[str(path.relative_to(fc))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (out/'freeciv-source-hashes.json').write_text(json.dumps(sources, indent=2)+'\n')
    items=json.loads((fc/'sets/draw_v1/continuous_300.json').read_text())
    wide=pd.read_csv(fc/'results/run2_paper/results_v1/freeciv_results_wide.csv').set_index('model').sort_index()
    models=list(wide.index)
    if len(models)!=24 or len(items)!=300:
        raise ValueError('Expected the paper panel of 24 FreeCiv models and 300 continuous items')
    rs={}
    for path in sorted((fc/'results/run2b_2026-09-20/batched').glob('*/results.jsonl')):
        for line in path.read_text().splitlines():
            r=json.loads(line);rs[r['model'],r['item'],r['arm']]=r
    pred=np.full((len(models),len(items),5),np.nan)
    truth=np.array([it['values'] for it in items],float)
    if truth.shape!=(300,1000) or not np.isfinite(truth).all():
        raise ValueError('Expected 1,000 finite replay outcomes per FreeCiv item')
    crossings=0
    for m,model in enumerate(models):
        for i,it in enumerate(items):
            r=rs.get((model,it['id'],'t1'));x=r.get('value') if r else None
            if x is not None:
                crossings+=int(any(np.diff(x)<0));pred[m,i]=np.sort(x)
    meta=pd.DataFrame([dict(item=it['id'],world=it['world'],horizon=it['T']-60,
        family=it['family'],metric=it.get('metric','')) for it in items])
    return dict(name='freeciv',models=models,eci=wide.eci.to_numpy(),q=pred,y=truth,
                meta=meta,taus=np.array([.05,.25,.5,.75,.95]),crossings=crossings)


def load_measles(ts, eci_scores, out):
    slug_map={m.replace('/','_').replace(':','_'):m for m in eci_scores}
    dfs=[]
    source_hashes={}
    for p in sorted((ts/'data/scores').glob('*.csv')):
        model=slug_map.get(p.stem)
        if model is None or model=='google/gemini-2.0-flash-lite-001':continue
        df=pd.read_csv(p)
        df=df[df.stratum=='measles'].copy()
        if df.empty:continue
        df['year']=df.series_id.str.rsplit('_',n=1).str[-1].astype(int)
        df=df[df.year.between(1928,1962)]
        if df.series_id.nunique()<1071:continue
        assert not df.duplicated(['series_id','horizon']).any()
        df['model']=model;dfs.append(df)
        source_hashes[str(p.relative_to(ts))]=hashlib.sha256(p.read_bytes()).hexdigest()
    if not dfs:
        raise ValueError('No eligible measles score files (1928–1962; at least 1,071 series per model)')
    df=pd.concat(dfs,ignore_index=True)
    models=sorted(df.model.unique())
    if len(models)!=28:
        raise ValueError(f'Expected the historical 28-model measles cohort, found {len(models)}')
    keys=df[['series_id','horizon','year']].drop_duplicates().sort_values(['series_id','horizon'])
    keys['state']=keys.series_id.str.removeprefix('measles_').str.rsplit('_',n=1).str[0]
    keys['item']=keys.series_id+'|'+keys.horizon.astype(str)
    keys=keys.reset_index(drop=True)
    if len(keys)!=7942 or keys.series_id.nunique()!=1339 or keys.year.nunique()!=35:
        raise ValueError('Measles input cohort differs from 1,339 series, 35 years, 7,942 targets')
    q=np.full((len(models),len(keys),5),np.nan);y=np.full(len(keys),np.nan)
    history_scales=np.empty(len(keys));truth_checked=0
    by_series={}
    for sid in keys.series_id.unique():
        path=ts/'data/series/measles'/f'{sid}.json'
        source_hashes[str(path.relative_to(ts))]=hashlib.sha256(path.read_bytes()).hexdigest()
        r=json.loads(path.read_text());by_series[sid]=r
    index=pd.MultiIndex.from_frame(keys[['series_id','horizon']])
    max_score_error=0
    for m,model in enumerate(models):
        g=df[df.model==model].set_index(['series_id','horizon']).reindex(index)
        q[m]=g[['p10','p25','p50','p75','p90']].to_numpy()
        yy=g.y_true.to_numpy();good=np.isfinite(yy)
        assert np.all(~np.isfinite(y[good]) | (y[good]==yy[good]))
        y[good]=yy[good]
        d=yy[:,None]-q[m];tau=np.array([.1,.25,.5,.75,.9])
        score=2*np.where(d>=0,tau*d,(tau-1)*d).mean(axis=1)
        err=np.nanmax(np.abs(score-g.crps_model.to_numpy()))
        max_score_error=max(max_score_error,err)
        np.testing.assert_allclose(score,g.crps_model.to_numpy(),rtol=1e-12,atol=1e-8,equal_nan=True)
    for i,r in keys.iterrows():
        source=by_series[r.series_id]
        assert y[i]==source['future'][r.horizon-1]
        history_scales[i]=max(float(np.mean(source['history'])),1.)
        truth_checked+=1
    crossing=np.any(np.diff(q,axis=2)<0,axis=2)&np.isfinite(q).all(axis=2)
    (out/'measles-source-hashes.json').write_text(json.dumps(source_hashes,indent=2)+'\n')
    return dict(name='measles',models=models,eci=np.array([eci_scores[m] for m in models]),
        q=q,y=y[:,None],meta=keys,taus=np.array([.1,.25,.5,.75,.9]),
        crossings=int(crossing.sum()),history_scales=history_scales,
        truth_checked=truth_checked,max_score_error=max_score_error)


def metrics(data):
    q,y=data['q'],data['y'];valid=np.isfinite(q).all(axis=2)
    lower=np.empty_like(q);upper=np.empty_like(q)
    # Process one quantile at a time to bound memory for 1,000 replays.
    for k in range(5):
        lower[:,:,k]=(y[None,:,:]<q[:,:,k,None]).mean(axis=2)
        upper[:,:,k]=(y[None,:,:]<=q[:,:,k,None]).mean(axis=2)
    lower[~valid]=np.nan;upper[~valid]=np.nan
    names=[f'p{int(t*100):02}' for t in data['taus']]
    out={}
    for k,name in enumerate(names):
        out[name+'_below']=lower[:,:,k]
        out[name+'_at_or_below']=upper[:,:,k]
    out['central50_coverage']=upper[:,:,3]-lower[:,:,1]
    out['central50_lower_miss']=lower[:,:,1]
    out['central50_upper_miss']=1-upper[:,:,3]
    out['outer_coverage']=upper[:,:,4]-lower[:,:,0]
    out['outer_lower_miss']=lower[:,:,0]
    out['outer_upper_miss']=1-upper[:,:,4]
    return out


def overview(data,ms):
    rows=[];model_rows=[]
    meta=data['meta'];valid=np.isfinite(data['q']).all(axis=2)
    common=valid.all(axis=0)
    groups={'all':np.ones(len(meta),bool)}
    if data['name']=='freeciv':
        for fam in sorted(meta.family.unique()):groups[fam]=meta.family.to_numpy()==fam
    for panel,mask in [('available',np.ones(len(meta),bool)),('common_items',common)]:
        for group,sel in groups.items():
            for h in sorted(meta.horizon.unique()):
                use=mask&sel&(meta.horizon.to_numpy()==h)
                if not use.any():continue
                for metric,a in ms.items():
                    per_model=np.nanmean(a[:,use],axis=1)
                    rows.append(dict(dataset=data['name'],panel=panel,group=group,horizon=int(h),
                        metric=metric,value=float(np.nanmean(per_model)),n_items=int(use.sum()),
                        min_model=float(np.nanmin(per_model)),max_model=float(np.nanmax(per_model))))
                    if panel=='available' and group=='all':
                        for model,eci,val in zip(data['models'],data['eci'],per_model):
                            model_rows.append(dict(dataset=data['name'],model=model,eci=float(eci),horizon=int(h),metric=metric,value=float(val)))
    return rows,model_rows


def run(fc, ts, eci_scores, out):
    rows=[];mr=[];audit={}
    for data in [load_freeciv(fc, out),load_measles(ts, eci_scores, out)]:
        ms=metrics(data);r,m=overview(data,ms);rows+=r;mr+=m
        valid=np.isfinite(data['q']).all(axis=2)
        audit[data['name']]=dict(models=len(data['models']),items=len(data['meta']),
            valid_forecasts=int(valid.sum()),common_items=int(valid.all(axis=0).sum()),
            crossings=data['crossings'],model_names=data['models'],
            max_score_error=data.get('max_score_error'),truth_checked=data.get('truth_checked'))
        data['meta'].to_csv(out/(data['name']+'-items.csv'),index=False)
        np.savez_compressed(out/(data['name']+'-diagnostics.npz'),
            **ms,q=data['q'],truth=data['y'],eci=data['eci'],models=np.array(data['models']),taus=data['taus'])
    table=pd.DataFrame(rows);table.to_csv(out/'calibration-overview.csv',index=False)
    pd.DataFrame(mr).to_csv(out/'per-model-calibration.csv',index=False)
    (out/'verification.json').write_text(json.dumps(audit,indent=2)+'\n')
    show=table[(table.panel=='available')&(table.group=='all')&table.metric.isin(
        ['p25_below','p25_at_or_below','p50_below','p75_at_or_below','central50_coverage','central50_upper_miss'])]
    print(show.pivot(index=['dataset','horizon'],columns='metric',values='value').round(4).to_string())
    print(json.dumps({k:{a:b for a,b in v.items() if a!='model_names'} for k,v in audit.items()},indent=2))



