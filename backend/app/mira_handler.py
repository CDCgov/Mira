# Import future annotations for Pydantic models
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any

# Import polars
from fastapi import UploadFile
import polars as pl

# Import general python packages
import os
import re
import glob
import json
import time
import shutil
import signal
import psutil
import subprocess

# Import schema validator 
from .schema_validator import (
    _DEFAULT_DATA_STORAGE_PATH,
    _DEFAULT_MIRA_STORAGE_PATH,
    _MIRA_NF_IMAGE,
    _DEPLOY_TYPE,
    assembly_pa_schema,
    assembly_db_schema,
    ont_samplesheet_pa_schema,
    ont_samplesheet_db_schema,
    illumina_samplesheet_pa_schema,
    illumina_samplesheet_db_schema,
    validate_tbl,
    CUSTOM_PRIMER_CONFIG_FILENAME,
    CUSTOM_IRMA_CONFIG_FILENAME,
    CUSTOM_QC_SETTINGS_FILENAME,
)

# Import utils for dataframe operations
from .utils import (
    compare_and_update_db_table
)

# Import sqlite_handler for database connection
from .sqlite_handler import (
    lookup_tbl_in_database, 
    insert_tbl_to_database,
    update_tbl_in_database,
    delete_val_in_database,
)

# Import shared logger (INFO/DEBUG -> stdout, WARNING/ERROR/CRITICAL -> stderr)
from .logging_config import logger

# SQLite BOOLEAN columns are read back by Polars as strings ("0"/"1"), and
# bool("0") is truthy in Python. Coerce such values to a real boolean before use.
def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() in ("1", "true", "t", "yes")

# Build a cast expression for a column to a target Polars dtype. Polars cannot
# cast a string ("0"/"1") straight to Boolean, so map string values explicitly;
# all other dtypes use a plain cast.
def _cast_expr(col: str, dtype: Any) -> "pl.Expr":
    if dtype == pl.Boolean:
        return (
            pl.col(col).cast(pl.String).str.strip_chars().str.to_lowercase()
            .is_in(["1", "true", "t", "yes"]).alias(col)
        )
    return pl.col(col).cast(dtype)

# Function to remove previous pipeline outputs for a given run directory
def _remove_previous_pipeline_outputs(run_dir: str) -> None:

    # Get the absolute path of the data storage directory
    data_root = os.path.realpath(_DEFAULT_DATA_STORAGE_PATH)

    # Remove artifacts from the current run directory.
    output_paths = [
        os.path.join(run_dir, "outputs"),
        *glob.glob(os.path.join(run_dir, ".nextflow.log*")),
    ]

    # Define placeholder to store paths that could not be removed due to permission issues
    permission_denied_paths = []

    # Check each output path to ensure it is within the data directory before attempting to remove it
    for output_path in output_paths:
        if not os.path.lexists(output_path):
            continue
        resolved_path = os.path.realpath(output_path)
        if os.path.commonpath([data_root, resolved_path]) != data_root:
            raise ValueError(f"Refusing to remove outputs outside of data storage: {output_path}")
        try:
            if os.path.isdir(output_path) and not os.path.islink(output_path):
                shutil.rmtree(output_path)
            else:
                os.remove(output_path)
        except PermissionError:
            permission_denied_paths.append(output_path)

    # If there are any permission denied paths, attempt to remove them using a Docker container with elevated permissions
    if not permission_denied_paths:
        return

    # If the deployment type is Local, remove the outputs folder via a Docker container
    if _DEPLOY_TYPE == "Local":

        # Prepare the list of container paths for the permission denied outputs
        container_paths = []
        for output_path in permission_denied_paths:
            container_paths.append(f"/data/{os.path.relpath(output_path, data_root)}")

        # Run the Docker container to remove the outputs folder with elevated permissions
        try:
            subprocess.run(
                [
                    "docker", "run", "--rm",
                    "-v", f"{_DEFAULT_DATA_STORAGE_PATH}:/data",
                    _MIRA_NF_IMAGE,
                    "rm", "-rf", "--", *container_paths,
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as err:
            detail = err.stderr.strip() or err.stdout.strip() or str(err)
            raise PermissionError(f"Unable to clear previous pipeline outputs: {detail}") from err

        # After attempting to remove the outputs folder via Docker, check if any paths still exist
        remaining_paths = [path for path in permission_denied_paths if os.path.lexists(path)]
        if remaining_paths:
            raise PermissionError(f"Unable to clear previous pipeline outputs: {', '.join(remaining_paths)}")
    else:
        raise PermissionError(f"Unable to clear previous pipeline outputs: {', '.join(permission_denied_paths)}")

####################################################
#
# MIRA RESULTS RETRIEVAL FUNCTIONS
#
####################################################

# Get barcode assignment from storage
def retrieve_barcode_assignment(run_name: str, experiment_type: str) -> dict | None:
    try:    
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Get barcode assignment result from storage
        barcode_assignment_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "barcode_distribution.json")
        # Check if the barcode assignment file exists
        if os.path.exists(barcode_assignment_path):
            with open(barcode_assignment_path, "r") as f:
                barcode_assignment = json.load(f)
        else:
            barcode_assignment = None
    except Exception as err:
        raise Exception(str(err))
    return barcode_assignment

# Get QC statement from storage
def retrieve_qc_statement(run_name: str, experiment_type: str) -> dict | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]        
        # Get quality control result from storage
        qc_statement_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "qc_statement.json")
        # Check if the quality control result file exists
        if os.path.exists(qc_statement_path):
            with open(qc_statement_path, "r") as f:
                qc_statement = json.load(f)
        else:
            qc_statement = None
    except Exception as err:
        raise Exception(str(err))
    return qc_statement

# Get quality control decisions from storage
def retrieve_quality_control_decisions(run_name: str, experiment_type: str) -> dict | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]        
        # Get quality control result from storage
        qc_result_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "pass_fail_heatmap.json")
        # Check if the quality control result file exists
        if os.path.exists(qc_result_path):
            with open(qc_result_path, "r") as f:
                qc_result = json.load(f)
        else:
            qc_result = None
    except Exception as err:
        raise Exception(str(err))
    return qc_result

# Get MIRA summary from storage
def retrieve_mira_summary(run_name: str, experiment_type: str) -> list | None:
    try:
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        mira_summary_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "irma_summary.json")
        if os.path.exists(mira_summary_path):
            with open(mira_summary_path, "r") as f:
                raw = json.load(f)
            if isinstance(raw, dict) and "columns" in raw and "data" in raw:
                mira_summary_result = [dict(zip(raw["columns"], row)) for row in raw["data"]]
            else:
                mira_summary_result = raw
        else:
            mira_summary_result = None
    except Exception as err:
        raise Exception(str(err))
    return mira_summary_result

# Get reference coverage from storage
def retrieve_coverage_table(run_name: str, experiment_type: str) -> list | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Get reference coverage result from storage (coverage.json = per-position depth table)
        reference_coverage_result_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "coverage.json")
        # Check if the reference coverage result file exists
        if os.path.exists(reference_coverage_result_path):
            with open(reference_coverage_result_path, "r") as f:
                raw = json.load(f)
            # Convert Pandas split-format to list of row dicts
            if isinstance(raw, dict) and "columns" in raw and "data" in raw:
                reference_coverage_result = [dict(zip(raw["columns"], row)) for row in raw["data"]]
            else:
                reference_coverage_result = raw
        else:
            reference_coverage_result = None
    except Exception as err:
        raise Exception(str(err))
    return reference_coverage_result

# Get reference coverage heatmap from storage
def retrieve_coverage_heatmap(run_name: str, experiment_type: str) -> list | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Get coverage heatmap from storage (heatmap.json = per-position depth table)
        reference_coverage_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "heatmap.json")
        # Check if the heatmap file exists
        if os.path.exists(reference_coverage_path):
            with open(reference_coverage_path, "r") as f:
                raw = json.load(f)
            # Convert Pandas split-format to list of row dicts
            if isinstance(raw, dict) and "columns" in raw and "data" in raw:
                reference_coverage_heatmap = [dict(zip(raw["columns"], row)) for row in raw["data"]]
            else:
                reference_coverage_heatmap = raw
        else:
            reference_coverage_heatmap = None
    except Exception as err:
        raise Exception(str(err))
    return reference_coverage_heatmap

# Get sample list from storage
def retrieve_sample_coverage_list(run_name: str, experiment_type: str) -> dict | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Get sample coverage result from storage
        sample_coverage_list_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "reads.json")
        # Check if the sample coverage result file exists
        if os.path.exists(sample_coverage_list_path):
            with open(sample_coverage_list_path, "r") as f:
                sample_coverage_list = json.load(f)
        else:
            sample_coverage_list = None
    except Exception as err:
        raise Exception(str(err))
    return sample_coverage_list

# Get sample coverage sankeyfig from storage
def retrieve_sample_coverage_sankeyfig(run_name: str, experiment_type: str, sample_id: str) -> dict | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Get sample coverage sankeyfig result from storage
        sample_coverage_sankeyfig_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", f"readsfig_{sample_id}.json")
        # Check if the sample coverage sankeyfig result file exists
        if os.path.exists(sample_coverage_sankeyfig_path):
            with open(sample_coverage_sankeyfig_path, "r") as f:
                sample_coverage_sankeyfig = json.load(f)
        else:
            sample_coverage_sankeyfig = None
    except Exception as err:
        raise Exception(str(err))
    return sample_coverage_sankeyfig

# Get sample coverage plot from storage
def retrieve_sample_coverage_plot(run_name: str, experiment_type: str, sample_id: str) -> dict | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Get sample coverage plot result from storage
        sample_coverage_plot_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", f"coveragefig_{sample_id}_linear.json")
        # Check if the sample coverage plot result file exists
        if os.path.exists(sample_coverage_plot_path):
            with open(sample_coverage_plot_path, "r") as f:
                sample_coverage_plot = json.load(f)
        else:
            sample_coverage_plot = None
    except Exception as err:
        raise Exception(str(err))
    return sample_coverage_plot

# Get variants from storage
def retrieve_variants(run_name: str, experiment_type: str) -> dict | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Get variants result from storage
        variants_result_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "dais_vars.json")
        # Check if the variants result file exists
        if os.path.exists(variants_result_path):
            with open(variants_result_path, "r") as f:
                raw = json.load(f)
            # Convert Pandas split-format to list of row dicts
            if isinstance(raw, dict) and "columns" in raw and "data" in raw:
                variants_result = [dict(zip(raw["columns"], row)) for row in raw["data"]]
            else:
                variants_result = raw
        else:
            variants_result = None
    except Exception as err:
        raise Exception(str(err))
    return variants_result

# Retrieve Minor SNVs from storage
def retrieve_minor_snvs(run_name: str, experiment_type: str) -> dict | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        # Get minor snvs result from storage
        minor_snvs_result_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "minor_variants.json")
        # Check if the minor snvs result file exists
        if os.path.exists(minor_snvs_result_path):
            with open(minor_snvs_result_path, "r") as f:
                raw = json.load(f)
            # Convert Pandas split-format to list of row dicts
            if isinstance(raw, dict) and "columns" in raw and "data" in raw:
                minor_snvs_result = [dict(zip(raw["columns"], row)) for row in raw["data"]]
            else:
                minor_snvs_result = raw
        else:
            minor_snvs_result = None
    except Exception as err:
        raise Exception(str(err))
    return minor_snvs_result

# Get indels from storage
def retrieve_indels(run_name: str, experiment_type: str) -> dict | None:
    try:
        # Get pathogen and instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]        
        # Get indels result from storage
        indels_result_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "dash-json", "indels.json")
        # Check if the indels result file exists
        if os.path.exists(indels_result_path):
            with open(indels_result_path, "r") as f:
                raw = json.load(f)
            # Convert Pandas split-format to list of row dicts
            if isinstance(raw, dict) and "columns" in raw and "data" in raw:
                indels_result = [dict(zip(raw["columns"], row)) for row in raw["data"]]
            else:
                indels_result = raw
        else:
            indels_result = None
    except Exception as err:
        raise Exception(str(err))
    return indels_result

####################################################
#
# MIRA RETRIEVE FASTA FUNCTIONS
#
####################################################

# Get nt_passed_fasta location from storage
def retrieve_passed_amended_consensus(run_name: str, experiment_type: str) -> str | None:
    try:
        # Extract instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        fasta_path_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "mira-reports")
        fasta_path = None
        if os.path.isdir(fasta_path_dir):
            candidates = sorted(
                (f for f in os.listdir(fasta_path_dir)
                if f.startswith("mira") and f.endswith("amended_consensus.fasta") and "failed" not in f),
                reverse=True,
            )
            if candidates:
                fasta_path = os.path.join(fasta_path_dir, candidates[0])
        return fasta_path
    except Exception as err:
        raise Exception(str(err))
    
# Get nt_failed_fasta location from storage
def retrieve_failed_amended_consensus(run_name: str, experiment_type: str) -> str | None:
    try:
        # Extract instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        fasta_path_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "mira-reports")
        fasta_path = None
        if os.path.isdir(fasta_path_dir):
            candidates = sorted(
                (f for f in os.listdir(fasta_path_dir)
                if f.startswith("mira") and f.endswith("failed_amended_consensus.fasta")),
                reverse=True,
            )
            if candidates:
                fasta_path = os.path.join(fasta_path_dir, candidates[0])
        return fasta_path
    except Exception as err:
        raise Exception(str(err))

# Get aa_passed_fasta location from storage
def retrieve_passed_amino_acid_consensus(run_name: str, experiment_type: str) -> str | None:
    try:
        # Extract instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        fasta_path_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "mira-reports")
        fasta_path = None
        if os.path.isdir(fasta_path_dir):
            candidates = sorted(
                (f for f in os.listdir(fasta_path_dir)
                if f.startswith("mira") and f.endswith("amino_acid_consensus.fasta") and "failed" not in f),
                reverse=True,
            )
            if candidates:
                fasta_path = os.path.join(fasta_path_dir, candidates[0])
        return fasta_path
    except Exception as err:
        raise Exception(str(err))
    
# Get aa_failed_fasta location from storage
def retrieve_failed_amino_acid_consensus(run_name: str, experiment_type: str) -> str | None:
    try:
        # Extract instrument type from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]
        fasta_path_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "aggregate_outputs", "mira-reports")
        fasta_path = None
        if os.path.isdir(fasta_path_dir):
            candidates = sorted(
                (f for f in os.listdir(fasta_path_dir)
                if f.startswith("mira") and f.endswith("failed_amino_acid_consensus.fasta")),
                reverse=True,
            )
            if candidates:
                fasta_path = os.path.join(fasta_path_dir, candidates[0])
        return fasta_path
    except Exception as err:
        raise Exception(str(err))
    
# Get nextclade fasta location from storage
def retrieve_nextclade_aligned_fasta(run_name: str, experiment_type: str) -> str | None:
    try:
        # Extract pathogen and instrument from experiment_type
        pathogen = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]

        # Check if run has alias_name in assembly table
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["alias_name"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        if db_assembly_tbl.is_empty():
            raise ValueError(f"Run '{run_name}' not found in database for experiment type '{experiment_type}'.")

        # Determine alias_name to use for nextclade fasta file search, falling back to run_name if unset
        alias_name = db_assembly_tbl.select("alias_name").to_series()[0]
        nextclade_run_name = alias_name if alias_name else run_name

        # Create placeholder to store fasta for each pathogen, subtype, and segment combination
        nextclade_fasta_paths = {}
        fasta_path_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "outputs", "nextclade", "input_fasta_files")
        if os.path.isdir(fasta_path_dir):
            candidates = sorted(
                (f for f in os.listdir(fasta_path_dir) if f.startswith(f"nextclade") and f.endswith(".fasta")),
                reverse=True,
            )
            for f in candidates:
                match = re.search(rf"nextclade_{re.escape(nextclade_run_name)}_(.*?)\.fasta", f)
                if match:
                    dataset = match.group(1)
                    nextclade_fasta_paths[dataset] = os.path.join(fasta_path_dir, f)
        # Return the dictionary of nextclade fasta paths if any exist, otherwise return None
        if len(nextclade_fasta_paths) > 0:
            return nextclade_fasta_paths
        else:
            return None
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

####################################################
#
# MIRA CREATION FUNCTIONS
#
####################################################

# Define function to get run information
def retrieve_run(
    run_name: str, 
    experiment_type: str
) -> dict[str, Any] | None:
    try:
        # Get assembly table from database
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        if db_assembly_tbl.is_empty():
            return{
                "run_info": None,
                "samplesheet": None,
            }
        else:
            # Retrieve assembly information
            assembly_id = db_assembly_tbl.select("assembly_id").to_series()[0]
            # Get samplesheet table from database based on instrument type
            if "ONT" in experiment_type.upper():
                db_samplesheet_tbl = lookup_tbl_in_database(
                    db_tbl_name = ["ont_samplesheet"],
                    return_var = ["*"],
                    filter_coln_var = ["assembly_id"],
                    filter_coln_val = {"assembly_id": [assembly_id]},
                    filter_var_by = ["AND"]
                )
            elif "ILLUMINA" in experiment_type.upper():
                db_samplesheet_tbl = lookup_tbl_in_database(
                    db_tbl_name = ["illumina_samplesheet"],
                    return_var = ["*"],
                    filter_coln_var = ["assembly_id"],
                    filter_coln_val = {"assembly_id": [assembly_id]},
                    filter_var_by = ["AND"]
                )
            return {
                "run_info": db_assembly_tbl.to_dicts(),
                "samplesheet": db_samplesheet_tbl.to_dicts(),
            }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    
# Validate the samplesheet and ensure all referenced FASTQ files exist in storage location
def validate_samplesheet_and_fastqs_in_storage(
    run_name: str,
    experiment_type: str,
) -> dict[str, Any]:
    
    # Extract pathogen and instrument type from experiment_type
    pathogen = experiment_type.split("-")[0]
    instrument = experiment_type.split("-")[-1]

    # Retrieve assembly table from database
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name", "experiment_type"],
        filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
        filter_var_by = ["AND"]
    )

    # Extract assembly information from assembly_tbl
    assembly_id = db_assembly_tbl.select("assembly_id").to_series()[0]

    # Get samplesheet table from database based on assembly_id and experiment_type
    if "ONT" in instrument.upper():
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["ont_samplesheet"],
            return_var = ["*"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )
    elif "ILLUMINA" in instrument.upper():
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["illumina_samplesheet"],
            return_var = ["*"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )

    # Create placehodler to store missing FASTQ files
    missing_fastq_files = []

    # Extract sample_ids from db_samplesheet_tbl
    for i in range(db_samplesheet_tbl.shape[0]):
        sample_missing_fastq_files = []
        row = db_samplesheet_tbl.row(i, named=True)
        # Get the corresponding sample_id and fastq files
        if "ONT" in instrument.upper():
            sample_id = row["barcode"]
            sample_fastq_files = [row["fastq"]]
            storage_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "fastq_pass", sample_id)
        elif "ILLUMINA" in instrument.upper():
            sample_id = row["sample_id"]
            sample_fastq_files = [row["fastq_1"], row["fastq_2"]]
            storage_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, "fastqs")
        # Check if each FASTQ file exists in the storage location
        for fastq_file in sample_fastq_files:
            fastq_file_path = os.path.join(storage_dir, fastq_file)
            if not os.path.exists(fastq_file_path):
                sample_missing_fastq_files.append(fastq_file)
        # If any missing FASTQ files are found for the sample, add them to overall missing_fastq_files list
        if len(sample_missing_fastq_files) > 0:
            missing_fastq_files.append(f"{sample_id}: Missing {', '.join(sample_missing_fastq_files)}")
    
    # Return the validation results
    if len(missing_fastq_files) > 0:
        return {
            "validation_status": "failed",
            "missing_fastq_files": missing_fastq_files,
            "message": [
                f"The FASTQ files were missing from the storage location of this run.",
                f"The files might have been deleted or moved. Please check the storage location or simply upload the missing FASTQ files again.",
            ]
        }
    else:
        return {
            "validation_status": "passed",
            "missing_fastq_files": [],
            "message": [f"All FASTQ files exist in the storage location for this run."]
        }

# Validate custom primers, custom irma config, and custom nextclade config in storage if provided
def validate_custom_configs_in_storage(
    run_name: str,
    experiment_type: str,
) -> dict[str, Any]:

    # Retrieve assembly table from database
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name", "experiment_type"],
        filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
        filter_var_by = ["AND"]
    )

    # Make sure db_assembly_tbl is not empty
    if db_assembly_tbl.shape[0] == 0:
        raise ValueError(f"No assembly found for run_name '{run_name}' and experiment_type '{experiment_type}'.")
    
    # Extract pathogen and instrument type from experiment_type
    pathogen = experiment_type.split("-")[0]
    instrument = experiment_type.split("-")[-1]

    # Extract assembly information from assembly_tbl. SQLite BOOLEAN columns are
    # read back by Polars as strings ("0"/"1"), and bool("0") is truthy in Python,
    # so coerce to a real boolean before deciding whether a config file is required.
    custom_primers = _as_bool(db_assembly_tbl.select("custom_primers").to_series()[0])
    custom_irma_config = _as_bool(db_assembly_tbl.select("custom_irma_config").to_series()[0])
    custom_qc_settings = _as_bool(db_assembly_tbl.select("custom_qc_settings").to_series()[0])

    # Create placeholder to store missing config files
    missing_config_files = []

    # Check if custom primers file is provided and exists in storage
    if custom_primers:
        primers_storage_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, CUSTOM_PRIMER_CONFIG_FILENAME)
        if not os.path.exists(primers_storage_path):
            missing_config_files.append({"custom_primers": CUSTOM_PRIMER_CONFIG_FILENAME})

    # Check if custom irma config file is provided and exists in storage
    if custom_irma_config:
        irma_config_storage_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, CUSTOM_IRMA_CONFIG_FILENAME)
        if not os.path.exists(irma_config_storage_path):
            missing_config_files.append({"custom_irma_config": CUSTOM_IRMA_CONFIG_FILENAME})

    # Check if custom QC settings file is provided and exists in storage
    if custom_qc_settings:
        qc_settings_storage_path = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name, CUSTOM_QC_SETTINGS_FILENAME)
        if not os.path.exists(qc_settings_storage_path):
            missing_config_files.append({"custom_qc_settings": CUSTOM_QC_SETTINGS_FILENAME})

    # Return the validation results
    if len(missing_config_files) > 0:
        return {
            "validation_status": "failed",
            "missing_config_files": missing_config_files,
            "message": [
                f"The following custom configuration files were missing from the storage location of this run: {', '.join([list(d.values())[0] for d in missing_config_files])}.",
                f"Please check the storage location or upload the missing configuration files again.",
            ]
        }
    else:
        return {
            "validation_status": "passed",
            "missing_config_files": [],
            "message": [f"All provided custom configuration files exist in the storage location for this run."]
        }   

# Define function to upload assembly table in database
def update_assembly_in_database(
    run_name: str,
    experiment_type: str,
    assembly_tbl: pl.DataFrame,
    return_tbl: bool = True
) -> pl.DataFrame | None:
    try:
        # Check if assembly for this run_name exists in database
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        # Make sure db table match the schema data types
        db_assembly_tbl = db_assembly_tbl.with_columns([
            _cast_expr(col, assembly_db_schema.columns[col].dtype.type) for col in assembly_db_schema.columns
        ])
        # Validate db table against the schema
        db_assembly_tbl = validate_tbl(db_assembly_tbl, assembly_db_schema, "assembly")
        # Make sure assembly table match the schema data types
        assembly_tbl = assembly_tbl.with_columns([
            _cast_expr(col, assembly_pa_schema.columns[col].dtype.type) for col in assembly_pa_schema.columns
        ])
        # Validate assembly table against the schema
        assembly_tbl = validate_tbl(assembly_tbl, assembly_pa_schema, "assembly")
        # Check if db_assembly_tbl is empty, if so insert new assembly_tbl to database
        if db_assembly_tbl.is_empty():
            insert_tbl_to_database(
                db_tbl_name = ["assembly"],
                table = assembly_tbl
            )
        else:
            # Compare and update database table
            compare_and_update_db_table(
                unique_cols = ["run_name"],
                compare_tbl = assembly_tbl,
                db_tbl = db_assembly_tbl,
                db_tbl_name = "assembly"
            )    
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    # Whether to return database table
    if return_tbl:
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        return db_assembly_tbl
    else:
        return None
            
# Define function to upload samplesheet 
def update_samplesheet_in_database(
    run_name: str,
    experiment_type: str, 
    samplesheet_tbl: pl.DataFrame, 
    return_tbl: bool = True
) -> pl.DataFrame | None:
    try:
        # Get assembly table from database
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        # Make sure db_assembly_tbl is not empty
        if db_assembly_tbl.shape[0] == 0:
            raise ValueError(f"No assembly found for run_name '{run_name}' and experiment_type '{experiment_type}'.")
        # Retrieve assembly_id from assembly_tbl
        assembly_id = db_assembly_tbl.select("assembly_id").to_series()[0]        
        # Extract pathogen and instrument type from experiment_type
        instrument = experiment_type.split("-")[-1]        
        # Validate the samplesheet against the schema
        if "ONT" in instrument.upper():
            # Check samplesheet for this run_name exists in database
            db_samplesheet_tbl = lookup_tbl_in_database(
                db_tbl_name = ["ont_samplesheet"],
                return_var = ["*"],
                filter_coln_var = ["assembly_id"],
                filter_coln_val = {"assembly_id": [assembly_id]},
                filter_var_by = ["AND"]
            )             
            # Make sure db samplesheet match the schema data types
            db_samplesheet_tbl = db_samplesheet_tbl.with_columns([
                _cast_expr(col, ont_samplesheet_db_schema.columns[col].dtype.type) for col in ont_samplesheet_db_schema.columns
            ])   
            # Validate the db_samplesheet against the schema
            db_samplesheet_tbl = validate_tbl(db_samplesheet_tbl, ont_samplesheet_db_schema, "ont_samplesheet")
            # Make sure samplesheet match the schema data types
            samplesheet_tbl = samplesheet_tbl.with_columns([
                _cast_expr(col, ont_samplesheet_pa_schema.columns[col].dtype.type) for col in ont_samplesheet_pa_schema.columns
            ])            
            samplesheet_tbl = validate_tbl(samplesheet_tbl, ont_samplesheet_pa_schema, "ont_samplesheet")
        elif "ILLUMINA" in instrument.upper():
            # Check samplesheet for this run_name exists in database
            db_samplesheet_tbl = lookup_tbl_in_database(
                db_tbl_name = ["illumina_samplesheet"],
                return_var = ["*"],
                filter_coln_var = ["assembly_id"],
                filter_coln_val = {"assembly_id": [assembly_id]},
                filter_var_by = ["AND"]
            )   
            # Make sure db samplesheet match the schema data types
            db_samplesheet_tbl = db_samplesheet_tbl.with_columns([
                _cast_expr(col, illumina_samplesheet_db_schema.columns[col].dtype.type) for col in illumina_samplesheet_db_schema.columns
            ])
            # Validate the db_samplesheet against the schema
            db_samplesheet_tbl = validate_tbl(db_samplesheet_tbl, illumina_samplesheet_db_schema, "illumina_samplesheet")
            # Make sure samplesheet match the schema data types
            samplesheet_tbl = samplesheet_tbl.with_columns([
                _cast_expr(col, illumina_samplesheet_pa_schema.columns[col].dtype.type) for col in illumina_samplesheet_pa_schema.columns
            ]) 
            # Validate the samplesheet against the schema
            samplesheet_tbl = validate_tbl(samplesheet_tbl, illumina_samplesheet_pa_schema, "illumina_samplesheet")         
        # Add assembly_id column to samplesheet_tbl
        samplesheet_tbl = samplesheet_tbl.with_columns(pl.lit(assembly_id).alias("assembly_id"))
        # Check if db_samplesheet is empty, if so insert new samplesheet to database
        if db_samplesheet_tbl.is_empty():
            insert_tbl_to_database(
                db_tbl_name = ["ont_samplesheet" if "ONT" in instrument.upper() else "illumina_samplesheet"],
                table = samplesheet_tbl
            )
        else:
            # Compare and update database table
            unique_cols = ["assembly_id", "sample_id", "sample_type", "fastq_1", "fastq_2"] if "ILLUMINA" in instrument.upper() else ["assembly_id", "barcode", "sample_id", "sample_type", "fastq"]
            compare_and_update_db_table(
                unique_cols = unique_cols,
                compare_tbl = samplesheet_tbl,
                db_tbl = db_samplesheet_tbl,
                db_tbl_name = "ont_samplesheet" if "ONT" in instrument.upper() else "illumina_samplesheet"
            )   
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    # Whether to return database table
    if return_tbl:
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["ont_samplesheet" if "ONT" in instrument.upper() else "illumina_samplesheet"],
            return_var = ["*"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )  
        return db_samplesheet_tbl
    else:
        return None

# Define function to delete a single sample row from the samplesheet in the database
def delete_sample_from_run(
    run_name: str,
    experiment_type: str,
    sample_id: str,
    fastq: Optional[str] = None,
    fastq_1: Optional[str] = None,
    fastq_2: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        # Extract instrument type from experiment_type
        instrument = experiment_type.split("-")[-1]

        # Get assembly_id for this run from the database
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        if db_assembly_tbl.is_empty():
            raise ValueError(f"Run '{run_name}' not found in database.")
        assembly_id = db_assembly_tbl.select("assembly_id").to_series()[0]

        # Delete the matching sample row from the appropriate samplesheet table
        if "ONT" in instrument.upper():
            if not fastq:
                raise ValueError("'fastq' is required to delete a sample from an ONT samplesheet.")
            delete_val_in_database(
                db_tbl_name = ["ont_samplesheet"],
                delete_coln_var = ["assembly_id", "sample_id", "fastq"],
                delete_coln_val = {"assembly_id": [assembly_id], "sample_id": [sample_id], "fastq": [fastq]},
                delete_var_by = ["AND", "AND"]
            )
        elif "ILLUMINA" in instrument.upper():
            if not fastq_1 or not fastq_2:
                raise ValueError("'fastq_1' and 'fastq_2' are required to delete a sample from an Illumina samplesheet.")
            delete_val_in_database(
                db_tbl_name = ["illumina_samplesheet"],
                delete_coln_var = ["assembly_id", "sample_id", "fastq_1", "fastq_2"],
                delete_coln_val = {"assembly_id": [assembly_id], "sample_id": [sample_id], "fastq_1": [fastq_1], "fastq_2": [fastq_2]},
                delete_var_by = ["AND", "AND", "AND"]
            )
        else:
            raise ValueError(f"Unsupported experiment type: {experiment_type}")

        # Return
        return {
            "status": "success",
            "message": f"Sample '{sample_id}' has been removed from run '{run_name}'.",
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

# Look up a run's assembly row, and raise if it's missing or has a pipeline in progress
def _get_editable_assembly_row(run_name: str, experiment_type: str, action: str) -> Dict[str, Any]:
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name", "experiment_type"],
        filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
        filter_var_by = ["AND", "AND"]
    )
    if db_assembly_tbl.is_empty():
        raise ValueError(f"Run '{run_name}' not found in database.")
    assembly_row = db_assembly_tbl.row(0, named=True)
    if assembly_row.get("assembly_status") == "PROCESSING":
        raise ValueError(
            f"Run '{run_name}' has a pipeline in progress. Please wait for it to finish or cancel it before {action} it."
        )
    return assembly_row

# Define function to rename an existing MIRA run (database record + on-disk run directory)
def rename_mira_run(
    run_name: str,
    experiment_type: str,
    new_run_name: str,
) -> Dict[str, Any]:
    try:
        new_run_name = new_run_name.strip().replace(" ", "_")
        if not new_run_name:
            raise ValueError("'new_run_name' cannot be empty.")
        if new_run_name.lower() == run_name.lower():
            raise ValueError("'new_run_name' must be different from the current run name (case-insensitive).")

        # Extract pathogen and instrument type from experiment_type
        pathogen   = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]

        # Look up the run to rename, rejecting the request if it's currently processing
        assembly_tbl = _get_editable_assembly_row(run_name, experiment_type, "renaming")

        # Reject if a run with the new name already exists for this experiment type
        existing_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [new_run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND", "AND"]
        )
        if not existing_tbl.is_empty():
            raise ValueError(f"A run named '{new_run_name}' already exists for experiment type '{experiment_type}'.")

        # Rename the on-disk run directory first — if this fails the database is left untouched
        alias_name = assembly_tbl.get("alias_name", run_name)
        old_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name)
        new_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, new_run_name)

        # If new_dir already exists, remove it first, then move old_dir to new_dir
        if os.path.exists(old_dir):
            if os.path.exists(new_dir):
                shutil.rmtree(new_dir)
            shutil.move(old_dir, new_dir)

        # Update the run_name in the assembly table
        update_tbl_in_database(
            db_tbl_name = ["assembly"],
            table = pl.DataFrame({"run_name": [new_run_name], "alias_name": [alias_name]}),
            filter_coln_var  = ["run_name", "experiment_type"],
            filter_coln_val  = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by    = ["AND"]
        )
        # Return status
        return {
            "status":   "success",
            "message":  f"Run '{run_name}' has been renamed to '{new_run_name}'.",
            "run_name": new_run_name,
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

# Define function to delete an existing MIRA run's database record (files on disk are kept)
def delete_mira_run(
    run_name: str,
    experiment_type: str,
) -> Dict[str, Any]:
    try:
        # Extract pathogen and instrument type from experiment_type
        pathogen   = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]        

        # Look up the run to delete, rejecting the request if it's currently processing
        assembly_tbl = _get_editable_assembly_row(run_name, experiment_type, "deleting")

        # Reject if the run to delete does not exist
        if assembly_tbl.get("run_name", None) is None:
            raise ValueError(f"A run named '{run_name}' does not exist for experiment type '{experiment_type}'.")

        # Remove the on-disk run directory (FASTQs + outputs) first — if this fails the database is left untouched.
        run_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name)
        if os.path.exists(run_dir):
            shutil.rmtree(run_dir)

        # Delete the assembly row from the database
        delete_val_in_database(
            db_tbl_name = ["assembly"],
            delete_coln_var = ["run_name", "experiment_type"],
            delete_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
            delete_var_by = ["AND"]
        )
        # Return status
        return {
            "status":  "success",
            "message": f"Run '{run_name}' has been removed from the database.",
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

# Define function to copy an existing MIRA run — database record, samplesheet, and on-disk files — under a new name
def copy_mira_run(
    run_name: str,
    experiment_type: str,
    new_run_name: str,
) -> Dict[str, Any]:
    try:
        new_run_name = new_run_name.strip().replace(" ", "_")
        if not new_run_name:
            raise ValueError("'new_run_name' cannot be empty.")
        if new_run_name.lower() == run_name.lower():
            raise ValueError("'new_run_name' must be different from the current run name (case-insensitive).")

        # Extract pathogen and instrument type from experiment_type
        pathogen   = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]

        # Look up the run to copy, rejecting the request if it's currently processing
        assembly_tbl = _get_editable_assembly_row(run_name, experiment_type, "copying")
        old_assembly_id = assembly_tbl.get("assembly_id")

        # Reject if a run with the new name already exists for this experiment type
        existing_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [new_run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        if not existing_tbl.is_empty():
            raise ValueError(f"A run named '{new_run_name}' already exists for experiment type '{experiment_type}'.")

        # Copy the on-disk run directory (FASTQs + outputs) first — if this fails the database is left untouched.
        # Nextflow's "work" and ".nextflow" dirs hold transient execution state (often broken
        # symlinks to staged-in files), so they're skipped rather than duplicated.
        alias_name = assembly_tbl.get("alias_name", run_name)
        old_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name)
        new_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, new_run_name)
        if os.path.exists(old_dir):
            if os.path.exists(new_dir):
                shutil.rmtree(new_dir)
            shutil.copytree(old_dir, new_dir, ignore=shutil.ignore_patterns("work", ".nextflow"))

        # Insert a copy of the assembly row under the new run_name
        new_assembly_row = {k: v for k, v in assembly_tbl.items() if k != "assembly_id"}
        new_assembly_row["run_name"] = new_run_name
        new_assembly_row["alias_name"] = alias_name
        insert_tbl_to_database(
            db_tbl_name = ["assembly"],
            table = pl.DataFrame([new_assembly_row])
        )

        # Look up the newly inserted assembly_id
        new_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name = ["assembly"],
            return_var = ["*"],
            filter_coln_var = ["run_name", "experiment_type"],
            filter_coln_val = {"run_name": [new_run_name], "experiment_type": [experiment_type]},
            filter_var_by = ["AND"]
        )
        new_assembly_id = new_assembly_tbl.select("assembly_id").to_series()[0]

        # Copy the samplesheet rows under the new assembly_id
        samplesheet_tbl_name = "ont_samplesheet" if "ONT" in instrument.upper() else "illumina_samplesheet"
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = [samplesheet_tbl_name],
            return_var = ["*"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [old_assembly_id]},
            filter_var_by = ["AND"]
        )
        if not db_samplesheet_tbl.is_empty():
            new_samplesheet_tbl = db_samplesheet_tbl.with_columns(pl.lit(new_assembly_id).alias("assembly_id"))
            insert_tbl_to_database(
                db_tbl_name = [samplesheet_tbl_name],
                table = new_samplesheet_tbl
            )
        # Return status
        return {
            "status":   "success",
            "message":  f"Run '{run_name}' has been copied to '{new_run_name}'.",
            "run_name": new_run_name,
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

# Define function to run MIRA pipeline
def create_mira_run(
    run_name: str,
    experiment_type: str,
    assembly_tbl: pl.DataFrame,
    samplesheet_tbl: pl.DataFrame,
) -> Dict[str, Any]:
    try:
        # Update the assembly and samplesheet tables in database
        db_assembly_tbl = update_assembly_in_database(
            run_name = run_name, 
            experiment_type = experiment_type,
            assembly_tbl = assembly_tbl, 
            return_tbl = True
        )
        # Update the samplesheet table in database
        db_samplesheet_tbl = update_samplesheet_in_database(
            run_name = run_name, 
            experiment_type = experiment_type, 
            samplesheet_tbl = samplesheet_tbl, 
            return_tbl = True
        )
        # Return
        return {
            "status":  "success",
            "message": f"Run '{run_name}' has been successfully created.",
            "assembly_info": db_assembly_tbl.to_dicts(),
            "samplesheet": db_samplesheet_tbl.to_dicts(),
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))   
    
# Define function to launch MIRA-NF docker pipeline
def run_mira_docker(
    run_name: str,
    experiment_type: str, 
) -> Dict[str, Any]:
    try:
        # Pull assembly info from DB
        db_assembly_tbl = lookup_tbl_in_database(
            db_tbl_name     = ["assembly"],
            return_var       = ["*"],
            filter_coln_var  = ["run_name", "experiment_type"],
            filter_coln_val  = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by    = ["AND"]
        )

        # Check if assembly info exists in DB
        if db_assembly_tbl.is_empty():
            raise ValueError(f"No assembly found for run_name '{run_name}' and experiment_type '{experiment_type}'.")        

        # Extract assembly_id from assembly info
        assembly_row  = db_assembly_tbl.row(0, named=True)
        assembly_id   = assembly_row.get("assembly_id", 0)

        # Guard against launching a second pipeline for a run that is already
        # in-flight — this would otherwise wipe the shared output directory
        # (see _remove_previous_pipeline_outputs below) out from under the
        # first, still-running process, corrupting the trace/DAG files and
        # leaving an orphaned process that "Cancel Run" can't reach.
        if assembly_row.get("assembly_status") == "PROCESSING":
            raise ValueError(
                f"Run '{run_name}' already has a pipeline in progress. "
                "Please wait for it to finish or cancel it before starting a new run."
            )

        # Update run to PROCESSING in the assembly table to prevent multiple pipelines from running for the same run
        update_tbl_in_database(
            db_tbl_name = ["assembly"],
            table = pl.DataFrame({"alias_name": [run_name], "assembly_status": ["PROCESSING"]}),
            filter_coln_var  = ["assembly_id"],
            filter_coln_val  = {"assembly_id": [assembly_id]},
            filter_var_by    = ["AND"]
        )

        # Extract pathogen and instrument type from experiment_type
        pathogen  = experiment_type.split("-")[0]
        instrument = experiment_type.split("-")[-1]

        # Extract primer, subsample_reads, parquet_files, and nextclade from assembly_row
        if pathogen.lower() == "sc2" and instrument.lower() == "illumina":
            primer = assembly_row.get("sc2_primer", None)
        elif pathogen.lower() == "rsv" and instrument.lower() == "illumina":
            primer = assembly_row.get("rsv_primer", None)
        else:
            primer = None
        subsample_reads = assembly_row.get("subsample_reads", 0)
        parquet_files = _as_bool(assembly_row.get("parquet_files", False))
        nextclade = _as_bool(assembly_row.get("nextclade", True))

        # Extract custom primer from assembly_row
        custom_primers = _as_bool(assembly_row.get("custom_primers", None))

        # If a custom primer is provided, extract the primer_kmer_len and primer_restrict_window as well
        if custom_primers:
            primer_kmer_len = assembly_row.get("primer_kmer_len", None)
            primer_restrict_window = assembly_row.get("primer_restrict_window", None)

        # Get custom irma config and qc settings from assembly_row
        custom_irma_config = _as_bool(assembly_row.get("custom_irma_config", None))
        custom_qc_settings  = _as_bool(assembly_row.get("custom_qc_settings", None))

        # Get IRMA module from assembly_row ("" / None / "none" => built-in FLU default)
        irma_module = assembly_row.get("irma_module", None)

        # Pull samplesheet from DB (Keep rows only)
        if "ONT" in instrument.upper():
            db_samplesheet_tbl = lookup_tbl_in_database(
                db_tbl_name     = ["ont_samplesheet"],
                return_var       = ["*"],
                filter_coln_var  = ["assembly_id"],
                filter_coln_val  = {"assembly_id": [assembly_id]},
                filter_var_by    = ["AND"]
            )
            keep_samplesheet_rows = db_samplesheet_tbl.filter(pl.col("status") == "Keep")
        else:
            db_samplesheet_tbl = lookup_tbl_in_database(
                db_tbl_name     = ["illumina_samplesheet"],
                return_var       = ["*"],
                filter_coln_var  = ["assembly_id"],
                filter_coln_val  = {"assembly_id": [assembly_id]},
                filter_var_by    = ["AND"]
            )
            keep_samplesheet_rows = db_samplesheet_tbl.filter(pl.col("status") == "Keep")

        # Check if samplesheet has rows to process
        if keep_samplesheet_rows.is_empty():
            raise ValueError(f"No samples with status 'Keep' found in the samplesheet for run '{run_name}'.")
        
        # Define the run directory for the pipeline and create it if it doesn't exist
        run_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name)                   
        os.makedirs(run_dir, exist_ok=True)

        # Define the output directory for the pipeline outputs and create it if it doesn't exist       
        output_dir = os.path.join(run_dir, "outputs")
        os.makedirs(output_dir, exist_ok=True)

        # Remove previous pipeline outputs from the current run directory
        _remove_previous_pipeline_outputs(run_dir=run_dir)

        # Create the samplesheet CSV file based on instrument type
        samplesheet_path = os.path.join(run_dir, "samplesheet.csv")
        if "ONT" in instrument.upper():
            keep_samplesheet_rows.select(["barcode", "sample_id", "sample_type"]).unique().write_csv(samplesheet_path)
        elif "ILLUMINA" in instrument.upper():
            keep_samplesheet_rows.select(["sample_id", "sample_type"]).unique().write_csv(samplesheet_path)

        # Reset permissions on the run directory after the pipeline finishes
        permission_cleanup = (
            'status=$?; '
            'chown -R "$HOST_UID:$HOST_GID" "$CONTAINER_RUN_DIR" || true; '
            'chmod -R g+rwX "$CONTAINER_RUN_DIR" || true; '
            'find "$CONTAINER_RUN_DIR" -type d -exec chmod g+s {} + || true; '
            'exit "$status"'
        )

        # Set up Nextflow command and parameters 
        cmd = [
            "nextflow", "run", "/MIRA-NF/main.nf",
            "-profile", "mira_nf_container",
            "--check_version", "false",
            "--input",   samplesheet_path,
            "--runpath", run_dir,
            "--outdir",  output_dir,
            "--e",       experiment_type,
        ]

        # If running locally, the pipeline will be run through a Docker container; 
        # Otherwise, the pipeline will be run within a container environment
        if _DEPLOY_TYPE == "Local":
            cmd.extend([
                "docker", "run", "--privileged",
                "-v", f"{_DEFAULT_DATA_STORAGE_PATH}:/data",
                "-w", run_dir,
                "-e", f"HOST_UID={os.getuid()}",
                "-e", f"HOST_GID={os.getgid()}",
                "-e", f"CONTAINER_RUN_DIR={run_dir}",
                _MIRA_NF_IMAGE,
                "bash", "-c", f'trap "{permission_cleanup}" EXIT; "$@"', "--",
            ])

        # Add primer, subsample_reads, parquet_files, and nextclade options to the command if specified
        if primer:
            cmd.extend(["--p", primer])
        if custom_primers:
            container_custom_primer_file = f"{run_dir}/{CUSTOM_PRIMER_CONFIG_FILENAME}"
            cmd.extend(["--custom_primers", container_custom_primer_file])
            if primer_kmer_len:
                cmd.extend(["--primer_kmer_len", str(primer_kmer_len)])
            if primer_restrict_window:
                cmd.extend(["--primer_restrict_window", str(primer_restrict_window)])
        if subsample_reads and int(subsample_reads) >= 0:
            cmd.extend(["--subsample_reads", str(int(subsample_reads))])
        # Pass a specific IRMA module when selected; "" / None / "none" / "flu" uses the built-in FLU default
        if irma_module and str(irma_module).strip().lower() not in ("", "none", "flu"):
            cmd.extend(["--irma_module", str(irma_module).strip()])
        if custom_irma_config:
            container_custom_irma_config_file = f"{run_dir}/{CUSTOM_IRMA_CONFIG_FILENAME}"
            cmd.extend(["--custom_irma_config", container_custom_irma_config_file])
        if custom_qc_settings:
            container_custom_qc_settings_file = f"{run_dir}/{CUSTOM_QC_SETTINGS_FILENAME}"
            cmd.extend(["--custom_qc_settings", container_custom_qc_settings_file])
        if parquet_files:
            cmd.extend(["--parquet_files", "true"])
        if nextclade:
            cmd.extend(["--nextclade", "true"])

        # Log the command for reference
        if _DEPLOY_TYPE == "Local":
            logger.info(
                f"Launching MIRA-NF pipeline for run '{run_name}' with command:\n" +
                f"docker run --privileged\n" +
                f" -v {_DEFAULT_DATA_STORAGE_PATH}:/data\n" +
                f" -w {run_dir}\n" +
                f" -e HOST_UID={os.getuid()}\n" +
                f" -e HOST_GID={os.getgid()}\n" +
                f" -e CONTAINER_RUN_DIR={run_dir}\n" +
                f" {_MIRA_NF_IMAGE}\n" +
                f" bash -c 'trap \"{permission_cleanup}\" EXIT; \"$@\"' --\n" +
                f" nextflow run /MIRA-NF/main.nf\n" +
                f" -profile mira_nf_container\n" +
                f" --check_version false\n" +
                f" --input {samplesheet_path}\n" +
                f" --runpath {run_dir}\n" +
                f" --outdir {output_dir}\n" +
                f" --e {experiment_type}\n" +
                (f" --p {primer}\n" if primer else "") +
                (f" --custom_primers {run_dir}/{CUSTOM_PRIMER_CONFIG_FILENAME}\n" if custom_primers else "") +
                (f" --primer_kmer_len {primer_kmer_len}\n" if custom_primers and primer_kmer_len else "") +
                (f" --primer_restrict_window {primer_restrict_window}\n" if custom_primers and primer_restrict_window else "") +
                (f" --irma_module {str(irma_module).strip()}\n" if irma_module and str(irma_module).strip().lower() not in ("", "none", "flu") else "") +
                (f" --custom_irma_config {run_dir}/{CUSTOM_IRMA_CONFIG_FILENAME}\n" if custom_irma_config else "") +
                (f" --custom_qc_settings {run_dir}/{CUSTOM_QC_SETTINGS_FILENAME}\n" if custom_qc_settings else "") +
                (f" --subsample_reads {int(subsample_reads)}\n" if subsample_reads and int(subsample_reads) >= 0 else "") +
                (f" --parquet_files true\n" if parquet_files else "") +
                (f" --nextclade true\n" if nextclade else ""),
            )
        else:
            logger.info(
                f"Launching MIRA-NF pipeline for run '{run_name}' with command:\n" +
                f"nextflow run /MIRA-NF/main.nf\n" +
                f" -profile mira_nf_container\n" +
                f" --check_version false\n" +
                f" --input {samplesheet_path}\n" +
                f" --runpath {run_dir}\n" +
                f" --outdir {output_dir}\n" +
                f" --e {experiment_type}\n" +
                (f" --p {primer}\n" if primer else "") +
                (f" --custom_primers {run_dir}/{CUSTOM_PRIMER_CONFIG_FILENAME}\n" if custom_primers else "") +
                (f" --primer_kmer_len {primer_kmer_len}\n" if custom_primers and primer_kmer_len else "") +
                (f" --primer_restrict_window {primer_restrict_window}\n" if custom_primers and primer_restrict_window else "") +
                (f" --irma_module {str(irma_module).strip()}\n" if irma_module and str(irma_module).strip().lower() not in ("", "none", "flu") else "") +
                (f" --custom_irma_config {run_dir}/{CUSTOM_IRMA_CONFIG_FILENAME}\n" if custom_irma_config else "") +
                (f" --custom_qc_settings {run_dir}/{CUSTOM_QC_SETTINGS_FILENAME}\n" if custom_qc_settings else "") +
                (f" --subsample_reads {int(subsample_reads)}\n" if subsample_reads and int(subsample_reads) >= 0 else "") +
                (f" --parquet_files true\n" if parquet_files else "") +
                (f" --nextclade true\n" if nextclade else ""),
            )

        # Fire and forget — launch in background, do not block. Capture the pipeline's
        # console output (which includes the Nextflow completion summary / "Duration")
        # to a log file in the run directory so the runtime can be parsed later.
        nextflow_stdout_path = os.path.join(run_dir, "nextflow.stdout.log")
        stdout_fh = open(nextflow_stdout_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            cmd,
            cwd=run_dir,
            stdout=stdout_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        # The child has inherited its own copy of the file descriptor; the parent's copy
        # is no longer needed and can be closed safely.
        stdout_fh.close()

        # Return the process ID and command for reference
        return {
            "status":  "success",
            "pid":     proc.pid,
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    
# Return the live Docker client only when the PID belongs to this exact MIRA run.
def _get_mira_process(
    pid: int,
    run_name: str,
    experiment_type: str,
) -> psutil.Process | None:
    
    # Check if the PID is valid and exists
    if pid <= 0 or not psutil.pid_exists(pid):
        return None

    # Check if the process belongs to the MIRA run by verifying the command line arguments
    try:
        proc = psutil.Process(pid)
        if proc.status() == psutil.STATUS_ZOMBIE:
            return None
        return proc
    except psutil.NoSuchProcess:
        return None
    except psutil.AccessDenied as err:
        raise ValueError(f"Unable to verify PID '{pid}' for MIRA run '{run_name}'.") from err

# Check run process so user can interrupt, cancel, or terminate the run if needed
def check_mira_status(
    pid: int,
    run_name: str,
    experiment_type: str
) -> Dict[str, Any]:
    
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name", "experiment_type"],
        filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
        filter_var_by = ["AND", "AND"]
    )

    # Check if assembly for this run_name exists in database
    if db_assembly_tbl.is_empty():
        raise ValueError(f"Run name '{run_name}' does not exist in the database.")
    
    # Get assembly_status from database
    assembly_status = db_assembly_tbl.select("assembly_status").to_series()[0]

    # Check if the process is alive
    proc = _get_mira_process(pid, run_name, experiment_type)

    # Update assembly status based on process state
    if proc is not None:
        assembly_status = "PROCESSING"
        update_tbl_in_database(
            db_tbl_name = ["assembly"],
            table = pl.DataFrame({"assembly_status": [assembly_status]}),
            filter_coln_var  = ["run_name", "experiment_type"],
            filter_coln_val  = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by    = ["AND", "AND"]
        )
        return{
            "status":  "PROCESSING",
            "message": [f"Run '{run_name}' is currently processing."]
        }
    else:
        assembly_status = "COMPLETED" 
        update_tbl_in_database(
            db_tbl_name = ["assembly"],
            table = pl.DataFrame({"assembly_status": [assembly_status]}),
            filter_coln_var  = ["run_name", "experiment_type"],
            filter_coln_val  = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by    = ["AND", "AND"]
        )
        return {
            "status": f"{assembly_status}",
            "message": [f"Run '{run_name}' status is {assembly_status}."],
        }

# Cancel a running MIRA pipeline by killing the process group
def cancel_mira_run(
    pid: int,
    run_name: str,
    experiment_type: str
) -> Dict[str, Any]:
   
    # Get assembly table from database
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name", "experiment_type"],
        filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
        filter_var_by = ["AND", "AND"]
    )

    # Check if assembly for this run_name exists in database
    if db_assembly_tbl.is_empty():
        raise ValueError(f"Run name '{run_name}' does not exist in the database.")  
    
    # If db_assembly_tbl is not empty, check if the process is alive
    proc = _get_mira_process(pid, run_name, experiment_type)

    # If the process is alive, kill the entire process group to terminate the run
    if proc is not None:
        try:
            # Kill the entire process group so child Docker processes are also terminated
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (psutil.NoSuchProcess, ProcessLookupError):
            pass
        # Record an intentional user cancellation separately from a failure.
        update_tbl_in_database(
            db_tbl_name = ["assembly"],
            table = pl.DataFrame({"assembly_status": ["CANCELED"]}),
            filter_coln_var  = ["run_name", "experiment_type"],
            filter_coln_val  = {"run_name": [run_name], "experiment_type": [experiment_type]},
            filter_var_by    = ["AND"]
        )
        return {
            "status":  "canceled",
            "message": [f"Run '{run_name}' has been canceled."]
        }
    else:
        return {
            "status":  "not_running",
            "message": [f"PID '{pid}' does not exist. Run '{run_name}' is probably not running or completed. Nothing to be done."]
        }
    
# Define function to get pipeline DAG structure
def create_mira_dag(
    run_name: str,
    experiment_type: str,
) -> Dict[str, Any]:
    """
    Return workflow-level info (status, timestamps, task counts) and a flat
    list of tasks with their statuses, parsed from the Nextflow trace file and
    mira-nf.log for the given run.
    """
    # Get assembly table from database
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name", "experiment_type"],
        filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
        filter_var_by = ["AND", "AND"]
    )

    # Check if assembly for this run_name exists in database
    if db_assembly_tbl.is_empty():
        raise ValueError(f"Run name '{run_name}' does not exist in the database.")

    # Get assembly status and other workflow-level info from database and storage
    assembly_status = db_assembly_tbl.select("assembly_status").to_series()[0]
    assembly_id = db_assembly_tbl.select("assembly_id").to_series()[0]
    pathogen   = experiment_type.split("-")[0]
    instrument = experiment_type.split("-")[-1]
    run_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name)
    output_dir = os.path.join(run_dir, "outputs")
    nextflow_log = os.path.join(run_dir, ".nextflow.log")
    nextflow_stdout = os.path.join(run_dir, "nextflow.stdout.log")
    pipeline_info_dir = os.path.join(output_dir, "pipeline_info")

    # Runtime already persisted from a previous parse (None for runs that haven't completed)
    db_runtime = db_assembly_tbl.select("runtime").to_series()[0] if "runtime" in db_assembly_tbl.columns else None
    db_finished_at = db_assembly_tbl.select("finished_at").to_series()[0] if "finished_at" in db_assembly_tbl.columns else None

    # Get the actual sample_ids from the samplesheet, so run-level tasks (e.g.
    # CHECKMIRAVERSION (1)) or reference-dataset tasks (e.g. GETNEXTCLADEDATASET
    # (flu_h3n2_na)) aren't mistaken for real samples when counting below
    if "ONT" in instrument.upper():
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["ont_samplesheet"],
            return_var = ["sample_id"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )
    else:
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["illumina_samplesheet"],
            return_var = ["sample_id"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )
    known_sample_ids = set(db_samplesheet_tbl.select("sample_id").to_series().to_list())

    # Define workflow-level metadata dictionary
    workflow: Dict[str, Any] = {
        "run_name":        run_name,
        "experiment_type": experiment_type,
        "status":          assembly_status,
        "started_at":      None,
        "completed_at":    None,
        "tasks_total":     0,
        "tasks_succeeded": 0,
        "tasks_failed":    0,
        "number_of_samples": len(known_sample_ids),
        "number_of_samples_with_failed_tasks": 0,
        "number_of_samples_with_successful_tasks": 0,
        "runtime": db_runtime,
        "finished_at": db_finished_at,
    }

    # Create a placeholder for the message to be returned to the user
    message = []

    # Ordered list of every distinct process that the pipeline will run, parsed
    # from the "Starting process > ..." lines Nextflow emits at launch (before any
    # task is submitted). Lets the UI lay out all task rows up front.
    all_process_names: List[str] = []

    # (process_name, sample) pairs that Nextflow has *submitted* — i.e. the task has
    # started. The execution trace only records a task once it reaches a terminal
    # state (COMPLETED/FAILED) with its metrics, so submitted-but-unfinished tasks are
    # taken from the log to drive the UI's live "running" indicator.
    submitted_pairs: List[tuple] = []

    # ── 1. Parse .nextflow.log for workflow-level metadata ───────────
    if os.path.exists(nextflow_log):
        session_re  = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|\w+-\d+ \d{2}:\d{2}:\d{2}).*Session start")
        complete_re = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|\w+-\d+ \d{2}:\d{2}:\d{2}).*WorkflowStats")
        error_re = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}|\w+-\d+ \d{2}:\d{2}:\d{2}).*ERROR")
        starting_re = re.compile(r"Starting process\s*>\s*(\S+)")
        submitted_re = re.compile(r"\[([a-f0-9]{2}/[a-f0-9]+)\]\s*Submitted process\s*>\s*(\S+)\s*\(([^)]+)\)")
        with open(nextflow_log, errors="replace") as fh:
            for line in fh:
                if workflow["started_at"] is None:
                    m = session_re.search(line)
                    if m:
                        workflow["started_at"] = m.group(1)
                m = complete_re.search(line)
                if m and workflow["completed_at"] is None:
                        workflow["completed_at"] = m.group(1)
                sp = starting_re.search(line)
                if sp:      
                    process_name = sp.group(1).strip().split(":")[-1]
                    if process_name not in all_process_names:
                        all_process_names.append(process_name)
                sub = submitted_re.search(line)
                if sub:
                    sub_hash = sub.group(1).strip()
                    sub_process = sub.group(2).strip().split(":")[-1]
                    sub_sample = sub.group(3).strip()
                    submitted_pairs.append((sub_process, sub_sample, sub_hash))

    elif assembly_status == "CANCELED" and not os.path.exists(nextflow_log):
        message.append(f"MIRA run was canceled or interrupted.")
    elif assembly_status != "PROCESSING" and not os.path.exists(nextflow_log):
        message.append(f"Cannot find Nextflow log file for this run. The log file may have been deleted or moved. Try running MIRA again.")

    # ── 1b. Parse Nextflow stdout for the reported runtime and finish time ──
    # Nextflow prints its completion summary ("Completed at" / "Duration") to stdout,
    # which run_mira_docker captures to nextflow.stdout.log (overwritten each run, so
    # it always reflects the most recent run).
    parsed_runtime = None
    parsed_finished = None
    if os.path.exists(nextflow_stdout):
        ansi_re      = re.compile(r"\x1b\[[0-9;]*m")
        duration_re  = re.compile(r"(?:Execution\s+duration|Duration)\s*:\s*(.+)", re.IGNORECASE)
        completed_re = re.compile(r"Completed\s+at\s*:\s*(.+)", re.IGNORECASE)
        with open(nextflow_stdout, errors="replace") as fh:
            for line in fh:
                clean = ansi_re.sub("", line)
                d = duration_re.search(clean)
                if d:
                    parsed_runtime = d.group(1).strip()
                c = completed_re.search(clean)
                if c:
                    parsed_finished = c.group(1).strip()

    # The pipeline routes its "Completed at:" summary to the notification email rather
    # than stdout, so stdout rarely carries a finish time. Fall back to the completion
    # timestamp parsed from .nextflow.log's "Workflow completed" (WorkflowStats) line.
    if not parsed_finished and workflow.get("completed_at"):
        parsed_finished = workflow["completed_at"]

    if parsed_runtime:
        workflow["runtime"] = parsed_runtime
    if parsed_finished:
        workflow["finished_at"] = parsed_finished

    # Persist any new values to the DB so they survive log cleanup
    updates = {}
    if parsed_runtime and parsed_runtime != db_runtime:
        updates["runtime"] = parsed_runtime
    if parsed_finished and parsed_finished != db_finished_at:
        updates["finished_at"] = parsed_finished
    if updates:
        try:
            update_tbl_in_database(
                db_tbl_name = ["assembly"],
                table = pl.DataFrame({k: [v] for k, v in updates.items()}),
                filter_coln_var = ["assembly_id"],
                filter_coln_val = {"assembly_id": [assembly_id]},
                filter_var_by = ["AND"]
            )
        except Exception as err:
            # Persisting runtime/finish time is best-effort; never fail the DAG response over it
            logger.warning(f"Failed to persist runtime/finish time for run '{run_name}': {err}")

    # ── 2. Find the latest trace file ──────────────────────────────
    trace_file: Optional[str] = None
    if os.path.isdir(pipeline_info_dir):
        candidates = sorted(
            (f for f in os.listdir(pipeline_info_dir)
             if f.startswith("execution_trace_") and f.endswith(".txt")),
            reverse=True,
        )
        if candidates:
            trace_file = os.path.join(pipeline_info_dir, candidates[0])
  
    # ── 3. Parse trace file for per-task details ────────────────────
    tasks: List[Dict[str, Any]] = []; 
    if trace_file is not None:
        with open(trace_file, errors="replace") as fh:
            header = fh.readline().strip().split("\t")
            col = {name: i for i, name in enumerate(header)}
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if len(parts) < len(col):
                    continue
                full_name = parts[col.get("name", 3)].strip()
                # Split "PROCESS_PATH (sample)" → process_path, sample
                sample_m     = re.match(r"^(.+?)\s*\(([^)]+)\)\s*$", full_name)
                process_path = sample_m.group(1).strip() if sample_m else full_name
                sample       = sample_m.group(2).strip() if sample_m else None
                process_name = process_path.split(":")[-1]
                tasks.append({
                    "task_id":      int(parts[col.get("task_id", 0)] or 0),
                    "hash":         parts[col.get("hash", 1)].strip() if "hash" in col else "",
                    "process_name": process_name,
                    "sample":       sample,
                    "status":       parts[col.get("status", 4)].strip(),
                    "exit_code":    parts[col.get("exit", 5)].strip(),
                })
        # Sort tasks by task_id to ensure consistent ordering
        tasks.sort(key=lambda t: t["task_id"])
    elif assembly_status == "CANCELED" and trace_file is None:
        message.append(f"MIRA run was canceled or interrupted.")
    elif assembly_status != "PROCESSING" and trace_file is None:
        message.append(f"Cannot find execution trace file for this run. The trace file may have been deleted or moved. Try running MIRA again.")

    # ── 3b. Add live "running" tasks for submitted-but-unfinished work ──
    # While the run is still processing, surface tasks Nextflow has submitted but that
    # haven't reached a terminal state yet (so they're absent from the trace) as
    # RUNNING, giving each started task-sample cell a live spinner in the UI.
    if assembly_status == "PROCESSING":
        terminal_keys = {(t["process_name"], t["sample"]) for t in tasks}
        seen_running = set()
        for proc, smp, hsh in submitted_pairs:
            key = (proc, smp)
            if key in terminal_keys or key in seen_running:
                continue
            seen_running.add(key)
            tasks.append({
                "task_id":      -1,
                "hash":         hsh,
                "process_name": proc,
                "sample":       smp,
                "status":       "RUNNING",
                "exit_code":    "-",
            })

    # ── 4. Infer completion from trace tasks if DB status is stale ──
    # Covers the case where check_mira_status failed to update the DB
    sample_status: Dict[str, str] = {}    
    if os.path.exists(nextflow_log) and len(tasks) > 0 and workflow["status"] == "COMPLETED":
        has_failed = [t for t in tasks if t.get("status") != "COMPLETED"]
        workflow["status"] = "FAILED" if len(has_failed) > 0 else "COMPLETED"
        # Update workflow-level task counts
        workflow["tasks_total"] = len(tasks)
        if workflow["tasks_succeeded"] == 0 and workflow["tasks_failed"] == 0:
            workflow["tasks_succeeded"] = sum(1 for t in tasks if t["exit_code"] == "0")
            workflow["tasks_failed"]    = sum(1 for t in tasks if t["exit_code"] != "0")
        # Update workflow-level sample counts (restricted to known samples from
        # the samplesheet, so singleton/reference-dataset tasks aren't counted)
        for t in tasks:
            if t["sample"] is not None and t["sample"] in known_sample_ids:
                if t["sample"] not in sample_status and t["process_name"] == "PASSFAILED":
                    sample_status[t["sample"]] = "FAILED"
        # Check if any known samples were not present in the trace file and mark them as "FAILED"
        for sample_id in known_sample_ids:
            if sample_id not in sample_status and workflow["status"] == "COMPLETED":
                sample_status[sample_id] = "PASSED"
            else:
                sample_status[sample_id] = "FAILED"
        workflow["number_of_samples_with_failed_tasks"] = sum(1 for s in sample_status.values() if s == "FAILED")
        workflow["number_of_samples_with_successful_tasks"] = sum(1 for s in sample_status.values() if s == "PASSED")        

    # Return workflow-level info and task list
    return {
        "workflows": workflow,
        "tasks":    tasks,
        "process_names": all_process_names,
        "sample_ids": sorted(known_sample_ids),
        "message":   message
    }

# Define function to retrieve the error log for a single failed task
def retrieve_task_log(
    run_name: str,
    experiment_type: str,
    task_hash: str,
    stream: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Locate the Nextflow work directory for a single task (identified by its
    execution-trace hash, e.g. "9f/df6545") and return its log with the
    relative path, filename, exit code, and the error lines with line numbers.

    When ``stream`` is "stdout", the process output (.command.out / .command.log)
    is preferred; otherwise the error log (.command.err) is preferred.
    """
    if not task_hash or "/" not in task_hash:
        raise ValueError("A valid task hash (e.g. '9f/df6545') is required.")

    pathogen   = experiment_type.split("-")[0]
    instrument = experiment_type.split("-")[-1]
    run_dir = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name)
    work_dir = os.path.join(run_dir, "work")

    # The trace hash is truncated ("<a>/<short>"); the real directory name starts with it.
    prefix, rest = task_hash.split("/", 1)
    parent = os.path.join(work_dir, prefix)
    task_dir: Optional[str] = None
    if os.path.isdir(parent):
        for name in os.listdir(parent):
            if name.startswith(rest):
                task_dir = os.path.join(parent, name)
                break

    if task_dir is None or not os.path.isdir(task_dir):
        raise ValueError(f"Could not find the work directory for task '{task_hash}'. It may have been cleaned up.")

    # Read the exit code if present
    exit_code: Optional[str] = None
    exitcode_path = os.path.join(task_dir, ".exitcode")
    if os.path.exists(exitcode_path):
        try:
            with open(exitcode_path, errors="replace") as fh:
                exit_code = fh.read().strip()
        except Exception:
            exit_code = None

    # Prefer .command.err; fall back to .command.log. Return the file's lines with
    # 1-based line numbers, and flag the ones that look like errors.
    error_re = re.compile(r"error|exception|traceback|fail|not found|no such file|command not found|killed", re.IGNORECASE)
    chosen_file: Optional[str] = None
    if (stream or "").lower() == "stdout":
        candidates = (".command.out", ".command.log", ".command.err")
    else:
        candidates = (".command.err", ".command.log", ".command.out")
    for candidate in candidates:
        candidate_path = os.path.join(task_dir, candidate)
        if os.path.exists(candidate_path) and os.path.getsize(candidate_path) > 0:
            chosen_file = candidate
            break

    lines: List[Dict[str, Any]] = []
    error_lines: List[Dict[str, Any]] = []
    if chosen_file is not None:
        log_full_path = os.path.join(task_dir, chosen_file)
        with open(log_full_path, errors="replace") as fh:
            for i, raw in enumerate(fh, start=1):
                text = raw.rstrip("\n")
                entry = {"line_number": i, "text": text}
                lines.append(entry)
                if error_re.search(text):
                    error_lines.append(entry)
        # Keep the payload reasonable: cap the returned lines.
        if len(lines) > 500:
            lines = lines[-500:]
    else:
        chosen_file = candidates[0]

    rel_log_path = os.path.relpath(os.path.join(task_dir, chosen_file), run_dir)

    return {
        "task_hash":   task_hash,
        "log_file":    chosen_file,
        "log_path":    rel_log_path,
        "work_dir":    os.path.relpath(task_dir, run_dir),
        "exit_code":   exit_code,
        "error_lines": error_lines,
        "lines":       lines,
    }

# Define function to extract per-sample pass/fail status from the Nextflow execution log
def get_sample_workflow_status(
    run_name: str,
    experiment_type: str,
) -> Dict[str, Any]:
    """
    Parse the .nextflow.log file for a given run and determine, on a
    per-sample basis, whether every per-sample task in the workflow completed
    successfully ("PASSED") or whether at least one task failed ("FAILED").

    Only tasks whose Nextflow process name is suffixed with "(sample_id)"
    (e.g. "CDCGOV_MIRA_NF:MIRA:flu_o:IRMA (sample_1)") are considered
    per-sample tasks; run-level tasks (e.g. CHECKMIRAVERSION) are ignored.
    """
    # Get pathogen and instrument type from experiment_type, and locate the log file
    pathogen     = experiment_type.split("-")[0]
    instrument   = experiment_type.split("-")[-1]
    run_dir      = os.path.join(_DEFAULT_MIRA_STORAGE_PATH, pathogen, instrument, run_name)
    nextflow_log = os.path.join(run_dir, ".nextflow.log")

    # Check if the .nextflow.log file exists for this run
    if not os.path.exists(nextflow_log):
        raise ValueError(f"No .nextflow.log file found for run '{run_name}'.")

    # Get assembly table from database
    db_assembly_tbl = lookup_tbl_in_database(
        db_tbl_name = ["assembly"],
        return_var = ["*"],
        filter_coln_var = ["run_name", "experiment_type"],
        filter_coln_val = {"run_name": [run_name], "experiment_type": [experiment_type]},
        filter_var_by = ["AND"]
    )
    if db_assembly_tbl.is_empty():
        raise ValueError(f"Run name '{run_name}' does not exist in the database.")
    assembly_id = db_assembly_tbl.select("assembly_id").to_series()[0]

    # Get the actual sample_ids from the samplesheet, so run-level tasks (e.g.
    # CHECKMIRAVERSION (1)) or reference-dataset tasks (e.g. GETNEXTCLADEDATASET
    # (flu_h3n2_na)) aren't mistaken for real samples
    if "ONT" in experiment_type.upper():
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["ont_samplesheet"],
            return_var = ["sample_id"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )
    else:
        db_samplesheet_tbl = lookup_tbl_in_database(
            db_tbl_name = ["illumina_samplesheet"],
            return_var = ["sample_id"],
            filter_coln_var = ["assembly_id"],
            filter_coln_val = {"assembly_id": [assembly_id]},
            filter_var_by = ["AND"]
        )
    known_sample_ids = set(db_samplesheet_tbl.select("sample_id").to_series().to_list())

    # Regex to match a completed-task log line, e.g.:
    # "Task completed > TaskHandler[id: 14; name: PATH (sample_1); status: COMPLETED; exit: 0; error: -; workDir: ...]"
    task_re = re.compile(
        r"Task completed > TaskHandler\[id:\s*(\d+);\s*name:\s*(.+?);\s*status:\s*(\w+);\s*exit:\s*(-?\d+|-);"
    )
    # Regex to split "PROCESS_PATH (sample)" into process_path and sample
    sample_re = re.compile(r"^(.+?)\s*\(([^)]+)\)\s*$")

    # Track pass/fail state per sample
    samples: Dict[str, Dict[str, Any]] = {}

    with open(nextflow_log, errors="replace") as fh:
        for line in fh:
            m = task_re.search(line)
            if not m:
                continue
            full_name = m.group(2).strip()
            status    = m.group(3).strip()
            exit_code = m.group(4).strip()

            # Skip run-level tasks that are not tied to a specific known sample
            sample_m = sample_re.match(full_name)
            if not sample_m:
                continue
            process_path = sample_m.group(1).strip()
            sample_id    = sample_m.group(2).strip()
            if sample_id not in known_sample_ids:
                continue
            process_name = process_path.split(":")[-1]

            # A task is considered successful only if it completed with exit code 0
            task_passed = status == "COMPLETED" and exit_code == "0"

            # Initialize sample entry on first sighting, then downgrade to FAILED if needed
            entry = samples.setdefault(sample_id, {"status": "PASSED", "failed_steps": []})
            if not task_passed:
                entry["status"] = "FAILED"
                entry["failed_steps"].append({
                    "process_name": process_name,
                    "status":       status,
                    "exit_code":    exit_code,
                })

    # Any known sample that never appears in the log had no per-sample task
    # recorded at all — treat it as failed (e.g. excluded before task submission,
    # or the pipeline crashed before reaching it)
    for sample_id in known_sample_ids - samples.keys():
        samples[sample_id] = {
            "status": "FAILED",
            "failed_steps": [{
                "process_name": None,
                "status":       "NOT_RUN",
                "exit_code":    None,
            }],
        }

    # Split samples into passed / failed lists
    passed_samples = sorted(s for s, info in samples.items() if info["status"] == "PASSED")
    failed_samples = sorted(s for s, info in samples.items() if info["status"] == "FAILED")

    return {
        "run_name":        run_name,
        "experiment_type": experiment_type,
        "passed_samples":  passed_samples,
        "failed_samples":  failed_samples,
        "samples":         samples,
    }