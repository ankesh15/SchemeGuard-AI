from pathlib import Path
import json, re
from pypdf import PdfReader

root=Path(__file__).resolve().parent.parent
r=PdfReader(root/'SchemeGuard_Project_Report.pdf')
inv=json.loads((root/'report_inventory.json').read_text())
text='\n'.join(p.extract_text() or '' for p in r.pages)
assert len(r.pages)==inv['total_pages']==70
assert len(inv['figures'])==8 and len(inv['tables'])==22
assert not re.search(r'SchemeGuard\s*AI|schemeguardai',text,re.I)
assert '\ufffd' not in text and '\u25a0' not in text
assert not re.search('[\u2010-\u2015\u2212]',text)
assert not re.search(r'\[Name|\[Insert|\[Add |\[Authors|to be verified|TODO|lorem ipsum',text,re.I)
assert r.page_labels[2]=='iii' and r.page_labels[14]=='1' and r.page_labels[-1]=='56'
assert all(abs(float(p.mediabox.width)-595.276)<1 and abs(float(p.mediabox.height)-841.89)<1 for p in r.pages)
assert all((p.extract_text() or '').strip() for p in r.pages)
for level,title,page in inv['headings']:
    target=r.pages[inv['preliminary_pages']+page-1].extract_text() or ''
    # Title strings can wrap, so compare normalized whitespace.
    clean=lambda s:re.sub(r'\s+',' ',s).strip()
    assert clean(re.sub(r'^(?:\d+(?:\.\d+)?|A|B)\s+','',title)) in clean(target),title
assert set(re.findall(r'\[(\d+)\]',text))==set(str(i) for i in range(1,20))
links=sum(len(p.get('/Annots',[])) for p in r.pages)
assert links>=90
record={
 'checks_passed':True,
 'pages':len(r.pages),'preliminary_pages':14,'body_pages':56,
 'word_count':len(text.split()),'figures':8,'tables':22,'numbered_references':19,
 'all_heading_page_targets_checked':True,'pdf_links':links,
 'roman_and_arabic_page_labels':True,'all_pages_a4':True,
 'forbidden_brand_instances':0,'missing_glyph_markers':0,
 'report_authoring_only_no_application_tests_rerun':True,
 'visual_qa':'All 70 pages rendered and reviewed in contact sheets; detailed rechecks of contents, diagrams, tables and both screenshot pages after layout correction.',
 'pending':'Confirmed academic identity/supervision details and institutional sign-off/reports.'
}
(root/'report_verification.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record,indent=2))
