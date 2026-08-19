"""
Creates the vector index in the OpenSearch Serverless collection backing the
Bedrock Knowledge Base. Run once, after the collection reaches ACTIVE.

Field names and dimension must match infrastructure/storage-config.json and the
Titan Text Embeddings V2 output size (1024).
"""
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3

COLLECTION_HOST = "s706j4a490o2w56i0l9h.us-east-1.aoss.amazonaws.com"
REGION = "us-east-1"
INDEX_NAME = "bedrock-knowledge-base-default-index"

session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()

awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    "aoss",
    session_token=credentials.token,
)

client = OpenSearch(
    hosts=[{"host": COLLECTION_HOST, "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=60,
)

index_body = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 512,
        }
    },
    "mappings": {
        "properties": {
            "bedrock-knowledge-base-default-vector": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "engine": "faiss",
                    "space_type": "l2",
                    "name": "hnsw",
                    "parameters": {},
                },
            },
            "AMAZON_BEDROCK_TEXT_CHUNK": {"type": "text", "index": True},
            "AMAZON_BEDROCK_METADATA": {"type": "text", "index": False},
        }
    },
}

if __name__ == "__main__":
    try:
        response = client.indices.create(index=INDEX_NAME, body=index_body)
        print(f"Index created: {response}")
    except Exception as exc:
        print(f"Error: {exc}")
