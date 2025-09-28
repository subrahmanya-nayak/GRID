import logging
from langchain import PromptTemplate
from langchain.chains import LLMChain
from langchain_community.llms import Ollama

# Initialize LLM
llm = Ollama(model="gemma2:latest")

class QueryParser:
    def __init__(self):
        self.chain = LLMChain(
            llm=llm,
            prompt=PromptTemplate(
                input_variables=["sentence"],
                template="""
Extract all drug names, disease names, and target names mentioned in the following sentence.
If none are mentioned, use an empty list for that field.

Sentence: "{sentence}"

Output the result in JSON format with keys: "drug", "disease", and "target". Each key should map to a list of strings.
"""
            )
        )

    def extract_entities(self, sentence: str) -> str:
        try:
            result = self.chain.run(sentence).strip()
            logging.info(f"Extracted entities JSON: {result}")
            return result
        except Exception as e:
            logging.error(f"Failed to extract entities: {e}")
            raise
