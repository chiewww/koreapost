
#!/usr/bin/env python3
"""
Korea Post International Letter Post Monitor
=============================================

Repository: koreapost
Output:     output_korea.txt

Monitors the Korea Post International Letter Post destination dropdown.
Compares it with the 248-entry Postcrossing master list, extracts urgent
notices, translates Korean text to English, and identifies suspensions.

No Playwright or browser automation is used.

IMPORTANT:
The Korea Post form can change. The script validates extraction results
and raises an error if it cannot reliably discover the destination dropdown.
Review the first GitHub Actions run before relying on the report.
"""

from __future__ import annotations

import difflib
import html
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import pycountry


# ============================================================
# 1. Configuration
# ============================================================

SOURCE_URL = (
    "https://ems.epost.go.kr/"
    "front.EmsNormalAirShipSendCondition.postal"
    "?frnMailDivcdTab=1&frnTranspPartyDivcd=2"
)

OUTPUT_FILE = Path("output_korea.txt")

REQUEST_TIMEOUT = 30
REQUEST_DELAY_SECONDS = 0.4
TRANSLATION_DELAY_SECONDS = 0.15

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; KoreaPostMonitor/1.0; "
        "+https://github.com/)"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# The monitor must not mistake a failed request for a suspension.
STRICT_MODE = True


# ============================================================
# 2. Postcrossing master list: all 248 destinations
#    Each line is the assigned number followed by its name.
# ============================================================

MASTER_LIST_TEXT = """
1|Afghanistan
2|Åland Islands
3|Albania
4|Algeria
5|American Samoa
6|Andorra
7|Angola
8|Anguilla
9|Antarctica
10|Antigua & Barbuda
11|Argentina
12|Armenia
13|Aruba
14|Australia
15|Austria
16|Azerbaijan
17|Bahamas
18|Bahrain
19|Bangladesh
20|Barbados
21|Belarus
22|Belgium
23|Belize
24|Benin
25|Bermuda
26|Bhutan
27|Bolivia
28|Bonaire, Sint Eustatius and Saba
29|Bosnia-Herzegovina
30|Botswana
31|Brazil
32|British Indian Ocean Territory
33|Brunei
34|Bulgaria
35|Burkina Faso
36|Burundi
37|Cabo Verde
38|Cambodia
39|Cameroon
40|Canada
41|Cayman Islands
42|Central African Republic
43|Chad
44|Chile
45|China
46|Christmas Island
47|Cocos Islands
48|Colombia
49|Comoros
50|Congo
51|Dem. Rep. Of Congo
52|Cook Islands
53|Costa Rica
54|Côte d'Ivoire
55|Croatia
56|Cuba
57|Curaçao
58|Cyprus
59|Czechia
60|Denmark
61|Djibouti
62|Dominica
63|Dominican Republic
64|Ecuador
65|Egypt
66|El Salvador
67|Equatorial Guinea
68|Eritrea
69|Estonia
70|Eswatini /Swaziland
71|Ethiopia
72|Falkland Islands /Malvinas
73|Faroe Islands
74|Fiji
75|Finland
76|France
77|French Guiana
78|French Polynesia
79|French Southern Territories
80|Gabon
81|Gambia
82|Georgia
83|Germany
84|Ghana
85|Gibraltar
86|Greece
87|Greenland
88|Grenada
89|Guadeloupe
90|Guam
91|Guatemala
92|Guernsey
93|Guinea
94|Guinea-Bissau
95|Guyana
96|Haiti
97|Honduras
98|Hong Kong
99|Hungary
100|Iceland
101|India
102|Indonesia
103|Iran
104|Iraq
105|Ireland
106|Isle of Man
107|Israel
108|Italy
109|Jamaica
110|Japan
111|Jersey
112|Jordan
113|Kazakhstan
114|Kenya
115|Kiribati
116|Korea(North)
117|Korea(South)
118|Kosovo
119|Kuwait
120|Kyrgyzstan
121|Laos
122|Latvia
123|Lebanon
124|Lesotho
125|Liberia
126|Libya
127|Liechtenstein
128|Lithuania
129|Luxembourg
130|Macao
131|Madagascar
132|Malawi
133|Malaysia
134|Maldives
135|Mali
136|Malta
137|Marshall Islands
138|Martinique
139|Mauritania
140|Mauritius
141|Mayotte
142|Mexico
143|Micronesia
144|Moldova
145|Monaco
146|Mongolia
147|Montenegro
148|Montserrat
149|Morocco
150|Mozambique
151|Myanmar
152|Namibia
153|Nauru / Naoero
154|Nepal
155|Netherlands
156|New Caledonia
157|New Zealand
158|Nicaragua
159|Niger
160|Nigeria
161|Niue
162|Norfolk Island
163|Northern Mariana Islands
164|North Macedonia
165|Norway
166|Oman
167|Pakistan
168|Palau
169|Palestine
170|Panama
171|Papua New Guinea
172|Paraguay
173|Peru
174|Philippines
175|Pitcairn
176|Poland
177|Portugal
178|Puerto Rico
179|Qatar
180|Réunion
181|Romania
182|Russia
183|Rwanda
184|Saint Barthélemy
185|Saint Helena, Ascension and Tristan da Cunha
186|Saint Kitts and Nevis
187|Saint Lucia
188|Saint Martin
189|Saint Pierre & Miquelon
190|Saint Vincent and the Grenadines
191|Samoa
192|San Marino
193|Sao Tome and Principe
194|Saudi Arabia
195|Senegal
196|Serbia
197|Seychelles
198|Sierra Leone
199|Singapore
200|Sint Maarten
201|Slovakia
202|Slovenia
203|Solomon Islands
204|Somalia
205|South Africa
206|South Georgia and S. Sandwich Islands
207|South Sudan
208|Spain
209|Sri Lanka
210|Sudan
211|Suriname
212|Svalbard and Jan Mayen
213|Sweden
214|Switzerland
215|Syria
216|Taiwan
217|Tajikistan
218|Tanzania
219|Thailand
220|Timor-Leste
221|Togo
222|Tokelau
223|Tonga
224|Trinidad and Tobago
225|Tunisia
226|Turkey
227|Turkmenistan
228|Turks and Caicos Islands
229|Tuvalu
230|Uganda
231|Ukraine
232|United Arab Emirates
233|United Kingdom
234|Uruguay
235|U.S.A.
236|U.S. Minor Outlying Islands
237|Uzbekistan
238|Vanuatu
239|Vatican
240|Venezuela
241|Vietnam
242|Virgin Islands (UK)
243|Virgin Islands of the USA
244|Wallis & Futuna
245|Western Sahara
246|Yemen
247|Zambia
248|Zimbabwe
""".strip()


def parse_master_list():
    """Return a list of master-list records in assigned-number order."""
    records = []
    for line in MASTER_LIST_TEXT.splitlines():
        number, name = line.split("|", 1)
        records.append({
            "number": int(number),
            "name": name.strip(),
        })

    if len(records) != 248:
        raise RuntimeError(
            f"Master-list integrity check failed: "
            f"expected 248 entries, found {len(records)}."
        )

    if len({item["number"] for item in records}) != 248:
        raise RuntimeError("Duplicate number in master list.")

    return records


MASTER = parse_master_list()


# ============================================================
# 3. Name normalization and matching
# ============================================================

ALIASES = {
    "usa": "U.S.A.",
    "united states": "U.S.A.",
    "united states of america": "U.S.A.",
    "korea": "Korea(South)",
    "south korea": "Korea(South)",
    "republic of korea": "Korea(South)",
    "north korea": "Korea(North)",
    "democratic people's republic of korea": "Korea(North)",
    "hong kong china": "Hong Kong",
    "macao china": "Macao",
    "macau": "Macao",
    "czech republic": "Czechia",
    "turkiye": "Turkey",
    "türkiye": "Turkey",
    "eswatini": "Eswatini /Swaziland",
    "swaziland": "Eswatini /Swaziland",
    "cape verde": "Cabo Verde",
    "ivory coast": "Côte d'Ivoire",
    "cote d ivoire": "Côte d'Ivoire",
    "democratic republic of the congo": "Dem. Rep. Of Congo",
    "dr congo": "Dem. Rep. Of Congo",
    "congo kinshasa": "Dem. Rep. Of Congo",
    "republic of the congo": "Congo",
    "congo brazzaville": "Congo",
    "east timor": "Timor-Leste",
    "lao people's democratic republic": "Laos",
    "lao people's dem rep": "Laos",
    "russian federation": "Russia",
    "reunion": "Réunion",
    "faeroe islands": "Faroe Islands",
    "cocos keeling islands": "Cocos Islands",
    "cocos islands": "Cocos Islands",
    "christmas island australia": "Christmas Island",
    "brunei darussalam": "Brunei",
    "north macedonia": "North Macedonia",
    "palestinian territories": "Palestine",
    "state of palestine": "Palestine",
    "vatican city": "Vatican",
    "holy see": "Vatican",
    "virgin islands british": "Virgin Islands (UK)",
    "british virgin islands": "Virgin Islands (UK)",
    "virgin islands us": "Virgin Islands of the USA",
    "us virgin islands": "Virgin Islands of the USA",
    "american virgin islands": "Virgin Islands of the USA",
    "saint pierre and miquelon": "Saint Pierre & Miquelon",
    "saint kitts nevis": "Saint Kitts and Nevis",
    "saint vincent grenadines": "Saint Vincent and the Grenadines",
    "sao tome principe": "Sao Tome and Principe",
    "åland islands": "Åland Islands",
}


def normalize(value: str) -> str:
    """Normalize punctuation, accents, and spacing for matching."""
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(
        char for char in value if not unicodedata.combining(char)
    )
    value = value.lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


MASTER_BY_NORMALIZED = {
    normalize(record["name"]): record for record in MASTER
}


def master_match(name: str, country_code: str = ""):
    """
    Match a Korean Post dropdown item to the master list.

    Prefer ISO alpha-2 country codes where possible, then explicit aliases,
    then exact normalized English-name matching, then conservative fuzzy
    matching. Uncertain matches are left unmatched rather than guessed.
    """
    code = (country_code or "").strip().upper()

    # ISO alpha-2 country codes are useful, but not all destinations
    # (territories and special regions) have a usable pycountry entry.
    if re.fullmatch(r"[A-Z]{2}", code):
        country = pycountry.countries.get(alpha_2=code)
        if country:
            english = getattr(country, "common_name", country.name)
            normalized_english = normalize(english)
            if normalized_english in MASTER_BY_NORMALIZED:
                return MASTER_BY_NORMALIZED[normalized_english]

            alias_key = normalize(english)
            alias_target = ALIASES.get(alias_key)
            if alias_target:
                return MASTER_BY_NORMALIZED.get(normalize(alias_target))

    key = normalize(name)
    target = ALIASES.get(key)
    if target:
        return MASTER_BY_NORMALIZED.get(normalize(target))

    if key in MASTER_BY_NORMALIZED:
        return MASTER_BY_NORMALIZED[key]

    # Try aliases in both directions and a cautious similarity threshold.
    candidates = difflib.get_close_matches(
        key, list(MASTER_BY_NORMALIZED), n=1, cutoff=0.91
    )
    if candidates:
        return MASTER_BY_NORMALIZED[candidates[0]]

    return None


# ============================================================
# 4. HTTP and translation helpers
# ============================================================

session = requests.Session()
session.headers.update(HEADERS)


def fetch(url: str, **kwargs) -> requests.Response:
    """Fetch a page and raise an error for unsuccessful HTTP responses."""
    response = session.get(
        url,
        timeout=REQUEST_TIMEOUT,
        **kwargs,
    )
    response.raise_for_status()
    return response


def translate_to_english(text: str) -> str:
    """
    Translate Korean text to English using Google's public translation
    endpoint. If translation fails, preserve the original text and mark
    it as untranslated rather than inventing an English translation.
    """
    text = (text or "").strip()
    if not text:
        return ""

    # Avoid wasting requests on text that appears to be English already.
    if not re.search(r"[가-힣]", text):
        return text

    endpoint = "https://translate.googleapis.com/translate_a/single"
    try:
        response = session.get(
            endpoint,
            params={
                "client": "gtx",
                "sl": "ko",
                "tl": "en",
                "dt": "t",
                "q": text,
            },
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
        translated = "".join(
            segment[0]
            for segment in payload[0]
            if segment and segment[0]
        ).strip()

        time.sleep(TRANSLATION_DELAY_SECONDS)
        return translated or f"[Translation unavailable] {text}"

    except (requests.RequestException, ValueError, TypeError, IndexError):
        return f"[Translation unavailable] {text}"


# ============================================================
# 5. Discover the destination dropdown
# ============================================================

def is_destination_select(select) -> bool:
    """Identify the select associated with 도착국 (destination country)."""
    context = " ".join([
        select.get("name", ""),
        select.get("id", ""),
        select.get("aria-label", ""),
        select.find_previous("label").get_text(" ", strip=True)
        if select.find_previous("label")
        else "",
        select.parent.get_text(" ", strip=True)
        if select.parent
        else "",
    ])
    return "도착국" in context or "destination" in context.lower()


def discover_form_and_options(soup: BeautifulSoup):
    """Find the destination select and its parent HTML form."""
    selects = soup.find_all("select")
    candidates = [select for select in selects if is_destination_select(select)]

    if not candidates:
        # Some pages do not associate the visible label with the select.
        # Look for a likely country selector by its name or ID.
        candidates = [
            select for select in selects
            if any(
                token in (
                    select.get("name", "") + " " + select.get("id", "")
                ).lower()
                for token in ("nation", "country", "dest", "arrive")
            )
        ]

    if not candidates:
        raise RuntimeError(
            "Could not identify the 도착국 dropdown. "
            "The site HTML may have changed; inspect the live page form."
        )

    select = candidates[0]
    form = select.find_parent("form")

    options = []
    for option in select.find_all("option"):
        value = (option.get("value") or "").strip()
        label = option.get_text(" ", strip=True)

        # Ignore empty placeholders such as [Select].
        if not value or not label or label.lower() in {
            "select", "[select]", "선택", "선택하세요"
        }:
            continue

        options.append({
            "value": value,
            "korean": label,
        })

    if not options:
        raise RuntimeError(
            "The destination select was found, but it contains no options."
        )

    return form, select, options


# ============================================================
# 6. Submit the country selection and extract the urgent notice
# ============================================================

def extract_urgent_notice(soup: BeautifulSoup) -> str:
    """
    Extract the urgent-notice textarea when present.

    If the expected textarea is missing, inspect the page text near
    긴급공지 as a fallback. A missing notice is not automatically
    interpreted as a service suspension.
    """
    textarea = soup.find("textarea", attrs={"name": "textarea"})
    if textarea:
        return textarea.get_text("\n", strip=True)

    headings = soup.find_all(
        string=re.compile(r"긴급공지")
    )
    for heading in headings:
        parent = heading.parent
        if not parent:
            continue
        container = parent.parent or parent
        text = container.get_text("\n", strip=True)
        text = text.replace("긴급공지", "", 1).strip()
        if text:
            return text

    return ""


def build_form_payload(form, select, selected_value: str) -> dict:
    """
    Construct a form payload from the live page, preserving hidden fields.
    """
    payload = {}

    if form:
        for field in form.find_all(["input", "textarea"]):
            name = field.get("name")
            if not name:
                continue

            field_type = (field.get("type") or "").lower()
            if field_type in {"submit", "button", "image", "reset", "file"}:
                continue
            if field_type in {"checkbox", "radio"} and not field.has_attr(
                "checked"
            ):
                continue

            payload[name] = field.get("value", "")

        for other_select in form.find_all("select"):
            name = other_select.get("name")
            if not name:
                continue

            chosen = (
                selected_value
                if other_select is select
                else next(
                    (
                        option.get("value", "")
                        for option in other_select.find_all("option")
                        if option.has_attr("selected")
                    ),
                    "",
                )
            )
            if chosen:
                payload[name] = chosen

    # Ensure the target country is included even if the form has unusual
    # markup or the select was not associated with a form.
    select_name = select.get("name")
    if select_name:
        payload[select_name] = selected_value

    return payload


def query_destination(form, select, option) -> BeautifulSoup:
    """
    Submit the selected country through the form discovered in the page.

    If the website uses JavaScript-only submission, this method may need
    to be adjusted after reviewing the first workflow log.
    """
    if not form:
        raise RuntimeError(
            "The destination dropdown is not inside an HTML form. "
            "The site's JavaScript submission behavior needs inspection."
        )

    action = urljoin(SOURCE_URL, form.get("action") or SOURCE_URL)
    method = (form.get("method") or "get").lower()
    payload = build_form_payload(form, select, option["value"])

    if method == "post":
        response = session.post(
            action,
            data=payload,
            timeout=REQUEST_TIMEOUT,
            headers={"Referer": SOURCE_URL},
        )
    else:
        response = session.get(
            action,
            params=payload,
            timeout=REQUEST_TIMEOUT,
            headers={"Referer": SOURCE_URL},
        )

    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


# ============================================================
# 7. Suspension detection
# ============================================================

SUSPENSION_PATTERNS = [
    # Korean service suspension / unavailable-route language.
    r"접수\s*(?:가\s*)?(?:불가|불가능)",
    r"접수\s*중지",
    r"접수\s*중단",
    r"서비스\s*(?:중단|중지|불가)",
    r"취급\s*(?:중지|중단|불가)",
    r"발송\s*(?:중지|중단|불가)",
    r"운송편\s*(?:중단|취소)",
    r"항공편\s*(?:중단|취소)",
    r"운송\s*불가",
    r"배달\s*불가",
    r"서비스\s*제공\s*불가",

    # English equivalents.
    r"\bservice\s+suspension\b",
    r"\bservice\s+suspended\b",
    r"\bno\s+service\b",
    r"\bservice\s+unavailable\b",
    r"\broute\s+unavailable\b",
    r"\broute\s+suspended\b",
    r"\bnot\s+available\b",
    r"\btemporarily\s+suspended\b",
    r"\bpostal\s+service\s+suspended\b",
]

SUSPENSION_REGEX = re.compile(
    "|".join(f"(?:{pattern})" for pattern in SUSPENSION_PATTERNS),
    flags=re.IGNORECASE,
)


def is_suspended_by_notice(notice_ko: str, notice_en: str) -> bool:
    """Return True if either language contains a suspension indicator."""
    return bool(
        SUSPENSION_REGEX.search(notice_ko or "")
        or SUSPENSION_REGEX.search(notice_en or "")
    )


# ============================================================
# 8. Report formatting
# ============================================================

def format_destination(record: dict) -> str:
    """Format one destination for the text report."""
    lines = [
        f"Postcrossing No.: {record['master_number'] or 'UNMATCHED'}",
        f"Korean name: {record['korean']}",
        f"English name: {record['english']}",
        f"Dropdown value: {record['value']}",
        f"Urgent notice (Korean): {record['notice_ko'] or '(none)'}",
        f"Urgent notice (English): {record['notice_en'] or '(none)'}",
    ]
    return "\n".join(lines)


def write_report(records: list, errors: list, fetched_at: str):
    """Write the complete destination and suspension report."""
    by_master_number = {}
    for record in records:
        number = record["master_number"]
        if number is not None:
            by_master_number[number] = record

    missing = [
        item for item in MASTER
        if item["number"] not in by_master_number
    ]

    explicit_suspensions = [
        record for record in records if record["suspended_by_notice"]
    ]

    # Suspension list is the union of explicit notices and master-list
    # destinations missing from the live dropdown.
    suspension_keys = set()
    suspended = []

    for record in explicit_suspensions:
        key = ("master", record["master_number"]) if (
            record["master_number"] is not None
        ) else ("dropdown", record["value"])

        if key not in suspension_keys:
            suspension_keys.add(key)
            suspended.append({
                "number": record["master_number"],
                "korean": record["korean"],
                "english": record["english"],
                "reason": "Urgent notice indicates possible service suspension",
                "notice_ko": record["notice_ko"],
                "notice_en": record["notice_en"],
            })

    for item in missing:
        key = ("master", item["number"])
        if key not in suspension_keys:
            suspension_keys.add(key)
            suspended.append({
                "number": item["number"],
                "korean": "(not present in dropdown)",
                "english": item["name"],
                "reason": "Missing from the Korea Post destination dropdown",
                "notice_ko": "",
                "notice_en": "",
            })

    lines = [
        "=" * 72,
        "KOREA POST — INTERNATIONAL LETTER POST MONITOR",
        "=" * 72,
        f"Source: {SOURCE_URL}",
        f"Generated (UTC): {fetched_at}",
        "",
        "SUMMARY",
        "-" * 72,
        f"Master-list destinations: {len(MASTER)}",
        f"Destinations found in dropdown: {len(records)}",
        f"Matched to master list: {len(by_master_number)}",
        f"Unmatched dropdown destinations: "
        f"{sum(1 for r in records if r['master_number'] is None)}",
        f"Master-list destinations missing from dropdown: {len(missing)}",
        f"Destinations with suspension indicators in notices: "
        f"{len(explicit_suspensions)}",
        f"Total unique suspended destinations: {len(suspended)}",
        "",
        "NOTE: A missing dropdown entry is flagged as potentially suspended.",
        "A notice match is a keyword-based indicator and should be reviewed.",
        "",
        "=" * 72,
        "SECTION 1 — ALL DESTINATIONS IN THE DROPDOWN",
        "=" * 72,
        "",
    ]

    for index, record in enumerate(records, start=1):
        lines.append(f"[DESTINATION {index} of {len(records)}]")
        lines.append(format_destination(record))
        lines.append("-" * 72)

    lines.extend([
        "",
        "=" * 72,
        f"SECTION 2 — SUSPENDED DESTINATIONS ({len(suspended)} TOTAL)",
        "=" * 72,
        "",
    ])

    for item in sorted(
        suspended,
        key=lambda value: (
            value["number"] is None,
            value["number"] or 999,
            value["english"].lower(),
        ),
    ):
        number = (
            str(item["number"])
            if item["number"] is not None
            else "UNMATCHED"
        )
        lines.extend([
            f"Postcrossing No.: {number}",
            f"Korean name: {item['korean']}",
            f"English name: {item['english']}",
            f"Reason: {item['reason']}",
        ])

        if item["notice_ko"]:
            lines.append(
                f"Urgent notice (Korean): {item['notice_ko']}"
            )
            lines.append(
                f"Urgent notice (English): "
                f"{item['notice_en'] or '(translation unavailable)'}"
            )
        else:
            lines.append("Urgent notice (Korean): (not available)")
            lines.append("Urgent notice (English): (not available)")

        lines.append("-" * 72)

    if errors:
        lines.extend([
            "",
            "=" * 72,
            f"SECTION 3 — WARNINGS AND EXTRACTION ERRORS ({len(errors)})",
            "=" * 72,
            "",
        ])
        lines.extend(f"- {error}" for error in errors)
    else:
        lines.extend([
            "",
            "Extraction warnings: none recorded.",
        ])

    lines.extend([
        "",
        "END OF REPORT",
        "",
    ])

    OUTPUT_FILE.write_text("\n".join(lines), encoding="utf-8")


# ============================================================
# 9. Main monitoring workflow
# ============================================================

def main():
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    errors = []

    print(f"Fetching Korea Post page: {SOURCE_URL}")
    response = fetch(SOURCE_URL)
    page_soup = BeautifulSoup(response.text, "html.parser")

    form, destination_select, options = discover_form_and_options(
        page_soup
    )

    print(f"Destination options discovered: {len(options)}")

    records = []
    seen_values = set()

    for index, option in enumerate(options, start=1):
        value = option["value"]
        korean_name = html.unescape(option["korean"]).strip()

        if value in seen_values:
            errors.append(
                f"Duplicate dropdown value {value!r} for {korean_name!r}"
            )
            continue
        seen_values.add(value)

        print(
            f"[{index}/{len(options)}] "
            f"Checking {korean_name} (value={value})"
        )

        try:
            selected_soup = query_destination(
                form, destination_select, option
            )
            notice_ko = extract_urgent_notice(selected_soup)

            # Translate the country name and any urgent notice.
            english_name = translate_to_english(korean_name)
            notice_en = translate_to_english(notice_ko) if notice_ko else ""

            # Match against the supplied master list.
            master_record = master_match(
                english_name,
                country_code=value,
            )

            # Prefer a matched master-list name as the English display name.
            if master_record:
                english_name = master_record["name"]

            record = {
                "value": value,
                "korean": korean_name,
                "english": english_name,
                "master_number": (
                    master_record["number"] if master_record else None
                ),
                "notice_ko": notice_ko,
                "notice_en": notice_en,
                "suspended_by_notice": is_suspended_by_notice(
                    notice_ko, notice_en
                ),
            }
            records.append(record)

        except Exception as exc:
            message = (
                f"Failed to query {korean_name!r} "
                f"(value={value!r}): {type(exc).__name__}: {exc}"
            )
            errors.append(message)
            print(f"WARNING: {message}", file=sys.stderr)

            if STRICT_MODE:
                # Do not publish an incomplete report as if it were complete.
                raise RuntimeError(
                    "A destination query failed. See the log above. "
                    "Fix the extraction problem before trusting the totals."
                ) from exc

        time.sleep(REQUEST_DELAY_SECONDS)

    if not records:
        raise RuntimeError("No destination records were successfully read.")

    # Do not quietly publish a partial list if individual requests failed.
    if STRICT_MODE and errors:
        raise RuntimeError(
            f"Extraction finished with {len(errors)} error(s). "
            "No reliable complete report can be produced."
        )

    write_report(records, errors, fetched_at)

    print()
    print(f"Report written to: {OUTPUT_FILE.resolve()}")
    print(f"Destinations found: {len(records)}")
    print(f"Extraction warnings: {len(errors)}")
    print("Review the generated report before enabling change monitoring.")


if __name__ == "__main__":
    main()
