# %% [markdown]
# # Validation test for the map visualization. 

# %%
import pandas as pd
import sys

# %%
def get_stroke_color(row):
    """Border color - prominent and opaque"""
    if row["rank_cate"] <= 50:  # TOP_N
        # Bright red borders for top kill zones
        return [220, 20, 20, 255]
    else:
        # Gradient from orange (high) to blue (low) for others
        norm = row["cate_norm"]
        if norm > 0.5:
            # Orange to yellow for higher risk
            r = 255
            g = int(100 + 155 * (1 - norm))
            b = 0
        else:
            # Yellow to blue for lower risk
            r = int(255 * (norm * 2))
            g = int(200 * (norm * 2))
            b = int(100 + 155 * (1 - norm * 2))
        return [r, g, b, 200]

def get_fill_color(row):
    """Fill color - very translucent to show map underneath"""
    if row["rank_cate"] <= 50:  # TOP_N
        # Light red fill for kill zones
        return [255, 80, 80, 50]  # Very transparent
    else:
        # Subtle gradient fill
        norm = row["cate_norm"]
        r = int(150 + 100 * norm)
        g = int(150 + 50 * (1 - norm))
        b = int(200 - 100 * norm)
        return [r, g, b, 35]  # Very transparent to show map


# %%
# Mock data for testing
test_data = pd.DataFrame({
    'h3_index': ['test1', 'test2', 'test3', 'test4'],
    'cate_mean': [0.011, 0.005, 0.002, 0.0001],
    'rank_cate': [1, 25, 500, 1000],
    'cate_norm': [1.0, 0.5, 0.2, 0.0]
})

print("=" * 70)
print("Map Visualization Validation Test")
print("=" * 70)
print()

all_tests_passed = True

# Test 1: Top-ranked cell (rank 1) should have red border
print("Test 1: Top-ranked cell (rank 1)")
row1 = test_data.iloc[0]
stroke1 = get_stroke_color(row1)
fill1 = get_fill_color(row1)
print(f"  Stroke color: {stroke1}")
print(f"  Fill color: {fill1}")
if stroke1 == [220, 20, 20, 255] and fill1 == [255, 80, 80, 50]:
    print("  ✅ PASS - Red border with translucent red fill")
else:
    print("  ❌ FAIL - Expected red colors")
    all_tests_passed = False
print()

# Test 2: Mid-ranked cell (rank 25) should have red border (still in top 50)
print("Test 2: Mid-ranked kill zone (rank 25)")
row2 = test_data.iloc[1]
stroke2 = get_stroke_color(row2)
fill2 = get_fill_color(row2)
print(f"  Stroke color: {stroke2}")
print(f"  Fill color: {fill2}")
if stroke2 == [220, 20, 20, 255] and fill2 == [255, 80, 80, 50]:
    print("  ✅ PASS - Red border (in top 50)")
else:
    print("  ❌ FAIL - Expected red colors")
    all_tests_passed = False
print()

# Test 3: Lower-ranked cell (rank 500) should have gradient colors
print("Test 3: Lower-ranked cell (rank 500, norm=0.2)")
row3 = test_data.iloc[2]
stroke3 = get_stroke_color(row3)
fill3 = get_fill_color(row3)
print(f"  Stroke color: {stroke3}")
print(f"  Fill color: {fill3}")
# Should NOT be red (rank > 50)
if stroke3 != [220, 20, 20, 255] and fill3 != [255, 80, 80, 50]:
    print("  ✅ PASS - Non-red gradient colors")
else:
    print("  ❌ FAIL - Should not be red")
    all_tests_passed = False
print()

# Test 4: Check opacity values
print("Test 4: Opacity values")
print(f"  Top cell fill opacity: {fill1[3]} (should be ~50 for translucency)")
print(f"  Top cell stroke opacity: {stroke1[3]} (should be 255 for visibility)")
print(f"  Other cell fill opacity: {fill3[3]} (should be ~35 for translucency)")
print(f"  Other cell stroke opacity: {stroke3[3]} (should be 200 for visibility)")
if fill1[3] <= 60 and stroke1[3] >= 200 and fill3[3] <= 60 and stroke3[3] >= 180:
    print("  ✅ PASS - Correct opacity ranges")
else:
    print("  ❌ FAIL - Opacity values out of range")
    all_tests_passed = False
print()

print("=" * 70)
if all_tests_passed:
    print("✅ ALL TESTS PASSED - Visualization should work correctly!")
    print()
    print("Expected behavior:")
    print("  • Top 50 cells: RED borders with light red fill")
    print("  • Other cells: Gradient borders (orange→yellow→blue) with subtle fill")
    print("  • All fills are translucent (opacity 35-50) to show map underneath")
    print("  • All borders are opaque (opacity 200-255) to be clearly visible")
else:
    print("❌ SOME TESTS FAILED - Check color functions!")
    sys.exit(1)
print("=" * 70)
