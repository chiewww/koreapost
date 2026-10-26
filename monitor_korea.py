
# ============================================================
# Korea Post International Letter Post Monitor
# File: monitor_korea.py
# Output: output_korea.txt
#
# Features:
#   1. Opens the Korea Post service page.
#   2. Explicitly clicks the 국제통상 tab (a#go_emsP).
#   3. Captures XHR/fetch network diagnostics.
#   4. Reads the live destination dropdown.
#   5. Matches destinations against the 248-entry master list.
#   6. Extracts ONLY 긴급공지, excluding 주요안내사항.
#   7. Translates Korean urgent notices into English when possible.
#   8. Flags possible suspension wording in urgent notices.
#   9. Reports unmatched master-list destinations without claiming
#      they are suspended.
#
# IMPORTANT:
# Missing from the dropdown does NOT prove suspension.
# ============================================================

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pycountry
import requests
from playwright.sync_api import sync_playwright


# ============================================================
# 1. SETTINGS
# ============================================================

PAGE_URL = (
    "https://ems.epost.go.kr/front.EmsNormalAirShipSendCondition.postal"
    "?frnMailDivcdTab=1&frnTranspPartyDivcd=2"
)

OUTPUT_FILE = Path("output_korea.txt")

BROWSER_TIMEOUT_MS = 20000
INITIAL_PAGE_WAIT_MS = 2500
TAB_WAIT_MS = 2500
SEARCH_WAIT_MS = 900
TRANSLATION_TIMEOUT_SECONDS = 20
REQUEST_DELAY_SECONDS = 0.3

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"


# ============================================================
# 2. POSSIBLE SUSPENSION WORDING
# ============================================================

SUSPENSION_TERMS = (
    "발송 중지", "발송중지",
    "접수 중지", "접수중지",
    "접수 불가", "접수불가",
    "발송 불가", "발송불가",
    "서비스 중지", "서비스중지",
    "서비스 중단", "서비스중단",
    "취급 중지", "취급중지",
    "배달 중지", "배달중지",
    "운송 중단", "운송중단",
    "일시 중지", "일시중지",
    "이용 불가", "이용불가",
    "접수 제한", "접수제한",
    "발송 제한", "발송제한",
    "운송 제한", "운송제한",
    "항공편 중단",
    "항공편 운항 중단",
    "중단되었습니다",
    "중지되었습니다",
    "불가합니다",
)


# ============================================================
# 3. POSTCROSSING MASTER LIST
# Original numbers 1–248 are preserved.
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
    entries = []

    for line in MASTER_LIST_TEXT.splitlines():
        number, name = line.split("|", 1)
        entries.append((int(number), name.strip()))

    expected_numbers = list(range(1, 249))
    actual_numbers = [number for number, _ in entries]

    if actual_numbers != expected_numbers:
        raise ValueError(
            "Master list validation failed. Expected entries 1–248."
        )

    return entries


MASTER_LIST = parse_master_list()


# ============================================================
# 4. COUNTRY-NAME MATCHING
# ============================================================

CODE_NAME_OVERRIDES = {
    "AX": "Åland Islands",
    "BQ": "Bonaire, Sint Eustatius and Saba",
    "CD": "Dem. Rep. Of Congo",
    "CG": "Congo",
    "CI": "Côte d'Ivoire",
    "CZ": "Czechia",
    "FK": "Falkland Islands /Malvinas",
    "GB": "United Kingdom",
    "HK": "Hong Kong",
    "KP": "Korea(North)",
    "KR": "Korea(South)",
    "LA": "Laos",
    "MO": "Macao",
    "MM": "Myanmar",
    "PS": "Palestine",
    "RU": "Russia",
    "SZ": "Eswatini /Swaziland",
    "TW": "Taiwan",
    "TR": "Turkey",
    "US": "U.S.A.",
    "UM": "U.S. Minor Outlying Islands",
    "VA": "Vatican",
    "VE": "Venezuela",
    "VN": "Vietnam",
}

ALIASES = {
    "aland islands": "aland islands",
    "antigua and barbuda": "antigua and barbuda",
    "bosnia herzegovina": "bosnia herzegovina",
    "brunei darussalam": "brunei",
    "cape verde": "cabo verde",
    "cote divoire": "cote d ivoire",
    "ivory coast": "cote d ivoire",
    "democratic republic of the congo": "dem rep of congo",
    "democratic republic of congo": "dem rep of congo",
    "dr congo": "dem rep of congo",
    "congo democratic republic": "dem rep of congo",
    "congo kinshasa": "dem rep of congo",
    "republic of the congo": "congo",
    "congo brazzaville": "congo",
    "czech republic": "czechia",
    "eswatini": "eswatini swaziland",
    "swaziland": "eswatini swaziland",
    "falkland islands": "falkland islands malvinas",
    "malvinas": "falkland islands malvinas",
    "macau": "macao",
    "north korea": "korea north",
    "south korea": "korea south",
    "lao peoples democratic republic": "laos",
    "lao pdr": "laos",
    "republic of moldova": "moldova",
    "burma": "myanmar",
    "nauru": "nauru naoero",
    "naoero": "nauru naoero",
    "the netherlands": "netherlands",
    "state of palestine": "palestine",
    "russian federation": "russia",
    "saint pierre and miquelon": "saint pierre miquelon",
    "st pierre and miquelon": "saint pierre miquelon",
    "east timor": "timor leste",
    "turkiye": "turkey",
    "united states": "usa",
    "united states of america": "usa",
    "usa": "usa",
    "u s a": "usa",
    "holy see": "vatican",
    "vatican city": "vatican",
    "viet nam": "vietnam",
    "british virgin islands": "virgin islands uk",
    "virgin islands british": "virgin islands uk",
    "us virgin islands": "virgin islands of the usa",
    "virgin islands us": "virgin islands of the usa",
    "virgin islands u s": "virgin islands of the usa",
    "wallis and futuna": "wallis futuna",
}


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def canonical(value: str) -> str:
    normalized = normalize(value)
    return ALIASES.get(normalized, normalized)


MASTER_INDEX = {
    canonical(name): number
    for number, name in MASTER_LIST
}


def master_number(name: str):
    return MASTER_INDEX.get(canonical(name))


def english_name(code: str, korean_name: str) -> str:
    code = (code or "").strip().upper()

    if code in CODE_NAME_OVERRIDES:
        return CODE_NAME_OVERRIDES[code]

    country = pycountry.countries.get(alpha_2=code)

    if country:
        return getattr(country, "common_name", country.name)

    return translate_text(korean_name) or korean_name


# ============================================================
# 5. TRANSLATION
# ============================================================

translation_cache = {}


def translate_text(text: str):
    """Translate Korean text to English; return None if unavailable."""
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return None

    if text in translation_cache:
        return translation_cache[text]

    # Split long notices into smaller translation requests.
    if len(text) > 3500:
        pieces = []
        remaining = text

        while remaining:
            cut = min(3500, len(remaining))

            if cut < len(remaining):
                split_at = remaining.rfind(" ", 0, cut)
                if split_at > 1000:
                    cut = split_at

            pieces.append(remaining[:cut])
            remaining = remaining[cut:].strip()

        translated_pieces = [
            translate_text(piece)
            for piece in pieces
        ]

        if any(piece is None for piece in translated_pieces):
            translation_cache[text] = None
            return None

        result = " ".join(translated_pieces)
        translation_cache[text] = result
        return result

    for attempt in range(3):
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
                timeout=TRANSLATION_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            data = response.json()

            result = "".join(
                part[0]
                for part in data[0]
                if part and part[0]
            ).strip()

            if result:
                translation_cache[text] = result
                return result

        except (
            requests.RequestException,
            ValueError,
            TypeError,
            IndexError,
            KeyError,
        ):
            time.sleep(1 + attempt)

    translation_cache[text] = None
    return None


# ============================================================
# 6. NETWORK DIAGNOSTICS
# ============================================================

def attach_network_diagnostics(page, network_events):
    """Record browser XHR/fetch requests and their responses."""

    def on_request(request):
        if request.resource_type in ("xhr", "fetch"):
            event = {
                "kind": "request",
                "method": request.method,
                "resource_type": request.resource_type,
                "url": request.url,
            }
            network_events.append(event)

            print(
                "[NETWORK REQUEST]",
                request.resource_type,
                request.method,
                request.url,
            )

    def on_response(response):
        request = response.request

        if request.resource_type in ("xhr", "fetch"):
            content_type = response.headers.get("content-type", "")

            event = {
                "kind": "response",
                "status": response.status,
                "resource_type": request.resource_type,
                "url": response.url,
                "content_type": content_type,
            }
            network_events.append(event)

            print(
                "[NETWORK RESPONSE]",
                response.status,
                request.resource_type,
                response.url,
                f"content-type={content_type}",
            )

    page.on("request", on_request)
    page.on("response", on_response)


# ============================================================
# 7. PAGE AND TAB DIAGNOSTICS
# ============================================================

def print_page_diagnostics(page, heading="PAGE DIAGNOSTICS"):
    print(f"\n========== {heading} ==========")
    print("Final URL:", page.url)
    print("Page title:", page.title())

    print("\nTabs and service labels:")

    for label in ["국제소포", "국제통상"]:
        locator = page.get_by_text(label, exact=True)
        print(f"{label}: count={locator.count()}")

        for index in range(locator.count()):
            try:
                item = locator.nth(index)
                print(
                    f"  [{index}]",
                    "tag=", item.evaluate("(el) => el.tagName"),
                    "id=", item.get_attribute("id"),
                    "href=", item.get_attribute("href"),
                    "title=", item.get_attribute("title"),
                    "class=", item.get_attribute("class"),
                    "aria-selected=",
                    item.get_attribute("aria-selected"),
                )
            except Exception as exc:
                print("  Could not inspect:", exc)

    print("\nHidden fields related to service selection:")

    try:
        hidden_fields = page.locator(
            "input[type='hidden'][name='frnMailDivcdTab'], "
            "input[type='hidden'][name='frnTranspPartyDivcd']"
        ).evaluate_all("""
            elements => elements.map(el => ({
                name: el.name,
                value: el.value,
                id: el.id
            }))
        """)
        for field in hidden_fields:
            print(" ", field)
    except Exception as exc:
        print("Could not inspect hidden fields:", exc)

    print("\nAll select elements:")

    selects = page.locator("select")

    for index in range(selects.count()):
        item = selects.nth(index)

        try:
            print({
                "index": index,
                "name": item.get_attribute("name"),
                "title": item.get_attribute("title"),
                "id": item.get_attribute("id"),
                "options": item.locator("option").count(),
                "visible": item.is_visible(),
            })
        except Exception as exc:
            print(f"Select {index} inspection failed:", exc)

    print("======================================\n")


def activate_international_letter_tab(page):
    """
    Click the JavaScript-controlled 국제통상 tab.

    The supplied HTML showed:
        <a id="go_emsP" href="#" title="국제통상">국제통상</a>

    Clicking is intentional because href='#' does not navigate to a
    separate service URL by itself.
    """
    tab = page.locator("a#go_emsP")

    if tab.count() != 1:
        raise RuntimeError(
            "Expected exactly one a#go_emsP International Letter Post tab; "
            f"found {tab.count()}."
        )

    print("Activating 국제통상 using a#go_emsP ...")

    try:
        tab.click(timeout=BROWSER_TIMEOUT_MS)
    except Exception as exc:
        raise RuntimeError(
            f"Could not click the 국제통상 tab: {exc}"
        ) from exc

    # The tab may update the page with JavaScript or trigger a navigation.
    try:
        page.wait_for_load_state(
            "domcontentloaded",
            timeout=4000,
        )
    except Exception:
        # A JavaScript-only update does not necessarily navigate.
        pass

    page.wait_for_timeout(TAB_WAIT_MS)

    print("URL after clicking 국제통상:", page.url)
    print("Title after clicking 국제통상:", page.title())


# ============================================================
# 8. DESTINATION DROPDOWN
# ============================================================

def select_destination_dropdown(page):
    selectors = [
        "select[name='nation'][title='도착국']",
        "select[title='도착국']",
        "select[name='nation']",
    ]

    for selector in selectors:
        locator = page.locator(selector)

        if locator.count() == 1 and locator.is_visible():
            return locator

    # Fallback: search visible select elements.
    selects = page.locator("select")

    for index in range(selects.count()):
        candidate = selects.nth(index)

        try:
            if not candidate.is_visible():
                continue

            details = candidate.evaluate("""
                el => [
                    el.name || '',
                    el.id || '',
                    el.title || ''
                ].join(' ').toLowerCase()
            """)

            if any(
                word in details
                for word in ("nation", "country", "dest", "도착국")
            ):
                return candidate

        except Exception:
            continue

    raise RuntimeError(
        "Could not find the destination dropdown."
    )


def read_dropdown_options(page):
    """Read the current dropdown options, excluding placeholders."""
    dropdown = select_destination_dropdown(page)

    options = dropdown.locator("option").evaluate_all("""
        elements => elements.map(option => ({
            value: (option.value || '').trim(),
            text: (option.textContent || '').trim(),
            selected: option.selected
        }))
    """)

    destinations = []

    placeholders = {
        "선택",
        "선택하세요",
        "도착국 선택",
        "국가 선택",
        "전체",
    }

    for option in options:
        value = option["value"]
        text = option["text"]

        if not value or not text:
            continue

        if text in placeholders:
            continue

        destinations.append({
            "value": value,
            "text": text,
        })

    print("\n========== DROPDOWN RESULTS ==========")
    print("Dropdown selector:", "select[name='nation'][title='도착국']")
    print("Raw option count:", len(options))
    print("Destination dropdown count:", len(destinations))

    print("\nAll current destination options:")
    for index, option in enumerate(destinations, start=1):
        print(
            f"  {index}. value={option['value']!r}, "
            f"text={option['text']!r}"
        )

    print("======================================\n")

    return destinations


# ============================================================
# 9. SEARCH AND URGENT NOTICE EXTRACTION
# ============================================================

def click_search(page):
    """Click the visible 검색 control."""
    try:
        button = page.get_by_text("검색", exact=True).first

        if button.count() and button.is_visible():
            button.click(timeout=5000)
            page.wait_for_timeout(SEARCH_WAIT_MS)
            return

    except Exception:
        pass

    # Fallback for button, link, input, or image-based controls.
    clicked = page.evaluate("""
        () => {
            const nodes = [
                ...document.querySelectorAll(
                    'button, a, input[type="button"], ' +
                    'input[type="submit"], img'
                )
            ];

            const target = nodes.find(el => {
                const text = [
                    el.innerText,
                    el.value,
                    el.alt,
                    el.title,
                    el.getAttribute('aria-label')
                ].filter(Boolean).join(' ').trim();

                return text === '검색' || text.includes('검색');
            });

            if (!target) return false;

            const clickable = target.closest(
                'button, a, input[type="button"], input[type="submit"]'
            ) || target;

            clickable.click();
            return true;
        }
    """)

    if not clicked:
        raise RuntimeError("Could not find the Korea Post 검색 button.")

    page.wait_for_timeout(SEARCH_WAIT_MS)


def extract_urgent_notice(page) -> str:
    """
    Extract only the text between 긴급공지 and 주요안내사항.

    If either boundary is missing, return an empty string rather than
    risk including text from 주요안내사항.
    """
    body_text = page.locator("body").inner_text(timeout=10000)

    start_marker = "긴급공지"
    end_marker = "주요안내사항"

    start = body_text.find(start_marker)

    if start < 0:
        return ""

    start += len(start_marker)
    end = body_text.find(end_marker, start)

    if end < 0:
        return ""

    section = body_text[start:end]

    lines = [
        line.strip()
        for line in section.splitlines()
        if line.strip()
    ]

    ignored = {
        "초기화",
        "인쇄",
        "닫기",
        "검색",
        "도착국",
        "국가별 공통사항",
        "국가별공통사항",
    }

    lines = [
        line for line in lines
        if line not in ignored
    ]

    return "\n".join(lines).strip()


def is_suspension_notice(text: str) -> bool:
    return any(term in text for term in SUSPENSION_TERMS)


# ============================================================
# 10. REPORT GENERATION
# ============================================================

def format_destination_line(record):
    number = (
        f"#{record['number']}"
        if record["number"] is not None
        else "#UNMATCHED"
    )

    return (
        f"{number} | {record['korean']} | {record['english']} | "
        f"code={record['code']}"
    )


def build_report(
    timestamp,
    destination_records,
    missing,
    errors,
    network_events,
):
    lines = [
        "KOREA POST INTERNATIONAL LETTER POST MONITOR",
        f"Generated: {timestamp}",
        f"Destination dropdown count: {len(destination_records)}",
        "",
        "DESTINATIONS",
        "=" * 60,
    ]

    for record in destination_records:
        lines.append(format_destination_line(record))

        if record["notice_ko"]:
            lines.append("긴급공지 (Korean):")
            lines.extend(record["notice_ko"].splitlines())

            lines.append("Urgent notice (English):")

            if record["notice_en"]:
                lines.append(record["notice_en"])
            else:
                lines.append(
                    "[Translation unavailable; original Korean is retained.]"
                )
        else:
            lines.append("긴급공지: No text extracted.")

        lines.append("")

    # --------------------------------------------------------
    # A. Potential suspension indicators
    # --------------------------------------------------------

    lines.extend([
        "",
        "A. URGENT NOTICES WITH POSSIBLE SUSPENSION WORDING",
        "=" * 60,
    ])

    suspension_records = [
        record
        for record in destination_records
        if record["suspension"]
    ]

    if suspension_records:
        for record in sorted(
            suspension_records,
            key=lambda item: (
                item["number"]
                if item["number"] is not None
                else 9999
            ),
        ):
            number = (
                f"#{record['number']}"
                if record["number"] is not None
                else "#UNMATCHED"
            )

            lines.append(
                f"{number} | {record['korean']} | "
                f"{record['english']} | code={record['code']}"
            )

            if record["notice_ko"]:
                lines.append(f"  Korean: {record['notice_ko']}")

            if record["notice_en"]:
                lines.append(f"  English: {record['notice_en']}")
    else:
        lines.append(
            "No urgent notices matched the configured suspension terms."
        )

    # --------------------------------------------------------
    # B. Master-list destinations not matched
    # --------------------------------------------------------

    lines.extend([
        "",
        "B. MASTER-LIST DESTINATIONS NOT MATCHED TO LIVE DROPDOWN",
        "=" * 60,
    ])

    if missing:
        for number, name in missing:
            lines.append(
                f"#{number} | {name} | NOT MATCHED IN LIVE DROPDOWN "
                "(not proof of suspension)"
            )
    else:
        lines.append("All master-list destinations matched.")

    # --------------------------------------------------------
    # C. Data-quality summary
    # --------------------------------------------------------

    lines.extend([
        "",
        "IMPORTANT INTERPRETATION",
        "=" * 60,
        "A destination absent from the observed dropdown is not confirmed "
        "suspended by that fact alone.",
        "Suspension wording is a candidate indicator and should be checked "
        "against the complete official notice.",
        "This report extracts only 긴급공지 and intentionally excludes "
        "주요안내사항.",
        "",
        "DATA-QUALITY SUMMARY",
        "=" * 60,
        f"Live dropdown destinations: {len(destination_records)}",
        f"Master-list destinations not matched: {len(missing)}",
        f"Urgent notices with possible suspension wording: "
        f"{len(suspension_records)}",
        f"Destination processing errors: {len(errors)}",
    ])

    if len(destination_records) < 100:
        lines.extend([
            "",
            "WARNING: FEWER THAN 100 LIVE DROPDOWN DESTINATIONS",
            "The observed dropdown may be incomplete, may be in the wrong "
            "service state, or may be populated dynamically.",
            "Do not treat unmatched master-list destinations as confirmed "
            "suspensions.",
        ])

    if errors:
        lines.extend([
            "",
            "DESTINATIONS THAT COULD NOT BE CHECKED",
            "=" * 60,
        ])
        lines.extend(f"- {error}" for error in errors)

    # --------------------------------------------------------
    # D. Network diagnostics
    # --------------------------------------------------------

    lines.extend([
        "",
        "BROWSER NETWORK DIAGNOSTICS",
        "=" * 60,
        "XHR/fetch requests and responses captured during this run:",
    ])

    if network_events:
        for event in network_events:
            if event["kind"] == "request":
                lines.append(
                    f"REQUEST | {event['resource_type']} | "
                    f"{event['method']} | {event['url']}"
                )
            else:
                lines.append(
                    f"RESPONSE | status={event['status']} | "
                    f"{event['resource_type']} | "
                    f"content-type={event['content_type']} | "
                    f"{event['url']}"
                )
    else:
        lines.append(
            "No XHR/fetch events were captured. The page may use another "
            "resource type or include options in its initial HTML."
        )

    lines.extend([
        "",
        "END OF REPORT",
    ])

    return "\n".join(lines) + "\n"


# ============================================================
# 11. MAIN
# ============================================================

def main():
    timestamp = datetime.now(timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )

    destination_records = []
    errors = []
    network_events = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)

        page = browser.new_page(
            locale="ko-KR",
            user_agent=HEADERS["User-Agent"],
        )
        page.set_default_timeout(BROWSER_TIMEOUT_MS)

        # Attach listeners before navigation and tab activation.
        attach_network_diagnostics(page, network_events)

        try:
            print("Opening Korea Post page:")
            print(PAGE_URL)

            page.goto(
                PAGE_URL,
                wait_until="domcontentloaded",
                timeout=BROWSER_TIMEOUT_MS,
            )

            page.wait_for_timeout(INITIAL_PAGE_WAIT_MS)

            print_page_diagnostics(
                page,
                heading="PAGE DIAGNOSTICS BEFORE TAB CLICK",
            )

            # ------------------------------------------------
            # CRITICAL UPDATE:
            # Explicitly activate the JavaScript-controlled tab.
            # ------------------------------------------------

            activate_international_letter_tab(page)

            print_page_diagnostics(
                page,
                heading="PAGE DIAGNOSTICS AFTER TAB CLICK",
            )

            # Read the dropdown only after clicking 국제통상.
            options = read_dropdown_options(page)

            print(
                "Destination dropdown count after tab click:",
                len(options),
            )

            if len(options) < 100:
                print(
                    "WARNING: Fewer than 100 destinations are available "
                    "after clicking 국제통상. The missing destinations "
                    "will NOT be classified as confirmed suspensions."
                )

            # -----------------------------------------------
            # Process each destination visible in the dropdown
            # -----------------------------------------------

            for index, option in enumerate(options, start=1):
                code = option["value"]
                korean_name = option["text"]

                print(
                    f"[{index}/{len(options)}] "
                    f"Checking {korean_name} ({code})"
                )

                try:
                    dropdown = select_destination_dropdown(page)
                    dropdown.select_option(value=code)

                    click_search(page)

                    notice_ko = extract_urgent_notice(page)
                    notice_en = (
                        translate_text(notice_ko)
                        if notice_ko
                        else None
                    )

                    en_name = english_name(code, korean_name)
                    number = master_number(en_name)

                    record = {
                        "code": code,
                        "korean": korean_name,
                        "english": en_name,
                        "number": number,
                        "notice_ko": notice_ko,
                        "notice_en": notice_en,
                        "suspension": is_suspension_notice(notice_ko),
                    }

                    destination_records.append(record)

                except Exception as exc:
                    error_message = (
                        f"{korean_name} ({code}): "
                        f"{type(exc).__name__}: {exc}"
                    )
                    errors.append(error_message)
                    print("WARNING:", error_message)

                time.sleep(REQUEST_DELAY_SECONDS)

        finally:
            browser.close()

    # ========================================================
    # 12. FIND UNMATCHED MASTER-LIST DESTINATIONS
    # ========================================================

    found_numbers = {
        record["number"]
        for record in destination_records
        if record["number"] is not None
    }

    missing = [
        (number, name)
        for number, name in MASTER_LIST
        if number not in found_numbers
    ]

    # ========================================================
    # 13. WRITE REPORT
    # ========================================================

    report = build_report(
        timestamp=timestamp,
        destination_records=destination_records,
        missing=missing,
        errors=errors,
        network_events=network_events,
    )

    OUTPUT_FILE.write_text(report, encoding="utf-8")

    print("\n========== RUN SUMMARY ==========")
    print("Report written to:", OUTPUT_FILE.resolve())
    print("Destinations processed:", len(destination_records))
    print("Master-list destinations not matched:", len(missing))
    print("Destination processing errors:", len(errors))
    print("Network events captured:", len(network_events))
    print("=================================\n")

    if not destination_records:
        raise RuntimeError(
            "No destinations were processed. Check the GitHub Actions log "
            "and output_korea.txt for browser diagnostics."
        )


if __name__ == "__main__":
    main()
