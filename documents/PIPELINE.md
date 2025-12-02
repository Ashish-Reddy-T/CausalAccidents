# Pipeline Documentation

**NYC Rain Crash Risk: Complete Data Pipeline**  
From Raw Data to Heterogeneous Treatment Effects

---

## Executive Summary

This pipeline estimates the causal effect of rain on motor vehicle crash risk across NYC neighborhoods using:
- **Spatial Framework**: H3 hexagonal indexing (resolution 8, ~600m cells)
- **Causal Method**: DoWhy framework with propensity score weighting
- **Heterogeneity Analysis**: T-Learner with Gradient Boosting to estimate location-specific treatment effects

**Key Result**: Rain increases crash probability by **0.10 percentage points on average**, with effects varying **13.6x across locations** (max 1.38pp in highest-risk zones).

---

## Pipeline Overview

```
Raw Data Sources
    ├─> [1] Crash Data   (NYPD)
    ├─> [2] Weather Data (Open-Meteo)
    └─> [3] Traffic Data (TLC Taxi)
         │
         ▼
Data Cleaning & Feature Engineering
    ├─> 01_data_cleaning.ipynb       (Crashes)
    ├─> 04.5_TLC_data_cleaning.ipynb (Traffic)
    └─> 03_weather.ipynb             (Weather)
         │
         ▼
Spatial Aggregation (H3 Hexagons)
    ├─> 02_a_h3_construction.ipynb      (Initial panel)
    └─> 02_b_h3_full_construction.ipynb (Full panel with zeros)
         │
         ▼
Causal Inference (Average Treatment Effect)
    ├─> 04_causal.ipynb              (DoWhy ATE estimation)
    └─> 05_causal_validation.ipynb   (Traffic-adjusted validation)
         │
         ▼
Heterogeneous Effects (Conditional ATE)
    └─> 06_CATE.ipynb                (T-Learner by location/context)
         │
         ▼
Outputs
    ├─> cate_by_h3_cells.csv         (Spatial risk map)
    ├─> app.py                       (Interactive visualization)
    └─> HETEROGENEITY_RESULTS.md     (Business insights)
```

---

## Stage 1: Data Collection & Cleaning

### 1.1 Crash Data (`01_data_cleaning.ipynb`)

**Source**: [NYC Open Data - Motor Vehicle Collisions](https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95)

**Time Period**: 2022-01-01 to 2025-10-31 (46 months)

**Cleaning Steps**:
1. **Parse timestamps**: Combine `crash_date` + `crash_time` → `crash_datetime`
2. **Filter missing data**: Drop rows with NULL `lat`/`lon`/`datetime`
3. **Geographic outliers**: Remove crashes outside NYC bounding box
   - Latitude: 40.477° to 40.917° N
   - Longitude: -74.259° to -73.700° W
4. **Temporal outliers**: Remove dates outside 2022-2025 range
5. **Feature extraction**:
   - `day_of_week` (0=Monday, 6=Sunday)
   - `is_weekend` (Sat/Sun)
   - `month` (1-12)
   - `is_rush_hour` (7-9am, 4-7pm on weekdays)

**Output**: `crashes_cleaned.csv` (~340k valid crashes)

**Data Quality**:
- Retention rate: **92.24%** of raw records
- Missing lat/lon: **7.76%**
- Geographic outliers: **1.31%**
- Temporal outliers: **0%**

---

### 1.2 Weather Data (`03_weather.ipynb`)

**Source**: [Open-Meteo Historical Weather API](https://open-meteo.com/)

**Variables**:
- `precipitation` (mm/hour)
- `visibility` (meters)

**Treatment Definition**:
```python
rain_flag = (precipitation > 0.1)  # Binary treatment
```

**Threshold Rationale**: 0.1mm = light rain (enough to wet roads, affect visibility)

**Output**: `nyc_weather_hourly.csv`
- Hourly observations: **34248** hours
- Rain prevalence: **10.76%** of hours

---

### 1.3 Traffic Data (`04.5_TLC_data_cleaning.ipynb`)

**Source**: [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)

**Processing**:
1. **Zone-to-H3 mapping**: Polyfill TLC taxi zones with H3 cells
2. **Distributed allocation**: 
   ```python
   distribution_factor = 1 / n_hexes_per_zone
   traffic_count = SUM(pickups × distribution_factor)
   ```
3. **Hourly aggregation**: Group by (h3_index, hour_bin)

**DuckDB Optimization**: Direct parquet querying (50x faster than pandas)

**Output**: `traffic_h3_2022_2025_polyfill.parquet`
- Unique H3 cells with traffic: **1070**
- Avg pickups/hour (active cells): **3.27**

---

## Stage 2: Spatial Aggregation (H3 Panel)

### 2.1 Initial Panel (`02_a_h3_construction.ipynb`)

**H3 Resolution 8**: ~600m hexagons (neighborhood-scale)

**Steps**:
1. Apply H3 indexing to each crash:
   ```python
   df['h3'] = df.apply(lambda r: h3.latlng_to_cell(r['lat'], r['lon'], 8), axis=1)
   ```
2. Extract time features (hour, day_of_week, etc.)
3. Aggregate to `(h3_cell, date, hour)` level:
   - `accidents_count`: number of crashes in that cell-hour
   - `accident_indicator`: binary (≥1 crash)

**Output**: `h3_panel_res8.csv` (dense panel, ~XXXk observations)

**Statistics**:
- Unique H3 cells: **1135** (cells with ≥1 crash historically)
- Avg crashes per cell-hour: **0.008** (sparse)

---

### 2.2 Full Panel Construction (`02_b_h3_full_construction.ipynb`)

**Problem**: Dense panel only includes cells with crashes → **selection bias**

**Solution**: Create full Cartesian product
```
Full Panel = H3_cells × Dates × Hours
```

**Steps**:
1. Extract all unique H3 cells from dense panel
2. Create Cartesian product with all (date, hour) from weather data
3. Merge crash counts (fill missing with 0)
4. Compute `Baseline_Risk` per cell:
   ```python
   baseline_risk = crashes_last_30_hours / 30  # Rolling average
   ```

**Output**: `h3_full_panel_res8.csv` (~40M observations)

**Key Variables**:
- `h3_index`: H3 cell identifier
- `date`, `hour`: Temporal coordinates
- `accidents_count`: Crashes in this cell-hour (mostly 0)
- `accident_indicator`: Binary outcome
- `Baseline_Risk`: Historical crash rate (lag-adjusted)
- Time features: `day_of_week`, `is_weekend`, `month`, `is_rush_hour`

---

## Stage 3: Causal Inference (Average Treatment Effect)

### 3.1 Initial ATE Estimation (`04_causal.ipynb`)

**Framework**: DoWhy (Microsoft Research)

**Causal Graph (DAG)**:
```
Confounders → Rain → Accident
Confounders → Accident
```

**Confounders**:
- Temporal: `day_of_week`, `is_weekend`, `month`, `is_rush_hour`
- Spatial: `Baseline_Risk`
- Exposure: `Traffic_Proxy` (initial synthetic proxy)

**Method**: Propensity Score Weighting
```python
model = CausalModel(
    data=df_clean,
    treatment='rain_flag',
    outcome='accident_indicator',
    common_causes=[confounders]
)
estimate = model.estimate_effect(method="backdoor.propensity_score_weighting")
```

**Result**: ATE ≈ **0.000913** (0.091pp increase)

**Robustness Checks**:
- ✓ Random common cause: PASSED
- ✓ Placebo treatment: PASSED

---

### 3.2 Traffic-Adjusted Validation (`05_causal_validation.ipynb`)

**Improvement**: Replace `Traffic_Proxy` with real TLC `traffic_count`

**Merge Strategy**:
```python
df = panel.merge(
    traffic[['h3_index', 'match_hour', 'traffic_count']], 
    left_on=['h3_index', 'datetime'], 
    right_on=['h3_index', 'match_hour'],
    how='left'
)
df['traffic_count'].fillna(0)  # Zero for cells without taxi pickups
```

**Updated ATE**: ≈ 0.00095 (0.095pp increase)

**Comparison**:
- Proxy-based: **0.091pp**
- TLC-based: **0.095pp**
- Difference: **+4.4%** (consistent, minor refinement)

**Interpretation**: Real traffic data validates initial estimate. Effect is robust.

---

## Stage 4: Heterogeneous Treatment Effects (CATE)

### 4.1 T-Learner Setup (`06_CATE.ipynb`)

**Motivation**: Average effect masks spatial/contextual variation

**Method**: T-Learner (two separate models)
1. **Control model** (µ₀): Predict crash risk when `rain_flag = 0`
2. **Treatment model** (µ₁): Predict crash risk when `rain_flag = 1`
3. **CATE** = µ₁(X) - µ₀(X) for each observation

**Base Learner**: GradientBoostingRegressor
```python
GradientBoostingRegressor(
    n_estimators=100, 
    max_depth=5, 
    learning_rate=0.1,
    random_state=42
)
```

**Features (X)**:
- `log_traffic`: Log-transformed traffic count
- `Baseline_Risk`: Historical crash rate per cell
- `day_of_week`: Day of week (0-6)
- `is_weekend`: Weekend indicator
- `month`: Month (1-12)
- `is_rush_hour`: Rush hour indicator

---

### 4.2 Sampling Strategy

**Challenge**: 40M observations → memory constraints

**Solution**: Stratified sampling
```python
sample_size = 1,000,000  # 1M observations
df_sample = df.groupby('rain_flag').apply(
    lambda x: x.sample(n=sample_size // 2, random_state=42)
)
```

**Stratification**:
- 50% rain hours
- 50% no-rain hours
- Ensures balanced treatment/control groups

**Validation**:
- Rain balance: 50.0% / 50.0% ✓
- Accident rate: ~0.85% (matches population)

---

### 4.3 Model Training

**Step 1: Split by treatment**
```python
X_control = X[rain_flag == 0]
Y_control = Y[rain_flag == 0]
X_treated = X[rain_flag == 1]
Y_treated = Y[rain_flag == 1]
```

**Step 2: Fit separate models**
```python
model_control.fit(X_control, Y_control)  # ~500k samples
model_treated.fit(X_treated, Y_treated)  # ~500k samples
```

**Training Time**: ~56 seconds total (on M1/M2 Mac)

**Step 3: Predict CATE**
```python
mu_0 = model_control.predict(X)  # Predicted risk without rain
mu_1 = model_treated.predict(X)  # Predicted risk with rain
cate = mu_1 - mu_0               # Heterogeneous treatment effect
```

---

### 4.4 Spatial Aggregation

**Goal**: Get mean CATE per H3 cell (for mapping)

```python
cate_by_h3 = df_sample.groupby('h3_index').agg({
    'cate': ['mean', 'median', 'std'],
    'traffic_count': 'mean',
    'Baseline_Risk': 'mean',
    'accident_indicator': 'sum'  # Total crashes
})
```

**Output**: `cate_by_h3_cells.csv` (1,135 H3 cells)

**Columns**:
- `h3_index`: Cell identifier
- `cate_mean`: Average treatment effect in this cell
- `cate_median`: Median (robust to outliers)
- `cate_std`: Within-cell variation
- `avg_traffic`: Average taxi pickups/hour
- `avg_baseline_risk`: Historical crash rate
- `total_crashes`: Observed crashes in sample

---

## Stage 5: Outputs & Visualization

### 5.1 Spatial Risk Map (`cate_by_h3_cells.csv`)

**Top 5 High-Risk Zones**:
| Rank | H3 Cell | CATE (pp) | Location |
|------|---------|-----------|----------|
| 1 | 882a100d69fffff | 1.378 | 885 Lexington Ave (UES) |
| 2 | 882a1008d1fffff | 0.487 | E 115th St (Harlem) |
| 3 | 882a100d65fffff | 0.485 | W 52nd St (Midtown) |
| 4 | 882a100ab5fffff | 0.425 | W 142nd St (Hamilton Hts) |
| 5 | 882a1008d9fffff | 0.415 | E 125th St (Harlem) |

**Key Statistics**:
- Mean CATE: **0.1013%** (0.10pp)
- Std CATE: **0.0732%**
- Max CATE: **1.378%** (13.6x average)
- Min CATE: **-0.246%** (some cells safer in rain! Many possibilities on why.)

---

### 5.2 Interactive Dashboard (`src/app.py`)

**Technology**: Streamlit + PyDeck

**Features**:
1. **Map View**:
   - H3 hexagons with black borders (all cells visible)
   - Gray fill for top N high-risk zones (adjustable 10-200)
   - Hover tooltips with CATE, traffic, baseline risk
   - Geocoded addresses for top 5 zones

2. **Analysis View**:
   - CATE distribution histogram
   - Traffic vs CATE scatter plot
   - Top 20 zones table (with addresses)
   - Summary statistics dashboard

**Usage**:
```bash
streamlit run src/app.py
```

---

## Technical Notes

### Computational Efficiency

**Bottlenecks & Solutions**:
1. **Full panel creation**: ~40M rows
   - Solution: Chunked processing, efficient dtypes
2. **TLC data querying**: 46 months × 12 files
   - Solution: DuckDB (50x faster than pandas)
3. **T-Learner training**: 1M sample
   - Solution: Stratified sampling, gradient boosting (vs random forest)

**Memory Usage**:
- Full panel (in memory): ~3GB
- CATE sample: ~500MB
- Final aggregated data: <1MB

---

### Causal Assumptions

**Identifiability (Backdoor Criterion)**:
- Assumes: All confounders observed and controlled
- **Strong assumption**: No unobserved confounding
  - E.g., driver behavior changes during rain (not observed)
  - Road conditions, visibility vary within hourly data

**Conditional Ignorability**:
```
Y(1), Y(0) ⊥ T | X
```
Given confounders X, treatment assignment is "as-if-random"

**SUTVA (Stable Unit Treatment Value)**:
- No spillover between H3 cells (questionable for traffic)
- Treatment definition is stable (rain > 0.1mm)

**Limitations**:
1. **Exposure proxy**: TLC data only captures taxi pickups (not total traffic)
2. **Temporal resolution**: Hourly aggregation misses sub-hour dynamics
3. **Weather uniformity**: Single weather station for entire NYC

---

### Model Validation

**Cross-Validation** (not performed due to time constraints):
- Future: K-fold CV on spatial blocks to assess generalization

**Sensitivity Analysis**:
- Rain threshold: Tested 0.05mm, 0.1mm, 0.5mm (0.1mm optimal)
- H3 resolution: Res 7 (≈1.5km) too coarse, Res 9 (≈250m) sparse data

**External Validity**:
- Results specific to NYC (dense urban environment)
- Replication needed for other cities (Chicago, LA, SF)

---

## Data Dictionary

### Key Variables

| Variable | Type | Range | Description |
|----------|------|-------|-------------|
| `h3_index` | String | 15 chars | H3 cell ID (resolution 8) |
| `date` | Date | 2022-01-01 to 2025-10-31 | Calendar date |
| `hour` | Integer | 0-23 | Hour of day |
| `accident_indicator` | Binary | 0/1 | Any crash in this cell-hour |
| `accidents_count` | Integer | 0-10+ | Number of crashes |
| `rain_flag` | Binary | 0/1 | Rain > 0.1mm (treatment) |
| `precipitation` | Float | 0-50+ mm | Hourly precipitation |
| `traffic_count` | Float | 0-500+ | Taxi pickups (exposure) |
| `Baseline_Risk` | Float | 0-1 | Historical crash rate (30h rolling) |
| `day_of_week` | Integer | 0-6 | Day (0=Mon, 6=Sun) |
| `is_weekend` | Binary | 0/1 | Saturday or Sunday |
| `month` | Integer | 1-12 | Month of year |
| `is_rush_hour` | Binary | 0/1 | 7-9am or 4-7pm (weekdays) |
| `cate_mean` | Float | -0.0025 to 0.014 | Mean treatment effect in cell |

---

## Reproducibility

### Environment Setup

**Python Version**: 3.12+

**Key Dependencies**:
```
pandas==2.1+
numpy==1.24+
h3==4.0+
dowhy==0.11+
scikit-learn==1.3+
streamlit==1.28+
pydeck==0.8+
```

**Install**:
```bash
pip install -r requirements.txt
```

---

### Execution Order

**Full Pipeline** (start to finish):
```bash
# 1. Data cleaning
jupyter notebook notebooks/01_data_cleaning.ipynb
jupyter notebook notebooks/04.5_TLC_data_cleaning.ipynb
jupyter notebook notebooks/03_weather.ipynb

# 2. Spatial aggregation
jupyter notebook notebooks/02_a_h3_construction.ipynb
jupyter notebook notebooks/02_b_h3_full_construction.ipynb

# 3. Causal analysis
jupyter notebook notebooks/04_causal.ipynb
jupyter notebook notebooks/05_causal_validation.ipynb

# 4. Heterogeneous effects
jupyter notebook notebooks/06_CATE.ipynb

# 5. Visualization
streamlit run src/app.py
```

---

## Future Enhancements

### Methodological
1. **Instrumental variables**: Use wind direction as instrument for rain
2. **Regression discontinuity**: Exploit sudden rain onset/offset
3. **Difference-in-differences**: Compare NYC vs non-rainy cities
4. **Neural T-Learner**: Replace GBM with deep learning

### Data Improvements
1. **Real-time traffic**: Integrate Google Maps / Waze APIs
2. **Road conditions**: Add potholes, construction, streetlight data
3. **Driver behavior**: Add hard braking, speeding from telematics
4. **Weather granularity**: Radar-based precipitation (spatial variation)

### Operationalization
1. **Real-time scoring**: Deploy CATE model as REST API
2. **A/B testing framework**: Test interventions in high-CATE zones
3. **Multi-city deployment**: Extend to 10+ US cities
4. **Driver app integration**: Push safety alerts during rain in kill zones

---

## References

### Data Sources
- [NYPD Motor Vehicle Collisions](https://data.cityofnewyork.us/Public-Safety/Motor-Vehicle-Collisions-Crashes/h9gi-nx95)
- [NYC TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)
- [Open-Meteo Weather API](https://open-meteo.com/)

### Methods & Tools
- [H3 Spatial Indexing](https://h3geo.org/) (Uber)
- [DoWhy Causal Inference](https://www.pywhy.org/dowhy/) (Microsoft Research)
- [T-Learner Paper](https://arxiv.org/abs/1706.03461) (Künzel et al., 2019)

### Related Work
- Eisenberg & Warner (2005): Rain and accident rates
- Brodsky & Hakkert (1988): Weather effects on crashes
- Athey & Imbens (2016): Causal forests for heterogeneous effects

---

## Contact & Contributions

**Maintainer**: Ashish Reddy Tummuri  
**Repository**: https://github.com/Ashish-Reddy-T/CausalAccidents.git  
**Issues**: [Issue tracker] (TBD)

**Contributions are welcome 🙃 :)**

---

*Last updated*: December 1, 2025  
*Pipeline version*: 1.0  
*Data currency*: Through October 2025

---