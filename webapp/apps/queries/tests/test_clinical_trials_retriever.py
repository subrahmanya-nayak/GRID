from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
from django.test import SimpleTestCase

from retriever.Clinical_Trials_Retriever_Agent import (
    display_and_save_results,
    extract_phase,
    sanitize_filename,
)


class ExtractPhaseTests(SimpleTestCase):
    def test_returns_none_when_no_phase_present(self) -> None:
        self.assertIsNone(extract_phase("Latest immunotherapy approaches"))

    def test_extracts_numeric_phase(self) -> None:
        self.assertEqual(extract_phase("Need phase 3 lung cancer trials"), "Phase 3")

    def test_extracts_roman_phase(self) -> None:
        self.assertEqual(extract_phase("looking for Phase II studies"), "Phase 2")


class SanitizeFilenameTests(SimpleTestCase):
    def test_replaces_illegal_characters(self) -> None:
        self.assertEqual(sanitize_filename("lung cancer?:phase 2"), "lung_cancer__phase_2")

    def test_returns_none_for_empty_values(self) -> None:
        self.assertIsNone(sanitize_filename(None))


class DisplayAndSaveResultsTests(SimpleTestCase):
    def test_writes_csv_and_returns_path(self) -> None:
        df = pd.DataFrame([{"title": "trial", "NCT Number": "NCT1"}])
        filename = "trial:results.csv"

        output_path = display_and_save_results(df, filename)

        try:
            self.assertTrue(Path(output_path).exists())
            with open(output_path, "r", encoding="utf-8") as handle:
                contents = handle.read()
            self.assertIn("NCT1", contents)
            self.assertTrue(output_path.endswith("trial_results.csv"))
        finally:
            if os.path.exists(output_path):
                os.remove(output_path)
