
# ============================================================
# Korea Post International Letter Post Monitor
# Output: output_korea.txt
#
# Features:
#   1. Reads the live Korea Post destination dropdown.
#   2. Records the original Postcrossing master-list number.
#   3. Extracts ONLY 긴급공지 (urgent notices).
#   4. Excludes 주요안내사항.
#   5. Translates urgent notices into English where possible.
#   6. Flags explicit suspension wording.
#   7. Lists master-list destinations missing from the dropdown.
#   8. Logs XHR/fetch network activity to help diagnose the dropdown.
#
# IMPORTANT:
# Missing from the dropdown does NOT prove a destination is suspended.
# ============================================================

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import pycountry
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


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
# 2. SUSPENSION WORDING
# These terms indicate possible suspension, not a legal conclusion.
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
# Original number and English name, entries 1–248.
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
    result = []

    for line in MASTER_LIST_TEXT.splitlines():
        number, name = line.split("|", 1)
        result.append((int(number), name.strip()))

    expected = list(range(1, 249))
    actual = [number for number, _ in result]

    if actual != expected:
        raise ValueError(
            "Master list validation failed: expected entries numbered 1–248."
        )

    return result


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


# ============================================================
# 5. TRANSLATION
# ============================================================

translation_cache = {}


def translate_text(text: str):
    """Translate Korean text to English. Return None on failure."""
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return None

    if text in translation_cache:
        return translation_cache[text]

    # Split very long text into smaller pieces.
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


def english_name(code: str, korean_name: str) -> str:
    """Map a Korea Post country code to a master-list English name."""
    code = (code or "").strip().upper()

    if code in CODE_NAME_OVERRIDES:
        return CODE_NAME_OVERRIDES[code]

    country = pycountry.countries.get(alpha_2=code)

    if country:
        # Use the standard country name; aliases handle many differences.
        return getattr(country, "common_name", country.name)

    return translate_text(korean_name) or korean_name


# ============================================================
# 6. NETWORK DIAGNOSTICS
# ============================================================

def attach_network_diagnostics(page, network_events):
    """
    Log browser XHR/fetch requests and their responses.

    These diagnostics help reveal whether the destination list is loaded
    dynamically. They do not change requests or page behavior.
    """

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
            try:
                content_type = response.headers.get("content-type", "")
            except Exception:
                content_type = ""

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
# 7. BROWSER HELPERS
# ============================================================

def select_destination_dropdown(page):
    """Find the destination dropdown, normally select[name='nation'].""" 
    selectors = [
        "select[name='nation'][title='도착국']",
        "select[title='도착국']",
        "select[name='nation']",
    ]

    for selector in selectors:
        locator = page.locator(selector)

        if locator.count() == 1 and locator.is_visible():
            return locator

    # Fallback: inspect all visible select elements.
    selects = page.locator("select")

    for index in range(selects.count()):
        candidate = selects.nth(index)

        try:
            if not candidate.is_visible():
                continue

            details = candidate.evaluate(
                "(el) => `${el.name || ''} ${el.id || ''} "
                "${el.title || ''}`.toLowerCase()"
            )

            if any(
                word in details
                for word in ("nation", "country", "dest", "도착국")
            ):
                return candidate

        except Exception:
            continue

    raise RuntimeError(
        "Could not find the destination dropdown. "
        "Korea Post may have changed the page."
    )


def read_dropdown_options(page):
    """
    Read destination options from the live dropdown.
    Placeholder entries are excluded.
    """
    selectors = [
        "select[name='nation'][title='도착국']",
        "select[title='도착국']",
        "select[name='nation']",
    ]

    for selector in selectors:
        dropdown = page.locator(selector)

        if dropdown.count() != 1:
            continue

        options = dropdown.locator("option").evaluate_all("""
            elements => elements.map(option => ({
                value: (option.value || "").trim(),
                text: (option.textContent || "").trim(),
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

        print(f"Dropdown selector used: {selector}")
        print(f"Raw option count: {len(options)}")
        print(f"Destination option count: {len(destinations)}")

        print("First 10 destinations:")
        for item in destinations[:10]:
            print(
                f"  value={item['value']!r}, "
                f"text={item['text']!r}"
            )

        print("Last 10 destinations:")
        for item in destinations[-10:]:
            print(
                f"  value={item['value']!r}, "
                f"text={item['text']!r}"
            )

        return destinations

    raise RuntimeError(
        "Could not identify the destination dropdown "
        "(select[name='nation'][title='도착국'])."
    )


def click_search(page):
    """Click the Korea Post search control."""
    try:
        button = page.get_by_text("검색", exact=True).first

        if button.count() and button.is_visible():
            button.click(timeout=5000)
            page.wait_for_timeout(SEARCH_WAIT_MS)
            return

    except (PlaywrightTimeoutError, Exception):
        pass

    # Fallback for buttons, links, inputs, or image-based controls.
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
    risk accidentally including 주요안내사항.
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

    # Remove standalone headings and UI labels.
    while lines and lines[0] in {
        "국가별 공통사항",
        "국가별공통사항",
    }:
        lines.pop(0)

    ignored = {
        "초기화",
        "인쇄",
        "닫기",
        "검색",
        "도착국",
    }

    lines = [
        line for line in lines
        if line not in ignored
    ]

    return "\n".join(lines).strip()


def is_suspension_notice(text: str) -> bool:
    return any(term in text for term in SUSPENSION_TERMS)


def print_page_diagnostics(page):
    """Print page, tab, and select-element information."""
    print("\n========== PAGE DIAGNOSTICS ==========")
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
                    "class=", item.get_attribute("class"),
                    "aria-selected=", item.get_attribute("aria-selected"),
                )
            except Exception as exc:
                print("  Could not inspect:", exc)

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
            print(f"  Select {index} inspection failed: {exc}")

    print("======================================\n")


# ============================================================
# 8. REPORT HELPERS
# ============================================================

def format_destination_line(record):
    number = (
        f"#{record['number']}"
        if record["number"] is not None
        else "#UNMATCHED"
    )

    return (
        f"{number} | {record['korean']} | "
        f"{record['english']} | code={record['code']}"
    )


def build_report(timestamp, destination_records, missing, errors, network_events):
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

    # Possible suspensions are separated from unlisted destinations.
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
                f"{number} | {record['korean']} | {record['english']} | "
                f"code={record['code']} | urgent notice contains "
                "possible suspension wording"
            )
            if record["notice_ko"]:
                lines.append(f"  Korean: {record['notice_ko']}")
            if record["notice_en"]:
                lines.append(f"  English: {record['notice_en']}")
    else:
        lines.append("No urgent notices matched the configured terms.")

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

    lines.extend([
        "",
        "IMPORTANT INTERPRETATION",
        "=" * 60,
        "A destination absent from the observed dropdown is not confirmed "
        "suspended by that fact alone.",
        "Suspension wording is a candidate indicator and should be checked "
        "against the full official notice and applicable service rules.",
        "This report extracts only 긴급공지. It intentionally excludes "
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
            "The observed dropdown may be incomplete, may be in a different "
            "page state, or may be populated dynamically.",
            "Do not treat the unmatched master-list destinations as confirmed "
            "suspensions.",
        ])

    if errors:
        lines.extend([
            "",
            "DESTINATIONS THAT COULD NOT BE CHECKED",
            "=" * 60,
        ])
        lines.extend(f"- {error}" for error in errors)

    lines.extend([
        "",
        "BROWSER NETWORK DIAGNOSTICS",
        "=" * 60,
        "XHR/fetch requests and responses observed during this run:",
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
            "No XHR/fetch events were captured. The page may use other "
            "resource types or load its options in the initial HTML."
        )

    lines.extend([
        "",
        "END OF REPORT",
    ])

    return "\n".join(lines) + "\n"


# ============================================================
# 9. MAIN
# ============================================================

def main():
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

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

        attach_network_diagnostics(page, network_events)

        try:
            print(f"Opening: {PAGE_URL}")

            page.goto(
                PAGE_URL,
                wait_until="domcontentloaded",
                timeout=BROWSER_TIMEOUT_MS,
            )

            page.wait_for_timeout(INITIAL_PAGE_WAIT_MS)
            print_page_diagnostics(page)

            # Do not click the 국제통상 label automatically.
            # The URL already requests that tab; clicking it may alter
            # the page state or switch to a different service.

            options = read_dropdown_options(page)

            print("Dropdown destinations found:", len(options))

            if len(options) < 100:
                print(
                    "WARNING: The live dropdown has fewer than 100 "
                    "destinations. This does not establish that the other "
                    "destinations are suspended."
                )

            # Snapshot the live dropdown before changing the selection.
            for index, option in enumerate(options, start=1):
                code = option["value"]
                korean_name = option["text"]

                print(
                    f"[{index}/{len(options)}] "
                    f"Selecting {korean_name} ({code})"
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
    # 10. FIND MASTER-LIST DESTINATIONS NOT MATCHED
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
    # 11. WRITE REPORT
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
    print("Destination errors:", len(errors))
    print("Network events captured:", len(network_events))
    print("=================================\n")

    # Fail the workflow if no destinations could be processed.
    if not destination_records:
        raise RuntimeError(
            "No destinations were processed. Check the GitHub Actions log "
            "and the browser diagnostics in this run."
        )


if __name__ == "__main__":
    main()
