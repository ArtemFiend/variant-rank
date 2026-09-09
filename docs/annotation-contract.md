# Ensembl VEP annotation contract

VariantRank uses Ensembl Variant Effect Predictor as the boundary between
normalized genomic variants and biological features. The flattened schema and
feature builder form the shared contract for upcoming annotated training and
VCF inference stages.

## Supported execution modes

| Mode | Intended workload | Interface |
|---|---|---|
| Ensembl REST | Small VCF files and integration checks | `variantrank annotate-vcf` |
| Local VEP cache | Dataset-scale annotation | Planned batch runner |

The public REST service is deliberately limited to batches of at most 200
variants. It is not used to annotate the full ClinVar training snapshot.

## Output schema

| Field | Type | Description |
|---|---|---|
| `variant` | string | Normalized `chrom:pos:ref:alt` key |
| `gene`, `gene_id` | nullable string | Gene symbol and Ensembl stable ID |
| `transcript` | nullable string | Selected Ensembl transcript |
| `consequence` | string | Sequence Ontology consequence terms joined with `&` |
| `impact`, `biotype` | nullable string | VEP impact and transcript biotype |
| `exon`, `intron` | nullable string | Transcript-relative location |
| `protein_position` | nullable integer | Protein residue position |
| `amino_acids`, `codons` | nullable string | Protein and codon change |
| `canonical` | boolean | Ensembl canonical transcript flag |
| `mane_select` | nullable string | MANE Select transcript identifier |
| `allele_frequency` | nullable float | Maximum overall reported AF |
| `population_max_af` | nullable float | Maximum supported population AF |
| `afr_af`, `amr_af`, `eas_af`, `nfe_af`, `sas_af` | nullable float | Population AF values |
| `rare_variant_flag` | nullable boolean | `population_max_af <= 0.01`; null when AF is unavailable |

Missing frequency remains null rather than being converted to zero. This keeps
“not observed” distinct from “not available” and allows the model pipeline to
impute missing values explicitly.

## Transcript selection

REST requests enable VEP `pick`, MANE, and canonical annotations. If an endpoint
returns multiple transcript consequences, VariantRank deterministically prefers
the record marked as picked, then MANE Select, then canonical. Intergenic
variants retain the stable fallback consequence `intergenic_variant`.

## Provenance

Each Parquet output has an adjacent `*.metadata.json` file containing:

- source VCF path;
- source VCF SHA-256 checksum;
- genome assembly;
- exact VEP endpoint and enabled options;
- UTC creation time;
- row count;
- ordered output schema.

The annotation layer never reads ClinVar clinical significance or target fields.
