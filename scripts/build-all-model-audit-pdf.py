"""Model-only audit matrix: every catalog item/unit across every export."""
import json,csv
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape,letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,LongTable,TableStyle,Spacer,PageBreak
root=Path('outputs/NeoviBOM/04-Audits/All-Models');reports=[json.loads(p.read_text()) for p in sorted(root.glob('*.audit.json'))]
verify=json.loads((root/'verification.json').read_text());catalog=json.load(open('outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json'))
standards=json.load(open('config/confirmed-site-standards.json'))
by_line={r['lineId']:r for r in catalog}
csv_path=root/'All-Models-Every-Item-Unit.csv'
with csv_path.open(encoding='utf-8-sig',newline='') as stream:
 reader=csv.DictReader(stream);fields=list(reader.fieldnames);csv_rows=list(reader)
for field in ['Catalog ID','Category Path']:
 if field not in fields:fields.append(field)
for row in csv_rows:
 line=by_line[row['Line']];row['Catalog ID']=line['catalogId'];row['Category Path']=' > '.join(line['categoryPath'])
with csv_path.open('w',encoding='utf-8-sig',newline='') as stream:
 writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(csv_rows)
style=ParagraphStyle('body',fontName='Helvetica',fontSize=7,leading=9)
head=ParagraphStyle('head',parent=style,textColor=colors.white,fontName='Helvetica-Bold')
title=ParagraphStyle('title',parent=style,fontName='Helvetica-Bold',fontSize=16,leading=19)
def p(x,s=style):return Paragraph(escape(str(x)),s)
def table(data,widths):
 t=LongTable([[p(v,head if i==0 else style) for v in row] for i,row in enumerate(data)],colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#223347')),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f1f4f7')]),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]));return t
story=[p('All models | Every item and unit audit',title),Spacer(1,8),p(f"{verify['models']} original Downloads exports; {verify['elementsScanned']:,} elements scanned; {verify['itemUnitChecks']:,} catalog item/unit checks. Verification: PASS."),Spacer(1,8),p('No planning estimates or quantities borrowed from other projects. Numbers are measured quantities, model-route quantities or derived per-device allowances; JSON evidence identifies each rule. Std marks your confirmed standards (3 pile-pin sets, 1 four-point strap set, 2 two-point lifts), which are not model measurements. N/A means no resolved source-to-item quantity, not zero and not proof that the item is absent.'),Spacer(1,8)]
sources=[['Model ID','Project / original source','Elements','Mapped lines']]
for i,r in enumerate(reports):sources.append([f'M{i+1}',Path(r['source']).name,r['elementsScanned'],len(r['mapped'])])
story += [table(sources,[45,510,85,85]),Spacer(1,8),p('Unit checks inspect typed instance length, area, volume or mass parameters; EA uses unique instances. A compatible physical unit alone does not establish material or installation scope. DAY requires scheduling inputs. Model dimensions are in FT; floor areas are SQFT. CSV contains all candidate counts, exclusions, unit results, missing requirements and mapping status.'),Spacer(1,8),p('Circuit exception: assigned, nonphased power circuits are included; spare circuit rows are excluded. Circuit cable sizes and routes do not prove MC construction. Imported wood-floor names can conflict with stone material metadata, so names alone are not treated as floorboard takeoffs.'),PageBreak(),p(f'{len(catalog)} catalog rows x {len(reports)} models',title),Spacer(1,8)]
rows=[['Section / Line','Item / Phase','Unit']+[f'M{i+1}' for i in range(len(reports))]]
for line in sorted(catalog,key=lambda l:(l['deliveryStage'],[int(x) for x in l['categorySection'].split('.')],l['lineId'])):
 values=[]
 for r in reports:
  e=r['mapped'].get(line['lineId']);values.append(f"{e['value']:.2f}" if e else f"Std {line['fixedQty']:g}" if line['lineId'] in standards else 'N/A')
 rows.append([line['catalogId']+' / '+line['categorySection']+' / '+line['lineId'],line['description']+' | '+line['phase']+' | '+' > '.join(line['categoryPath']),line['unit']]+values)
story.append(table(rows,[75,155,35]+[46]*len(reports)))
def footer(c,d):
 c.setFont('Helvetica',7);c.drawString(24,18,'All units shown beside items. Model IDs refer to the source register on page 1. Estimates are excluded.');c.drawRightString(765,18,str(d.page))
SimpleDocTemplate(str(root/'All-Models-Item-Unit-Audit.pdf'),pagesize=landscape(letter),leftMargin=24,rightMargin=24,topMargin=24,bottomMargin=35).build(story,onFirstPage=footer,onLaterPages=footer)
print('Built model-only item/unit audit PDF')
