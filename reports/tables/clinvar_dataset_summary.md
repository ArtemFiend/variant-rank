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

## VEP input export

Dataset A was streamed to a compressed GRCh38 VCF for offline annotation.

| Property | Value |
|---|---|
| Variants | 1,633,976 |
| Compressed size | 16,091,000 bytes |
| Source Parquet SHA-256 | `27a44446962bc49cdaa40fca89add23f6872645ffff09100162b819164fd0830` |
| VCF.GZ SHA-256 | `86adcef8c57ab9c8cce23dad75b3cc318e488fe5ecadb2ba62b40ecc8300ddec` |
| Variant ID encoding | URL-safe Base64 of `chrom:pos:ref:alt` |

The generated VCF and manifest remain untracked data artifacts. They can be
recreated with `uv run variantrank export-vep-input`; a repeated invocation
returns a checksum-validated cache hit.

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
