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

def generate_telco_fixture():
    output_dir = os.path.join(os.path.dirname(__file__), "fixtures")
    os.makedirs(output_dir, exist_ok=True)
    fixture_path = os.path.join(output_dir, "telco_churn_data.csv")

    np.random.seed(42)
    n_rows = 200

    customer_ids = [f"7590-VHVEG{i:03d}" for i in range(1, n_rows + 1)]
    genders = np.random.choice(["Female", "Male"], size=n_rows)
    senior_citizens = np.random.choice([0, 1], size=n_rows, p=[0.84, 0.16])
    partners = np.random.choice(["Yes", "No"], size=n_rows, p=[0.52, 0.48])
    dependents = np.random.choice(["Yes", "No"], size=n_rows, p=[0.30, 0.70])
    tenures = np.random.randint(1, 72, size=n_rows)
    # Ensure some tenure >= 60 and some tenure < 6
    tenures[0:10] = 65
    tenures[10:20] = 3
    tenures[20:25] = 1

    phone_services = np.random.choice(["Yes", "No"], size=n_rows, p=[0.90, 0.10])
    multiple_lines = np.random.choice(["Yes", "No", "No phone service"], size=n_rows)
    internet_services = np.random.choice(["DSL", "Fiber optic", "No"], size=n_rows, p=[0.45, 0.40, 0.15])
    online_securities = np.random.choice(["Yes", "No", "No internet service"], size=n_rows)
    online_backups = np.random.choice(["Yes", "No", "No internet service"], size=n_rows)
    device_protections = np.random.choice(["Yes", "No", "No internet service"], size=n_rows)
    tech_supports = np.random.choice(["Yes", "No", "No internet service"], size=n_rows)
    streaming_tvs = np.random.choice(["Yes", "No", "No internet service"], size=n_rows)
    streaming_movies = np.random.choice(["Yes", "No", "No internet service"], size=n_rows)
    contracts = np.random.choice(["Month-to-month", "One year", "Two year"], size=n_rows, p=[0.55, 0.21, 0.24])
    paperless_billings = np.random.choice(["Yes", "No"], size=n_rows, p=[0.59, 0.41])
    payment_methods = np.random.choice([
        "Electronic check", "Mailed check", "Bank transfer (automatic)", "Credit card (automatic)"
    ], size=n_rows)

    monthly_charges = np.round(np.random.uniform(18.25, 118.75, size=n_rows), 2)
    # Ensure some monthly charges > 75
    monthly_charges[0:15] = 85.50

    total_charges = np.round(monthly_charges * tenures, 2)
    # Ensure some High Value Customers (TotalCharges > 5000)
    total_charges[0:10] = 5500.00
    total_charges[10:15] = 6200.50

    churns = np.random.choice(["Yes", "No"], size=n_rows, p=[0.27, 0.73])

    df = pd.DataFrame({
        "customerID": customer_ids,
        "gender": genders,
        "SeniorCitizen": senior_citizens,
        "Partner": partners,
        "Dependents": dependents,
        "tenure": tenures,
        "PhoneService": phone_services,
        "MultipleLines": multiple_lines,
        "InternetService": internet_services,
        "OnlineSecurity": online_securities,
        "OnlineBackup": online_backups,
        "DeviceProtection": device_protections,
        "TechSupport": tech_supports,
        "StreamingTV": streaming_tvs,
        "StreamingMovies": streaming_movies,
        "Contract": contracts,
        "PaperlessBilling": paperless_billings,
        "PaymentMethod": payment_methods,
        "MonthlyCharges": monthly_charges,
        "TotalCharges": total_charges,
        "Churn": churns
    })

    df.to_csv(fixture_path, index=False)
    print(f"Generated telco churn fixture with {len(df)} rows at {fixture_path}")

if __name__ == "__main__":
    generate_sales_fixture()
    generate_telco_fixture()
