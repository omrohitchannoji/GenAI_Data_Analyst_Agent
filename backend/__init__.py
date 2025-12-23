from rag.context_builder import build_dataset_context
from rag.vector_store import DatasetVectorStore
import pandas as pd

df = pd.read_csv("employee_attrition.csv")

chunks = build_dataset_context(df)

store = DatasetVectorStore()
store.store_context(chunks)

print("Dataset context stored successfully!")
