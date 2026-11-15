"""Rebuild the SchemeGuard academic report from structured, editable content.
Requires reportlab, Pillow and pypdf. No application data is modified.
"""
from pathlib import Path
import json, re, math, html, sys
from dataclasses import dataclass, field
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Spacer, Table, TableStyle, Image, Flowable, KeepTogether
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.lib.pagesizes import A4

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
W,H = A4
LEFT,RIGHT,TOP,BOTTOM = 85.04,56.69,70.87,63.78
WIDTH = W-LEFT-RIGHT
FONTROOT=Path('/usr/share/fonts/truetype/msttcorefonts')
for name,f in [('TimesR','Times_New_Roman.ttf'),('TimesB','Times_New_Roman_Bold.ttf'),('TimesI','Times_New_Roman_Italic.ttf'),('TimesBI','Times_New_Roman_Bold_Italic.ttf')]:
    if not (FONTROOT/f).exists():
        alt={'TimesR':'LiberationSerif-Regular.ttf','TimesB':'LiberationSerif-Bold.ttf','TimesI':'LiberationSerif-Italic.ttf','TimesBI':'LiberationSerif-BoldItalic.ttf'}[name]
        fpath=Path('/usr/share/fonts/truetype/liberation')/alt
    else: fpath=FONTROOT/f
    if fpath.exists():
        pdfmetrics.registerFont(TTFont(name,str(fpath)))
    else:
        base={'TimesR':'Times-Roman','TimesB':'Times-Bold','TimesI':'Times-Italic','TimesBI':'Times-BoldItalic'}[name]
        pdfmetrics.registerFont(pdfmetrics.Font(name,base,'WinAnsiEncoding'))
pdfmetrics.registerFontFamily('TimesR',normal='TimesR',bold='TimesB',italic='TimesI',boldItalic='TimesBI')
S={
 'body':ParagraphStyle('body',fontName='TimesR',fontSize=12,leading=17.4,alignment=TA_JUSTIFY,spaceAfter=10,allowWidows=0,allowOrphans=0),
 'small':ParagraphStyle('small',fontName='TimesR',fontSize=10.4,leading=14.3,spaceAfter=8,alignment=TA_JUSTIFY),
 'h1':ParagraphStyle('h1',fontName='TimesB',fontSize=17.2,leading=21,spaceBefore=10,spaceAfter=12,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='TimesB',fontSize=13.2,leading=17,spaceBefore=7,spaceAfter=7,keepWithNext=True),
 'caption':ParagraphStyle('caption',fontName='TimesR',fontSize=10.8,leading=14,alignment=TA_CENTER,spaceBefore=5,spaceAfter=11),
 'cell':ParagraphStyle('cell',fontName='TimesR',fontSize=9.6,leading=12.4,spaceAfter=0),
 'cellb':ParagraphStyle('cellb',fontName='TimesB',fontSize=9.6,leading=12.4,spaceAfter=0),
 'center':ParagraphStyle('center',fontName='TimesR',fontSize=12,leading=18,alignment=TA_CENTER,spaceAfter=12),
 'quote':ParagraphStyle('quote',fontName='TimesI',fontSize=14,leading=21,alignment=TA_CENTER,spaceAfter=12),
 'code':ParagraphStyle('code',fontName='Courier',fontSize=8.7,leading=12,spaceAfter=9,backColor=colors.HexColor('#f4f4f4'),borderPadding=8),
 'ref':ParagraphStyle('ref',fontName='TimesR',fontSize=10.5,leading=14.5,spaceAfter=11,alignment=TA_LEFT),
 'toc':ParagraphStyle('toc',fontName='TimesR',fontSize=11.5,leading=16,spaceAfter=6),
}
BLACK=colors.black
LIGHT=colors.HexColor('#f2f2f2')
GREEN=colors.HexColor('#235c4d')

def esc(x): return html.escape(str(x),quote=False)
def para(t,style='body'):return Paragraph(t,S[style])
def table(headers,rows,widths=None):
    widths=[WIDTH*v/sum(widths) for v in (widths or [1]*len(headers))]
    data=[[para(esc(h),'cellb') for h in headers]]+[[para(str(c),'cell') for c in row] for row in rows]
    t=Table(data,colWidths=widths,hAlign='CENTER',repeatRows=1)
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.45,BLACK),('BACKGROUND',(0,0),(-1,0),LIGHT),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    return t

class Diagram(Flowable):
    def __init__(self,kind,height=260): super().__init__();self.width=WIDTH;self.height=height;self.kind=kind
    def draw(self):
        c=self.canv
        def box(x,y,w,h,title,lines=(),fill=False):
            c.setStrokeColor(BLACK);c.setLineWidth(.7);c.setFillColor(LIGHT if fill else colors.white);c.roundRect(x,y,w,h,4,stroke=1,fill=1)
            p=Paragraph('<b>'+esc(title)+'</b>'+(' <br/>'+'<br/>'.join(esc(l) for l in lines) if lines else ''),ParagraphStyle('d',fontName='TimesR',fontSize=10,leading=12,alignment=TA_CENTER))
            pw,ph=p.wrap(w-12,h-8);p.drawOn(c,x+6,y+(h-ph)/2)
        def arrow(x1,y1,x2,y2):
            c.setStrokeColor(BLACK);c.setLineWidth(.8);c.line(x1,y1,x2,y2)
            a=math.atan2(y2-y1,x2-x1);l=5
            c.line(x2,y2,x2-l*math.cos(a-.45),y2-l*math.sin(a-.45));c.line(x2,y2,x2-l*math.cos(a+.45),y2-l*math.sin(a+.45))
        if self.kind=='architecture':
            box(0,210,130,58,'Citizen / Guest',['Profile -> recommendations','Assessment / history'])
            box(WIDTH-130,210,130,58,'Administrator',['Documents / review','Monitoring / audit'])
            box(150,210,153,58,'Next.js frontend',['Same-origin fixed proxies'],True)
            arrow(130,239,150,239);arrow(WIDTH-130,239,303,239)
            box(106,120,242,62,'FastAPI modular monolith',['Discovery | typed eligibility | auth','Ingestion | LangGraph | review | RAG'],True)
            arrow(226,210,226,182)
            box(0,18,136,62,'PostgreSQL + pgvector',['Policies / evidence / profiles','Durable jobs / checkpoints'])
            box(159,18,136,62,'Celery workers + Beat',['Bounded jobs / retries','Singleton scheduling'])
            box(318,18,135,62,'Original documents',['Persistent volume / S3','Checksummed immutable files'])
            arrow(156,120,68,80);arrow(227,120,227,80);arrow(300,120,386,80)
            c.setFont('TimesI',9);c.drawCentredString(227,0,'Redis carries task identifiers; PostgreSQL owns durable business state.')
        elif self.kind=='journey':
            labels=[('Home','Find My Schemes'),('Optional questionnaire','Five short steps'),('Ranked recommendations','Reasons + missing information'),('Scheme details','Official metadata / source'),('Supported assessment','Approved or illustrative basis'),('Explainable report','Evidence / version / UNKNOWN')]
            for i,(a,b) in enumerate(labels):
                y=250-i*43;box(78,y,297,34,a,[b],i in (1,2))
                if i<5:arrow(226,y,226,y-9)
        elif self.kind=='pipeline':
            stages=[('Approved source + original PDF','URL authorization, hash, immutable version'),('PyMuPDF + page-aware chunks','Text / blocks / tables / source locators'),('Gemini structured candidates','Pydantic / field / unit / evidence checks'),('LangGraph human-review interrupt','Saved revision digest and explicit decision'),('Transactional publication','New RuleSet / conditions / exact evidence')]
            for i,(a,b) in enumerate(stages):
                y=245-i*52;box(35,y,383,41,a,[b],i==3)
                if i<4:arrow(226,y,226,y-11)
            c.setFont('TimesI',10);c.drawCentredString(226,5,'A candidate can never execute as a government rule before approval.')
        elif self.kind=='erd':
            # Canonical lineage in two branches; full table inventory is in Chapter 4.
            nodes=[(0,270,138,50,'schemes',['id / stable slug']),(159,270,138,50,'scheme_sources',['scheme_id / URL']),(318,270,135,50,'document_versions',['source_id / hash']),
                   (318,180,135,52,'pages / chunks',['document_id / page']),(159,180,138,52,'rule_sets',['scheme / document / version']),(0,180,138,52,'rule_conditions',['rule_set_id / typed JSON']),
                   (0,85,138,52,'rule_evidence',['condition / page / excerpt']),(159,85,138,52,'assessments',['user / rule / encrypted trace']),(318,85,135,52,'profiles / users',['owner / encrypted data'])]
            for x,y,w,h,a,b in nodes:box(x,y,w,h,a,b,a in ('schemes','rule_sets'))
            arrow(138,295,159,295);arrow(297,295,318,295);arrow(386,270,386,232)
            arrow(351,270,265,232);arrow(159,206,138,206);arrow(68,180,68,137)
            arrow(228,180,228,137);arrow(318,111,297,111)
            c.setFont('TimesI',9.5);c.drawCentredString(226,48,'1-to-many relations are enforced with UUID FKs and provenance constraints.')
            c.drawCentredString(226,28,'Separate processing, review, monitoring and checkpoint tables retain history.')
        elif self.kind=='monitor':
            vals=[('Opt-in schedule','Beat -> durable job -> Redis'),('Secure conditional fetch','ETag / Last-Modified / SHA-256'),('Changed original preserved','Reuse parser and LangGraph'),('Normalized structured diff','Old approved vs new proposal'),('Human review + publication','No automatic policy activation'),('Authorized reassessment','Append report + deduplicated notification')]
            for i,(a,b) in enumerate(vals):
                y=270-i*46;box(48,y,357,37,a,[b],i==4)
                if i<5:arrow(226,y,226,y-9)
        elif self.kind=='deploy':
            box(91,245,272,43,'HTTPS edge / browser',['Only public application entry'],True)
            box(91,177,272,43,'Next.js frontend',['Fixed upstream proxy; server-only URL'])
            arrow(227,245,227,220)
            box(91,107,272,43,'FastAPI + worker + singleton Beat',['Same backend image / separate processes'])
            arrow(227,177,227,150)
            box(0,13,135,61,'PostgreSQL',['Private / durable / backups'])
            box(160,13,135,61,'Redis broker',['Private / ID-only tasks'])
            box(319,13,134,61,'Document storage',['Private volume or S3'])
            arrow(150,107,68,74);arrow(227,107,227,74);arrow(302,107,386,74)

@dataclass
class Page:
    kind:str='normal'
    chapter:str=''
    number:str=''
    title:str=''
    flows:list=field(default_factory=list)
    entries:list=field(default_factory=list)

pages=[];chap='';chapn='';figs=[];tables=[];headings=[]

def new(chapter=None,title=None):
    global chap,chapn
    if chapter:
        chapn,title=chapter;chap=title
        p=Page('chapter',chap,chapn,title)
        headings.append((0,f'{chapn}  {title}',len(pages)+1))
    else:p=Page('normal',chap,chapn,'')
    pages.append(p);return p

def add(t,style='body'):pages[-1].flows.append(para(t,style))
def h(n,t):
    pages[-1].flows.append(para(n+'  '+t,'h1'));headings.append((1,n+'  '+t,len(pages)))
def sub(t):add(t,'h2')
def tbl(n,title,headers,rows,widths=None):
    pages[-1].flows.append(para(f'Table {n}: {title}','caption'));pages[-1].flows.append(table(headers,rows,widths));pages[-1].flows.append(Spacer(1,10));tables.append((f'{n}  {title}',len(pages)))
def fig(n,title,kind,height=285):
    pages[-1].flows.append(Diagram(kind,height));pages[-1].flows.append(para(f'Figure {n}: {title}','caption'));figs.append((f'{n}  {title}',len(pages)))
def code(t):add(esc(t).replace('\n','<br/>').replace(' ','&#160;'),'code')
def imagefig(n,title,filename,w=WIDTH):
    imgpath=HERE/'assets'/filename
    iw,ih=ImageReader(str(imgpath)).getSize()
    im=Image(str(imgpath),width=w,height=w*ih/iw);im.hAlign='CENTER'
    pages[-1].flows.append(im);pages[-1].flows.append(para(f'Figure {n}: {title}','caption'));figs.append((f'{n}  {title}',len(pages)))

# Editable technical content, kept separate from layout code.
exec((HERE/'report_content.py').read_text(),globals())


def roman(n):
    pairs=[(1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),(100,'c'),(90,'xc'),(50,'l'),(40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')];s=''
    for a,b in pairs:
        while n>=a:s+=b;n-=a
    return s


def flow(c,items,top=H-TOP,bottom=BOTTOM):
    y=top
    for item in items:
        ww,hh=item.wrap(WIDTH,y-bottom)
        if hh>y-bottom+.1:
            raise RuntimeError(f'Page {c.getPageNumber()} overflow: needs {hh:.1f}, remaining {y-bottom:.1f}, {str(getattr(item,"text",item))[:130]}')
        item.drawOn(c,LEFT+(WIDTH-ww)/2 if getattr(item,'hAlign',None)=='CENTER' else LEFT,y-hh)
        y-=hh+getattr(item,'spaceAfter',0)+getattr(item,'spaceBefore',0)
    return y


def standard(c,p,n):
    if p.kind=='chapter':
        c.setFont('Helvetica',17);c.drawRightString(W-RIGHT,H-160,f'CHAPTER {p.number}' if p.number.isdigit() else f'APPENDIX {p.number}')
        c.setLineWidth(.65);c.line(LEFT,H-245,W-RIGHT,H-245)
        st=ParagraphStyle('ct',fontName='Helvetica',fontSize=18,leading=25,alignment=TA_RIGHT)
        pp=Paragraph(esc(p.title),st);_,hh=pp.wrap(WIDTH,80);pp.drawOn(c,LEFT,H-273-hh)
        liney=H-315 if hh<=26 else H-335
        c.line(LEFT,liney,W-RIGHT,liney)
        top=liney-43
    else:
        c.setFont('TimesI',10.2)
        text=(f'CHAPTER {p.number}. {p.chapter}' if p.number.isdigit() else p.chapter).upper()
        if pdfmetrics.stringWidth(text,'TimesI',10.2)>WIDTH:
            text={'3':'CHAPTER 3. PROPOSED METHODOLOGY','4':'CHAPTER 4. SYSTEM DESIGN AND IMPLEMENTATION'}.get(p.number,text)
        c.drawRightString(W-RIGHT,H-50,text)
        c.setLineWidth(.5);c.line(LEFT,H-55,W-RIGHT,H-55);top=H-73
    c.setFont('TimesR',11.5);c.drawCentredString(LEFT+WIDTH/2,38,str(n))
    if p.kind!='chapter':c.line(LEFT,54,W-RIGHT,54)
    flow(c,p.flows,top=top)


def frontpage(c,title,n,items,top=None):
    c.setFont('TimesB',20.7);c.drawCentredString(LEFT+WIDTH/2,H-112,title)
    flow(c,items,top=top or H-155)
    c.setFont('TimesR',11.5);c.drawCentredString(LEFT+WIDTH/2,38,roman(n))


def cover(c,meta,second=False):
    cx=LEFT+WIDTH/2
    if not second:
        c.setFont('TimesB',24);c.drawCentredString(cx,H-160,'SCHEMEGUARD')
        p=para('PERSONALIZED GOVERNMENT SCHEME DISCOVERY,<br/>EVIDENCE-BACKED ELIGIBILITY AND POLICY MONITORING','center');p.wrap(WIDTH,100);p.drawOn(c,LEFT,H-223)
        # Original project emblem, not an institutional crest.
        c.setStrokeColor(GREEN);c.setLineWidth(2.2)
        path=c.beginPath();path.moveTo(cx-48,H-306);path.lineTo(cx+48,H-306);path.lineTo(cx+43,H-371);path.curveTo(cx+40,H-403,cx+10,H-422,cx,H-428);path.curveTo(cx-10,H-422,cx-40,H-403,cx-43,H-371);path.close();c.drawPath(path)
        c.line(cx-22,H-362,cx-4,H-379);c.line(cx-4,H-379,cx+27,H-340)
        c.setFillColor(BLACK);c.setStrokeColor(BLACK)
        p=para('<b><i>'+esc(meta['authors_line'])+'</i></b>','center');p.wrap(WIDTH,100);p.drawOn(c,LEFT,H-567)
        items=[para('<b>COMPUTER SCIENCE &amp; ENGINEERING DEPARTMENT</b>','center')]
        if meta.get('institute'):items+=[para('<b>'+esc(meta['institute']).upper()+'</b>','center')]
        items+=[para('<b>BACHELOR OF TECHNOLOGY PROJECT REPORT</b>','center'),para('<b>'+esc(meta['date'])+'</b>','center')]
        flow(c,items,top=H-610)
    else:
        c.setFont('TimesB',24);c.drawCentredString(cx,H-92,'SCHEMEGUARD')
        items=[para('Personalized Government Scheme Discovery,<br/>Evidence-backed Eligibility and Policy Monitoring','center'),Spacer(1,14),para('<b><i>Report submitted for the award of the degree of</i></b>','center'),para('<b><i>Bachelor of Technology<br/>in Computer Science &amp; Engineering</i></b>','center'),Spacer(1,15),para('<i>by</i>','center'),para('<b>'+esc(meta['authors_line'])+'</b>','center')]
        if meta.get('rolls'):items+=[para(esc(meta['rolls']),'center')]
        items+=[Spacer(1,12),para('<b><i>Under the Guidance of</i></b>','center'),para(esc(meta.get('guide') or 'Project Supervisor'),'center')]
        if meta.get('guide_designation'):items+=[para(esc(meta['guide_designation']),'center')]
        items+=[Spacer(1,22),para('<b>COMPUTER SCIENCE &amp; ENGINEERING DEPARTMENT</b>','center')]
        if meta.get('institute'):items+=[para('<b>'+esc(meta['institute']).upper()+'</b>','center')]
        items+=[para('<b>'+esc(meta['date'])+'</b>','center')]
        flow(c,items,top=H-140)


def index_entry(c,label,page,y,bold=False,indent=0):
    font='TimesB' if bold else 'TimesR'
    size=11.2
    lines=simpleSplit(label,font,size,WIDTH-indent-32)
    c.setFont(font,size)
    for j,line in enumerate(lines):
        c.drawString(LEFT+indent,y-j*15,line)
    baseline=y-(len(lines)-1)*15
    endx=LEFT+indent+pdfmetrics.stringWidth(lines[-1],font,size)
    dotw=pdfmetrics.stringWidth('.','TimesR',size)
    count=max(0,int((W-RIGHT-22-endx-8)/dotw))
    c.setFont('TimesR',size)
    if count:c.drawString(endx+7,baseline,'.'*count)
    c.drawRightString(W-RIGHT,baseline,str(page))
    if str(page).isdigit():
        c.linkAbsolute(label,'body'+str(page),Rect=(LEFT,y-len(lines)*15,W-RIGHT,y+12),thickness=0)
    return y-len(lines)*15-8-(3 if bold else 0)


def listpage(c,title,n,entries):
    c.setFont('TimesB',20.7);c.drawString(LEFT,H-112,title)
    y=H-157
    for label,num in entries:
        y=index_entry(c,label,num,y)
        if y<65:raise RuntimeError(title+' index overflow')
    c.setFont('TimesR',11.5);c.drawCentredString(LEFT+WIDTH/2,38,roman(n))


def build():
    meta=json.loads((HERE/'submission.json').read_text())
    target=OUT/'SchemeGuard_Project_Report.pdf'
    c=canvas.Canvas(str(target),pagesize=A4,pageCompression=1)
    c.addPageLabel(0,style='ROMAN_LOWER',start=1)
    c.setTitle('SchemeGuard - B.Tech Project Report');c.setAuthor(meta['authors_line']);c.setSubject('Personalized government scheme discovery, deterministic eligibility, source-grounded document intelligence and policy monitoring')
    cover(c,meta);c.showPage();cover(c,meta,True);c.showPage()
    frontpage(c,'Dedicated To',3,[Spacer(1,120),para('Our families, teachers and mentors, whose support and encouragement made this work possible.','quote')]);c.showPage()
    frontpage(c,'',4,[Spacer(1,140),para('Trustworthy decisions begin with verifiable evidence.','quote'),para('A guiding principle of the SchemeGuard project.','center')]);c.showPage()
    frontpage(c,'REPORT APPROVAL FOR B.TECH',5,[
        para('This report entitled <b>"SchemeGuard: Personalized Government Scheme Discovery, Evidence-backed Eligibility and Policy Monitoring"</b>, submitted by <b>'+esc(meta['authors_line'])+'</b>, is presented for approval in partial fulfilment of the requirements for the award of <b>Bachelor of Technology in Computer Science &amp; Engineering</b>.'),
        para('Institutional approval is recorded by the authorized signatories below. This unsigned report does not represent an issued approval.','small'),Spacer(1,62),
        para(esc(meta.get('guide') or 'Project Supervisor'),'center'),para('(Project Supervisor)','center'),Spacer(1,42),
        para(esc(meta.get('hod') or 'Head of the Department'),'center'),para('(Head of the Department)','center'),Spacer(1,30),para('Date: ____________________<br/>Place: ____________________','body')]);c.showPage()
    frontpage(c,'DECLARATION',6,[
        para('I/We declare that this report titled <b>"SchemeGuard: Personalized Government Scheme Discovery, Evidence-backed Eligibility and Policy Monitoring"</b> is submitted for the award of the Bachelor of Technology degree in Computer Science &amp; Engineering. The report describes the implemented system and distinguishes verified results, project-authored demonstrations and unverified capabilities.'),
        para('Ideas, methods, software documentation and official information drawn from other sources are acknowledged in the references. Recorded test results are attributed to their repository verification records. No live model accuracy, government approval, institutional certification or production deployment is claimed without supporting evidence.'),
        para('The declaration is to be confirmed and signed by the submitting authors in accordance with their institute\'s academic integrity policy. Tool-assisted drafting and formatting are disclosed in Appendix A.'),Spacer(1,60),para(esc(meta['date'])+'<br/><br/>Author signature(s): ______________________________'),para(esc(meta['authors_line']),'center')]);c.showPage()
    frontpage(c,'CERTIFICATE',7,[
        para('This page is reserved for the project supervisor\'s certification of the work contained in the report titled <b>"SchemeGuard: Personalized Government Scheme Discovery, Evidence-backed Eligibility and Policy Monitoring"</b>, submitted by <b>'+esc(meta['authors_line'])+'</b>.'),
        para('Certification of supervision, originality and degree-submission status must be made by the authorized supervisor after reviewing the report and demonstration. No signature or institutional endorsement has been reproduced or fabricated.'),Spacer(1,95),para(esc(meta.get('guide') or 'Project Supervisor'),'center'),para(esc(meta.get('guide_designation') or 'Computer Science & Engineering Department'),'center'),Spacer(1,50),para('Supervisor signature: ___________________________<br/><br/>Date: ____________________')]);c.showPage()
    frontpage(c,'Acknowledgement',8,[
        para('We express our gratitude to our teachers and mentors for the knowledge and encouragement that supported the development of SchemeGuard. Their emphasis on clear reasoning, careful engineering and academic integrity shaped the project\'s approach to evidence and explainable decisions.'),
        para('We acknowledge the government departments and public portals whose authorized information supports the discovery catalog, and the open-source communities behind the frameworks, databases and tools used in the implementation. These sources are referenced where relevant.'),
        para('We thank our classmates, friends and families for their support. The project also acknowledges the use of AI-assisted development, drafting and formatting tools; responsibility for technical accuracy and final academic submission remains with the authors.'),Spacer(1,55),para(esc(meta['authors_line']),'center')]);c.showPage()
    listpage(c,'List of Figures',9,figs);c.showPage()
    listpage(c,'List of Tables',10,tables);c.showPage()
    frontpage(c,'Abstract',11,[
        para('Government scheme information is distributed across portals, departmental pages and frequently revised policy documents. Citizens face difficulty finding relevant programmes, interpreting conditions and understanding whether a later policy version affects a previous assessment. SchemeGuard addresses this problem through profile-first discovery, deterministic eligibility evaluation and evidence-preserving document intelligence.'),
        para('The system combines a Next.js interface with a modular FastAPI backend, PostgreSQL, versioned rules, PyMuPDF, Gemini structured extraction, checkpointed LangGraph workflows and Celery-based monitoring. Optional user details drive explainable category relevance; they do not imply eligibility. AI proposes candidate expressions, while human review and source-page validation precede immutable publication. A typed three-valued engine produces PASS, FAIL or UNKNOWN, and saved assessments pin their original evidence and policy version.'),
        para('The recorded application contains 282 source-traceable government discovery records and one separately identified development scheme. No government rule set is currently approved. The latest recorded regression run passed 491 backend tests, 84 frontend tests and nine browser tests. Isolated synthetic workflows verified publication, historical replay, change comparison, reassessment and notification deduplication. Real Gemini extraction accuracy, independent reviewer agreement and live cloud deployment remain unverified.'),
        para('<b>Keywords:</b> government schemes, explainable recommendations, deterministic eligibility, document intelligence, evidence provenance, human review, policy monitoring.','small')]);c.showPage()
    # Three-page contents, matching the reference's roman preliminary sequence.
    contents=[(0,'Acknowledgement','viii'),(0,'Abstract','xi')]+[(level,text,str(pg)) for level,text,pg in headings]
    chunks=[contents[i:i+20] for i in range(0,len(contents),20)]
    for j,chunk in enumerate(chunks):
        c.setFont('TimesB',20.7);c.drawString(LEFT,H-112,'Contents' if j==0 else 'Contents (continued)')
        y=H-155
        for level,text,pg in chunk:
            y=index_entry(c,text,pg,y,bold=level==0,indent=0 if level==0 else 14)
            if y<65:raise RuntimeError('Contents page overflow')
        c.drawCentredString(LEFT+WIDTH/2,38,roman(12+j));c.showPage()
    c.addPageLabel(11+len(chunks),style='ARABIC',start=1)
    for n,p in enumerate(pages,1):
        c.bookmarkPage('body'+str(n));
        if p.kind=='chapter':c.addOutlineEntry(p.number+' '+p.title,'body'+str(n),0)
        standard(c,p,n);c.showPage()
    c.save()
    (OUT/'report_inventory.json').write_text(json.dumps({'pdf':target.name,'preliminary_pages':11+len(chunks),'body_pages':len(pages),'total_pages':11+len(chunks)+len(pages),'headings':headings,'figures':figs,'tables':tables,'snapshot_date':'2026-11-14','branding':'SchemeGuard','source_format_pages':31},indent=2))
    print(target);print('Pages:',11+len(chunks)+len(pages))

if __name__=='__main__':build()
