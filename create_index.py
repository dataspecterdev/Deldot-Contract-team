"""
Creates the vector index in the OpenSearch Serverless collection.
Uses opensearch-py with AWS4Auth for proper AOSS authentication.
"""
from opensearchpy import OpenSearch, RequestsHttpConnection
from requests_aws4auth import AWS4Auth
import boto3

# Get credentials from the current session
session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()

# AWS4Auth for OpenSearch Serverless (service name is 'aoss')
awsauth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    "us-east-1",
    "aoss",
    session_token=credentials.token
)

# Connect to the OpenSearch Serverless collection
host = "s706j4a490o2w56i0l9h.us-east-1.aoss.amazonaws.com"
client = OpenSearch(
    hosts=[{"host": host, "port": 443}],
    http_auth=awsauth,
    use_ssl=True,
    verify_certs=True,
    connection_class=RequestsHttpConnection,
    timeout=60
)

# Define the vector index
index_name = "bedrock-knowledge-base-default-index"
index_body = {
    "settings": {
        "index": {
            "knn": True,
            "knn.algo_param.ef_search": 512
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
                    "parameters": {}
                }
            },
            "AMAZON_BEDROCK_TEXT_CHUNK": {
                "type": "text",
                "index": True
            },
            "AMAZON_BEDROCK_METADATA": {
                "type": "text",
                "index": False
            }
        }
    }
}

# Create the index
try:
    response = client.indices.create(index=index_name, body=index_body)
    print(f"Index created successfully: {response}")
except Exception as e:
    print(f"Error: {e}")
