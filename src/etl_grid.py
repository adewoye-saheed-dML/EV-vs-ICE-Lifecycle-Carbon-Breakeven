import logging
from pathlib import Path
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


RAW_PATH = Path("data/raw/IFI_Grid_Factors_2021_v3.2.xlsx")
OUTPUT_PATH = Path("data/processed/grid_intensity_all.csv")



# Helpers

def find_data_sheet(xls: pd.ExcelFile) -> str:
    for sheet in xls.sheet_names:
        preview = pd.read_excel(xls, sheet_name=sheet, header=None, nrows=15)
        if preview.astype(str).apply(
            lambda col: col.str.contains("Country", case=False, na=False)
        ).any().any():
            return sheet
    raise ValueError("No sheet containing country data found.")


def build_flat_columns(df_raw: pd.DataFrame, header_rows: int = 3) -> pd.DataFrame:
    """
    Build a single flat header from merged IFI header rows.
    """
    headers = df_raw.iloc[:header_rows].fillna(method="ffill", axis=1)
    data = df_raw.iloc[header_rows:].reset_index(drop=True)

    flat_columns = []
    for col_idx in range(headers.shape[1]):
        parts = [
            str(headers.iloc[row, col_idx]).strip()
            for row in range(header_rows)
            if pd.notna(headers.iloc[row, col_idx])
        ]
        flat_columns.append(" | ".join(parts))

    data.columns = flat_columns
    return data


def process_ifi_grid_data(
    input_path: Path = RAW_PATH,
    output_path: Path = OUTPUT_PATH,
) -> pd.DataFrame:
    logger.info("Opening Excel file: %s", input_path)
    xls = pd.ExcelFile(input_path)

    sheet_name = find_data_sheet(xls)
    logger.info("Detected data sheet: %s", sheet_name)

    # Read raw (no headers)
    df_raw = pd.read_excel(
        input_path,
        sheet_name=sheet_name,
        header=None,
    )

    df = build_flat_columns(df_raw, header_rows=3)

    # Identify columns via semantic matching

    country_col = [c for c in df.columns if "country" in c.lower()][0]

    combined_margin_col = [
        c for c in df.columns
        if "combined margin" in c.lower()
        and "electricity consumption" in c.lower()
    ][0]

    operating_margin_col = [
        c for c in df.columns
        if "operating margin" in c.lower()
        and "electricity consumption" in c.lower()
    ][0]

    logger.info("Using Combined Margin column: %s", combined_margin_col)
    logger.info("Using Operating Margin column: %s", operating_margin_col)


    clean_df = df[
        [country_col, combined_margin_col, operating_margin_col]
    ].copy()

    clean_df.columns = [
        "country",
        "carbon_intensity_average",
        "carbon_intensity_marginal",
    ]

    clean_df = clean_df.dropna(subset=["country"])

    for col in ["carbon_intensity_average", "carbon_intensity_marginal"]:
        clean_df[col] = pd.to_numeric(clean_df[col], errors="coerce")

    clean_df = clean_df.dropna()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    clean_df.to_csv(output_path, index=False)

    logger.info("Processed %d countries", len(clean_df))
    logger.info("Saved to %s", output_path)

    return clean_df

if __name__ == "__main__":
    process_ifi_grid_data()
