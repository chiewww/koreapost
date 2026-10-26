
# ============================================================
# Korea Post International Letter Post Monitor
# File: monitor_korea.py
#
# Report: output_korea.txt
#
# What it does:
#   1. Loads the 248 numbered Postcrossing destinations.
#   2. Reads the destination dropdown from Korea Post's
#      International Letter Post (국제통상) page.
#   3. Records each available destination's Korean and English name.
#   4. Extracts urgent notices and attempts Korean-to-English translation.
#   5. Lists master destinations absent from the live dropdown.
#   6. Flags incomplete extraction and translation failures.
#
# Important:
#   A destination absent from the dropdown is classified as
#   "not listed / verify suspension". Absence alone does not prove
#   that Korea Post has officially suspended service.
# ============================================================

from __future__ import annotations

import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin

import pycountry
import requests
from bs4 import BeautifulSoup, Tag


# ============================================================
# 1. SETTINGS
# ============================================================

PAGE_URL = (
    "https://ems.epost.go.kr/"
    "front.EmsNormalAirShipSendCondition.postal"
    "?frnMailDivcdTab=1&frnTranspPartyDivcd=2"
)

OUTPUT_FILE = Path("output_korea.txt")

REQUEST_TIMEOUT = 25
REQUEST_DELAY_SECONDS = 0.4

# Translation endpoint. Translation is best-effort; Korean text is
# always retained if translation is unavailable.
TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# Try translations once per unique text and cache the result.
TRANSLATION_CACHE: dict[str, Optional[str]] = {}

# These expressions help identify notices about service availability.
SUSPENSION_TERMS = (
    "발송 중지",
    "발송중지",
    "접수 중지",
    "접수중지",
    "접수 불가",
    "접수불가",
    "발송 불가",
    "발송불가",
    "서비스 중지",
    "서비스중지",
    "서비스 중단",
    "서비스중단",
    "취급 중지",
    "취급중지",
    "배달 중지",
    "배달중지",
    "운송 중단",
    "운송중단",
    "일시 중지",
    "일시중지",
    "이용 불가",
    "이용불가",
    "우편물 접수 제한",
    "접수 제한",
    "접수제한",
    "발송 제한",
    "발송제한",
    "운송 제한",
    "운송제한",
    "항공편 중단",
    "항공편 운항 중단",
    "중단되었습니다",
    "중지되었습니다",
    "불가합니다",
)

NOTICE_KEYWORDS = (
    "긴급공지",
    "긴급 공지",
    "공지사항",
    "공지 사항",
    "발송 중지",
    "발송중지",
    "접수 중지",
    "접수중지",
    "접수 불가",
    "접수불가",
    "서비스 중단",
    "서비스중단",
    "서비스 중지",
    "서비스중지",
    "우편물",
    "국제통상",
    "배달 지연",
    "배달지연",
)


# ============================================================
# 2. POSTCROSSING MASTER LIST — PRESERVED AS PROVIDED
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


@dataclass(frozen=True)
class MasterDestination:
    number: int
    name: str


@dataclass(frozen=True)
class Destination:
    code: str
    korean_name: str
    english_name: str
    master_number: Optional[int]


@dataclass(frozen=True)
class Notice:
    korean_text: str
    english_text: Optional[str]
    is_suspension: bool


def load_master_list(text: str) -> list[MasterDestination]:
    """Parse the numbered master list without changing its order."""
    results: list[MasterDestination] = []

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        number_text, separator, name = line.partition("|")
        if not separator:
            raise ValueError(f"Invalid master-list line: {line!r}")

        results.append(
            MasterDestination(
                number=int(number_text.strip()),
                name=name.strip(),
            )
        )

    if len(results) != 248:
        raise ValueError(
            f"Expected 248 master destinations; parsed {len(results)}."
        )

    expected_numbers = list(range(1, 249))
    actual_numbers = [item.number for item in results]

    if actual_numbers != expected_numbers:
        raise ValueError(
            "The master list must contain every number from 1 to 248 "
            "in order, without duplicates."
        )

    return results


MASTER_LIST = load_master_list(MASTER_LIST_TEXT)


# ============================================================
# 3. COUNTRY NAME NORMALIZATION AND MATCHING
# ============================================================

def normalize_name(value: str) -> str:
    """Normalize punctuation, accents, and spacing for comparisons."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value if not unicodedata.combining(char)
    )
    value = value.casefold()
    value = value.replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


# Common names that differ between the master list and ISO country names.
ALIASES = {
    "aland islands": "aland islands",
    "antigua and barbuda": "antigua and barbuda",
    "bosnia herzegovina": "bosnia herzegovina",
    "brunei darussalam": "brunei",
    "cape verde": "cabo verde",
    "cabo verde": "cabo verde",
    "democratic republic of the congo": "dem rep of congo",
    "democratic republic of congo": "dem rep of congo",
    "dr congo": "dem rep of congo",
    "congo democratic republic": "dem rep of congo",
    "republic of the congo": "congo",
    "congo brazzaville": "congo",
    "congo kinshasa": "dem rep of congo",
    "cote divoire": "cote d ivoire",
    "ivory coast": "cote d ivoire",
    "czech republic": "czechia",
    "swaziland": "eswatini swaziland",
    "eswatini": "eswatini swaziland",
    "falkland islands": "falkland islands malvinas",
    "malvinas": "falkland islands malvinas",
    "hong kong": "hong kong",
    "macao": "macao",
    "macau": "macao",
    "north korea": "korea north",
    "korea north": "korea north",
    "south korea": "korea south",
    "korea south": "korea south",
    "laos": "laos",
    "lao peoples democratic republic": "laos",
    "moldova": "moldova",
    "republic of moldova": "moldova",
    "myanmar": "myanmar",
    "burma": "myanmar",
    "nauru": "nauru naoero",
    "naoero": "nauru naoero",
    "netherlands": "netherlands",
    "the netherlands": "netherlands",
    "palestine": "palestine",
    "state of palestine": "palestine",
    "reunion": "reunion",
    "russian federation": "russia",
    "russia": "russia",
    "sao tome and principe": "sao tome and principe",
    "saint pierre and miquelon": "saint pierre miquelon",
    "st pierre and miquelon": "saint pierre miquelon",
    "svalbard and jan mayen": "svalbard and jan mayen",
    "taiwan": "taiwan",
    "province of china taiwan": "taiwan",
    "timor leste": "timor leste",
    "east timor": "timor leste",
    "turkey": "turkey",
    "turkiye": "turkey",
    "united states": "usa",
    "united states of america": "usa",
    "usa": "usa",
    "u s a": "usa",
    "united states minor outlying islands": "u s minor outlying islands",
    "us minor outlying islands": "u s minor outlying islands",
    "holy see": "vatican",
    "vatican city": "vatican",
    "vatican": "vatican",
    "venezuela": "venezuela",
    "venezuela bolivarian republic of": "venezuela",
    "viet nam": "vietnam",
    "virgin islands british": "virgin islands uk",
    "british virgin islands": "virgin islands uk",
    "virgin islands u s": "virgin islands of the usa",
    "virgin islands us": "virgin islands of the usa",
    "us virgin islands": "virgin islands of the usa",
    "wallis and futuna": "wallis futuna",
    "western sahara": "western sahara",
}


def canonical_name(value: str) -> str:
    normalized = normalize_name(value)
    return ALIASES.get(normalized, normalized)


def master_name_index(
    master_list: list[MasterDestination],
) -> dict[str, int]:
    """Build a name-to-master-number lookup."""
    index: dict[str, int] = {}

    for item in master_list:
        index[canonical_name(item.name)] = item.number

    # Extra equivalences for common international naming variants.
    additional = {
        "united states": "usa",
        "united states of america": "usa",
        "u s a": "usa",
        "ivory coast": "cote d ivoire",
        "cape verde": "cabo verde",
        "czech republic": "czechia",
        "burma": "myanmar",
        "macau": "macao",
        "east timor": "timor leste",
        "turkiye": "turkey",
        "holy see": "vatican",
        "vatican city": "vatican",
        "brunei darussalam": "brunei",
        "lao peoples democratic republic": "laos",
        "russian federation": "russia",
        "viet nam": "vietnam",
        "republic of moldova": "moldova",
        "state of palestine": "palestine",
        "british virgin islands": "virgin islands uk",
        "us virgin islands": "virgin islands of the usa",
    }

    for alias, canonical in additional.items():
        if canonical in index:
            index[alias] = index[canonical]

    return index


MASTER_NAME_INDEX = master_name_index(MASTER_LIST)


# English names for common ISO alpha-2 codes. pycountry supplies the rest.
CODE_NAME_OVERRIDES = {
    "AX": "Åland Islands",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "CD": "Dem. Rep. Of Congo",
    "CG": "Congo",
    "CI": "Côte d'Ivoire",
    "CZ": "Czechia",
    "FK": "Falkland Islands /Malvinas",
    "FM": "Micronesia",
    "GB": "United Kingdom",
    "HK": "Hong Kong",
    "IR": "Iran",
    "KP": "Korea(North)",
    "KR": "Korea(South)",
    "LA": "Laos",
    "MO": "Macao",
    "MM": "Myanmar",
    "NL": "Netherlands",
    "PS": "Palestine",
    "RU": "Russia",
    "SZ": "Eswatini /Swaziland",
    "TW": "Taiwan",
    "TR": "Turkey",
    "US": "U.S.A.",
    "VA": "Vatican",
    "VE": "Venezuela",
    "VN": "Vietnam",
}


def english_name_from_code(code: str, korean_name: str) -> str:
    """Get a useful English name using the dropdown's country code."""
    code = code.strip().upper()

    if code in CODE_NAME_OVERRIDES:
        return CODE_NAME_OVERRIDES[code]

    try:
        country = pycountry.countries.get(alpha_2=code)
        if country:
            return getattr(country, "common_name", country.name)
    except (KeyError, AttributeError):
        pass

    # If the code isn't an ISO alpha-2 code, translate the Korean label.
    translated = translate_to_english(korean_name)
    if translated:
        return translated

    return f"{korean_name} (English translation unavailable)"


def match_master_number(english_name: str) -> Optional[int]:
    return MASTER_NAME_INDEX.get(canonical_name(english_name))


# ============================================================
# 4. HTTP SESSION
# ============================================================

def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update(HEADERS)
    return session


def get_page(
    session: requests.Session,
    url: str,
) -> requests.Response:
    response = session.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response


# ============================================================
# 5. TRANSLATION
# ============================================================

def translate_to_english(text: str) -> Optional[str]:
    """
    Translate Korean text using Google's public translation endpoint.

    Translation is best-effort. A failed translation never removes the
    original Korean notice from the report.
    """
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return None

    if text in TRANSLATION_CACHE:
        return TRANSLATION_CACHE[text]

    # Avoid repeatedly sending extremely long page fragments.
    if len(text) > 4500:
        text = text[:4500]

    try:
        response = requests.get(
            TRANSLATE_URL,
            params={
                "client": "gtx",
                "sl": "ko",
                "tl": "en",
                "dt": "t",
                "q": text,
            },
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()

        translated_parts = []
        for segment in data[0]:
            if segment and segment[0]:
                translated_parts.append(segment[0])

        translated = "".join(translated_parts).strip()

        if not translated:
            TRANSLATION_CACHE[text] = None
            return None

        TRANSLATION_CACHE[text] = translated
        return translated

    except (requests.RequestException, ValueError, TypeError, IndexError) as exc:
        print(
            f"WARNING: Translation failed: {exc}",
            file=sys.stderr,
        )
        TRANSLATION_CACHE[text] = None
        return None


# ============================================================
# 6. READ THE DESTINATION DROPDOWN
# ============================================================

def get_destination_select(soup: BeautifulSoup) -> Optional[Tag]:
    """Find the country dropdown by its known name, then by heuristics."""
    select = soup.find("select", attrs={"name": "nation"})
    if isinstance(select, Tag):
        return select

    # Fallback: look for a select whose name/id suggests a destination.
    for candidate in soup.find_all("select"):
        name = str(candidate.get("name", "")).lower()
        element_id = str(candidate.get("id", "")).lower()
        combined = f"{name} {element_id}"

        if any(word in combined for word in ("nation", "country", "dest")):
            return candidate

    return None


def read_destinations(
    soup: BeautifulSoup,
    master_list: list[MasterDestination],
) -> list[Destination]:
    select = get_destination_select(soup)

    if select is None:
        raise RuntimeError(
            "Could not find the destination dropdown. "
            "The website may have changed its HTML."
        )

    destinations: list[Destination] = []
    seen_codes: set[str] = set()

    for option in select.find_all("option"):
        code = str(option.get("value", "")).strip()
        korean_name = option.get_text(" ", strip=True)

        # Ignore placeholders such as "Select destination".
        if not code or not korean_name:
            continue

        if code.lower() in {"", "0", "select", "all", "none"}:
            continue

        if korean_name in {"선택", "선택하세요", "도착국 선택"}:
            continue

        code_upper = code.upper()

        # Avoid duplicate option entries.
        if code_upper in seen_codes:
            continue
        seen_codes.add(code_upper)

        english_name = english_name_from_code(code_upper, korean_name)
        number = match_master_number(english_name)

        destinations.append(
            Destination(
                code=code_upper,
                korean_name=korean_name,
                english_name=english_name,
                master_number=number,
            )
        )

    if not destinations:
        raise RuntimeError(
            "The destination dropdown was found, but it contained no "
            "usable destination options."
        )

    return destinations


# ============================================================
# 7. EXTRACT URGENT NOTICES
# ============================================================

def has_notice_keyword(text: str) -> bool:
    return any(keyword in text for keyword in NOTICE_KEYWORDS)


def is_suspension_notice(text: str) -> bool:
    return any(term in text for term in SUSPENSION_TERMS)


def clean_notice_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip(" \t\r\n-•")


def extract_notice_candidates(soup: BeautifulSoup) -> list[str]:
    """
    Find likely notice blocks without treating the entire page as one notice.

    The site can change its markup, so this checks common notice containers
    and then falls back to lines containing notice/suspension keywords.
    """
    candidates: list[str] = []
    seen: set[str] = set()

    # First inspect elements likely to contain notices.
    selectors = [
        "[class*='notice']",
        "[id*='notice']",
        "[class*='urgent']",
        "[id*='urgent']",
        "[class*='gongji']",
        "[id*='gongji']",
        "[class*='board']",
        "[class*='alert']",
        "[class*='info']",
        "table",
        "ul",
        "ol",
    ]

    for selector in selectors:
        try:
            elements = soup.select(selector)
        except Exception:
            elements = []

        for element in elements:
            text = clean_notice_text(element.get_text("\n", strip=True))

            if not text or len(text) < 8 or len(text) > 2500:
                continue

            if not has_notice_keyword(text):
                continue

            normalized = normalize_name(text)
            if normalized in seen:
                continue

            seen.add(normalized)
            candidates.append(text)

    # Fallback: inspect individual lines of page text.
    page_text = soup.get_text("\n", strip=True)
    lines = [clean_notice_text(line) for line in page_text.splitlines()]
    lines = [line for line in lines if line]

    for index, line in enumerate(lines):
        if not has_notice_keyword(line):
            continue

        # Include nearby lines because headings and notice bodies are often
        # rendered as separate elements.
        start = max(0, index - 1)
        end = min(len(lines), index + 4)
        combined = clean_notice_text("\n".join(lines[start:end]))

        if len(combined) > 2500:
            combined = combined[:2500]

        normalized = normalize_name(combined)
        if normalized not in seen:
            seen.add(normalized)
            candidates.append(combined)

    # If the markup only exposes a suspension statement, include it.
    if not candidates:
        for line in lines:
            if is_suspension_notice(line):
                normalized = normalize_name(line)
                if normalized not in seen:
                    seen.add(normalized)
                    candidates.append(line)

    return candidates


def extract_notices(soup: BeautifulSoup) -> list[Notice]:
    raw_candidates = extract_notice_candidates(soup)
    notices: list[Notice] = []

    for text in raw_candidates:
        # Skip generic navigation labels.
        if len(text) < 12:
            continue

        english = translate_to_english(text)

        notices.append(
            Notice(
                korean_text=text,
                english_text=english,
                is_suspension=is_suspension_notice(text),
            )
        )

    return notices


# ============================================================
# 8. OPTIONAL PER-DESTINATION PAGE CHECK
# ============================================================

def collect_form_values(form: Tag) -> dict[str, str]:
    """
    Collect basic named form values so a country-specific POST can be tried.

    Korea Post may change form fields or require JavaScript. If the form
    cannot be submitted this way, the script keeps the original page data
    and explicitly reports that per-destination notices were not verified.
    """
    values: dict[str, str] = {}

    for element in form.find_all(["input", "select", "textarea"]):
        name = element.get("name")
        if not name:
            continue

        tag_name = element.name.lower()

        if tag_name == "input":
            input_type = str(element.get("type", "text")).lower()

            if input_type in {"submit", "button", "image", "reset", "file"}:
                continue

            if input_type in {"checkbox", "radio"} and not element.has_attr(
                "checked"
            ):
                continue

            values[name] = str(element.get("value", ""))

        elif tag_name == "select":
            selected = element.find("option", selected=True)
            if selected is None:
                selected = element.find("option")

            if selected is not None:
                values[name] = str(selected.get("value", ""))

        elif tag_name == "textarea":
            values[name] = element.get_text()

    return values


def try_country_specific_page(
    session: requests.Session,
    original_soup: BeautifulSoup,
    destination: Destination,
) -> Optional[BeautifulSoup]:
    """
    Try posting the selected destination to the page's form.

    This is deliberately conservative: if the form submission fails or
    returns an unusable page, return None rather than claiming success.
    """
    select = get_destination_select(original_soup)
    if select is None:
        return None

    form = select.find_parent("form")
    if not isinstance(form, Tag):
        return None

    action = str(form.get("action", "")).strip()
    method = str(form.get("method", "get")).strip().lower()
    target_url = urljoin(PAGE_URL, action or PAGE_URL)

    data = collect_form_values(form)
    data["nation"] = destination.code

    # Include a likely search button if the HTML exposes one.
    for button in form.find_all(["button", "input"]):
        button_type = str(button.get("type", "")).lower()
        name = str(button.get("name", "")).strip()
        value = str(button.get("value", "")).strip()
        label = button.get_text(" ", strip=True)

        if button_type == "submit" or "검색" in label or "검색" in value:
            if name and value:
                data[name] = value
                break

    try:
        time.sleep(REQUEST_DELAY_SECONDS)

        if method == "post":
            response = session.post(
                target_url,
                data=data,
                timeout=REQUEST_TIMEOUT,
                headers={"Referer": PAGE_URL},
            )
        else:
            response = session.get(
                target_url,
                params=data,
                timeout=REQUEST_TIMEOUT,
                headers={"Referer": PAGE_URL},
            )

        response.raise_for_status()

        if not response.text or len(response.text) < 200:
            return None

        return BeautifulSoup(response.text, "html.parser")

    except requests.RequestException as exc:
        print(
            f"WARNING: Country-specific request failed for "
            f"{destination.korean_name} ({destination.code}): {exc}",
            file=sys.stderr,
        )
        return None


def notice_signature(notices: list[Notice]) -> tuple[str, ...]:
    return tuple(
        normalize_name(notice.korean_text)
        for notice in notices
    )


def get_country_notices(
    session: requests.Session,
    original_soup: BeautifulSoup,
    original_notices: list[Notice],
    destination: Destination,
) -> tuple[list[Notice], bool]:
    """
    Return notices for a destination and whether a distinct response was
    observed. A distinct response is not automatically proof that the site
    accepted the selected destination; this is an HTML-based best effort.
    """
    country_soup = try_country_specific_page(
        session,
        original_soup,
        destination,
    )

    if country_soup is None:
        return [], False

    country_notices = extract_notices(country_soup)

    if not country_notices:
        return [], False

    if notice_signature(country_notices) == notice_signature(original_notices):
        # The server likely returned the same generic page.
        return [], False

    return country_notices, True


# ============================================================
# 9. REPORT FORMATTING
# ============================================================

def format_destination(destination: Destination) -> str:
    number_text = (
        f"#{destination.master_number}"
        if destination.master_number is not None
        else "#NOT MATCHED"
    )

    return (
        f"{number_text} | {destination.korean_name} | "
        f"{destination.english_name} | code={destination.code}"
    )


def format_notice(notice: Notice) -> list[str]:
    lines = [
        f"  Korean: {notice.korean_text}",
    ]

    if notice.english_text:
        lines.append(f"  English: {notice.english_text}")
    else:
        lines.append(
            "  English: Translation unavailable; Korean text retained."
        )

    lines.append(
        "  Suspension wording detected: "
        + ("YES" if notice.is_suspension else "NO / not detected")
    )

    return lines


def build_report(
    destinations: list[Destination],
    notices: list[Notice],
    extraction_warnings: list[str],
    per_country_notice_results: dict[str, list[Notice]],
    per_country_verified: set[str],
    master_list: list[MasterDestination],
    page_status: int,
) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    listed_master_numbers = {
        destination.master_number
        for destination in destinations
        if destination.master_number is not None
    }

    missing_destinations = [
        item
        for item in master_list
        if item.number not in listed_master_numbers
    ]

    unmatched_live_destinations = [
        item
        for item in destinations
        if item.master_number is None
    ]

    # A master-list destination is a notice-based suspension candidate only
    # if a country-specific response was observed and the notice text
    # includes suspension wording. Otherwise, the script does not infer it.
    notice_suspension_codes: set[str] = set()

    for code, country_notices in per_country_notice_results.items():
        if any(notice.is_suspension for notice in country_notices):
            notice_suspension_codes.add(code)

    destinations_by_code = {
        destination.code: destination
        for destination in destinations
    }

    report: list[str] = []

    report.extend(
        [
            "KOREA POST INTERNATIONAL LETTER POST MONITOR",
            "=" * 64,
            f"Generated: {timestamp}",
            f"Page: {PAGE_URL}",
            f"HTTP status: {page_status}",
            f"Master Postcrossing destinations: {len(master_list)}",
            f"Live dropdown destinations: {len(destinations)}",
            f"Urgent/notice blocks detected on main page: {len(notices)}",
            "",
            "IMPORTANT INTERPRETATION",
            "-" * 64,
            "This report reflects the HTML returned by Korea Post when the",
            "script ran. A destination absent from the dropdown is listed",
            "as 'not listed / verify suspension'; absence alone does not",
            "confirm an official service suspension.",
            "",
            "The website may render additional information with JavaScript",
            "or require a form interaction that plain HTTP requests cannot",
            "reproduce. Review the extraction warnings below.",
            "",
            "1. DESTINATIONS IN THE LIVE DROPDOWN",
            "=" * 64,
        ]
    )

    for index, destination in enumerate(destinations, start=1):
        report.append(f"{index}. {format_destination(destination)}")

        country_notices = per_country_notice_results.get(
            destination.code,
            [],
        )

        if country_notices:
            report.append("  Destination-specific notices:")
            for notice in country_notices:
                report.extend(format_notice(notice))
        else:
            report.append(
                "  Destination-specific notice: "
                + (
                    "No distinct country-specific notice was verified."
                    if destination.code in per_country_verified
                    else "Not independently verified by the HTTP form check."
                )
            )

    report.extend(
        [
            "",
            f"TOTAL LIVE DROPDOWN DESTINATIONS: {len(destinations)}",
            "",
            "2. URGENT NOTICES FOUND ON THE MAIN PAGE",
            "=" * 64,
        ]
    )

    if notices:
        for index, notice in enumerate(notices, start=1):
            report.append(f"Notice {index}:")
            report.extend(format_notice(notice))
            report.append("")
    else:
        report.append(
            "No notice block matching the script's notice keywords was found."
        )
        report.append(
            "This does not prove that no notice exists; the page markup may "
            "have changed or notices may load dynamically."
        )

    main_page_suspension_notices = [
        notice for notice in notices if notice.is_suspension
    ]

    report.extend(
        [
            "",
            "3. DESTINATIONS WITH VERIFIED COUNTRY-SPECIFIC SUSPENSION WORDING",
            "=" * 64,
        ]
    )

    verified_suspensions = []
    for code in sorted(notice_suspension_codes):
        destination = destinations_by_code.get(code)
        if destination:
            verified_suspensions.append(destination)

    if verified_suspensions:
        for destination in verified_suspensions:
            report.append(format_destination(destination))
    else:
        report.append(
            "None verified. The site may display general notices, or the "
            "HTTP form check may not reproduce the interactive search."
        )

    report.append(
        f"TOTAL DESTINATIONS WITH VERIFIED COUNTRY-SPECIFIC SUSPENSION "
        f"WORDING: {len(verified_suspensions)}"
    )
    report.append(
        f"MAIN-PAGE NOTICE BLOCKS CONTAINING SUSPENSION WORDING: "
        f"{len(main_page_suspension_notices)}"
    )

    report.extend(
        [
            "",
            "4. MASTER DESTINATIONS ABSENT FROM THE LIVE DROPDOWN",
            "=" * 64,
            "These are candidates to investigate, not confirmed suspensions.",
            "",
        ]
    )

    if missing_destinations:
        for item in missing_destinations:
            report.append(f"#{item.number} | {item.name}")
    else:
        report.append(
            "None. All master-list destinations matched a live dropdown item."
        )

    report.append(
        f"TOTAL MASTER DESTINATIONS ABSENT FROM DROPDOWN: "
        f"{len(missing_destinations)}"
    )

    report.extend(
        [
            "",
            "5. LIVE DROPDOWN ITEMS THAT DID NOT MATCH THE MASTER LIST",
            "=" * 64,
        ]
    )

    if unmatched_live_destinations:
        for destination in unmatched_live_destinations:
            report.append(format_destination(destination))
    else:
        report.append("None.")

    report.append(
        f"TOTAL UNMATCHED LIVE DROPDOWN ITEMS: "
        f"{len(unmatched_live_destinations)}"
    )

    report.extend(
        [
            "",
            "6. EXTRACTION WARNINGS",
            "=" * 64,
        ]
    )

    if extraction_warnings:
        for warning in extraction_warnings:
            report.append(f"- {warning}")
    else:
        report.append("No structural extraction warnings detected.")

    if len(destinations) <= 30:
        report.append(
            "- The live dropdown contains 30 or fewer destinations. "
            "Confirm manually that the page is displaying the intended "
            "International Letter Post (국제통상) service and that the "
            "destination list is not being filtered."
        )

    if len(destinations) < 100:
        report.append(
            "- The live dropdown is much smaller than the 248-item master "
            "list. This report does not assume that every missing destination "
            "is officially suspended."
        )

    report.extend(
        [
            "",
            "7. SUMMARY",
            "=" * 64,
            f"Master destinations: {len(master_list)}",
            f"Live dropdown destinations: {len(destinations)}",
            f"Master destinations absent from dropdown: "
            f"{len(missing_destinations)}",
            f"Unmatched live dropdown entries: "
            f"{len(unmatched_live_destinations)}",
            f"Main-page urgent/notice blocks: {len(notices)}",
            f"Main-page notices containing suspension wording: "
            f"{len(main_page_suspension_notices)}",
            f"Country-specific suspensions verified by form response: "
            f"{len(verified_suspensions)}",
            "",
            "END OF REPORT",
        ]
    )

    return "\n".join(report) + "\n"


# ============================================================
# 10. MAIN
# ============================================================

def main() -> int:
    print("=" * 64)
    print("Korea Post International Letter Post Monitor")
    print("=" * 64)
    print(f"Master list: {len(MASTER_LIST)} destinations")
    print(f"Target page: {PAGE_URL}")

    session = make_session()

    try:
        response = get_page(session, PAGE_URL)
    except requests.RequestException as exc:
        print(f"ERROR: Could not retrieve Korea Post page: {exc}", file=sys.stderr)
        return 1

    print(f"HTTP status: {response.status_code}")
    print(f"Final URL: {response.url}")

    soup = BeautifulSoup(response.text, "html.parser")
    warnings: list[str] = []

    try:
        destinations = read_destinations(soup, MASTER_LIST)
    except Exception as exc:
        print(f"ERROR: Could not extract destinations: {exc}", file=sys.stderr)
        return 1

    if len(destinations) <= 30:
        warnings.append(
            f"Only {len(destinations)} destination options were extracted. "
            "The source may be filtered, incomplete, or dynamically rendered."
        )

    if len(destinations) < len(MASTER_LIST):
        warnings.append(
            "The number of live dropdown options is smaller than the "
            "248-item master list. Missing entries are reported separately "
            "and are not automatically treated as confirmed suspensions."
        )

    print(f"Destination dropdown count: {len(destinations)}")

    for index, destination in enumerate(destinations, start=1):
        print(
            f"[{index}/{len(destinations)}] "
            f"{destination.korean_name} "
            f"(code={destination.code}, "
            f"English={destination.english_name})"
        )

    notices = extract_notices(soup)
    print(f"Main-page notice blocks detected: {len(notices)}")

    if not notices:
        warnings.append(
            "No urgent notice blocks were detected. Check the page manually "
            "if Korea Post displays notices through JavaScript."
        )

    # Attempt country-specific form requests. If the page does not respond
    # differently, the report says that country-specific notices were not
    # independently verified rather than assigning generic notices to every
    # destination.
    country_notice_results: dict[str, list[Notice]] = {}
    country_verified: set[str] = set()

    print("Checking whether destination-specific notices can be retrieved...")

    for index, destination in enumerate(destinations, start=1):
        print(
            f"[notice check {index}/{len(destinations)}] "
            f"{destination.korean_name}"
        )

        country_notices, verified = get_country_notices(
            session=session,
            original_soup=soup,
            original_notices=notices,
            destination=destination,
        )

        if verified:
            country_verified.add(destination.code)
            country_notice_results[destination.code] = country_notices

        time.sleep(REQUEST_DELAY_SECONDS)

    if not country_verified:
        warnings.append(
            "The HTTP form check did not verify distinct country-specific "
            "notice responses. The website may require JavaScript or a "
            "different form submission. Do not interpret the absence of "
            "country-specific notices as proof that no restrictions exist."
        )

    # Warn when country-code-to-English mapping did not match the master list.
    unmatched = [d for d in destinations if d.master_number is None]
    if unmatched:
        warnings.append(
            f"{len(unmatched)} live dropdown entries could not be matched "
            "to the 248-item master list. Review the English names and aliases."
        )

    report = build_report(
        destinations=destinations,
        notices=notices,
        extraction_warnings=warnings,
        per_country_notice_results=country_notice_results,
        per_country_verified=country_verified,
        master_list=MASTER_LIST,
        page_status=response.status_code,
    )

    try:
        OUTPUT_FILE.write_text(report, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Could not write report: {exc}", file=sys.stderr)
        return 1

    print()
    print(f"Report written to: {OUTPUT_FILE.resolve()}")
    print(f"Master destinations: {len(MASTER_LIST)}")
    print(f"Live dropdown destinations: {len(destinations)}")
    print(f"Main-page notices: {len(notices)}")
    print(f"Extraction warnings: {len(warnings)}")

    if len(destinations) <= 30:
        print(
            "WARNING: Only a small destination list was returned. "
            "Review the report's extraction warnings before relying on "
            "the missing-destination list."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
