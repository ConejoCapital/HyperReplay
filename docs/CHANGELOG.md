# Changelog

## 2025-01-XX - Position Tracking Improvements

### Fixed
- **Position size tracking**: Enhanced position update logic with fallback handling for cases where `side` field may be missing. The script now:
  - Uses `side` field ('B' for buy, 'A' for sell) as primary method
  - Falls back to `direction` field parsing if `side` is unavailable
  - Ensures correct calculation: `new_size = startPosition + size` (buy) or `new_size = startPosition - size` (sell)
  
### Technical Details
- `startPosition` represents the position size **before** the fill
- `size` is the fill amount
- Position size after fill is correctly calculated based on side/direction
- This fix ensures accurate position tracking throughout the replay, especially important for ADL event analysis

### Impact
- More robust handling of edge cases in fill data
- Improved accuracy of position reconstruction
- Better compatibility with different data formats

