"""A plain, complete category reference for the current Site BOM."""
import json
from collections import defaultdict
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf/Neovi-Site-BOM-Categories.pdf'
INK = colors.HexColor('#254e78')
MUTED = colors.HexColor('#6a7787')
BODY = ParagraphStyle('body', fontName='Helvetica', fontSize=9, leading=12, textColor=INK)
SMALL = ParagraphStyle('small', parent=BODY, fontSize=7, leading=10, textColor=MUTED)
DETAIL = ParagraphStyle('detail', parent=BODY, fontSize=8, leading=10.5, textColor=colors.HexColor('#53657b'))
TITLE = ParagraphStyle('title', parent=BODY, fontName='Helvetica-Bold', fontSize=16, leading=20, spaceAfter=7, keepWithNext=True)
SUB = ParagraphStyle('sub', parent=BODY, fontName='Helvetica-Bold', fontSize=10, leading=13, spaceBefore=8, spaceAfter=4, keepWithNext=True)
PHASE = ParagraphStyle('phase', parent=BODY, fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=INK)
GROUP = ParagraphStyle('group', parent=BODY, fontName='Helvetica-Bold', fontSize=9, leading=12)
PHASES = ('Foundation', 'Panels', 'Finishing')
PHASE_NUMBERS = {phase: number for number, phase in enumerate(PHASES, 1)}
CATEGORY_ORDER = ['Equipment', 'Tools', 'Rigging', 'Sitework', 'Structural', 'Fasteners',
                  'Materials', 'Roof and Envelope', 'Electrical', 'Fire Protection',
                  'Plumbing', 'Mechanical', 'Doors and Windows', 'Interior Finishes']


def section_key(section):
    return tuple(int(part) for part in section.split('.'))

IDENTIFIERS = {
    'MAT': ('Materials', 'Building materials, installed components, and material consumables'),
    'TOOL': ('Tools', 'Hand tools, power tools, and tool accessories'),
    'FAST': ('Fasteners', 'Screws, bolts, nuts, washers, pins, and connecting hardware'),
    'EQUIP': ('Equipment', 'Site equipment and rentals'),
    'SUP': ('Supplies', 'Marking and layout supplies'),
    'FIX': ('Fixtures', 'Drill pedestals and fixtures that support or position tools'),
    'RIG': ('Rigging', 'Lifting chains, slings, and straps'),
}

def item_cells(item, identities):
    import re
    use = ' / '.join(dict.fromkeys(filter(None, [item.get('stage'), item.get('system')])))
    spec = item.get('specification', '').strip()
    if not spec or spec.startswith('TBD'):
        spec = 'Exact specification to be confirmed.'
    elif not item.get('specificationApproved'):
        spec += ' (Approval pending.)'
    notes = list(dict.fromkeys(item.get(k, '').strip() for k in ('itemNotes', 'lineNotes', 'ruleNotes') if item.get(k, '').strip()))
    comment = re.sub(r'\b(?:FND|PAN|FIN)-\d+\b', lambda m: identities.get(m[0], m[0]), ' '.join(notes))
    values = [item['catalogId'], item['description'], item['unit'], item['categorySection'],
              use or 'To be confirmed', spec, comment]
    return [Paragraph(escape(value), DETAIL) for value in values]


def subgroup_name(item):
    system = item['system']
    return {
        'Magnetic Drill - Fixtures': 'Magnetic Drill / Fixtures',
        'Survey & Layout Tools': 'Survey and Layout / Laser Tools',
        'Magnetic Drill': 'Magnetic Drill / Drill, Bits and Cutting Fluid',
        'Magnetic Drill - Bits': 'Magnetic Drill / Drill, Bits and Cutting Fluid',
        'Magnetic Drill - Cutting Fluid': 'Magnetic Drill / Drill, Bits and Cutting Fluid',
        'Rigging': 'Lifting and Rigging',
        'Crane & Rigging': 'Lifting and Rigging',
    }.get(system, system)


def section_table(label, items, identities):
    headers = ['Item ID', 'Description', 'Unit', 'Section', 'Used for', 'Specification', 'Comments']
    rows = [[Paragraph(escape(label), PHASE)] + [''] * 6,
            [Paragraph(text, GROUP) for text in headers]]
    subgroups = defaultdict(list)
    for item in items:
        subgroups[subgroup_name(item)].append(item)
    heading_rows = []
    for subgroup, members in subgroups.items():
        heading_rows.append(len(rows))
        rows.append([Paragraph(escape(subgroup), GROUP)] + [''] * 6)
        rows.extend(item_cells(item, identities) for item in members)
    table = Table(rows, colWidths=[50, 115, 33, 46, 100, 172, 192], repeatRows=2, hAlign='LEFT')
    commands = [
        ('GRID', (0, 0), (-1, -1), .35, colors.HexColor('#bdcddd')),
        ('SPAN', (0, 0), (-1, 0)),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dce9f7')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#e8eef5')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    for row in heading_rows:
        commands += [
            ('SPAN', (0, row), (-1, row)),
            ('BACKGROUND', (0, row), (-1, row), colors.HexColor('#f0f4f8')),
            ('NOSPLIT', (0, row), (-1, row+1)),
        ]
    table.setStyle(TableStyle(commands))
    return table


def footer(c, doc):
    c.setStrokeColor(colors.HexColor('#dce4ee'))
    c.line(42, 42, 750, 42)
    c.setFont('Helvetica', 8)
    c.setFillColor(MUTED)
    c.drawString(42, 28, 'NEOVI  /  SITE BOM  /  SECTION REFERENCE')
    c.drawRightString(750, 28, str(doc.page))

def build():
    data = json.loads((ROOT / 'outputs/NeoviBOM/NeoviBOM.json').read_text(encoding='utf-8'))
    identities = {item['lineId']: item['catalogId'] for item in data['items']}
    # Delivery sections remain item properties. Group related work across
    # delivery stages so floor and wall packages are not scattered.
    import re
    registry_source = (ROOT / 'src/workbook-formulas.mjs').read_text(encoding='utf-8')
    registry = {number: (phase, stage, trade) for number, phase, stage, trade in
                re.findall(r'\["([0-9.]+)", "([^"]+)", "([^"]+)", "([^"]+)"\]', registry_source)}
    groups = defaultdict(list)
    for item in data['items']:
        phase, stage, trade = registry[item['categorySection']]
        assert phase == item['phase'] and stage == item['stage']
        if stage in ('Rough MEP', 'Finish MEP'):
            section = ('Rough' if stage == 'Rough MEP' else 'Finish') + ' ' + trade
        elif stage == 'General':
            section = {'3.7': 'Drywall', '3.8': 'Garage Doors'}[item['categorySection']]
        else:
            section = stage
        groups[(phase, section)].append(item)
    story = [Paragraph('Site BOM', TITLE),
             Paragraph('Foundation / Panels / Finishing', SUB),
             Paragraph(f"{len(data['items'])} items / {len(groups)} construction sections", BODY),
             Spacer(1, 10), Paragraph('HOW TO READ', SUB),
             Paragraph('One item per row. Read across the columns for its description, unit, delivery section, use, specification, and comments. Blue section headings collect related construction work; shaded subgroup headings keep related components and tools together. Section and column headings repeat on subsequent pages.', SMALL),
             Spacer(1, 7),
             Paragraph('Phase: 1 = Foundation; 2 = Panels; 3 = Finishing. Original delivery-section numbers remain on each item for traceability; they do not split related work into separate boxes. Each item retains its use, specification, and comments. Missing comments are blank.', SMALL)]
    assert {item['catalogId'].rsplit('-', 1)[0] for item in data['items']} <= IDENTIFIERS.keys()
    story += [Spacer(1, 10), Paragraph('IDENTIFIER KEY', SUB)]
    key_rows = [[Paragraph('PREFIX', SMALL), Paragraph('MEANING', SMALL), Paragraph('USED FOR', SMALL)]]
    for prefix, (meaning, explanation) in IDENTIFIERS.items():
        key_rows.append([Paragraph(prefix, GROUP), Paragraph(meaning, BODY), Paragraph(explanation, BODY)])
    key_table = Table(key_rows, colWidths=[58, 100, 550], hAlign='LEFT')
    key_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8f0fa')),
        ('LINEBELOW', (0, 1), (-1, -1), .3, colors.HexColor('#e1e7ee')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story += [key_table, Spacer(1, 7),
              Paragraph('<b>Example: MAT-114</b> means material item 114 in the catalog. The number is a permanent identifier, not a quantity, phase, or delivery stage. IDs stay the same when items move between categories; gaps in numbering are normal. MAT appears across several trade categories.', SMALL)]
    used = []
    ordered = sorted(groups.items(), key=lambda pair: (
        PHASES.index(pair[0][0]),
        min(section_key(i['categorySection']) for i in pair[1])))
    for (phase, section), items in ordered:
        # Keep related systems adjacent within the shared construction section.
        systems = {}
        for item in items:
            systems.setdefault(item['system'], len(systems))
        items = sorted(items, key=lambda item: (systems[item['system']],
                       section_key(item['categorySection']), item['catalogId']))
        used.extend(item['lineId'] for item in items)
        sections = ', '.join(sorted({i['categorySection'] for i in items}, key=section_key))
        label = f'{PHASE_NUMBERS[phase]} {phase.upper()} / {section}  |  Sections {sections}'
        story += [Spacer(1, 10), section_table(label, items, identities)]
    assert len(used) == len(set(used)) == len(data['items'])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = BaseDocTemplate(str(OUT), pagesize=landscape(letter), rightMargin=42, leftMargin=42,
                          topMargin=42, bottomMargin=56, title='Neovi Site BOM - Construction Sections',
                          author='Neovi')
    frames = [Frame(42, 56, 708, 514, leftPadding=0, rightPadding=0,
                    topPadding=0, bottomPadding=0, id='rows')]
    doc.addPageTemplates(PageTemplate(id='rows', frames=frames, onPage=footer))
    doc.build(story)
    print(OUT)

if __name__ == '__main__':
    build()
