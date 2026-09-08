# VariantRank

End-to-end machine-learning system for prioritizing potentially pathogenic
genetic variants from VCF files using functional, population, and genomic
annotations.

> [!WARNING]
> VariantRank is a research and educational project. It is not intended for
> diagnosis, treatment decisions, or other clinical use.

## Status

VariantRank is under active development. The initial specification is available
in [`VariantRank_TZ.md`](VariantRank_TZ.md).

## Planned pipeline

```text
VCF
 → parsing and normalization
 → functional and population annotation
 → feature engineering
 → calibrated pathogenicity scoring
 → ranked variants
 → CSV / JSON / HTML report and REST API
```

## Core principles

- reproducible, CPU-first workflows;
- explicit safeguards against label leakage;
- random and gene-aware validation;
- calibrated probabilities and ranking metrics;
- explainable predictions;
- tested CLI and API interfaces.

## License

This project is licensed under the MIT License. See [`LICENSE`](LICENSE).
