"""Functional and population annotation interfaces."""

from variantrank.annotation.vep import (
    VEPAnnotation,
    VEPClient,
    VEPRequestError,
    annotate_vcf,
    parse_vep_response,
)

__all__ = [
    "VEPAnnotation",
    "VEPClient",
    "VEPRequestError",
    "annotate_vcf",
    "parse_vep_response",
]
