# VariantRank REST API

The FastAPI service exposes health, model provenance, and ranked VCF inference.
OpenAPI documentation is served at `/docs` and `/redoc`.

## Configuration

| Environment variable | Required | Meaning |
|---|---:|---|
| `VARIANTRANK_MODEL_PATH` | For prediction | Persisted fitted or calibrated pipeline |
| `VARIANTRANK_THRESHOLD` | No | Classification threshold, default `0.5` |
| `VARIANTRANK_VEP_SERVER` | No | Ensembl VEP REST base URL |

The service starts without a configured model so health monitoring remains
available. In that state, `/model/info` reports `not_loaded` and `/predict`
returns HTTP 503.

## `GET /health`

Returns HTTP 200 while the API process is responsive:

```json
{"status": "ok"}
```

## `GET /model/info`

Reports the loaded artifact, feature contract, training timestamp, and active
threshold without exposing filesystem paths or internal metadata.

## `POST /predict`

Accepts one `multipart/form-data` field named `file`. Supported filenames end
in `.vcf` or `.vcf.gz`; the maximum upload size is 10 MiB. The request is
annotated through configured Ensembl VEP, transformed with the shared feature
contract, scored, and returned in descending score order.

```bash
curl --fail-with-body \
  --form "file=@variants.vcf;type=text/plain" \
  http://localhost:8000/predict
```

```json
{
  "model": "catboost",
  "threshold": 0.4761,
  "variants": [
    {
      "rank": 1,
      "variant_id": "17:7674220:C:T",
      "chrom": "17",
      "pos": 7674220,
      "ref": "C",
      "alt": "T",
      "gene": "TP53",
      "consequence": "missense_variant",
      "score": 0.947,
      "prediction": "pathogenic"
    }
  ]
}
```

Expected failures use HTTP 413 for oversized files, 415 for unsupported file
extensions, 422 for invalid VCF or inference contracts, 502 for an upstream VEP
failure, and 503 when no model is configured.

Uploaded and derived files live only in a request-scoped temporary directory
and are removed after the response is built. The API is intended for small
research batches, not whole-genome uploads or clinical decision support.
