from pathlib import Path

import pandas as pd


def load_creator_data(file_path: str = "data/creators.csv") -> pd.DataFrame:
    """Load creator data from CSV file."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Creator data file not found: {file_path}")

    return pd.read_csv(path)
