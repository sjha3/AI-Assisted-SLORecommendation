import argparse
import json
import logging
import re
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
TARGET_DIR = (BASE_DIR / ".." / "DB" / "Config" / "Service").resolve()
TARGET_DIR.mkdir(parents=True, exist_ok=True)

_VALID_FILE_PATTERN = re.compile(r"^[A-Za-z0-9._-]+\.json$")
logger = logging.getLogger(__name__)


def _file_path(file_name: str) -> Path:
    if not _VALID_FILE_PATTERN.fullmatch(file_name):
        raise ValueError("file_name must be a safe json filename like '<id>.json'")
    return TARGET_DIR / file_name


def write_json_file(file_name: str, data: Any, overwrite: bool = False) -> Path:
    logger.info("Writing json file '%s' (overwrite=%s)", file_name, overwrite)
    file_path = _file_path(file_name)
    if file_path.exists() and not overwrite:
        logger.warning("Write blocked: file already exists '%s'", file_name)
        raise FileExistsError(f"File '{file_name}' already exists")

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Json file written: %s", file_path)
    return file_path


def update_json_file(file_name: str, data: Any) -> Path:
    logger.info("Updating json file '%s'", file_name)
    file_path = _file_path(file_name)
    if not file_path.exists():
        logger.warning("Update failed: file not found '%s'", file_name)
        raise FileNotFoundError(f"File '{file_name}' does not exist")

    with file_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Json file updated: %s", file_path)
    return file_path


def read_json_file(file_name: str) -> Any:
    logger.info("Reading json file '%s'", file_name)
    file_path = _file_path(file_name)
    if not file_path.exists():
        logger.warning("Read failed: file not found '%s'", file_name)
        raise FileNotFoundError(f"File '{file_name}' does not exist")

    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    logger.info("Json file read: %s", file_path)
    return data


def delete_json_file(file_name: str) -> Path:
    logger.info("Deleting json file '%s'", file_name)
    file_path = _file_path(file_name)
    if not file_path.exists():
        logger.warning("Delete failed: file not found '%s'", file_name)
        raise FileNotFoundError(f"File '{file_name}' does not exist")

    file_path.unlink()
    logger.info("Json file deleted: %s", file_path)
    return file_path





