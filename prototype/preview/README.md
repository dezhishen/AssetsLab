# Current AssetsLab Preview

This preview was rewritten on 2026-07-31 to show only the current test base,
the current four-direction runtime composition, the automatic movement GIF,
the vertical candidate, and the isolated pixel-art style experiment.

Build the current assets and publish a Tailscale snapshot from the repository
root:

```powershell
.\tools\capture_walk_gif.ps1 -RebuildHead -VerticalCandidate -VerticalOnly
.\tools\serve_preview.ps1 -SnapshotName current_test_base
```

The snapshot is copied into `prototype/preview/snapshots/` and can be opened
from the Tailscale URL printed by `serve_preview.ps1`.

The page intentionally excludes retired RGS proxies, old body candidates,
Skeleton2D experiments, obsolete calibration pages, and previous GIFs.
