import os

from pinecone import Pinecone


pc = Pinecone(os.environ.get("PINECONE_API_KEY", "")),
index = pc.index("quickstart")