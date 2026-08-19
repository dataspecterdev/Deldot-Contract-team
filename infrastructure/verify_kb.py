"""
Verifies the Bedrock Knowledge Base after ingestion.

Checks, per probe query:
  - which source files the retrieved chunks came from
  - whether any chunk is returned twice (duplicate indexing)
  - whether the top hit is the expected CC requirement file (no cross-file bleed)
"""
import boto3
from botocore.config import Config

KB_ID = "7BKLBOJA7F"
REGION = "us-east-1"

client = boto3.client(
    "bedrock-agent-runtime",
    region_name=REGION,
    config=Config(retries={"max_attempts": 5, "mode": "adaptive"}),
)

PROBES = [
    ("What is the required proposal guaranty percentage for bid bonds?", "CC-02"),
    ("liquidated damages daily charge for a $3,250,000 contract", "CC-17"),
    ("order of precedence when contract documents conflict", "CC-10"),
    ("record retention period for audit after final payment", "CC-13"),
    ("percentage of work the prime must perform with its own organization", "CC-14"),
    ("must FHWA-1273 be physically incorporated or referenced", "CC-01"),
]


def source_name(result):
    uri = result.get("location", {}).get("s3Location", {}).get("uri", "")
    return uri.rsplit("/", 1)[-1] or uri


def probe(query, expected_prefix):
    response = client.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": 5}},
    )
    results = response.get("retrievalResults", [])

    files = [source_name(r) for r in results]
    texts = [r.get("content", {}).get("text", "") for r in results]

    duplicates = len(texts) != len(set(texts))
    top_file = files[0] if files else "(none)"
    top_ok = top_file.startswith(expected_prefix)

    print(f"\nQuery: {query}")
    print(f"  expected top source : {expected_prefix}*")
    print(f"  actual top source   : {top_file}  {'OK' if top_ok else 'MISMATCH'}")
    print(f"  duplicate chunks    : {'YES' if duplicates else 'no'}")
    print(f"  sources returned    : {files}")
    if results:
        score = results[0].get("score")
        print(f"  top score           : {score}")
        print(f"  top chunk preview   : {texts[0][:160].replace(chr(10), ' ')}...")

    return top_ok, duplicates


if __name__ == "__main__":
    all_top_ok = True
    any_duplicates = False
    for query, expected in PROBES:
        top_ok, duplicates = probe(query, expected)
        all_top_ok = all_top_ok and top_ok
        any_duplicates = any_duplicates or duplicates

    print("\n" + "=" * 60)
    print(f"top-hit correct on all probes : {'YES' if all_top_ok else 'NO'}")
    print(f"duplicate chunks detected     : {'YES' if any_duplicates else 'NO'}")
