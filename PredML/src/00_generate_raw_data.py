import numpy as np
import pandas as pd
import json
from config import (
    RAW_FILE, PRODUCTS, REGIONS,
    DATA_START_DATE, DATA_END_DATE,
    PRODUCT_MASTER_FILE,
    ensure_dirs, banner,
)

def generate_product_master():
    """Generate data/product_master.json file - the governance/catalogue file"""
    master = {}
    for prod_id, prod_name, catagory, base_sales, cost_ratio in PRODUCTS:
        master[prod_id] = {
            "status": "active", # active, retired, launch
            "product_name": prod_name,
            "category": catagory,
            "launch_date": "2020-01-01", # pre-dates our training window
            "analog_sku": None, # only used for launch/retired
            "notes": "seeded from PRODUCTS in config.py"
        }

    # Sentinal guidance for manual editing
    master["_README"] = (
        "to simulate a product launch, set status to 'launch' and analog_sku to the sku of the exisitrng product so that "
        "we can predict the cost with low confidence and once the status is active after some monts on sales data it will be high only"
        "to simulate a product retirement, set status to 'retired' and analog_sku to the sku of the exisitrng product so that "
        "we can predict the cost with low confidence and once the status is retired after some months on sales data it will be high only"
    )
    PRODUCT_MASTER_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRODUCT_MASTER_FILE.write_text(json.dumps(master, indent=2))
    print(f"\n Product master file saved to {PRODUCT_MASTER_FILE}")
    print(f"   Active SKUs: {sum(1 for k, v in master.items() if isinstance(v, dict) and v.get('status') == 'active')}")
    print(f" edit {PRODUCT_MASTER_FILE} to simulate product launches and retirements")



def generate_raw_data():
    """
    Generate raw data for the prediction model.
    """
    ensure_dirs() # create all folders data/ and model/ directories if they don't exist
    banner("Stage 0: Generating Raw Transaction Data") # Print a banner/visual for the stage
    rng = np.random.default_rng(seed=42)  # For reproducibility same output every time we run this script

    # Create a date range
    date_range = pd.date_range(start=DATA_START_DATE, end=DATA_END_DATE , freq="D")

    # Create a list to hold the data collect dict here , then convert to DataFrame at the end for performance
    data = []

    for date in date_range:
        # Seasonality multiplier: higher sales in Q4 (Oct-Dec), lower in Q1 (Jan-Mar)
        is_q4 = date.month in (10, 11, 12)
        is_weekend = date.weekday() >= 5
        q4_boost = 1.40 if is_q4 else 1.0 # Q4 sales are 40% higher(holiday push , budget spend) than other quarters
        weekend_dip = .70 if is_weekend else 1.0 # Weekend sales are 30% lower than weekdays(fewer doctors in office, less prescriptions filled)

        for prod_id, prod_name, catagory, base_sales, cost_ratio in PRODUCTS:
            for region in REGIONS:
                # sales = base * seasonality * regional_factor * random_noise
                regional_factor = {"NA": 1.2, "EU": 1.0, "APAC": 0.8, "LATAM": 0.6}[region]  # Random factor for regional differences
                noise = rng.normal(1.0, 0.1)  # Random noise
                sales = base_sales * q4_boost * weekend_dip * regional_factor * noise
                # cost = sales * cost_ratio + Q4 supply chain premium + noise
                cost_noise = rng.normal(1.0, 0.08)  # Random noise for cost
                q4_supply_premium = 1.10 if is_q4 else 1.0  # Q4 supply chain premium
                actual_cost = sales * cost_ratio + q4_supply_premium * cost_noise # Final cost calculation

                data.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "product_id": prod_id,
                    "product_name": prod_name,
                    "category": catagory,
                    "region": region,
                    "sales": round(sales, 2),
                    "actual_cost": round(actual_cost, 2)
                })

    df = pd.DataFrame(data)

    # Inject realistic data-quality issues: ~ 0.5% missing values and outliers
    n = len(df)
    missing_indices = rng.choice(n, size=int(0.005 * n), replace=False)
    df.loc[missing_indices, "sales"] = np.nan

    outlier_indices = rng.choice(n, size=int(0.001 * n), replace=False)
    df.loc[outlier_indices, "actual_cost"] *= 15

    df.to_csv(RAW_FILE, index=False)

    print(f"Raw data saved to {RAW_FILE}")
    print(f"Total rows generated: {len(df)}")
    print(f" Data range: {df['date'].min()} to {df['date'].max()}")
    print(f" Products: {df['product_id'].nunique()} | Regions: {len(REGIONS)}")
    print(f" Missing sales values: {df['sales'].isna().sum()} | Outliers in actual_cost: {len(outlier_indices)}")
    print(f" Sample data:\n{df.head(5)}\n")
    print(f"Records with missing sales ({len(missing_indices)}):")
    print(df.loc[missing_indices].sort_index().head(5).to_string(index=False))
    print(f"\nRecords with outlier actual_cost ({len(outlier_indices)}):")
    print(df.loc[outlier_indices].sort_index().head(5).to_string(index=False))

    generate_product_master()

if __name__ == "__main__":
    generate_raw_data()