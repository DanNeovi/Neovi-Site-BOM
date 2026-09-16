"""Reconcile every nonempty supplied-list cell to the catalog or a stated disposition."""
import csv,json
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'outputs/NeoviBOM/04-Audits'
links=defaultdict(list)
def put(row,col,*ids):links[f'{row}:{col}'].extend(ids)
def seq(rows,col,prefix,start):
 for n,row in enumerate(rows):put(row,col,f'{prefix}-{start+n:03d}')
seq([3,4,5],13,'FND',3)
put(2,13,'FND-002');put(3,2,'FND-006','FND-007');put(4,2,'FND-008');put(5,2,'FND-009');put(6,2,'FND-011');put(2,7,'FND-011');put(9,8,'FND-009');put(12,7,'FND-001')
for row,num in [(9,14),(10,15),(11,16),(12,17),(13,18),(14,19)]:put(row,2,f'FND-{num:03d}')
for row,num in [(17,1),(18,2),(19,6),(20,7),(21,3),(22,4),(23,5),(26,8),(27,9),(28,10),(29,12),(30,11),(31,13),(32,14),(33,15),(35,16),(36,17),(37,19),(38,18),(41,20),(42,21),(43,23),(44,24),(45,22)]:put(row,2,f'PAN-{num:03d}')
put(21,7,'PAN-012');put(22,8,'PAN-012');put(23,7,'PAN-010');put(21,5,'PAN-029','PAN-013');put(35,7,'FIN-107');put(36,7,'FIN-109');put(19,8,'PAN-025')
seq(range(49,63),3,'FIN',1)
seq(range(49,54),8,'FIN',57);seq(range(57,64),8,'FIN',62)
seq(range(68,72),4,'FIN',15);seq(range(73,77),4,'FIN',19);put(68,8,'FIN-069')
seq(range(79,90),4,'FIN',23);seq(range(91,100),4,'FIN',34);seq(range(101,108),4,'FIN',43)
seq([110,111],4,'FIN',50);seq(range(115,120),3,'FIN',52)
seq([79,80],8,'FIN',70);seq([91,92,93],8,'FIN',72);put(94,8,'FIN-078');put(97,8,'FIN-045')
seq(range(101,107),9,'FIN',75);put(110,9,'FIN-081')
seq(range(123,127),3,'FIN',82);put(127,2,'FIN-086');seq(range(130,134),3,'FIN',87)
put(138,3,'FIN-091');put(139,3,'FIN-092');put(142,3,'FIN-093');put(145,2,'FIN-094')
seq(range(150,154),2,'FIN',95);put(158,3,'FIN-099');put(160,2,'FIN-100');seq(range(164,169),2,'FIN',101);seq(range(171,175),2,'FIN',106)
for row,num in [(177,110),(178,111),(179,115),(180,116),(181,112),(182,113),(183,114),(184,117),(185,118)]:put(row,2,f'FIN-{num:03d}')
seq(range(188,195),2,'FIN',119)
# Repeat occurrences of shared equipment remain linked to one purchasable item.
put(50,4,'PAN-043');put(56,4,'FND-030');put(177,4,'PAN-044');put(178,4,'FND-026','FND-030');put(134,3,'FIN-162')
additions=json.loads((ROOT/'config/additions-2026-09-15.json').read_text())
for r in additions:
 for cell in r['sourceCells'].split(';'):
  if cell.strip():links[cell.strip()].append(r['lineId'])
headers={'Foundation','Tools','Equipment','Helical Piles','Useful','Steel Bedframe','Panels','Floors','Walls','Trusses','Roof Panels','Finishing','Rough MEP','Finish MEP','Electrical','Solar?','Plumbing','Fire','Hot Water','Cold Water','Sewer','Vent','Mechanical','Windows and Doors','Doors','Windows','Cabinets','Bathroom','Kitchen','Low Voltage','General','Drywall','Flooring','Truss Area Finish','Gutter / Fascia','Ceiling','Solid Sruface'}
reviews={
 '3:2':'Different pile types and extensions are represented, but sizes/types still require a pile schedule.',
 '21:5':'Bolts and washer/nut assemblies are represented. Source lists them beside floor tools; confirm floor-versus-wall hold-down scope before allocating quantities.',
 '31:7':'CB interpreted as cement board; confirm abbreviation and scope.',
 '35:7':'Provisionally linked to existing truss-area concrete board. Confirm this is the same material and whether needed during Stage 2 erection or Stage 3 finishing.',
 '36:7':'Provisionally linked to existing truss-area foam. Confirm whether this is the same product and erection versus finish scope.',
 '81:5':'Red tool is retained, but exact tool/product is unidentified.',
 '89:8':'Fan cover provisionally classified as HVAC finish; source location alone does not identify the fan.',
 '103:4':'Original typo interpreted as flush buttons/trim, matching the later Toilet Buttons entry; confirm it does not mean a separate toilet base/trim product.',
 '164:2':'Sand and level may describe sanding work rather than a bulk sand material. Existing leveling item and new sanding tools cover candidates; confirm intended material.',
}
def build():
 catalog={r['lineId']:r for r in json.loads((ROOT/'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())}
 retired=json.loads((ROOT/'config/catalog-revision-2026-09-15.json').read_text())['retired']
 rows=[]
 for row,line in enumerate((ROOT/'config/supplied-item-list-2026-09-15.tsv').read_text().splitlines(),1):
  for col,raw in enumerate(line.split('\t')):
   text=raw.strip()
   if not text:continue
   cell=f'{row}:{col}';ids=list(dict.fromkeys(links.get(cell,[])))
   if ids:
    original=ids
    ids=list(dict.fromkeys(j for i in original for j in (retired[i]['replacements'] if i in retired else [i])))
    assert all(i in catalog for i in ids),(cell,ids)
    if any(i in retired for i in original):
     status='SUPERSEDED BY USER' if ids else 'EXCLUDED BY USER'
     note='; '.join(retired[i]['reason'] for i in original if i in retired)
    else:
     status='NEEDS CLARIFICATION' if cell in reviews else 'COVERED'
     note=reviews.get(cell,'Represented in catalog. Repeated uses share the same item ID; accessories and kit contents must not be purchased twice.')
   elif cell=='8:2':status='EXCLUDED BY USER';note='Welding consumables were explicitly removed; not silently restored.'
   elif col==0 and row in [80,81,82]:status='SPECIFICATION REQUIREMENT';note='Record pipe size/material, fitting type and manufacturer/model in Specification and Part Number; selections are not provided by this list.'
   elif text in headers:status='SECTION HEADING';note='Organizational label, not a separate purchasable item.'
   else:status='UNACCOUNTED';note='Requires reconciliation.'
   rows.append({'Source Cell':cell,'Source Text':text,'Status':status,'Item IDs':'; '.join(ids),'Catalog Items':'; '.join(catalog[i]['description'] for i in ids),'Units':'; '.join(catalog[i]['unit'] for i in ids),'Sections / Stages':'; '.join(catalog[i]['categorySection']+' / Stage '+catalog[i]['deliveryStage'] for i in ids),'Specific Categories':'; '.join(catalog[i]['system'] for i in ids),'Disposition / Review':note})
 DEST.mkdir(parents=True,exist_ok=True)
 with (DEST/'Source-List-Completeness-Audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 print(dict(Counter(r['Status'] for r in rows)))
 for r in rows:
  if r['Status']=='UNACCOUNTED':print(r['Source Cell'],r['Source Text'])
 assert not any(r['Status']=='UNACCOUNTED' for r in rows), 'Unaccounted source entries remain'
 assert len({r['Source Cell'] for r in rows})==len(rows)
 counts=Counter(r['Status'] for r in rows)
 findings=[r for r in rows if r['Status']=='NEEDS CLARIFICATION']
 report=['# Supplied-list completeness audit','',
  f'Compared the supplied list with the current {len(catalog)}-item catalog, including the subsequent annotated PDF and explicit removals.',
  '',f"All {len(rows)} nonempty source cells are accounted for: {dict(counts)}.",
  '', 'No clearly missing catalog item was found. Coverage is not confirmation of specifications, quantities, kit contents, or the completeness of the construction scope.',
  '', '## Clarifications remaining','']
 for r in findings: report.append(f"- **{r['Source Text']}** ({r['Item IDs']}): {r['Disposition / Review']}")
 report+=['','## Traceability','',
  'Source-List-Completeness-Audit.csv records every nonempty source cell, item IDs, catalog descriptions, units, numbered sections/stages, specific categories and disposition. Source cells use one-based row numbers and zero-based column numbers.',
  '', 'Repeated tools are linked to the same catalog item. Pipe/fitting sizes and model numbers remain specification requirements. Welding consumables stay excluded as requested. No quantities were invented.']
 (DEST/'Source-List-Completeness-Audit.md').write_text('\n'.join(report)+'\n',encoding='utf-8')
 from reportlab.lib import colors
 from reportlab.lib.styles import ParagraphStyle
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
 from xml.sax.saxutils import escape
 body=ParagraphStyle('body',fontName='Helvetica',fontSize=9,leading=12)
 title=ParagraphStyle('title',parent=body,fontName='Helvetica-Bold',fontSize=17,leading=21)
 p=lambda s:Paragraph(escape(s),body)
 story=[Paragraph('NeoviBOM | Supplied-List Completeness Audit',title),Spacer(1,10),p(report[2]),Spacer(1,8),p(report[4]),Spacer(1,8),p(report[6]),Spacer(1,12),Paragraph('Items needing clarification',title),Spacer(1,8)]
 data=[[p('Source entry / catalog IDs'),p('Unresolved interpretation')]]
 for r in findings:data.append([p(r['Source Text']+' / '+r['Item IDs']),p(r['Disposition / Review'])])
 table=Table(data,colWidths=[170,370],repeatRows=1)
 table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DFE7EE')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F3F6F8')]),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
 story+=[table,Spacer(1,12),p(report[-3]),Spacer(1,8),p(report[-1])]
 def footer(c,d):
  c.setFont('Helvetica',7);c.drawString(36,20,'Scope: reconciliation to the supplied list; not a complete construction procurement review.');c.drawRightString(576,20,str(d.page))
 SimpleDocTemplate(str(DEST/'Source-List-Completeness-Audit.pdf'),leftMargin=36,rightMargin=36,topMargin=30,bottomMargin=36,pagesize=(612,792)).build(story,onFirstPage=footer,onLaterPages=footer)
 return rows
if __name__=='__main__':build()
