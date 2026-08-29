from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REGISTRY_PATH = Path(__file__).with_name("factories.json")

class SwitchboardError(RuntimeError): pass

def canonical_factory_id(factory_id:str,switchboard:dict[str,Any])->str:
    current=str(factory_id or '').strip(); aliases=dict(switchboard.get('aliases') or {}); seen=set()
    while current in aliases:
        if current in seen: raise SwitchboardError(f'factory alias cycle: {factory_id}')
        seen.add(current); current=str(aliases[current]).strip()
    return current

def load_switchboard(path:Path=REGISTRY_PATH)->dict[str,Any]:
    with path.open('r',encoding='utf-8') as handle:data=json.load(handle)
    if data.get('scope')!='switchboard_only':raise SwitchboardError('factory registry must remain switchboard_only')
    ids:set[str]=set()
    for factory in data.get('factories',[]):
        factory_id=str(factory.get('id') or '').strip()
        if not factory_id or factory_id in ids:raise SwitchboardError('factory ids must be unique and non-empty')
        ids.add(factory_id)
        if not str(factory.get('name') or '').strip():raise SwitchboardError(f'factory name required: {factory_id}')
        if not str(factory.get('target') or '').strip():raise SwitchboardError(f'factory target required: {factory_id}')
    aliases=data.get('aliases') or {}
    if not isinstance(aliases,dict):raise SwitchboardError('factory aliases must be an object')
    for alias,target in aliases.items():
        alias=str(alias).strip();target=str(target).strip()
        if not alias or alias in ids:raise SwitchboardError(f'invalid or colliding factory alias: {alias}')
        if target not in ids:raise SwitchboardError(f'factory alias target missing: {alias} -> {target}')
        canonical_factory_id(alias,data)
    return data

def start_packet(factory_id:str,switchboard:dict[str,Any])->dict[str,str]:
    canonical_id=canonical_factory_id(factory_id,switchboard)
    for factory in switchboard.get('factories',[]):
        if factory.get('id')!=canonical_id:continue
        signal=str(factory.get('signal') or switchboard.get('default_signal') or 'X')
        return {'factory_id':canonical_id,'requested_factory_id':str(factory_id),'name':str(factory['name']),'target':str(factory['target']),'signal':signal,'payload':(f'{signal} — RESUME THE EXISTING FACTORY. DO NOT RESTART. CONTINUE AUTONOMOUSLY WITH MAXIMUM SAFE AUTONOMY. A TURN OR TECHNICAL WINDOW END IS NOT A STOP CONDITION. FREEZE THE EXACT BATON AND RESUME THE NEXT EXECUTABLE ACTION UNTIL REAL COMPLETION OR A TRUE EXTERNAL BLOCKER.')}
    raise SwitchboardError(f'unknown factory: {factory_id}')

def list_switches(switchboard:dict[str,Any])->list[dict[str,str]]:
    default_signal=str(switchboard.get('default_signal') or 'X')
    return [{'factory_id':str(f['id']),'name':str(f['name']),'target':str(f['target']),'signal':str(f.get('signal') or default_signal)} for f in switchboard.get('factories',[])]

def main()->int:
    parser=argparse.ArgumentParser(description='Factory Cloud thin switchboard');parser.add_argument('factory_id',nargs='?',help='factory switch to turn on');parser.add_argument('--list',action='store_true',dest='list_all');parser.add_argument('--registry',type=Path,default=REGISTRY_PATH);args=parser.parse_args()
    try:
        switchboard=load_switchboard(args.registry)
        if args.list_all:result:Any=list_switches(switchboard)
        elif args.factory_id:result=start_packet(args.factory_id,switchboard)
        else:parser.error('provide factory_id or --list')
    except (OSError,json.JSONDecodeError,SwitchboardError) as exc:parser.error(str(exc))
    print(json.dumps(result,indent=2,ensure_ascii=False));return 0

if __name__=='__main__':raise SystemExit(main())
