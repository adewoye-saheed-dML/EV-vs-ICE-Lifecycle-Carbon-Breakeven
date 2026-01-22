import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pathlib import Path
from typing import Tuple
from etl_ice import get_ice_emissions  


DATA_PROCESSED = Path("data/processed")
MFG_PATH = DATA_PROCESSED / "manufacturing_baselines.csv"
GRID_PATH = DATA_PROCESSED / "grid_intensity_all.csv"
KM_STEP = 1000
MAX_KM = 250000

st.set_page_config(page_title="EV vs ICE Lifecycle Breakeven", layout="wide")

@st.cache_data
def load_data(mfg_path: Path = MFG_PATH, grid_path: Path = GRID_PATH) -> Tuple[pd.DataFrame, pd.DataFrame]:
    mfg = pd.read_csv(mfg_path)
    grid = pd.read_csv(grid_path)
    return mfg, grid

# ----------------------
# Utility functions
# ----------------------
def safe_country_index(grid_df: pd.DataFrame, default: str = "United States") -> int:
    try:
        return int(grid_df[grid_df["country"] == default].index[0])
    except Exception:
        return 0

def build_simulation(
    ice_mpg: float,
    ev_kwh_per_100km: float,
    annual_km: float,
    grid_base_g_per_kwh: float,
    grid_mode: str,
    grid_uncertainty_pct: float,
    ev_deg_pct: float,
    ice_real_world_penalty_pct: float,
    decarbonize: bool,
    annual_decarbonization_rate: float,
    ice_mfg: float,
    ev_mfg: float,
) -> pd.DataFrame:
    """Return simulation trajectories at KM_STEP resolution with full lifecycle integration."""
    km_points = np.arange(0, MAX_KM + KM_STEP, KM_STEP)

    # Adjust for uncertainties
    grid_adj = grid_base_g_per_kwh * (1 + grid_uncertainty_pct / 100)
    ev_eff_adj = ev_kwh_per_100km * (1 + ev_deg_pct / 100)
    ice_mpg_adj = ice_mpg * (1 - ice_real_world_penalty_pct / 100)

    # ICE operational slope
    ice_slope_g_km = get_ice_emissions(ice_mpg_adj)
    ice_slope_kg_km = ice_slope_g_km / 1000.0
    ice_step_kg = ice_slope_kg_km * KM_STEP

    # EV operational slope (dynamic grid if decarbonizing)
    ev_kwh_per_km = ev_eff_adj / 100.0
    years = km_points / max(annual_km, 1.0)
    if decarbonize:
        dynamic_grid_gpkwh = grid_adj * (1 - annual_decarbonization_rate) ** years
        ev_slope_g_km_points = ev_kwh_per_km * dynamic_grid_gpkwh
    else:
        ev_slope_g_km_points = np.full_like(km_points, ev_kwh_per_km * grid_adj, dtype=float))

    ev_slope_kg_km_points = ev_slope_g_km_points / 1000.0
    ev_step_kg_points = ev_slope_kg_km_points * KM_STEP

    # Cumulative operational emissions
    ice_cum = np.cumsum(np.concatenate([[0.0], np.repeat(ice_step_kg, len(km_points) - 1)]))
    ev_cum = np.cumsum(np.concatenate([[0.0], ev_step_kg_points[1:]]))

    # Build DataFrame
    df = pd.DataFrame({
        "km": km_points,
        "ice_operational_kg": ice_cum,
        "ev_operational_kg": ev_cum,
        "ev_slope_g_per_km": ev_slope_g_km_points,
        "grid_used_g_per_kwh": np.repeat(grid_adj, len(km_points)) if not decarbonize else dynamic_grid_gpkwh,
        "ice_mfg_kg": ice_mfg,
        "ev_mfg_kg": ev_mfg,
    })

    # Total emissions
    df["ice_total_kg"] = df["ice_operational_kg"] + ice_mfg
    df["ev_total_kg"] = df["ev_operational_kg"] + ev_mfg
    df["delta_kg"] = df["ice_total_kg"] - df["ev_total_kg"]

    return df

# Load data
try:
    df_mfg, df_grid = load_data()
except FileNotFoundError:
    st.error("Data files not found. Run ETL scripts first.")
    st.stop()


# Sidebar inputs

with st.sidebar:
    st.header("Simulation Settings")

    # Country & grid selection
    default_idx = safe_country_index(df_grid)
    selected_country = st.selectbox("Country", df_grid["country"].unique(), index=default_idx)
    grid_mode = st.radio("Grid Mode", ["Average", "Marginal"])
    grid_row = df_grid[df_grid["country"] == selected_country]
    grid_base_value = (
        float(grid_row["carbon_intensity_average"].iat[0]) if grid_mode=="Average" else float(grid_row["carbon_intensity_marginal"].iat[0])
    ) if not grid_row.empty else float(df_grid["carbon_intensity_average"].mean())

    # Vehicle specs
    st.subheader("Vehicle Specs")
    ice_mpg = st.slider("ICE Fuel Economy (MPG)", 10.0, 80.0, 30.0, 1.0)
    ev_eff = st.slider("EV Efficiency (kWh/100km)", 8.0, 30.0, 18.0, 0.5)

    # Usage
    st.subheader("Usage & Behavior")
    annual_km = st.number_input("Annual Driving (km)", min_value=1000, max_value=100000, value=15000)

    # Uncertainty & degradation
    st.subheader("Uncertainty & Degradation")
    grid_uncertainty_pct = st.slider("Grid Intensity Variation (%)", -50, 50, 0)
    ev_degradation_pct = st.slider("EV Efficiency Degradation (%)", 0, 50, 0)
    ice_real_world_penalty_pct = st.slider("ICE Real-world MPG Penalty (%)", 0, 50, 0)

    # Forward scenarios
    st.subheader("Forward Scenarios")
    decarbonize = st.checkbox("Apply Grid Decarbonization Scenario")
    annual_decarbonization_rate = st.slider("Annual Grid Decarbonization Rate (%)", 0.0, 10.0, 3.0) / 100.0 if decarbonize else 0.0

    # Policy lens
    st.subheader("Policy Lens")
    carbon_price = st.slider("Carbon Price ($/tCO2)", 0, 500, 50)

    st.markdown("---")
    st.checkbox("Show debug tables", key="debug")

# Manufacturing baselines
ice_mfg = float(df_mfg[df_mfg["vehicle_type"] == "ICE_Sedan"]["total_manufacturing_co2_kg"].iat[0])
ev_mfg = float(df_mfg[df_mfg["vehicle_type"] == "EV_Sedan"]["total_manufacturing_co2_kg"].iat[0])


# Build simulation
sim_df = build_simulation(
    ice_mpg=ice_mpg,
    ev_kwh_per_100km=ev_eff,
    annual_km=annual_km,
    grid_base_g_per_kwh=grid_base_value,
    grid_mode=grid_mode,
    grid_uncertainty_pct=grid_uncertainty_pct,
    ev_deg_pct=ev_degradation_pct,
    ice_real_world_penalty_pct=ice_real_world_penalty_pct,
    decarbonize=decarbonize,
    annual_decarbonization_rate=annual_decarbonization_rate,
    ice_mfg=ice_mfg,
    ev_mfg=ev_mfg,
)

# Breakeven calculation
breakeven_row = sim_df[sim_df["delta_kg"] > 0]
if not breakeven_row.empty:
    breakeven_km = int(breakeven_row["km"].iat[0])
    breakeven_years = breakeven_km / max(annual_km,1)
else:
    breakeven_km = None
    breakeven_years = None

# Dashboard layout
st.title("EV vs ICE Lifecycle Carbon Breakeven Analysis")

col1, col2, col3 = st.columns(3)
col1.metric("Manufacturing Carbon Debt (EV − ICE)", f"{int(ev_mfg - ice_mfg)} kg CO2")
col2.metric("Grid Intensity (selected)", f"{grid_base_value:.0f} gCO2/kWh")
if breakeven_km is not None:
    col3.metric("Breakeven", f"{breakeven_km:,} km", f"{breakeven_years:.1f} years")
else:
    col3.metric("Breakeven", "NEVER within range", "Check assumptions or grid")


# Distance inspector

with st.expander("Inspect Emissions at Specific Distance"):
    inspect_km = st.slider("Distance (km)", 0, MAX_KM, min(5000, MAX_KM))
    row = sim_df.iloc[(inspect_km // KM_STEP)]
    st.write(f"**At {inspect_km:,} km:**")
    c1, c2, c3 = st.columns(3)
    c1.metric("ICE total (kg CO2)", f"{row['ice_total_kg']:,.0f}")
    c2.metric("EV total (kg CO2)", f"{row['ev_total_kg']:,.0f}")
    label = "EV advantage" if row["delta_kg"] > 0 else "EV disadvantage"
    c3.metric("Difference (ICE − EV)", f"{row['delta_kg']:,.0f} kg CO2", label)
    monetized = (row["delta_kg"] / 1000.0) * carbon_price
    st.write(f"Monetized difference at this distance: ${monetized:,.2f} (using ${carbon_price}/tCO2)")


# Plots

# Cumulative emissions
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=sim_df["km"], 
    y=sim_df["ev_total_kg"], 
    name="EV Total", 
    line=dict(width=3)
))

fig.add_trace(go.Scatter(
    x=sim_df["km"], 
    y=sim_df["ice_total_kg"], 
    name="ICE Total", 
    line=dict(width=3),
    fill='tonexty',
    fillcolor='rgba(0, 200, 0, 0.1)' 
))

fig.add_trace(go.Scatter(
    x=np.concatenate([sim_df["km"], sim_df["km"][::-1]]),
    y=np.concatenate([sim_df["delta_kg"], np.zeros_like(sim_df["delta_kg"]) + sim_df["delta_kg"].min() - 1e3][::-1]),
    fill="toself",
    fillcolor="rgba(200,200,200,0.15)",
    line=dict(color="rgba(255,255,255,0)"),
    showlegend=False,
    hoverinfo="skip",
))
if breakeven_km:
    fig.add_vline(x=breakeven_km, line=dict(color="black", dash="dash"))
    fig.add_annotation(x=breakeven_km, y=max(sim_df["ice_total_kg"].max(), sim_df["ev_total_kg"].max()), text="Breakeven", showarrow=True, arrowhead=2)
fig.update_layout(title="Lifecycle Emissions: Manufacturing + Driving", xaxis_title="Distance (km)", yaxis_title="Cumulative CO2 (kg)", template="plotly_white", hovermode="x unified")
st.plotly_chart(fig, use_container_width=True)

# Delta emissions
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=sim_df["km"], y=sim_df["delta_kg"], name="ICE − EV (kg)", mode="lines"))
fig2.add_hline(y=0, line=dict(color="black", dash="dash"))
fig2.update_layout(title="Delta Emissions (ICE − EV)", xaxis_title="Distance (km)", yaxis_title="kg CO2", template="plotly_white")
st.plotly_chart(fig2, use_container_width=True)

# Export

export_df = sim_df[["km", "ice_total_kg", "ev_total_kg", "delta_kg", "grid_used_g_per_kwh", "ev_slope_g_per_km"]].copy()
export_df.rename(columns={
    "km":"distance_km",
    "ice_total_kg":"ice_total_kg_co2",
    "ev_total_kg":"ev_total_kg_co2",
    "delta_kg":"ice_minus_ev_kg_co2"
}, inplace=True)
csv = export_df.to_csv(index=False)
st.download_button("Download scenario results (CSV)", data=csv, file_name="breakeven_scenario.csv", mime="text/csv")


# Data assumptions

with st.expander("Data Sources & Assumptions"):
    st.markdown("""
- **Manufacturing baselines:** GREET 2025
- **Fuel chemistry:** EPA/IPCC gasoline carbon factor
- **Grid intensities:** IFI dataset (Average & Marginal)
- **System boundary:** Cradle-to-Wheel (manufacturing + use phase)
- **Uncertainty handling:** Grid variation & vehicle degradation
- **Decarbonization model:** Exponential decline applied to grid intensity
    """)

if st.session_state.get("debug"):
    with st.expander("Debug Data"):
        st.write("Manufacturing baselines:")
        st.write(df_mfg)
        st.write("Grid sample:")
        st.write(df_grid.head())
        st.write("Simulation head:")
        st.write(sim_df.head())

st.markdown("---")
st.caption("Professional lifecycle analysis — interactive, scenario-ready, and policy-sensitive.")
