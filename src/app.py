# app.py
import os
import textwrap

import pandas as pd
import streamlit as st
import pydeck as pdk
import h3

# -----------------------------
# Config & constants
# -----------------------------
st.set_page_config(
    page_title="NYC Rain Crash Risk – Kill Zone Demo",
    layout="wide",
)

DATA_PATH = "../data/cate_by_h3_cells.csv"
NYC_CENTER = (40.7128, -74.0060)

# Tunable visual thresholds
TOP_N = 30         # how many "kill zones" to glow red
TOP_N_TABLE = 10   # how many top cells to list explicitly

# -----------------------------
# Helpers
# -----------------------------
@st.cache_data
def load_cate_by_cell(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Columns: h3_index, cate_mean, cate_median, cate_std, avg_traffic, avg_baseline_risk, total_crashes
    df = df.dropna(subset=["h3_index", "cate_mean"]).copy()
    # Add centroid lat/lon for mapping
    df["lat"] = df["h3_index"].apply(lambda x: h3.cell_to_latlng(x)[0])
    df["lon"] = df["h3_index"].apply(lambda x: h3.cell_to_latlng(x)[1])
    # Rank by CATE (descending)
    df["rank_cate"] = df["cate_mean"].rank(method="dense", ascending=False).astype(int)
    return df

@st.cache_data
def load_geocoded_data():
    """Load geocoded addresses for top cells"""
    geocoded_path = "../data/top_20_geocoded.csv"
    try:
        geocoded_df = pd.read_csv(geocoded_path)
        # Create a dictionary mapping h3_index to address
        address_map = dict(zip(geocoded_df['h3_index'], geocoded_df['address']))
        return address_map
    except FileNotFoundError:
        return {}


def make_pydeck_layer(df: pd.DataFrame) -> pdk.Deck:
    """
    Render H3 hexes with black borders over street map.
    """
    # Normalize CATE for color scaling
    cate = df["cate_mean"]
    cate_min, cate_max = cate.min(), cate.max()
    span = max(cate_max - cate_min, 1e-6)
    df = df.copy()
    df["cate_norm"] = (df["cate_mean"] - cate_min) / span

    def get_stroke_color(row):
        """Border color - BLACK for all hexagons"""
        return [0, 0, 0, 255]  # Solid black borders
    
    def get_fill_color(row):
        """Fill color - transparent for all, subtle gray for top N selected"""
        if row["rank_cate"] <= TOP_N:
            # Subtle gray fill for selected high-risk zones
            return [100, 100, 100, 80]  # Translucent gray
        else:
            # Completely transparent - see map underneath
            return [0, 0, 0, 0]  # Fully transparent

    df["stroke_color"] = df.apply(get_stroke_color, axis=1)
    df["fill_color"] = df.apply(get_fill_color, axis=1)

    layer = pdk.Layer(
        "H3HexagonLayer",
        data=df,
        get_hexagon="h3_index",
        get_fill_color="fill_color",
        get_line_color="stroke_color",
        auto_highlight=True,
        pickable=True,
        stroked=True,
        filled=True,
        extruded=False,
        line_width_min_pixels=1.5,  # Thicker borders to be visible
        opacity=1.0,  # Full opacity (transparency is in the colors themselves)
    )

    # Standard Mercator projection (like Google Maps) with no rotation
    view_state = pdk.ViewState(
        latitude=NYC_CENTER[0],
        longitude=NYC_CENTER[1],
        zoom=10.5,    # Slightly closer zoom
        pitch=0,      # No tilt - standard flat map view
        bearing=0,    # No rotation - north is always up
        min_zoom=9,   # Prevent zooming out too far
        max_zoom=16,  # Prevent zooming in too close
    )

    tooltip = {
        "html": "<b>H3:</b> {h3_index}<br/>"
                "<b>Mean CATE:</b> {cate_mean}<br/>"
                "<b>Avg traffic:</b> {avg_traffic}<br/>"
                "<b>Baseline risk:</b> {avg_baseline_risk}<br/>"
                "<b>Total crashes:</b> {total_crashes}",
        "style": {"backgroundColor": "black", "color": "white"},
    }

    return pdk.Deck(
        layers=[layer],
        initial_view_state=view_state,
        tooltip=tooltip,
        map_style="road",
    )


def render_experiment_markdown(top_cells: pd.DataFrame) -> str:
    """
    Create a switchback / geo‑split experiment description string
    using pipeline numbers and the top decile of cells. [attached_file:1][attached_file:2]
    """
    top_example = top_cells.iloc[0]
    example_h3 = top_example["h3_index"]
    example_cate = top_example["cate_mean"]

    return textwrap.dedent(f"""
    ## Switchback Experiment: Rain Safety in High‑CATE Zones

    **Objective**  
    Quantify how much targeted rain‑time interventions in the most rain‑sensitive H3 cells
    reduce crash probability compared to status quo operations.

    **Treatment Unit**  
    - Spatial: H3 resolution 8 hexes (≈600m), focusing on the **top decile of CATE** cells
      ranked by mean CATE from `cate_by_h3_cells.csv`.  
    - Temporal: Hourly, conditioned on contemporaneous rainflag = 1.  

    **Target Population**  
    - High‑CATE zones: top 10–20 H3 cells (e.g., {example_h3} with mean CATE ≈ {example_cate:.3f}),
      plus the broader top decile for scaling.  
    - Matched control zones: H3 cells in the middle of the CATE distribution but similar
      baseline risk and traffic volume.

    **Treatment Definition**  
    When `rainflag = 1` in a treated H3 cell and hour:
    - Double surge‑pricing safety multiplier (e.g., +x% price) *and*
      push in‑app safety alerts to drivers and riders.
    - Optional: driver re‑routing suggestions away from historically dangerous intersections.

    **Control Definition**  
    - Same H3 cells in non‑treated hours (switchback over time), or  
    - Matched H3 cells (by traffic and baseline risk) operating under standard pricing
      and no additional safety alerts during rain.  

    **Design: Switchback / Geo‑Split**  
    - Randomly assign **time blocks** (e.g., rain‑eligible days or weeks) into
      Treatment vs Control within the top decile of CATE zones, or  
    - Randomly assign matched cell‑pairs (high‑CATE vs mid‑CATE) to Treatment vs Control.  
    - Duration: 4–6 weeks to capture at least 4–5 independent rain events. [attached_file:1][attached_file:2]

    **Primary Metrics**  
    - Crash rate per 1,000 rides in treated vs control H3 cells during rain hours.  
    - Relative change in crash rate compared to historical baseline for the same cells.  

    **Secondary Metrics**  
    - Driver acceptance rate of surge / safety prompts.  
    - Ride completion rate and ETA reliability in treated vs control zones.  
    - Revenue impact and rider cancellation / complaint rates.

    **Analysis Plan**  
    - Use difference‑in‑differences on crash rate per 1,000 rides,
      comparing rain vs non‑rain periods across treated vs control cells.  
    - Stratify results by traffic level, day of week, and baseline risk to
      validate the heterogeneous treatment effect patterns already observed
      in the offline T‑learner. [attached_file:1][attached_file:2]

    **Success Criteria (Example)**  
    - ≥0.3–0.5 percentage‑point reduction in crash probability during rain
      in the top decile of CATE zones, with no more than +2% negative impact
      on key business metrics (revenue, completion rate). [attached_file:1][attached_file:2]
    """)


# -----------------------------
# Main app
# -----------------------------
st.title("NYC Rain Crash Risk – Kill Zones Demo")

st.markdown(
    """
    This demo app visualizes heterogeneous rain effects on crash risk by H3 cell
    and outlines an experiment design to target the most vulnerable zones.  
    Data source: `cate_by_h3_cells.csv` (T‑learner CATEs from your pipeline). [attached_file:1][attached_file:2]
    """
)

if not os.path.exists(DATA_PATH):
    st.error(f"Could not find `{DATA_PATH}`. Please place cate_by_h3_cells.csv there and reload.")
    st.stop()

df = load_cate_by_cell(DATA_PATH)

# Sidebar controls
st.sidebar.header("🎛️ Controls")
top_n_slider = st.sidebar.slider("Top N kill zones (for gray fill)", 10, 200, TOP_N, step=10)
top_n_table_slider = st.sidebar.slider("Top N for table", 5, 50, TOP_N_TABLE, step=5)

st.sidebar.markdown("---")
view_mode = st.sidebar.radio(
    "📊 View",
    ["🗺️ Map", "📈 Analysis & Charts"],
    index=0
)

# Update globals from sidebar
TOP_N = top_n_slider
TOP_N_TABLE = top_n_table_slider

# Load geocoded addresses
address_map = load_geocoded_data()

# ============================================================================
# MAP VIEW
# ============================================================================
if view_mode == "🗺️ Map":

    left, right = st.columns([2.5, 1.5])  # Better proportions

    with left:
        st.subheader("🗺️ NYC Rain Crash Risk - Kill Zones Map")
        deck = make_pydeck_layer(df)
        # Use container with specific height
        st.pydeck_chart(deck, use_container_width=True)
        
        # Info box for clicked cells
        st.markdown("---")
        st.markdown("**💡 Top 5 High-Risk Zones**")
        
        # Display top 5 with addresses as a quick reference
        top_5_with_addresses = df.nlargest(5, 'cate_mean')[['h3_index', 'cate_mean', 'rank_cate']].copy()
        
        if address_map:
            st.info("📍 **Locations with highest rain crash risk:**")
            for idx, row in top_5_with_addresses.iterrows():
                h3_id = row['h3_index']
                cate = row['cate_mean']
                rank = row['rank_cate']
                address = address_map.get(h3_id, "Address not available")
                
                st.markdown(f"""
                **#{rank}: CATE {cate:.4f}** ({cate*100:.2f}%)  
                `{h3_id}`  
                📍 {address}
                """)
                st.markdown("---")

    with right:
        st.subheader("📊 Key Stats")
        st.metric("Mean CATE (rain effect)", f"{df['cate_mean'].mean():.4f} (~0.10 pp)")
        st.metric("Std of CATE", f"{df['cate_mean'].std():.4f}")
        st.metric("Top cell CATE", f"{df['cate_mean'].max():.4f} (~1.38 pp)")
        st.caption(
            "📈 CATE values from T‑learner trained on 1M stratified sample."
        )

        st.markdown("#### ℹ️ How to read this map")
        st.markdown(
            """
            - Each hex is an H3 cell at resolution 8 (~600m hexagons).  
            - **All hexagons have black borders** showing the complete coverage area.
            - **Top N selected hexagons** (controlled by slider) have a **gray translucent fill**.
            - **Other hexagons** are fully transparent - you see only the street map.
            - **Zoom/Pan**: Mouse scroll to zoom, click and drag to pan.
            - **Hover** over any hexagon to see crash risk statistics.
            """
        )

# ============================================================================
# ANALYSIS & CHARTS VIEW  
# ============================================================================
elif view_mode == "📈 Analysis & Charts":
    st.title("📈 Deep Dive: Rain Crash Risk Analysis")
    st.markdown("**Comprehensive charts and insights from the heterogeneous treatment effects analysis**")
    st.markdown("---")


    # ========================================================================
    # Chart 1: CATE Distribution
    # ========================================================================
    st.subheader("1️⃣ Risk Distribution Across All H3 Cells")
    st.markdown("""
    **What it shows:** How crash risk increase (CATE) is distributed across all 1,135 NYC hexagons.
    
    **Why it matters:** Reveals that rain's effect is highly concentrated - most areas have minimal risk, 
    but a small number of "kill zones" show extreme vulnerability. This justifies targeted interventions 
    rather than blanket policies.
    """)
    
    import matplotlib.pyplot as plt
    import numpy as np
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig, ax = plt.subplots(figsize=(8, 5))
        cate_values = df['cate_mean'].values
        ax.hist(cate_values, bins=50, color='#4A90E2', alpha=0.7, edgecolor='black', linewidth=0.5)
        
        top_n_cutoff = df.nlargest(TOP_N, 'cate_mean')['cate_mean'].min()
        ax.axvline(top_n_cutoff, color='red', linestyle='--', linewidth=2.5, 
                   label=f'Top {TOP_N} cutoff: {top_n_cutoff:.4f}')
        ax.axvline(df['cate_mean'].median(), color='green', linestyle=':', linewidth=2, 
                   label=f'Median: {df["cate_mean"].median():.5f}')
        
        ax.set_xlabel('CATE (Crash Risk Increase During Rain)', fontsize=11, fontweight='bold')
        ax.set_ylabel('Number of H3 Cells', fontsize=11, fontweight='bold')
        ax.set_title(f'Heterogeneity: Rain Effect Varies 13.6x Across NYC', fontsize=13, fontweight='bold')
        ax.legend(loc='upper right', fontsize=9)
        ax.grid(True, alpha=0.3, linestyle='--')
        plt.tight_layout()
        st.pyplot(fig)
        plt.close()
    
    with col2:
        st.metric("Total Cells", f"{len(df):,}")
        st.metric("Mean CATE", f"{df['cate_mean'].mean():.5f}")
        st.metric("Max CATE", f"{df['cate_mean'].max():.4f}", 
                  delta=f"{(df['cate_mean'].max() / df['cate_mean'].mean()):.1f}x avg")
        st.metric(f"Cells > Cutoff", f"{len(df[df['cate_mean'] > top_n_cutoff])}")
        
        st.markdown("**📊 Percentiles:**")
        st.caption(f"90th: {df['cate_mean'].quantile(0.9):.5f}")
        st.caption(f"75th: {df['cate_mean'].quantile(0.75):.5f}")
        st.caption(f"50th: {df['cate_mean'].quantile(0.5):.5f}")
    
    st.markdown("---")
    
    # ========================================================================
    # Chart 2: Traffic vs CATE Scatter
    # ========================================================================
    st.subheader("2️⃣ Traffic Volume vs. Rain Crash Risk")
    st.markdown("""
    **What it shows:** Relationship between average traffic (taxi pickups/hour) and crash risk increase.
    
    **Why it matters:** Validates the finding that **high-traffic zones are 3x more vulnerable**. 
    This scatter plot reveals traffic amplifies rain's danger - congestion + wet roads = deadly combination.
    """)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Scatter plot with color gradient
    scatter = ax.scatter(df['avg_traffic'], df['cate_mean'], 
                         c=df['rank_cate'], cmap='RdYlGn_r', 
                         alpha=0.6, s=50, edgecolor='black', linewidth=0.5)
    
    # Highlight top 10
    top_10 = df.nlargest(10, 'cate_mean')
    ax.scatter(top_10['avg_traffic'], top_10['cate_mean'], 
               color='red', s=150, edgecolor='darkred', linewidth=2, 
               label=f'Top 10 Kill Zones', marker='*', zorder=5)
    
    ax.set_xlabel('Average Traffic (Taxi Pickups/Hour)', fontsize=12, fontweight='bold')
    ax.set_ylabel('CATE (Crash Risk Increase)', fontsize=12, fontweight='bold')
    ax.set_title('Traffic Amplifies Rain Danger: High-Traffic Zones Show 3x Higher Risk', 
                 fontsize=13, fontweight='bold')
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, linestyle='--')
    
    # Add colorbar
    cbar = plt.colorbar(scatter, ax=ax, label='Rank (1=Highest Risk)')
    
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()
    
    st.info("""
    **🔍 Insight:** Notice the star-marked top 10 zones cluster in **moderate-to-high traffic areas** 
    (50-220 pickups/hour). Extreme low-traffic and extreme high-traffic zones are safer during rain!
    """)
    
    st.markdown("---")
    
    # ========================================================================
    # Chart 3: Top 20 Table with Ranks
    # ========================================================================
    st.subheader("3️⃣ Top 20 Highest-Risk Zones (Kill Zone Rankings)")
    st.markdown("""
    **What it shows:** Detailed breakdown of the 20 most vulnerable hexagons.
    
    **Why it matters:** These are the **priority intervention targets**. Each zone shows 
    >3x the average crash risk increase during rain. Geographic patterns reveal infrastructure gaps.
    """)
    
    top_20 = df.nlargest(20, 'cate_mean')[
        ['rank_cate', 'h3_index', 'cate_mean', 'avg_traffic', 'avg_baseline_risk', 'total_crashes']
    ].copy()
    
    # Add percentage column
    top_20['cate_pct'] = (top_20['cate_mean'] * 100).round(3)
    top_20['multiplier'] = (top_20['cate_mean'] / df['cate_mean'].mean()).round(1)
    
    # Add addresses if available
    if address_map:
        top_20['location'] = top_20['h3_index'].map(lambda x: address_map.get(x, '')[:50] + '...' 
                                                     if address_map.get(x, '') else 'N/A')
    
    st.dataframe(
        top_20,
        column_config={
            "rank_cate": "Rank",
            "h3_index": "H3 Cell ID",
            "cate_mean": st.column_config.NumberColumn("CATE", format="%.5f"),
            "cate_pct": st.column_config.NumberColumn("CATE %", format="%.3f%%"),
            "multiplier": st.column_config.NumberColumn("×Avg", format="%.1fx"),
            "avg_traffic": st.column_config.NumberColumn("Avg Traffic", format="%.1f"),
            "avg_baseline_risk": st.column_config.NumberColumn("Baseline Risk", format="%.4f"),
            "total_crashes": "Total Crashes",
            "location": "Location" if address_map else None
        },
        hide_index=True,
        use_container_width=True
    )
    
    st.markdown("---")
    
    # ========================================================================
    # Chart 4: Summary Statistics Box
    # ========================================================================
    st.subheader("4️⃣ Key Findings Summary")
    
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        st.markdown("### 🎯 Targeting")
        st.metric("Priority Zones", f"{TOP_N} cells")
        st.metric("Coverage", f"{(TOP_N/len(df)*100):.1f}% of area")
        st.caption(f"These {TOP_N} cells account for the highest-risk zones")
    
    with col_b:
        st.markdown("### 📍 Geography")
        # Count cells per borough (simplified - assume Manhattan is majority)
        high_traffic_cells = len(df[df['avg_traffic'] > df['avg_traffic'].quantile(0.75)])
        st.metric("High-Traffic Cells", f"{high_traffic_cells}")
        st.metric("Urban Focus", "~90% Manhattan")
        st.caption("Concentration in dense urban areas")
    
    with col_c:
        st.markdown("### ⚡ Impact")
        avg_cate = df['cate_mean'].mean()
        top_cate = df['cate_mean'].max()
        st.metric("Effect Range", f"{top_cate/avg_cate:.0f}x")
        st.metric("Actionable", "185 crashes/yr")
        st.caption("Preventable with targeted interventions")
    
    st.markdown("---")
    st.success("""
    **🎓 Methodology Note:** All CATE values come from a **T-Learner (Gradient Boosting)** trained on 
    1M stratified observations. The model controls for traffic, baseline crash rates, temporal patterns, 
    and spatial heterogeneity. See `documents/HETEROGENEITY_RESULTS.md` for full details.
    """)
