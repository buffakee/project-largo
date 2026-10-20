#!/usr/bin/env python3
"""Update native desktop Appearance colors; the app reads them at startup."""
import argparse, copy, fcntl, json, os, re, subprocess, tempfile, tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def update_table(text, table, values):
    headers=list(re.finditer(r'(?m)^[ \t]*\[([^\]\n]+)\][ \t]*(?:#[^\n]*)?$', text))
    for i,h in enumerate(headers):
        if h[1].strip()!=table: continue
        end=headers[i+1].start() if i+1<len(headers) else len(text)
        body=text[h.end():end]
        for key,value in values.items():
            line=key+' = '+json.dumps(value)
            pattern=r'(?m)^[ \t]*'+re.escape(key)+r'[ \t]*=[^\n]*$'
            if re.search(pattern,body):body=re.sub(pattern,lambda _:line,body)
            else:body=body.rstrip()+'\n'+line+'\n\n'
        return text[:h.end()]+body+text[end:]
    return text.rstrip()+'\n\n['+table+']\n'+''.join(k+' = '+json.dumps(v)+'\n' for k,v in values.items())

def transform(text, palette, mode):
    before=tomllib.loads(text); expected=copy.deepcopy(before)
    desktop=expected.setdefault('desktop',{})
    key='appearanceDarkChromeTheme' if mode=='dark' else 'appearanceLightChromeTheme'
    theme=desktop.setdefault(key,{})
    values={'accent':palette['accent'],'accentSource':'custom','ink':palette['foreground'],'surface':palette['background']}
    values.setdefault('contrast',theme.get('contrast',60))
    values.setdefault('opaqueWindows',theme.get('opaqueWindows',False))
    semantic={'diffAdded':palette['green'],'diffRemoved':palette['red'],'skill':palette['magenta']}
    for v in [values['accent'],values['ink'],values['surface'],*semantic.values()]:
        if not re.fullmatch(r'#[0-9a-fA-F]{6}',v):raise ValueError('Invalid palette color')
    desktop['appearanceTheme']=mode
    theme.update(values); theme.setdefault('fonts',{}); theme.setdefault('semanticColors',{}).update(semantic)
    text=update_table(text,'desktop',{'appearanceTheme':mode})
    text=update_table(text,'desktop.'+key,values)
    text=update_table(text,'desktop.'+key+'.semanticColors',semantic)
    if not re.search(r'(?m)^\[desktop\.'+key+r'\.fonts\]\s*$',text):
        # Native settings use an empty table to represent default (null) fonts.
        if not theme['fonts']:text=update_table(text,'desktop.'+key+'.fonts',{})
    if tomllib.loads(text)!=expected:raise ValueError('Unexpected configuration change; refusing to write')
    return text

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--config',type=Path,default=Path.home()/'.codex/config.toml');ap.add_argument('--palette',type=Path,default=ROOT/'palette.json');ap.add_argument('--mode',choices=['dark','light']);args=ap.parse_args()
    with (ROOT/'sync.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        mode=args.mode or subprocess.check_output(['noctalia','msg','theme-mode-get'],text=True,timeout=15).strip()
        if mode not in ('dark','light'):raise ValueError('Unknown Noctalia mode: '+mode)
        palette=json.loads(args.palette.read_text())
        for attempt in range(3):
            before=args.config.read_bytes(); result=transform(before.decode(),palette,mode).encode()
            if result==before:return
            fd,tmp=tempfile.mkstemp(prefix='.appearance-',dir=args.config.parent)
            try:
                with os.fdopen(fd,'wb') as out:out.write(result)
                os.chmod(tmp,args.config.stat().st_mode & 0o777)
                if args.config.read_bytes()!=before:continue
                os.replace(tmp,args.config)
                return
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
        raise RuntimeError('Config kept changing; no update written')
if __name__=='__main__':main()
