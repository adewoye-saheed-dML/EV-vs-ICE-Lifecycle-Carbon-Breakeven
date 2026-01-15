from typing import Union

MILES_TO_KM = 1.60934
CO2_TAILPIPE_G_PER_GAL = 8887
WTP_OVERHEAD_FACTOR = 1.266


def get_ice_emissions(fuel_efficiency_mpg: Union[int, float]) -> float:
    """
    Compute lifecycle ICE emissions intensity (g CO2 / km).
    """
    total_co2_per_gal = CO2_TAILPIPE_G_PER_GAL * WTP_OVERHEAD_FACTOR
    grams_per_mile = total_co2_per_gal / fuel_efficiency_mpg
    return grams_per_mile / MILES_TO_KM


if __name__ == "__main__":
    print(f"30 MPG Car Slope: {get_ice_emissions(30):.1f} g/km")
