"""
CLI Commands:
  python main.py analyze --url "..."                    # Analisis satu link
  python main.py analyze --file "laporan.xlsx"          # Dari file Excel
  python main.py compare --links-file links.json        # Multi-bulan
  python main.py compare --links-file links.json --ai   # + AI report
  python main.py cache --list                           # Lihat cache
  python main.py cache --clear                          # Hapus cache
"""
import click
import webbrowser
import os
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def cli():
    pass


@cli.command()
@click.option("--url", default=None, help="URL Google Sheets")
@click.option("--file", "file_path", default=None, help="Path file Excel (.xlsx/.xls)")
@click.option("--ai", is_flag=True, default=False, help="Tambahkan saran AI")
@click.option("--no-graph", is_flag=True, default=False, help="Skip dependency graph")
@click.option("--no-cache", is_flag=True, default=False, help="Jangan pakai cache")
@click.option("--output", default="analysis", help="Nama file output (tanpa ekstensi)")
def analyze(url, file_path, ai, no_graph, no_cache, output):
    """Analisis satu spreadsheet."""
    from core.reader import SpreadsheetReader
    from core.cache_manager import CacheManager
    from core.formula_parser import FormulaParser
    from core.dependency_graph import DependencyGraph
    from visualizer.graph_viz import generate_dependency_graph
    from visualizer.dashboard import generate_dashboard

    if not url and not file_path:
        console.print("[red]Gunakan --url atau --file[/red]")
        return

    cache = CacheManager()
    reader = SpreadsheetReader()

    if not no_cache and url and cache.has_cache(url):
        with console.status("Memuat dari cache..."):
            data = cache.load(url)
    else:
        with console.status("Membaca spreadsheet..."):
            data = reader.read_from_url(url) if url else reader.read_from_excel(file_path)
        if url and not no_cache:
            cache.save(url, data)

    console.print(f"[green]'{data['title']}' - {len(data['sheets'])} sheet(s)[/green]")

    parser = FormulaParser(data.get("named_ranges", []))
    all_a = {}
    with console.status("Parsing formula..."):
        for sn, sd in data["sheets"].items():
            all_a.update(parser.parse_sheet(sd, sn))

    dg = DependencyGraph()
    with console.status("Building dependency graph..."):
        dg.build(data, all_a)
    gs = dg.get_summary()

    console.print(f"Formula: {gs['formula_cells']} | Cells: {gs['total_cells']} | "
                  f"Missing refs: {len(gs['missing_refs'])} | Circular: {len(gs['circular_refs'])}")

    ai_r = ""
    if ai:
        from core.ai_suggester import AISuggester
        with console.status("Generating AI report..."):
            ai_r = AISuggester().generate_improvement_report(all_a, gs)

    with console.status("Generating dashboard..."):
        dp = generate_dashboard(all_a, gs, ai_r, output)
        if not no_graph:
            generate_dependency_graph(dg.graph, all_a, output)

    webbrowser.open(f"file://{os.path.abspath(dp)}")
    console.print(f"[bold green]Done: {os.path.abspath(dp)}[/bold green]")


@cli.command()
@click.option("--links-file", default=None, help="Path ke links.json")
@click.option("--url", "urls", multiple=True, help="URL langsung (bisa multiple)")
@click.option("--label", "labels", multiple=True, help="Label untuk tiap URL")
@click.option("--sheet", "sheet_name", default=None, help="Nama sheet yang dibandingkan")
@click.option("--ai", is_flag=True, default=False, help="Tambahkan analisis AI")
@click.option("--force-refresh", is_flag=True, default=False, help="Fetch ulang semua, abaikan cache")
@click.option("--threshold", default=20.0, help="Threshold % perubahan dianggap drastis (default: 20)")
@click.option("--output", default="comparison", help="Nama file output")
def compare(links_file, urls, labels, sheet_name, ai, force_refresh, threshold, output):
    """Bandingkan banyak spreadsheet (multi-bulan)."""
    import json
    from core.multi_reader import MultiReader
    from comparator.schema_comparator import extract_schema, compare_schemas
    from comparator.value_comparator import compare_numeric_values
    from comparator.trend_analyzer import analyze_trends
    from visualizer.comparison_dashboard import generate_comparison_dashboard

    links = []
    if links_file:
        with open(links_file) as f:
            links = json.load(f)
    elif urls:
        for i, u in enumerate(urls):
            links.append({"url": u, "label": labels[i] if i < len(labels) else f"Period {i + 1}"})

    if not links:
        console.print("[red]Gunakan --links-file links.json atau --url[/red]")
        console.print('\nFormat links.json:\n[\n  {"url": "https://...", "label": "Jan 2024"},\n  {"url": "https://...", "label": "Feb 2024"}\n]')
        return

    console.print(f"\nMembandingkan [bold]{len(links)}[/bold] periode...")
    mr = MultiReader(use_cache=True)
    monthly = mr.read_multiple(links, force_refresh=force_refresh)
    valid = {k: v for k, v in monthly.items() if "error" not in v}

    if len(valid) < 2:
        console.print("[red]Minimal 2 link valid diperlukan[/red]")
        return

    with console.status("Membandingkan struktur..."):
        schemas = {lb: extract_schema(d) for lb, d in valid.items()}
        sc = compare_schemas(schemas)

    all_sheets = set()
    for d in valid.values():
        all_sheets.update(d.get("sheets", {}).keys())
    targets = [sheet_name] if sheet_name else list(all_sheets)

    vc, tr = {}, {}
    with console.status("Analisis nilai & tren..."):
        for sn in targets:
            comp = compare_numeric_values(valid, sn, threshold)
            if "error" not in comp:
                vc[sn] = comp
                tr[sn] = analyze_trends(comp)

    ai_r = ""
    if ai:
        from core.ai_suggester import AISuggester
        all_drastic = [d for c in vc.values() for d in c.get("drastic_changes", [])]
        all_trends = {col: t for sheet_t in tr.values() for col, t in sheet_t.items()}
        with console.status("AI analysis..."):
            ai_r = AISuggester().analyze_multi_month(
                list(valid.keys()), all_drastic, sc.get("summary", []), all_trends
            )

    with console.status("Generating comparison dashboard..."):
        dp = generate_comparison_dashboard(vc, sc, tr, ai_r, output)

    webbrowser.open(f"file://{os.path.abspath(dp)}")
    console.print(f"\n[bold green]Done: {os.path.abspath(dp)}[/bold green]")

    if sc.get("summary"):
        console.print("\n[yellow]Perubahan Struktur:[/yellow]")
        for s in sc["summary"]:
            console.print(f"  {s}")


@cli.command()
@click.option("--list", "list_cache", is_flag=True, help="Tampilkan daftar cache")
@click.option("--clear", is_flag=True, help="Hapus semua cache")
@click.option("--clear-url", default=None, help="Hapus cache untuk URL tertentu")
def cache(list_cache, clear, clear_url):
    """Kelola cache lokal."""
    from core.cache_manager import CacheManager
    cm = CacheManager()
    if list_cache:
        cached = cm.list_cached()
        if not cached:
            console.print("Belum ada cache")
            return
        t = Table(title=f"Cache ({cm.get_cache_size_mb()} MB)")
        t.add_column("Label", style="cyan")
        t.add_column("Sheets")
        t.add_column("Di-cache", style="dim")
        for c in cached:
            t.add_row(c["label"], ", ".join(c.get("sheets", [])[:3]), c["cached_at"][:16])
        console.print(t)
    elif clear:
        cm.invalidate_all()
        console.print("Cache dihapus semua")
    elif clear_url:
        cm.invalidate(clear_url)
        console.print(f"Cache dihapus: {clear_url[:50]}")
    else:
        console.print("Gunakan --list, --clear, atau --clear-url")


if __name__ == "__main__":
    cli()
