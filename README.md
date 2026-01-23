# EV vs ICE Lifecycle Carbon Breakeven Calculator

A professional-grade interactive simulation tool built with Streamlit to compare the lifecycle carbon emissions of Electric Vehicles (EV) and Internal Combustion Engine (ICE) vehicles.

This project simulate vehicle physics, grid dynamics, and manufacturing debt over a 250,000 km lifecycle. It is designed to identify the exact "Breakeven Point" where an EV's operational carbon savings offset its higher initial manufacturing footprint.

<img width="1560" height="840" alt="Image" src="https://github.com/user-attachments/assets/3e3ea83b-d3e3-48ca-8bc5-9477e345eef3" />


---

## Mathematical & Simulation Logic

This application uses a discrete-time simulation model (step = 1,000 km) to calculate cumulative CO2 emissions. Below are the governing equations used in the code.

### ICE (Internal Combustion Engine) Physics
The ICE model accounts for both tailpipe emissions and the upstream emissions required to produce the fuel (Well-to-Pump).

* **Formula:**
    $$E_{ice}(d) = \text{Mfg}_{ice} + \sum_{k=0}^{d} \left( \frac{8,887 \text{ gCO}_2/\text{gal}}{MPG_{adj}} \times 1.266 \right)$$

* **Logic Explained:**
    * 8,887 g: The amount of CO2 released by burning 1 gallon of gasoline (EPA standard).
    * 1.266 (WTP Factor): A "Well-to-Pump" multiplier adds 26.6% to account for oil drilling, refining, and transport (GREET model).
    * **Real-World Penalty:** The user-input MPG is penalized by a percentage to simulate real-world traffic conditions:
        $$MPG_{adj} = MPG_{rated} \times (1 - \text{Penalty}\%)$$

### EV (Electric Vehicle) Physics
The EV model is dynamic. It accounts for battery degradation(efficiency loss) and grid decarbonization (grid cleaning) simultaneously over time.

#### Linear Efficiency Degradation
Batteries lose capacity and efficiency as they age. We model this linearly over the vehicle's lifespan (0 to 250,000 km).

* **Formula:**
    $$\eta_{ev}(d) = \eta_{base} \times \left( 1 + \text{Degradation}\% \times \frac{d}{250,000} \right)$$

    * Logic: An EV that starts at 18 kWh/100km might degrade to 21 kWh/100km by the end of its life, requiring more energy to drive the same distance.

#### Grid Decarbonization (Exponential Decay)
The simulator assumes the electricity grid gets cleaner over time based on a user-defined annual rate.
* **Formula:**
    $$G_{intensity}(t) = G_{base} \times (1 - \text{DecarbRate})^{t}$$
    * Where: $t$ is calculated as $d / \text{AnnualDriving}_{km}$.

### Cumulative Integration (The "Riemann Sum" Fix)
To avoid "forward-bias" errors (where the car gets credit for a cleaner grid before it actually reaches that year), the simulation uses a **Left Riemann Sum** logic for integration.
* **Logic:** For the interval $k$ to $k+1000$, we use the emissions rate at distance $k$ (start of interval), not $k+1000$ (end of interval).
* **Code Implementation:**
    ```python
    # EV Cumulative Calculation
    # Uses [:-1] to take the rate at the START of the interval
    ev_cum = np.cumsum(np.concatenate([[0.0], ev_step_kg_points[:-1]]))
    ```

### Manufacturing Debt (The "Backpack")
The simulation starts at $d=0$ with a manufacturing carbon debt.
* **EV Debt:** Includes Glider + Battery + Fluids + Assembly (~10,500 kg CO2).
* **ICE Debt:** Includes Glider + Engine + Fluids + Assembly (~6,000 kg CO2).
* **Source:** GREET 2025 Model.

---

## Data Sources & ETL Pipelines

The project uses a structured ETL (Extract, Transform, Load) process to ensure data integrity.

### 1. Grid Intensity Data (`src/etl_grid.py`)
* **Source:** IFI Dataset of Default Grid Factors v3.2 (2021).
* **Logic:**
    * Extracts Average (Baseload) and Marginal (Peaker) emissions factors for 200+ countries.
    * **Handling Nulls:** If "Marginal" data is missing (NaN) for a country, the application falls back to "Average" data to prevent simulation crashes.
    * **Hydro Logic:** Correctly preserves `0 gCO2/kWh` for 100% renewable grids (e.g., Albania, Paraguay).

### 2. Manufacturing Baselines (`src/etl_mfg.py`)
* **Source:** Argonne National Lab GREET Model (2025).
* **Hardcoded Constants:**
    * Battery Manufacturing: ~98 kg CO2 per kWh of capacity.
    * Glider (Body): Shared footprint for both vehicle types to ensure fair comparison.

### 3. ICE Constants (`src/etl_ice.py`)
* **Carbon Content:** 8,887 grams per gallon (Gasoline).
* **Upstream Overhead:** 1.266 (26.6% adder for extraction/refining).

---

## Installation & Setup

### Prerequisites
* Python 3.8+
* Pip (Python Package Installer)

### Step 1: Clone & Environment
```bash
git clone https://github.com/adewoye-saheed-dML/EV-vs-ICE-Lifecycle-Carbon-Breakeven.git
cd EV-vs-ICE-Lifecycle-Carbon-Breakeven

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```
### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```
### Step 3: Run ETL (Optional)
```bash
python src/etl_mfg.py
python src/etl_grid.py
```
### Step 4: Launch App
```bash
streamlit run src/app.py
```
## Application Architecture
```text
├── src/
│   ├── app.py          # CONTROL LAYER: UI, Simulation Engine, Visualization
│   ├── etl_grid.py     # DATA LAYER: Grid intensity parsing & cleaning
│   ├── etl_ice.py      # LOGIC LAYER: Internal Combustion physics
│   └── etl_mfg.py      # DATA LAYER: Manufacturing baseline generation
├── data/
│   ├── raw/            # IFI Excel Data
│   └── processed/      # Optimized CSVs for the app
└── requirements.txt    # Dependencies (pandas, numpy, plotly, streamlit)
```

## Features & Controls
**Grid Mode Toggle:** 
*  * Average: Represents the current mix of generation.
   * Marginal: Represents the emissions impact of adding new * load (EV charging) to the grid.

**Sensitivity Analysis:**
*    Sliders allow users to test "Worst Case" (Dirty Grid +   High Degradation) vs "Best Case" scenarios.

**Monetization:**
*    Calculates the social cost of carbon savings using a user-defined price (e.g., $50/ton).

**Robust Error Handling:**
*    Prevents crashes when selecting countries with incomplete data.
*    Validates slider inputs to prevent impossible physics (e.g., negative distance).