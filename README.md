# HyperReplay

Tools and canonical datasets to replay Hyperliquid's October 10, 2025 ADL cascade from public S3 data and clearinghouse snapshots.

This repository packages:
- Raw inputs (node fills, misc events, clearinghouse snapshots) split into GitHub-friendly chunks.
- Canonical outputs (12-minute ADL fills, liquidation feed, real-time per-position metrics).
- Reproduction scripts that rebuild the full real-time account reconstruction and net-volume analysis from scratch.

## Repository Layout

```
HyperReplay/
├── data/
│   ├── raw/                # Raw S3 + clearinghouse artifacts (split into <100MB chunks)
│   └── canonical/          # Canonical CSV + JSON outputs produced by the replay
├── docs/
├── scripts/                # Reproduction utilities
└── README.md
```

### Raw inputs (`data/raw/`)
- `node_fills_20251010_21.lz4.part-*` – Hyperliquid node fills for 21:00–22:00 UTC.
- `misc_events_20251010_21.lz4` – Funding + ledger events for the same hour.
- `asset_ctxs_20251010.csv.lz4` – Instrument metadata.
- `clearinghouse_snapshot_20251010.tar.xz.part-*` – Clearinghouse snapshot + fills/misc JSON (20:00–22:00 UTC) used for real-time reconstruction.

Recombine split archives before running the scripts (details below).

### Canonical outputs (`data/canonical/`)
- `adl_fills_full_12min_raw.csv`
- `adl_net_volume_full_12min.csv`
- `ADL_NET_VOLUME_FULL_12MIN.md`
- `adl_detailed_analysis_REALTIME.csv`
- `adl_by_user_REALTIME.csv`
- `adl_by_coin_REALTIME.csv`
- `realtime_analysis_summary.json`
- `liquidations_full_12min.csv`

These match the datasets published in [HyperMultiAssetedADL](https://github.com/ConejoCapital/HyperMultiAssetedADL) and power HyperFireworks.

### Scripts (`scripts/`)
- `extract_full_12min_adl.py` – Rebuilds the canonical ADL fills and net-volume report from `node_fills`.
- `replay_real_time_accounts.py` – Reconstructs account values, leverage, and equity in real time using the clearinghouse snapshot + fill/misc streams.

Both scripts automatically concatenate split archives when necessary and emit results into `data/canonical/`.

## Quick Start

1. **Install dependencies** (Python 3.10+):
   ```bash
   pip install pandas lz4 tqdm
   ```

2. **Reassemble split archives** (optional – scripts will do this automatically, but these commands show the manual steps):
   ```bash
   # Rebuild node_fills lz4
   cat data/raw/node_fills_20251010_21.lz4.part-* > data/raw/node_fills_20251010_21.lz4

   # Rebuild clearinghouse snapshot archive and extract JSON inputs
   cat data/raw/clearinghouse_snapshot_20251010.tar.xz.part-* > data/raw/clearinghouse_snapshot_20251010.tar.xz
   tar -xJf data/raw/clearinghouse_snapshot_20251010.tar.xz -C data/raw
   ```

3. **Reproduce the canonical datasets:**
   ```bash
   # From repository root
   python scripts/extract_full_12min_adl.py
   python scripts/replay_real_time_accounts.py
   ```

   Outputs are written to `data/canonical/` and will match the shipped CSV/JSON artifacts.

4. **Verify canonical CSVs (optional):**
   ```python
   import pandas as pd
   df = pd.read_csv('data/canonical/adl_detailed_analysis_REALTIME.csv')
   assert len(df) == 34_983
   assert {'leverage_realtime', 'is_negative_equity'} <= set(df.columns)
   ```

## Notes

- The raw clearinghouse snapshot archive (≈260 MB) was split into three parts to stay below GitHub's 100 MB limit. The scripts will stitch the pieces together automatically.
- Raw approximation-era CSVs were deliberately excluded. Only canonical, real-time outputs are distributed here.
- The repository currently targets the October 10, 2025 cascade. You can adapt the scripts to different windows by swapping in the appropriate S3 and clearinghouse snapshots.

## License

GPL-3.0. See [LICENSE](LICENSE).
