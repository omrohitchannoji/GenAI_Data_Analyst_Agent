import pandas as pd
from typing import List

def build_dataset_context(df:pd.DataFrame, table_name:str ="uploaded_data") -> List[str]:
    chunks = []
    # table overview
    chunks.append(
        f"Table Name: {table_name}."
        f"The dataset contains {df.shape[0]} rows and {df.shape[1]} columns."
    )

    # columns metadata
    for col in df.columns:
        col_data = df.columns
        dtype = str(col_data.dtype)
        null_pct = df.isna().mean()*100

    column_chunk={
        f"Columns:{col}",
        f"Data type:{dtype}",
        f"Missing Values:{null_pct}"
    }

    if pd.api.types.is_numeric_dtype(col_data):
        column_chunk += (
            f"Min:{col_data.min()}",
            f"Max:{col_data.max()}",
            f"Average:{col_data.avg()}"
        )
    chunks.append(column_chunk)

    # sample rows
    sample_rows = df.head(3).to_dict(orient="records")
    chunks.append(
        f"sample rows: {sample_rows}"
    )
    # Ensure all chunks are strings (LangChain requirement)
    chunks = [str(chunk) for chunk in chunks]
    return chunks

