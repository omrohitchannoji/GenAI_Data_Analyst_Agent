import os
import pandas as pd
import numpy as np

def generate_sales_fixture():
    output_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    os.makedirs(output_dir, exist_ok=True)
    fixture_path = os.path.join(output_dir, "sales_data.csv")

    np.random.seed(42)
    n_rows = 150

    order_ids = [1000 + i for i in range(1, n_rows + 1)]
    dates = pd.date_range(start="2023-01-15", end="2025-12-01", periods=n_rows).strftime("%Y-%m-%d")
    regions = np.random.choice(["North", "South", "East", "West"], size=n_rows, p=[0.3, 0.25, 0.25, 0.2])
    categories = np.random.choice(["Electronics", "Furniture", "Office Supplies"], size=n_rows)
    customer_ids = [f"C{np.random.randint(1, 25):03d}" for _ in range(n_rows)]
    customer_statuses = np.random.choice(["Active", "Inactive", "Pending", None], size=n_rows, p=[0.6, 0.2, 0.15, 0.05])
    quantities = np.random.randint(1, 15, size=n_rows)
    revenues = np.round(np.random.uniform(20.0, 1500.0, size=n_rows), 2)
    
    # Introduce deliberate edge cases:
    # 1. Some null revenues to test null handling
    revenues[5] = np.nan
    revenues[25] = np.nan
    
    # 2. Some zero costs to test division by zero / margin calculations
    costs = np.round(revenues * np.random.uniform(0.4, 0.85, size=n_rows), 2)
    costs[10] = 0.0

    df = pd.DataFrame({
        "order_id": order_ids,
        "order_date": dates,
        "customer_id": customer_ids,
        "customer_status": customer_statuses,
        "region": regions,
        "category": categories,
        "quantity": quantities,
        "revenue": revenues,
        "cost": costs
    })

    df.to_csv(fixture_path, index=False)
    print(f"Generated sales fixture with {len(df)} rows at {fixture_path}")

if __name__ == "__main__":
    generate_sales_fixture()
