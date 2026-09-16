"""Landscape revision in the original PDF's compact Helvetica list style.

Uses the same normalized BOM model as build-no-quantity-inputs.mjs.
Run: python scripts/build-compact-category-pdf.py
"""
import json
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import landscape, letter
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/NeoviBOM/_Internal/Legacy-Layouts/Neovi-Material-Categories-Compact-Landscape.pdf'
W, H = landscape(letter)
GRAY = colors.HexColor('#707070')
ITEM = ParagraphStyle('item', fontName='Helvetica', fontSize=8, leading=9.5, textColor=colors.HexColor('#303030'))
NOTE = ParagraphStyle('note', fontName='Helvetica', fontSize=6.8, leading=8.2, textColor=GRAY)
SUBTITLE = ParagraphStyle('subtitle', fontName='Helvetica', fontSize=8.5, leading=11, textColor=GRAY)

# Parallel row arrays map grouped descriptions back to real catalog identities.
# Unmapped additions never receive invented item IDs or approved quantities.
SOURCES = {
 'Site Setup & Shared Supplies': {'parts': [[1],[],[],[]], 'consumables': [[],[],['PAN-007','PAN-015','FIN-109'],[]], 'prefix':'FND'},
 'Helical Piles': {'parts': [[6,7],[8,9,10]], 'tools': [[11],[],[]], 'prefix':'FND'},
 'Steel Bedframe': {'parts': [[12],[15,14],[16,18],[19]], 'prefix':'FND'},
 'Floor': {'parts': [[2],[3,5],[6]], 'tools': [[1],[],[],[]], 'prefix':'PAN'},
 'Wall': {'parts': [[9],[12,10],[11],[13,14]], 'tools': [[8],[],[],[]], 'prefix':'PAN'},
 'Truss': {'parts': [[16],[17],[18],[19]], 'prefix':'PAN'},
 'Roof': {'parts': [[20],[21],[22]], 'tools': [[24],[],[],[]], 'consumables': [[23],[]], 'prefix':'PAN'},
 'Rough Electrical': {'parts': [[1,2,3,4,5,6],[7,12],[9,10,11],[13],[14]], 'prefix':'FIN'},
 'Finish Electrical': {'parts': [[57],[58],[59],[60],[61]], 'prefix':'FIN'},
 'Solar': {'parts': [[62,63,64],[65,66],[67,68]], 'prefix':'FIN'},
 'Rough Plumbing': {'parts': [[23,24,25],[34,35,36],[28,29,30,31,32],[26,27,33,42],[37,38,39,40,41]], 'prefix':'FIN'},
 'Finish Plumbing': {'parts': [[70,72,74,79],[75,76,77,80],[71,73,78],[81]], 'prefix':'FIN'},
 'Sewer & Vent': {'parts': [[44,45,46],[47],[48],[50,51]], 'tools': [[],[43,49],[],[]], 'prefix':'FIN'},
 'Fire Protection': {'parts': [[15,16,17],[18,69],[19,20],[21,22],[8]], 'prefix':'FIN'},
 'HVAC': {'parts': [[52],[53],[54],[55],[56]], 'prefix':'FIN'},
 'Low Voltage / Smart Home': {'parts': [[95],[96],[97],[98]], 'prefix':'FIN'},
 'Windows & Doors': {'parts': [[82],[84],[88],[86]], 'consumables': [[83],[85],[89],[90]], 'prefix':'FIN'},
 'Kitchen Cabinets': {'parts': [[],[93],[],[]], 'prefix':'FIN'},
 'Bathroom Vanity': {'parts': [[91],[92]], 'prefix':'FIN'},
 'Closets': {},
 'Flooring': {'parts': [[103],[104],[105]], 'consumables': [[101],[],[102]], 'prefix':'FIN'},
 'Truss Finish': {'parts': [[106],[107],[108]], 'prefix':'FIN'},
 'Exterior Finish': {'parts': [[110,115,116],[111,112,113,114],[117,118],[100]], 'prefix':'FIN'},
 'Ceiling': {'parts': [[99],[119],[120,121,122],[]], 'tools': [[124],[],[],[]], 'consumables': [[123],[125]], 'prefix':'FIN'},
 'Solid Surface Touch-Up': {},
 'Final Finishes': {'parts': [[],[],[87],[],[]], 'prefix':'FIN'},
}

def paragraph(text, width, style=ITEM):
    p = Paragraph(text, style)
    _, height = p.wrap(width, H)
    return p, height

def draw_text(c, text, x, top, width, style=ITEM):
    p, height = paragraph(text, width, style)
    p.drawOn(c, x, top-height)
    return height

def quantity(line):
    mode = line['sourceMode']
    key = line.get('inputKey', '').replace('_', ' ')
    if mode == 'DIRECT': parts = [f'Use {key}']
    elif mode == 'CALCULATED': parts = [f'Calculate from {key}']
    elif mode == 'FIXED': parts = ['Standard site item; confirm before shipment']
    else: parts = ['Confirm quantity to ship']
    if line['multiplier'] != 1: parts.append(f"{line['multiplier']:g} per source quantity")
    if line['sparePercent'] > 0: parts.append(f"include {line['sparePercent']*100:g}% spare")
    if line['minimumKitQty'] > 0: parts.append(f"minimum {line['minimumKitQty']:g}")
    return '; '.join(parts)

def source_ids(item, key, index):
    spec = SOURCES[item['title']]
    values = spec.get(key, [])
    values = values[index] if index < len(values) else []
    return [v if isinstance(v,str) else f"{spec['prefix']}-{v:03d}" for v in values]

def entry_content(item, key, index, text, catalog):
    refs = source_ids(item,key,index)
    label = f'<b>{escape(text)}</b>'
    notes = []
    if refs:
        # Item identifiers are hidden for now; retain the display code for later.
        # identity = ', '.join(f"{ref} | {'unit TBD' if ref in {'PAN-020', 'FIN-101'} else catalog[ref]['unit']}" for ref in refs)
        # label += f' <font size="6.8" color="#777777">({identity})</font>'
        active = [r for r in refs if catalog[r]['sourceMode'] != 'MANUAL']
        if 'PAN-020' in refs:
            notes.append('Confirm stud counts, lengths and heights; replaces area takeoff.')
        elif 'FIN-101' in refs:
            notes.append('Confirm abrasive type, unit and quantity; replaces sand / leveling material.')
        elif item['title'] == 'Ceiling' and index == 0 and key == 'parts':
            notes.append('Drywall: '+quantity(catalog['FIN-099'])+'. Screws: confirm count separately.')
        elif active:
            # notes.extend((r+': ' if len(refs)>1 else '')+quantity(catalog[r]) for r in active)
            notes.extend((catalog[r]['description']+': ' if len(refs)>1 else '')+quantity(catalog[r]) for r in active)
        else: notes.append('Confirm quantity to ship')
    return label, notes

def section(c, item, number, x, top, width, catalog, measure=False):
    if not measure:
        c.setFillColor(colors.HexColor('#222222'))
        c.setFont('Helvetica-Bold',9.8)
        c.drawString(x,top-10,f"{number}. {item['title']}")
        c.setFont('Helvetica',6.8)
        c.setFillColor(GRAY)
        c.drawRightString(x+width,top-10,item['stage'].replace('STAGE ','Stage ').replace('ALL STAGES','All stages'))
    top -= 20
    colx = x+5
    bottoms = []
    for fraction,key in zip([.51,.245,.245],['parts','tools','consumables']):
        colw = (width-5)*fraction
        contentw = colw-10
        if not measure:
            c.setFillColor(colors.HexColor('#1F4E78'))
            c.setFont('Helvetica-Bold',8)
            c.drawString(colx,top-8,key.title())
        y = top-16
        for i,entry in enumerate(item[key]):
            label,notes = entry_content(item,key,i,entry,catalog)
            p,ph = paragraph(label,contentw)
            if not measure: p.drawOn(c,colx,y-ph)
            y -= ph+1.2
            for note in notes:
                p,ph = paragraph(escape(note),contentw,NOTE)
                if not measure: p.drawOn(c,colx,y-ph)
                y -= ph
            if not measure:
                c.setStrokeColor(colors.HexColor('#E7E7E7'))
                c.setLineWidth(.25)
                c.line(colx,y-1.8,colx+contentw,y-1.8)
            y -= 5
        bottoms.append(y)
        colx += colw
    bottom = min(bottoms)
    if item.get('note'):
        note = item['note'].replace('Original quantity references: page 9.','').replace('Existing quantity rules: page 9.','')
        _,ph = paragraph(escape(note),width-10,NOTE)
        if not measure: draw_text(c,escape(note),x+5,bottom-3,width-10,NOTE)
        bottom -= ph+6
    return bottom-13

def page_header(c,title,number):
    c.setFillColor(colors.HexColor('#222222'))
    c.setFont('Helvetica-Bold',17)
    c.drawString(50,H-58,title)
    draw_text(c,'Detailed package contents  |  + Proposed addition; confirm with trade lead',50,H-65,W-100,SUBTITLE)
    c.setFillColor(colors.HexColor('#888888'))
    c.setFont('Helvetica',7)
    c.drawString(50,24,'Neovi Co. | Material Categories')
    c.drawRightString(W-50,24,str(number))

def build():
    data = json.loads((ROOT/'config/material-categories.json').read_text(encoding='utf-8'))
    result = subprocess.run(['node','--input-type=module','-e',
        "import {loadTemplateConfig} from './src/template-model.mjs'; console.log(JSON.stringify((await loadTemplateConfig()).lines));"],
        cwd=ROOT,check=True,capture_output=True,text=True,encoding='utf-8')
    catalog = {line['lineId']:line for line in json.loads(result.stdout)}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    c = canvas.Canvas(str(OUT),pagesize=(W,H))
    c.setTitle('Material Categories - Landscape')
    c.setAuthor('Neovi Co.')
    count = 0
    used_ids = []
    for n,page in enumerate(data['pages'],1):
        page_header(c,page['title'].upper(),n)
        rows = []
        for item in page['cards']:
            if not rows or rows[-1][0]['box'][1] != item['box'][1]: rows.append([])
            rows[-1].append(item)
        y = H-94
        for row in rows:
            width = (W-100-24*(len(row)-1))/len(row)
            heights = []
            for i,item in enumerate(row):
                count += 1
                x = 50+i*(width+24)
                bottom = section(c,item,count,x,y,width,catalog,measure=True)
                if bottom < 42: raise ValueError(f"Page {n} overflow at {item['title']}: {bottom:.1f}")
                section(c,item,count,x,y,width,catalog)
                heights.append(bottom)
                for key in ['parts','tools','consumables']:
                    for index in range(len(item[key])): used_ids.extend(source_ids(item,key,index))
            y = min(heights)
        c.showPage()
    removed = {'FND-013','FND-017','PAN-004'}
    replaced = {'FND-002','FND-003','FND-004','FND-005','FIN-094'}
    missing = set(catalog)-set(used_ids)-removed-replaced
    if missing: raise ValueError(f'Unaccounted source items: {sorted(missing)}')
    if len(used_ids) != len(set(used_ids)): raise ValueError('Source IDs duplicated across categories')
    c.save()
    print(f'{OUT}\n{len(data["pages"])} landscape pages; {count} categories; all {len(catalog)} original BOM rows accounted for.')

if __name__ == '__main__': build()
