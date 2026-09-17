# Import future annotations for Pydantic models
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any, Tuple

# Import polars
import polars as pl

# Import general python packages
import os
import re
import yaml
import shutil
import csv
import tempfile
import subprocess
from datetime import date
from threading import Lock

# Import shared logger (INFO/DEBUG -> stdout, WARNING/ERROR/CRITICAL -> stderr)
from .logging_config import logger

# Import local schema modules
from .schema_validator import (
    _DEFAULT_SEQSENDER_STORAGE_PATH,
    CONFIG_FILENAME,
    METADATA_FILENAME,
    FASTA_FILENAME,
    GFF_FILENAME,
    TABLE2ASN_FILENAME,
    SUBMISSION_LOG_FILENAME,
    SUBMISSION_STATUS_REPORT_FILENAME,
    CONFIG_TEMPLATE_PATH,
    SEQSENDER_DATABASE_ALIASES,
    SEQSENDER_STATUS_MAP,
    database_prefixes,
    validate_tbl,
    biosample_packages,
    submitter_db_schema,
    submitter_pa_schema,
    submission_db_schema,
    submission_pa_schema,
    submission_log_pa_schema,
    submission_status_report_pa_schema,
)

# Import local sqlite modules
from .sqlite_handler import (
    lookup_tbl_in_database,
    insert_tbl_to_database,
    update_tbl_in_database,
    delete_val_in_database,
)

# Import local utils
from .utils import (
    _cast_expr,
    compare_and_update_db_table,
)

# Global dictionaries and lock for managing SeqSender processes and their terminal results.
_SEQSENDER_PROCESSES: Dict[int, Dict[str, Any]] = {}
_SEQSENDER_TERMINAL_RESULTS: Dict[int, Dict[str, Any]] = {}
_SEQSENDER_PROCESS_LOCK = Lock()
_MAX_TERMINAL_RESULTS = 256

# Locate the SeqSender CLI entrypoint and its isolated Micromamba Python interpreter.
def _seqsender_cli_paths() -> Tuple[str, str]:
    seqsender_dir = os.environ.get("SEQSENDER_DIR", "/seqsender")
    seqsender_script = os.path.join(seqsender_dir, "seqsender.py")
    mamba_root_prefix = os.environ.get("MAMBA_ROOT_PREFIX", "/opt/conda")
    seqsender_python = os.path.join(mamba_root_prefix, "envs", "seqsender", "bin", "python")
    if not os.path.isfile(seqsender_python):
        raise FileNotFoundError(f"SeqSender Python interpreter '{seqsender_python}' does not exist.")
    if not os.path.isfile(seqsender_script):
        raise FileNotFoundError(f"SeqSender executable '{seqsender_script}' does not exist.")
    return seqsender_python, seqsender_script

def _get_seqsender_version() -> str:
    seqsender_python, seqsender_script = _seqsender_cli_paths()
    result = subprocess.run(
        [seqsender_python, seqsender_script, "version"],
        capture_output=True,
        text=True,
        check=True
    )
    # SeqSender's stdout wraps the version in extra text (e.g. "SeqSender version 1.2.3"), so
    # pull out just the dotted version number.
    version_match = re.search(r"\d+\.\d+\.\d+", result.stdout)

    # Return version if match found, otherwise return a default "0.0.0"
    return version_match.group(0) if version_match else "0.0.0"

# Function to generate a unique identity for a SeqSender process based on submission details.
def _seqsender_process_identity(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
) -> Tuple[str, str, Tuple[str, ...], str]:
    return submission_name, organism, tuple(sorted(database)), submission_type


# Function to normalize the database name for SeqSender submissions.
def _normalize_seqsender_database(database: str) -> str:
    normalized_database = database.strip().upper()
    return SEQSENDER_DATABASE_ALIASES.get(normalized_database, normalized_database)


# Function to build the database name written by SeqSender to its submission log.
def _seqsender_log_database(database: str, table2asn: bool) -> str:
    normalized_database = _normalize_seqsender_database(database)
    if normalized_database == "GENBANK":
        submission_method = "TABLE2ASN" if table2asn else "FTP"
        return f"{normalized_database}-{submission_method}"
    return normalized_database


# Function to read and parse the submission log of a SeqSender process.
def _read_submission_log(
    submission_log_file: str,
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
    table2asn: bool = False,
) -> Dict[str, Dict[str, str]]:

    # Normalize the requested databases to ensure consistent comparison with the submission log.
    requested_databases = list(dict.fromkeys(
        _normalize_seqsender_database(target_database)
        for target_database in database
    ))

    # Read and validate the submission log table.
    submission_log_tbl = pl.read_csv(submission_log_file)
    submission_log_tbl = validate_tbl(submission_log_tbl, submission_log_pa_schema, "submission_log")

    # Place holder to track databases that are missing from the submission log.
    missing_databases = []
    database_statuses: Dict[str, Dict[str, str]] = {}

    # Iterate over each requested database to find its submission status in the log.
    for target_database in requested_databases:
        log_database = _seqsender_log_database(target_database, table2asn)
        submission_log_tbl_filtered = submission_log_tbl.filter(
            (pl.col("Submission_Name").str.strip_chars().str.to_lowercase() == submission_name.strip().casefold()) &
            (pl.col("Organism").str.strip_chars().str.to_uppercase() == organism.strip().upper()) &
            (pl.col("Database").str.strip_chars().str.to_uppercase() == log_database) &
            (pl.col("Submission_Type").str.strip_chars().str.to_uppercase() == submission_type.strip().upper())
        )

        # Check if submission log is empty
        if submission_log_tbl_filtered.is_empty():
            missing_databases.append(target_database)
            continue

        # Retrieve the submission ID and status
        status_row = submission_log_tbl_filtered.to_dicts()[0]
        status = str(status_row["Submission_Status"]).strip().upper()
        database_statuses[target_database] = {
            "submission_id": str(status_row["Submission_ID"]).strip(),
            "submission_status": status,
            "status": SEQSENDER_STATUS_MAP[status],
        }

    # Raise an error if any requested databases are missing from the submission log.
    if missing_databases:
        raise ValueError(
            f"Cannot find submission status for submission '{submission_name}' in the submission log '{submission_log_file}' for database(s): {', '.join(sorted(missing_databases))}."
        )

    # Return the dictionary containing the submission status for each requested database.
    return database_statuses


# Column names declared in submission_status_report_pa_schema for a given database (matched
# by the database's short prefix, e.g. "gb-", or its full name, e.g. "genbank_"), mapped to
# their generic field name — that same matched prefix stripped off the column name (e.g.
# "gb-sample_name" -> "sample_name", "genbank_status" -> "status").
def _columns_for_database(target_database: str) -> Dict[str, str]:
    prefix = database_prefixes.get(target_database, "").lower()
    full_name = target_database.lower()
    prefixes = (f"{prefix}-", f"{prefix}_", f"{full_name}-", f"{full_name}_")
    field_columns: Dict[str, str] = {}
    for column in submission_status_report_pa_schema.columns:
        matched_prefix = next((p for p in prefixes if column.lower().startswith(p)), None)
        if matched_prefix is None:
            continue
        field_columns[column[len(matched_prefix):]] = column
    return field_columns


# Function to read and parse the per-sample submission status report of a SeqSender process.
def _read_submission_status_report(
    submission_status_report_file: str,
    database: List[str],
) -> Dict[str, List[Dict[str, Any]]]:

    # Normalize and deduplicate the list of requested databases.
    requested_databases = list(dict.fromkeys(
        _normalize_seqsender_database(target_database) for target_database in database
    ))

    # Read in the submission status report CSV file as-is — its columns depend on
    # which databases were submitted to, so it isn't schema-validated.
    status_report_tbl = pl.read_csv(submission_status_report_file)
    status_report_tbl = validate_tbl(status_report_tbl, submission_status_report_pa_schema, "submission_status_report")

    # Initialize the report dictionary for each requested database.
    report_by_database: Dict[str, List[Dict[str, Any]]] = {}
    for target_database in requested_databases:
        field_columns = _columns_for_database(target_database)
        if not field_columns:
            continue
        # select() can't take a dict directly — select each db-prefixed column and alias it
        # to its generic field name, then dedupe the resulting rows.
        report_tbl = status_report_tbl.select(
            [pl.col(column).alias(field) for field, column in field_columns.items()]
        ).unique()
        report_by_database[target_database] = report_tbl.to_dicts()

    # Return the report organized by database.
    return report_by_database


# Function to update the submission details of a SeqSender process in the database.
def _update_database_submission_status(
    submission_name: str,
    organism: str,
    submission_type: str,
    database_details: Dict[str, Dict[str, str]],
) -> None:
    # Update the submission status for each target database based on the provided details.
    for target_database, details in database_details.items():
        filter_coln_val = {
            "submission_name": [submission_name],
            "organism": [organism],
            "database": [target_database],
            "submission_type": [submission_type],
        }
        update_columns: Dict[str, List[Any]] = {
            "ncbi_submission_status": [details["submission_status"]],
            "ncbi_submission_id": [details["submission_id"]],
            "date_updated": [date.today().isoformat()],
        }

        # Update the submission record in the database with the new status and ID.
        update_tbl_in_database(
            db_tbl_name=["submission"],
            table=pl.DataFrame(update_columns),
            filter_coln_var=["submission_name", "organism", "database", "submission_type"],
            filter_coln_val=filter_coln_val,
            filter_var_by=["AND", "AND", "AND"],
        )


# Function to read the error log of a SeqSender process.
def _read_seqsender_error(log_path: str, max_bytes: int = 16_384) -> str:
    try:
        with open(log_path, "rb") as log_file:
            log_file.seek(0, os.SEEK_END)
            log_size = log_file.tell()
            log_file.seek(max(0, log_size - max_bytes))
            return log_file.read().decode("utf-8", errors="replace").strip()
    except OSError as err:
        logger.warning("Unable to read SeqSender log '%s': %s", log_path, err)
        return ""


# Ensure every metadata "sequence_name" has a matching FASTA record, and drop any FASTA
# record that isn't referenced by the metadata (e.g. left over after rows were removed from
# the metadata table). Raises if the metadata references a sample with no sequence at all.
def _reconcile_fasta_with_metadata_samples(metadata_file: str, fasta_file: str) -> None:

    # Read the metadata file and collect all sequence names.
    with open(metadata_file, "r", newline="", encoding="utf-8-sig") as fh:
        metadata_samples = {
            row["sequence_name"].strip()
            for row in csv.DictReader(fh)
            if row.get("sequence_name", "").strip()
        }

    # Parse the FASTA into (header_line, sequence_lines) records, keyed by the first
    # whitespace-delimited token of the header (the sequence ID SeqSender matches on).
    records: List[Tuple[str, List[str]]] = []
    current_header: Optional[str] = None
    current_lines: List[str] = []
    with open(fasta_file, "r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(">"):
                if current_header is not None:
                    records.append((current_header, current_lines))
                current_header = line.rstrip("\n")
                current_lines = []
            else:
                current_lines.append(line.rstrip("\n"))
        if current_header is not None:
            records.append((current_header, current_lines))
    record_ids = {header[1:].split()[0]: header for header, _ in records if header[1:].split()}

    # Every metadata sample must have a sequence — SeqSender can't submit a sample with none.
    missing_from_fasta = sorted(metadata_samples - record_ids.keys())
    if missing_from_fasta:
        raise ValueError(
            f"Metadata contains sample(s) with no matching sequence in '{fasta_file}': {', '.join(missing_from_fasta)}."
        )

    # Drop any FASTA record whose sample isn't in the metadata, then rewrite the file.
    kept_records = [
        (header, lines) for header, lines in records
        if header[1:].split() and header[1:].split()[0] in metadata_samples
    ]
    if len(kept_records) != len(records):
        with open(fasta_file, "w", encoding="utf-8") as fh:
            for header, lines in kept_records:
                fh.write(header + "\n")
                for line in lines:
                    fh.write(line + "\n")


# The installed SeqSender build resolves a bare (non-absolute) "sra-file_N" filename against
# "<submission_dir>/raw_reads" (it omits the submission_name segment SeqSender's own error
# message claims to use), which never matches where this backend actually stores uploaded raw
# reads ("<submission_dir>/<submission_name>/raw_reads/<file>"). Rewriting bare filenames to
# their absolute path here sidesteps that bug entirely, since SeqSender uses the path as-is
# whenever it's already absolute.
def _absolutize_raw_reads_paths(metadata_file: str, submission_name_dir: str) -> None:
    raw_reads_dir = os.path.join(submission_name_dir, "raw_reads")
    sra_file_column_re = re.compile(r"^sra-file_[1-9]\d*$", re.IGNORECASE)

    with open(metadata_file, "r", newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        fieldnames = reader.fieldnames or []
        sra_file_columns = [column for column in fieldnames if sra_file_column_re.match(column)]
        if not sra_file_columns:
            return
        rows = list(reader)

    changed = False
    for row in rows:
        for column in sra_file_columns:
            value = (row.get(column) or "").strip()
            if value and not os.path.isabs(value):
                row[column] = os.path.join(raw_reads_dir, value)
                changed = True

    if changed:
        with open(metadata_file, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


# Function to update the submitter information in the database with the provided submitter information
def update_submitter_in_database(
    submitter_name: str,
    submission_portal: str,
    submitter_tbl: pl.DataFrame,
    return_tbl: bool = False
) -> Optional[pl.DataFrame]:
    """
    Update submitter in the database with the provided submitter information.
    
    Args:
        submitter_name (str): Name of the submitter.
        submission_portal (str): Submission portal used by the submitter.
        submitter_tbl (pl.DataFrame): Submitter table containing submitter information.
        return_tbl (bool, optional): Whether to return the updated submitter table. Defaults to False.

    Returns:
        Optional[pl.DataFrame]: Updated submitter table if return_tbl is True, otherwise None.
    """
    try:
        # Check if submitter for this submitter_name exists in database
        db_submitter_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submitter"],
            return_var = ["*"],
            filter_coln_var = ["submitter_name", "submission_portal"],
            filter_coln_val = {"submitter_name": [submitter_name], "submission_portal": [submission_portal]},
            filter_var_by = ["AND", "AND"]
        )
        # Make sure db table match the schema data types
        db_submitter_tbl = db_submitter_tbl.with_columns([
            _cast_expr(col, submitter_db_schema.columns[col].dtype.type) for col in submitter_db_schema.columns
        ])
        # Validate db table against the schema
        db_submitter_tbl = validate_tbl(db_submitter_tbl, submitter_db_schema, "submitter")
        # Make sure submission table match the schema data types
        submitter_tbl = submitter_tbl.with_columns([
            _cast_expr(col, submitter_pa_schema.columns[col].dtype.type) for col in submitter_pa_schema.columns
        ])
        # Validate submission table against the schema
        submitter_tbl = validate_tbl(submitter_tbl, submitter_pa_schema, "submitter")
        # Check if db_submitter_tbl is empty, if so insert new submitter_tbl to database
        if db_submitter_tbl.is_empty():
            # Add date_created column
            submitter_tbl = submitter_tbl.with_columns([pl.lit(date.today().isoformat()).alias("created_date")])
            insert_tbl_to_database(
                db_tbl_name = ["submitter"],
                table = submitter_tbl
            )
        else:
            # Add updated_date column
            submitter_tbl = submitter_tbl.with_columns([pl.lit(date.today().isoformat()).alias("updated_date")])
            # Compare and update database table
            compare_and_update_db_table(
                unique_cols = ["submitter_name", "submission_portal"],
                compare_tbl = submitter_tbl,
                db_tbl = db_submitter_tbl,
                db_tbl_name = "submitter"
            )
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    # Whether to return database table
    if return_tbl:
        db_submitter_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submitter"],
            return_var = ["*"],
            filter_coln_var = ["submitter_name", "submission_portal"],
            filter_coln_val = {"submitter_name": [submitter_name], "submission_portal": [submission_portal]},
            filter_var_by = ["AND", "AND"]
        )
        return db_submitter_tbl
    else:
        return None


# Save a submitter's credentials on their own, independent of creating a submission.
def save_submitter(submitter_tbl: pl.DataFrame) -> Dict[str, Any]:
    try:
        row = submitter_tbl.to_dicts()[0]
        submitter_name = row["submitter_name"]
        submission_portal = row["submission_portal"]
        db_submitter_tbl = update_submitter_in_database(
            submitter_name = submitter_name,
            submission_portal = submission_portal,
            submitter_tbl = submitter_tbl,
            return_tbl = True
        )
        return {
            "status": "success",
            "message": f"Submitter '{submitter_name}' has been saved for {submission_portal}.",
            "SubmitterInfo": db_submitter_tbl.to_dicts(),
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Remove a saved submitter's credentials (identified by name + portal) from the database.
def delete_submitter(submitter_name: str, submission_portal: str) -> Dict[str, Any]:
    try:
        db_submitter_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submitter"],
            return_var = ["*"],
            filter_coln_var = ["submitter_name", "submission_portal"],
            filter_coln_val = {"submitter_name": [submitter_name], "submission_portal": [submission_portal]},
            filter_var_by = ["AND"],
        )
        if db_submitter_tbl.is_empty():
            raise ValueError(f"Submitter '{submitter_name}' does not exist for {submission_portal}.")

        delete_val_in_database(
            db_tbl_name = ["submitter"],
            delete_coln_var = ["submitter_name", "submission_portal"],
            delete_coln_val = {"submitter_name": [submitter_name], "submission_portal": [submission_portal]},
            delete_var_by = ["AND"]
        )
        return {
            "status": "success",
            "message": f"Submitter '{submitter_name}' has been removed from {submission_portal}.",
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Function to update the submission worksheet in the database with the provided submission information
def update_submission_in_database(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
    submission_tbl: pl.DataFrame,
    return_tbl: bool = False
) -> Optional[pl.DataFrame]:
    """
    Update the submission worksheet in the database with the provided submission information.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.
        submission_tbl (pl.DataFrame): Submission table containing submission information.
        return_tbl (bool, optional): Whether to return the updated submission table. Defaults to False.

    Returns:
        Optional[pl.DataFrame]: Updated submission table if return_tbl is True, otherwise None.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        
        # Make sure db table match the schema data types
        db_submission_tbl = db_submission_tbl.with_columns([
            _cast_expr(col, submission_db_schema.columns[col].dtype.type) for col in submission_db_schema.columns
        ])
        # Validate db table against the schema
        db_submission_tbl = validate_tbl(db_submission_tbl, submission_db_schema, "submission")
        # Make sure submission table match the schema data types
        submission_tbl = submission_tbl.with_columns([
            _cast_expr(col, submission_pa_schema.columns[col].dtype.type) for col in submission_pa_schema.columns
        ])
        # Validate submission table against the schema
        submission_tbl = validate_tbl(submission_tbl, submission_pa_schema, "submission")
        # Check if db_submission_tbl is empty, if so insert new submission_tbl to database
        if db_submission_tbl.is_empty():
            insert_tbl_to_database(
                db_tbl_name = ["submission"],
                table = submission_tbl
            )
        else:
            # Compare and update database table
            compare_and_update_db_table(
                unique_cols = ["submission_name", "organism", "database", "submission_type"],
                compare_tbl = submission_tbl,
                db_tbl = db_submission_tbl,
                db_tbl_name = "submission"
            )

        # Keep rows for databases removed from the current selection as history, but exclude
        # them from future submission and status operations.
        all_submission_rows = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["database"],
            filter_coln_var = ["submission_name", "organism", "submission_type"],
            filter_coln_val = {
                "submission_name": [submission_name],
                "organism": [organism],
                "submission_type": [submission_type],
            },
            filter_var_by = ["AND", "AND", "AND"],
        )
        selected_databases = {str(value).strip().upper() for value in database}
        archived_databases = [
            value
            for value in all_submission_rows.get_column("database").to_list()
            if str(value).strip().upper() not in selected_databases
        ]
        if archived_databases:
            update_tbl_in_database(
                db_tbl_name = ["submission"],
                table = pl.DataFrame({"database_status": ["ARCHIVED"]}),
                filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
                filter_coln_val = {
                    "submission_name": [submission_name],
                    "organism": [organism],
                    "database": archived_databases,
                    "submission_type": [submission_type],
                },
                filter_var_by = ["AND", "AND", "AND", "AND"],
            )
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    # Whether to return database table
    if return_tbl:
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        return db_submission_tbl
    else:
        return None
    

# Retrieve submission information from the database for a given submission name, organism, database, and submission type
def retrieve_submission(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission information from the database for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        Dict[str, Any]: Dictionary containing the status, message, and submission information.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.is_empty():
            return {
                "submission_info": None,
                "message": f"Submission '{submission_name}' does not exist in the database.",
            }
        else:
            return {
                "submission_info": db_submission_tbl.to_dicts(),
                "message": f"Submission '{submission_name}' has been successfully retrieved.",
            }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Update the free-text comments field for a single database row of a stored submission.
def update_seqsender_submission_comments(
    submission_name: str,
    organism: str,
    database: str,
    submission_type: str,
    comments: Optional[str],
) -> Dict[str, Any]:
    try:
        # Lookup the submission row in the database to ensure it exists before attempting to update comments.
        filter_coln_val = {
            "submission_name": [submission_name],
            "organism": [organism],
            "database": [_normalize_seqsender_database(database)],
            "submission_type": [submission_type.strip().upper()],
        }
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name=["submission"],
            return_var=["*"],
            filter_coln_var=["submission_name", "organism", "database", "submission_type"],
            filter_coln_val=filter_coln_val,
            filter_var_by=["AND", "AND", "AND"],
        )
        if db_submission_tbl.is_empty():
            raise ValueError(f"Submission '{submission_name}' does not exist for database '{database}' in the database.")
        
        # Ensure that the comments field is not None before updating the database.
        update_tbl_in_database(
            db_tbl_name=["submission"],
            table=pl.DataFrame({"comments": [comments]}),
            filter_coln_var=["submission_name", "organism", "database", "submission_type"],
            filter_coln_val=filter_coln_val,
            filter_var_by=["AND", "AND", "AND"],
        )
        return {
            "status": "success",
            "message": "Submission comments updated successfully.",
            "comments": comments,
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Update the "Message" values a user typed into the status report table (StatusReportTable's
# editable Message column) for one database's rows, keyed by that row's sample_name, and
# persist them back into the on-disk submission_status_report.csv used by check/load status.
def update_seqsender_submission_status_report_messages(
    submission_name: str,
    organism: str,
    database: str,
    submission_type: str,
    messages: Dict[str, Optional[str]],
) -> Dict[str, Any]:
    try:
        normalized_database = _normalize_seqsender_database(database)
        filter_coln_val = {
            "submission_name": [submission_name],
            "organism": [organism],
            "database": [normalized_database],
            "submission_type": [submission_type.strip().upper()],
        }
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name=["submission"],
            return_var=["*"],
            filter_coln_var=["submission_name", "organism", "database", "submission_type"],
            filter_coln_val=filter_coln_val,
            filter_var_by=["AND", "AND", "AND"],
        )
        if db_submission_tbl.is_empty():
            raise ValueError(f"Submission '{submission_name}' does not exist for database '{database}' in the database.")

        # Ensure the submission directory exists
        if not messages:
            return {"status": "success", "message": "No message edits to save."}

        # Define submission directory paths
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        submission_status_report_file = os.path.join(submission_name_dir, "submission_files", SUBMISSION_STATUS_REPORT_FILENAME)
        if not os.path.isfile(submission_status_report_file):
            raise ValueError(
                f"Submission status report file '{SUBMISSION_STATUS_REPORT_FILENAME}' does not exist for submission '{submission_name}'."
            )

        # Resolve this database's actual sample_name/message column names in the shared report CSV.
        field_columns = _columns_for_database(normalized_database)
        sample_name_column = field_columns.get("sample_name")
        message_column = field_columns.get("message")
        if not sample_name_column or not message_column:
            raise ValueError(f"Database '{database}' does not have a message column in the submission status report.")

        # Read in the status report
        status_report_tbl = pl.read_csv(submission_status_report_file)
        status_report_tbl = validate_tbl(status_report_tbl, submission_status_report_pa_schema, "submission_status_report")

        # Overwrite the message column only for rows whose sample_name has an edited message.
        status_report_tbl = status_report_tbl.with_columns(
            pl.when(pl.col(sample_name_column).cast(pl.Utf8).is_in(list(messages.keys())))
            .then(pl.col(sample_name_column).cast(pl.Utf8).replace_strict(messages, default=None))
            .otherwise(pl.col(message_column))
            .alias(message_column)
        )
        status_report_tbl.write_csv(submission_status_report_file)

        return {
            "status": "success",
            "message": "Submission status report messages updated successfully.",
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# ---------- Helper: create SeqSender config file ----------
def create_seqsender_config_file(
    gisaid_submitter_name: Optional[str],
    ncbi_submitter_name: Optional[str],
    submission_name: str,
    organism: str,
    database: List[str],
) -> None:
    try:
        # NCBI section is needed if any non-GISAID database is active; GISAID section only if GISAID is active
        needs_ncbi = any(db != "GISAID" for db in database)
        needs_gisaid = "GISAID" in database

        # Read in the config template file
        with open(CONFIG_TEMPLATE_PATH, "r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh)

        # Populate the config with the submitter's credentials from the database
        if needs_ncbi:
            submission_tbl = lookup_tbl_in_database(
                db_tbl_name = ["submission"],
                return_var = ["*"],
                filter_coln_var = ["submission_name", "submission_portal"],
                filter_coln_val = {"submission_name": [submission_name], "submission_portal": ["NCBI"]},
                filter_var_by = ["AND", "AND"]
            )
            ncbi_tbl = lookup_tbl_in_database(
                db_tbl_name = ["submitter"],
                return_var = ["*"],
                filter_coln_var = ["submitter_name", "submission_portal"],
                filter_coln_val = {"submitter_name": [ncbi_submitter_name], "submission_portal": ["NCBI"]},
                filter_var_by = ["AND", "AND"]
            )
            if submission_tbl.is_empty():
                raise ValueError(f"NCBI submission '{submission_name}' does not exist in the database.")
            if ncbi_tbl.is_empty():
                raise ValueError(f"NCBI submitter '{ncbi_submitter_name}' does not exist in the database.")
            # Convert null to empty string
            submission_tbl = submission_tbl.with_columns(
                pl.col(pl.String).fill_null("")
            )
            ncbi_tbl = ncbi_tbl.with_columns(
                pl.col(pl.String).fill_null("")
            )
            # Extract the first row from the NCBI table as a dictionary
            ncbi_row = ncbi_tbl.to_dicts()[0]
            submission_row = submission_tbl.to_dicts()[0]
            text = lambda value: "" if value is None else str(value)
            postal_code = text(ncbi_row["ncbi_addr_postal_code"]).strip()
            if not postal_code.isdigit():
                raise ValueError("NCBI postal code must contain only digits for SeqSender.")
            ncbi_cfg = config["Submission"]["NCBI"]
            ncbi_cfg["Username"] = text(ncbi_submitter_name)
            ncbi_cfg["Password"] = text(ncbi_row["submitter_password"])
            ncbi_cfg["Spuid_Namespace"] = text(ncbi_row["ncbi_spuid_namespace"])
            ncbi_cfg["BioSample_Package"] = text(biosample_packages[organism])
            ncbi_cfg["Publication_Title"] = text(submission_row["ncbi_publication_title"])
            ncbi_cfg["Publication_Status"] = text(submission_row["ncbi_publication_status"])
            ncbi_cfg["Specified_Release_Date"] = text(submission_row["ncbi_release_date"])
            ncbi_cfg["GenBank_Auto_Remove_Failed_Samples"] = False
            ncbi_cfg["Link_Sample_Between_NCBI_Databases"] = True
            ncbi_cfg["Add_Definition_Line_Accessions"] = True
            ncbi_cfg["Submission_Position"] = 2 if needs_gisaid else 1
            org = ncbi_cfg["Description"]["Organization"]
            org["Role"] = text(ncbi_row["ncbi_org_role"])
            org["Type"] = text(ncbi_row["ncbi_org_type"])
            org["Name"] = text(ncbi_row["ncbi_org_name"])
            addr = org["Address"]
            addr["Affil"] = text(ncbi_row["ncbi_org_affiliation"])
            addr["Div"] = text(ncbi_row["ncbi_org_division"])
            addr["Street"] = text(ncbi_row["ncbi_addr_street"])
            addr["City"] = text(ncbi_row["ncbi_addr_city"])
            addr["Sub"] = text(ncbi_row["ncbi_addr_state"])
            addr["Postal_Code"] = int(postal_code)
            addr["Country"] = text(ncbi_row["ncbi_addr_country"])
            addr["Email"] = text(ncbi_row["ncbi_addr_email"])
            addr["Phone"] = text(ncbi_row["ncbi_addr_phone"])
            submitter_cfg = org["Submitter"]
            submitter_cfg["Email"] = text(ncbi_row["ncbi_submitter_email"])
            submitter_cfg["Alt_Email"] = text(ncbi_row["ncbi_submitter_alt_email"])
            submitter_cfg["Name"]["First"] = text(ncbi_row["ncbi_submitter_first_name"])
            submitter_cfg["Name"]["Last"] = text(ncbi_row["ncbi_submitter_last_name"])
        else:
            del config["Submission"]["NCBI"]

        # Populate the GISAID section of the config if needed
        if needs_gisaid:
            gisaid_tbl = lookup_tbl_in_database(
                db_tbl_name = ["submitter"],
                return_var = ["*"],
                filter_coln_var = ["submitter_name", "submission_portal"],
                filter_coln_val = {"submitter_name": [gisaid_submitter_name], "submission_portal": ["GISAID"]},
                filter_var_by = ["AND", "AND"]
            )
            if gisaid_tbl.is_empty():
                raise ValueError(f"GISAID submitter '{gisaid_submitter_name}' does not exist in the database.")
            gisaid_row = gisaid_tbl.to_dicts()[0]
            gisaid_cfg = config["Submission"]["GISAID"]
            gisaid_cfg["Client-Id"] = text(gisaid_row["gisaid_client_id"])
            gisaid_cfg["Username"] = text(gisaid_submitter_name)
            gisaid_cfg["Password"] = text(gisaid_row["submitter_password"])
            gisaid_cfg["Submission_Position"] = 2 if needs_ncbi else 1
        else:
            del config["Submission"]["GISAID"]

        # Write the rendered config into the submission's directory
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        os.makedirs(submission_name_dir, exist_ok=True)
        config_file_path = os.path.join(submission_name_dir, CONFIG_FILENAME)
        with open(config_file_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(config, fh, sort_keys=False)
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    
    
# Create a SeqSender submission for a given submission name, organism, database, and submission type
def create_seqsender_submission(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
    ncbi_submitter_info: Optional[pl.DataFrame] = None,
    gisaid_submitter_info: Optional[pl.DataFrame] = None,
    gff_file: Optional[bool] = False,
    table2asn: Optional[bool] = False,
    ncbi_publication_title: Optional[str] = None,
    ncbi_publication_status: str = "Unpublished",
    ncbi_release_date: Optional[str] = None,
) -> Dict[str, Any]:
    try:
        # Create NCBI submitter
        ncbi_submitter_tbl = ncbi_submitter_info
        if ncbi_submitter_tbl is not None and not ncbi_submitter_tbl.is_empty():
            row = ncbi_submitter_tbl.to_dicts()[0]
            submitter_name = row["submitter_name"]
            submission_portal = "NCBI"
            ncbi_submitter_name = row["submitter_name"]
            update_submitter_in_database(
                submitter_name = submitter_name,
                submission_portal = submission_portal,
                submitter_tbl = ncbi_submitter_tbl,
                return_tbl = True
            )
        else:
            ncbi_submitter_name = None

        # Create GISAID submitter
        gisaid_submitter_tbl = gisaid_submitter_info
        if gisaid_submitter_tbl is not None and not gisaid_submitter_tbl.is_empty():
            row = gisaid_submitter_tbl.to_dicts()[0]
            submitter_name = row["submitter_name"]
            submission_portal = "GISAID"
            gisaid_submitter_name = row["submitter_name"]
            update_submitter_in_database(
                submitter_name = submitter_name,
                submission_portal = submission_portal,
                submitter_tbl = gisaid_submitter_tbl,
                return_tbl = True
            )
        else:
            gisaid_submitter_name = None

        # Create submission table. Every column declared in submission_pa_schema must be
        # present (even if null) — update_submission_in_database casts/validates against
        # every schema column, and a missing column raises a Polars ColumnNotFoundError.
        submission_tbl = pl.DataFrame({
            "submission_name": [submission_name for db in database],
            "organism": [organism for db in database],
            "submission_portal": ["NCBI" if db != "GISAID" else "GISAID" for db in database],
            "database": [db for db in database],
            "database_status": ["ACTIVE" for db in database],
            "submission_type": [submission_type if db != "GISAID" else "PRODUCTION" for db in database],
            "gff_file": [gff_file if db != "GISAID" else False for db in database],
            "table2asn": [table2asn if db != "GISAID" else False for db in database],
            "submitter_name": [ncbi_submitter_name if db != "GISAID" else gisaid_submitter_name for db in database],
            "ncbi_publication_title": [ncbi_publication_title if db != "GISAID" else None for db in database],
            "ncbi_publication_status": [ncbi_publication_status if db != "GISAID" else "Unpublished" for db in database],
            "ncbi_release_date": [ncbi_release_date if db != "GISAID" else None for db in database],
            "number_of_samples": [0 for db in database],
            "ncbi_submission_id": [None for db in database],
            "ncbi_submission_status": [None for db in database],
            "submission_status": ["CREATED" for db in database],
            "comments": [None for db in database],
            "date_submitted": [None for db in database],
            "date_updated": [None for db in database],
        })

        # Update submission worksheet in database
        db_submission_tbl = update_submission_in_database(
            submission_name = submission_name,
            organism = organism,
            database = database,
            submission_type = submission_type,
            submission_tbl = submission_tbl,
            return_tbl = True
        )

        # Create config file after the submission rows exist so NCBI publication and release
        # values can be read from the submission table.
        create_seqsender_config_file(
            ncbi_submitter_name = ncbi_submitter_name,
            gisaid_submitter_name = gisaid_submitter_name,
            submission_name = submission_name,
            organism = organism,
            database = database,
        )

        # Return
        return {
            "status":  "success",
            "message": f"Submission '{submission_name}' has been successfully created.",
            "submission_info": db_submission_tbl.to_dicts(),
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Delete every database row and on-disk folder for a submission (identified by name + organism,
# since GISAID rows are always stored under submission_type PRODUCTION regardless of the
# submission's actual type, so filtering by submission_type would miss them).
def delete_seqsender_submission(
    submission_name: str,
    organism: str,
) -> Dict[str, Any]:
    try:
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism]},
            filter_var_by = ["AND"]
        )
        if db_submission_tbl.is_empty():
            raise ValueError(f"Submission '{submission_name}' does not exist in the database.")

        # Remove the on-disk submission directory (config, metadata, FASTA, raw reads, etc.)
        # first — if this fails the database is left untouched.
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism, submission_name))
        if os.path.exists(submission_dir):
            shutil.rmtree(submission_dir)

        # Delete every row (every database target) for this submission from the database
        delete_val_in_database(
            db_tbl_name = ["submission"],
            delete_coln_var = ["submission_name", "organism"],
            delete_coln_val = {"submission_name": [submission_name], "organism": [organism]},
            delete_var_by = ["AND"]
        )
        return {
            "status":  "success",
            "message": f"Submission '{submission_name}' has been removed from the database.",
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Duplicate an existing submission's database rows and on-disk folder under a new submission name.
def copy_seqsender_submission(
    submission_name: str,
    organism: str,
    new_submission_name: str,
) -> Dict[str, Any]:
    try:
        # Look up every row (every database target) for the submission to duplicate
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism]},
            filter_var_by = ["AND"]
        )
        if db_submission_tbl.is_empty():
            raise ValueError(f"Submission '{submission_name}' does not exist in the database.")

        # Reject if a submission with the new name already exists for this organism
        existing_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism"],
            filter_coln_val = {"submission_name": [new_submission_name], "organism": [organism]},
            filter_var_by = ["AND"]
        )
        if not existing_tbl.is_empty():
            raise ValueError(f"A submission named '{new_submission_name}' already exists for organism '{organism}'.")

        # Copy the on-disk submission directory (config, metadata, FASTA, raw reads, etc.) first —
        # if this fails the database is left untouched.
        old_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism, submission_name))
        new_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism, new_submission_name))
        if os.path.exists(old_dir):
            if os.path.exists(new_dir):
                shutil.rmtree(new_dir)
            shutil.copytree(old_dir, new_dir)

        # Remove submission files from the old directory after copying to the new directory.
        submission_files_dir = os.path.join(new_dir, "submission_files")
        if os.path.exists(submission_files_dir):
            shutil.rmtree(submission_files_dir) 

        # Insert a copy of every database row under the new submission_name. Reset status to
        # CREATED since the copy hasn't actually been (re-)submitted anywhere yet, and drop
        # submission_id so the database assigns a fresh one. date_submitted/date_updated are
        # reset to NULL — the copy hasn't been submitted or checked yet, so there's nothing to
        # date-stamp until that actually happens.
        new_rows = db_submission_tbl.with_columns([
            pl.lit(new_submission_name).alias("submission_name"),
            pl.lit("").alias("ncbi_submission_id"),
            pl.lit("").alias("ncbi_submission_status"),
            pl.lit("CREATED").alias("submission_status"),
            pl.lit(None, dtype=pl.Utf8).alias("date_submitted"),
            pl.lit(None, dtype=pl.Utf8).alias("date_updated"),
        ]).drop("submission_id")

        # Insert the new rows into the database.
        insert_tbl_to_database(
            db_tbl_name = ["submission"],
            table = new_rows
        )

        # Look up the newly inserted submission to return its details.
        new_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism"],
            filter_coln_val = {"submission_name": [new_submission_name], "organism": [organism]},
            filter_var_by = ["AND"]
        )

        # Return the details of the newly copied submission.
        return {
            "status":            "success",
            "message":           f"Submission '{submission_name}' has been copied to '{new_submission_name}'.",
            "submission_name":   new_submission_name,
            "submission_info":   new_submission_tbl.to_dicts(),
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Generate (via SeqSender's own `test_data` command) a metadata template shaped for the
# selected organism and database targets, and return the path to the resulting CSV.
# SeqSender combines each database's example metadata columns (bs-/sra-/gb-/gs- prefixed)
# into one CSV, which is exactly the header layout a real submission's metadata file needs.
def retrieve_seqsender_metadata_template(
    organism: str,
    database: List[str],
) -> str:
    try:
        seqsender_python, seqsender_script = _seqsender_cli_paths()

        # Cache the generated template per organism + sorted database combo so repeat
        # downloads don't re-invoke the SeqSender subprocess every time.
        cache_key = f"{organism}_{'-'.join(sorted(db.strip().upper() for db in database))}"
        cache_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, "_metadata_templates"))
        cached_file = os.path.join(cache_dir, f"{cache_key}_metadata_template.csv")
        if os.path.exists(cached_file):
            return cached_file

        database_flags = {"BIOSAMPLE": "--biosample", "SRA": "--sra", "GENBANK": "--genbank", "GISAID": "--gisaid"}
        with tempfile.TemporaryDirectory(prefix="seqsender_test_data_") as tmp_dir:
            cmd = [seqsender_python, seqsender_script, "test_data", "--organism", organism, "--submission_dir", tmp_dir]
            cmd.extend(flag for db in database if (flag := database_flags.get(db.strip().upper())))
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            generated_file = os.path.join(tmp_dir, f"{organism}_TEST_DATA", "metadata.csv")
            if not os.path.exists(generated_file):
                raise ValueError(
                    (proc.stdout or proc.stderr or "").strip() or
                    f"SeqSender does not have a metadata template available for organism '{organism}'."
                )

            os.makedirs(cache_dir, exist_ok=True)
            shutil.copy(generated_file, cached_file)

        return cached_file
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Retrieve submission config file for a given submission name, organism, database, and submission type
def retrieve_seqsender_config(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission config for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission config file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve config file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        config_file_path = os.path.join(submission_name_dir, CONFIG_FILENAME)
        if not os.path.exists(config_file_path):
            raise ValueError(f"Config file '{CONFIG_FILENAME}' does not exist in submission directory '{submission_name_dir}'. File might have been moved or deleted.")
        # Return file path
        return config_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    

# Retrieve submission metadata for a given submission name, organism, database, and submission type
def retrieve_seqsender_metadata(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission metadata for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission metadata file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        metadata_file_path = os.path.join(submission_name_dir, METADATA_FILENAME)
        if not os.path.exists(metadata_file_path):
            raise ValueError(f"Metadata file '{METADATA_FILENAME}' does not exist in submission directory '{submission_name_dir}'. File might have been moved or deleted.")
        # Return file path
        return metadata_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

    
# Retrieve submission fasta file for a given submission name, organism, database, and submission type
def retrieve_seqsender_fasta(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission fasta file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission fasta file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        fasta_file_path = os.path.join(submission_name_dir, FASTA_FILENAME)
        if not os.path.exists(fasta_file_path):
            raise ValueError(f"Fasta file '{FASTA_FILENAME}' does not exist in submission directory '{submission_name_dir}'. File might have been moved or deleted.")
        # Return file path
        return fasta_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))   


# Retrieve raw read files for a given submission name, organism, database, and submission type
def retrieve_seqsender_raw_reads(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> List[str]:
    """Return the paths of raw read files stored for an existing submission."""
    try:
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
            raise ValueError(f"Submission '{submission_name}' does not exist in the database.")

        raw_reads_dir = os.path.realpath(os.path.join(
            _DEFAULT_SEQSENDER_STORAGE_PATH,
            organism,
            submission_name,
            "raw_reads"
        ))
        if not os.path.isdir(raw_reads_dir):
            raise ValueError(f"Raw reads folder do not exist for submission '{submission_name}'. Folder might have been moved or deleted.")

        raw_read_paths = sorted(
            os.path.join(raw_reads_dir, filename)
            for filename in os.listdir(raw_reads_dir)
            if os.path.isfile(os.path.join(raw_reads_dir, filename))
        )
        if not raw_read_paths:
            raise ValueError(f"Raw reads do not exist for submission '{submission_name}'. Files might have been moved or deleted.")
        return raw_read_paths
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Function to validate the presence of files required for a SeqSender submission.
def validate_seqsender_uploaded_files(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
    require_gff: bool = False,
) -> Dict[str, Any]:
    
    # Validate that the submission exists in the database and retrieve the selected databases.
    db_submission_tbl = lookup_tbl_in_database(
        db_tbl_name = ["submission"],
        return_var = ["*"],
        filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
        filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
        filter_var_by = ["AND", "AND", "AND", "AND"]
    )
    if db_submission_tbl.shape[0] == 0:
        raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
    
    # Ensure that the submission exists in the database before proceeding.
    selected_databases = db_submission_tbl.select("database").unique().to_series().to_list()
    submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
    submission_name_dir = os.path.join(submission_dir, submission_name)
    raw_reads_dir = os.path.join(submission_name_dir, "raw_reads")
    gisaid_cli_dir = os.path.join(submission_dir, "gisaid_cli")

    # Check the presence of required files for the SeqSender submission.
    file_status = {
        "metadata": os.path.isfile(os.path.join(submission_name_dir, METADATA_FILENAME)),
        "fasta": os.path.isfile(os.path.join(submission_name_dir, FASTA_FILENAME)) if "GenBank" in selected_databases or "GISAID" in selected_databases else True,
        "raw_reads": "SRA" not in selected_databases or (
            os.path.isdir(raw_reads_dir)
            and any(
                os.path.isfile(os.path.join(raw_reads_dir, filename))
                for filename in os.listdir(raw_reads_dir)
            )
        ),
        "gisaid_cli": "GISAID" not in selected_databases or os.path.isfile(os.path.join(
            gisaid_cli_dir,
            organism.lower() + "CLI",
        )),
        "gff": not require_gff or os.path.isfile(os.path.join(submission_name_dir, GFF_FILENAME)),
    }

    # Define human-readable labels for each required file.
    labels = {
        "metadata": "Metadata File",
        "fasta": "FASTA File",
        "raw_reads": "Raw Reads (FASTQs)",
        "gisaid_cli": "GISAID CLI",
        "gff": "GFF File",
    }

    # Return the status of required files for the submission.
    return {
        "files": file_status,
        "missing_files": [
            {"key": key, "label": labels[key]}
            for key, exists in file_status.items()
            if not exists
        ],
    }


# Retrieve gff file for a given submission name, organism, database, and submission type
def retrieve_seqsender_gff(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission gff file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission gff file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        gff_file_path = os.path.join(submission_name_dir, GFF_FILENAME)
        if not os.path.exists(gff_file_path):
            raise ValueError(f"GFF file '{GFF_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # Return file path
        return gff_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))   


# Retrieve table2asn file for a given submission name, organism, database, and submission type
def retrieve_seqsender_table2asn(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission table2asn file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission table2asn file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        table2asn_file_path = os.path.join(submission_name_dir, TABLE2ASN_FILENAME)
        if not os.path.exists(table2asn_file_path):
            raise ValueError(f"Table2asn file '{TABLE2ASN_FILENAME}' does not exist in submission directory '{submission_name_dir}'.")
        # Return file path
        return table2asn_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))   
    

# Retrieve gisaid cli file for a given submission name, organism, database, and submission type
def retrieve_seqsender_gisaid_cli(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission GISAID CLI file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        Dict[str, Any]: Dictionary containing the details of the submission GISAID CLI file location.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        GISAID_CLI_FILENAME = organism.lower() + "CLI"
        gisaid_cli_file_path = os.path.join(submission_dir, GISAID_CLI_FILENAME)
        if not os.path.exists(gisaid_cli_file_path):
            raise ValueError(f"GISAID CLI file '{GISAID_CLI_FILENAME}' does not exist in submission directory '{submission_dir}'.")
        # Return file path
        return {"gisaid_cli_file_path": gisaid_cli_file_path}
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))

    
# Retrieve submission log file for a given submission name, organism, database, and submission type
def retrieve_seqsender_submission_log(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission log file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        str: Path to the submission log file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        submission_log_file_path = os.path.join(submission_name_dir, SUBMISSION_LOG_FILENAME)
        if not os.path.exists(submission_log_file_path):
            return None
        else:
            return submission_log_file_path
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    

# Retrieve submission status report file for a given submission name, organism, database, and submission type
def retrieve_seqsender_status_report(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Retrieve submission status report file for a given submission name, organism, database, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        Dict[str, Any]: Dictionary containing the path to the submission status report file.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": database, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
        # Retrieve metadata file path
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        submission_status_report_file_path = os.path.join(submission_name_dir, SUBMISSION_STATUS_REPORT_FILENAME)
        if not os.path.exists(submission_status_report_file_path):
            return {"submission_status_report_file_path": None}
        else:
            return {"submission_status_report_file_path": submission_status_report_file_path}
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))
    

# Function to submit submission to the specified database for a given submission name, organism, and submission type
def submit_ncbi_submission(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Submit submission to the specified database for a given submission name, organism, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to submit to.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        Dict[str, Any]: Dictionary containing the status and message of the submission process.
    """
    try:
        # Check if submission for this submission_name exists in database
        selected_databases = [_normalize_seqsender_database(db) for db in database]
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": selected_databases, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        # Check if submission exists in the database
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")

        # Define the submission directory as seen by this backend process (used for local
        # file-existence checks, Popen's cwd, and the stdout log file).
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)

        # Run the copied SeqSender application in its isolated Micromamba environment.
        seqsender_python, seqsender_script = _seqsender_cli_paths()
        submit_cmd = [
            seqsender_python,
            seqsender_script,
            "submit",
        ]
        cmd = [
            "--submission_dir", submission_dir,
            "--submission_name", submission_name,
            "--organism", organism
        ]

        # Check if config file exists in the submission directory
        config_file = os.path.join(submission_name_dir, CONFIG_FILENAME)
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file '{config_file}' does not exist.")
        else:
            cmd.extend(["--config_file", config_file])

        # Check if metadata file exists in the submission directory
        metadata_file = os.path.join(submission_name_dir, METADATA_FILENAME)
        if not os.path.exists(metadata_file):
            raise FileNotFoundError(f"Metadata file '{metadata_file}' does not exist.")
        else:
            cmd.extend(["--metadata_file", metadata_file])

        # If SRA is selected, ensure sra-file_1/sra-file_2/... paths are absolute. This is necessary
        # due to a known bug in the installed SeqSender build where relative paths in the metadata
        # file can cause submission failures.
        if "SRA" in selected_databases:
            _absolutize_raw_reads_paths(metadata_file, submission_name_dir)

        # Check if fasta file exists in the submission directory. Only pass --fasta_file when
        # GenBank is selected -- SeqSender validates the path even for BioSample/SRA-only runs.
        fasta_file = os.path.join(submission_name_dir, FASTA_FILENAME)
        if "GENBANK" in selected_databases:
            if not os.path.exists(fasta_file):
                raise FileNotFoundError(f"FASTA file '{fasta_file}' does not exist.")
            cmd.extend(["--fasta_file", fasta_file])

        # Make sure every metadata sample has a matching sequence, and drop any FASTA record
        # that isn't referenced by the metadata (e.g. left over after rows were removed).
        if "GENBANK" in selected_databases:
            _reconcile_fasta_with_metadata_samples(metadata_file, fasta_file)

        # Record the sample count on every database row for this submission (not just the
        # rows for the currently-selected databases), since the count isn't database-specific.
        metadata_tbl = pl.read_csv(metadata_file)
        for target_database in selected_databases:
            n_kept_records = metadata_tbl.select(f"{database_prefixes[target_database]}-sample_name").unique().height
            update_tbl_in_database(
                db_tbl_name=["submission"],
                table=pl.DataFrame({"number_of_samples": [n_kept_records]}),
                filter_coln_var=["submission_name", "organism", "database", "submission_type"],
                filter_coln_val={
                    "submission_name": [submission_name],
                    "organism": [organism],
                    "database": [target_database],
                    "submission_type": [submission_type],
                },
                filter_var_by=["AND", "AND", "AND"],
            )

        # If gff file is true, check if it exists
        gff_file = db_submission_tbl.select("gff_file").to_series().to_list()[0]
        if gff_file:
            gff_file_path = os.path.join(submission_name_dir, GFF_FILENAME)
            if not os.path.exists(gff_file_path):
                raise FileNotFoundError(f"GFF file '{gff_file_path}' does not exist.")
            cmd.extend(["--gff_file", gff_file_path])

        # If table2asn is true, check if it exists
        table2asn = db_submission_tbl.select("table2asn").to_series().to_list()[0]
        if table2asn:
            cmd.extend(["--table2asn"])

        # Check if BioSample is in the database list
        if "BIOSAMPLE" in [db.strip().upper() for db in database]:
            cmd.extend(["--biosample"])
        # Check if SRA is in the database list
        if "SRA" in [db.strip().upper() for db in database]:
            cmd.extend(["--sra"])
        # Check if GenBank is in the database list
        if "GENBANK" in [db.strip().upper() for db in database]:
            cmd.extend(["--genbank"])
        # Check submission type
        if "TEST" == submission_type.strip().upper():
            cmd.extend(["--test"])

        # Log the command that will be executed
        logger.info(
            f"Launching SeqSender pipeline for submission '{submission_name}' with command:\n" +
            f"{seqsender_python} {seqsender_script} submit\n" +
            f" --submission_dir {submission_dir}\n" +
            f" --submission_name {submission_name}\n" +
            f" --organism {organism}\n" +
            f" --config_file {config_file}\n" +
            f" --metadata_file {metadata_file}\n" +
            (f" --fasta_file {fasta_file}\n" if "GENBANK" in selected_databases else "") +
            (f" --gff_file {gff_file_path}\n" if gff_file else "") +
            (f" --table2asn\n" if table2asn else "") +
            (f" --biosample\n" if "BIOSAMPLE" in [db.strip().upper() for db in database] else "") +
            (f" --sra\n" if "SRA" in [db.strip().upper() for db in database] else "") +
            (f" --genbank\n" if "GENBANK" in [db.strip().upper() for db in database] else "") +
            (f" --test\n" if "TEST" == submission_type.strip().upper() else "")
        )    

        # Create seqsender_stdout.log file in the submission directory
        seqsender_stdout_path = os.path.join(submission_name_dir, "seqsender.stdout.log")
        stdout_fh = open(seqsender_stdout_path, "w", encoding="utf-8")

        # Run SeqSender asynchronously so the API can return its PID immediately.
        submit_proc = subprocess.Popen(
            submit_cmd + cmd,
            cwd=submission_name_dir,
            stdout=stdout_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        # The child has inherited its own copy of the file descriptor; the parent's copy
        # is no longer needed and can be closed safely.
        stdout_fh.close()

        # Record the process information in the global dictionary with thread safety.
        with _SEQSENDER_PROCESS_LOCK:
            _SEQSENDER_PROCESSES[submit_proc.pid] = {
                "process": submit_proc,
                "identity": _seqsender_process_identity(
                    submission_name,
                    organism,
                    database,
                    submission_type,
                ),
                "log_path": seqsender_stdout_path,
            }

        # Return the process ID and command for reference
        return {
            "status":  "success",
            "pid":     submit_proc.pid,
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Function to submit submissions to GISAID
def submit_gisaid_submission(
    submission_name: str,
    organism: str,
    database: str,
    submission_type: str
) -> Dict[str, Any]:
    """
    Submit submission to GISAID for a given submission name, organism, and submission type.
    
    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (Literal["GISAID"]): Database to which the submission is being made (e.g., "GISAID").
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        Dict[str, Any]: Dictionary containing the status and message of the submission process.
    """
    try:
        # Check if submission for this submission_name exists in database
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": [database], "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )

        # Check if submission exists in the database
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")

        # Retrieve submitter from submission table
        submitter = db_submission_tbl.select("submitter").to_series().to_list()[0]

        # Look up submitter credentials
        submitter_tbl = lookup_tbl_in_database(
            db_tbl_name=["submitter"],
            filter_coln_var=["submitter", "submission_portal"],
            filter_coln_val={"submitter": [submitter], "submission_portal": [database]},
            filter_var_by=["AND", "AND"]
        )

        # Check if submitter credentials exist in the database
        if submitter_tbl.shape[0] == 0:
            raise ValueError(f"Submitter '{submitter}' does not have credentials for {database}.")

        # Retrieve GISAID credentials for the submitter
        gisaid_username = submitter_tbl.select("username").to_series().to_list()[0]
        gisaid_password = submitter_tbl.select("password").to_series().to_list()[0]
        gisaid_client_id = submitter_tbl.select("gisaid_client_id").to_series().to_list()[0]

        # Define the submission directory as seen by this backend process (used for local
        # file-existence checks, Popen's cwd, and the stdout log file).
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)
        submission_files_dir = os.path.join(submission_name_dir, "submission_files", "GISAID")
        gisaid_cli_file = os.path.join(submission_dir, "gisaid_cli", f"{organism.lower()}CLI")

        # Check if gisaid_cli_file exists
        if not os.path.exists(gisaid_cli_file):
            raise FileNotFoundError(f"GISAID CLI file '{gisaid_cli_file}' does not exist.")

        # Run the copied SeqSender application in its isolated Micromamba environment.
        upload_cmd = [
            f"{gisaid_cli_file}",
            "upload",
        ]
        cmd = [
            "--username", gisaid_username,
            "--password", gisaid_password,
            "--clientid", gisaid_client_id,
        ]

        # Check if metadata file exists in the submission directory
        metadata_file = os.path.join(submission_files_dir, METADATA_FILENAME)
        if not os.path.exists(metadata_file):
            raise FileNotFoundError(f"Metadata file '{metadata_file}' does not exist.")
        else:
            cmd.extend(["--metadata", metadata_file])

        # Check if fasta file exists in the submission directory
        fasta_file = os.path.join(submission_files_dir, FASTA_FILENAME)
        if not os.path.exists(fasta_file):
            raise FileNotFoundError(f"FASTA file '{fasta_file}' does not exist.")
        else:
            cmd.extend(["--fasta", fasta_file])

        # Add the log file path to the command arguments
        gisaid_log = os.path.join(submission_files_dir, "gisaid.log")
        cmd.extend(["--log", gisaid_log])

        # Make sure every metadata sample has a matching sequence, and drop any FASTA record
        # that isn't referenced by the metadata (e.g. left over after rows were removed).
        _reconcile_fasta_with_metadata_samples(metadata_file, fasta_file)

        # Record the sample count on every database row for this submission (not just the
        # rows for the currently-selected databases), since the count isn't database-specific.
        metadata_tbl = pl.read_csv(metadata_file)
        n_kept_records = metadata_tbl.select(f"{database_prefixes[database]}-sample_name").unique().height
        update_tbl_in_database(
            db_tbl_name=["submission"],
            table=pl.DataFrame({"number_of_samples": [n_kept_records]}),
            filter_coln_var=["submission_name", "organism", "database", "submission_type"],
            filter_coln_val={
                "submission_name": [submission_name],
                "organism": [organism],
                "database": [database],
                "submission_type": [submission_type],
            },
            filter_var_by=["AND", "AND", "AND", "AND"],
        )

        # Create seqsender_stdout.log file in the submission directory
        gisaid_stdout_path = os.path.join(submission_name_dir, "gisaid.stdout.log")
        stdout_fh = open(gisaid_stdout_path, "w", encoding="utf-8")

        # Log the command that will be executed
        logger.info(
            f"Launching GISAID CLI pipeline for submission '{submission_name}' with command:\n" +
            f"{gisaid_cli_file} upload\n" +
            f" --username {gisaid_username}\n" +
            f" --password {gisaid_password}\n" +
            f" --clientid {gisaid_client_id}\n" +
            f" --metadata {metadata_file}\n" +
            f" --fasta {fasta_file}\n" +
            f" --log {gisaid_log}\n"
        )    

        # Run SeqSender asynchronously so the API can return its PID immediately.
        upload_proc = subprocess.Popen(
            upload_cmd + cmd,
            cwd=submission_name_dir,
            stdout=stdout_fh,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )

        # The child has inherited its own copy of the file descriptor; the parent's copy
        # is no longer needed and can be closed safely.
        stdout_fh.close()

        # Record the process information in the global dictionary with thread safety.
        with _SEQSENDER_PROCESS_LOCK:
            _SEQSENDER_PROCESSES[upload_proc.pid] = {
                "process": upload_proc,
                "identity": f"{submission_name}_{organism}_GISAID_{submission_type}",
                "log_path": gisaid_stdout_path,
            }

        # Return the process ID and command for reference
        return {
            "status":  "success",
            "pid":     upload_proc.pid,
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Prepare SeqSender submission files without submitting to any portal
def prep_seqsender_submission(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str
) -> Dict[str, Any]:
    """
    Generate the per-database submission files (BioSample/SRA/GenBank/GISAID) for a stored
    submission without launching an actual submission to any portal.

    Args:
        submission_name (str): Name of the submission.
        organism (str): Type of organism.
        database (List[str]): List of databases to create submission files for.
        submission_type (str): Type of submissions: Test or Production.

    Returns:
        Dict[str, Any]: Dictionary containing the status, message, and created file locations.
    """
    try:
        # Check if submission for this submission_name exists in database
        selected_databases = [_normalize_seqsender_database(db) for db in database]
        db_submission_tbl = lookup_tbl_in_database(
            db_tbl_name = ["submission"],
            return_var = ["*"],
            filter_coln_var = ["submission_name", "organism", "database", "submission_type"],
            filter_coln_val = {"submission_name": [submission_name], "organism": [organism], "database": selected_databases, "submission_type": [submission_type]},
            filter_var_by = ["AND", "AND", "AND", "AND"]
        )
        # Check if submission exists in the database
        if db_submission_tbl.shape[0] == 0:
           raise ValueError(f"Submission '{submission_name}' does not exist in the database.")

        # Define the submission directory as seen by this backend process.
        submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
        submission_name_dir = os.path.join(submission_dir, submission_name)

        # Run the copied SeqSender application in its isolated Micromamba environment.
        seqsender_python, seqsender_script = _seqsender_cli_paths()
        prep_cmd = [
            seqsender_python,
            seqsender_script,
            "prep",
        ]
        cmd = [
            "--submission_dir", submission_dir,
            "--submission_name", submission_name,
            "--organism", organism
        ]

        # Check if config file exists in the submission directory
        config_file = os.path.join(submission_name_dir, CONFIG_FILENAME)
        if not os.path.exists(config_file):
            raise FileNotFoundError(f"Config file '{config_file}' does not exist.")
        else:
            cmd.extend(["--config_file", config_file])

        # Check if metadata file exists in the submission directory
        metadata_file = os.path.join(submission_name_dir, METADATA_FILENAME)
        if not os.path.exists(metadata_file):
            raise FileNotFoundError(f"Metadata file '{metadata_file}' does not exist.")
        else:
            cmd.extend(["--metadata_file", metadata_file])

        # Check if fasta file exists in the submission directory. Only pass --fasta_file when
        # GenBank is selected -- SeqSender validates the path even for BioSample/SRA-only runs.
        fasta_file = os.path.join(submission_name_dir, FASTA_FILENAME)
        if "GENBANK" in selected_databases:
            if not os.path.exists(fasta_file):
                raise FileNotFoundError(f"FASTA file '{fasta_file}' does not exist.")
            cmd.extend(["--fasta_file", fasta_file])

        # Work around the installed SeqSender build's raw_reads path bug (see helper docstring).
        if "SRA" in selected_databases:
            _absolutize_raw_reads_paths(metadata_file, submission_name_dir)

        # Reconcile sequence records when GenBank is selected, then record each database's
        # unique sample count using its own sample_name column.
        if "GENBANK" in selected_databases:
            _reconcile_fasta_with_metadata_samples(metadata_file, fasta_file)

        # Ensure that the metadata table has the expected structure before proceeding
        metadata_tbl = pl.read_csv(metadata_file)
        for target_database in selected_databases:
            n_kept_records = metadata_tbl.select(f"{database_prefixes[target_database]}-sample_name").unique().height
            update_tbl_in_database(
                db_tbl_name=["submission"],
                table=pl.DataFrame({"number_of_samples": [n_kept_records]}),
                filter_coln_var=["submission_name", "organism", "database", "submission_type"],
                filter_coln_val={
                    "submission_name": [submission_name],
                    "organism": [organism],
                    "database": [target_database],
                    "submission_type": [submission_type],
                },
                filter_var_by=["AND", "AND", "AND", "AND"],
            )

        # If gff file is true, check if it exists
        gff_file = db_submission_tbl.select("gff_file").to_series().to_list()[0]
        if gff_file:
            gff_file_path = os.path.join(submission_name_dir, GFF_FILENAME)
            if not os.path.exists(gff_file_path):
                raise FileNotFoundError(f"GFF file '{gff_file_path}' does not exist.")
            cmd.extend(["--gff_file", gff_file_path])

        # If table2asn is true, check if it exists
        table2asn = db_submission_tbl.select("table2asn").to_series().to_list()[0]
        if table2asn:
            cmd.extend(["--table2asn"])

        # Database selection flags -- these only select which per-database files "prep" creates,
        # no actual portal submission (and thus no GISAID CLI) is required for this command.
        if "BIOSAMPLE" in selected_databases:
            cmd.extend(["--biosample"])
        if "SRA" in selected_databases:
            cmd.extend(["--sra"])
        if "GENBANK" in selected_databases:
            cmd.extend(["--genbank"])
        if "GISAID" in selected_databases:
            cmd.extend(["--gisaid"])

        # Log the command that will be executed
        logger.info(
            f"Creating SeqSender submission files for '{submission_name}' with command:\n" +
            f"{seqsender_python} {seqsender_script} prep\n" +
            f" --submission_dir {submission_dir}\n" +
            f" --submission_name {submission_name}\n" +
            f" --organism {organism}\n" +
            (f" --biosample\n" if "BIOSAMPLE" in selected_databases else "") +
            (f" --sra\n" if "SRA" in selected_databases else "") +
            (f" --genbank\n" if "GENBANK" in selected_databases else "") +
            f" --config_file {config_file}\n" +
            f" --metadata_file {metadata_file}\n" +
            (f" --fasta_file {fasta_file}\n" if "GENBANK" in selected_databases else "") +
            (f" --gff_file {gff_file_path}\n" if gff_file else "") +
            (f" --table2asn\n" if table2asn else "")
        )

        # "prep" only writes local files (no network calls to submission portals), so run it
        # synchronously and return its outcome directly instead of tracking it as a background process.
        prep_proc = subprocess.run(
            prep_cmd + cmd,
            cwd=submission_name_dir,
            capture_output=True,
            text=True,
        )
        if prep_proc.returncode != 0:
            output = (prep_proc.stdout or "") + (prep_proc.stderr or "")
            raise Exception(output.strip()[-4000:] or f"SeqSender 'prep' exited with code {prep_proc.returncode}.")

        # Report which per-database submission_files subdirectories were actually created.
        submission_files_dir = os.path.join(submission_name_dir, "submission_files")
        created_databases = [
            db for db in selected_databases
            if os.path.isdir(os.path.join(submission_files_dir, db))
        ]

        return {
            "status": "success",
            "message": f"Submission files created for {', '.join(created_databases) or ', '.join(selected_databases)}.",
            "submission_files_dir": submission_files_dir,
            "databases": created_databases,
        }
    except ValueError as err:
        raise ValueError(str(err))
    except Exception as err:
        raise Exception(str(err))


# Check the lifecycle status of a SeqSender child process without a background waiter.
def retrieve_seqsender_process_status(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
    pid: int,
) -> Dict[str, Any]:
    
    # Ensure the submission exists in the database before attempting to retrieve its status.
    db_submission_tbl = lookup_tbl_in_database(
        db_tbl_name=["submission"],
        return_var=["*"],
        filter_coln_var=["submission_name", "organism", "database", "submission_type"],
        filter_coln_val={
            "submission_name": [submission_name],
            "organism": [organism],
            "database": database,
            "submission_type": [submission_type],
        },
        filter_var_by=["AND", "AND", "AND", "AND"],
    )
    # Check if the submission exists in the database.
    if db_submission_tbl.shape[0] == 0:
        raise ValueError(f"Submission '{submission_name}' does not exist in the database.")

    # Get submission status of the submission
    submission_status = db_submission_tbl.select("submission_status").to_series().to_list()[0]
    
    # Generate the unique identity for the SeqSender process based on the submission details.
    identity = _seqsender_process_identity(submission_name, organism, database, submission_type)
    with _SEQSENDER_PROCESS_LOCK:
        terminal_result = _SEQSENDER_TERMINAL_RESULTS.get(pid)
        process_record = _SEQSENDER_PROCESSES.get(pid)

    if terminal_result is not None:
        if terminal_result["identity"] != identity:
            raise ValueError(f"SeqSender process status does not match PID {pid}.")
        return terminal_result["payload"]

    # If the process has not terminated and is still being tracked, return its current status.
    if process_record is None:
        raise FileNotFoundError(
            f"SeqSender PID {pid} is not tracked by this backend process. "
            "The backend may have restarted after the submission was launched."
        )
    if process_record["identity"] != identity:
        raise ValueError(f"SeqSender process status does not match PID {pid}.")

    # Extract the process object from the process record for further inspection.
    process = process_record["process"]
    return_code = process.poll()

    # Check if the process is still running, keep status as previous submission status.
    if return_code is None:
        return {
            "status": submission_status,
            "pid": pid,
            "return_code": None,
            "message": "SeqSender submissions are being processed.",
        }

    # Handle the case where the process has finished and returned a code.
    if return_code == 0:
        status = "SUBMITTED"
        message = (
            f"Submissions have been submitted to {', '.join(database)} successfully. You can refresh its status periodically to track its progress."
        )
    else:
        status = "FAILED"
        log_error = _read_seqsender_error(process_record["log_path"])
        message = f"Submissions failed with exit code {return_code}."
        if log_error:
            message = f"{message}\n{log_error}"

    # Update the submission status in the database and record the terminal result.
    update_tbl_in_database(
        db_tbl_name=["submission"],
        table=pl.DataFrame({
            "submission_status": [status],
            "date_submitted": [date.today().isoformat()]
        }),
        filter_coln_var=["submission_name", "organism", "database", "submission_type"],
        filter_coln_val={
            "submission_name": [submission_name],
            "organism": [organism],
            "database": database,
            "submission_type": [submission_type],
        },
        filter_var_by=["AND", "AND", "AND", "AND"],
    )
    payload = {
        "status": status,
        "pid": pid,
        "return_code": return_code,
        "message": message,
    }

    # Cache the terminal result and stop tracking the finished process so repeat polls don't
    # re-read the log/re-write the database, and _SEQSENDER_PROCESSES doesn't grow unbounded.
    with _SEQSENDER_PROCESS_LOCK:
        _SEQSENDER_PROCESSES.pop(pid, None)
        _SEQSENDER_TERMINAL_RESULTS[pid] = {"identity": identity, "payload": payload}
        if len(_SEQSENDER_TERMINAL_RESULTS) > _MAX_TERMINAL_RESULTS:
            _SEQSENDER_TERMINAL_RESULTS.pop(next(iter(_SEQSENDER_TERMINAL_RESULTS)))

    return payload


# Function to check the status of a SeqSender submission.
def check_seqsender_submission(
    submission_name: str,
    organism: str,
    database: list[str],
    submission_type: str
) -> Dict[str, Any]:

    # Look up the submission record in the database.
    db_submission_tbl = lookup_tbl_in_database(
        db_tbl_name=["submission"],
        return_var=["*"],
        filter_coln_var=["submission_name", "organism", "database", "submission_type"],
        filter_coln_val={
            "submission_name": [submission_name],
            "organism": [organism],
            "database": database,
            "submission_type": [submission_type],
        },
        filter_var_by=["AND", "AND", "AND", "AND"],
    )
    # Raise an error if the submission does not exist in the database.
    if db_submission_tbl.is_empty():
        raise ValueError(f"Submission '{submission_name}' does not exist in the database.")

    # Ensure the submission directory exists.
    submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
    submission_name_dir = os.path.join(submission_dir, submission_name)
    if not os.path.isdir(submission_name_dir):
        raise ValueError(f"Submission directory '{submission_name_dir}' does not exist.")

    # Prepare the SeqSender CLI command to check the submission status.
    seqsender_python, seqsender_script = _seqsender_cli_paths()
    check_cmd = [
        seqsender_python,
        seqsender_script,
        "submission_status",
        "--submission_dir", submission_dir,
        "--submission_name", submission_name,
    ]

    # Execute the SeqSender CLI command and capture the output.
    check_result = subprocess.run(
        check_cmd,
        cwd=submission_name_dir,
        capture_output=True,
        text=True,
    )

    # Check if the SeqSender CLI command executed successfully.
    if check_result.returncode != 0:
        return {
            "status": "FAILED",
            "database_statuses": {},
            "submission_status_report": {},
            "message": f"SeqSender status check failed with exit code {check_result.returncode}. Error: {check_result.stderr.strip()}. NCBI's FTP Server is currently unavailable. Try refresh the status again later.",
        }
    
    # Get submission status from the database record.
    submission_status = load_submission_status(
        submission_name=submission_name,
        organism=organism,
        database=database,
        submission_type=submission_type,
    )

    # Return the submission status retrieved from the database.
    return submission_status


# Load submission log and submission status report for a given submission.
def load_submission_status(
    submission_name: str,
    organism: str,
    database: List[str],
    submission_type: str,
):
    # Look up the submission record in the database.
    db_submission_tbl = lookup_tbl_in_database(
        db_tbl_name=["submission"],
        return_var=["*"],
        filter_coln_var=["submission_name", "organism", "database", "submission_type"],
        filter_coln_val={
            "submission_name": [submission_name],
            "organism": [organism],
            "database": database,
            "submission_type": [submission_type],
        },
        filter_var_by=["AND", "AND", "AND", "AND"],
    )
    # Raise an error if the submission does not exist in the database.
    if db_submission_tbl.is_empty():
        raise ValueError(f"Submission '{submission_name}' does not exist in the database.")
    
    # Retrieve values from the submission.
    submission_status = db_submission_tbl.select("submission_status").to_series().to_list()[0]
    table2asn = any(
        _normalize_seqsender_database(str(row["database"])) == "GENBANK"
        and bool(row.get("table2asn"))
        for row in db_submission_tbl.to_dicts()
    )    

   # Ensure the submission directory exists.
    submission_dir = os.path.realpath(os.path.join(_DEFAULT_SEQSENDER_STORAGE_PATH, organism))
    submission_name_dir = os.path.join(submission_dir, submission_name)
    if not os.path.isdir(submission_name_dir):
        raise ValueError(f"Submission directory '{submission_name_dir}' does not exist.")

    # SeqSender stores one shared CSV log per organism. Keep the older per-submission
    # location as a fallback for submissions created by earlier deployments.
    submission_log_file = os.path.join(submission_dir, SUBMISSION_LOG_FILENAME)
    if not os.path.isfile(submission_log_file):
        raise ValueError(
            f"Submission log file '{SUBMISSION_LOG_FILENAME}' does not exist in "
            f"'{submission_dir}'."
        )
    
    #  Ensure the submission status report file exists before proceeding.
    submission_status_report_dir = os.path.join(submission_name_dir, "submission_files")
    submission_status_report_file = os.path.join(submission_status_report_dir, SUBMISSION_STATUS_REPORT_FILENAME)
    if not os.path.isfile(submission_status_report_file):
        raise ValueError(
            f"Submission status report file '{SUBMISSION_STATUS_REPORT_FILENAME}' does not exist in "
            f"'{submission_status_report_dir}'."
        )
    
    # Read the submission log to extract the details for the specified database.
    database_statuses = _read_submission_log(
        submission_log_file = submission_log_file,
        submission_name = submission_name,
        organism = organism,
        database = database,
        submission_type = submission_type,
        table2asn = table2asn,
    )

    # Read the per-sample submission status report for the specified databases.
    submission_status_report = _read_submission_status_report(
        submission_status_report_file = submission_status_report_file,
        database = database,
    )

    # Update the submission status for each database.
    _update_database_submission_status(
        submission_name = submission_name,
        organism = organism,
        submission_type = submission_type,
        database_details = database_statuses,
    )

    # Determine the overall status based on the individual database statuses.
    db_statuses = [details["status"] for target_database, details in database_statuses.items()]
    if all(value == "COMPLETED" for value in db_statuses):
        submission_status = "COMPLETED"
    else:
        submission_status = "PROCESSING"

    # Update overall submission status in the database.
    update_tbl_in_database(
        table=pl.DataFrame({"submission_status": [submission_status]}),
        db_tbl_name=["submission"],
        filter_coln_var=["submission_name", "organism", "submission_type"],
        filter_coln_val={
            "submission_name": [submission_name],
            "organism": [organism],
            "submission_type": [submission_type.strip().upper()],
        },
        filter_var_by=["AND", "AND"],
    )

    # Return submission status and details. database_statuses is trimmed down to just the
    # {status, accession} fields the frontend renders (badge label + accession number),
    # dropping the raw "submission_status" field used only internally above.
    return {
        "status": submission_status,
        "database_statuses": {
            target_database: {"status": details["submission_status"], "accession": details["submission_id"]}
            for target_database, details in database_statuses.items()
        },
        "submission_status_report": submission_status_report,
        "message": f"Submission status was successfully pulled and updated accordingly.",
    }
