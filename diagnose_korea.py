
#!/usr/bin/env python3
"""
Korea Post diagnostic utility
=============================
Investigates:
1. How many destination options each candidate endpoint returns.
2. Whether the endpoint returns a country table or dropdown.
3. Whether Google's public translation endpoint responds correctly.

Run:
    pip install requests beautifulsoup4
    python diagnose_korea.py
"""

from __future__ import annotations

import re
import sys
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# 1. Configuration
# ============================================================

BASE_URL = "https://ems.epost.go.kr"

CANDIDATE_URLS = {
    "Current International Letter Post page": (
        BASE_URL
        + "/front.EmsNormalAirShipSendCondition.postal"
        + "?frnMailDivcdTab=1&frnTranspPartyDivcd=2"
    ),
    "Country list candidate emsgb=1": (
        BASE_URL
        + "/front.EmsApplyGetNationCd.postal"
        + "?emsgb=1&is_return=Y&tempTrans=1"
    ),
    "Country list candidate emsgb=2": (
        BASE_URL
        + "/front.EmsApplyGetNationCd.postal"
        + "?emsgb=2&is_return=Y&tempTrans=1"
    ),
    "EMS available-country page": (
        BASE_URL + "/front.EmsApplyGetDeliveryNation.postal"
    ),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

TIMEOUT = 25

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# 2. Inspect HTML and count country entries
# ============================================================

def inspect_page(label: str, url: str) -> None:
    print("\n" + "=" * 75)
    print(label)
    print("=" * 75)
    print("Requested URL:", url)

    try:
        response = session.get(url, timeout=TIMEOUT)
        print("HTTP status:", response.status_code)
        print("Final URL:", response.url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Report all dropdowns and their option counts.
        selects = soup.find_all("select")
        print("\nDropdowns found:", len(selects))

        for index, select in enumerate(selects, start=1):
            options = [
                option
                for option in select.find_all("option")
                if (option.get("value") or "").strip()
            ]

            print(
                f"\nSELECT {index}: "
                f"name={select.get('name')!r}, "
                f"id={select.get('id')!r}, "
                f"options={len(options)}"
            )

            for option in options[:8]:
                print(
                    "  OPTION:",
                    repr(option.get("value")),
                    repr(option.get_text(" ", strip=True)),
                )

        # Report table sizes; some endpoints return a country table.
        tables = soup.find_all("table")
        print("\nTables found:", len(tables))

        for index, table in enumerate(tables, start=1):
            rows = table.find_all("tr")
            print(f"TABLE {index}: rows={len(rows)}")

            for row in rows[:4]:
                cells = row.find_all(["th", "td"])
                values = [
                    cell.get_text(" ", strip=True)
                    for cell in cells
                ]
                print("  ROW:", " | ".join(values))

        # Report form fields needed to diagnose the original request.
        print("\nForms:")
        for index, form in enumerate(soup.find_all("form"), start=1):
            print(
                f"FORM {index}: "
                f"action={form.get('action')!r}, "
                f"method={form.get('method')!r}"
            )

            for field in form.find_all("input"):
                name = field.get("name")
                if name:
                    print(
                        "  INPUT:",
                        name,
                        "=",
                        repr(field.get("value", "")),
                        "type=",
                        repr(field.get("type", "")),
                    )

        # Find references to JavaScript files that may populate the list.
        print("\nJavaScript references:")
        for tag in soup.find_all("script", src=True):
            print(" ", urljoin(response.url, tag["src"]))

        # Look for relevant endpoint names in inline scripts.
        inline_text = "\n".join(
            tag.get_text()
            for tag in soup.find_all("script")
            if not tag.get("src")
        )

        keywords = (
            "GetNation",
            "nation",
            "frnMailDivcdTab",
            "sbtn_search",
            "ajax",
        )

        print("\nRelevant inline-script lines:")
        count = 0

        for line in inline_text.splitlines():
            if any(
                keyword.lower() in line.lower()
                for keyword in keywords
            ):
                print(" ", line.strip()[:300])
                count += 1

                if count >= 20:
                    print("  ... output limited to 20 lines")
                    break

        if count == 0:
            print("  No matching inline-script lines found.")

    except Exception as exc:
        print(f"REQUEST OR PARSING ERROR: {type(exc).__name__}: {exc}")


# ============================================================
# 3. Test translation service
# ============================================================

def test_translation(text: str) -> None:
    print("\nTranslation test input:", text)

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
            timeout=TIMEOUT,
        )

        print("Translation HTTP status:", response.status_code)
        print("Translation response type:", response.headers.get(
            "Content-Type", "(unknown)"
        ))
        response.raise_for_status()

        payload = response.json()
        translated = "".join(
            str(segment[0])
            for segment in payload[0]
            if segment and segment[0]
        ).strip()

        print("Translated text:", translated or "(empty response)")

    except Exception as exc:
        print(
            "TRANSLATION ERROR:",
            f"{type(exc).__name__}: {exc}",
        )


# ============================================================
# 4. Main
# ============================================================

def main() -> None:
    print("KOREA POST DIAGNOSTICS")
    print("Python:", sys.version.split()[0])

    for label, url in CANDIDATE_URLS.items():
        inspect_page(label, url)

    print("\n" + "=" * 75)
    print("TRANSLATION SERVICE TESTS")
    print("=" * 75)

    test_translation("국제통상")
    test_translation(
        "우편 물량 및 항공 운송편에 따라 발송 및 배달이 지연될 수 있음"
    )

    print("\nDiagnostics finished.")
    print("No repository files were changed by this script.")


if __name__ == "__main__":
    main()
