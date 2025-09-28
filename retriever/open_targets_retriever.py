import requests
import logging
import pandas as pd

BASE_URL = "https://api.platform.opentargets.org/api/v4/graphql"
cache = {}

def query_api(query, variables=None):
    key = f"{query}-{variables}"
    if key in cache:
        logging.info(f"Cache hit for query with variables: {variables}")
        return cache[key]

    try:
        response = requests.post(
            BASE_URL,
            json={"query": query, "variables": variables},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        data = response.json()

        if "errors" in data:
            logging.error(f"GraphQL errors: {data['errors']}")
            raise ValueError(f"GraphQL errors: {data['errors']}")

        cache[key] = data
        return data
    except Exception as e:
        logging.error(f"API query failed: {e}")
        raise

def query_disease_known_drugs(efo_id: str):
    query = """
    query ($efoId: String!) {
      disease(efoId: $efoId) {
        knownDrugs {
          rows {
            drug {
              name
              id
              maximumClinicalTrialPhase
            }
            phase
            label
            targetClass
          }
        }
      }
    }
    """
    variables = {"efoId": efo_id}
    data = query_api(query, variables)
    return data.get("data", {}).get("disease", {}).get("knownDrugs", {}).get("rows", [])

def query_drug_indications(chembl_id: str):
    query = """
    query ($chemblId: String!) {
      drug(chemblId: $chemblId) {
        indications {
          rows {
            disease {
              name
              id
            }
            maxPhaseForIndication
          }
        }
      }
    }
    """
    variables = {"chemblId": chembl_id}
    data = query_api(query, variables)
    return data.get("data", {}).get("drug", {}).get("indications", {}).get("rows", [])

def query_target_associated_diseases(efo_id: str):
    query = """
    query ($efoId: String!) {
      disease(efoId: $efoId) {
        associatedTargets {
          rows {
            target {
              id
              approvedSymbol
              approvedName
            }
            datasourceScores {
              id
              score
            }
          }
        }
      }
    }
    """
    variables = {"efoId": efo_id}
    data = query_api(query, variables)
    return data.get("data", {}).get("disease", {}).get("associatedTargets", {}).get("rows", [])

def merge_and_rank(disease_known_drugs_rows, drug_indications_rows, target_associated_diseases_rows):
    df_dkd = pd.json_normalize(disease_known_drugs_rows, sep='_') if disease_known_drugs_rows else pd.DataFrame()
    df_di = pd.json_normalize(drug_indications_rows, sep='_') if drug_indications_rows else pd.DataFrame()
    df_tad = pd.json_normalize(target_associated_diseases_rows, sep='_') if target_associated_diseases_rows else pd.DataFrame()

    if df_dkd.empty:
        df_dkd = pd.DataFrame(columns=['drug.name', 'drug.id', 'phase', 'label', 'targetClass'])
    if df_di.empty:
        df_di = pd.DataFrame(columns=['disease.name', 'disease.id', 'maxPhaseForIndication'])
    if df_tad.empty:
        df_tad = pd.DataFrame(columns=['target.id', 'target.approvedSymbol', 'score'])

    if 'drug.name' in df_dkd.columns and 'disease.name' in df_di.columns:
        merged_1 = pd.merge(
            df_dkd,
            df_di,
            left_on='drug.name',
            right_on='disease.name',
            how='outer',
            suffixes=('_known_drugs', '_drug_indications')
        )
    else:
        merged_1 = pd.concat([df_dkd, df_di], axis=0, ignore_index=True)

    for col in ['phase', 'maxPhaseForIndication']:
        if col not in merged_1.columns:
            merged_1[col] = 0

    merged_1['phase'] = pd.to_numeric(merged_1['phase'], errors='coerce').fillna(0)
    merged_1['maxPhaseForIndication'] = pd.to_numeric(merged_1['maxPhaseForIndication'], errors='coerce').fillna(0)

    merged_1['combined_score'] = merged_1[['phase', 'maxPhaseForIndication']].max(axis=1)
    merged_1 = merged_1.sort_values(by='combined_score', ascending=False)

    return merged_1, df_tad
