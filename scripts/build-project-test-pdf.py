"""Render the independently verified Franklin and Santa Rita arithmetic tests."""
import json
import re
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, LongTable

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs/NeoviBOM/02-Projects/Franklin-and-Santa-Rita-Test-Results.pdf'
INK = colors.HexColor('#223347')
GRAY = colors.HexColor('#53616E')
styles = {
    'title': ParagraphStyle('title', fontName='Helvetica-Bold', fontSize=17, leading=20, textColor=INK),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=8.5, leading=11, textColor=INK),
    'small': ParagraphStyle('small', fontName='Helvetica', fontSize=7.5, leading=9.5, textColor=GRAY),
    'head': ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white),
}


def p(text, style='body'):
    for short,full in {'R':'Required Quantity','S':'Spare Quantity','E':'Manual Extra Quantity','K':'Kit Quantity'}.items():
        text=re.sub(r'\b'+short+r'\b',full,text)
    text=re.sub(r'(?<!Round )\bup\(', 'Round up(', text).replace('Base kit','Base Kit Quantity')
    return Paragraph(text, styles[style])


def table(rows, widths, small=False):
    data = [[p(escape(str(value)), 'head' if i == 0 else 'small' if small else 'body')
             for value in row] for i, row in enumerate(rows)]
    result = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    result.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), INK),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F4F6F8')]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3), ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 5), ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))
    return result


def footer(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(GRAY)
    canvas.setFont('Helvetica', 7)
    canvas.drawString(30, 29, 'Net Quantity = MAX(0, total kit quantity + target stock - on hand - committed).')
    canvas.drawString(30, 19, 'Order Quantity = Round up(MAX(net quantity, minimum order), pack); zero if net is zero. Total Cost = order quantity x unit cost.')
    canvas.drawRightString(762, 19, str(doc.page))
    canvas.restoreState()


def build(project_filter=None):
    audit = json.loads((ROOT / 'outputs/NeoviBOM/_Internal/Model-Data/full-project-calculations.json').read_text(encoding='utf-8'))
    projects = sorted(audit['projects'], key=lambda project: 'Santa Rita' in project['project'])
    projects = [project for project in projects if project_filter is None or project_filter in project['project']]
    story = []
    for index, project in enumerate(projects):
        if index:
            story.append(PageBreak())
        label = '898 Santa Rita Ave' if 'Santa Rita' in project['project'] else '560 Franklin St'
        supported=sum(r['required'] is not None for r in project['rows'])
        estimated=sum(r.get('planningEstimate') is not None for r in project['rows'])
        story += [p(f'{label} | All Item Calculations', 'title'), Spacer(1, 6),
                  p(f"All {len(project['rows'])} BOM items audited. {project['elementCount']:,} model elements in source export."),
                  p(f'<b>{supported+estimated}/{len(project["rows"])} items have quantities: {supported} measured/derived/confirmed and {estimated} planning estimates.</b>'),
                  p('Estimate is a separate, user-authorized budget scenario. Its rates are editable in planning-allowances.json. It is not a measured takeoff or an installation design. S and Base kit use the estimate when R is unavailable. Independent allowances can overlap; reconcile assemblies before purchasing.', 'small'),
                  p('Purchasing: Net / Order / Cost remain N/A wherever inventory, extras or prices are missing. These fields and every purchasing formula are retained in the project CSV; the common formulas are below each page.', 'small'),
                  p('R shows model quantities, confirmed project standards, or labeled derived allowances. S and base kit use catalog rules; base kit excludes unentered extras. N/A means the source or required input is missing, never zero. Orders and costs require actual purchasing inputs. Derived allowances still need installation/supply review.', 'small'),
                  p('R = required; S = spare; Base kit = required + spare, rounded to catalog minimum; up(value, step) = round up. All formulas for demand, inventory, orders and costs are also included in the matching project CSV. Shared purchasing formulas appear in every page footer.', 'small'),
                  p(f"Source: {escape(Path(project['source']).name)} | Export: {escape(project['exportedAt'][:10])}", 'small'), Spacer(1, 9)]
        if any(r['mappingStatus']=='MODEL_ROUTE_QUANTITY' for r in project['rows']):
            story += [p('Circuit correction: assigned electrical systems have no construction phase and are included explicitly. Routes use model Cable Size, Length and # of Runs. MC construction is not established by the model cable type; see Circuit-Evidence.csv for individual circuit records.', 'small'),Spacer(1,6)]
        available = [r for r in project['rows'] if r['required'] is not None]
        summary = [['Section / item', 'Quantity / unit', 'Evidence / rule (allowances labeled)']]
        for r in available:
            m = project['mapped'][r['lineId']]
            summary.append([r['categorySection'] + ' / ' + r['item'], f"{r['required']:,.3f} {r['unit']}", m['description'] + ': ' + m['formula']])
        story += [p('Quantities, confirmed standards and allowances', 'title'), Spacer(1, 6), table(summary, [265, 100, 355], small=True), Spacer(1, 8), p('Scope: unique New Construction instances; no demolished, view-specific or design-option objects. Foundation steel, plates and hold-downs use the structural link; other matches use the host. Hardware/cover allowances use stated per-device rules; factory-included parts must be checked. Exact source keys and every item search are in the companion CSV/JSON audit. Candidate matches are evidence, not purchase counts.', 'small')]
        counts={}
        for row in project['rows']: counts[row['mappingStatus']]=counts.get(row['mappingStatus'],0)+1
        story += [Spacer(1,8),p('Audit coverage: '+escape('; '.join(f"{key.replace('_',' ').lower()}: {value}" for key,value in counts.items())), 'small'),Spacer(1,12)]
        wall_trim=project['openingTakeoffs']['supplemental'].get('WALL-TRIM')
        if wall_trim:
            story += [p('3.13 Wall trim (supplemental) | Stage 3 | Phase: Finishing | Interior Finishes', 'body'),
                      p(f"Gross wall trim = 2 x {wall_trim['interiorLength']:,.3f} FT interior + {wall_trim['exteriorLength']:,.3f} FT exterior = <b>{wall_trim['value']:,.3f} FT</b>.", 'body'),
                      p('Your side rule uses model wall Function on primary host stud walls (including garage separation walls). Gross run: no opening deductions or waste added. Linked walls and separate cladding pieces are excluded. This is a supplemental takeoff because the catalog has no wall-trim line.', 'small'),Spacer(1,12)]
        hardware=project['openingTakeoffs'].get('hardwareEvidence',{})
        if hardware:
            hardware_rows=[['Model hardware', 'Measured quantity', 'Calculation / remaining assignment']]
            for name, evidence in hardware.items():
                hardware_rows.append([name, f"{evidence['value']:g} EA", evidence['formula']+'. '+evidence['description']])
            story += [p('Structural hardware measurements | Stage / phase assignment unresolved', 'body'),
                      table(hardware_rows,[170,100,450],small=True),
                      p('These are measured model quantities, not additional purchase lines. Do not add them to catalog hardware totals until their connection and factory/site scope is assigned. Individual source keys are saved in Source evidence.', 'small'),Spacer(1,12)]
        # Compact formulas beside every item; phase and category repeat at group boundaries.
        header = [p(value, 'head') for value in ['Section / Line', 'Item / unit', 'Calculation / source status', 'Required Quantity', 'Estimated Quantity', 'Spare Quantity', 'Base Kit Quantity']]
        rows = [[p(label + f' | {len(project["rows"])} items | Estimates separately labeled', 'head')] + [''] * 6, header]
        groups = []
        last = None
        for row in project['rows']:
            if row['categorySection'] != last:
                groups.append(len(rows))
                rows.append([p(f"<b>{row['categorySection']} {escape(row['workArea'])}</b> | Phase: {row['phase']} | Stage: {row['deliveryStage']} | {escape(row['category'])}", 'small')] + [''] * 6)
                last = row['categorySection']
            base = row['requiredFormula']
            if row['sourceMode'] == 'MANUAL' and row['required'] is None and not row.get('takeoffFormula') and row['lineId'] not in ('FIN-085','FIN-089','FIN-090'):
                base = 'R = verified item takeoff'
            base = base.replace('SUM(', 'sum(')
            compact = escape(base) + '<br/>' + escape(row['spareFormula'] + '; ' + row['baseKitFormula'])
            reason = ('Roof-to-material mapping N/A' if row['lineId'] == 'PAN-020'
                      else 'Project applicability N/A' if row['sourceMode'] == 'FIXED'
                      else 'Verified model takeoff N/A' if row['sourceMode'] == 'MANUAL'
                      else 'Mapped model input N/A')
            reason = row['mappingStatus'].replace('_',' ').title()+': '+row['reason']
            if row['required'] is None and row['sourceGroups']:
                groups_preview='; '.join(f"{g['family'] or g['category']} / {g['type']}: {g['count']}" for g in row['sourceGroups'][:2])
                reason += ' Evidence candidates (not takeoff): '+groups_preview[:200]+'.'
            compact += '<br/><font color="#8A5C21">' + escape(reason) + '</font>'
            is_estimate=row.get('planningEstimate') is not None
            if is_estimate:
                compact='<b>PLANNING ESTIMATE</b><br/>'+escape(row['planningFormula'])+'<br/>'+escape(row['planningAssumption'])
            raw_values=[row['required'],row.get('planningEstimate'),row['planningSpare'] if is_estimate else row['spare'],row['planningBaseKit'] if is_estimate else row['baseKit']]
            values = ['N/A' if v is None else f'{v:g}' for v in raw_values]
            if not is_estimate:values[1]='--'
            rows.append([p(f"<b>{row['catalogId']}</b><br/>{row['categorySection']} / {row['lineId']}", 'small'),
                         p(f"{escape(row['item'])}<br/><font color=\"#53616E\">{row['unit']} | {escape(row.get('categoryPath',''))}</font>", 'body'),
                         p(compact, 'small'), *[p(value, 'small') for value in values]])
        t = LongTable(rows, colWidths=[68, 145, 316, 45, 60, 45, 45], repeatRows=2, hAlign='LEFT')
        commands = [('SPAN', (0, 0), (-1, 0)), ('BACKGROUND', (0, 0), (-1, 1), INK),
                    ('ROWBACKGROUNDS', (0, 2), (-1, -1), [colors.white, colors.HexColor('#F4F6F8')]),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('TOPPADDING', (0, 0), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 3), ('LEFTPADDING', (0, 0), (-1, -1), 4), ('RIGHTPADDING', (0, 0), (-1, -1), 4)]
        for g in groups:
            commands.extend([('SPAN', (0, g), (-1, g)), ('BACKGROUND', (0, g), (-1, g), colors.HexColor('#DFE7EE')),
                             ('NOSPLIT', (0, g), (-1, g+1))])
        t.setStyle(TableStyle(commands))
        story += [t, PageBreak(), p(f'{label} | Available Roof Evidence', 'title'), Spacer(1, 7),
                  p('Category 2.4 Roof Panels | Phase: Panels | Stage: 2 | Building Envelope'),
                  p('The following measurements exist in the export. They are not a verified takeoff for floor-cassette slope material. That item remains N/A because applicability and layer overlap are unresolved.', 'small'), Spacer(1, 8)]
        evidence = [['Source element key', 'Roof type', 'Level', 'Measured area (SQFT)']]
        for r in project['candidates']:
            evidence.append([r['key'], r['type'], r['level'] or 'N/A', f"{r['value']:,.8f}"])
        story += [table(evidence, [320, 125, 140, 135], small=True), Spacer(1, 8),
                  p(f"Raw candidate area sum = {sum(r['value'] for r in project['candidates']):,.8f} SQFT. BOM required / spare / kit / order / cost = <b>N/A</b>.", 'body'),
                  p('Earlier 100 SQFT inventory, 32 SQFT packs and $2.50/SQFT examples were synthetic arithmetic tests. Those assumptions are not used as project results in this report.', 'small')]
    out = OUT if project_filter is None else OUT.parent / ('Santa-Rita' if project_filter == 'Santa Rita' else 'Franklin') / (('Santa-Rita' if project_filter == 'Santa Rita' else 'Franklin') + '-All-Items-Calculations.pdf')
    out.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(str(out), pagesize=landscape(letter), leftMargin=24, rightMargin=24,
                      topMargin=24, bottomMargin=46, title=(project_filter or 'Franklin and Santa Rita') + ' - All Item Calculations', author='Neovi').build(story, onFirstPage=footer, onLaterPages=footer)
    print(out)


if __name__ == '__main__':
    build("Franklin")
    build("Santa Rita")
