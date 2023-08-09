from langchain import OpenAI
from langchain import OpenAI, SerpAPIWrapper
from langchain.agents import initialize_agent, Tool, AgentType
from langchain.chat_models import ChatOpenAI

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.embeddings.openai import OpenAIEmbeddings

import os
import pinecone
from dotenv import load_dotenv

load_dotenv()

# Initialize large language models
searchllm = OpenAI(model_name="text-davinci-002", temperature=0, streaming=True)
pdfllm = ChatOpenAI(
    model_name="gpt-3.5-turbo",
    temperature=0,
    # max_tokens=100,
    streaming=True,
)

# Initialize search tool
search = SerpAPIWrapper()
tools = [
    Tool(
        name="Search",
        func=search.run,
        description="useful for when you need to answer questions about current events. You should ask targeted questions",
    )
]
search_agent = initialize_agent(
    tools, searchllm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True
)

# Initialize Pinecone
pinecone.init(
    api_key=os.environ["PINECONE_API_KEY"],
    environment=os.environ["PINECONE_ENV"],
)

index_name = "langchain-demo"
embedding_size = 1536
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
namespaces = set()

if index_name not in pinecone.list_indexes():
    # if does not exist, create index
    pinecone.create_index(index_name, dimension=embedding_size, metric="cosine")


__all__ = [
    "pdfllm",
    "search_agent",
    "index_name",
    "embedding_size",
    "text_splitter",
    "embeddings",
    "namespaces",
]
