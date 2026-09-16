"""Publish the annotated-catalog revision, preserving retired source identities."""
import csv,json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import landscape,letter
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,LongTable,TableStyle
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'outputs/NeoviBOM/04-Audits'
def build():
 revision=json.loads((ROOT/'config/catalog-revision-2026-09-15.json').read_text())
 catalog={r['lineId']:r for r in json.loads((ROOT/'outputs/NeoviBOM/_Internal/Model-Data/catalog-lines.json').read_text())}
 rows=[]
 for lid,r in revision['retired'].items():
  rows.append({'Action':'Removed / replaced','Line':lid,'Catalog ID':'Retired legacy reference','Item':r['description'],'Category Path':'','Change':r['reason'],'Replacement Lines':'; '.join(r['replacements'])})
 for change in revision['changes']:
  lid=change['lineId'];r=catalog[lid]
  rows.append({'Action':'Added' if change['before'] is None else 'Updated','Line':lid,'Catalog ID':r['catalogId'],'Item':r['description'],'Category Path':' > '.join(r['categoryPath']),'Change':r['itemNotes'],'Replacement Lines':''})
 with (DEST/'Catalog-Changes.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 body=ParagraphStyle('body',fontName='Helvetica',fontSize=8,leading=10)
 title=ParagraphStyle('title',parent=body,fontSize=17,leading=21,fontName='Helvetica-Bold')
 p=lambda s:Paragraph(escape(s),body)
 story=[Paragraph('NeoviBOM | Annotated Catalog Changes',title),Spacer(1,8),p(revision['source']),Spacer(1,5),p(f'{len(catalog)} active items. Every active item now has a permanent category ID and a nested category path. Legacy IDs remain available for model mapping. Removed items are not restored from older lists.'),Spacer(1,10)]
 data=[[p(s) for s in ['Change / ID','Item','Category / disposition']]]
 for r in rows:data.append([p(r['Action']+' / '+r['Line']+' / '+r['Catalog ID']),p(r['Item']),p(r['Category Path']+'\n'+r['Change']+(' Replacements: '+r['Replacement Lines'] if r['Replacement Lines'] else ''))])
 t=LongTable(data,colWidths=[145,205,382],repeatRows=1)
 t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DFE7EE')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F3F6F8')]),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
 story.append(t)
 SimpleDocTemplate(str(DEST/'Catalog-Changes.pdf'),pagesize=landscape(letter),leftMargin=30,rightMargin=30,topMargin=26,bottomMargin=30).build(story)
 print('Published annotated catalog change log:',len(rows),'changes')
if __name__=='__main__':build()
