# Position Size Calculation Bug Fix - Comparison Report

**Date**: December 2025  
**Issue**: Position size was incorrectly set to `startPosition` (before fill) instead of calculating new size after fill  
**Fix**: Now correctly calculates `new_size = startPosition + fill_size` (buy) or `startPosition - fill_size` (sell)  
**Additional Fix**: Use `startPosition` from ADL event for ADL moment analysis (not position size after ADL)

---

## Key Metrics Comparison

| Metric | OLD (Buggy) | NEW (Fixed) | Difference | % Change |
|--------|-------------|-------------|------------|----------|
| **Median Leverage** | 0.18x | 0.20x | +0.02x | +10.4% |
| **Average Leverage** | 3,321.71x | 2,005.58x | -1,316.13x | -39.6% |
| **95th Percentile Leverage** | 4.23x | 5.10x | +0.88x | +20.8% |
| **99th Percentile Leverage** | 74.18x | 122.69x | +48.51x | +65.4% |
| **Profitable Positions %** | 94.5% | 99.4% | +4.9% | +5.2% |
| **Average PNL %** | 80.58% | 85.93% | +5.35% | +6.6% |
| **Median PNL %** | 50.09% | 52.25% | +2.17% | +4.3% |
| **Negative Equity Count** | 1,147 | 302 | -845 | -73.7% |
| **Total Negative Equity** | -$109,288,587 | -$23,191,104 | +$86,097,483 | +78.8% |

---

## Analysis

### ✅ Metrics That Are Very Close

1. **Median Leverage**: 0.18x → 0.20x (+10.4%)
   - Very close, indicating the fix didn't dramatically change the core leverage distribution
   - The median is robust to outliers

2. **Profitable Positions %**: 94.5% → 99.4% (+4.9%)
   - Both datasets show ADL targets profitable positions
   - New data shows even stronger profit targeting

3. **Average/Median PNL %**: Very close (within 7%)
   - Confirms the profit-based prioritization finding
   - New data shows slightly higher profitability

### ⚠️ Metrics With Significant Differences

1. **Negative Equity**: 1,147 → 302 accounts (-73.7%)
   - **This is the most significant change**
   - Old data: -$109.3M total negative equity
   - New data: -$23.2M total negative equity
   - **The new calculation is more accurate** because it uses correct position sizes for total equity calculation

2. **Average Leverage**: 3,321.71x → 2,005.58x (-39.6%)
   - Still high due to outliers (accounts with near-zero account values)
   - Median leverage (0.20x) is the more representative metric
   - The reduction in average is due to more accurate position size tracking

3. **99th Percentile Leverage**: 74.18x → 122.69x (+65.4%)
   - Some extreme outliers in the new data
   - These are likely accounts with very small account values but large positions
   - The median (0.20x) remains stable

---

## What Was Fixed

### Bug 1: Position Size Update During Replay
**Before (Buggy)**:
```python
new_size = event['startPosition']  # Wrong - this is position BEFORE fill
working_states[user]['positions'][coin]['size'] = new_size
```

**After (Fixed)**:
```python
start_position = event['startPosition']
fill_size = event['size']
if event['side'] == 'B':  # Buy
    new_size = start_position + fill_size
else:  # Sell
    new_size = start_position - fill_size
working_states[user]['positions'][coin]['size'] = new_size
```

### Bug 2: Position Size at ADL Moment
**Before (Buggy)**:
```python
position = account_state['positions'][coin]
position_size = position['size']  # Wrong - this is position AFTER ADL (close to 0)
```

**After (Fixed)**:
```python
position_size_at_adl = adl['startPosition']  # Correct - position BEFORE ADL
# Use this for leverage, PNL, and notional calculations
```

---

## Impact on Research Findings

### Findings That Remain Valid

1. ✅ **ADL targets profitable positions**: 99.4% profitable (was 94.5%)
2. ✅ **Low median leverage**: 0.20x (was 0.18x) - still very low
3. ✅ **Profit-based prioritization**: Average PNL 85.93% (was 80.58%)

### Findings That Changed

1. ⚠️ **Insurance fund impact**: -$23.2M (was -$109.3M)
   - **The new value is more accurate** because it uses correct position sizes
   - Negative equity detection depends on accurate total equity calculation
   - Total equity = account_value + unrealized_PNL (all positions)
   - With correct position sizes, unrealized PNL is more accurate

2. ⚠️ **Negative equity account count**: 302 (was 1,147)
   - **The new value is more accurate** for the same reason
   - Many accounts that appeared underwater were actually not, due to incorrect position size tracking

---

## Conclusion

The fix corrects a critical bug in position size tracking that affected:
- Leverage calculations
- Unrealized PNL calculations
- Total equity calculations
- Negative equity detection

**The new canonical data is more accurate** and should be used for all future research. The key findings (profit-based ADL prioritization, low median leverage) remain valid, but the insurance fund impact is significantly lower than previously reported.

---

**Files Updated**:
- `adl_detailed_analysis_REALTIME.csv` - Regenerated with fixed position size calculation
- `adl_by_user_REALTIME.csv` - Regenerated
- `adl_by_coin_REALTIME.csv` - Regenerated
- `realtime_analysis_summary.json` - Updated with new metrics

**Scripts Fixed**:
- `HyperReplay/scripts/replay_real_time_accounts.py`
- `ADL Clearinghouse Data/full_analysis_realtime.py`

