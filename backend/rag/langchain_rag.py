from langchain_core.documents import Document
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from typing import List

def build_vector_store(chunks :List[str], persist_dir = "vector_store"):
    """
    Takes dataset context chunks and stores them
    in a LangChain-compatible vector database.
    """
    documents = [Document(page_content=chunk) for chunk in chunks]

    embeddings = HuggingFaceEmbeddings(model_name = "sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = Chroma.from_documents(
        documents = documents,
        embedding=embeddings,
        persist_directory=persist_dir
    )

    vectorstore.persist()
    return vectorstore

def retrieve_context(question:str, vector_store, K:int=3) -> str:
    """
    Retrieves top-k relevant dataset context chunks for a question.
    """
    retriever = vector_store.as_retrieve(search_kwargs={"k":k})
    docs = retriever.get_relevant_documents(question)
    return "\n".join([doc.page_content for doc in docs])