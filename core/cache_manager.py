"""
Cache Manager: Simpan & load data spreadsheet ke JSON lokal.

Kenapa penting:
- Google Sheets API quota: 60 req/menit
- 12 bulan = 12 fetch = lambat + bisa kena limit
- Dengan cache: hanya link BARU yang di-fetch
- Cache bisa di-invalidate manual jika data berubah

Struktur:
  cache/index.json   -> { hash: {label, url, file, cached_at, sheets} }
  cache/[hash].json  -> data spreadsheet lengkap
"""
import json, os, hashlib, re
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    from config import CACHE_DIR
except ImportError:
    CACHE_DIR = "./cache"

INDEX_FILE = os.path.join(CACHE_DIR, "index.json")


class CacheManager:
    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = cache_dir or CACHE_DIR
        os.makedirs(self.cache_dir, exist_ok=True)
        global INDEX_FILE
        INDEX_FILE = os.path.join(self.cache_dir, "index.json")
        self.index = self._load_index()

    def _load_index(self) -> dict:
        if not os.path.exists(INDEX_FILE):
            return {}
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        migrated = {}
        changed = False
        for old_key, entry in raw.items():
            url = entry.get("url", "")
            new_key = hashlib.md5(self._extract_sheet_id(url).encode()).hexdigest()[:12]
            migrated[new_key] = entry
            if new_key != old_key:
                changed = True
        if changed:
            with open(INDEX_FILE, "w", encoding="utf-8") as f:
                json.dump(migrated, f, indent=2, ensure_ascii=False)
        return migrated

    def _save_index(self):
        with open(INDEX_FILE, "w", encoding="utf-8") as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)

    @staticmethod
    def _extract_sheet_id(url: str) -> str:
        m = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
        return m.group(1) if m else url.strip()

    def _key(self, url: str) -> str:
        canonical = self._extract_sheet_id(url)
        return hashlib.md5(canonical.encode()).hexdigest()[:12]

    def has_cache(self, url: str) -> bool:
        k = self._key(url)
        return k in self.index and os.path.exists(self.index[k].get("file", ""))

    def load(self, url: str) -> dict | None:
        k = self._key(url)
        if not self.has_cache(url):
            return None
        logger.info(f"  Cache hit: {self.index[k].get('label', url[:40])}")
        with open(self.index[k]["file"], "r", encoding="utf-8") as f:
            return json.load(f)

    def save(self, url: str, data: dict, label: str = ""):
        k = self._key(url)
        cache_file = os.path.join(self.cache_dir, f"{k}.json")
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, default=str)
        self.index[k] = {
            "url": url, "label": label or data.get("title", url[:40]),
            "title": data.get("title", ""), "cached_at": datetime.now().isoformat(),
            "file": cache_file, "sheets": list(data.get("sheets", {}).keys()),
        }
        self._save_index()
        logger.info(f"  Saved to cache: {label or data.get('title', '')}")

    def invalidate(self, url: str):
        k = self._key(url)
        if k in self.index:
            f = self.index[k].get("file", "")
            if os.path.exists(f):
                os.remove(f)
            del self.index[k]
            self._save_index()

    def invalidate_all(self):
        for e in self.index.values():
            if os.path.exists(e.get("file", "")):
                os.remove(e["file"])
        self.index = {}
        self._save_index()

    def list_cached(self) -> list:
        return sorted(
            [e for k, e in self.index.items() if os.path.exists(e.get("file", ""))],
            key=lambda x: x["cached_at"]
        )

    def get_cache_size_mb(self) -> float:
        total = sum(
            os.path.getsize(e["file"]) for e in self.index.values()
            if os.path.exists(e.get("file", ""))
        )
        return round(total / 1024 / 1024, 2)
