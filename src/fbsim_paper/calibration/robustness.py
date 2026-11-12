"""Cluster uncertainty and sensitivity for the predeclared calibration grid."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

B=10000
SEED=20261110
METRICS=['p25_below','p25_at_or_below','p50_below','p50_at_or_below',
         'p75_below','p75_at_or_below','central50_coverage','central50_upper_miss']


def cluster_boot(meta,arrays,cluster,b=B):
    """Equal-model average, retaining each model's available-item denominator."""
    rng=np.random.default_rng(SEED)
    groups=sorted(meta[cluster].unique())
    horizons=sorted(meta.horizon.unique())
    n_models=arrays.shape[0]
    sums=np.zeros((len(groups),n_models,len(horizons),len(METRICS)))
    counts=np.zeros_like(sums)
    for g,name in enumerate(groups):
        for h,horizon in enumerate(horizons):
            use=(meta[cluster].to_numpy()==name)&(meta.horizon.to_numpy()==horizon)
            v=arrays[:,use,:]
            sums[g,:,h,:]=np.nansum(v,axis=1)
            counts[g,:,h,:]=np.isfinite(v).sum(axis=1)
    draws=rng.multinomial(len(groups),np.repeat(1/len(groups),len(groups)),b)
    num=(draws@sums.reshape(len(groups),-1)).reshape(b,n_models,len(horizons),len(METRICS))
    den=(draws@counts.reshape(len(groups),-1)).reshape(num.shape)
    estimates=np.nanmean(np.divide(num,den,out=np.full_like(num,np.nan),where=den>0),axis=1)
    # Simultaneous Bonferroni bands for the entire two-dataset horizon x metric
    # grid are supplied as a conservative sensitivity, alongside pointwise CIs.
    family_size=(5+6)*len(METRICS)
    rows=[]
    for h,horizon in enumerate(horizons):
        for k,metric in enumerate(METRICS):
            x=estimates[:,h,k]
            lo,hi=np.nanquantile(x,[.025,.975])
            blo,bhi=np.nanquantile(x,[.05/(2*family_size),1-.05/(2*family_size)])
            rows.append(dict(cluster=cluster,n_clusters=len(groups),horizon=int(horizon),metric=metric,
                ci_low=float(lo),ci_high=float(hi),bonferroni_low=float(blo),bonferroni_high=float(bhi)))
    differences=[]
    for k,metric in enumerate(METRICS):
        lo,hi=np.nanquantile(estimates[:,-1,k]-estimates[:,0,k],[.025,.975])
        differences.append(dict(cluster=cluster,metric=metric,ci_low=float(lo),ci_high=float(hi)))
    return rows,differences


def run(out):
    intervals=[];deltas=[];sens=[];cluster_rows=[];relations=[]
    for dataset in ['freeciv','measles']:
        a=np.load(out/f'{dataset}-diagnostics.npz')
        meta=pd.read_csv(out/f'{dataset}-items.csv')
        vals=np.stack([a[k] for k in METRICS],axis=2)
        horizons=sorted(meta.horizon.unique());complete=np.isfinite(vals).all(axis=(0,2))
        clusters=['world'] if dataset=='freeciv' else ['year','state']
        for cluster in clusters:
            r,d=cluster_boot(meta,vals,cluster)
            intervals += [dict(dataset=dataset,**x) for x in r]
            deltas += [dict(dataset=dataset,**x) for x in d]
            for name,g in meta.groupby(cluster):
                for h in horizons:
                    use=(meta[cluster].to_numpy()==name)&(meta.horizon.to_numpy()==h)
                    if not use.any():continue
                    for k,metric in enumerate(METRICS):
                        per_model=np.nanmean(vals[:,use,k],axis=1)
                        cluster_rows.append(dict(dataset=dataset,cluster=cluster,cluster_id=str(name),
                            horizon=int(h),metric=metric,value=float(np.nanmean(per_model)),n_items=int(use.sum())))
        # Keep the panel fixed and remove one model, provider or data cluster.
        providers=np.array([m.split('/')[0] for m in a['models']])
        for grouping,names in [('model',a['models']),('provider',providers)]:
            for name in sorted(set(names)):
                keep=names!=name
                for h in [horizons[0],horizons[-1]]:
                    use=meta.horizon.to_numpy()==h
                    for k,metric in enumerate(METRICS):
                        val=np.nanmean(np.nanmean(vals[keep][:,use,k],axis=1))
                        sens.append(dict(dataset=dataset,check='leave_one_'+grouping,removed=name,
                            horizon=int(h),metric=metric,value=float(val)))
        for cluster in clusters:
            for name in sorted(meta[cluster].unique()):
                for h in [horizons[0],horizons[-1]]:
                    use=(meta[cluster].to_numpy()!=name)&(meta.horizon.to_numpy()==h)
                    for k,metric in enumerate(METRICS):
                        val=np.nanmean(np.nanmean(vals[:,use,k],axis=1))
                        sens.append(dict(dataset=dataset,check='leave_one_'+cluster,removed=str(name),
                            horizon=int(h),metric=metric,value=float(val)))
        if dataset=='measles':
            # Match the historical series across all horizons, including parse
            # availability in every model. This is a sensitivity, not the main panel.
            series_counts=meta.loc[complete].groupby('series_id').horizon.nunique()
            stable=set(series_counts[series_counts==len(horizons)].index)
            use_base=meta.series_id.isin(stable).to_numpy()
            assert np.isfinite(vals[:,use_base,:]).all()
            for h in horizons:
                use=use_base&(meta.horizon.to_numpy()==h)
                for k,metric in enumerate(METRICS):
                    sens.append(dict(dataset=dataset,check='same_series_all_models_all_horizons',removed='',
                        horizon=int(h),metric=metric,value=float(vals[:,use,k].mean()),n_items=int(use.sum())))
        for h in horizons:
            use=meta.horizon.to_numpy()==h
            for k,metric in enumerate(METRICS):
                pm=np.nanmean(vals[:,use,k],axis=1)
                relations.append(dict(dataset=dataset,horizon=int(h),metric=metric,
                    eci_rho=float(spearmanr(a['eci'],pm).statistic)))
    pd.DataFrame(intervals).to_csv(out/'cluster-intervals.csv',index=False)
    pd.DataFrame(deltas).to_csv(out/'cluster-horizon-differences.csv',index=False)
    pd.DataFrame(sens).to_csv(out/'sensitivity.csv',index=False)
    pd.DataFrame(cluster_rows).to_csv(out/'per-cluster-calibration.csv',index=False)
    pd.DataFrame(relations).to_csv(out/'secondary-eci-correlations.csv',index=False)
    info=dict(n_boot=B,seed=SEED,aggregation='equal-model average of within-model item averages',
        clusters={'freeciv':['world'],'measles':['year','state']},
        limitations=['Clusters resampled separately; no joint model/world or state/year uncertainty claim.',
            'Only eight FreeCiv world clusters; bootstrap bounds are approximate.',
            'Pointwise percentile intervals; supplemental Bonferroni bands use extreme bootstrap quantiles and are approximate.',
            'Analysis is exploratory; correlated model families are held fixed in cluster intervals.'])
    (out/'uncertainty-method.json').write_text(json.dumps(info,indent=2)+'\n')
    table=pd.DataFrame(intervals)
    print(table[(table.horizon.isin([2,20,30,150]))&table.metric.isin(['central50_coverage','central50_upper_miss'])].round(4).to_string(index=False))
    print('Long-horizon leave-one sensitivity:')
    s=pd.DataFrame(sens)
    print(s[(s.horizon.isin([20,150]))&(s.metric=='central50_upper_miss')].groupby(['dataset','check']).value.agg(['min','max']).round(4).to_string())


