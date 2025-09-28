import json
import logging
from rich.console import Console

from query_parser.open_targets_query_parser import QueryParser
from normalizer.open_targets_normalizer import Normalizer
from retriever.open_targets_retriever import (
    query_disease_known_drugs,
    query_drug_indications,
    query_target_associated_diseases,
    merge_and_rank,
)
from utils.helpers import save_results

logging.basicConfig(level=logging.INFO)
console = Console()

def extract_and_normalize(sentence):
    parser = QueryParser()
    normalizer = Normalizer()

    output_json_str = parser.extract_entities(sentence)

    if output_json_str.startswith("```"):
        output_json_str = output_json_str.strip("` \n\r")
        if output_json_str.lower().startswith("json"):
            output_json_str = output_json_str[4:].strip()

    try:
        entities = json.loads(output_json_str)
    except json.JSONDecodeError as e:
        logging.error(f"Failed to parse JSON output from LLM. Error: {e}")
        logging.error(f"Raw output was: {output_json_str}")
        return None

    efo_results = {}
    for key in ["drug", "disease", "target"]:
        terms = entities.get(key, [])
        if not isinstance(terms, list):
            terms = [terms] if terms else []

        normalized_list = []
        for term in terms:
            term = term.strip()
            if term:
                efo_id = None
                chembl_id = None
                try:
                    efo_id = normalizer.get_efo_id_from_zooma(term)
                except Exception as e:
                    logging.warning(f"No EFO ID for {key} '{term}': {e}")

                if key == "drug" and efo_id is None:
                    chembl_id = normalizer.get_chembl_id(term)

                normalized_list.append({
                    "term": term,
                    "efo_id": efo_id,
                    "chembl_id": chembl_id
                })
        efo_results[key] = normalized_list

    return efo_results

def run_pipeline(input_sentence: str):
    console.print(f"[bold blue]Running pipeline for:[/bold blue] {input_sentence}")
    results = extract_and_normalize(input_sentence)
    if results is None:
        console.print("[red]Entity extraction or normalization failed.[/red]")
        return

    disease_known_drugs_rows = []
    drug_indications_rows = []
    target_associated_diseases_rows = []

    for item in results["disease"]:
        if item["efo_id"]:
            try:
                rows = query_disease_known_drugs(item["efo_id"])
                disease_known_drugs_rows.extend(rows)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    for item in results["drug"]:
        if item["chembl_id"]:
            try:
                rows = query_drug_indications(item["chembl_id"])
                drug_indications_rows.extend(rows)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    for item in results["disease"]:
        if item["efo_id"]:
            try:
                rows = query_target_associated_diseases(item["efo_id"])
                target_associated_diseases_rows.extend(rows)
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    merged_df, targets_df = merge_and_rank(
        disease_known_drugs_rows,
        drug_indications_rows,
        target_associated_diseases_rows
    )

    save_results(disease_known_drugs_rows, "disease_known_drugs.csv")
    save_results(drug_indications_rows, "drug_indications.csv")
    save_results(target_associated_diseases_rows, "target_associated_targets.csv")
    save_results(merged_df.to_dict(orient="records"), "merged_results.csv")
    save_results(targets_df.to_dict(orient="records"), "targets_only.csv")

    console.print("[bold green]Pipeline completed successfully![/bold green]")

if __name__ == "__main__":
    test_sentence = "Breast cancer drugs targeting BRCA1"
    run_pipeline(test_sentence)
