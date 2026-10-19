import pandas as pd


def prepare(input_path, prepared_path):
    """Read the raw dataset, materialize a prepared (intermediate) copy, and
    return its path. Splitting the loading into a local module lets the version
    model illustrate (i) a local module as definition provenance and (ii) an
    intermediate file object written and then read within the same trial."""
    df = pd.read_csv(input_path, encoding='utf-8')
    df.to_csv(prepared_path, index=False)
    return prepared_path
