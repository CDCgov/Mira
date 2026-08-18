from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal, Dict, Any, Union
import polars as pl

# Import schema validator
from .schema_validator import (
    validate_tbl,
    experiment_types,
    sample_types,
    sample_status,
    sc2_primers,
    rsv_primers,
    irma_modules,
    assembly_status,
    assembly_pa_schema,
    ont_samplesheet_pa_schema,
    illumina_samplesheet_pa_schema,
)

# Pre-compute Literal types at module level to avoid class-body name collisions
_ExperimentTypes  = Literal[tuple(experiment_types)]
_SampleTypes      = Literal[tuple(sample_types)]
_SampleStatus    = Literal[tuple(sample_status)]
_Sc2Primers      = Literal[tuple(sc2_primers)]
_RsvPrimers      = Literal[tuple(rsv_primers)]
_IrmaModules     = Literal[tuple(irma_modules)]
_AssemblyStatus  = Literal[tuple(assembly_status)]

# Allowed FASTQ file MIME types
ALLOWED_FASTQ_TYPES = {"application/gzip", "application/x-gzip"}

# ------ ASSEMBLY INFO MODEL ----------
class AssemblyInfo(BaseModel):
    run_name: str = Field("ont_tiny_test_run", description="Name of the sequencing run.")
    experiment_type: _ExperimentTypes = Field(..., description="Type of sequencing experiments.")
    sc2_primer: Optional[Union[_Sc2Primers, Literal[""]]] = Field("", description="A SC2 primer if experiment type is SC2.")
    rsv_primer: Optional[Union[_RsvPrimers, Literal[""]]] = Field("", description="A RSV primer if experiment type is RSV.")
    subsample_reads: int = Field(0, description="Number of reads to subsample for MIRA assembly.")
    custom_primers: bool = Field(False, description="Whether to use a custom primer file for assembly.")
    primer_kmer_len: Optional[int] = Field(None, description="K-mer length for primer trimming. Default is 0 (no trimming).")
    primer_restrict_window: Optional[int] = Field(None, description="Window size for primer trimming. Default is 0 (no trimming).")
    irma_module: Optional[Union[_IrmaModules, Literal[""]]] = Field("", description="An IRMA module to use for assembly.")
    custom_irma_config: bool = Field(False, description="Whether to use a custom IRMA config file for assembly.")
    custom_qc_settings: bool = Field(False, description="Whether to use custom QC settings for assembly.")
    parquet_files: bool = Field(False, description="Whether to generate parquet files for the assembly outputs.")
    nextclade: bool = Field(True, description="Whether to run NextClade for lineage assignment.")
    assembly_status: _AssemblyStatus = Field(..., description="Assembly status for the sequencing run")
    @model_validator(mode='after')
    def validate_against_assembly_schema(self) -> 'AssemblyInfo':
        tbl = pl.DataFrame([self.model_dump()])
        validate_tbl(tbl, assembly_pa_schema, "assembly")
        return self

# ------ DB ASSEMBLY INFO MODEL ----------
class DBAssemblyInfo(AssemblyInfo):
    assembly_id: int = Field(..., description="Assembly ID.")

# ------ ONT SAMPLESHEET MODEL ----------
class OntSamplesheet(BaseModel):
    barcode: str = Field("barcode01", description="ONT barcode identifier (e.g. barcode01).")
    sample_id: str = Field("sample_1", description="Sample ID.")
    sample_type: _SampleTypes = Field("Test", description="Sample type.")
    single_end: bool = Field(True, description="Whether the reads are single-end or paired-end. Always true for ONT.")
    fastq: str = Field("AMx369_pass_barcode1_143deb51_0.fastq.gz", description="FASTQ filename.")
    status: _SampleStatus = Field("Keep", description="Whether to keep or exclude the sample.")
    @model_validator(mode='after')
    def validate_against_samplesheet_schema(self) -> 'OntSamplesheet':
        tbl = pl.DataFrame([self.model_dump()])
        validate_tbl(tbl, ont_samplesheet_pa_schema, "ont_samplesheet")
        return self
    
# ------ DB ONT SAMPLESHEET MODEL ----------
class DBOntSamplesheet(OntSamplesheet):
    assembly_id: int = Field(..., description="Assembly ID.")

# ------ ILLUMINA SAMPLESHEET MODEL ----------
class IlluminaSamplesheet(BaseModel):
    sample_id: str = Field("sample_1", description="Sample ID.")
    sample_type: _SampleTypes = Field("Test", description="Sample type.")
    single_end: bool = Field(False, description="Whether the reads are single-end or paired-end. Always false for Illumina.")
    fastq_1: str = Field("sample_1_R1.fastq.gz", description="R1 FASTQ filename.")
    fastq_2: str = Field("sample_1_R2.fastq.gz", description="R2 FASTQ filename.")
    status: _SampleStatus = Field("Keep", description="Whether to keep or exclude the sample.")
    @model_validator(mode='after')
    def validate_against_samplesheet_schema(self) -> 'IlluminaSamplesheet':
        tbl = pl.DataFrame([self.model_dump()])
        validate_tbl(tbl, illumina_samplesheet_pa_schema, "illumina_samplesheet")
        return self
    
# ------ DB ILLUMINA SAMPLESHEET MODEL ----------
class DBIlluminaSamplesheet(IlluminaSamplesheet):
    assembly_id: int = Field(..., description="Assembly ID.") 

# ------  RUN REQUEST (REQUIRED: RUN NAME, EXPERIMENT TYPE) ----------
class RunRequest(BaseModel):
    run_name: str = Field(..., description="Name of the sequencing run.")
    experiment_type: _ExperimentTypes = Field(..., description="Type of sequencing experiment.")

# ------ RUN RESPONSE ----------
class RunResponse(BaseModel):
    run_info: Optional[List[DBAssemblyInfo]] = Field(None, description="Assembly information for the sequencing run.")

# ------  RUN STATUS REQUEST (REQUIRED: RUN NAME, EXPERIMENT TYPE, PID) ----------
class RunStatusRequest(RunRequest):
    pid: int = Field(..., description="Process ID of the running MIRA assembly pipeline.")

# ------  TASK LOG REQUEST (REQUIRED: RUN NAME, EXPERIMENT TYPE, HASH) ----------
class TaskLogRequest(RunRequest):
    hash: str = Field(..., description="Execution-trace hash of the task whose error log to retrieve (e.g. '9f/df6545').")

# ------  DOWNLOAD FASTA REQUEST (REQUIRED: RUN NAME, EXPERIMENT TYPE, KEY) ----------
class DownloadFastaRequest(RunRequest):
    key: str = Field(..., description="Key for the Nextclade FASTA file to download. If not provided, the first available key will be used.")

# ------  DELETE SAMPLE REQUEST (REQUIRED: RUN NAME, EXPERIMENT TYPE, SAMPLE ID) ----------
class DeleteSampleRequest(RunRequest):
    sample_id: str = Field(..., description="Sample ID of the sample to remove from the samplesheet.")
    fastq: Optional[str] = Field(None, description="FASTQ filename identifying the row to remove (required for ONT experiments).")
    fastq_1: Optional[str] = Field(None, description="R1 FASTQ filename identifying the row to remove (required for Illumina experiments).")
    fastq_2: Optional[str] = Field(None, description="R2 FASTQ filename identifying the row to remove (required for Illumina experiments).")

# ------  RENAME RUN REQUEST (REQUIRED: RUN NAME, EXPERIMENT TYPE, NEW RUN NAME) ----------
class RenameRunRequest(RunRequest):
    new_run_name: str = Field(..., description="New name for the sequencing run.")

# ------  COPY RUN REQUEST (REQUIRED: RUN NAME, EXPERIMENT TYPE, NEW RUN NAME) ----------
class CopyRunRequest(RunRequest):
    new_run_name: str = Field(..., description="Name for the duplicated sequencing run.")

# ------ ASSEMBLY REQUEST (REQUIRED: ASSEMBLY INFO, SAMPLESHEET) ----------
class AssemblyRequest(AssemblyInfo):
    samplesheet: List[OntSamplesheet] | List[IlluminaSamplesheet] = Field(..., description="Samplesheet for the sequencing run.")

# ------ GET RUN INFO RESPONSE ----------
class GetRunInfoResponse(BaseModel):
    assembly_info: Optional[List[Dict[str, Any]]] = Field(None, description="Assembly information for the sequencing run.")
    samplesheet: Optional[List[Dict[str, Any]]] = Field(None, description="Samplesheet rows from the UI.")
    barcode_assignments: Optional[Dict[str, Any]] = Field(None, description="Barcode assignment for the sequencing run.")
    qc_statement: Optional[Dict[str, Any]] = Field(None, description="QC statement for the sequencing run.")
    quality_control_decisions: Optional[Dict[str, Any]] = Field(None, description="Quality control decisions for the sequencing run.")
    assembly_results: Optional[Dict[str, Any]] = Field(None, description="MIRA assembly results for the sequencing run.")
    coverage: Optional[Dict[str, Any]] = Field(None, description="Reference coverage for the sequencing run.")
    sample_coverage_list: Optional[List[Dict[str, Any]]] = Field(None, description="Sample coverage list for the sequencing run.")
    sample_coverage_sankeyfig: Optional[Dict[str, Any]] = Field(None, description="Sample coverage sankey figure for the sequencing run.")
    variants: Optional[Dict[str, Any]] = Field(None, description="Reference variants for the sequencing run.")
    indels: Optional[Dict[str, Any]] = Field(None, description="Reference indels for the sequencing run.")
    minor_snvs: Optional[Dict[str, Any]] = Field(None, description="Minor SNVs for the sequencing run.")
    nt_passed_fasta_location: Optional[str] = Field(None, description="Location of the NT passed FASTA file for the sequencing run.")
    nt_failed_fasta_location: Optional[str] = Field(None, description="Location of the NT failed FASTA file for the sequencing run.")
    aa_passed_fasta_location: Optional[str] = Field(None, description="Location of the AA passed FASTA file for the sequencing run.")
    aa_failed_fasta_location: Optional[str] = Field(None, description="Location of the AA failed FASTA file for the sequencing run.")
    nextclade_fasta_location: Optional[List[Dict[str, Any]]] = Field(None, description="Location of the Nextclade FASTA file for the sequencing run.")
    message: Optional[str] = Field(None, description="Message indicating the status of the request.")
