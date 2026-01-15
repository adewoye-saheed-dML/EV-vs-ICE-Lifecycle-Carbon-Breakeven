import logging
from pathlib import Path
from typing import Union

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_OUTPUT = Path("data/processed/manufacturing_baselines.csv")


def get_manufacturing_data(output_path: Union[str, Path] = DEFAULT_OUTPUT) -> pd.DataFrame:
    """
    Create and persist a baseline manufacturing emissions table (kg CO2).
    Returns the created DataFrame.
    """
    # baseline numbers (units: kg CO2)
    vehicle_types = ["ICE_Sedan", "EV_Sedan"]
    total_manufacturing_co2 = [6079, 10471]
    battery_manufacturing_co2 = [34, 5238]
    fluids_co2 = [745, 174]

    # compute glider as residual: total - battery - fluids
    glider_co2 = [
        total - battery - fluids
        for total, battery, fluids in zip(total_manufacturing_co2, battery_manufacturing_co2, fluids_co2)
    ]

    data = {
        "vehicle_type": vehicle_types,
        "total_manufacturing_co2_kg": total_manufacturing_co2,
        "battery_manufacturing_co2_kg": battery_manufacturing_co2,
        "fluids_co2_kg": fluids_co2,
        "glider_co2_kg": glider_co2,
    }

    df = pd.DataFrame(data)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    # summary stats
    ice_total = df.loc[df["vehicle_type"] == "ICE_Sedan", "total_manufacturing_co2_kg"].iat[0]
    ev_total = df.loc[df["vehicle_type"] == "EV_Sedan", "total_manufacturing_co2_kg"].iat[0]
    ev_battery = df.loc[df["vehicle_type"] == "EV_Sedan", "battery_manufacturing_co2_kg"].iat[0]

    ev_carbon_debt = ev_total - ice_total
    battery_share = ev_battery / ev_total if ev_total else 0.0

    logger.info("Manufacturing data written to %s", output_path)
    logger.info("EV carbon debt: %d kg CO2", ev_carbon_debt)
    logger.info("Battery share of EV manufacturing emissions: %.1f%%", battery_share * 100)

    return df


if __name__ == "__main__":
    get_manufacturing_data()
