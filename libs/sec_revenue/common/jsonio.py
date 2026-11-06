"""JSON 讀寫：排序鍵、縮排兩格、保留非 ASCII 字元；寫入以暫存檔原子替換，`.gz` 自動解壓。"""

from __future__ import annotations

import gzip
import json
import os
from pathlib import Path
import tempfile


class JsonCodec:
    @staticmethod
    def encode(value: object) -> bytes:
        return (
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, default=str)
            + "\n"
        ).encode()

    @classmethod
    def write(cls, path: Path, value: object) -> None:
        cls.write_bytes(path, cls.encode(value))

    @staticmethod
    def write_bytes(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=path.name + ".", delete=False
        ) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            except BaseException:
                temporary.unlink(missing_ok=True)
                raise
        temporary.replace(path)

    @staticmethod
    def read(path: Path) -> dict:
        return json.loads(
            gzip.decompress(path.read_bytes())
            if path.suffix == ".gz"
            else path.read_bytes()
        )
