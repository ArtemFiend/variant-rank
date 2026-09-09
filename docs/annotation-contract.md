# Ensembl VEP annotation contract

VariantRank uses Ensembl Variant Effect Predictor as the boundary between
normalized genomic variants and biological features. The flattened schema and
feature builder form the shared contract for upcoming annotated training and
VCF inference stages.

## Supported execution modes

| Mode | Intended workload | Interface |
|---|---|---|
| Ensembl REST | Small VCF files and integration checks | `variantrank annotate-vcf` |
| Local VEP cache | Dataset-scale annotation | `variantrank annotate-local` |

The public REST service is deliberately limited to batches of at most 200
variants. It is not used to annotate the full ClinVar training snapshot.

## Offline VEP execution

The local runner uses the pinned multi-architecture image
`ensemblorg/ensembl-vep:release_116.1` with the matching Ensembl release 116
GRCh38 cache. The cache is external data and is not stored in Git.

Install the cache and reference FASTA once:

```bash
mkdir -p data/external/vep
docker run --rm -it \
  -v "$PWD/data/external/vep:/data" \
  ensemblorg/ensembl-vep:release_116.1 \
  INSTALL.pl -c /data -a cf -s homo_sapiens -y GRCh38
```

Export the curated ClinVar Parquet to a streaming, compressed VCF without
loading the full dataset into memory:

```bash
uv run variantrank export-vep-input
```

Variant IDs are URL-safe Base64 encodings of the canonical variant key. This
avoids VEP parser ambiguity while keeping every annotation join reversible.
The export is written atomically and reused only when its own checksum and the
source Parquet checksum match the sidecar manifest.

Preview the exact offline command without requiring the cache:

```bash
uv run variantrank annotate-local tests/fixtures/example.vcf --dry-run
```

Run annotation after the cache is installed:

```bash
uv run variantrank annotate-local tests/fixtures/example.vcf \
  --cache-dir data/external/vep \
  --output-path data/annotated/example.vep.jsonl
```

For the full Dataset A export, pass
`data/interim/clinvar.vep.vcf.gz` as the input instead of the fixture.

Convert the raw line-delimited VEP JSON to the typed annotation contract:

```bash
uv run variantrank parse-vep-output data/annotated/vep.jsonl
```

The parser streams JSON records into compressed Parquet row groups, restores
canonical variant keys from the safe VCF identifiers, preserves missing
frequency values, and writes its own checksum manifest. Malformed JSON or an
empty annotation result never replaces a previously valid Parquet output.

The runner writes to a partial file, promotes it only after a successful VEP
exit, and stores a sidecar manifest containing the input/output checksums,
container image, cache version, full argv, runtime, and annotation options. A
subsequent invocation is skipped only when the input checksum, configuration,
output checksum, and manifest all match. `--force` explicitly bypasses this
cache check.

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
