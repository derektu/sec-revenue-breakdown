"""讀取 repo 根目錄的 `.env`，把設定放進環境變數。

格式為一行一個 `KEY=VALUE`；`#` 開頭的行與空白行略過，值前後的單引號或雙引號會去掉。
已存在的環境變數優先，不被 `.env` 覆蓋，所以命令列臨時指定的值永遠有效。
"""

import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not key:
            raise ValueError(f"{path}:{number} 格式應為 KEY=VALUE")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1]
        os.environ.setdefault(key, value)
