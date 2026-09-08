# ClinVar dataset build summary

Build date: 2026-09-08
Genome assembly: GRCh38
Source: [NCBI ClinVar `variant_summary.txt.gz`](https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz)

## Source snapshot

| Property | Value |
|---|---|
| Compressed size | 442,645,117 bytes |
| Published MD5 | `17ec6902042d1c5d9f87c2d64eb95a69` |
| Verified MD5 | `17ec6902042d1c5d9f87c2d64eb95a69` |
| SHA-256 | `0946d1661f102f39e4a5b37db1e04be2990478eb547cceb21ffb0ba23c7ee78f` |
| Source rows | 9,050,979 |
| GRCh38 rows | 4,491,757 |

## Curated datasets

| Dataset | Pathogenic | Benign | Total |
|---|---:|---:|---:|
| Dataset A — all unambiguous labels | 297,360 | 1,336,616 | 1,633,976 |
| Dataset B — high confidence | 85,098 | 287,975 | 373,073 |

Dataset B retains review statuses `criteria provided, multiple submitters, no
conflicts`, `reviewed by expert panel`, and `practice guideline`.

## Filtering audit

| Stage | Rows removed |
|---|---:|
| Non-GRCh38 assembly | 4,559,222 |
| Unsupported variant type | 126,753 |
| Ambiguous or out-of-scope label | 2,727,179 |
| Missing gene | 358 |
| Invalid VCF coordinates or alleles | 3,489 |
| Non-canonical chromosome | 1 |
| Conflicting normalized variants | 0 |
| Duplicate rows | 1 |

The filter counts plus 1,633,977 eligible pre-deduplication rows equal the
4,491,757 GRCh38 input rows. After one duplicate removal, Dataset A contains
1,633,976 unique normalized variant keys.

The complete transformation rules are defined in the
[ClinVar training data contract](../../docs/data-contract.md).
