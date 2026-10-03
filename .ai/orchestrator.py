#!/usr/bin/env python3
import json, os, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.ai'/'runs'; OUT.mkdir(parents=True,exist_ok=True)

def ask(url,headers,payload):
    req=urllib.request.Request(url,data=json.dumps(payload).encode(),headers=headers,method='POST')
    try:
        with urllib.request.urlopen(req,timeout=180) as r: return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError('HTTP '+str(e.code)+': '+e.read().decode(errors='replace')[:1500])

def call_openai(prompt):
    k=os.getenv('OPENAI_API_KEY'); m=os.getenv('OPENAI_MODEL','gpt-5')
    if not k: return {'provider':'openai','ok':False,'error':'OPENAI_API_KEY missing'}
    x=ask('https://api.openai.com/v1/responses',{'Authorization':'Bearer '+k,'Content-Type':'application/json'},{'model':m,'input':prompt})
    return {'provider':'openai','model':m,'ok':True,'text':x.get('output_text','')}

def call_claude(prompt):
    k=os.getenv('ANTHROPIC_API_KEY'); m=os.getenv('CLAUDE_MODEL','')
    if not k: return {'provider':'claude','ok':False,'error':'ANTHROPIC_API_KEY missing'}
    if not m: return {'provider':'claude','ok':False,'error':'CLAUDE_MODEL missing'}
    x=ask('https://api.anthropic.com/v1/messages',{'x-api-key':k,'anthropic-version':'2023-06-01','content-type':'application/json'},{'model':m,'max_tokens':6000,'messages':[{'role':'user','content':prompt}]})
    text=''.join(p.get('text','') for p in x.get('content',[]) if p.get('type')=='text')
    return {'provider':'claude','model':m,'ok':True,'text':text}

def call_grok(prompt):
    k=os.getenv('XAI_API_KEY'); m=os.getenv('GROK_MODEL','grok-4.7')
    if not k: return {'provider':'grok','ok':False,'error':'XAI_API_KEY missing'}
    x=ask('https://api.x.ai/v1/responses',{'Authorization':'Bearer '+k,'Content-Type':'application/json'},{'model':m,'input':prompt,'store':False})
    return {'provider':'grok','model':m,'ok':True,'text':x.get('output_text','')}

def main():
    task=os.getenv('TASK','').strip()
    if not task: raise SystemExit('TASK is required')
    files='\n'.join(p for p in __import__('subprocess').check_output(['git','ls-files'],text=True).splitlines()[:250])
    base='Repository: '+os.getenv('GITHUB_REPOSITORY','')+'\nTask: '+task+'\nTracked files:\n'+files
    prompts={
      'openai':base+'\nAct as coordinator: architecture, risks, implementation plan and validation.',
      'claude':base+'\nAct as implementation specialist: concrete code changes, compatibility and tests.',
      'grok':base+'\nAct as adversarial reviewer: find regressions, security issues and edge cases.'}
    funcs={'openai':call_openai,'claude':call_claude,'grok':call_grok}
    results=[]
    with ThreadPoolExecutor(max_workers=3) as pool:
        fs={pool.submit(funcs[n],prompts[n]):n for n in funcs}
        for f in as_completed(fs):
            try: results.append(f.result())
            except Exception as e: results.append({'provider':fs[f],'ok':False,'error':str(e)})
    good=[x for x in results if x.get('ok')]
    if not good: raise SystemExit('No provider succeeded')
    dossier='\n\n'.join('### '+x['provider']+'\n'+x.get('text','') for x in good)
    final=call_openai(base+'\nSynthesize these independent reviews into one actionable engineering decision.\n'+dossier)
    run=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    record={'run_id':run,'task':task,'agents':results,'synthesis':final}
    (OUT/(run+'.json')).write_text(json.dumps(record,indent=2,ensure_ascii=False))
    print(json.dumps(record,indent=2,ensure_ascii=False))

if __name__=='__main__': main()