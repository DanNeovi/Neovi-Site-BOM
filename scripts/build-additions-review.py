"""Publish the supplied additions with stable section numbers and specific categories."""
import csv
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'outputs/NeoviBOM/04-Audits/History'

def build():
    catalog = json.loads((ROOT/'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())
    additions = {r['lineId']: r for r in json.loads((ROOT/'config/additions-2026-09-15.json').read_text())}
    selected = sorted((r for r in catalog if r['lineId'] in additions), key=lambda r: (tuple(map(int,r['categorySection'].split('.'))),r['system'],r['lineId']))
    retired=json.loads((ROOT/'config/catalog-revision-2026-09-15.json').read_text())['retired']
    assert {r['lineId'] for r in selected} == set(additions)-set(retired)
    DEST.mkdir(parents=True,exist_ok=True)
    with (DEST/'New-Items-by-Category.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f)
        w.writerow(['Section','Stage','Phase','Work Area','Category','Specific Category','Line ID','Item','Unit','Notes','Source Cells'])
        for r in selected:
            a=additions[r['lineId']]
            w.writerow([r['categorySection'],r['deliveryStage'],r['phase'],r['stage'],' > '.join(r['categoryPath']),r['system'],r['catalogId']+' / '+r['lineId'],r['description'],r['unit'],r['itemNotes'],a['sourceCells']])
    body=ParagraphStyle('body',fontName='Helvetica',fontSize=8,leading=10,textColor=colors.HexColor('#223347'))
    head=ParagraphStyle('head',parent=body,fontName='Helvetica-Bold',textColor=colors.white)
    title=ParagraphStyle('title',parent=body,fontName='Helvetica-Bold',fontSize=17,leading=21)
    p=lambda text,style=body:Paragraph(escape(str(text)),style)
    story=[p('NeoviBOM | Earlier Additions - Active Items',title),Spacer(1,8),p(f'{len(selected)} retained from the earlier additions | {len(catalog)} total active catalog items | Updated September 15, 2026'),Spacer(1,5),p('Subsequent removals are excluded. For the latest changes and new items see 04-Audits/Catalog-Changes.csv; the full collection is in 03-Categories. Quantities require takeoff or crew requirements.'),Spacer(1,10)]
    rows=[[p(t,head) for t in ['Section / Line','Phase / Stage / Work Area','Specific Category','Item / Unit','Notes']]]
    for r in selected:
        rows.append([p(r['catalogId']+' / '+r['lineId']),p(f"{r['phase']} / Stage {r['deliveryStage']} / {r['categorySection']} {r['stage']}"),p(' > '.join(r['categoryPath'])),p(r['description']+' / '+r['unit']),p(r['itemNotes'])])
    table=LongTable(rows,colWidths=[78,133,140,170,211],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#223347')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F0F4F7')]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(table)
    def footer(canvas,doc):
        canvas.setFont('Helvetica',7)
        canvas.drawString(30,19,'New additions only. Full catalog and project calculations are in the companion PDFs.')
        canvas.drawRightString(762,19,str(doc.page))
    SimpleDocTemplate(str(DEST/'New-Items-by-Category.pdf'),pagesize=landscape(letter),leftMargin=30,rightMargin=30,topMargin=26,bottomMargin=34).build(story,onFirstPage=footer,onLaterPages=footer)
    print(f'Published {len(selected)} retained earlier additions: PDF and CSV')

if __name__=='__main__':
    build()
