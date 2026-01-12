from __future__ import annotations

import json

from v011.api.app import app


def main() -> None:
    print(json.dumps(app.openapi(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
