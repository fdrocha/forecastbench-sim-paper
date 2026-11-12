"""Check saved quantiles against retained output text without calling providers.

The conservative sensitivity excludes any forecast whose five quantiles cannot
be independently recovered from explicit labelled output and matched. Detected
format differences are logged, not silently repaired in the primary analysis.
"""
from pathlib import Path
import json,re,subprocess,gzip
import numpy as np
import pandas as pd

NUMBER=r'[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d*)?|\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?'
PAIR=re.compile(r'\bp(\d+)\s*[=:]\s*('+NUMBER+')',re.I)
BLOCK=re.compile(r'<<<PERCENTILES?>>>(.*?)<<<END>>>',re.I|re.S)


def read_lines(text,keys,last=False):
    blocks=BLOCK.findall(text or '')
    content=blocks[-1 if last else 0] if blocks else text or ''
    out=[]
    for line in content.splitlines():
        vals={int(k):float(v.replace(',','')) for k,v in PAIR.findall(line)}
        if all(k in vals for k in keys):
            pos=re.match(r'\s*Q(\d+)\s*[:.)-]',line)
            out.append((int(pos[1]) if pos else None,np.array([vals[k] for k in keys])))
    return out


def run(out, ts, fc, raw_repo, raw_ref):
    reports={};summary=[];issues=[]
    for name in ['freeciv','measles']:
        with np.load(out/f'{name}-diagnostics.npz') as packed:
            a={key:packed[key] for key in ['q','models','central50_coverage','central50_upper_miss']}
        meta=pd.read_csv(out/f'{name}-items.csv')
        good=np.zeros(a['q'].shape[:2],bool);valid=np.isfinite(a['q']).all(axis=2)
        linked=0;different=0;unavailable=0
        if name=='measles':
            for m,model in enumerate(a['models']):
                slug=model.replace('/','_').replace(':','_')
                for sid,g in meta.groupby('series_id',sort=False):
                    path=(ts/'data/forecasts')/slug/'measles'/f'{sid}.json'
                    if not path.exists():unavailable+=1;continue
                    r=json.loads(path.read_text())
                    if not r.get('parse_ok'):continue
                    parsed=read_lines(r.get('raw',''),[10,25,50,75,90])
                    hs=r['horizons']
                    for i,row in g.iterrows():
                        if not valid[m,i]:continue
                        saved=r['percentiles_by_horizon'].get(str(row.horizon))
                        assert saved is not None
                        np.testing.assert_allclose(a['q'][m,i],[saved[k] for k in ['p10','p25','p50','p75','p90']],rtol=0,atol=0)
                        linked+=1
                        pos=hs.index(row.horizon)
                        if pos>=len(parsed):continue
                        label,values=parsed[pos]
                        if label is not None and label!=pos+1:continue
                        values=np.maximum.accumulate(values)
                        if np.array_equal(values,a['q'][m,i]):good[m,i]=True
                        else:
                            different+=1
                            issues.append(dict(dataset=name,model=model,item=row['item'],
                                stored=a['q'][m,i].tolist(),text_values=values.tolist()))
        else:
            by_item={s:i for i,s in enumerate(meta.item)}
            for m,model in enumerate(a['models']):
                # Match by the source's model field rather than guessing folder escaping.
                for path in sorted((fc/'results/run2b_2026-09-20/batched').glob('*/results.jsonl')):
                    rs=[json.loads(s) for s in path.read_text().splitlines()]
                    if rs[0]['model']!=model:continue
                    rel='worlds/freeciv/fbsim_v3/results/run2b_2026-09-20/batched/'+path.parent.name+'/calls.jsonl.gz'
                    raw=subprocess.check_output(['git','show',raw_ref+':'+rel],cwd=raw_repo)
                    calls={}
                    for line in gzip.decompress(raw).splitlines():
                        c=json.loads(line);calls[c['call_id']]=c
                    for r in rs:
                        if r['item'] not in by_item or r['arm']!='t1':continue
                        i=by_item[r['item']]
                        if not valid[m,i]:continue
                        np.testing.assert_allclose(a['q'][m,i],np.sort(r['value']),rtol=0,atol=0)
                        c=calls.get(r['call_id'])
                        if c is None:unavailable+=1;continue
                        linked+=1
                        found=dict((pos,v) for pos,v in read_lines(c.get('text',''),[5,25,50,75,95],last=True) if pos is not None)
                        values=found.get(r['position'])
                        if values is None:continue
                        values=np.sort(values)
                        if np.array_equal(values,a['q'][m,i]):good[m,i]=True
                        else:
                            different+=1
                            issues.append(dict(dataset=name,model=model,item=r['item'],
                                stored=a['q'][m,i].tolist(),text_values=values.tolist()))
                    break
        for h in sorted(meta.horizon.unique()):
            use=meta.horizon.to_numpy()==h
            for metric in ['central50_coverage','central50_upper_miss']:
                v=np.where(good[:,use],a[metric][:,use],np.nan)
                summary.append(dict(dataset=name,horizon=int(h),metric=metric,
                    value=float(np.nanmean(np.nanmean(v,axis=1))),audited_forecasts=int(good[:,use].sum())))
        reports[name]=dict(valid_forecasts=int(valid.sum()),linked_to_saved_raw_record=linked,
            independently_matched_quantiles=int(good.sum()),different_text_values=different,
            unavailable_records=unavailable,remaining_not_independently_matched=int((valid&~good).sum()))
        np.save(out/f'{name}-parser-confirmed.npy',good)
        print(name, reports[name], flush=True)
    pd.DataFrame(summary).to_csv(out/'parser-audited-sensitivity.csv',index=False)
    (out/'parser-audit.json').write_text(json.dumps(reports,indent=2)+'\n')
    (out/'parser-differences.json').write_text(json.dumps(issues,indent=2)+'\n')
    print(json.dumps(reports,indent=2))
    print(pd.DataFrame(summary).round(4).to_string(index=False))


