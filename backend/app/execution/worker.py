import json
import sys

import pandas as pd

from app.analysis.engine import analyze


def main():
    with open(sys.argv[1], encoding="utf-8") as handle:
        request = json.load(handle)
    frame = pd.DataFrame.from_records(request["rows"], columns=request["columns"])
    print(
        json.dumps(
            analyze(frame, request["question"], request.get("previous")),
            allow_nan=False,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
