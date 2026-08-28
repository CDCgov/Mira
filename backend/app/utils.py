# Import future annotations for Pydantic models
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any

# Python packages to work with data frame
import polars as pl
from pl_compare import compare

# Import sqlite handler for database operations
from .sqlite_handler import (
    insert_tbl_to_database,
    update_tbl_in_database,
)

# Function to join two dataframes while ignoring case sensitivity in the join keys
def join_ignore_case(df1: pl.DataFrame, df2: pl.DataFrame, on: List[str], how: Literal["left", "right", "full", "semi", "anti", "cross"] = "left") -> pl.DataFrame:
    """
    Join two dataframes while ignoring case sensitivity in the join keys.
    Only string columns are lowercased; numeric and other types are joined as-is.
    """
    # Identify which join columns are string type (only those need case normalization)
    str_cols = [col for col in on if df1[col].dtype == pl.Utf8 or df1[col].dtype == pl.String]
    # Create normalized versions of the string join keys in both dataframes
    for col in str_cols:
        df1 = df1.with_columns(pl.col(col).str.to_lowercase().alias(f"{col}_lower"))
        df2 = df2.with_columns(pl.col(col).str.to_lowercase().alias(f"{col}_lower"))
    # Replace string join keys with their lowercased versions for the join
    if str_cols:
        df1_lower = df1.with_columns([pl.col(f"{col}_lower").alias(col) for col in str_cols])
        df2_lower = df2.with_columns([pl.col(f"{col}_lower").alias(col) for col in str_cols])
    else:
        df1_lower = df1
        df2_lower = df2
    # Perform the join
    joined_df = df1_lower.join(df2_lower, on=on, how=how)
    # Drop the temporary lowercase columns
    for col in str_cols:
        joined_df = joined_df.drop(f"{col}_lower")
    # Return the joined dataframe
    return joined_df

# Define function to compare two tables and return the comparison result
def compare_and_update_db_table(unique_cols: List[str], compare_tbl: pl.DataFrame, db_tbl: pl.DataFrame, db_tbl_name: str) -> None:
    # Normalize case for comparison (lowercase key columns only)
    compare_tbl_norm = compare_tbl.with_columns([pl.col(c).cast(pl.String).str.to_lowercase().alias(c) for c in unique_cols])
    db_tbl_norm = db_tbl.with_columns([pl.col(c).cast(pl.String).str.to_lowercase().alias(c) for c in unique_cols])
    # Get anti-join between compare and database table (case-insensitive)
    tbl_anti_join = join_ignore_case(compare_tbl_norm, db_tbl_norm, on=unique_cols, how="anti")
    # Upload rows with different values 
    if tbl_anti_join.shape[0] > 0:
        # Get index of anti-join entries in compare_tbl_norm, retrieve original rows
        anti_join_idx = (
            compare_tbl_norm
            .with_row_index("_idx")
            .join(tbl_anti_join, on=unique_cols, how="inner")
            ["_idx"]
            .to_list()
        )
        upload_tbl = compare_tbl[anti_join_idx]
        # Insert new entries into database
        insert_tbl_to_database(
            db_tbl_name = [db_tbl_name],
            table = upload_tbl 
        )
    # Compare assembly table and database assembly table and update overlapping rows with different values
    tbl_compare = compare(unique_cols, compare_tbl_norm, db_tbl_norm)    
    # Upload matching rows with different values
    if not tbl_compare.is_equal() and tbl_compare.values_sample().shape[0] > 0:
        # Get normalized diff keys, find matching row indices in compare_tbl_norm, retrieve original rows
        diff_keys = tbl_compare.values_sample().select(unique_cols)
        matching_idx = (
            compare_tbl_norm
            .with_row_index("_idx")
            .join(diff_keys, on=unique_cols, how="inner")
            ["_idx"]
            .to_list()
        )
        update_tbl = compare_tbl[matching_idx]     
        # Update rows one by one
        for l in range(update_tbl.shape[0]):
            update_tbl_in_database(
                db_tbl_name = [db_tbl_name],
                table = update_tbl.slice(l, 1),
                filter_coln_var = [*unique_cols],
                filter_coln_val = {col: [update_tbl[col][l]] for col in unique_cols},
                filter_var_by = ["AND"] * (len(unique_cols) - 1),
            )
            
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