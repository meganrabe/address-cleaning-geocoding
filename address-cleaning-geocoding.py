"""Clean address data before geocoding.

This script standardizes city names and removes common unit/building details
from street addresses.  It is intended as a starting point: review the output
and add rules that reflect the address conventions in your own data.

Required input files
--------------------
1. A CSV of address records with these columns:
   - ``city``: city supplied with the address
   - ``jurisdiction``: fallback jurisdiction that submitted the permits
   - ``zip9``: ZIP code or ZIP+4, if available
   - ``siteaddresspartial``: street address to clean
2. A CSV city-name crosswalk with these columns:
   - ``cm_name``: city name as it appears in the address records (ex: SLC)
   - ``update_name``: preferred standardized city name (ex: Salt Lake City)

Edit the three settings below before running the script. The output retains all
input columns and adds ``city_update``, ``zone``, ``addrstreet_preupdate``, and
``addrstreet_update``.
"""

from pathlib import Path
import re

import numpy as np
import pandas as pd


# -----------------------------------------------------------------------------
# Settings: replace these example paths with paths on your computer.
# -----------------------------------------------------------------------------
INPUT_FILE = Path("input/address_records.csv")
CITY_CROSSWALK_FILE = Path("input/city_name_crosswalk.csv")
OUTPUT_FILE = Path("output/addresses_cleaned.csv")

# ZIP codes in this list were not useful geocoding zones in the original data.
# Replace, expand, or remove this list based on your own data-quality review.
INVALID_ZONES = {
    "10930", "19028", "14000", "22425", "29909", "34900", "44020",
    "46113", "46120", "48121", "49331", "76244", "79762", "94032",
    "94098", "94656", "97133", "46113-8854", "46151-8914",
    "97055-6854", "55024",
}

REQUIRED_ADDRESS_COLUMNS = {"city", "jurisdiction", "zip9", "siteaddresspartial"}
REQUIRED_CROSSWALK_COLUMNS = {"cm_name", "update_name"}

STREET_SUFFIXES = (
    r"St|Street|Ave|Avenue|Blvd|Boulevard|Rd|Road|Ln|Lane|Dr|Drive|"
    r"Ct|Court|Cir|Circle|Pkwy|Parkway|Ter|Terrace|Way|Loop|Hwy|Highway|"
    r"Pl|Place|Trl|Trail|Run|Cv|Cove|Sq|Square|Path|Bnd|Bend|Pt|Point|"
    r"Pk|Park|Commons|Cmns|Plz|Plaza|North|South|East|West|N|S|E|W|Crt"
)
UNIT_KEYWORDS = (
    r"Bldg|Blgd|Bld|Building|Units?|Apt|Apartment|Suite|Ste|#|Lot|Trlr|"
    r"Sb|Sub|Shop|Rm|Room|Fl|Floor|Plat"
)
DIRECTIONALS = {"N", "S", "E", "W", "North", "South", "East", "West"}
DIR_PATTERN = r"[NSEW](?:orth|outh|ast|est)?"


def validate_columns(dataframe: pd.DataFrame, required: set[str], file_label: str) -> None:
    """Raise a clear error when an expected input column is absent."""
    missing = required - set(dataframe.columns)
    if missing:
        raise ValueError(f"{file_label} is missing required column(s): {', '.join(sorted(missing))}")


def clean_address_end(address: object) -> object:
    """Remove common trailing unit or building information from an address."""
    if pd.isna(address): # type: ignore
        return address

    address = str(address).strip()
    if not address:
        return address

    # Retain the street through its final recognized suffix/directional. For a
    # highway, retain the route number immediately following "Hwy" or "Highway".
    suffix_matches = list(re.finditer(rf"\b(?:{STREET_SUFFIXES})\b", address, re.IGNORECASE))
    if suffix_matches:
        last_suffix = suffix_matches[-1]
        street_end = last_suffix.end()
        if last_suffix.group(0).lower() in {"hwy", "highway"}:
            route_number = re.match(r"\s+\d+[A-Za-z]?", address[street_end:])
            if route_number:
                street_end += route_number.end()
        street_part = address[:street_end].strip()
    else:
        street_part = address

    # Remove an explicit unit/building phrase and anything after it.
    cleaned = re.sub(
        rf"\s+\b(?:{UNIT_KEYWORDS})\b.*$",
        "",
        street_part,
        flags=re.IGNORECASE,
    ).strip()

    # A # is not a word character, so it needs a separate pattern.
    cleaned = re.sub(r"\s*#\s*[A-Za-z0-9\-&,/ ]+$", "", cleaned).strip()
    cleaned = re.sub(r"\([^)]*[#A-Za-z0-9\-]+[^)]*\)", "", cleaned).strip()
    cleaned = re.sub(r"\bTh[-\s]?\d+[A-Za-z\- ]*$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"[ ,;/]+$", "", cleaned)
    return cleaned


def clean_address_front(address: object, debug: bool = False) -> object:
    """Resolve common multiple-address patterns at the start of an address.

    When several unit/street numbers refer to the same street, this function
    keeps the highest number. This mirrors the original workflow; change the
    selection rule if the lowest number or every number is more appropriate.
    """
    if pd.isna(address) or not isinstance(address, str): # type: ignore
        return address

    address = address.strip()
    if not address:
        return address

    def log(message: str) -> None:
        if debug:
            print(message)

    # Normalize truncated directionals that occur in some source systems.
    directional_fixes = {r"\bSou(?:th?)?\b": "S", r"\bNor(?:th?)?\b": "N",
                         r"\bEas(?:t)?\b": "E", r"\bWes(?:t)?\b": "W"}
    for pattern, replacement in directional_fixes.items():
        address = re.sub(pattern, replacement, address, flags=re.IGNORECASE)

    # Remove apartment/building details that appear after the street address.
    preserve_bldg = bool(re.search(r"[A-Z][a-z]+\s+Bldg\s+\d+", address, re.IGNORECASE))
    address = re.sub(r"\s+[\d-]+\s+Bldg\s+\d+", "", address, flags=re.IGNORECASE)
    if not preserve_bldg:
        address = re.sub(r"\s+Bldg\s+\d+\s*$", "", address, flags=re.IGNORECASE)
    address = re.sub(r"\s+Apt\s+.*$", "", address, flags=re.IGNORECASE)

    # "132 E 1500 N & 144 E 1500 N" becomes "144 E 1500 N".
    match = re.match(rf"^(\d+)\s+({DIR_PATTERN})\s+(.+?)\s*[&+]\s*(\d+)\s+\2\s+\3$", address, re.IGNORECASE)
    if match:
        address = f"{max(int(match.group(1)), int(match.group(4)))} {match.group(2)} {match.group(3)}"

    # "965 + 969 N 165 W" becomes "969 N 165 W".
    match = re.match(rf"^(\d+)\s*({DIR_PATTERN})?\s*[&+]\s*(\d+)\s+({DIR_PATTERN})\s+(.+)$", address, re.IGNORECASE)
    if match and (not match.group(2) or match.group(2).lower() == match.group(4).lower()):
        address = f"{max(int(match.group(1)), int(match.group(3)))} {match.group(4)} {match.group(5)}"

    # For semicolon-delimited alternatives, keep the final address-like entry.
    if ";" in address:
        parts = [part.strip() for part in address.split(";")]
        address_like = [part for part in parts if re.search(rf"\d+\s+{DIR_PATTERN}", part, re.IGNORECASE)]
        if address_like:
            address = address_like[-1]

    # For leading ranges such as "100-104 W Main St", retain the highest number.
    match = re.match(r"^([\d\s-]+?)\s+([A-Z])", address, re.IGNORECASE)
    if match and "-" in match.group(1):
        numbers = [int(number) for number in re.findall(r"\d+", match.group(1))]
        if len(numbers) >= 2:
            address = address.replace(match.group(0), f"{max(numbers)} {match.group(2)}", 1)

    # For a leading slash pair such as "100/104 W Main St", retain the higher number.
    match = re.match(r"^(\d+)/(\d+)\s+", address)
    if match:
        address = re.sub(r"^\d+/\d+\s+", f"{max(int(match.group(1)), int(match.group(2)))} ", address, count=1)

    # "159 W, 163 W, 167 W 900 N" becomes "167 W 900 N".
    match = re.match(rf"^((?:\d+\s+{DIR_PATTERN}\s*,\s*)+\d+\s+{DIR_PATTERN})\s+(.+)$", address, re.IGNORECASE)
    if match:
        pairs = re.findall(rf"(\d+)\s+({DIR_PATTERN})", match.group(1), re.IGNORECASE)
        if pairs:
            number, direction = pairs[-1]
            address = f"{number} {direction} {match.group(2)}"

    # Handle a leading comma/ampersand number list, without changing ordinals.
    match = re.match(r"^([\d,\s&]+?)([A-Z])", address, re.IGNORECASE)
    if match and not re.match(r"^(st|nd|rd|th)", address[match.end(1):], re.IGNORECASE):
        numbers = [int(number) for number in re.findall(r"\d+", match.group(1))]
        if len(numbers) > 1:
            address = address.replace(match.group(1), f"{max(numbers)} ", 1)

    # Remove trailing dash-based unit/range text (for example, "-1-4" or "-A-3").
    address = re.sub(r"\s*-\s*[A-Za-z]?\d+(?:-\d+)?\s*$", "", address)
    address = re.sub(r"\s+", " ", address).strip()
    log(f"Cleaned address: {address}")
    return address


def main() -> None:
    """Read input data, add geocoding fields, clean addresses, and write CSV."""