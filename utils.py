from langchain.chains import RetrievalQAWithSourcesChain
from langchain.document_loaders import PyPDFLoader, TextLoader
from langchain.vectorstores import Pinecone

import chainlit as cl
from chainlit.types import AskFileResponse

from setup import index_name, text_splitter, namespaces, embeddings, pdfllm

import tiktoken

encoding = tiktoken.get_encoding("cl100k_base")
encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")


def process_file(file: AskFileResponse):
    """Read text files from user input"""
    import tempfile

    if file.type == "text/plain":
        Loader = TextLoader
    elif file.type == "application/pdf":
        Loader = PyPDFLoader

    tokens = 0
    with tempfile.NamedTemporaryFile() as tempfile:
        tempfile.write(file.content)
        loader = Loader(tempfile.name)
        documents = loader.load()
        docs = text_splitter.split_documents(documents)
        for i, doc in enumerate(docs):
            tokens += len(encoding.encode(doc.page_content))
            doc.metadata["source"] = f"source_{i}"
        return docs, tokens


def get_docsearch(file: AskFileResponse):
    """Save documents as token into Pinecone vector"""
    docs, tokens = process_file(file)

    # Save data in the user session
    cl.user_session.set("docs", docs)

    # Create a unique namespace for the file
    namespace = str(hash(file.content))

    if namespace in namespaces:
        docsearch = Pinecone.from_existing_index(
            index_name=index_name, embedding=embeddings, namespace=namespace
        )
    else:
        docsearch = Pinecone.from_documents(
            docs, embeddings, index_name=index_name, namespace=namespace
        )
        namespaces.add(namespace)

    return docsearch, tokens


async def create_pdf_agent():
    """Create a PDF reader chain for each uploaded document"""
    files = None
    while files is None:
        files = await cl.AskFileMessage(
            content="Welcome to the PDF reader mode! Upload a PDF or a text file",
            accept=["text/plain", "application/pdf"],
            max_files=1,
            max_size_mb=50,
            timeout=180,
        ).send()

    file = files[0]

    msg = cl.Message(content=f"Processing `{file.name}`...")
    await msg.send()

    # No async implementation in the Pinecone client, fallback to sync
    docsearch, tokens = await cl.make_async(get_docsearch)(file)

    agent = RetrievalQAWithSourcesChain.from_chain_type(
        llm=pdfllm,
        chain_type="stuff",
        retriever=docsearch.as_retriever(max_tokens_limit=4097),
        verbose=True,
    )

    # Let the user know that the system is ready
    msg.content = f"`{file.name}` processed."
    await msg.update()

    return agent, tokens


async def process_response(res, total_cost, mess_len):
    """Include sources in bot's response"""
    pdf_mode = cl.user_session.get("pdf_mode")
    if not pdf_mode:
        await cl.Message(
            content=f"{res['output']} \
                    \n*Cost: ${round(total_cost, 6)}* \
                    \n*Price breakdown: $0.002 x {mess_len} words (question and answer)*"
        ).send()
        return

    answer = res["answer"]
    sources = res["sources"].strip()
    source_elements = []

    # Get the documents from the user session
    docs = cl.user_session.get("docs")
    metadatas = [doc.metadata for doc in docs]
    all_sources = [m["source"] for m in metadatas]

    if sources:
        found_sources = []

        # Add the sources to the message
        for source in sources.split(","):
            source_name = source.strip().replace(".", "")
            # Get the index of the source
            try:
                index = all_sources.index(source_name)
            except ValueError:
                continue
            text = docs[index].page_content
            found_sources.append(source_name)
            # Create the text element referenced in the message
            source_elements.append(cl.Text(content=text, name=source_name))

        if found_sources:
            answer += f"\nSources: {', '.join(found_sources)}"
        else:
            answer += "\nNo sources found"

    answer += f"\n*Cost: ${round(total_cost, 6)}* \
                \n*Price breakdown: $0.5 x 1 file + $0.002 x {mess_len} words (question and answer)*"

    await cl.Message(content=answer, elements=source_elements).send()
