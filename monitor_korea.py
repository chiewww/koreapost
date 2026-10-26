
# ============================================================
# Korea Post International Letter Post Monitor
# Output: output_korea.txt
#
# Extracts only:
#   - Destination dropdown entries
#   - The 긴급공지 section for each selected destination
#   - English translations of urgent notices
#   - Destinations missing from the live dropdown
#
# Explicitly excludes 주요안내사항.
# ============================================================

from __future__ import annotations

import re
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import pycountry
import requests
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)

# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

PAGE_URL = (
    "https://ems.epost.go.kr/front.EmsNormalAirShipSendCondition.postal"
    "?frnMailDivcdTab=1&frnTranspPartyDivcd=2"
)

OUTPUT_FILE = Path("output_korea.txt")
BROWSER_TIMEOUT_MS = 20000
SEARCH_WAIT_MS = 900
TRANSLATION_TIMEOUT_SECONDS = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    )
}

TRANSLATE_URL = "https://translate.googleapis.com/translate_a/single"

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
    "항공편 중단", "항공편 운항 중단",
    "중단되었습니다", "중지되었습니다",
    "불가합니다",
)

# ------------------------------------------------------------
# MASTER LIST: ORIGINAL POSTCROSSING NUMBERS AND NAMES
# ------------------------------------------------------------

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

    if len(result) != 248 or [n for n, _ in result] != list(range(1, 249)):
        raise ValueError("Master list validation failed; expected numbers 1–248.")

    return result


MASTER_LIST = parse_master_list()


# ------------------------------------------------------------
# COUNTRY NAME MATCHING
# ------------------------------------------------------------

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
    "republic of the congo": "congo",
    "congo brazzaville": "congo",
    "congo kinshasa": "dem rep of congo",
    "czech republic": "czechia",
    "eswatini": "eswatini swaziland",
    "swaziland": "eswatini swaziland",
    "falkland islands": "falkland islands malvinas",
    "malvinas": "falkland islands malvinas",
    "macau": "macao",
    "north korea": "korea north",
    "south korea": "korea south",
    "lao peoples democratic republic": "laos",
    "republic of moldova": "moldova",
    "burma": "myanmar",
    "nauru": "nauru naoero",
    "naoero": "nauru naoero",
    "the netherlands": "netherlands",
    "state of palestine": "palestine",
    "reunion": "reunion",
    "russian federation": "russia",
    "sao tome and principe": "sao tome and principe",
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
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.casefold().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def canonical(value: str) -> str:
    value = normalize(value)
    return ALIASES.get(value, value)


MASTER_INDEX = {canonical(name): number for number, name in MASTER_LIST}


def english_name(code: str, korean_name: str) -> str:
    code = code.upper()

    if code in CODE_NAME_OVERRIDES:
        return CODE_NAME_OVERRIDES[code]

    country = pycountry.countries.get(alpha_2=code)
    if country:
        return getattr(country, "common_name", country.name)

    return translate_text(korean_name) or korean_name


def master_number(name: str):
    return MASTER_INDEX.get(canonical(name))


# ------------------------------------------------------------
# TRANSLATION
# ------------------------------------------------------------

translation_cache = {}


def translate_text(text: str):
    """Translate Korean text; return None if translation cannot be obtained."""
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return None

    if text in translation_cache:
        return translation_cache[text]

    # Translate in chunks if necessary, avoiding oversized requests.
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

        translated_pieces = [translate_text(piece) for piece in pieces]
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
                part[0] for part in data[0] if part and part[0]
            ).strip()

            if result:
                translation_cache[text] = result
                return result

        except (requests.RequestException, ValueError, TypeError, IndexError):
            time.sleep(1.0 + attempt)

    translation_cache[text] = None
    return None


# ------------------------------------------------------------
# BROWSER HELPERS
# ------------------------------------------------------------

def select_destination_dropdown(page):
    """Find the destination select control, normally named 'nation'."""
    select = page.locator("select[name='nation']").first

    if select.count() and select.is_visible():
        return select

    candidates = page.locator("select")
    for i in range(candidates.count()):
        candidate = candidates.nth(i)
        try:
            if not candidate.is_visible():
                continue
            details = candidate.evaluate(
                "(el) => `${el.name || ''} ${el.id || ''}`.toLowerCase()"
            )
            if any(word in details for word in ("nation", "country", "dest")):
                return candidate
        except Exception:
            continue

    raise RuntimeError(
        "Could not find the destination dropdown. "
        "Korea Post may have changed the page."
    )


def read_dropdown_options(page):
    """
    Read every destination from the actual destination dropdown.
    Do not use the first select[name='nation'] blindly.
    """
    selectors = [
        "select[name='nation'][title='도착국']",
        "select[title='도착국']",
        "select[name='nation']",
    ]

    for selector in selectors:
        dropdown = page.locator(selector)

        # Skip selectors that do not identify exactly one dropdown.
        if dropdown.count() != 1:
            continue

        options = dropdown.locator("option").evaluate_all("""
            elements => elements.map(option => ({
                value: (option.value || "").trim(),
                text: (option.textContent || "").trim(),
                selected: option.selected
            }))
        """)

        # Keep real destination entries, excluding empty placeholders.
        destinations = []
        for option in options:
            value = option["value"]
            text = option["text"]

            if not value or not text:
                continue

            # Ignore common placeholder options.
            if text in ("선택", "선택하세요", "도착국 선택", "국가 선택"):
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
            print(f"  value={item['value']!r}, text={item['text']!r}")
        print("Last 10 destinations:")
        for item in destinations[-10:]:
            print(f"  value={item['value']!r}, text={item['text']!r}")

        return destinations

    raise RuntimeError(
        "Could not identify the destination dropdown "
        "(select[name='nation'][title='도착국'])."
    )

def click_search(page):
    """Click the search control after selecting a destination."""
    try:
        button = page.get_by_text("검색", exact=True).first
        button.click(timeout=5000)
        page.wait_for_timeout(SEARCH_WAIT_MS)
        return
    except PlaywrightTimeoutError:
        pass

    # Fallback for a search button implemented with an image or JS handler.
    clicked = page.evaluate(
        """() => {
            const nodes = [...document.querySelectorAll(
                'button, a, input[type="button"], input[type="submit"], img'
            )];

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
        }"""
    )

    if not clicked:
        raise RuntimeError("Could not find the Korea Post 검색 button.")

    page.wait_for_timeout(SEARCH_WAIT_MS)


def extract_urgent_notice(page) -> str:
    """
    Extract text strictly between 긴급공지 and 주요안내사항.

    This intentionally excludes 주요안내사항 and all following content.
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
        # Fail closed: if the end boundary is missing, do not accidentally
        # include the 주요안내사항 section.
        return ""

    section = body_text[start:end]
    lines = [line.strip() for line in section.splitlines()]
    lines = [line for line in lines if line]

    # Remove a standalone heading often used for shared notices.
    while lines and lines[0] in {"국가별 공통사항", "국가별공통사항"}:
        lines.pop(0)

    # Keep only the urgent notice text. Remove empty UI/navigation labels.
    ignored = {"초기화", "인쇄", "닫기", "검색", "도착국"}
    lines = [line for line in lines if line not in ignored]

    return "\n".join(lines).strip()


def is_suspension_notice(text: str) -> bool:
    return any(term in text for term in SUSPENSION_TERMS)


def select_international_letter_tab(page):
    """
    The URL requests the International Letter Post tab. Click its visible
    tab label as well when possible, in case the page defaults elsewhere.
    """
    try:
        tab = page.get_by_text("국제통상", exact=True).first
        if tab.count() and tab.is_visible():
            tab.click(timeout=3000)
            page.wait_for_timeout(500)
    except Exception:
        # The URL already requests 국제통상; continue and verify the dropdown.
        pass


# ------------------------------------------------------------
# REPORT
# ------------------------------------------------------------

def main():
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    session = requests.Session()
    session.headers.update(HEADERS)

    destination_records = []
    errors = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(locale="ko-KR")
        page.set_default_timeout(BROWSER_TIMEOUT_MS)

        try:
            print(f"Opening: {PAGE_URL}")
            page.goto(PAGE_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)
            
            print("\n========== PAGE DIAGNOSTICS ==========")
            print("Final URL:", page.url)
            print("Page title:", page.title())

            print("\nTabs and service labels:")
            for label in ["국제소포", "국제통상"]:
                locator = page.get_by_text(label, exact=True)
                print(f"{label}: count={locator.count()}")
                for i in range(locator.count()):
                    try:
                        print(
                            f"  [{i}]",
                            locator.nth(i).get_attribute("class"),
                            locator.nth(i).get_attribute("aria-selected"),
                        )
                    except Exception as exc:
                        print("  Could not inspect:", exc)

            print("\nAll select elements:")
            for i in range(page.locator("select").count()):
                item = page.locator("select").nth(i)
                print({
                    "index": i,
                    "name": item.get_attribute("name"),
                    "title": item.get_attribute("title"),
                    "id": item.get_attribute("id"),
                    "options": item.locator("option").count(),
                })

            print("======================================\n")
            
            # The URL already specifies the International Letter Post tab.
            # Do not click the tab again; doing so may change the page state.

            # Read the full dropdown before iterating. Do not filter by notice.
            options = read_dropdown_options(page)
            if len(options) < 100:
                raise RuntimeError(
                    f"Only {len(options)} destinations were read. "
                    "Refusing to generate a potentially incorrect report."
                )
            print("Raw dropdown option count:",
                  page.locator("select[name='nation'] option").count())
            print("First 10 options:",
                  page.locator("select[name='nation'] option").all_text_contents()[:10])
            print("Last 10 options:",
                  page.locator("select[name='nation'] option").all_text_contents()[-10:])
            print(f"Dropdown destinations found: {len(options)}")

            for index, (code, korean_name) in enumerate(options, start=1):
                print(
                    f"[{index}/{len(options)}] "
                    f"Selecting {korean_name} ({code})"
                )

                try:
                    dropdown = select_destination_dropdown(page)
                    dropdown.select_option(value=code)
                    click_search(page)

                    notice_ko = extract_urgent_notice(page)
                    notice_en = translate_text(notice_ko) if notice_ko else None

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
                    errors.append(
                        f"{korean_name} ({code}): {type(exc).__name__}: {exc}"
                    )
                    print(f"WARNING: {errors[-1]}")

                # Avoid sending rapid consecutive requests.
                time.sleep(0.3)

        finally:
            browser.close()

    # --------------------------------------------------------
    # Compute missing master-list destinations.
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # Write concise output.
    # --------------------------------------------------------

    lines = [
        "KOREA POST INTERNATIONAL LETTER POST MONITOR",
        f"Generated: {timestamp}",
        f"Destination dropdown count: {len(destination_records)}",
        "",
        "DESTINATIONS",
        "=" * 60,
    ]

    for record in destination_records:
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
            lines.append("긴급공지 (Korean):")
            lines.extend(record["notice_ko"].splitlines())

            lines.append("Urgent notice (English):")
            if record["notice_en"]:
                lines.append(record["notice_en"])
            else:
                lines.append(
                    "[Translation unavailable; original Korean is retained.]"
                )

        lines.append("")

    # Suspended candidates: explicit suspension wording in an urgent notice
    # OR absent from the live dropdown. Missing alone is not proof of a
    # confirmed official suspension.
    lines.extend([
        "",
        "SUSPENDED / NOT-LISTED DESTINATIONS",
        "=" * 60,
    ])

    candidates = []

    for record in destination_records:
        if record["suspension"]:
            number = record["number"]
            candidates.append({
                "number": number if number is not None else 9999,
                "line": (
                    f"#{number if number is not None else 'UNMATCHED'} | "
                    f"{record['korean']} | {record['english']} | "
                    f"code={record['code']} | urgent notice mentions "
                    "possible suspension"
                ),
            })

    for number, name in missing:
        candidates.append({
            "number": number,
            "line": (
                f"#{number} | {name} | NOT LISTED IN LIVE DROPDOWN "
                "(verify suspension)"
            ),
        })

    candidates.sort(key=lambda item: item["number"])

    for item in candidates:
        lines.append(item["line"])

    lines.append(f"TOTAL SUSPENDED / NOT-LISTED CANDIDATES: {len(candidates)}")

    if len(destination_records) <= 27:
        lines.extend([
            "",
            "WARNING",
            "The browser returned 27 or fewer destinations. Verify the tab and "
            "dropdown manually; the missing list may be incomplete.",
        ])

    if errors:
        lines.extend([
            "",
            "DESTINATIONS THAT COULD NOT BE CHECKED",
            "=" * 60,
        ])
        lines.extend(f"- {error}" for error in errors)

    lines.append("")
    lines.append("END OF REPORT")

    OUTPUT_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Report written to: {OUTPUT_FILE.resolve()}")
    print(f"Destinations processed: {len(destination_records)}")
    print(f"Missing master destinations: {len(missing)}")
    print(f"Errors: {len(errors)}")

    # Fail the workflow if the page could not be read at all.
    if not destination_records:
        raise RuntimeError(
            "No destinations were processed. Check the page interaction "
            "and the GitHub Actions log."
        )


if __name__ == "__main__":
    main()
