# Local VEP environment summary

Installation date: 2026-09-09

| Property | Value |
|---|---|
| VEP image | `ensemblorg/ensembl-vep:release_116.1` |
| Image digest | `sha256:6972667883d89b9fa55e5cbe94f1b4c259ebc6bbd178310cef78f617e055eb75` |
| Cache release | 116 |
| Assembly | GRCh38.p14 |
| Gene build | GENCODE 50 |
| gnomAD exomes | v4.1 |
| gnomAD genomes | v4.1 |
| dbSNP | 156 |
| Compressed cache bytes | 27,644,657,162 |
| Published BSD checksum | `56036 26996736` |
| Installed cache size | approximately 26 GiB |

The downloaded archive matched its published byte count, passed `gzip -t`, and
matched the Ensembl `CHECKSUMS` entry before extraction. The archive was removed
after a successful offline smoke test; the installed cache remains under the
ignored `data/external/vep/` directory.

## Offline smoke test

The decomposed fixture contains three alternate alleles. Pinned VEP release 116
produced three allowlisted tabular records, and the streaming converter produced
three typed Parquet rows:

| Variant | Gene | Consequence | Impact |
|---|---|---|---|
| `17:7674220:C:T` | TP53 | missense_variant | MODERATE |
| `13:32340301:C:T` | BRCA2 | synonymous_variant | LOW |
| `13:32340301:C:G` | BRCA2 | missense_variant | MODERATE |

## Dataset A annotation run

The complete curated Dataset A was annotated offline after removing source rows
whose reference and alternate alleles were identical. The VEP input, raw output,
and typed output contain exactly the same number of unique variants.

| Property | Value |
|---|---|
| Dataset A variants | 1,633,439 |
| Excluded no-change ClinVar rows | 538 |
| VEP records | 1,633,439 |
| Typed Parquet rows | 1,633,439 |
| Annotation coverage | 100% |
| VEP runtime | 1,216.88 seconds |
| VEP input SHA-256 | `a653b6c9a168c402aacdbe7e759ce591fc096256d6185d5cb841516f05975cb2` |
| Allowlisted TSV SHA-256 | `fc06d9431b16b6f011ad639587c4ac8aaaeecf0968143f512629c48c9ec42f6a` |
| Typed Parquet SHA-256 | `dff48c45ea6b903e369f2432fa7c938c18b357a0e507a571db80052399b07fd4` |

VEP emitted three internal Perl warnings while calculating protein coordinates
for complex alleles. The process exited successfully, retained one annotation
for every input variant, and the converter represents unknown protein-position
boundaries as null values.

## Leakage boundary

The human VEP cache includes a September 2025 ClinVar snapshot among its
co-located variant metadata. VariantRank requests an explicit tabular field
allowlist that excludes clinical significance, phenotype, disease, and ClinVar
synonym fields before data reaches disk. The typed parser repeats this boundary;
only transcript consequences and population frequencies enter model features.
