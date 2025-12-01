# NYC Rain Crash Risk Dashboard 🌧️🚗

An interactive Streamlit dashboard visualizing heterogeneous treatment effects of rain on NYC crash risk using H3 spatial indexing and causal inference.

![Status](https://img.shields.io/badge/status-ready-brightgreen)
![Python](https://img.shields.io/badge/python-3.12-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## 🎯 Overview

This project analyzes how rain affects crash probability across different locations in NYC using:
- **Geospatial Analysis**: H3 hexagonal indexing (resolution 8, ~600m cells)
- **Causal Inference**: T-Learner with Gradient Boosting to estimate Conditional Average Treatment Effects (CATE)
- **Interactive Visualization**: Flat Mercator map showing "kill zones" over NYC streets

### Key Findings
- Rain increases crash probability by **0.1pp on average**
- Effect varies **11x across locations** (max 1.1pp in most vulnerable zones)
- High-traffic zones show **3x stronger rain sensitivity**
- Top vulnerable cell: `882a100d69fffff` (**885 Lexington Avenue, Upper East Side**)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.12+
- Virtual environment with dependencies installed (see `requirements.txt`)

### Running the App

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the app (if you already have the data/ folder)
streamlit run src/app.py
```

The app will open at `http://localhost:8501`

---

## 📊 Features

The dashboard has **two main views** accessible via sidebar:

### 🗺️ **Map View** (Default)
**Interactive NYC map with all 1,135 H3 hexagons**

- **Clean Visualization**: All hexagons display with black borders over a street map
- **Selective Highlighting**: Top N highest-risk zones (adjustable 10-200) filled with translucent gray
- **Google Maps-like Controls**: Flat Mercator projection, scroll to zoom, drag to pan
- **Hover Tooltips**: See CATE, traffic, baseline risk, and crash count for any cell
- **Top 5 Quick Reference**: Geocoded addresses for the 5 most vulnerable zones
  - Example: #1 - 885 Lexington Ave (CATE: 1.104%)

**Screenshot Placeholder:** *[ADD SCREENSHOT HERE: Map view showing NYC with black hexagon borders and gray-filled top zones]*

---

### 📈 **Analysis & Charts View**
**Comprehensive visual analytics with 4 key charts**

#### 1. **Risk Distribution Histogram**
- Shows how CATE is distributed across all 1,135 cells
- Red dashed line marks Top N cutoff
- Reveals highly-skewed distribution (justifies targeted interventions)

#### 2. **Traffic vs. CATE Scatter Plot**
- Validates 3x traffic amplification effect
- Top 10 zones highlighted as red stars
- Color-coded by risk rank

#### 3. **Top 20 Kill Zones Table**
- Detailed breakdown with geocoded addresses
- Ranks, CATE values, traffic, baseline risk
- Shows multiplier vs. average (e.g., 11.1x)

#### 4. **Summary Statistics Dashboard**
- Three-panel overview: Targeting, Geography, Impact
- Key metrics and percentiles
- Methodology notes

**Screenshot Placeholder:** *[ADD SCREENSHOT HERE: Analysis view showing the 4 charts side-by-side]*

---

### ✅ **Completed Enhancements**
- ✅ Geocoded top 20 H3 cells to street addresses
- ✅ Flat Mercator projection (no 3D rotation)
- ✅ Black border visualization for clean, professional look
- ✅ Comprehensive analysis charts with explanations

---

## 📁 Project Structure

```
CausalAccidents/
├── data/
│   ├── cate_by_h3_cells.csv            # Main data (1,135 H3 cells)
│   ├── top_20_geocoded.csv             # Top 20 cells with street addresses
│   ├── nyc_crash_data.csv              # Raw crash data
│   ├── nyc_weather_hourly.csv          # Weather data
│   └── ...                             # Other pipeline outputs
│
├── documents/
│   ├── HETEROGENEITY_RESULTS.md        # Analysis results summary
│   └── PIPELINE_SUMMARY.md             # Full pipeline documentation
│
├── notebooks/
│   ├── 01_data_cleaning.ipynb          # Data cleaning and Feature Engineering (Collisions Data)
│   ├── 02_a_h3_construction.ipynb      # H3 initial construction
│   ├── 02_b_h3_full_construction.ipynb # H3 full panel construction (h3_cell, date, hour)
│   ├── 03_weather.ipynb                # Weather integration
│   ├── 04_causal.ipynb                 # Initial causal analysis
│   ├── 04.5_TLC_data_cleaning.ipynb    # Data cleaning and Feature Engineering (TLC Data)
│   ├── 05_causal_validation.ipynb      # Traffic-adjusted analysis
│   └── 06_CATE.ipynb                   # T-Learner CATE estimation
│
├── src/
│   ├── app.py                          # Main Streamlit dashboard (Map + Analysis views)
│   ├── geocode_top_20.py               # Geocoding script for top 20 H3 cells
│   └── test_map_visual.py              # Test map visualization
│  
├── requirements.txt                    # Python dependencies
└── README.md                           # Project documentation
```

---

## 🔧 Technical Details

### Data Pipeline
1. **Data Cleaning** (`01_data_cleaning.ipynb`)
   - NYPD Motor Vehicle Collisions (2022-2025)
   - Filter to valid lat/lon, derive time features

2. **H3 Indexing** (`02_h3_panel_construction.ipynb`)
   - Aggregate crashes to H3 resolution 8 (~600m hexagons)
   - Create panel dataset: (h3_cell, date, hour)

3. **Weather Integration** (`03_weather.ipynb`)
   - Hourly precipitation data from Open-Meteo
   - Binary rain flag (precip > threshold)

4. **Causal Analysis** (`04-05_causal_*.ipynb`)
   - DoWhy framework for causal inference
   - Propensity score matching
   - Traffic volume controls

5. **Heterogeneous Effects** (`06_heterogeneous_effects.ipynb`)
   - T-Learner with GradientBoostingRegressor
   - Stratified sampling (1M observations, 50% rain/no rain)
   - Output: `data/cate_by_h3_cells.csv`

### Model Details
- **Algorithm**: T-Learner (two separate models for treatment/control)
- **Base Learner**: GradientBoostingRegressor (100 estimators, max_depth=5)
- **Features**: log_traffic, baseline_risk, day_of_week, is_weekend, month, is_rush_hour
- **Training Time**: ~56 seconds total
- **Sample Size**: 1M stratified sample

---

## 📈 Results Summary

From `HETEROGENEITY_RESULTS.md`:

| Metric | Value |
|--------|-------|
| **Mean CATE** | 0.000990 (0.099pp) |
| **Std CATE** | 0.000739 |
| **Max CATE** | 0.011039 (1.1pp) |
| **Total H3 Cells** | 1,135 |
| **High-traffic effect** | 0.21pp (3x average) |
| **Low-traffic effect** | 0.07pp |

### Recommendations
1. **Target high-CATE zones** (top 10%) with 2x surge pricing + safety alerts
2. **Sunday rain events**: Pre-position drivers, proactive warnings (2.4x higher risk)
3. **Low-CATE zones**: Standard operations (maintain competitiveness)

---

## 🔬 Testing

Run the test suite:
```bash
python test_app.py
```

Tests verify:
- ✓ Data file exists and loads correctly
- ✓ Column names match expected schema
- ✓ H3 to lat/lng conversion works
- ✓ CATE statistics are reasonable
- ✓ All dependencies are installed

---

## 🚧 Future Enhancements

- [x] ~~Geocoding integration (H3 → street addresses)~~ **DONE**
- [ ] Real-time CATE scoring API
- [ ] Historical back-testing dashboard  
- [ ] Multi-city support (Chicago, LA, SF)
- [ ] Driver positioning optimization algorithm
- [ ] Live weather forecast integration
- [ ] A/B test deployment framework

---

## 📚 References

- **H3 Spatial Indexing**: [Uber H3](https://h3geo.org/)
- **Causal Inference**: [DoWhy](https://www.pywhy.org/dowhy/v0.14/)
- **Data Sources**:
  - [NYPD Motor Vehicle Collisions](https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95)
  - [NYC TLC Trip Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
  - [Open-Meteo Weather API](https://open-meteo.com/)

---
