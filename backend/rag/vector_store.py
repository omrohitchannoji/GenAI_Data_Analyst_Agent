from typing import List
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings

class DatasetVectorStore:
    def __init__ (self, persist_dir:str = "vector_store"):
        """
        Handles embedding and storage of dataset context
        using a vector database.
        """
        self.embedder = SentenceTransformer("all-MiniLM-L6-v2")

        self.client = chromadb.Client(
            Settings (persist_directory = persist_dir)
        )
        self.collection = self.client.get_or_create_collection(
            name="dataset_context"
        )

    def store_dataset_context(self, chunks:List[str]):
        """
        Converts text chunks into embeddings
        and stores them in the vector database.
        """

        emdeddings = self.embedder.encode(chunks).tolist()

        ids = [f"chunks_{i}" for i in range(len(chunks))]

        self.collection.add(
            documents=chunks,
            embeddings=emdeddings,
            ids=ids
        )
        self.client.persists()