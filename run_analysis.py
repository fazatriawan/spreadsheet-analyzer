import sys
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()

from core.cache_manager import CacheManager
from core.formula_parser import FormulaParser
from core.dependency_graph import DependencyGraph
from visualizer.dashboard import generate_dashboard

cache = CacheManager()
url = 'https://docs.google.com/spreadsheets/d/1buwCNKe-YZE1gSgPYDTh-5EKvqPmzVj-f8bWK_bk_6s/edit?usp=sharing'
data = cache.load(url)
print(f"Loaded: {data['title']} - {len(data['sheets'])} sheets")

parser = FormulaParser(data.get('named_ranges', []))
all_a = {}
for sn, sd in data['sheets'].items():
    all_a.update(parser.parse_sheet(sd, sn))
print(f"Total formulas: {len(all_a)}")

dg = DependencyGraph()
dg.build(data, all_a)
gs = dg.get_summary()
print(f"Graph: {gs['total_nodes']} nodes, {gs['total_edges']} edges")
print(f"Formula cells: {gs['formula_cells']}")
print(f"Missing refs: {len(gs['missing_refs'])}")
print(f"Circular refs: {len(gs['circular_refs'])}")
print(f"Orphan cells: {len(gs['orphan_cells'])}")

print("Generating dashboard...")
dp = generate_dashboard(all_a, gs, '', 'analysis')
print(f"Done: {dp}")
