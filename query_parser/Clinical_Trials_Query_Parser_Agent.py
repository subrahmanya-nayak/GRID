# -*- coding: utf-8 -*-
import re
import json
import ast
import logging
from rich.console import Console
from langchain import PromptTemplate
from langchain_community.llms import Ollama
from langchain.chains import LLMChain

# === Setup ===
console = Console()

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# === Initialize LLM ===
llm = Ollama(model="gemma2:latest")

# === Prompt ===
keyword_prompt = PromptTemplate(
    input_variables=["sentence"],
    template="""
Extract the following information from the user query. 
If not present, return null for that field. 
Output JSON ONLY, no commentary.

Fields:
- Condition/Disease
- Intervention/Treatment/Drug
- Location
- Status
- Phase
- Outcome/Results/Conclusion
- Study IDs/NCT IDs
- Facility Name
- Date Range

Sentence: "{sentence}"
JSON:
"""
)

keyword_chain = LLMChain(llm=llm, prompt=keyword_prompt)

# === Utility: JSON Parser ===
def parse_json_flex(text):
    if not text or not isinstance(text, str):
        return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if m:
        candidate = m.group(0)
        try:
            return json.loads(candidate)
        except Exception:
            try:
                return ast.literal_eval(candidate)
            except Exception:
                pass
    return None

# === Fallback ===
def fallback_extract(sentence):
    return {
        "Condition/Disease": None,
        "Intervention/Treatment/Drug": None,
        "Location": None,
        "Status": None,
        "Phase": None,
        "Outcome/Results/Conclusion": None,
        "Study IDs/NCT IDs": None,
        "Facility Name": None,
        "Date Range": None
    }

# === Main Parser ===
def parse_query(user_input: str) -> dict:
    console.rule(f"[bold cyan]Query Parser Agent[/bold cyan] {user_input}")

    # ?? Always initialize
    extracted = None  

    try:
        llm_output = keyword_chain.run(user_input)
        console.log(f"[blue]LLM raw output:[/blue] {llm_output}")
        parsed = parse_json_flex(llm_output)
        if parsed and isinstance(parsed, dict):
            extracted = parsed
        else:
            console.log("[yellow]LLM output not valid JSON; falling back.[/yellow]")
    except Exception as e:
        console.log(f"[red]Parser LLM failed: {e}. Using fallback.[/red]")

    # ?? Ensure fallback is used if nothing extracted
    if not extracted:
        extracted = fallback_extract(user_input)

    console.log(f"[green]Extracted fields:[/green] {extracted}")
    return extracted





