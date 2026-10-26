from unittest import TestCase
from unittest.mock import patch

import polars as pl
from pydantic import ValidationError

from app.schema import SubmitterInfo
from app.schema_validator import submitter_db_schema
from app.seqsender_handler import delete_submitter, save_submitter

SUBMITTER = dict(
    submitter_name="user1", submitter_password="pw", submission_portal="NCBI", ncbi_spuid_namespace="ns",
    ncbi_org_role="owner", ncbi_org_type="institute", ncbi_org_name="CDC", ncbi_org_affiliation="CDC",
    ncbi_org_division="DIV", ncbi_addr_street="1 Main", ncbi_addr_city="Atlanta", ncbi_addr_state="GA",
    ncbi_addr_postal_code="30333", ncbi_addr_country="USA", ncbi_addr_email="a@b.com", ncbi_addr_phone="1",
    ncbi_submitter_email="a@b.com", ncbi_submitter_first_name="A", ncbi_submitter_last_name="B",
)


def empty_submitter_table() -> pl.DataFrame:
    return pl.DataFrame(schema={name: column.dtype.type for name, column in submitter_db_schema.columns.items()})


class SubmitterOrganismTests(TestCase):
    def test_organism_is_required_and_validated(self):
        with self.assertRaises(ValidationError):
            SubmitterInfo(**SUBMITTER)
        with self.assertRaises(ValidationError):
            SubmitterInfo(**SUBMITTER, organism="NOT-AN-ORGANISM")
        self.assertEqual(SubmitterInfo(**SUBMITTER, organism="FLU").organism, "FLU")

    @patch("app.seqsender_handler.insert_tbl_to_database")
    @patch("app.seqsender_handler.lookup_tbl_in_database")
    def test_new_submitter_is_stored_with_its_organism(self, lookup, insert):
        lookup.side_effect = [empty_submitter_table(), empty_submitter_table()]
        info = SubmitterInfo(**SUBMITTER, organism="COV")

        result = save_submitter(pl.DataFrame([info.model_dump()]))

        stored = insert.call_args.kwargs["table"]
        self.assertEqual(stored["organism"].to_list(), ["COV"])
        first_lookup = lookup.call_args_list[0].kwargs
        self.assertEqual(first_lookup["filter_coln_var"], ["submitter_name", "organism", "submission_portal"])
        self.assertEqual(first_lookup["filter_coln_val"]["organism"], ["COV"])
        self.assertIn("(COV)", result["message"])

    @patch("app.seqsender_handler.delete_val_in_database")
    @patch("app.seqsender_handler.lookup_tbl_in_database")
    def test_delete_only_removes_the_given_organism(self, lookup, delete):
        lookup.return_value = pl.DataFrame({"organism": ["FLU"]})

        delete_submitter("user1", "FLU", "NCBI")

        kwargs = delete.call_args.kwargs
        self.assertEqual(kwargs["delete_coln_var"], ["submitter_name", "organism", "submission_portal"])
        self.assertEqual(kwargs["delete_coln_val"]["organism"], ["FLU"])

    @patch("app.seqsender_handler.delete_val_in_database")
    @patch("app.seqsender_handler.lookup_tbl_in_database", return_value=pl.DataFrame())
    def test_delete_reports_a_missing_organism(self, _lookup, delete):
        with self.assertRaisesRegex(ValueError, r"\(COV\)"):
            delete_submitter("user1", "COV", "NCBI")
        delete.assert_not_called()
