"""Functional and population annotation interfaces."""

from variantrank.annotation.input import VEPInputResult, export_vep_input
from variantrank.annotation.local_vep import (
    DEFAULT_CACHE_VERSION,
    DEFAULT_VEP_IMAGE,
    LocalVEPConfig,
    LocalVEPError,
    LocalVEPResult,
    format_command,
    run_local_vep,
)
from variantrank.annotation.vep import (
    VEPAnnotation,
    VEPClient,
    VEPRequestError,
    annotate_vcf,
    decode_variant_identifier,
    encode_variant_identifier,
    parse_vep_response,
)

__all__ = [
    "DEFAULT_CACHE_VERSION",
    "DEFAULT_VEP_IMAGE",
    "LocalVEPConfig",
    "LocalVEPError",
    "LocalVEPResult",
    "VEPAnnotation",
    "VEPClient",
    "VEPInputResult",
    "VEPRequestError",
    "annotate_vcf",
    "decode_variant_identifier",
    "encode_variant_identifier",
    "export_vep_input",
    "format_command",
    "parse_vep_response",
    "run_local_vep",
]
