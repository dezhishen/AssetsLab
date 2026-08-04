# Current AssetsLab Preview

This preview was rewritten on 2026-07-31 to show only the current test base,
the current four-direction runtime composition, the automatic movement GIF,
the vertical candidate, and the isolated pixel-art style experiment.

Build the current assets and publish a Tailscale snapshot from the repository
root:

```bash
python workflow/tools/assetslab.py capture-walk --rebuild-head --vertical-candidate --vertical-only
python workflow/tools/lan_preview_server.py --port 8765 --directory prototype/preview --name current_test_base
```

The snapshot is copied into `prototype/preview/snapshots/` and can be opened
from the Tailscale URL printed by `workflow/tools/lan_preview_server.py`.

The page intentionally excludes retired RGS proxies, old body candidates,
Skeleton2D experiments, obsolete calibration pages, and previous GIFs.
