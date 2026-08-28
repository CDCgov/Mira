from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal, Dict, Any, Union
import polars as pl

# Import schema validator
from .schema_validator import (
    validate_tbl,
    organisms,
    database_targets,
    database_status,
    submission_types,
    submission_status,
    experiment_types,
    sample_types,
    sample_status,
    sc2_primers,
    rsv_primers,
    irma_modules,
    assembly_status,
    assembly_pa_schema,
    submission_pa_schema,
    ont_samplesheet_pa_schema,
    illumina_samplesheet_pa_schema,
)

# Pre-compute Literal types for SeqSender submission
Organism = Literal[tuple(organisms)]
DatabaseTargets = Literal[tuple(database_targets)]
DatabaseStatus = Literal[tuple(database_status)]
SubmissionTypes = Literal[tuple(submission_types)]
SubmissionStatus = Literal[tuple(submission_status)]

# Pre-compute Literal types for MIRA assembly
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
class ListRunResponse(BaseModel):
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

# -------- SEQSENDER MODELS --------
class SubmissionInfo(BaseModel):
    submission_name: str = Field(..., description="Name of the submission.")
    organism: Literal[Organism] = Field(..., description="Organism for which to send sequences.")
    database: List[Literal[DatabaseTargets]] = Field(..., description="One or more databases to submit to.")
    database_status: List[Literal[DatabaseStatus]] = Field(..., description="Status of the submission to each database.")
    submission_type: Literal[SubmissionTypes] = Field(..., description="Type of submission.")
    gff_file: bool = Field(..., description="Indicates if a GFF file is included in the submission.")
    table2asn: bool = Field(..., description="Indicates if a table2asn file is included in the submission.")
    submission_id: Optional[str] = Field(None, description="Unique identifier for the submission.")
    submission_status: Literal[SubmissionStatus] = Field(..., description="Status of the submission.")
    @model_validator(mode='after')
    def validate_against_submission_schema(self) -> 'SubmissionInfo':
        tbl = pl.DataFrame([self.model_dump()])
        validate_tbl(tbl, submission_pa_schema, "submission")
        return self
    
class DBSubmissionInfo(SubmissionInfo):
    submission_id_pk: str = Field(..., description="Unique identifier for the submission.")

class ListSubmissionResponse(BaseModel):
    submission_info: Optional[List[DBSubmissionInfo]] = Field(None, description="Information about the submissions.")

class SubmissionRequest(BaseModel):
    submission_name: str = Field(..., description="Name of the submission.")
    organism: Literal[Organism] = Field(..., description="Organism for which to send sequences.")
    database: List[Literal[DatabaseTargets]] = Field(..., description="One or more databases to submit to.")
    submission_type: Literal[SubmissionTypes] = Field(..., description="Type of submission.")

class SeqSenderRequest(SubmissionRequest):
    database_status: List[Literal[DatabaseStatus]] = Field(..., description="Status of the submission to each database.")
    gff_file: bool = Field(..., description="Indicates if a GFF file is included in the submission.")
    table2asn: bool = Field(..., description="Indicates if a table2asn file is included in the submission.")

