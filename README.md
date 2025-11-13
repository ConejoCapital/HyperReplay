# HyperReplay

HyperReplay is a **general-purpose Hyperliquid replay toolkit**. It ships with everything required to reconstruct historical account state, fills, and ledger movements from the public S3 archives. Out of the box we demonstrate the full October 10 2025 ADL cascade, rebuilt by ConejoCapital with support from with the Hydromancer teamm, AlgoBluffy & Xeno. The same tooling can be pointed at *any* time window once you provide the corresponding raw inputs.

This repository packages:
- Raw inputs (node fills, misc events, clearinghouse snapshots) split into GitHub-friendly chunks.
- Canonical outputs (12-minute ADL fills, liquidation feed, real-time per-position metrics) that match the datasets published in [HyperMultiAssetedADL](https://github.com/ConejoCapital/HyperMultiAssetedADL).
- Reproduction scripts that rebuild the full real-time account reconstruction and net-volume analysis from scratch, including complete misc-ledger coverage (internal transfers, spot transfers, vault flows, rewards, liquidation overrides, etc.).

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

These match the datasets published in [HyperMultiAssetedADL](https://github.com/ConejoCapital/HyperMultiAssetedADL) and power HyperFireworks. They reflect the **cash-only baseline** replay (snapshot unrealized PnL removed) and include:
- 34,983 ADL events with real-time leverage (median 0.18x, p95 4.23x, p99 74.18x)
- Negative-equity detection for 1,147 accounts (aggregate −$109.29M)

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

## Adapting to other windows

1. **Download the relevant S3 shards** for the period you care about (node fills, misc events, clearinghouse snapshot). The scripts expect the same directory structure — adjust the filenames or symlink if necessary.
2. **Update the time bounds** inside `scripts/replay_real_time_accounts.py` (and the extraction script if you are trimming the fills file). The defaults are hard-coded to the ADL window (`ADL_START_TIME` / `ADL_END_TIME`).
3. **Regenerate**:
   ```bash
   python scripts/extract_full_12min_adl.py      # or your custom extraction script
   python scripts/replay_real_time_accounts.py
   ```
4. **Publish your outputs** under `data/canonical/` (or a new folder) to share them with downstream researchers.

Ledger deltas beyond deposits/withdrawals are already handled (internal/sub-account transfers, spot transfers, vault deposits/withdrawals, vault commissions, rewards, liquidation overrides, etc.), so no additional plumbing is needed when you move to a different timeframe.

## Notes

- The raw clearinghouse snapshot archive (≈260 MB) was split into three parts to stay below GitHub's 100 MB limit. The scripts will stitch the pieces together automatically.
- The repository currently targets the October 10, 2025 cascade. You can adapt the scripts to different windows by swapping in the appropriate S3 and clearinghouse snapshots.

## License

HyperReplay is distributed under the **HyperReplay Custom License v1.0**, which allows free non-commercial use and derivative work as long as the attribution requirements are preserved. **Commercial use requires a paid commercial license from ConejoCapital.**

- For the full terms, see [`HyperReplay_Custom_License_v1.0.md`](HyperReplay_Custom_License_v1.0.md).
- To discuss commercial licensing, contact **x.com/ConejoCapital** or **mauricio.jp.trujillo@gmail.com**.

## Acknowledgements

- Hydromancer team (AlgoBluffy & Xeno) — initial ledger deep-dives and infrastructure support.
- Hyperliquid for publishing the full S3 archive.
- Everyone contributing reproducibility feedback via [HyperMultiAssetedADL](https://github.com/ConejoCapital/HyperMultiAssetedADL).

