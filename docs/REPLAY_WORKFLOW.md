# HyperReplay Workflow Guide

This document explains how to reconstruct Hyperliquid's October 10, 2025 ADL cascade from scratch and how to adapt the workflow to future events.

## 1. Data Sources

| Artifact | Purpose | Location in this repo | Original source |
|----------|---------|------------------------|-----------------|
| `node_fills_20251010_21.lz4.part-*` | All fills for 21:00–22:00 UTC | `data/raw/` | Hyperliquid public S3 (`node_fills_YYYYMMDD_HH.lz4`) |
| `misc_events_20251010_21.lz4` | Funding + ledger updates | `data/raw/` | Hyperliquid public S3 (`misc_events_YYYYMMDD_HH.lz4`) |
| `asset_ctxs_20251010.csv.lz4` | Instrument metadata (tick sizes, lot sizes) | `data/raw/` | Hyperliquid public S3 |
| `20_fills.json`, `21_fills.json` | Clearinghouse fills (20:00–22:00 UTC) | extracted from `clearinghouse_snapshot_20251010.tar.xz.part-*` | Hyperliquid clearinghouse snapshot (block 758750000) |
| `20_misc.json`, `21_misc.json` | Clearinghouse misc events | extracted from archive | same as above |
| `account_value_snapshot_758750000_1760126694218.json` | Account-level cash snapshot | extracted from archive | clearinghouse snapshot |
| `perp_positions_by_market_758750000_1760126694218.json` | Open perp positions per asset | extracted from archive | clearinghouse snapshot |
| `spot_balances__758750000_1760126694218.json` | Spot balances for transfer events | extracted from archive | clearinghouse snapshot |

## 2. Environment Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install pandas lz4 tqdm
```

*Optional:* install `poetry` or `pip-tools` if you prefer lock-file management.

## 3. Rebuild Raw Archives

Scripts attempt to reassemble split files automatically. Manual commands for reference:

```bash
# Reassemble node fills (lz4)
cat data/raw/node_fills_20251010_21.lz4.part-* > data/raw/node_fills_20251010_21.lz4

# Reassemble clearinghouse snapshot (tar.xz) and extract JSON inputs
cat data/raw/clearinghouse_snapshot_20251010.tar.xz.part-* > data/raw/clearinghouse_snapshot_20251010.tar.xz
tar -xJf data/raw/clearinghouse_snapshot_20251010.tar.xz -C data/raw
```

The extraction step yields `20_fills.json`, `21_fills.json`, `20_misc.json`, `21_misc.json`, and the snapshot JSON files required by the reconstruction script.

## 4. Generate Canonical ADL Fills

```bash
python scripts/extract_full_12min_adl.py
```

Outputs written to `data/canonical/`:
- `adl_fills_full_12min_raw.csv`
- `adl_net_volume_full_12min.csv`
- `ADL_NET_VOLUME_FULL_12MIN.md`

These capture all 34,983 ADL fills between 21:15:00 and 21:27:00 UTC with notional totals, per-ticker breakdowns, and methodology notes.

### Customizing for Other Windows
- Update `ADL_START` and `ADL_END` inside the script.
- Swap `node_fills_20251010_21.lz4.part-*` for the desired hour(s).
- Provide the corresponding `misc_events_YYYYMMDD_HH.lz4` file if you also want funding stats.

## 5. Reconstruct Real-Time Account Metrics

```bash
python scripts/replay_real_time_accounts.py
```

Outputs written to `data/canonical/`:
- `adl_detailed_analysis_REALTIME.csv`
- `adl_by_user_REALTIME.csv`
- `adl_by_coin_REALTIME.csv`
- `realtime_analysis_summary.json`

Key metrics include:
- Real-time account value and leverage per ADL event.
- Negative-equity detection (account cash + PNL).
- Counterparty user linkage for every ADL.

### How It Works
1. Load baseline account values and open positions from the clearinghouse snapshot (70 minutes before the cascade).
2. Stream all fills (20:00–22:00 UTC) and misc ledger events in chronological order, updating account cash balances and position sizes.
3. The ledger stream now captures **every** balance delta we observed on-chain (deposits/withdrawals, account-class moves, internal/sub-account transfers, spot transfers, vault deposits/withdrawals/commissions, rewards claims, liquidation overrides, etc.).
4. At each ADL event, capture real-time account value, exposure, and unrealized PNL before the ADL adjustment executes.

### Adapting to Future Snapshots
- Replace the snapshot JSON files with the target block/time.
- Update `SNAPSHOT_TIME`, `ADL_START_TIME`, and `ADL_END_TIME` constants.
- Ensure you have the corresponding `*_fills.json` and `*_misc.json` exports from the clearinghouse snapshot pipeline.

## 6. Liquidation Feed (Optional)

The canonical liquidation dataset (`data/canonical/liquidations_full_12min.csv`) was generated via a similar extraction script (not included yet). For completeness, you can reproduce it by filtering `node_fills` for directions containing `Liquidated` and aligning timestamps with the ADL feed.

## 7. Verification Checklist

To confirm outputs match the published canonical data:

```python
import pandas as pd
from pathlib import Path

root = Path('data/canonical')
assert len(pd.read_csv(root/'adl_fills_full_12min_raw.csv')) == 34_983
assert len(pd.read_csv(root/'adl_detailed_analysis_REALTIME.csv')) == 34_983
```

Key metrics should align with the published verification report:
- 34,983 ADL events
- $2.103B ADL notional
- 94.5% profitable ADLs
- Median leverage 0.18x (p95 4.23x, p99 74.18x)
- 1,147 negative-equity accounts ($ −109.29M aggregate)

## 8. Extending the Workflow

To apply this replay to other assets or time windows:
1. Download the relevant `node_fills`, `misc_events`, and clearinghouse snapshot files from Hyperliquid (public S3 + clearinghouse endpoints).
2. Split large archives into `<100MB` chunks if you need to share them on GitHub.
3. Update script constants (filenames, timestamps).
4. Re-run the extraction and reconstruction scripts.

Consider automating steps 1–3 with a downloader script (future work item for this repository).

## 9. Troubleshooting

- **Missing JSON files**: Ensure the clearinghouse archive parts were concatenated and extracted. Re-run the commands in section 3.
- **Memory usage**: The reconstruction script processes ~3.2M events. Run it on a machine with at least 16 GB RAM for comfortable headroom.
- **Performance**: Use `pypy3` or enable Python's `-O` flag if you need faster execution. Parallelization is possible but not yet implemented.

## 10. Contribution Ideas

- Automate S3 download + splitting pipeline for arbitrary dates.
- Add a liquidation extractor script mirroring the ADL extractor.
- Publish notebooks/visualizations that consume the canonical CSVs.
- Integrate regression tests ensuring outputs remain stable when scripts evolve.

Happy replaying!
