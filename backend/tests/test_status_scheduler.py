from unittest import TestCase
from unittest.mock import patch

import polars as pl

from app.status_scheduler import update_all_submission_statuses


class UpdateAllSubmissionStatusesTests(TestCase):
    @patch("app.status_scheduler._record_run")
    @patch("app.status_scheduler.check_seqsender_submission")
    @patch("app.status_scheduler.lookup_tbl_in_database")
    def test_skips_submission_when_any_active_database_is_created(
        self,
        lookup_submission,
        check_submission,
        record_run,
    ):
        lookup_submission.return_value = pl.DataFrame(
            [
                {
                    "submission_name": "mixed-status",
                    "organism": "FLU",
                    "database": "GENBANK",
                    "submission_type": "consensus",
                    "submission_status": "SUBMITTED",
                    "ncbi_submission_status": None,
                },
                {
                    "submission_name": "ready",
                    "organism": "FLU",
                    "database": "GENBANK",
                    "submission_type": "consensus",
                    "submission_status": "PROCESSING",
                    "ncbi_submission_status": None,
                },
                {
                    "submission_name": "mixed-status",
                    "organism": "FLU",
                    "database": "NCBI",
                    "submission_type": "consensus",
                    "submission_status": "CREATED",
                    "ncbi_submission_status": None,
                },
                {
                    "submission_name": "ready",
                    "organism": "FLU",
                    "database": "NCBI",
                    "submission_type": "consensus",
                    "submission_status": "SUBMITTED",
                    "ncbi_submission_status": "SUBMITTED",
                },
            ]
        )
        check_submission.return_value = {"status": "PROCESSING"}

        summary = update_all_submission_statuses()

        lookup_submission.assert_called_once_with(
            db_tbl_name=["submission"],
            return_var=[
                "submission_name",
                "organism",
                "database",
                "submission_type",
                "submission_status",
                "ncbi_submission_status",
            ],
            filter_coln_var=["database_status"],
            filter_coln_val={"database_status": ["ACTIVE"]},
        )
        check_submission.assert_called_once_with(
            submission_name="ready",
            organism="FLU",
            database=["GENBANK", "NCBI"],
            submission_type="consensus",
        )
        self.assertEqual(
            summary,
            {
                "checked": 1,
                "succeeded": 1,
                "failed": 0,
                "skipped_created": 1,
                "errors": [],
            },
        )
        record_run.assert_called_once()

    @patch("app.status_scheduler._record_run")
    @patch("app.status_scheduler.check_seqsender_submission")
    @patch("app.status_scheduler.lookup_tbl_in_database")
    def test_excludes_created_and_processed_database_rows(
        self,
        lookup_submission,
        check_submission,
        record_run,
    ):
        lookup_submission.return_value = pl.DataFrame(
            [
                {
                    "submission_name": "partially-finished",
                    "organism": "FLU",
                    "database": "BIOSAMPLE",
                    "submission_type": "TEST",
                    "submission_status": "PROCESSING",
                    "ncbi_submission_status": "PROCESSED",
                },
                {
                    "submission_name": "partially-finished",
                    "organism": "FLU",
                    "database": "SRA",
                    "submission_type": "TEST",
                    "submission_status": "PROCESSING",
                    "ncbi_submission_status": "PROCESSING",
                },
                {
                    "submission_name": "raw-created",
                    "organism": "FLU",
                    "database": "GENBANK",
                    "submission_type": "TEST",
                    "submission_status": "PROCESSING",
                    "ncbi_submission_status": "CREATED",
                },
            ]
        )
        check_submission.return_value = {"status": "PROCESSING"}

        summary = update_all_submission_statuses()

        check_submission.assert_called_once_with(
            submission_name="partially-finished",
            organism="FLU",
            database=["SRA"],
            submission_type="TEST",
        )
        self.assertEqual(summary["checked"], 1)
        self.assertEqual(summary["succeeded"], 1)
        record_run.assert_called_once()