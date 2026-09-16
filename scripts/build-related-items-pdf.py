"""Build a complete, side-by-side catalog grouped by trade and specific system."""
import json
import csv
import re
import shutil
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT/'outputs/NeoviBOM'
OUT = ROOT/'outputs/NeoviBOM/01-Catalog/Neovi-All-Related-Items-Side-by-Side.pdf'
INK = colors.HexColor('#223347')
BODY = ParagraphStyle('body', fontName='Helvetica', fontSize=8, leading=9.5, textColor=INK)
TITLE = ParagraphStyle('title', parent=BODY, fontName='Helvetica-Bold', fontSize=16, leading=19, keepWithNext=True)
SUB = ParagraphStyle('sub', parent=BODY, fontName='Helvetica-Bold', fontSize=11, leading=15, keepWithNext=True, spaceBefore=10, spaceAfter=5)
LABELS = {'Sitework':'Site Setup & Shared Tools', 'Structural':'Foundations, Panels & Structural', 'Electrical':'Electrical, Solar & Low Voltage', 'Plumbing':'Water, Sanitary & Vent', 'Fire Protection':'Fire Protection', 'Mechanical':'HVAC & Mechanical', 'Building Envelope':'Roof, Gutters, Fascia & Envelope', 'Doors & Windows':'Doors, Windows & Shades', 'Interior Finishes':'Interiors, Flooring, Ceilings & Solid Surface'}

def card(r):
    if r.get('takeoffFormula'):
        basis=r['takeoffFormula']
    elif r['sourceMode']=='FIXED':
        basis=f"{r['fixedQty']:g} {r['unit']} (catalog standard)"
    elif r['sourceMode']=='MANUAL':
        basis=f"entered measured / counted takeoff in {r['unit']}"
    else:
        basis=f"SUM({r['inputKey'].replace('_',' ')}) x {r['multiplier']:g}"
    return Paragraph(
        f"<font size='7' color='#53616E'>{escape(' > '.join(r['categoryPath'][1:]))}</font><br/>"
        f"<b>{r['catalogId']} | {escape(r['description'])}</b> | {r['unit']}<br/>"
        f"<font size='7' color='#53616E'>{r['categorySection']} / {r['lineId']} | Phase: {escape(r['phase'])} | Stage: {r['deliveryStage']} | {escape(r['stage'])}</font><br/>"
        f"<font size='7'>Required Quantity = {escape(basis)}<br/>"
        f"Spare: {r['sparePercent']*100:g}% | Minimum kit: {r['minimumKitQty']:g} | Pack: {r['packSize']:g} | Round up to: {r['quantityIncrement']:g}<br/>"
        f"{escape(r['itemNotes'])}"
        + ('<br/>Variants: '+escape('; '.join(v['catalogId']+' '+v['description'] for v in r['variants'])) if r.get('variants') else '')
        + '</font>', BODY)

def build():
    catalog=json.loads((ROOT/'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())
    grouped=defaultdict(lambda: defaultdict(list))
    for r in catalog: grouped[r['categoryPath'][0]][' > '.join(r['categoryPath'][1:])].append(r)
    story=[]; used=[]
    for trade in sorted(grouped):
        label=trade
        if not grouped[trade]: continue
        if story: story.append(PageBreak())
        story += [Paragraph(escape(label),TITLE),Spacer(1,5),Paragraph(f"{sum(map(len,grouped[trade].values()))} related items | Complete catalog, including the latest additions",BODY),Spacer(1,4)]
        ordered=[]
        for system,items in sorted(grouped[trade].items()):
            items.sort(key=lambda r:(int(r['deliveryStage']),r['phaseOrder'],r['lineId']))
            ordered.extend(items)
        # Keep related drilling and bedframe parts next to each other on the page.
        priority={lid:n for n,lid in enumerate(['FND-046','FND-047','FND-048','FND-055','FND-056','FND-057','FND-014','FND-015','FND-058','FND-016'])}
        ordered.sort(key=lambda r:(r['categoryPath'][1], 0 if r['lineId'] in priority else 1, priority.get(r['lineId'],0), ' > '.join(r['categoryPath'][2:]),int(r['deliveryStage']),r['lineId']))
        rows=[]
        batch=[]; previous=None
        for r in ordered:
            parent=r['categoryPath'][1]
            if batch and parent!=previous and (parent in ('Magnetic Drill','Steel Bedframe') or previous in ('Magnetic Drill','Steel Bedframe')):
                rows.append([card(v) for v in batch]+['']*(3-len(batch)));batch=[]
            batch.append(r);used.append(r['lineId']);previous=parent
            if len(batch)==3:rows.append([card(v) for v in batch]);batch=[]
        if batch:rows.append([card(v) for v in batch]+['']*(3-len(batch)))
        t=Table(rows,colWidths=[244,244,244],hAlign='LEFT')
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#F0F4F7')),('LINEBEFORE',(1,0),(1,-1),5,colors.white),('LINEBEFORE',(2,0),(2,-1),5,colors.white),('LINEBELOW',(0,0),(-1,-1),4,colors.white),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6)]))
        story.append(t)
        category_out=DEST/'03-Categories'/safe_name(trade)
        category_out.mkdir(parents=True,exist_ok=True)
        # Build a fresh table: ReportLab flowables are consumed during layout.
        import copy
        SimpleDocTemplate(str(category_out/'Related-Items.pdf'),pagesize=landscape(letter),leftMargin=30,rightMargin=30,topMargin=25,bottomMargin=35).build([Paragraph(escape(label),TITLE),Spacer(1,8),copy.deepcopy(t)])
    assert len(used)==len(set(used))==len(catalog)
    def footer(c,d):
        c.setFont('Helvetica',7); c.setFillColor(INK)
        c.drawString(30,23,'Formula reference. See the Formula Guide for full kit and order math; project PDFs contain quantities and source status.')
        c.drawRightString(762,23,str(d.page))
    OUT.parent.mkdir(parents=True,exist_ok=True)
    SimpleDocTemplate(str(OUT),pagesize=landscape(letter),leftMargin=30,rightMargin=30,topMargin=25,bottomMargin=40,title='Neovi - All Related Items Side by Side').build(story,onFirstPage=footer,onLaterPages=footer)
    DEST.mkdir(parents=True,exist_ok=True)
    projects=json.loads((ROOT/'outputs/NeoviBOM/_Internal/Model-Data/full-project-calculations.json').read_text())['projects']
    project_rows={('Santa Rita' if 'Santa Rita' in p['project'] else 'Franklin'):{r['lineId']:r for r in p['rows']} for p in projects}
    folders=defaultdict(list)
    for r in catalog:folders[tuple(r['categoryPath'])].append(r)
    index=[]
    for category_path,items in sorted(folders.items()):
        folder=DEST/'03-Categories'
        for part in category_path:folder/=safe_name(part)
        folder.mkdir(parents=True,exist_ok=True)
        fields=['Catalog ID','Category Path','Legacy Line ID','Item','Unit','Phase','Stage','Section','Required Formula','Spare Percent','Minimum Kit','Pack Size','Procurement','Optional','Specification','Notes','Franklin Required','Franklin Estimate','Santa Rita Required','Santa Rita Estimate']
        with (folder/'Items.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.writer(f);w.writerow(fields)
            for r in items:
                basis=r.get('takeoffFormula') or (f"{r['fixedQty']} {r['unit']}" if r['sourceMode']=='FIXED' else 'SUM('+r['inputKey']+') x '+str(r['multiplier']) if r['inputKey'] else 'Entered takeoff')
                values=[]
                for name in ['Franklin','Santa Rita']:
                    pr=project_rows[name][r['lineId']]
                    values.extend(pr[k] if pr[k] is not None else 'N/A' for k in ['required','planningEstimate'])
                w.writerow([r['catalogId'],' > '.join(category_path),r['lineId'],r['description'],r['unit'],r['phase'],r['deliveryStage'],r['categorySection'],basis,r['sparePercent'],r['minimumKitQty'],r['packSize'],r['procurementMethod'],r['optional'],r['specification'],r['itemNotes'],*values])
                index.append([r['catalogId'],r['lineId'],r['description'],' > '.join(category_path),str((folder/'Items.csv').relative_to(DEST))])
                if r.get('variants'):
                    with (folder/(r['catalogId']+'-Length-Variants.csv')).open('w',encoding='utf-8-sig',newline='') as vf:
                        vw=csv.writer(vf);vw.writerow(['Variant ID','Parent Catalog ID','Description','Length FT','Required Qty EA','Rated Load','Note'])
                        for v in r['variants']:
                            vw.writerow([v['catalogId'],r['catalogId'],v['description'],v['lengthFt'],'','','Enter quantities by variant; parent is the combined total, not an additional order.'])
                            index.append([v['catalogId'],r['lineId']+' / '+v['key'],v['description'],' > '.join(category_path),str((folder/(r['catalogId']+'-Length-Variants.csv')).relative_to(DEST))])
    with (DEST/'01-Catalog/Catalog-Folder-Index.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['Catalog ID','Legacy Line ID','Item','Category Path','File']);w.writerows(index)
    (DEST/'03-Categories/READ-ME.txt').write_text('Open a category folder for its Related-Items.pdf. Continue into subfolders for Items.csv with formulas and separate Franklin / Santa Rita quantities.\n\nCatalog IDs are permanent: TOOL = tools, FIX = fixtures, FAST = fasteners, RIG = rigging, EQUIP = equipment, SUP = supplies, MAT = materials/components. Numbers are append-only decimal strings with no fixed digit limit. Legacy FND/PAN/FIN references and phase/stage sections remain visible.\n\nEdit config/site-bom.template.json: supply categoryPath and inventoryPrefix, then run node scripts/sync-catalog-identities.mjs. Existing IDs do not change when folders move; deleted IDs remain reserved in config/catalog-identities.json. Rebuild with python scripts/rebuild-project-reports.py --package.\n\nLifting strap length is unspecified. Add size variants only after the actual requirements are confirmed; specify rated load and configuration.\n',encoding='utf-8')
    print(f'Built {OUT.name}: {len(used)} items in {len(grouped)} category roots / {len(folders)} folders')

def safe_name(s):
    return re.sub(r'[<>:"/\\|?*]','-',s).strip().rstrip('.')

if __name__=='__main__': build()
