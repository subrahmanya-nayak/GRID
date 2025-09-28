import os
import logging
import pandas as pd
from rich.console import Console

console = Console()

def save_results(rows, filename):
    df = pd.DataFrame(rows)
    os.makedirs("output", exist_ok=True)
    file_path = os.path.join("output", filename)
    df.to_csv(file_path, index=False)
    logging.info(f"Results saved to: {file_path}")
    console.print(f"[green]Results saved to: {file_path}[/green]")
