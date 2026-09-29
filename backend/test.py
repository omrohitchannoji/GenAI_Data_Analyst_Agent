import pandas as pd
from rag.context_builder import build_dataset_context
from rag.langchain_rag import build_vector_store

df = pd.read_csv("emplyee_attrition.csv")
chunks = build_dataset_context(df)

vectorstore = build_vector_store(chunks)

print("Vector store created")
