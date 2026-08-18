# Infrastructure Records — Contract Clause Risk Flagging

Record of the AWS resources backing the reference RAG layer, and the order they
must be created in. Every config file referenced here lives in this folder, so the
stack can be rebuilt from scratch without re-deriving any values.

## Deployed resources

| Resource | Identifier |
|---|---|
| Region | `us-east-1` |
| Account | `777761317151` |
| S3 bucket (reference sources) | `deldot-contract-references-777761317151` |
| S3 prefix | `sources/` (18 objects) |
| KB service role | `arn:aws:iam::777761317151:role/DelDOTRef` |
| OpenSearch Serverless collection | `deldot-kb-vectors` / id `s706j4a490o2w56i0l9h` |
| Collection ARN | `arn:aws:aoss:us-east-1:777761317151:collection/s706j4a490o2w56i0l9h` |
| Collection endpoint | `https://s706j4a490o2w56i0l9h.us-east-1.aoss.amazonaws.com` |
| Vector index | `bedrock-knowledge-base-default-index` |
| Knowledge Base | `DeldotContractReferences` / id `7BKLBOJA7F` |
| Data source | `DeldotReferenceSources` / id `FF8HQPONEH` |
| Embedding model | `amazon.titan-embed-text-v2:0` (1024 dimensions) |

### AOSS security policies

| Policy | Name | Type |
|---|---|---|
| Encryption | `deldot-kb-encryption` | `encryption` (AWS-owned key) |
| Network | `deldot-kb-network` | `network` (public, IAM-gated) |
| Data access | `deldot-kb-access` | `data` |

### IAM policies on `DelDOTRef`

| Policy name | Grants | File |
|---|---|---|
| `BedrockModelInvocation` | `bedrock:InvokeModel` on Titan V2 | `iam/model-policy.json` |
| `S3DataSourceAccess` | `s3:GetObject`, `s3:ListBucket` on the bucket | `iam/s3-policy.json` |
| `AOSSAccess` | `aoss:APIAccessAll` on the collection | `iam/aoss-policy.json` |

`AOSSAccess` is also attached to `WSParticipantRole` so the index can be created
from a local session.

## Chunking configuration

`vector-ingestion-config.json` — SEMANTIC, `maxTokens: 600`, `bufferSize: 0`,
`breakpointPercentileThreshold: 95`.

Both values are deliberate:

- `bufferSize: 0` — a non-zero buffer pulls neighbouring sentences into each
  chunk, which made one CC section's text bleed into another section's retrieval
  results. Zero keeps each requirement's text self-contained.
- `maxTokens: 600` — large enough to hold Table 108.9-1 (13 rows of liquidated
  damages rates) in a single chunk. At 300 tokens the table split across chunks
  and a lookup could return only part of the rate schedule.

Chunking cannot be changed on an existing data source. Changing it means deleting
and recreating the data source, then re-ingesting.

## Rebuild order

Order matters — creating the KB before the vector index exists fails with an
opaque storage-configuration error.

1. `aws s3 mb s3://deldot-contract-references-777761317151`
2. `aws s3 sync Contract_Clause_Risk_Flagging/Sources s3://deldot-contract-references-777761317151/sources/`
3. `aws iam create-role --role-name DelDOTRef --assume-role-policy-document file://iam/trust-policy.json`
4. Attach `iam/model-policy.json`, `iam/s3-policy.json`, `iam/aoss-policy.json` to the role
5. Create AOSS policies from `opensearch/encryption-policy.json`, `opensearch/network-policy.json`, `opensearch/data-access-policy.json`
6. `aws opensearchserverless create-collection --name deldot-kb-vectors --type VECTORSEARCH`, wait for `ACTIVE`
7. `python opensearch/create_index.py`
8. `aws bedrock-agent create-knowledge-base --knowledge-base-configuration file://kb-config.json --storage-configuration file://storage-config.json`
9. `aws bedrock-agent create-data-source --data-source-configuration file://datasource-config.json --vector-ingestion-configuration file://vector-ingestion-config.json`
10. `aws bedrock-agent start-ingestion-job`, poll `get-ingestion-job` until `COMPLETE`
11. `python verify_kb.py`

IAM and AOSS data-access policies are eventually consistent. Steps 3-7 may need a
retry with backoff if they fail with `NoSuchEntity` or `403 Forbidden`.

## Verification

`verify_kb.py` probes six requirement areas and reports, per probe, the source
file of each retrieved chunk, whether any chunk was returned twice, and whether
the top hit is the expected CC file.

Last run: top hit correct on all 6 probes, no duplicate chunks.
Last ingestion: 18 scanned, 18 indexed, 0 failed, 0 skipped.

Two scripts predate `verify_kb.py` and are kept as lighter spot checks:
`test_kb.py` (one query per requirement area) and `test_retrieve.py` (three
queries with scores).

## Known history

The index originally held two data sources (`BZ9FHGXV7F` at 300/buffer 0 and
`649NNUDWJ4` at 600/buffer 1) both pointing at the same `sources/` prefix. Every
document was therefore embedded twice into one index, and the buffered source
mixed adjacent sections together — retrieval returned duplicate and
cross-contaminated chunks. Both were deleted and replaced by the single
`FF8HQPONEH` data source above.
