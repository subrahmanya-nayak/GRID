# -*- coding: utf-8 -*-
import os
import re
import requests
import pandas as pd
from rich.console import Console
from IPython.display import display

console = Console()

# === Phase Extractor ===
def extract_phase(query):
    phase_match = re.search(r"(phase[-\s]*[1-4])", query, re.IGNORECASE)
    return phase_match.group(1).replace(" ", "-").title() if phase_match else None

# === ClinicalTrials.gov Fetcher ===
def fetch_clinical_trials(condition=None, intervention=None, phase=None, status=None, location=None):
    base_url = "https://clinicaltrials.gov/api/v2/studies"
    params = {"pageSize": 50}
    if condition:
        params["query.cond"] = condition
    if intervention:
        params["query.intr"] = intervention
    if status:
        params["filter.overallStatus"] = status
    if location:
        params["query.locn"] = location

    trials = []
    while True:
        try:
            response = requests.get(base_url, params=params, timeout=20)
        except Exception as e:
            console.log(f"[red]API request error: {e}[/red]")
            break

        if response.status_code != 200:
            console.log(f"[red]ClinicalTrials.gov API failed: {response.status_code}[/red]")
            break

        data = response.json()
        studies = data.get("studies", [])
        if not studies:
            break

        for study in studies:
            protocol = study.get("protocolSection", {})
            identification = protocol.get("identificationModule", {})
            nctId = identification.get("nctId", "N/A")
            title = identification.get("briefTitle") or nctId or "Clinical trial"
            status_val = protocol.get("statusModule", {}).get("overallStatus", "Unknown")
            conds = ", ".join(protocol.get("conditionsModule", {}).get("conditions", []))
            interventions = protocol.get("armsInterventionsModule", {}).get("interventions", [])
            interventions_str = ", ".join([i.get("name", "") for i in interventions]) or "None"
            phases = ", ".join(protocol.get("designModule", {}).get("phases", []))
            trial_url = f"https://clinicaltrials.gov/study/{nctId}" if nctId and nctId != "N/A" else ""

            if phase and phases and phase.lower() not in phases.lower():
                continue

            trials.append({
                "title": title,
                "NCT Number": nctId,
                "Status": status_val,
                "Condition": conds,
                "Interventions": interventions_str,
                "Phases": phases,
                "url": trial_url,
            })

        nextPageToken = data.get("nextPageToken")
        if nextPageToken:
            params["pageToken"] = nextPageToken
        else:
            break

    df = pd.DataFrame(trials).drop_duplicates(subset=["NCT Number"])
    df.attrs.update({
        "source": "ClinicalTrials.gov",
        "title_field": ("title", "NCT Number"),
        "summary_field": ("Status",),
        "link_field": ("url",),
    })
    return df

# === Save & Display ===
def sanitize_filename(name):
    return re.sub(r'[^A-Za-z0-9_\-\.]', '_', name) if name else None

def display_and_save_results(df, filename):
    os.makedirs("output", exist_ok=True)
    filepath = os.path.join("output", sanitize_filename(filename) or "trials_results.csv")
    try:
        display(df)
    except Exception:
        console.log("[yellow]Could not render dataframe; continuing.[/yellow]")
    df.to_csv(filepath, index=False)
    console.log(f"[green]Trials saved to {filepath}[/green]")

# === Retriever Agent ===
def retrieve_trials(parsed_query: dict, original_query: str):
    console.rule("[bold magenta]Retriever Agent[/bold magenta]")

    condition = parsed_query.get("Condition/Disease")
    drug = parsed_query.get("Intervention/Treatment/Drug")
    location = parsed_query.get("Location")
    status = parsed_query.get("Status")
    phase = parsed_query.get("Phase") or extract_phase(original_query)

    console.log(f"[cyan]Running retrieval with:[/cyan] {parsed_query}")

    parts = [str(x) for x in [condition, drug, phase] if x]
    filename = "_".join(parts) + "_trials.csv" if parts else "trials_results.csv"

    # ?? Always initialize df (empty by default)
    df = pd.DataFrame()

    try:
        df = fetch_clinical_trials(condition, drug, phase, status, location)
        if not df.empty:
            display_and_save_results(df, filename)
        else:
            console.log("[yellow]No trials found for this query.[/yellow]")
    except Exception as e:
        console.log(f"[red]Retriever failed: {e}[/red]")

    return df
