import os
import sys
import tempfile
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from app.core.dataset_registry import DatasetRegistry

def test_dataset_registration_and_scoping():
    temp_db = os.path.join(tempfile.gettempdir(), "test_registry.db")
    if os.path.exists(temp_db):
        os.remove(temp_db)

    registry = DatasetRegistry(db_path=temp_db)

    # 1. Register dataset under principal_A
    ds_meta = registry.register_dataset(
        dataset_id="ds_sales_2025",
        principal_id="user_alice",
        filename="sales_2025.csv",
        table_name="data",
        db_path="uploaded_data.db",
        row_count=1500,
        column_types={"numeric": ["revenue"], "categorical": ["region"]}
    )
    assert ds_meta["dataset_id"] == "ds_sales_2025"

    # 2. Authorized access for user_alice
    assert registry.is_authorized("ds_sales_2025", "user_alice") is True
    retrieved = registry.get_dataset("ds_sales_2025", "user_alice")
    assert retrieved is not None
    assert retrieved["filename"] == "sales_2025.csv"
    assert retrieved["row_count"] == 1500

    # 3. Unauthorized access for user_bob
    assert registry.is_authorized("ds_sales_2025", "user_bob") is False
    assert registry.get_dataset("ds_sales_2025", "user_bob") is None

    # 4. Upload size limit validation
    assert registry.validate_upload_size(5 * 1024 * 1024) is True
    try:
        registry.validate_upload_size(15 * 1024 * 1024)
        assert False, "Should have raised ValueError for exceeding 10 MiB limit"
    except ValueError as e:
        assert "exceeds 10 MiB limit" in str(e)

    # 5. Persistence across server restart (new registry instance on same DB)
    new_registry_instance = DatasetRegistry(db_path=temp_db)
    reloaded = new_registry_instance.get_dataset("ds_sales_2025", "user_alice")
    assert reloaded is not None
    assert reloaded["row_count"] == 1500

    print("\n[Test T05 Passed] Dataset registration, principal scoping, upload limits, and persistence verified.")

if __name__ == "__main__":
    test_dataset_registration_and_scoping()
