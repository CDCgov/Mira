from unittest import TestCase
from unittest.mock import patch

import polars as pl

from app.seqsender_handler import delete_seqsender_submission


class DeleteSeqsenderSubmissionTests(TestCase):
    @patch("app.seqsender_handler.shutil.rmtree")
    @patch("app.seqsender_handler.os.path.exists", return_value=True)
    @patch("app.seqsender_handler.delete_val_in_database")
    @patch("app.seqsender_handler.lookup_tbl_in_database")
    def test_rejects_mismatched_database_set(
        self,
        lookup_submission,
        delete_submission,
        _path_exists,
        remove_directory,
    ):
        lookup_submission.return_value = pl.DataFrame({
            "database": ["GENBANK", "SRA"],
        })

        with self.assertRaisesRegex(ValueError, "no longer match"):
            delete_seqsender_submission(
                submission_name="submission-one",
                organism="FLU",
                database=["GENBANK"],
                submission_type="TEST",
            )

        delete_submission.assert_not_called()
        remove_directory.assert_not_called()

    @patch("app.seqsender_handler.shutil.rmtree")
    @patch("app.seqsender_handler.os.path.exists", return_value=True)
    @patch("app.seqsender_handler.delete_val_in_database")
    @patch("app.seqsender_handler.lookup_tbl_in_database")
    def test_deletes_only_exact_identity_and_preserves_shared_directory(
        self,
        lookup_submission,
        delete_submission,
        _path_exists,
        remove_directory,
    ):
        lookup_submission.side_effect = [
            pl.DataFrame({"database": ["GENBANK", "SRA"]}),
            pl.DataFrame({"submission_type": ["TEST", "PRODUCTION"]}),
        ]

        result = delete_seqsender_submission(
            submission_name="submission-one",
            organism="FLU",
            database=["SRA", "GENBANK"],
            submission_type="TEST",
        )

        delete_submission.assert_called_once_with(
            db_tbl_name=["submission"],
            delete_coln_var=["submission_name", "organism", "database", "submission_type"],
            delete_coln_val={
                "submission_name": ["submission-one"],
                "organism": ["FLU"],
                "database": ["GENBANK", "SRA"],
                "submission_type": ["TEST"],
            },
            delete_var_by=["AND", "AND", "AND"],
        )
        remove_directory.assert_not_called()
        self.assertEqual(result["status"], "success")

    @patch("app.seqsender_handler.shutil.rmtree")
    @patch("app.seqsender_handler.os.path.exists", return_value=True)
    @patch("app.seqsender_handler.delete_val_in_database")
    @patch("app.seqsender_handler.lookup_tbl_in_database")
    def test_removes_directory_when_no_sibling_submission_remains(
        self,
        lookup_submission,
        _delete_submission,
        _path_exists,
        remove_directory,
    ):
        lookup_submission.side_effect = [
            pl.DataFrame({"database": ["BIOSAMPLE"]}),
            pl.DataFrame({"submission_type": ["TEST"]}),
        ]

        delete_seqsender_submission(
            submission_name="submission-one",
            organism="FLU",
            database=["BIOSAMPLE"],
            submission_type="TEST",
        )

        remove_directory.assert_called_once()