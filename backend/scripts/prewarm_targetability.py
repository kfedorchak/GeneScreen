"""Pre-fetch Open Targets tractability for every dependency gene in the demo
subset, into app/data/targetability_cache.json, so the live agent is instant at
runtime (and we don't loop the API under load). Re-run to refresh; already-cached
genes are skipped. Unresolved genes (lncRNAs, clones) are negatively cached.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

from app.agents import targetability
from app.analysis import filters
from app.data import loader


def main() -> int:
    ds = loader.load_demo_subset()
    genes = sorted({filters.strip_entrez(g) for g in ds.B.columns})
    cache = targetability._load_cache()
    todo = [g for g in genes if g.upper() not in cache]
    print(f"{len(genes)} dependency genes; {len(todo)} to fetch", flush=True)

    def work(g: str):
        try:
            return g, targetability.fetch_live(g)
        except Exception as e:  # noqa: BLE001
            return g, {"_error": str(e)[:80]}

    done = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        for g, data in ex.map(work, todo):
            if data is not None and "_error" not in data:
                cache[g.upper()] = data
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(todo)}", flush=True)
                targetability._save_cache()

    targetability._save_cache()
    resolved = sum(1 for v in cache.values() if v.get("ensembl_id"))
    print(f"cache: {len(cache)} genes ({resolved} resolved to Ensembl)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
