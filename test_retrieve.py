"""Quick check that the Bedrock Knowledge Base returns relevant reference text."""
import boto3

client = boto3.client("bedrock-agent-runtime", region_name="us-east-1")

QUERIES = [
    "proposal guaranty 10 percent of total bid price",
    "liquidated damages daily charge for contract value between $2,000,000 and $5,000,000",
    "records retained three years after final payment audit",
]

for q in QUERIES:
    resp = client.retrieve(
        knowledgeBaseId="7BKLBOJA7F",
        retrievalQuery={"text": q},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 2}},
    )
    print(f"\n=== QUERY: {q}")
    for r in resp["retrievalResults"]:
        uri = r["location"]["s3Location"]["uri"].split("/")[-1]
        print(f"  [{r['score']:.3f}] {uri}: {r['content']['text'][:160].replace(chr(10), ' ')}...")
