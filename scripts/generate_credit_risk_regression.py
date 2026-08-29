from pathlib import Path

from lacopilot.config import get_settings
from lacopilot.regression_fixture import write_credit_risk_regression_fixture


def main() -> None:
    paths = write_credit_risk_regression_fixture(get_settings().incoming_dir)
    for kind, path in paths.items():
        print(f"{kind.upper()}: {Path(path).resolve()}")


if __name__ == "__main__":
    main()
