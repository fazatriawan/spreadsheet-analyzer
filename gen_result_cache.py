import sys, os, json, hashlib
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"C:\projects\spreadsheet-analyzer")
from dotenv import load_dotenv
load_dotenv(dotenv_path=r"C:\projects\spreadsheet-analyzer\.env")

from core.cache_manager import CacheManager
from core.formula_parser import FormulaParser
from core.dependency_graph import DependencyGraph

url = 'https://docs.google.com/spreadsheets/d/1buwCNKe-YZE1gSgPYDTh-5EKvqPmzVj-f8bWK_bk_6s/edit?usp=sharing'
cache = CacheManager()
data = cache.load(url)
print('Loaded:', data['title'], '-', len(data['sheets']), 'sheets')

parser = FormulaParser(data.get('named_ranges', []))
all_a = {}
for sn, sd in data['sheets'].items():
    all_a.update(parser.parse_sheet(sd, sn))
print('Formulas:', len(all_a))

dg = DependencyGraph()
dg.build(data, all_a)
gs = dg.get_summary()
print('Graph:', gs['total_nodes'], 'nodes')

cats = {}
for a in all_a.values():
    cats[a.formula_category] = cats.get(a.formula_category, 0) + 1

top_complex = sorted(
    [(k, v.complexity_score, v.formula_category, v.raw_formula[:80]) for k, v in all_a.items()],
    key=lambda x: x[1], reverse=True
)[:30]

warned = [
    {'cell': k, 'warnings': v.warnings, 'formula': v.raw_formula[:60]}
    for k, v in all_a.items() if v.warnings
][:50]

result = {
    'title': data['title'],
    'sheet_count': len(data['sheets']),
    'sheet_names': list(data['sheets'].keys()),
    'formula_count': len(all_a),
    'categories': cats,
    'top_complex': top_complex,
    'warnings': warned,
    'graph_summary': {k: v for k, v in gs.items() if k not in ('circular_refs', 'missing_refs', 'orphan_cells')},
    'missing_count': len(gs.get('missing_refs', [])),
    'orphan_count': len(gs.get('orphan_cells', [])),
    'circular_count': len(gs.get('circular_refs', [])),
    'ai_report': '',
    'complexity_scores': [v.complexity_score for v in all_a.values()],
}

sheet_id = CacheManager._extract_sheet_id(url)
k = hashlib.md5(sheet_id.encode()).hexdigest()[:12]
out = os.path.join(r'C:\projects\spreadsheet-analyzer\cache', k + '_result.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False)
print('Result cache saved:', out)
