from pydantic import BaseModel, Field, model_validator
from typing import List, Optional, Literal, Dict, Any, Union
import polars as pl

# Import schema validator
from .schema_validator import (
    validate_tbl,
    organisms,
    database_targets,
    database_statuses,
    submission_types,
    submission_portals,
    submission_statuses,
    ncbi_publication_statuses,
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
    submission_pa_schema,
    submitter_pa_schema,
)

# Pre-compute Literal types for SeqSender submission
_Organisms = Literal[tuple(organisms)]
_DatabaseTargets = Literal[tuple(database_targets)]
_DatabaseStatuses = Literal[tuple(database_statuses)]
_SubmissionTypes = Literal[tuple(submission_types)]
_SubmissionStatuses = Literal[tuple(submission_statuses)]
_SubmissionPortals = Literal[tuple(submission_portals)]
_NcbiPublicationStatuses = Literal[tuple(ncbi_publication_statuses)]

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
    keep_workdir: bool = Field(False, description="Whether to preserve the Nextflow work directory after a successful run (for reviewing per-task logs).")
    assembly_status: _AssemblyStatus = Field(..., description="Assembly status for the sequencing run")
    @model_validator(mode='after')
    def validate_against_assembly_schema(self) -> 'AssemblyInfo':
        tbl = pl.DataFrame([self.model_dump()])
        validate_tbl(tbl, assembly_pa_schema, "assembly")
        return self

# ------ DB ASSEMBLY INFO MODEL ----------
class DBAssemblyInfo(AssemblyInfo):
    assembly_id: int = Field(..., description="Assembly ID.")
    created_at: Optional[str] = Field(None, description="Timestamp when the run was created (YYYY-MM-DD HH:MM:SS).")
    finished_at: Optional[str] = Field(None, description="Timestamp when the run finished (YYYY-MM-DD HH:MM:SS).")

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
    stream: Optional[str] = Field(None, description="Which stream to prefer: 'stdout' reads .command.out/.command.log first; otherwise the error log is preferred.")
    full: Optional[bool] = Field(False, description="When true, also return the untruncated file contents in 'full_text' (used for copy).")

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

# -------------------------------------------
#
#  SEQSENDER MODELS --------
#
# -------------------------------------------
class SubmissionInfo(BaseModel):
    submission_name: str = Field(..., description="Name of the submission.")
    organism: _Organisms = Field(..., description="Organism for which to send sequences.")
    submission_portal: _SubmissionPortals = Field(..., description="Submission portal (NCBI or GISAID).")
    database: _DatabaseTargets = Field(..., description="Database being submitted to.")
    database_status: _DatabaseStatuses = Field(..., description="Status of the submission to the database.")
    submission_type: _SubmissionTypes = Field(..., description="Type of submission.")
    gff_file: bool = Field(..., description="Indicates if a GFF file is included in the submission.")
    table2asn: bool = Field(..., description="Indicates if a table2asn file is included in the submission.")
    submitter_name: Optional[str] = Field(None, description="Submitter name for the submission.")
    ncbi_publication_title: Optional[str] = Field(None, description="NCBI publication title.")
    ncbi_publication_status: _NcbiPublicationStatuses = Field(..., description="NCBI publication status.")
    ncbi_release_date: Optional[str] = Field(None, description="NCBI release date.")
    number_of_samples: Optional[int] = Field(None, description="Number of samples in the submission's metadata/FASTA.")
    ncbi_submission_id: Optional[str] = Field(None, description="Accession/ID returned by the submission portal.")
    ncbi_submission_status: Optional[str] = Field(None, description="Raw status reported by the submission portal.")
    submission_status: _SubmissionStatuses = Field(..., description="Status of the submission.")
    comments: Optional[str] = Field(None, description="Additional comments for the submission.")
    date_submitted: Optional[str] = Field(None, description="Date the submission was created.")
    date_updated: Optional[str] = Field(None, description="Date the submission was last updated.")
    @model_validator(mode='after')
    def validate_against_submission_schema(self) -> 'SubmissionInfo':
        tbl = pl.DataFrame([self.model_dump()])
        validate_tbl(tbl, submission_pa_schema, "submission")
        return self
        
class DBSubmissionInfo(SubmissionInfo):
    submission_id: int = Field(..., description="Unique identifier for the submission.")

class ListSubmissionResponse(BaseModel):
    submission_info: Optional[List[DBSubmissionInfo]] = Field(None, description="Information about the submissions.")

class SubmitterInfo(BaseModel):
    submitter_name: str = Field(..., description="Name of the submitter.")
    submitter_password: str = Field(..., description="Password for the submitter.")
    submission_portal: _SubmissionPortals = Field(..., description="Submission portal (NCBI or GISAID).")
    # Portal-specific credential fields
    ncbi_spuid_namespace: Optional[str] = Field(None, description="NCBI SPUID namespace for the submitter.")
    gisaid_client_id: Optional[str] = Field(None, description="GISAID client ID for the submitter.")
    # NCBI Description.Organization
    ncbi_org_role: Optional[str] = Field(None, description="NCBI organization role for the submitter.")
    ncbi_org_type: Optional[str] = Field(None, description="NCBI organization type for the submitter.")
    ncbi_org_name: Optional[str] = Field(None, description="NCBI organization name for the submitter.")
    ncbi_org_affiliation: Optional[str] = Field(None, description="NCBI organization affiliation for the submitter.")
    ncbi_org_division: Optional[str] = Field(None, description="NCBI organization division for the submitter.")
    # NCBI Description.Organization.Address
    ncbi_addr_street: Optional[str] = Field(None, description="NCBI address street for the submitter.")
    ncbi_addr_city: Optional[str] = Field(None, description="NCBI address city for the submitter.")
    ncbi_addr_state: Optional[str] = Field(None, description="NCBI address state for the submitter.")
    ncbi_addr_postal_code: Optional[str] = Field(None, description="NCBI address postal code for the submitter.")
    ncbi_addr_country: Optional[str] = Field(None, description="NCBI address country for the submitter.")
    ncbi_addr_email: Optional[str] = Field(None, description="NCBI address email for the submitter.")
    ncbi_addr_phone: Optional[str] = Field(None, description="NCBI address phone for the submitter.")
    # NCBI Description.Organization.Address.Submitter
    ncbi_submitter_email: Optional[str] = Field(None, description="NCBI submitter email.")
    ncbi_submitter_alt_email: Optional[str] = Field(None, description="NCBI submitter alternate email.")
    ncbi_submitter_first_name: Optional[str] = Field(None, description="NCBI submitter first name.")
    ncbi_submitter_last_name: Optional[str] = Field(None, description="NCBI submitter last name.")
    @model_validator(mode='after')
    def validate_against_submitter_schema(self) -> 'SubmitterInfo':
        tbl = pl.DataFrame([self.model_dump()])
        validate_tbl(tbl, submitter_pa_schema, "submitter")
        return self
    
class DBSubmitterInfo(SubmitterInfo):
    submitter_id: int = Field(..., description="Unique identifier for the submitter.")

class ListSubmitterResponse(BaseModel):
    SubmitterInfo: Optional[List[DBSubmitterInfo]] = Field(None, description="Information about the submitters.")

# ------  DELETE SUBMITTER REQUEST (REQUIRED: SUBMITTER NAME, SUBMISSION PORTAL) ----------
class DeleteSubmitterRequest(BaseModel):
    submitter_name: str = Field(..., description="Name of the submitter.")
    submission_portal: _SubmissionPortals = Field(..., description="Submission portal (NCBI or GISAID).")

class SubmissionRequest(BaseModel):
    submission_name: str = Field(..., description="Name of the submission.")
    organism: _Organisms = Field(..., description="Organism for which to send sequences.")
    database: List[_DatabaseTargets] = Field(..., description="One or more databases to submit to.")
    submission_type: _SubmissionTypes = Field(..., description="Type of submission.")

class StatusUpdateCronRequest(BaseModel):
    frequency: Literal["hourly"] = Field("hourly", description="How often submission statuses are updated.")
    interval_hours: Literal[1, 2, 3, 4] = Field(1, description="Number of hours between status updates.")

# ------  DELETE SUBMISSION REQUEST (REQUIRED: SUBMISSION NAME, ORGANISM) ----------
class DeleteSubmissionRequest(BaseModel):
    submission_name: str = Field(..., description="Name of the submission.")
    organism: _Organisms = Field(..., description="Organism for which to send sequences.")

# ------  COPY SUBMISSION REQUEST (REQUIRED: SUBMISSION NAME, ORGANISM, NEW SUBMISSION NAME) ----------
class CopySubmissionRequest(DeleteSubmissionRequest):
    new_submission_name: str = Field(..., description="Name for the duplicated submission.")

# ------  UPDATE SUBMISSION COMMENTS REQUEST ----------
class UpdateSubmissionCommentsRequest(BaseModel):
    submission_name: str = Field(..., description="Name of the submission.")
    organism: _Organisms = Field(..., description="Organism for which to send sequences.")
    database: _DatabaseTargets = Field(..., description="Database whose row's comments should be updated.")
    submission_type: _SubmissionTypes = Field(..., description="Type of submission.")
    comments: Optional[str] = Field(None, description="Additional comments for the submission.")

# ------  UPDATE SUBMISSION STATUS REPORT MESSAGES REQUEST ----------
class UpdateSubmissionStatusReportMessagesRequest(BaseModel):
    submission_name: str = Field(..., description="Name of the submission.")
    organism: _Organisms = Field(..., description="Organism for which to send sequences.")
    database: _DatabaseTargets = Field(..., description="Database whose status report messages should be updated.")
    submission_type: _SubmissionTypes = Field(..., description="Type of submission.")
    messages: Dict[str, Optional[str]] = Field(default_factory=dict, description="Mapping of sample_name -> edited message for this database's status report rows.")

class CreateSubmissionRequest(SubmissionRequest):
    ncbi_submitter_info: Optional[SubmitterInfo] = Field(None, description="NCBI submitter information for the submission.")
    gisaid_submitter_info: Optional[SubmitterInfo] = Field(None, description="GISAID submitter information for the submission.")
    gff_file: bool = Field(..., description="Indicates if a GFF file is included in the submission.")
    table2asn: bool = Field(..., description="Indicates if a table2asn file is included in the submission.")
    ncbi_publication_title: Optional[str] = Field(None, description="NCBI publication title for the submission.")
    ncbi_publication_status: _NcbiPublicationStatuses = Field(..., description="NCBI publication status for the submission.")
    ncbi_release_date: Optional[str] = Field(None, description="NCBI release date for the submission.")

    @model_validator(mode='after')
    def validate_ncbi_submitter_info(self) -> 'CreateSubmissionRequest':
        if self.ncbi_submitter_info is not None:
            postal_code = (self.ncbi_submitter_info.ncbi_addr_postal_code or "").strip()
            if not postal_code.isdigit():
                raise ValueError("NCBI postal code must contain only digits for SeqSender.")
            if not (self.ncbi_submitter_info.ncbi_org_affiliation or "").strip():
                raise ValueError("NCBI organization affiliation is required for SeqSender.")
            if not (self.ncbi_submitter_info.ncbi_org_division or "").strip():
                raise ValueError("NCBI organization division is required for SeqSender.")
            if not (self.ncbi_submitter_info.ncbi_addr_email or "").strip():
                raise ValueError("NCBI organization email is required for SeqSender.")
        return self


