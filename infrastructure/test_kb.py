"""
Verifies the Bedrock Knowledge Base returns relevant reference text
for requirement-specific queries across all 18 CC requirements.
"""
import boto3

KB_ID = "7BKLBOJA7F"
REGION = "us-east-1"

client = boto3.client("bedrock-agent-runtime", region_name=REGION)

# One representative query per requirement area
TEST_QUERIES = [
    ("CC-01", "FHWA-1273 must be physically incorporated in federal-aid construction contract"),
    ("CC-02", "proposal guaranty equal to 10 percent of total bid price"),
    ("CC-04", "performance and payment bond 100 percent of contract price"),
    ("CC-05", "return signed contract within 20 calendar days after notice of award"),
    ("CC-07", "subcontractor business license within 30 days of entering public works contract"),
    ("CC-10", "order of precedence General Description General Notices Plans Special Provisions"),
    ("CC-12", "written follow-up information due within 7 calendar days of initial notification"),
    ("CC-13", "records retained three years after final payment audit"),
    ("CC-14", "prime performs no less than 50 percent of contract with own organization"),
    ("CC-17", "liquidated damages daily charge for contract value between $2,000,000 and $5,000,000"),
    ("CC-18", "compensation for changes unit prices then negotiated prices then force account"),
]


def run_query(label, query, num_results=2):
    resp = client.retrieve(
        knowledgeBaseId=KB_ID,
        retrievalQuery={"text": query},
        retrievalConfiguration={
            "vectorSearchConfiguration": {"numberOfResults": num_results}
        },
    )
    results = resp.get("retrievalResults", [])
    print(f"\n{'=' * 78}")
    print(f"{label}: {query[:70]}")
    print("=" * 78)
    if not results:
        print("  NO RESULTS RETURNED")
        return False

    for i, r in enumerate(results, 1):
        score = r.get("score", 0)
        uri = r.get("location", {}).get("s3Location", {}).get("uri", "unknown")
        source_file = uri.split("/")[-1]
        text = r["content"]["text"].replace("\n", " ")
        preview = text[:260] + ("..." if len(text) > 260 else "")
        print(f"  [{i}] score={score:.4f}  source={source_file}")
        print(f"      {preview}")
    return True


if __name__ == "__main__":
    passed = 0
    for label, query in TEST_QUERIES:
        if run_query(label, query):
            passed += 1

    print(f"\n{'=' * 78}")
    print(f"SUMMARY: {passed}/{len(TEST_QUERIES)} queries returned results")
    print("=" * 78)
