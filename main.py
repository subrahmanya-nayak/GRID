# query_router.py

from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
from langchain.chains import LLMChain

from open_targets_copy import run_pipeline as run_open_targets
from Clinical_Trials_Controller_Agent_copy import run_controller as run_clinical_trials

from rich.console import Console

console = Console()

# === Initialize LLM ===
llm = Ollama(model="gemma2:latest")

# === Router Prompt ===
router_template = """
You are an assistant that decides whether a biomedical query is about:

- clinical trials
- drug/target data
- both
- none

Respond ONLY with one of these exact options:
- clinical_trials
- open_targets
- both
- none

Do NOT explain. Just return one of the options exactly as listed.

Query: {query}
Answer:
"""

router_prompt = PromptTemplate(
    input_variables=["query"],
    template=router_template,
)

router_chain = LLMChain(
    llm=llm,
    prompt=router_prompt
)


class DBFinder:
    def __init__(self):
        self.llm_router = router_chain

    def classify_query(self, query: str) -> str:
        try:
            response = self.llm_router.run(query).strip().lower()
            if response in {"clinical_trials", "open_targets", "both", "none"}:
                return response
            return "unknown"
        except Exception as e:
            console.print(f"[red]Error during query classification: {e}[/red]")
            return "unknown"

    def route_and_query(self, query: str):
        classification = self.classify_query(query)
        console.print(f"[bold blue]Query classified as:[/bold blue] {classification}")

        results = []

        if classification == "clinical_trials":
            console.print("[yellow]Fetching from Clinical Trials...[/yellow]")
            results.append(run_clinical_trials(query))

        elif classification == "open_targets":
            console.print("[yellow]Fetching from Open Targets...[/yellow]")
            results.append(run_open_targets(query))

        elif classification == "both":
            console.print("[yellow]Fetching from both sources...[/yellow]")
            results.append(run_clinical_trials(query))
            results.append(run_open_targets(query))

        elif classification == "none":
            console.print("[red]Query does not match any known biomedical data source.[/red]")
            return None

        else:
            console.print("[red]Could not determine an appropriate data source.[/red]")
            return None

        return results


if __name__ == "__main__":
    finder = DBFinder()
    while True:
        user_input = input("Enter query (or type 'exit'): ").strip()
        if user_input.lower() == "exit":
            break

        output = finder.route_and_query(user_input)
        if output:
            console.print("[green]Query Results:[/green]")
            for result in output:
                if hasattr(result, 'to_string'):
                    print(result.to_string())
                else:
                    print(result)
