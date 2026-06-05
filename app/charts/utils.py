from __future__ import annotations

import math
from collections.abc import Iterable

import pandas as pd


ISO2_TO_ISO3 = {
    "AD": "AND",
    "AE": "ARE",
    "AR": "ARG",
    "AT": "AUT",
    "AU": "AUS",
    "BE": "BEL",
    "BG": "BGR",
    "BR": "BRA",
    "CA": "CAN",
    "CH": "CHE",
    "CL": "CHL",
    "CN": "CHN",
    "CO": "COL",
    "CZ": "CZE",
    "DE": "DEU",
    "DK": "DNK",
    "EE": "EST",
    "ES": "ESP",
    "FI": "FIN",
    "FR": "FRA",
    "GB": "GBR",
    "GR": "GRC",
    "HK": "HKG",
    "HU": "HUN",
    "IE": "IRL",
    "IL": "ISR",
    "IN": "IND",
    "IR": "IRN",
    "IS": "ISL",
    "IT": "ITA",
    "JP": "JPN",
    "KR": "KOR",
    "LU": "LUX",
    "MX": "MEX",
    "MY": "MYS",
    "NL": "NLD",
    "NO": "NOR",
    "NZ": "NZL",
    "PL": "POL",
    "PT": "PRT",
    "RO": "ROU",
    "RU": "RUS",
    "SA": "SAU",
    "SE": "SWE",
    "SG": "SGP",
    "SI": "SVN",
    "TH": "THA",
    "TR": "TUR",
    "TW": "TWN",
    "UA": "UKR",
    "US": "USA",
    "ZA": "ZAF",
}

COUNTRY_NAMES = {
    "ARE": "United Arab Emirates",
    "ARG": "Argentina",
    "AUS": "Australia",
    "AUT": "Austria",
    "BEL": "Belgium",
    "BGR": "Bulgaria",
    "BRA": "Brazil",
    "CAN": "Canada",
    "CHE": "Switzerland",
    "CHL": "Chile",
    "CHN": "China",
    "COL": "Colombia",
    "CZE": "Czechia",
    "DEU": "Germany",
    "DNK": "Denmark",
    "ESP": "Spain",
    "EST": "Estonia",
    "FIN": "Finland",
    "FRA": "France",
    "GBR": "United Kingdom",
    "GRC": "Greece",
    "HKG": "Hong Kong",
    "HUN": "Hungary",
    "IND": "India",
    "IRL": "Ireland",
    "IRN": "Iran",
    "ISL": "Iceland",
    "ISR": "Israel",
    "ITA": "Italy",
    "JPN": "Japan",
    "KOR": "South Korea",
    "LUX": "Luxembourg",
    "MEX": "Mexico",
    "MYS": "Malaysia",
    "NLD": "Netherlands",
    "NOR": "Norway",
    "NZL": "New Zealand",
    "POL": "Poland",
    "PRT": "Portugal",
    "ROU": "Romania",
    "RUS": "Russia",
    "SAU": "Saudi Arabia",
    "SGP": "Singapore",
    "SVN": "Slovenia",
    "SWE": "Sweden",
    "THA": "Thailand",
    "TUR": "Turkey",
    "TWN": "Taiwan",
    "UKR": "Ukraine",
    "USA": "United States",
    "ZAF": "South Africa",
}
COUNTRY_NAME_TO_ISO3 = {name.upper(): iso3 for iso3, name in COUNTRY_NAMES.items()}
COUNTRY_NAME_TO_ISO3.update(
    {
        "UNITED STATES OF AMERICA": "USA",
        "UNITED KINGDOM": "GBR",
        "SOUTH KOREA": "KOR",
        "CZECH REPUBLIC": "CZE",
    }
)


def split_tokens(value: object, sep: str = ",") -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    tokens = [part.strip() for part in str(value).split(sep)]
    return [token for token in tokens if token and token != "Unknown"]


def explode_tokens(papers: pd.DataFrame, source_column: str, output_column: str) -> pd.DataFrame:
    """Explode a delimited text column into one row per token.

    Uses '|' as separator for institutions_text (to handle institution names
    that contain commas), and ',' for all other columns.
    """
    if papers.empty or source_column not in papers.columns:
        return pd.DataFrame(columns=list(papers.columns) + [output_column])
    sep = " | " if source_column == "institutions_text" else ","
    data = papers.copy()
    data[output_column] = data[source_column].apply(lambda v: split_tokens(v, sep))
    data = data.explode(output_column)
    data[output_column] = data[output_column].fillna("")
    return data[data[output_column].ne("")].copy()


def country_iso3(value: object) -> str | None:
    text = str(value).strip().upper()
    if not text or text == "UNKNOWN":
        return None
    if len(text) == 3:
        return text
    return ISO2_TO_ISO3.get(text) or COUNTRY_NAME_TO_ISO3.get(text)


def country_display(value: object) -> str:
    iso3 = country_iso3(value)
    return COUNTRY_NAMES.get(iso3 or "", str(value).strip())


def format_delta(value: float) -> str:
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}"


def first_known(values: Iterable[str]) -> str:
    for value in values:
        if value and value != "Unknown":
            return value
    return "None"
