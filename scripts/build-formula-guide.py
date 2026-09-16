"""Build a compact item-by-item formula PDF from the same normalized BOM catalog."""
import json
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, PageBreak, KeepTogether

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/NeoviBOM/01-Catalog/Neovi-Site-BOM-Formula-Guide.pdf'
PAGE = landscape(letter)
INK = colors.HexColor('#223347')
MUTED = colors.HexColor('#53616E')
STYLES = {
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=17, leading=21, textColor=INK, spaceAfter=5),
    'section': ParagraphStyle('section', fontName='Helvetica-Bold', fontSize=11, leading=15, textColor=INK, spaceBefore=8, spaceAfter=7, keepWithNext=True),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9, leading=12, textColor=INK),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=8, leading=10, textColor=MUTED),
    'item': ParagraphStyle('item', fontName='Helvetica', fontSize=8.6, leading=10.5, textColor=INK),
    'formula': ParagraphStyle('formula', fontName='Helvetica', fontSize=8, leading=10, textColor=MUTED),
    'head': ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white),
}


def p(text, style='body'):
    for short,full in {'R':'Required Quantity','E':'Manual Extra Quantity'}.items():
        text=re.sub(r'\b'+short+r'\b',full,text)
    text=re.sub(r'(?<!Round )\bup\(', 'Round up(', text)
    return Paragraph(text, STYLES[style])


def base(line):
    if line.get('takeoffFormula'):return 'R = '+escape(line['takeoffFormula'])
    if line['sourceMode'] == 'FIXED':
        return f"R = {line['fixedQty']:g} (fixed)"
    if line['sourceMode'] == 'MANUAL':
        return 'R = entered takeoff'
    key = line['inputKey'].replace('_', ' ')
    return f"R = sum({escape(key)}) x {line['multiplier']:g}"


def footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor('#D9DFE4'))
    canvas.line(30, 31, PAGE[0]-30, 31)
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(30, 19, 'NEOVI  /  SITE BOM 0.4.0  /  Formula reference - quantities and specifications need project review')
    canvas.drawRightString(PAGE[0]-30, 19, str(doc.page))
    canvas.restoreState()


def build():
    raw = subprocess.check_output(['node', '--input-type=module', '-e',
        "import {loadTemplateConfig} from './src/template-model.mjs'; const {lines}=await loadTemplateConfig(); console.log(JSON.stringify(lines));"], cwd=ROOT, text=True, encoding='utf-8')
    lines = json.loads(raw)
    widths = [70, 177, 33, 215, 55, 55, 45, 49]
    story = [p('Neovi Site BOM | Formula Guide', 'title'),
             p(f'{len(lines)} items - permanent IDs and category paths; numbered work categories retain phase and delivery stage. The CSV contains full explanations.', 'small'), Spacer(1, 8),
             p('<b>Required Quantity</b> is the installation quantity before spares. <b>Manual Extra Quantity</b> is an entered addition. Round up(value, step) rounds to the next multiple.', 'small'),
             p('<b>Spare</b> = up(R x spare %, increment). <b>Kit</b> = up(MAX(R + Spare + E, minimum kit), increment).', 'small'),
             p('<b>Net</b> = MAX(0, sum of all kits for an Item ID + target stock - on hand - already committed).', 'small'),
             p('<b>Order</b> = 0 when Net is 0; otherwise up(MAX(Net, minimum order), pack). <b>Cost</b> = Order x unit cost.', 'small'),
             p('Order once per Item ID. Pack and increment use the row unit. All current minimum orders are 0; confirm vendor terms. Entered takeoff means the project measurement/count is still needed.', 'small'), Spacer(1, 7)]
    assert all(line['minimumOrderQty'] == 0 for line in lines), 'Update the guide to show nonzero minimum orders.'
    used = []
    for stage in ('1', '2', '3'):
        if stage != '1':
            story.append(Spacer(1, 10))
        selected = [line for line in lines if line['deliveryStage'] == stage]
        rows = [[p(f'Delivery stage {stage}  |  {len(selected)} items', 'head')] + [''] * 7,
                [p(text, 'head') for text in ['Section / Line', 'Item', 'Unit', 'Required Quantity Formula', 'Spare Percentage', 'Minimum Kit Quantity', 'Pack Size', 'Rounding Increment']]]
        group_rows = []
        previous_section = None
        for line in selected:
            if line['categorySection'] != previous_section:
                group_rows.append(len(rows))
                rows.append([p(f"<b>{line['categorySection']} {escape(line['stage'])}</b> | Phase: {escape(line['phase'])} | {escape(line['category'])}", 'small')] + [''] * 7)
                previous_section = line['categorySection']
            used.append(line['lineId'])
            item = escape(line['description']) + '<br/><font size="7" color="#53616E">' + escape(' > '.join(line['categoryPath'])) + '</font>'
            if line['lineId'] == 'PAN-002':
                item += '<br/><font size="7" color="#8A5C21">Minimum 100 vs 250 still unresolved.</font>'
            rows.append([p(f"<b>{line['catalogId']}</b><br/>{line['categorySection']} / {line['lineId']}", 'small'), p(item, 'item'), p(line['unit'], 'small'),
                         p(base(line), 'formula'), p(f"{line['sparePercent']*100:g}%", 'small'),
                         p(f"{line['minimumKitQty']:g}", 'small'), p(f"{line['packSize']:g}", 'small'), p(f"{line['quantityIncrement']:g}", 'small')])
        table = LongTable(rows, colWidths=widths, repeatRows=2, hAlign='LEFT')
        table.setStyle(TableStyle([
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 1), INK), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('ROWBACKGROUNDS', (0, 2), (-1, -1), [colors.white, colors.HexColor('#F4F6F8')]),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, INK),
        ]))
        for group_row in group_rows:
            table.setStyle(TableStyle([
                ('SPAN', (0, group_row), (-1, group_row)),
                ('BACKGROUND', (0, group_row), (-1, group_row), colors.HexColor('#DFE7EE')),
                ('NOSPLIT', (0, group_row), (-1, group_row + 1)),
            ]))
        story.append(table)
    audit = json.loads((ROOT / 'outputs/NeoviBOM/_Internal/Model-Data/full-project-calculations.json').read_text(encoding='utf-8'))
    story += [Spacer(1,12), p('Santa Rita + Franklin | Complete Item Audit', 'title'),
              p(f'Separate project PDFs contain all {len(lines)} items with source status, formulas and quantities where supported. Each item has a saved search rule and takeoff requirement.', 'small'),Spacer(1,6)]
    for project in audit['projects']:
        label = 'Santa Rita' if 'Santa Rita' in project['project'] else 'Franklin'
        found = [row for row in project['rows'] if row['required'] is not None]
        hold = next(row for row in project['rows'] if row['lineId']=='PAN-013')
        story.append(KeepTogether([p(label,'section'),
            p(f"{project['elementCount']:,} export elements; {len(lines)} item definitions audited; {len(found)} measured/derived/confirmed lines plus {sum(r.get('planningEstimate') is not None for r in project['rows'])} separate planning estimates.", 'body'),
            p(f"Example 2.2 hold-down hardware: {hold['required']:g} assemblies + {hold['spare']:g} spare = {hold['baseKit']:g} base kit, excluding unentered extras.", 'body'),
            p(label.replace(' ','-') + '-All-Items-Calculations.pdf', 'small'),Spacer(1,10)]))
    story += [p('Project PDFs now include a separate Estimate column with user-authorized budget rates and model drivers. Edit config/planning-allowances.json in the repository and rebuild to change assumptions. Estimates do not replace verified takeoffs. N/A remains for unresolved requirements and actual purchasing inputs; no synthetic inventory or prices are used.', 'small')]
    assert len(used) == len(set(used)) == len(lines)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=PAGE, rightMargin=30, leftMargin=30, topMargin=27, bottomMargin=42,
                            title='Neovi Site BOM - Compact Formula Guide', author='Neovi')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    print(OUT)


if __name__ == '__main__':
    build()
