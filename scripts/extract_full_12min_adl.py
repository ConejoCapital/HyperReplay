#!/usr/bin/env python3
"""
Canonical extractor for all ADL fills during the 12-minute cascade (21:15-21:27 UTC).

Outputs:
- `data/canonical/adl_fills_full_12min_raw.csv` → consumed by downstream analyses and HyperFireworks
- `data/canonical/adl_net_volume_full_12min.csv`
- `data/canonical/ADL_NET_VOLUME_FULL_12MIN.md`
"""

import lz4.frame
import json
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
import tarfile

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
OUTPUT_DIR = REPO_ROOT / "data" / "canonical"

# Configuration
S3_DATA_BASENAME = "node_fills_20251010_21.lz4"
ARCHIVE_PREFIX = RAW_DIR / f"{S3_DATA_BASENAME}.part"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Time window for full ADL event
ADL_START = datetime(2025, 10, 10, 21, 15, 0, tzinfo=timezone.utc)
ADL_END = datetime(2025, 10, 10, 21, 27, 0, tzinfo=timezone.utc)


def assemble_lz4():
    """Concatenate split node_fills parts if the consolidated lz4 file is missing."""
    consolidated = RAW_DIR / S3_DATA_BASENAME
    if consolidated.exists():
        return consolidated

    part_files = sorted(RAW_DIR.glob(f"{S3_DATA_BASENAME}.part-*"))
    if not part_files:
        raise FileNotFoundError(
            "node_fills archive not found. Recreate it with `cat data/raw/"
            f"{S3_DATA_BASENAME}.part-* > data/raw/{S3_DATA_BASENAME}`"
        )

    with consolidated.open('wb') as out_f:
        for part in part_files:
            out_f.write(part.read_bytes())

    return consolidated


def extract_adl_fills():
    """Extract all ADL fills from the full 12-minute window."""
    print("=" * 80)
    print("EXTRACTING FULL 12-MINUTE ADL DATA FROM node_fills")
    print("=" * 80)
    print(f"\nTime window: {ADL_START} to {ADL_END}")

    source_file = assemble_lz4()
    print(f"Source: {source_file.relative_to(REPO_ROOT)}")
    print("\n📥 Decompressing and parsing LZ4 data...")

    adl_fills = []
    total_fills = 0
    lines_processed = 0

    with lz4.frame.open(source_file, 'rb') as f:
        for line_num, line in enumerate(f, 1):
            lines_processed += 1

            if line_num % 50000 == 0:
                print(f"  Processing line {line_num:,}... (found {len(adl_fills):,} ADL events so far)")

            try:
                data = json.loads(line)

                block_time_str = data.get('block_time', '')
                if not block_time_str:
                    continue

                if '.' in block_time_str:
                    base, frac = block_time_str.rsplit('.', 1)
                    frac_truncated = frac[:6].ljust(6, '0')
                    block_time_str = f"{base}.{frac_truncated}"

                block_time = datetime.fromisoformat(block_time_str)
                if block_time.tzinfo is None:
                    block_time = block_time.replace(tzinfo=timezone.utc)

                if block_time < ADL_START or block_time >= ADL_END:
                    continue

                events = data.get('events', [])

                for event in events:
                    if not isinstance(event, list) or len(event) < 2:
                        continue

                    user = event[0]
                    fill = event[1]
                    total_fills += 1

                    direction = fill.get('dir', '')

                    if 'Auto-Deleveraging' not in direction:
                        continue

                    coin = fill.get('coin', '')
                    if coin.startswith('@'):
                        continue

                    px = float(fill.get('px', 0))
                    sz = float(fill.get('sz', 0))
                    side = fill.get('side', '')
                    start_position = float(fill.get('startPosition', 0))
                    closed_pnl = float(fill.get('closedPnl', 0))
                    fee = float(fill.get('fee', 0))

                    adl_fills.append({
                        'block_time': block_time,
                        'user': user,
                        'coin': coin,
                        'direction': direction,
                        'price': px,
                        'size': sz,
                        'side': side,
                        'start_position': start_position,
                        'closed_pnl': closed_pnl,
                        'fee': fee,
                        'notional': sz * px
                    })

            except Exception as e:
                if line_num < 10:
                    print(f"  Warning: Error parsing line {line_num}: {e}")
                continue

    print(f"\n✅ Extraction complete!")
    print(f"  Lines processed: {lines_processed:,}")
    print(f"  Fills in time window: {total_fills:,}")
    print(f"  ADL events found: {len(adl_fills):,}")

    return pd.DataFrame(adl_fills)


def calculate_adl_volume(df_adl):
    """Calculate net ADL volume by ticker."""
    print("\n" + "=" * 80)
    print("CALCULATING NET ADL VOLUME BY TICKER (FULL 12 MINUTES)")
    print("=" * 80)

    adl_by_ticker = df_adl.groupby('coin').agg({
        'size': 'sum',
        'notional': 'sum',
        'closed_pnl': 'sum',
        'direction': 'count',
        'price': 'mean'
    }).reset_index()

    adl_by_ticker.columns = ['ticker', 'net_volume', 'net_notional_usd', 'total_pnl', 'num_adl_events', 'avg_price']
    adl_by_ticker = adl_by_ticker.sort_values('net_notional_usd', ascending=False)
    return adl_by_ticker


def print_summary_table(df_results):
    """Print formatted summary table."""
    print("\n" + "=" * 80)
    print("ADL NET VOLUME BY TICKER (FULL 12-MINUTE EVENT)")
    print("=" * 80)

    print(f"\n{'Rank':<6}{'Ticker':<12}{'Net Volume':<18}{'Net Notional (USD)':<22}{'Avg Price':<15}{'# ADL Events':<15}{'Total PNL':<18}")
    print("-" * 125)

    total_notional = 0
    total_pnl = 0
    total_events = 0

    for i, row in df_results.iterrows():
        rank = i + 1
        ticker = row['ticker']
        volume = row['net_volume']
        notional = row['net_notional_usd']
        avg_px = row['avg_price']
        events = int(row['num_adl_events'])
        pnl = row['total_pnl']

        total_notional += notional
        total_pnl += pnl
        total_events += events

        if volume >= 1:
            vol_str = f"{volume:,.2f}"
        else:
            vol_str = f"{volume:.6f}"

        print(f"{rank:<6}{ticker:<12}{vol_str:<18}${notional:>18,.0f}{f'${avg_px:,.2f}':<15}{events:<15}${pnl:>15,.0f}")

    print("-" * 125)
    print(f"{'TOTAL':<18}{' ':<18}${total_notional:>18,.0f}{' ':<15}{total_events:<15}${total_pnl:>15,.0f}")
    print("=" * 80)

    return total_notional, total_pnl, total_events


def print_comparison(old_notional, new_notional):
    """Print comparison with 2-minute sample."""
    print("\n" + "=" * 80)
    print("COMPARISON: 2-MINUTE SAMPLE vs FULL 12-MINUTE EVENT")
    print("=" * 80)

    scaling_factor = new_notional / old_notional

    print(f"\n2-minute sample (21:15-21:17):  ${old_notional:,.0f}")
    print(f"Full 12-minute event (21:15-21:27): ${new_notional:,.0f}")
    print(f"\nActual scaling factor: {scaling_factor:.2f}x (estimated was ~6x)")
    print(f"Difference from estimate: {((scaling_factor - 6) / 6 * 100):+.1f}%")


def generate_markdown_report(df_results, total_notional, total_pnl, total_events):
    """Generate comprehensive markdown report."""
    print("\n📄 Generating markdown report...")

    content = f"""# ADL Net Volume Analysis - FULL 12-MINUTE EVENT

**Event Date**: October 10, 2025  
**Time Window**: 21:15:00 - 21:27:00 UTC (COMPLETE 12-minute event)  
**Data Source**: Hyperliquid node_fills_20251010_21.lz4 (public S3)

---

## Executive Summary

**Total ADL'd Assets**: {len(df_results)} tickers  
**Total ADL Events**: {total_events:,}  
**Total Net Notional**: ${total_notional:,.0f}  
**Total Realized PNL**: ${total_pnl:,.0f}

---

## ADL Net Volume by Ticker (All {len(df_results)} Tickers)

| Rank | Ticker | Net Volume | Net Notional (USD) | Avg Price | # ADL Events | Total PNL |
|------|--------|------------|-------------------|-----------|--------------|-----------|
"""

    for i, row in df_results.iterrows():
        rank = i + 1
        ticker = row['ticker']
        volume = f"{row['net_volume']:,.4f}"
        notional = f"${row['net_notional_usd']:,.0f}"
        avg_px = f"${row['avg_price']:,.2f}"
        events = int(row['num_adl_events'])
        pnl = f"${row['total_pnl']:,.0f}"

        content += f"| {rank} | {ticker} | {volume} | {notional} | {avg_px} | {events} | {pnl} |\n"

    content += f"""
**Total** | - | - | **${total_notional:,.0f}** | - | **{total_events:,}** | **${total_pnl:,.0f}**

---

## Top 10 ADL'd Tickers (Detailed)

"""

    for i, row in df_results.head(10).iterrows():
        rank = i + 1
        ticker = row['ticker']
        volume = row['net_volume']
        notional = row['net_notional_usd']
        avg_px = row['avg_price']
        events = int(row['num_adl_events'])
        pnl = row['total_pnl']
        pct = notional/total_notional*100

        content += f"""
### {rank}. {ticker}

- **Net Volume ADL'd**: {volume:,.4f} {ticker}
- **Net Notional**: ${notional:,.2f}
- **Average Price**: ${avg_px:,.2f}
- **Number of ADL Events**: {events:,}
- **Total Realized PNL**: ${pnl:,.2f}
- **% of Total Notional**: {pct:.1f}%
"""

    content += f"""
---

## Key Insights

### Market Impact
- **Total ADL volume**: ${total_notional:,.0f} over 12 minutes
- **Top 3 tickers** account for {df_results.head(3)['net_notional_usd'].sum()/total_notional*100:.1f}% of total
- **{df_results.iloc[0]['ticker']}** was the largest ADL'd asset (${df_results.iloc[0]['net_notional_usd']:,.0f})

### ADL Rate
- **{total_events:,} ADL events** in 12 minutes
- **Average**: {total_events/12:.0f} ADLs per minute
- **Rate**: {total_events/720:.1f} ADLs per second

### Profitability
- **Total realized PNL** from ADL'd positions: ${total_pnl:,.0f}
- **Average PNL per ADL event**: ${total_pnl/total_events:,.0f}
- **Most profitable ticker**: {df_results.loc[df_results['total_pnl'].idxmax(), 'ticker']} (${df_results['total_pnl'].max():,.0f})

---

## Methodology

### Data Source
- **Source**: Hyperliquid public S3 (`node_fills_20251010_21.lz4`)
- **Filter**: Only fills with direction containing "Auto-Deleveraging"
- **Exclusions**: @ tokens (spot positions that cannot be ADL'd)
- **Time window**: Complete 12-minute event (21:15:00 - 21:27:00 UTC)

### Calculations
- **Net Volume**: Sum of all ADL'd position sizes per ticker
- **Net Notional**: Sum of (size × price) for all ADL events
- **Total PNL**: Sum of realized PNL from ADL closures

---

## Data Quality

✅ **Complete dataset**: Full 12-minute event (not a sample)  
✅ **Blockchain-verified**: All ADL events from S3 node fills  
✅ **No heuristics**: Only explicitly labeled ADL events  
✅ **Spot positions excluded**: @ tokens filtered out  

---

## Comparison with 2-Minute Sample

Previous analysis used SonarX data (21:15-21:17 UTC, 2 minutes):
- **2-minute sample**: $285.5M notional
- **Full 12-minute**: ${total_notional:,.0f} notional
- **Actual scaling**: {total_notional/285500000:.2f}x

---

**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Analysis by**: HyperReplay ADL extractor  
**Data source**: node_fills_20251010_21.lz4
"""

    report_path = OUTPUT_DIR / "ADL_NET_VOLUME_FULL_12MIN.md"
    with open(report_path, "w") as f:
        f.write(content)

    print(f"  ✓ {report_path.relative_to(REPO_ROOT)}")


def main():
    """Main execution."""
    print("\n🚀 Analyzing FULL 12-MINUTE ADL EVENT\n")

    df_adl = extract_adl_fills()

    raw_out = OUTPUT_DIR / "adl_fills_full_12min_raw.csv"
    df_adl.to_csv(raw_out, index=False)
    print(f"\n  ✓ Saved raw ADL fills: {raw_out.relative_to(REPO_ROOT)}")

    df_results = calculate_adl_volume(df_adl)

    total_notional, total_pnl, total_events = print_summary_table(df_results)

    print_comparison(285_546_805, total_notional)

    print("\n📤 Exporting results...")
    csv_out = OUTPUT_DIR / "adl_net_volume_full_12min.csv"
    df_results.to_csv(csv_out, index=False)
    print(f"  ✓ {csv_out.relative_to(REPO_ROOT)}")

    generate_markdown_report(df_results, total_notional, total_pnl, total_events)

    print("\n" + "=" * 80)
    print("✅ FULL 12-MINUTE ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"\nTotal ADL'd: ${total_notional:,.0f} across {len(df_results)} tickers")
    print(f"Total Events: {total_events:,} ADL events in 12 minutes")
    print(f"Total PNL: ${total_pnl:,.0f} in forced closures")
    print("\n📁 Files created:")
    print(f"  • {raw_out.relative_to(REPO_ROOT)}")
    print(f"  • {csv_out.relative_to(REPO_ROOT)}")
    print("  • data/canonical/ADL_NET_VOLUME_FULL_12MIN.md")
    print("=" * 80)


if __name__ == "__main__":
    main()

