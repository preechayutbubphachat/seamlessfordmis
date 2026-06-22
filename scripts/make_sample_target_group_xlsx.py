import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    source = Path("seed/sample_target_group.csv")
    target = Path("data/samples/sample_target_group.xlsx")
    frame = pd.read_csv(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    frame.to_excel(target, index=False)
    print("created sample_target_group.xlsx")


if __name__ == "__main__":
    main()
