"""
Multi Reader: Baca banyak link dengan cache + rate limiting.

Batas aman:
- Max 12 link sekaligus (1 tahun) tanpa masalah
- Batch per 6 link dengan jeda otomatis
- Cache JSON lokal: link yang sudah pernah dibaca -> instan dari disk
- Hanya link BARU yang fetch dari Google API
"""
import time
from tqdm import tqdm
from rich.console import Console
from rich.table import Table
from core.reader import SpreadsheetReader
from core.cache_manager import CacheManager
from utils.logger import get_logger

logger = get_logger(__name__)
console = Console()

MAX_PER_BATCH = 6
DELAY_BETWEEN = 2.0
RECOMMENDED_MAX = 12


class MultiReader:
    def __init__(self, use_cache=True):
        self.reader = SpreadsheetReader()
        self.cache = CacheManager()
        self.use_cache = use_cache

    def read_multiple(self, links: list, force_refresh=False) -> dict:
        """
        links: [{"url": "...", "label": "Jan 2024"}, ...]
        Return: {"Jan 2024": data, "Feb 2024": data, ...}
        """
        total = len(links)
        if total > RECOMMENDED_MAX:
            console.print(f"[yellow]  {total} link. Rekomendasi max {RECOMMENDED_MAX}.[/yellow]")

        results, to_fetch, from_cache = {}, [], []
        for entry in links:
            url = entry["url"]
            if self.use_cache and not force_refresh and self.cache.has_cache(url):
                from_cache.append(entry)
            else:
                to_fetch.append(entry)

        if from_cache:
            console.print(f"[green]{len(from_cache)} link[/green] dari cache")
            for e in from_cache:
                data = self.cache.load(e["url"])
                label = e.get("label") or data.get("title", e["url"][:30])
                results[label] = data

        if to_fetch:
            console.print(f"[yellow]{len(to_fetch)} link baru[/yellow] di-fetch...")
            batches = [to_fetch[i:i + MAX_PER_BATCH] for i in range(0, len(to_fetch), MAX_PER_BATCH)]
            for bi, batch in enumerate(batches):
                if bi > 0:
                    wait = MAX_PER_BATCH * DELAY_BETWEEN
                    console.print(f"  Rate limit pause {wait}s...")
                    time.sleep(wait)
                console.print(f"\nBatch {bi + 1}/{len(batches)} ({len(batch)} link):")
                for entry in tqdm(batch, desc="  Fetch", unit="link"):
                    url, label = entry["url"], entry.get("label", "")
                    try:
                        data = (
                            self.reader.read_from_excel(url)
                            if url.endswith((".xlsx", ".xls"))
                            else self.reader.read_from_url(url)
                        )
                        label = label or data.get("title", url[:40])
                        if self.use_cache:
                            self.cache.save(url, data, label)
                        results[label] = data
                        time.sleep(DELAY_BETWEEN)
                    except Exception as e:
                        console.print(f"  [red]Error {label or url[:40]}: {e}[/red]")
                        results[label or url[:40]] = {"error": str(e)}

        table = Table(title="Multi-Link Summary")
        table.add_column("Label", style="cyan")
        table.add_column("Sheet(s)", style="white")
        table.add_column("Status", justify="center")
        for label, data in results.items():
            if "error" in data:
                table.add_row(label, "-", "[red]Error[/red]")
            else:
                sheets = ", ".join(list(data.get("sheets", {}).keys())[:3])
                cached = any(e.get("label") == label for e in from_cache)
                status = "[green]Cache[/green]" if cached else "[yellow]Fetched[/yellow]"
                table.add_row(label, sheets, status)
        console.print(table)
        console.print(f"  Cache size: {self.cache.get_cache_size_mb()} MB")
        return results
