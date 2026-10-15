"""Run native cached reporting in disposable directories, never the manuscript."""
from pathlib import Path
import json, os, shutil, subprocess, sys, time
from .runner import ASSETS, sha, validate

def _env(out, extra=()):
    env = dict(os.environ)
    # Do not inherit a coauthor's live paper destination or provider config.
    env.pop('PAPER_REPO_PATH', None)
    env.update(PYTHONDONTWRITEBYTECODE='1', MPLBACKEND='Agg',
               MPLCONFIGDIR=str(out/'mpl'),
               PYTHONPATH=os.pathsep.join([str(ASSETS/'offline'), *map(str,extra), *sys.path]),
               MICROPOLIS_CORE_PATH=str(out/'engine-unavailable'),
               FBSIM_DATA_DIR=str(out/'no-production-data'))
    return env

def _compare(ref, paper, before):
    rows=[]
    for p in sorted(paper.rglob('*')):
        if not p.is_file(): continue
        rel=str(p.relative_to(paper)); h=sha(p)
        if before.get(rel)==(h,p.stat().st_mtime_ns): continue
        old=ref/rel
        row=dict(path=rel,sha256=h,reference_exists=old.is_file())
        if old.is_file():
            row['byte_equal']=h==sha(old)
            if p.suffix=='.pdf':
                row['pdf_text_equal']=subprocess.check_output(['pdftotext','-layout',str(p),'-'])==subprocess.check_output(['pdftotext','-layout',str(old),'-'])
            elif p.suffix=='.json':
                def numbers(v,path=''):
                    if isinstance(v,dict): return {k:n for a,b in v.items() for k,n in numbers(b,path+'/'+a).items()}
                    if isinstance(v,list): return {k:n for a,b in enumerate(v) for k,n in numbers(b,path+'/'+str(a)).items()}
                    return {path:v} if isinstance(v,(int,float)) else {}
                a=numbers(json.loads(p.read_text()));b=numbers(json.loads(old.read_text()))
                row['numeric_equal']=a==b
                row['numeric_differences']=[dict(field=k,current=a.get(k),reference=b.get(k)) for k in sorted(a.keys()|b.keys()) if a.get(k)!=b.get(k)]
        rows.append(row)
    return rows

def commands(world,data,paper,tmp,micropolis_inputs):
    """(env, commands) running a world's reporting scripts into the manuscript tree `paper`; scratch goes in `tmp`."""
    if world=='micropolis':
        # Native script writes beside its CSVs, so pass only a disposable copy.
        inputs=tmp/'inputs';shutil.copytree(micropolis_inputs,inputs)
        env=_env(tmp,[ASSETS/'micropolis']);env['PAPER_REPO_PATH']=str(paper)
        return env,[[sys.executable,str(ASSETS/'micropolis/scripts/analyze_paper.py'),'--datadir',str(inputs),'--outdir',str(tmp/'figures'),'--no-extra']]
    env=_env(tmp);env.update(FBSIM_SOURCE_ROOT=str(data/'datasets/freeciv-source/worlds/freeciv/fbsim_v3'),FBSIM_RUN='run2_paper',FBSIM_PAPER_ROOT=str(paper))
    return env,[[sys.executable,str(ASSETS/'freeciv'/s),'--paper-root',str(paper)] for s in ['make_freeciv_tables.py','make_freeciv_difficulty_table.py','make_freeciv_family_table.py','make_freeciv_figs.py']]

def run(world,data,out):
    checks=validate(data)
    required=data/'manifests/cached-worlds-20260924.json'
    if not required.is_file(): raise ValueError('Missing cached-worlds-20260924.json; obtain the versioned private data bundle, not simulator output generated ad hoc.')
    for row in json.loads(required.read_text())['files']:
        if row['world']!=world:continue
        p=data/row['path']
        if not p.is_file():raise ValueError('Missing cached '+world+' input: '+row['path']+'; restore it from the recorded private source bundle.')
        if sha(p)!=row['sha256']:raise ValueError('Changed cached input: '+row['path'])
    if out.exists():raise ValueError('Output must be a new directory; existing results are never overwritten')
    out.mkdir(parents=True);start=time.monotonic();ref=data/'datasets/paper-f214afe3';paper=out/'paper';shutil.copytree(ref,paper)
    for p in paper.rglob('*'):
        if p.is_file():p.chmod(p.stat().st_mode|0o200)
    before={str(p.relative_to(paper)):(sha(p),p.stat().st_mtime_ns) for p in paper.rglob('*') if p.is_file()}
    env,cmds=commands(world,data,paper,out,paper/'data/micropolis')
    with (out/'run.log').open('w') as log:
        for cmd in cmds:
            log.write('COMMAND '+json.dumps(cmd)+'\n');log.flush()
            subprocess.run(cmd,env=env,stdout=log,stderr=subprocess.STDOUT,check=True)
    result=dict(world=world,execution='PASS',comparisons=_compare(ref,paper,before),elapsed_seconds=time.monotonic()-start,
                analysis_baseline=checks['analysis_baseline'],simulations=0,model_calls=0,
                note='Execution success does not establish frozen-result equality. Consult each comparison; date metadata and prior manual edits can differ. No output is promoted into frozen inputs.')
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
