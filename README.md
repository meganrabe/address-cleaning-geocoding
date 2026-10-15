[README_address_cleaning.md](https://github.com/user-attachments/files/33512102/README_address_cleaning.md)

# Address Cleaning for Geocoding

`clean_addresses_for_geocoding.py` prepares address data for geocoding. It
standardizes city names, creates a geocoding zone, and cleans common unit,
building, and multiple-address patterns from a street-address field.

The script is intended as a transparent starting point rather than a universal
address parser. Review the output before using it in a production workflow and
adapt the rules to your source data and local addressing conventions.

## What the script does

For each record, the script:

1. Merges a city-name crosswalk with the address data.
2. Creates `city_update`, a standardized city or jurisdiction name.
3. Creates `zone`, using ZIP/ZIP+4 when available and the standardized city as
   a fallback. The zone is intended to help a geocoder distinguish places with
   similar street names.
4. Creates `addrstreet_preupdate` by removing common unit and building
   information at the end of `siteaddresspartial`.
5. Creates `addrstreet_update` by resolving selected multiple-number patterns
   at the beginning of an address.
6. Writes a new CSV that retains the original fields and adds the new fields.

## Requirements

- Python 3.9 or newer
- `pandas`
- `numpy`

Install the packages once from a terminal or Anaconda Prompt:

```bash
python -m pip install pandas numpy
```

## Files to prepare

Place the script and two input CSV files in a working folder. The default
folder structure in the script is:

```text
your-project/
├── clean_addresses_for_geocoding.py
├── input/
│   ├── address_records.csv
│   └── city_name_crosswalk.csv
└── output/
```

You can use a different structure; just update the three file settings near
the top of the script.

### 1. Address-record file

The address-record CSV must contain the following columns.

| Column | Purpose |
| --- | --- |
| `city` | City or jurisdiction supplied with the address. |
| `jurisdiction` | A fallback jurisdiction or city name if 'city' is missing. |
| `zip9` | ZIP code or ZIP+4, when available. |
| `siteaddresspartial` | Street address that will be cleaned. |

The file may contain additional columns. They will be retained in the output.

### 2. City-name crosswalk file

The crosswalk CSV must contain the following columns.

| Column | Purpose |
| --- | --- |
| `cm_name` | City name as it appears in the address-record file. |
| `update_name` | Preferred standardized city name. |

Example:

```csv
cm_name,update_name
Salt Lake,Salt Lake City
St George,St. George
```

If an address record does not match the crosswalk, the script uses
`jurisdiction` when available, then retains the original `city` value.

## Configure the script

Open `clean_addresses_for_geocoding.py` and update these settings:

```python
INPUT_FILE = Path("input/address_records.csv")
CITY_CROSSWALK_FILE = Path("input/city_name_crosswalk.csv")
OUTPUT_FILE = Path("output/addresses_cleaned.csv")
```

Use forward slashes in the paths even on Windows, or make them raw strings if
you prefer Windows backslashes. For example:

```python
INPUT_FILE = Path(r"C:\MyProject\input\address_records.csv")
```

### Review `INVALID_ZONES`

`INVALID_ZONES` contains ZIP codes or ZIP+4 values that were not reliable
geocoding zones in the original workflow. For records with these values, the
script uses `jurisdiction` as the zone instead.

This list is data-specific. Remove it if it is not needed, or replace it with
values identified in your own quality-control review.

## Run the script

From a terminal in the folder containing the script, run:

```bash
python clean_addresses_for_geocoding.py
```

When it finishes, the script reports the number of records written and saves
the cleaned file to `OUTPUT_FILE`.

## Address-cleaning rules

The script handles several common issues, including:

- trailing apartment, suite, room, lot, building, floor, and `#` unit details;
- trailing parenthetical unit information;
- shortened directionals such as `Sou`, `Nor`, `Eas`, and `Wes`;
- leading address ranges such as `100-104 W Main St`;
- leading slash-separated numbers such as `100/104 W Main St`;
- repeated address alternatives such as `132 E 1500 N & 144 E 1500 N`;
- repeated number-and-direction fragments such as
  `159 W, 163 W, 167 W 900 N`.

For a multiple-number pattern, the script generally keeps the highest street
number. That decision was appropriate for the original workflow but may not be
right for yours. Check a sample of the results and adjust the patterns or
selection rule as needed.

## Output fields

| Field | Description |
| --- | --- |
| `city_update` | Standardized city or jurisdiction used by the workflow. |
| `zone` | ZIP/ZIP+4 or fallback city/jurisdiction for geocoding. |
| `addrstreet_preupdate` | Address after trailing unit/building cleanup. |
| `addrstreet_update` | Final cleaned street address for geocoding. |

## Quality-control recommendations

Before geocoding an entire file, review a sample of records with the original
and cleaned address fields side by side. Pay particular attention to:

- apartment complexes, buildings, and lot numbers;
- highways and route numbers;
- addresses containing `&`, `+`, commas, semicolons, slashes, or ranges;
- local street names that include words also used as suffixes or directionals;
- missing ZIP codes and unmatched city names.

Keep the original source fields in the output. They make it much easier to
identify and refine rules when a cleaned address is not appropriate.

## Customizing the code

- Add or remove street suffixes in `STREET_SUFFIXES`.
- Add or remove unit/building terms in `UNIT_KEYWORDS`.
- Modify `INVALID_ZONES` for your data.
- Add a clearly commented regular-expression rule in `clean_address_end()` or
  `clean_address_front()` when you identify a recurring issue.

When adding a rule, test it with a few real examples before applying it to the
full dataset. A small test list near the function is a good way to document
why the rule exists and prevent it from being accidentally broken later.

## Troubleshooting

**`ValueError: ... is missing required column(s)`**  
Check the column spelling and capitalization in the relevant CSV, or revise
the corresponding required-column list in the script.

**`FileNotFoundError`**  
Confirm the three paths in the settings section point to the correct files and
folders.

**Unexpected cleaning results**  
Compare `siteaddresspartial`, `addrstreet_preupdate`, and `addrstreet_update`
for the affected record. Then adjust or add a narrowly targeted rule rather
than applying a broad replacement to every address.
