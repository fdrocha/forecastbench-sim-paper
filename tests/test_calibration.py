"""Synthetic checks of quantile semantics and retained-data boundaries; no private inputs."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fbsim_paper.calibration.diagnostics import metrics, overview
from fbsim_paper.calibration.robustness import cluster_boot, METRICS
from fbsim_paper.calibration.parser_audit import read_lines
from fbsim_paper.calibration.context import run as context
from fbsim_paper.case_study import run


def test_discrete_quantile_ties_and_missing_forecast():
    data = dict(q=np.array([[[0, 1, 2, 3, 4], [np.nan]*5]], float),
                y=np.array([[1, 3, 3, 5], [1, 2, 3, 4]]), taus=np.array([.05,.25,.5,.75,.95]))
    result = metrics(data)
    assert result['central50_upper_miss'][0, 0] == .25  # strict >3, ties are not misses
    assert result['p75_below'][0, 0] == .25
    assert result['p75_at_or_below'][0, 0] == .75
    assert result['central50_coverage'][0, 0] == .75  # both bounds inclusive
    assert all(np.isnan(v[0, 1]) for v in result.values())


def test_equal_model_average_is_not_pooled_forecast_average():
    q=np.ones((2, 3, 5));q[1, 1:]=np.nan
    data=dict(name='measles', q=q, meta=pd.DataFrame({'horizon':[20,20,20]}),
              models=['a','b'], eci=[1,2])
    rows,_=overview(data, {'central50_upper_miss':np.array([[0,0,0],[1,np.nan,np.nan]])})
    available=next(r for r in rows if r['panel']=='available')
    assert available['value']==.5  # pooled would be .25


def test_cluster_bootstrap_uses_availability_denominators_and_fixed_seed():
    # Both clusters give model A 0 and model B 1, despite different available-item counts.
    meta=pd.DataFrame({'world':['a','a','b','b'], 'horizon':[1]*4})
    values=np.repeat(np.array([[0,0,0,0],[1,np.nan,1,np.nan]])[:,:,None],len(METRICS),axis=2)
    rows,differences=cluster_boot(meta,values,'world',b=100)
    assert all(r['ci_low']==r['ci_high']==.5 for r in rows)
    assert all(r['ci_low']==r['ci_high']==0 for r in differences)
    assert (rows,differences)==cluster_boot(meta,values,'world',b=100)


def test_parser_handles_grouped_numbers_scientific_notation_and_last_block():
    old='<<<PERCENTILES>>>\nQ1: p10=0 p25=0 p50=0 p75=0 p90=0\n<<<END>>>'
    new='<<<PERCENTILES>>>\nQ1: p10=1 p25=2 p50=3 p75=1,000 p90=2e3\n<<<END>>>'
    rows=read_lines(old+'\n'+new,[10,25,50,75,90],last=True)
    assert rows[0][0]==1
    np.testing.assert_array_equal(rows[0][1],[1,2,3,1000,2000])


def test_context_pairs_items_and_requires_identical_truth(tmp_path):
    ts=tmp_path/'timeseries';out=tmp_path/'out';out.mkdir();(ts/'data/scores').mkdir(parents=True)
    (out/'verification.json').write_text(json.dumps({'measles':{'model_names':['test/model']}}))
    rows=[dict(stratum='measles',series_id='measles_x_1930',horizon=20,y_true=10,p25=1,p75=9),
          dict(stratum='measles_named',series_id='measles_x_1930',horizon=20,y_true=10,p25=1,p75=11),
          dict(stratum='measles',series_id='measles_y_1930',horizon=20,y_true=50,p25=1,p75=1)]
    path=ts/'data/scores/test_model.csv';pd.DataFrame(rows).to_csv(path,index=False)
    context(ts,out)
    result=pd.read_csv(out/'matched-context.csv').set_index('context')
    assert (result.n==1).all()  # the unpaired item cannot affect either result
    assert result.loc['unlabeled','upper_miss']==1 and result.loc['named','upper_miss']==0
    rows[1]['y_true']=12;pd.DataFrame(rows).to_csv(path,index=False)
    with pytest.raises(AssertionError):context(ts,out)


def test_missing_inputs_and_existing_output_fail_before_writing(tmp_path):
    output=tmp_path/'new'
    with pytest.raises(ValueError,match='Missing private input'):
        run(tmp_path/'fc',tmp_path/'ts',tmp_path/'roster.json',output)
    assert not output.exists()
    output.mkdir();(output/'sentinel').write_text('keep')
    with pytest.raises(ValueError,match='new directory'):
        run(tmp_path/'fc',tmp_path/'ts',tmp_path/'roster.json',output)
    assert (output/'sentinel').read_text()=='keep'


def test_case_study_cli_has_explicit_paths():
    result=subprocess.run([sys.executable,'-m','fbsim_paper','case-study','--help'],capture_output=True,text=True)
    assert result.returncode==0
    for flag in ['--freeciv-root','--measles-root','--measles-roster','--output','--freeciv-raw-repo']:
        assert flag in result.stdout
