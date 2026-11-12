"""Paired sensitivity using the existing disease/location/season-labelled prompts."""
from pathlib import Path
import json
import numpy as np
import pandas as pd


def run(ts, out):
    models=json.loads((out/'verification.json').read_text())['measles']['model_names']
    rows=[]
    for model in models:
        f=(ts/'data/scores')/(model.replace('/','_').replace(':','_')+'.csv')
        d=pd.read_csv(f)
        d=d[d.stratum.isin(['measles','measles_named'])].copy()
        d['year']=d.series_id.str.rsplit('_',n=1).str[-1].astype(int)
        d=d[d.year.between(1928,1962)]
        u=d[d.stratum=='measles'];n=d[d.stratum=='measles_named']
        if n.empty:continue
        g=u.merge(n,on=['series_id','horizon'],suffixes=('_unlabeled','_named'),validate='one_to_one')
        assert np.all(g.y_true_unlabeled==g.y_true_named)
        for h,t in g.groupby('horizon'):
            for context in ['unlabeled','named']:
                rows.append(dict(model=model,horizon=int(h),context=context,n=len(t),
                    upper_miss=float((t.y_true_unlabeled>t['p75_'+context]).mean()),
                    coverage50=float(((t.y_true_unlabeled>=t['p25_'+context])&
                        (t.y_true_unlabeled<=t['p75_'+context])).mean())))
    r=pd.DataFrame(rows)
    r.to_csv(out/'matched-context.csv',index=False)
    print(r.groupby(['horizon','context'])[['upper_miss','coverage50']].mean().round(4).to_string())
