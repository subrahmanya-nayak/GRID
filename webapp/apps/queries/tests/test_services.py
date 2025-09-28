from __future__ import annotations

import pandas as pd
from django.test import SimpleTestCase

from apps.queries.services import normalize_results


class NormalizeResultsTests(SimpleTestCase):
    def test_dataframe_rows_are_expanded_with_metadata(self) -> None:
        df = pd.DataFrame([
            {
                'title': 'mRNA vaccine trial',
                'NCT Number': 'NCT12345678',
                'Status': 'Recruiting',
                'Condition': 'Lung Cancer',
                'Interventions': 'Drug A',
                'Phase': 'Phase 2',
                'url': 'https://clinicaltrials.gov/study/NCT12345678',
            }
        ])
        df.attrs.update(
            {
                'source': 'ClinicalTrials.gov',
                'title_field': ('title', 'NCT Number'),
                'summary_field': ('Status',),
                'link_field': ('url',),
            }
        )

        results = normalize_results([df])
        self.assertEqual(len(results), 1)
        entry = results[0]
        self.assertEqual(entry['source'], 'ClinicalTrials.gov')
        self.assertEqual(entry['title'], 'mRNA vaccine trial')
        self.assertEqual(entry['summary'], 'Recruiting')
        self.assertEqual(entry['link'], 'https://clinicaltrials.gov/study/NCT12345678')
        fields = {item['label']: item['value'] for item in entry['fields']}
        self.assertEqual(fields['Trial phase'], 'Phase 2')
        self.assertEqual(fields['Condition'], 'Lung Cancer')
        self.assertEqual(fields['Interventions'], 'Drug A')

    def test_nested_sequences_and_dicts_normalize(self) -> None:
        payload = [
            [
                {
                    'source': 'Open Targets',
                    'name': 'Drug B',
                    'Mechanism': 'Inhibitor',
                    'score': 0.82,
                }
            ],
            None,
        ]

        results = normalize_results(payload)
        self.assertEqual(len(results), 1)
        entry = results[0]
        self.assertEqual(entry['source'], 'Open Targets')
        self.assertEqual(entry['title'], 'Drug B')
        fields = {item['label']: item['value'] for item in entry['fields']}
        self.assertEqual(fields['Mechanism'], 'Inhibitor')
        self.assertEqual(fields['Score'], '0.82')
