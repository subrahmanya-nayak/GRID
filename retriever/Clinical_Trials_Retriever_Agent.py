# -*- coding: utf-8 -*-
from __future__ import annotations

"""Utilities for retrieving and persisting ClinicalTrials.gov search results."""

import os
import re
from json import JSONDecodeError
from typing import Dict, List, Optional

import pandas as pd
import requests
from rich.console import Console

try:  # pragma: no cover - optional dependency
    from IPython.display import display  # type: ignore
except ImportError:  # pragma: no cover - IPython is optional for the CLI usage
    display = None

console = Console()

_PHASE_PATTERN = re.compile(
    r"phase\s*(?:(?P<num>[1-4])|(?P<roman>i{1,3}|iv))",
    flags=re.IGNORECASE,
)


def extract_phase(query: str) -> Optional[str]:
    """Extract a clinical trial phase token from a free-text query.

    The ClinicalTrials.gov API expects phases as ``Phase 1`` … ``Phase 4``. Users
    routinely provide values such as ``phase 2`` or ``Phase II``; this helper
    normalises those variants into the canonical label. If no phase hint is
    present ``None`` is returned so the API may broaden the search.
    """

    if not query:
        return None

    match = _PHASE_PATTERN.search(query)
    if not match:
        return None

    if match.group("num"):
        phase_number = match.group("num")
    else:
        roman = match.group("roman").lower()
        roman_to_number = {"i": "1", "ii": "2", "iii": "3", "iv": "4"}
        phase_number = roman_to_number.get(roman)
        if not phase_number:
            return None

    return f"Phase {phase_number}"

# === ClinicalTrials.gov Fetcher ===
def fetch_clinical_trials(
    condition: Optional[str] = None,
    intervention: Optional[str] = None,
    phase: Optional[str] = None,
    status: Optional[str] = None,
    location: Optional[str] = None,
    *,
    page_size: int = 50,
    timeout: int = 20,
) -> pd.DataFrame:
    """Query the ClinicalTrials.gov v2 API and return a DataFrame of studies."""

    base_url = "https://clinicaltrials.gov/api/v2/studies"
    params: Dict[str, str] = {"pageSize": str(page_size)}
    if condition:
        params["query.cond"] = condition
    if intervention:
        params["query.intr"] = intervention
    if status:
        params["filter.overallStatus"] = status
    if location:
        params["query.locn"] = location

    trials: List[Dict[str, str]] = []
    while True:
        try:
            response = requests.get(base_url, params=params, timeout=timeout)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"ClinicalTrials.gov request failed: {exc}") from exc

        try:
            data = response.json()
        except (ValueError, JSONDecodeError) as exc:
            raise RuntimeError(
                "ClinicalTrials.gov returned invalid JSON payload"
            ) from exc
        studies = data.get("studies", [])
        if not studies:
            break

        for study in studies:
            protocol = study.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            nct_id = identification.get("nctId", "N/A")
            title = identification.get("briefTitle") or nct_id or "Clinical trial"
            status_val = (
                protocol.get("statusModule", {}).get("overallStatus", "Unknown")
            )
            conditions = ", ".join(
                protocol.get("conditionsModule", {}).get("conditions", [])
            )
            interventions = protocol.get("armsInterventionsModule", {}).get(
                "interventions", []
            )
            interventions_str = (
                ", ".join(intervention.get("name", "") for intervention in interventions)
                or "None"
            )
            phase_labels = protocol.get("designModule", {}).get("phases", [])
            phases = ", ".join(phase_labels)
            trial_url = (
                f"https://clinicaltrials.gov/study/{nct_id}"
                if nct_id and nct_id != "N/A"
                else ""
            )

            if phase and phases and phase.lower() not in phases.lower():
                continue

            trials.append(
                {
                    "title": title,
                    "NCT Number": nct_id,
                    "Status": status_val,
                    "Condition": conditions,
                    "Interventions": interventions_str,
                    "Phases": phases,
                    "url": trial_url,
                }
            )

        next_page_token = data.get("nextPageToken")
        if next_page_token:
            params["pageToken"] = next_page_token
        else:
            break

    df = pd.DataFrame(trials).drop_duplicates(subset=["NCT Number"])
    df.attrs.update(
        {
            "source": "ClinicalTrials.gov",
            "title_field": ("title", "NCT Number"),
            "summary_field": ("Status",),
            "link_field": ("url",),
        }
    )
    return df

# === Save & Display ===
def sanitize_filename(name: Optional[str]) -> Optional[str]:
    """Return a filesystem-safe filename derived from ``name``."""

    return re.sub(r"[^A-Za-z0-9_\-\.]", "_", name) if name else None

def display_and_save_results(df: pd.DataFrame, filename: str) -> str:
    """Persist the DataFrame to disk and render it if an IPython display exists."""

    os.makedirs("output", exist_ok=True)
    sanitized = sanitize_filename(filename) or "trials_results.csv"
    filepath = os.path.join("output", sanitized)

    if display is not None:
        try:  # pragma: no cover - requires IPython rich repr
            display(df)
        except Exception:
            console.log("[yellow]Could not render dataframe; continuing.[/yellow]")

    df.to_csv(filepath, index=False)
    console.log(f"[green]Trials saved to {filepath}[/green]")
    return filepath

# === Retriever Agent ===
def retrieve_trials(parsed_query: Dict[str, Optional[str]], original_query: str) -> pd.DataFrame:
    console.rule("[bold magenta]Retriever Agent[/bold magenta]")

    condition = parsed_query.get("Condition/Disease")
    drug = parsed_query.get("Intervention/Treatment/Drug")
    location = parsed_query.get("Location")
    status = parsed_query.get("Status")
    phase = parsed_query.get("Phase") or extract_phase(original_query)

    console.log(f"[cyan]Running retrieval with:[/cyan] {parsed_query}")

    parts = [str(x) for x in [condition, drug, phase] if x]
    filename = "_".join(parts) + "_trials.csv" if parts else "trials_results.csv"

    try:
        df = fetch_clinical_trials(condition, drug, phase, status, location)
    except RuntimeError as exc:
        console.log(f"[red]Retriever failed: {exc}[/red]")
        return pd.DataFrame()

    if df.empty:
        console.log("[yellow]No trials found for this query.[/yellow]")
        return df

    display_and_save_results(df, filename)
    return df
