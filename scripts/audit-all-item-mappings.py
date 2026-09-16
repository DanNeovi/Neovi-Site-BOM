"""Audit all 275 explicit selectors, keeping missing inputs and source evidence visible."""
import collections
import csv
import json
import re
from pathlib import Path
from model_takeoff_rules import select_unique

root=Path(__file__).resolve().parents[1]
folder=root/'outputs/NeoviBOM/_Internal/Model-Data'
register=json.loads((root/'config/model-item-mapping-register.json').read_text())
catalog=json.loads((folder/'catalog-lines.json').read_text())
assert set(register)=={r['lineId'] for r in catalog}
for slug in ('franklin','santa-rita'):
    raw=json.loads((folder/f'{slug}-takeoff-elements.json').read_text())
    elements=select_unique(raw)
    mapped=json.loads((folder/f'{slug}-mapped-takeoffs.json').read_text())
    # Search identity and description parameters only; parameter names such as
    # "Assembly Code" must not make every element match a product search.
    searchable=[]
    for e in elements:
        text=' '.join(str(e.get(k,'')) for k in ('category','family','type','name'))
        text+=' '+' '.join(str(p.get('displayValue','')) for p in e.get('parameters',[]) if p.get('hasValue') and p.get('name') in ('Description','BIMSF_Description','Part Description','Part Number','System Name','System Type','Material','Cable Size','Cable Type','Load Name','IFC Material Name'))
        text=re.sub(r'(?<=[a-z])(?=[A-Z])',' ',text).replace('_',' ')
        searchable.append((e,text))
    audits=[]
    for line in catalog:
        lid=line['lineId']; rule=register[lid]
        candidates=[e for e,text in searchable if e.get('category') in rule['categories'] and any(re.search(r'\b(?:'+pattern+r')',text,re.I) for pattern in rule['search'])]
        groups=collections.Counter((e.get('category',''),e.get('family',''),e.get('type',''),e.get('sourceKey','')) for e in candidates)
        evidence=mapped.get(lid)
        if evidence and evidence.get('status')=='CONFIRMED_STANDARD':
            candidates=[];groups=collections.Counter()
        if evidence:
            status=evidence.get('status','DERIVED_ALLOWANCE' if lid in ('PAN-013','FIN-046','FIN-052') else 'MODEL_MEASURED')
            reason=evidence['description']
            if lid=='PAN-002': reason+='; base kit uses catalog minimum 250, but the noted 100-versus-250 minimum remains unresolved.'
        elif line['description'].startswith('Define ') or lid == 'FIN-045':
            status='ITEM_DEFINITION_REQUIRED';reason=rule['requirement']
        elif line['sourceMode']=='FIXED':
            status='CATALOG_ALLOWANCE';reason=rule['requirement']
        elif not candidates:
            status='NO_IDENTIFIED_SOURCE';reason='No eligible named source matched the item search. '+rule['requirement']
        else:
            status='SOURCE_FOUND_INPUTS_REQUIRED';reason=rule['requirement']
        if lid=='FIN-082' and not evidence and candidates:
            reason='Exterior classification incomplete/conflicting: some door names indicate exterior but Function is Interior or missing. Correct opening classification before sill-pan count.'
        if lid=='FIN-099' and not evidence:
            reason='No gypsum ceiling passed the garage room footprint/material check. Stretch-ceiling area cannot be substituted for garage drywall.'
        if not evidence and lid in ('FND-006','FND-007','FND-008','FND-009','FND-010'):
            if not any(e.get('category')=='Structural Foundations' for e in elements):
                reason+=' No Structural Foundations instances in scanned categories; beam saddles do not establish helical piles.'
        if lid=='PAN-006' and not evidence:
            reason='Floor clips contain Leg 1/2 Number of Fasteners, but fastener type fields are blank. Counts cannot identify the specified floor screws.'
        audit=dict(lineId=lid,item=line['description'],phase=line['phase'],stage=line['deliveryStage'],categorySection=line['categorySection'],
                   status=status,requirement=rule['requirement'],search=rule['search'],reason=reason,candidateCount=len(candidates),
                   sourceGroups=[dict(category=k[0],family=k[1],type=k[2],sourceKey=k[3],count=v) for k,v in groups.items()],
                   candidateKeys=[e['key'] for e in candidates],mappedQuantity=evidence['value'] if evidence else None,
                   catalogAllowance=line['fixedQty'] if line['sourceMode']=='FIXED' else None)
        audits.append(audit)
    (folder/f'{slug}-all-item-mapping-audit.json').write_text(json.dumps(audits,indent=2))
    with (folder/f'{slug}-mapping-audit.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.writer(f);writer.writerow(['Line','Item','Phase','Stage','Section','Status','Mapped Quantity','Catalog Allowance','Candidate Elements (not quantity)','Requirement','Source Types'])
        for a in audits:
            writer.writerow([a['lineId'],a['item'],a['phase'],a['stage'],a['categorySection'],a['status'],a['mappedQuantity'] if a['mappedQuantity'] is not None else 'N/A',a['catalogAllowance'] if a['catalogAllowance'] is not None else 'N/A',a['candidateCount'],a['requirement'],'; '.join(f"{g['family']} / {g['type']}: {g['count']}" for g in a['sourceGroups'])])
    print(slug,dict(collections.Counter(a['status'] for a in audits)))
