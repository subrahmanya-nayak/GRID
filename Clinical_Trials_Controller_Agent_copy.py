# -*- coding: utf-8 -*-
import re
import json
import ast
import logging
from rich.console import Console
from langchain import PromptTemplate
from langchain_community.llms import Ollama
from langchain.chains import LLMChain

from query_parser.Clinical_Trials_Query_Parser_Agent import parse_query
from retriever.Clinical_Trials_Retriever_Agent import retrieve_trials
from rich.console import Console

console = Console()

def run_controller(user_query: str):
    console.rule("[bold green]Controller Agent[/bold green]")

    # Step 1: Parse the query
    parsed = parse_query(user_query)

    # Step 2: Retrieve trials based on parsed fields
    results = retrieve_trials(parsed, user_query)

    return results



