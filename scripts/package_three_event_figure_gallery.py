"""Assemble and verify the current seven-page gallery with the bundled PDF runtime."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse
import hashlib
import json
import sys
import zipfile
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'outputs/research_2026/three_event_scientific_figures_20261015'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links = []; self.ids = set(); self.articles = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a: self.ids.add(a['id'])
        if tag == 'article': self.articles.append(a.get('id'))
        for k in ['src', 'href']:
            if k in a: self.links.append(a[k])


def main():
    meta = json.loads((OUT/'figure_manifest.json').read_text())
    captions = '\n\n'.join(
        f"{m['stem']} | {m['title']}\n\n中文图注\n{m['caption_cn']}\n\nEnglish caption\n{m['caption_en']}"
        for m in meta)
    (OUT/'figure_captions.txt').write_text(captions+'\n', encoding='utf-8')
    expected = ['M1_air_sea_evolution', 'M2_JFM_configuration', 'M3_transport_persistence',
                'S1_wind_reference', 'S2_local_process_limits',
                'M4_transport_current_advection', 'M5_wind_current_momentum']
    assert [m['stem'] for m in meta] == expected
    qa = json.loads((OUT/'validation.json').read_text())
    paper_final = qa.get('paper_final', False)
    writer = PdfWriter()
    archive = OUT/'archive/before_summer_mechanisms_20261015'
    previous = (PdfReader(archive/'three_event_figure_book.pdf')
                if (archive/'three_event_figure_book.pdf').exists() and not paper_final else None)
    for i, m in enumerate(meta):
        stem = m['stem']; reader = PdfReader(OUT/f'{stem}.pdf')
        assert len(reader.pages) == 1
        for ext in ['png', 'pdf', 'svg']:
            assert (OUT/f'{stem}.{ext}').stat().st_size > 1000
        # Keep the original book's content streams and resources together.
        # Individual Matplotlib PDFs can use different font-resource names.
        writer.add_page(previous.pages[i] if previous is not None and i < 5 else reader.pages[0])
        writer.add_outline_item(m['title'], len(writer.pages)-1)
    writer.add_metadata({'/Title':'Three-event ENSO figures: summer-current mechanisms',
                         '/Subject':'Five main figures and two supporting figures; seven pages'})
    tmp = OUT/'three_event_figure_book.pending.pdf'
    with tmp.open('wb') as f: writer.write(f)
    new = PdfReader(tmp); assert len(new.pages) == 7
    assert 'SSTA' in new.pages[0].extract_text()
    assert 'JFM' in new.pages[1].extract_text()
    assert 'transport difference' in new.pages[5].extract_text()
    assert 'zonal current anomaly' in new.pages[6].extract_text()
    jfm_reviewed = '--record-jfm-visual-review' in sys.argv
    current_reviewed = '--record-current-visual-review' in sys.argv
    section_reviewed = '--record-section-visual-review' in sys.argv
    folded_reviewed = '--record-folded-visual-review' in sys.argv
    directional_reviewed = '--record-directional-visual-review' in sys.argv
    assert sum([jfm_reviewed,current_reviewed,section_reviewed,folded_reviewed,directional_reviewed])<=1
    unchanged_book_pages=[]
    if jfm_reviewed:
        assert 'D26' not in new.pages[1].extract_text()
        assert 'isopycnal depth anomaly' in new.pages[1].extract_text()
        archived=PdfReader(OUT/'archive/before_jfm_color_revision_20261015/three_event_figure_book.pdf')
        unchanged_book_pages=[i+1 for i in range(7) if i!=1 and
            archived.pages[i].get_contents().get_data()==new.pages[i].get_contents().get_data()]
        assert unchanged_book_pages==[1,3,4,5,6,7]
    if current_reviewed or section_reviewed or folded_reviewed or directional_reviewed:
        old_folder=('before_directional_advection_20261016' if directional_reviewed else
                    'before_folded_current_block_20261015' if folded_reviewed else
                    'before_140W_section_20261015' if section_reviewed else 'before_current_color_revision_20261015')
        archived=PdfReader(OUT/'archive'/old_folder/'three_event_figure_book.pdf')
        unchanged_book_pages=[i+1 for i in range(7) if i!=5 and
            archived.pages[i].get_contents().get_data()==new.pages[i].get_contents().get_data()]
        assert unchanged_book_pages==[1,2,3,4,5,7]
        if section_reviewed:
            assert '140' in new.pages[5].extract_text()
            assert qa['M4_section_revision']['panel_count']==8
        if folded_reviewed:
            assert 'folded out' in new.pages[5].extract_text()
            assert qa['M4_folded_revision']['panel_count']==6
            assert float(new.pages[5].mediabox.width)>700
        if directional_reviewed:
            assert 'Meridional' in new.pages[5].extract_text()
            assert 'Nonlinear interaction' in new.pages[5].extract_text()
            assert qa['M4_directional_revision']['panel_count']==6
    preserved_pages = []
    if previous is not None:
        old = PdfReader(archive/'three_event_figure_book.pdf')
        preserved_pages = [old.pages[i].get_contents().get_data() ==
                           new.pages[i].get_contents().get_data() for i in range(5)]
        assert all(preserved_pages)
    tmp.replace(OUT/'three_event_figure_book.pdf')
    parser = Links(); parser.feed((OUT/'index.html').read_text())
    assert parser.articles == expected
    missing = []
    for link in parser.links:
        u = urlparse(link)
        if u.scheme or u.netloc: continue
        if not u.path:
            if u.fragment and u.fragment not in parser.ids: missing.append(link)
        elif not (OUT/unquote(u.path)).exists(): missing.append(link)
    assert not missing, missing
    qa = json.loads((OUT/'validation.json').read_text())
    qa.pop('S3_model_refitted_full_sample', None)
    qa.pop('fullsample_update_verification', None)
    qa['gallery_delivery'] = {'pdf_pages':7, 'main_figures':5, 'supporting_figures':2,
        'first_five_pdf_page_contents_unchanged':preserved_pages,
        'paper_final_assembled_from_current_figures':paper_final,
        'gallery_article_order':expected, 'missing_local_links':missing,
        'individual_figure_formats_checked':21, 'final_group_replaces_old_S3':True}
    reviewed = '--record-visual-review' in sys.argv
    qa['visual_pdf_review'] = {
        'status':('PASS: all seven rendered PDF pages visually checked for labels, legends, units, '
                  'oblique-map/section alignment and page boundaries' if reviewed else 'Pending rendered-page review'),
        'page_numbers':list(range(1,8))}
    if jfm_reviewed:
        assert qa['JFM_color_revision']['other_figure_files_unchanged']==24
        qa['visual_pdf_review']={'status':'PASS: revised JFM page 2 rendered and checked; other six pages match the previously reviewed book',
            'page_numbers':list(range(1,8)), 'newly_reviewed_page_numbers':[2],
            'unchanged_book_page_numbers':unchanged_book_pages}
    if current_reviewed:
        assert qa['M4_color_revision']['other_figure_files_unchanged']==24
        qa['visual_pdf_review']={'status':'PASS: revised current-structure page 6 rendered and checked; other six pages match the previously reviewed book',
            'page_numbers':list(range(1,8)), 'newly_reviewed_page_numbers':[6],
            'unchanged_book_page_numbers':unchanged_book_pages}
    if section_reviewed:
        assert qa['M4_section_revision']['other_figure_files_unchanged']==24
        qa['visual_pdf_review']={'status':'PASS: revised page 6 with 140W sections rendered and checked; other six pages match the previously reviewed book',
            'page_numbers':list(range(1,8)), 'newly_reviewed_page_numbers':[6],
            'unchanged_book_page_numbers':unchanged_book_pages}
    if folded_reviewed:
        assert qa['M4_folded_revision']['other_figure_files_unchanged']==24
        qa['visual_pdf_review']={'status':'PASS: enlarged folded three-face M4 page rendered and checked; other six pages match the previously reviewed book',
            'page_numbers':list(range(1,8)), 'newly_reviewed_page_numbers':[6],
            'unchanged_book_page_numbers':unchanged_book_pages}
    if directional_reviewed:
        assert qa['M4_directional_revision']['other_figure_files_unchanged']==24
        qa['visual_pdf_review']={'status':'PASS: M4 full zonal/meridional-advection panels rendered and checked; other six pages match the previously reviewed book',
            'page_numbers':list(range(1,8)), 'newly_reviewed_page_numbers':[6],
            'unchanged_book_page_numbers':unchanged_book_pages}
    (OUT/'validation.json').write_text(json.dumps(qa, ensure_ascii=False, indent=2)+'\n')
    scripts = ['build_three_event_scientific_figures.py', 'update_three_event_mechanism_figures.py',
               'package_three_event_figure_gallery.py', 'paper_figure_blocks.py',
               'analyze_three_event_directional_advection.py','report_three_event_directional_advection.py']
    with zipfile.ZipFile(OUT/'figure_data.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted((OUT/'source_data').iterdir()):
            if p.name not in ['fixed_model_replay.csv', 'volume_budgets.csv', 'january_WWV26.csv', 'january_ocean_fields.nc']:
                z.write(p, 'source_data/'+p.name)
        for name in ['input_manifest.json', 'figure_manifest.json', 'figure_captions.txt', 'validation.json']:
            z.write(OUT/name, name)
        for name in scripts: z.write(ROOT/'scripts'/name, name)
    with zipfile.ZipFile(OUT/'figure_data.zip') as z:
        assert z.testzip() is None
        assert z.read('source_data/summer_case_seasons.csv') == (OUT/'source_data/summer_case_seasons.csv').read_bytes()
    files = [OUT/'index.html', OUT/'three_event_figure_book.pdf', OUT/'figure_data.zip',
             OUT/'figure_manifest.json', OUT/'figure_captions.txt', OUT/'input_manifest.json']
    files += [OUT/f'{s}.{ext}' for s in expected for ext in ['png', 'pdf', 'svg']]
    delivery = {'status':'PASS', 'pdf_pages':7, 'files_sha256':{p.name:sha(p) for p in files},
                'updated_scripts_sha256':{n:sha(ROOT/'scripts'/n) for n in scripts}}
    (OUT/'gallery_delivery_manifest.json').write_text(json.dumps(delivery, ensure_ascii=False, indent=2)+'\n')
    print('PASS: 7 PDF pages, 21 figure formats, gallery links and data ZIP verified.', flush=True)


if __name__ == '__main__': main()
