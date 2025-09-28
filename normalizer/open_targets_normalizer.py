import requests
import logging
from chembl_webresource_client.new_client import new_client
import mygene


class Normalizer:
    @staticmethod
    def get_efo_id_from_zooma(term: str) -> str:
        url = f"https://www.ebi.ac.uk/spot/zooma/v2/api/services/annotate?propertyValue={term}"
        headers = {"Accept": "application/json"}

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            raise Exception(f"ZOOMA request failed: {response.status_code}")

        for item in response.json():
            for mapping in item.get("semanticTags", []):
                if "EFO" in mapping:
                    efo_id = mapping.split("/")[-1]
                    logging.info(f"Found EFO ID for '{term}': {efo_id}")
                    return efo_id

        raise ValueError(f"No EFO ID found for: {term}")

    @staticmethod
    def get_chembl_id(term: str) -> str:
        molecule = new_client.molecule
        results = molecule.search(term)
        results_list = list(results)
        if results_list:
            chembl_id = results_list[0].get('molecule_chembl_id')
            logging.info(f"Found ChEMBL ID for '{term}': {chembl_id}")
            return chembl_id
        else:
            logging.warning(f"No ChEMBL ID found for '{term}'")
            return None

    @staticmethod
    def get_ensembl_id(term: str, species: str = "human") -> str:
        mg = mygene.MyGeneInfo()
        try:
            result = mg.query(term, species=species, fields="ensembl.gene")
            hits = result.get('hits', [])
            if not hits:
                logging.warning(f"No Ensembl ID found for '{term}'")
                return None

            for hit in hits:
                ensembl_data = hit.get('ensembl')
                if isinstance(ensembl_data, dict):
                    ensembl_id = ensembl_data.get('gene')
                    if ensembl_id:
                        logging.info(f"Found Ensembl ID for '{term}': {ensembl_id}")
                        return ensembl_id
                elif isinstance(ensembl_data, list):
                    for item in ensembl_data:
                        if 'gene' in item:
                            ensembl_id = item['gene']
                            logging.info(f"Found Ensembl ID for '{term}': {ensembl_id}")
                            return ensembl_id

        except Exception as e:
            logging.error(f"Failed to get Ensembl ID for '{term}': {str(e)}")
            return None
