#!/usr/bin/env python3
"""Connect a privately authorized tunnel; never save the runtime key."""
import argparse,getpass,os,pathlib,shlex,shutil,subprocess,sys
from paper_rag.config import config_path,read_config

def main():
    p=argparse.ArgumentParser();p.add_argument('--client',default=shutil.which('tunnel-client'));p.add_argument('--alias',default='scientific-library');a=p.parse_args()
    if not a.client:p.error('Install the official tunnel-client and pass --client /absolute/path')
    read_config()
    tunnel=input('Tunnel ID (from OpenAI Platform): ').strip()
    if not tunnel.startswith('tunnel_'):p.error('Expected tunnel_ ID')
    key=getpass.getpass('Runtime API key (hidden; not saved): ')
    if not key:p.error('Empty runtime key')
    env=os.environ.copy();env['CONTROL_PLANE_API_KEY']=key
    command=shlex.join(['env','PAPER_RAG_CONFIG='+str(config_path()),sys.executable,'-m','paper_rag.server'])
    subprocess.run([a.client,'runtimes','connect','--alias',a.alias,'--profile',a.alias,'--tunnel-id',tunnel,'--mcp-command',command,'--runtime-api-key','env:CONTROL_PLANE_API_KEY'],env=env,check=True)
    subprocess.run([a.client,'runtimes','status',a.alias,'--json'],env=env,check=True)
if __name__=='__main__':main()
