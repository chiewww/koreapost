#!/usr/bin/env python3
"""
koreapost - Daily monitor of the Korea Post EMS "service condition" page.

Writes a plain-text report to  output_korea.txt  containing:
  * every country in the 도착국 dropdown (Postcrossing #, Korean, English, 긴급공지 in KO + EN)
  * the total number of dropdown countries
  * the list of suspended countries (A: urgent notice mentions suspension, B: missing from dropdown)
  * the total number of suspended countries

Run:  python scrape_korea.py
Needs: pip install playwright deep-translator  &&  playwright install --with-deps chromium
"""

import json
import os
import re
import sys
import time

URL = "https://ems.epost.go.kr/front.EmsNormalAirShipSendCondition.postal"
OUTPUT_FILE = "output_korea.txt"
CACHE_FILE = "translation_cache.json"
DEBUG_FILE = "debug_page.html"

# --------------------------------------------------------------------------
# MASTER LIST OF 248 DESTINATIONS
# Format:  Postcrossing#|English name|ISO code|Korean name(s) separated by /
# (extra Korean spellings are aliases used only for matching the dropdown)
# --------------------------------------------------------------------------
MASTER_RAW = """
1|Afghanistan|AF|아프가니스탄
2|Åland Islands|AX|올란드제도/올란드
3|Albania|AL|알바니아
4|Algeria|DZ|알제리
5|American Samoa|AS|미국령사모아/아메리칸사모아
6|Andorra|AD|안도라
7|Angola|AO|앙골라
8|Anguilla|AI|앵귈라
9|Antarctica|AQ|남극/프랑스(프랑스령동남및남극권)/프랑스령동남및남극권
10|Antigua & Barbuda|AG|앤티가바부다/안티구아바부다
11|Argentina|AR|아르헨티나
12|Armenia|AM|아르메니아
13|Aruba|AW|아루바
14|Australia|AU|호주/오스트레일리아
15|Austria|AT|오스트리아
16|Azerbaijan|AZ|아제르바이잔
17|Bahamas|BS|바하마
18|Bahrain|BH|바레인
19|Bangladesh|BD|방글라데시
20|Barbados|BB|바베이도스
21|Belarus|BY|벨라루스
22|Belgium|BE|벨기에
23|Belize|BZ|벨리즈
24|Benin|BJ|베냉
25|Bermuda|BM|버뮤다/버뮤다섬
26|Bhutan|BT|부탄
27|Bolivia|BO|볼리비아
28|Bonaire, Sint Eustatius and Saba|BQ|보네르/보네르신트외스타티위스사바
29|Bosnia-Herzegovina|BA|보스니아헤르체고비나/보스니아
30|Botswana|BW|보츠와나
31|Brazil|BR|브라질
32|British Indian Ocean Territory|IO|영국령인도양지역/영국령인도양식민지
33|Brunei|BN|브루나이
34|Bulgaria|BG|불가리아
35|Burkina Faso|BF|부르키나파소
36|Burundi|BI|부룬디
37|Cabo Verde|CV|카보베르데/까보베르데
38|Cambodia|KH|캄보디아
39|Cameroon|CM|카메룬
40|Canada|CA|캐나다
41|Cayman Islands|KY|케이맨제도/케이먼제도
42|Central African Republic|CF|중앙아프리카공화국/중앙아프리카
43|Chad|TD|차드
44|Chile|CL|칠레
45|China|CN|중국
46|Christmas Island|CX|크리스마스섬
47|Cocos Islands|CC|코코스제도/코코스섬/코코스(킬링)제도
48|Colombia|CO|콜롬비아
49|Comoros|KM|코모로
50|Congo|CG|콩고/콩고공화국
51|Dem. Rep. Of Congo|CD|콩고민주공화국/민주콩고/콩고민주
52|Cook Islands|CK|쿡제도
53|Costa Rica|CR|코스타리카
54|Côte d'Ivoire|CI|코트디부아르/코트디브와르/코트디보아르
55|Croatia|HR|크로아티아
56|Cuba|CU|쿠바
57|Curaçao|CW|퀴라소/큐라소
58|Cyprus|CY|키프로스
59|Czechia|CZ|체코/체코공화국
60|Denmark|DK|덴마크
61|Djibouti|DJ|지부티
62|Dominica|DM|도미니카연방/도미니카
63|Dominican Republic|DO|도미니카공화국
64|Ecuador|EC|에콰도르
65|Egypt|EG|이집트
66|El Salvador|SV|엘살바도르
67|Equatorial Guinea|GQ|적도기니
68|Eritrea|ER|에리트레아
69|Estonia|EE|에스토니아
70|Eswatini /Swaziland|SZ|에스와티니/스와질란드/스와지랜드
71|Ethiopia|ET|에티오피아
72|Falkland Islands /Malvinas|FK|포클랜드제도/포클랜드/말비나스
73|Faroe Islands|FO|페로제도/페로군도
74|Fiji|FJ|피지
75|Finland|FI|핀란드
76|France|FR|프랑스
77|French Guiana|GF|프랑스령기아나/프랑스령가이아나
78|French Polynesia|PF|프랑스령폴리네시아
79|French Southern Territories|TF|프랑스령남방지역/프랑스령남방및남극지역
80|Gabon|GA|가봉
81|Gambia|GM|감비아
82|Georgia|GE|조지아/그루지야
83|Germany|DE|독일
84|Ghana|GH|가나
85|Gibraltar|GI|지브롤터
86|Greece|GR|그리스
87|Greenland|GL|그린란드
88|Grenada|GD|그레나다
89|Guadeloupe|GP|과들루프
90|Guam|GU|괌
91|Guatemala|GT|과테말라
92|Guernsey|GG|건지/건지섬
93|Guinea|GN|기니
94|Guinea-Bissau|GW|기니비사우
95|Guyana|GY|가이아나
96|Haiti|HT|아이티
97|Honduras|HN|온두라스
98|Hong Kong|HK|홍콩
99|Hungary|HU|헝가리
100|Iceland|IS|아이슬란드
101|India|IN|인도
102|Indonesia|ID|인도네시아
103|Iran|IR|이란
104|Iraq|IQ|이라크
105|Ireland|IE|아일랜드
106|Isle of Man|IM|맨섬/맨
107|Israel|IL|이스라엘
108|Italy|IT|이탈리아
109|Jamaica|JM|자메이카
110|Japan|JP|일본
111|Jersey|JE|저지/저지섬
112|Jordan|JO|요르단
113|Kazakhstan|KZ|카자흐스탄
114|Kenya|KE|케냐
115|Kiribati|KI|키리바시
116|Korea(North)|KP|북한/조선민주주의인민공화국
117|Korea(South)|KR|한국/대한민국
118|Kosovo|XK|코소보
119|Kuwait|KW|쿠웨이트
120|Kyrgyzstan|KG|키르기스스탄/키르기즈스탄
121|Laos|LA|라오스
122|Latvia|LV|라트비아
123|Lebanon|LB|레바논
124|Lesotho|LS|레소토
125|Liberia|LR|라이베리아
126|Libya|LY|리비아
127|Liechtenstein|LI|리히텐슈타인
128|Lithuania|LT|리투아니아
129|Luxembourg|LU|룩셈부르크
130|Macao|MO|마카오
131|Madagascar|MG|마다가스카르
132|Malawi|MW|말라위
133|Malaysia|MY|말레이시아
134|Maldives|MV|몰디브
135|Mali|ML|말리
136|Malta|MT|몰타
137|Marshall Islands|MH|마셜제도/마샬제도
138|Martinique|MQ|마르티니크
139|Mauritania|MR|모리타니/모리타니아
140|Mauritius|MU|모리셔스
141|Mayotte|YT|마요트
142|Mexico|MX|멕시코
143|Micronesia|FM|미크로네시아
144|Moldova|MD|몰도바
145|Monaco|MC|모나코
146|Mongolia|MN|몽골
147|Montenegro|ME|몬테네그로
148|Montserrat|MS|몬트세랫/몬트세라트
149|Morocco|MA|모로코
150|Mozambique|MZ|모잠비크
151|Myanmar|MM|미얀마
152|Namibia|NA|나미비아
153|Nauru / Naoero|NR|나우루
154|Nepal|NP|네팔
155|Netherlands|NL|네덜란드
156|New Caledonia|NC|뉴칼레도니아
157|New Zealand|NZ|뉴질랜드
158|Nicaragua|NI|니카라과
159|Niger|NE|니제르
160|Nigeria|NG|나이지리아
161|Niue|NU|니우에
162|Norfolk Island|NF|노퍽섬/노퍽/노폭섬
163|Northern Mariana Islands|MP|북마리아나제도/북마리아나
164|North Macedonia|MK|북마케도니아/마케도니아
165|Norway|NO|노르웨이
166|Oman|OM|오만
167|Pakistan|PK|파키스탄
168|Palau|PW|팔라우
169|Palestine|PS|팔레스타인
170|Panama|PA|파나마
171|Papua New Guinea|PG|파푸아뉴기니
172|Paraguay|PY|파라과이
173|Peru|PE|페루
174|Philippines|PH|필리핀
175|Pitcairn|PN|핏케언제도/핏케언/핏케언섬
176|Poland|PL|폴란드
177|Portugal|PT|포르투갈
178|Puerto Rico|PR|푸에르토리코
179|Qatar|QA|카타르
180|Réunion|RE|레위니옹/레위니옹섬
181|Romania|RO|루마니아
182|Russia|RU|러시아
183|Rwanda|RW|르완다
184|Saint Barthélemy|BL|생바르텔레미
185|Saint Helena, Ascension and Tristan da Cunha|SH|세인트헬레나/세인트헬레나어센션트리스탄다쿠냐
186|Saint Kitts and Nevis|KN|세인트키츠네비스/세인트크리스토퍼네비스
187|Saint Lucia|LC|세인트루시아
188|Saint Martin|MF|생마르탱
189|Saint Pierre & Miquelon|PM|생피에르미클롱/생피에르미켈롱
190|Saint Vincent and the Grenadines|VC|세인트빈센트그레나딘/세인트빈센트
191|Samoa|WS|사모아/서사모아
192|San Marino|SM|산마리노
193|Sao Tome and Principe|ST|상투메프린시페
194|Saudi Arabia|SA|사우디아라비아
195|Senegal|SN|세네갈
196|Serbia|RS|세르비아
197|Seychelles|SC|세이셸
198|Sierra Leone|SL|시에라리온
199|Singapore|SG|싱가포르
200|Sint Maarten|SX|신트마르턴
201|Slovakia|SK|슬로바키아
202|Slovenia|SI|슬로베니아
203|Solomon Islands|SB|솔로몬제도
204|Somalia|SO|소말리아
205|South Africa|ZA|남아프리카공화국/남아공
206|South Georgia and S. Sandwich Islands|GS|사우스조지아/사우스조지아사우스샌드위치제도
207|South Sudan|SS|남수단
208|Spain|ES|스페인
209|Sri Lanka|LK|스리랑카
210|Sudan|SD|수단
211|Suriname|SR|수리남
212|Svalbard and Jan Mayen|SJ|스발바르/스발바르얀마옌
213|Sweden|SE|스웨덴
214|Switzerland|CH|스위스
215|Syria|SY|시리아
216|Taiwan|TW|대만
217|Tajikistan|TJ|타지키스탄
218|Tanzania|TZ|탄자니아
219|Thailand|TH|태국
220|Timor-Leste|TL|동티모르/티모르레스테
221|Togo|TG|토고
222|Tokelau|TK|토켈라우
223|Tonga|TO|통가
224|Trinidad and Tobago|TT|트리니다드토바고
225|Tunisia|TN|튀니지
226|Turkey|TR|튀르키예/튀르키에/터키
227|Turkmenistan|TM|투르크메니스탄/투르크메니스탄
228|Turks and Caicos Islands|TC|터크스케이커스제도/터크스케이커스
229|Tuvalu|TV|투발루
230|Uganda|UG|우간다
231|Ukraine|UA|우크라이나
232|United Arab Emirates|AE|아랍에미리트/아랍에미리트연합
233|United Kingdom|GB|영국
234|Uruguay|UY|우루과이
235|U.S.A.|US|미국
236|U.S. Minor Outlying Islands|UM|미국령소군도/미국령군소제도
237|Uzbekistan|UZ|우즈베키스탄
238|Vanuatu|VU|바누아투
239|Vatican|VA|바티칸/바티칸시국
240|Venezuela|VE|베네수엘라
241|Vietnam|VN|베트남
242|Virgin Islands (UK)|VG|영국령버진아일랜드/영국령버진제도
243|Virgin Islands of the USA|VI|미국령버진아일랜드/미국령버진제도
244|Wallis & Futuna|WF|왈리스푸투나/월리스푸투나
245|Western Sahara|EH|서사하라
246|Yemen|YE|예멘
247|Zambia|ZM|잠비아
248|Zimbabwe|ZW|짐바브웨
"""

# Words in the 긴급공지 text that mean "service suspended / route unavailable / no service"
SUSPEND_KO = re.compile(r"중단|중지|불가|정지|폐쇄|운휴|없습니다|제한")
SUSPEND_EN = re.compile(
    r"suspen|unavailable|not available|no service|cannot|can not|halt|discontinu|"
    r"stopp|ceas|closed|not accepted|no route|not possible|impossible",
    re.I,
)
# 긴급공지 values that mean "nothing written"
EMPTY_NOTICES = {"", "-", "--", "없음", "해당없음", "해당 없음", "none", "null", "n/a"}
# Placeholder texts. These must NEVER be run through the suspension check
# (the old bug: "(translation unavailable)" contains the word "unavailable").
TRANSLATION_FAILED = "(translation unavailable)"
NOTICE_READ_FAILED = "(could not read page)"


# --------------------------------------------------------------------------
# Master list helpers
# --------------------------------------------------------------------------
def load_master():
    master = []
    for line in MASTER_RAW.strip().splitlines():
        num, eng, iso, kor = line.split("|")
        names = [k for k in kor.split("/") if k]
        master.append({"num": int(num), "en": eng, "iso": iso, "ko": names[0], "aliases": names})
    assert len(master) == 248, f"master list has {len(master)} rows, expected 248"
    return master


def norm_ko(s):
    return re.sub(r"[\s·・\-_.,'’]", "", s or "")


# Parent countries that appear in parentheses after a territory's name, e.g. "버뮤다섬(영국)".
# The text inside those parentheses is the PARENT country, not the territory itself,
# so it must never be used to identify the entry.
PARENT_STATES = {
    "영국", "프랑스", "미국", "네덜란드", "호주", "뉴질랜드", "덴마크",
    "노르웨이", "중국", "포르투갈", "스페인", "핀란드", "칠레", "에콰도르",
}


def ko_candidates(name):
    """'터키(튀르키예)'  -> (['터키(튀르키예)', '터키', '튀르키예'], [])
       '버뮤다섬(영국)'  -> (['버뮤다섬(영국)', '버뮤다섬'], ['영국'])   # 영국 is only a parent hint"""
    full = norm_ko(name)
    outside = norm_ko(re.sub(r"\(.*?\)", "", name))
    inside = [norm_ko(i) for i in re.findall(r"\((.*?)\)", name) if norm_ko(i)]
    parents = [i for i in inside if i in PARENT_STATES]
    alt_names = [i for i in inside if i not in PARENT_STATES]
    seen, result = set(), []
    for c in [full, outside] + alt_names:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result, parents


def name_score(ko, m):
    """How exactly a dropdown name matches a master entry (2 = primary name, 1 = alias, 0 = other)."""
    n = norm_ko(ko)
    if n == norm_ko(m["ko"]):
        return 2
    if n in {norm_ko(a) for a in m["aliases"]}:
        return 1
    return 0


def build_indexes(master):
    by_alias, by_iso = {}, {}
    for m in master:
        by_iso[m["iso"]] = m
        for a in m["aliases"]:
            by_alias.setdefault(norm_ko(a), m)
    return by_alias, by_iso


def match_master(ko_name, option_value, by_alias, by_iso, master):
    cands, parents = ko_candidates(ko_name)
    # 1) exact Korean (or alias) match
    for c in cands:
        if c in by_alias:
            return by_alias[c]
    # 2) option value is an ISO country code
    code = (option_value or "").strip().upper()
    if code in by_iso:
        return by_iso[code]
    # 3) unique partial match (only for reasonably long names)
    hits = set()
    for c in cands:
        if len(c) < 3:
            continue
        for m in master:
            for a in m["aliases"]:
                na = norm_ko(a)
                if len(na) >= 3 and (na in c or c in na):
                    hits.add(m["num"])
    # several partial hits, e.g. "버진아일랜드(영국)": use the parent country to pick the right one
    if len(hits) > 1 and parents:
        narrowed = {
            m["num"]
            for m in master
            if m["num"] in hits and any(p in norm_ko(a) for p in parents for a in m["aliases"])
        }
        if len(narrowed) == 1:
            hits = narrowed
    if len(hits) == 1:
        num = hits.pop()
        return next(m for m in master if m["num"] == num)
    return None


# --------------------------------------------------------------------------
# Translation (cached so the output file stays stable day to day)
# --------------------------------------------------------------------------
_cache = {}


def load_cache():
    global _cache
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, encoding="utf-8") as f:
                _cache = json.load(f)
        except Exception:
            _cache = {}


def save_cache():
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_cache, f, ensure_ascii=False, indent=0, sort_keys=True)


_fail_streak = 0  # consecutive texts that no translator could handle


def _google(chunk):
    from deep_translator import GoogleTranslator

    return GoogleTranslator(source="ko", target="en").translate(chunk)


def _mymemory(chunk):
    from deep_translator import MyMemoryTranslator

    return MyMemoryTranslator(source="ko-KR", target="en-US").translate(chunk)


def _translate_chunks(text, fn, size):
    parts = []
    for i in range(0, len(text), size):
        part = fn(text[i : i + size])
        if not part or not part.strip():
            raise RuntimeError("empty translation returned")
        parts.append(part.strip())
    return " ".join(parts)


def to_english(text):
    """Korean -> English. Tries Google, then MyMemory; paced and retried. Cached on success."""
    global _fail_streak
    text = (text or "").strip()
    if not text:
        return ""
    if text in _cache:
        return _cache[text]
    if _fail_streak >= 3:  # translators are clearly blocked: don't waste the run's time
        return TRANSLATION_FAILED
    for label, fn, size in (("google", _google, 4500), ("mymemory", _mymemory, 450)):
        for attempt in range(2):
            try:
                out = _translate_chunks(text, fn, size)
                _cache[text] = out
                _fail_streak = 0
                time.sleep(0.4)  # be gentle with the free endpoints
                return out
            except Exception as e:
                print(f"  [{label} attempt {attempt + 1} failed: {type(e).__name__}: {e}]", file=sys.stderr)
                time.sleep(1.5 * (attempt + 1))
    _fail_streak += 1
    return TRANSLATION_FAILED


# --------------------------------------------------------------------------
# Scraping with Playwright
# --------------------------------------------------------------------------
JS_GET_NOTICE = """
() => {
  // Page layout (from the real HTML):
  //   <div class="title_wrap"><h4>긴급공지</h4><a id="pop_commlimit">국가별 공통사항</a></div>
  //   <textarea readonly>...the notice text...</textarea>
  const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
  const heads = Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,strong,span,th,dt,label'))
    .filter(el => clean(el.textContent) === '긴급공지');
  const visible = heads.filter(el => el.offsetParent !== null);
  const pool = visible.length ? visible : heads;
  for (const h of pool) {
    const wrap = h.closest('.title_wrap') || h.parentElement;
    // the notice is the textarea that follows the title block
    let n = wrap.nextElementSibling;
    for (let i = 0; n && i < 5; i++, n = n.nextElementSibling) {
      const ta = n.tagName === 'TEXTAREA' ? n : n.querySelector('textarea');
      if (ta) return clean(ta.value || ta.textContent);
    }
    // fallback: first textarea after the heading in document order
    const after = Array.from(document.querySelectorAll('textarea'))
      .find(t => h.compareDocumentPosition(t) & Node.DOCUMENT_POSITION_FOLLOWING);
    if (after) return clean(after.value || after.textContent);
    return '';  // heading found, but no text box: treat as "no notice"
  }
  return null;  // the 긴급공지 section is not on the page at all
}
"""

JS_OPTIONS = "s => Array.from(s.options).map(o => [o.value, (o.textContent||'').trim()])"


def dump_debug(page, why):
    try:
        html = page.content()
        with open(DEBUG_FILE, "w", encoding="utf-8") as f:
            f.write(f"<!-- {why} -->\n" + html)
        for fr in page.frames[1:]:
            with open(DEBUG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n<!-- FRAME {fr.url} -->\n" + fr.content())
    except Exception as e:
        print("could not write debug file:", e, file=sys.stderr)


def click_intl_tab(page):
    selectors = [
        "div.btn.n2 a[title='탭이동']",
        "div.btn.n2 a",
        "a[title='탭이동']:has-text('국제통상')",
    ]
    for sel in selectors:
        for fr in page.frames:
            try:
                loc = fr.locator(sel).first
                if loc.count():
                    loc.click(timeout=5000)
                    page.wait_for_timeout(800)
                    return True
            except Exception:
                continue
    for fr in page.frames:
        try:
            fr.get_by_text("국제통상", exact=True).first.click(timeout=5000)
            page.wait_for_timeout(800)
            return True
        except Exception:
            continue
    return False


def find_country_select(page):
    """Return (frame, locator, options) for the visible <select> holding the country list."""
    best = None
    for fr in page.frames:
        try:
            selects = fr.locator("select")
            for i in range(selects.count()):
                sel = selects.nth(i)
                opts = sel.evaluate(JS_OPTIONS)
                texts = [t for _, t in opts]
                if len(opts) < 50 or not any("일본" in t for t in texts):
                    continue
                visible = sel.is_visible()
                score = (visible, len(opts))
                if best is None or score > best[0]:
                    best = (score, fr, sel, opts)
        except Exception:
            continue
    if best is None:
        return None
    return best[1], best[2], best[3]


def click_search(fr):
    for sel in ["#sbtn_search", "a#sbtn_search", "a:has-text('검색')", "button:has-text('검색')"]:
        try:
            loc = fr.locator(sel).first
            if loc.count() and loc.is_visible():
                loc.click(timeout=5000)
                return True
        except Exception:
            continue
    return False


def is_placeholder(value, text):
    t = text.replace(" ", "")
    return (not value.strip()) or t in ("선택", "국가선택", "도착국선택", "--선택--", "선택하세요", "전체") or "선택" in t and len(t) <= 8


def scrape():
    from playwright.sync_api import sync_playwright

    results = []  # list of (option_value, korean_name, notice_ko)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        )
        page = ctx.new_page()
        page.set_default_timeout(20000)
        page.on("dialog", lambda d: d.accept())  # "no result" alerts etc.

        def prepare():
            page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=60000)
            if not click_intl_tab(page):
                dump_debug(page, "international tab not found")
                raise RuntimeError("Could not click the 국제통상 tab")
            found = find_country_select(page)
            if not found:
                dump_debug(page, "country select not found")
                raise RuntimeError("Could not find the 도착국 dropdown (<select> with country options)")
            return found

        fr, sel, opts = prepare()
        countries = [(v, t) for v, t in opts if not is_placeholder(v, t)]
        print(f"Found {len(countries)} countries in the dropdown")
        if len(countries) < 50:
            dump_debug(page, "too few countries")
            raise RuntimeError(f"Only {len(countries)} countries found - something is wrong")

        for idx, (value, name) in enumerate(countries, 1):
            notice = None
            for attempt in range(3):
                try:
                    # make sure the tab/select are still alive (page may reload after a search)
                    try:
                        alive = sel.is_visible()
                    except Exception:
                        alive = False
                    if not alive:
                        fr, sel, _ = prepare()
                    sel.select_option(value=value)
                    if not click_search(fr):
                        raise RuntimeError("검색 button not found")
                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                    except Exception:
                        pass
                    page.wait_for_timeout(1000)  # let the results (and the notice box) refresh
                    # the page may have re-rendered: find frame again if needed
                    got = None
                    for f in page.frames:
                        try:
                            got = f.evaluate(JS_GET_NOTICE)
                            if got is not None:
                                break
                        except Exception:
                            continue
                    if got is None:
                        raise RuntimeError("긴급공지 section not found on the page")
                    notice = got
                    break
                except Exception as e:
                    print(f"  retry {attempt + 1} for {name}: {e}", file=sys.stderr)
                    try:
                        fr, sel, _ = prepare()
                    except Exception as e2:
                        print(f"  prepare failed: {e2}", file=sys.stderr)
                        time.sleep(2)
            if notice is None:
                notice = NOTICE_READ_FAILED
            if notice.strip().lower() in EMPTY_NOTICES:
                notice = ""
            results.append((value, name, notice))
            print(f"[{idx}/{len(countries)}] {name}: {notice[:60] if notice else '-'}")
        browser.close()
    return results


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------
def build_report(results):
    master = load_master()
    by_alias, by_iso = build_indexes(master)

    matched = {}  # master num -> dict
    unmatched = []  # dropdown entries that match nothing in the master list
    duplicates = []  # dropdown entries that landed on a master entry that is already taken
    for pos, (value, ko, notice) in enumerate(results):  # pos = position in the dropdown
        m = match_master(ko, value, by_alias, by_iso, master)
        if notice == NOTICE_READ_FAILED:
            notice_en = NOTICE_READ_FAILED  # English placeholder: nothing to translate
        else:
            notice_en = to_english(notice) if notice else ""
        entry = {"value": value, "ko": ko, "notice_ko": notice, "notice_en": notice_en, "order": pos}
        if m:
            entry["m"] = m
            old = matched.get(m["num"])
            if old is None:
                matched[m["num"]] = entry
            else:
                # two dropdown rows hit the same master row: keep the better name match
                # (on a tie, keep the one that has a notice), and LIST the other one - never drop it silently
                s_new, s_old = name_score(ko, m), name_score(old["ko"], m)
                if s_new > s_old or (s_new == s_old and notice and not old["notice_ko"]):
                    matched[m["num"]] = entry
                    duplicates.append(old)
                else:
                    duplicates.append(entry)
        else:
            entry["en"] = to_english(ko)
            unmatched.append(entry)

    def is_suspended_notice(e):
        ko, en = e["notice_ko"], e["notice_en"]
        if not ko or ko == NOTICE_READ_FAILED:
            return False
        # the Korean text is the primary check; the English only counts when it is a real translation
        en_is_real = bool(en) and en not in (TRANSLATION_FAILED, NOTICE_READ_FAILED)
        return bool(SUSPEND_KO.search(ko) or (en_is_real and SUSPEND_EN.search(en)))

    missing = [m for m in master if m["num"] not in matched]
    suspended_a = [e for e in matched.values() if is_suspended_notice(e)]
    suspended_a += [e for e in unmatched if is_suspended_notice(e)]
    suspended_a.sort(key=lambda e: e["order"])  # same order as the dropdown

    out = []
    w = out.append
    w("KOREA POST EMS - SERVICE CONDITION MONITOR")
    w(f"Source: {URL}")
    w("")
    w(f"TOTAL COUNTRIES IN 도착국 DROPDOWN: {len(results)}")
    w(f"TOTAL SUSPENDED COUNTRIES: {len(suspended_a) + len(missing)}")
    w(f"   (A: urgent notice mentions suspension = {len(suspended_a)}, "
      f"B: missing from dropdown = {len(missing)})")
    w("")
    w("=" * 70)
    w("SECTION 1: ALL COUNTRIES IN THE 도착국 DROPDOWN")
    w("=" * 70)
    for e in sorted(matched.values(), key=lambda x: x["order"]):  # dropdown order
        m = e["m"]
        w(f"[{m['num']}] {e['ko']} | {m['en']}")
        if e["notice_ko"]:
            w(f"    긴급공지 (KO): {e['notice_ko']}")
            w(f"    Urgent notice (EN): {e['notice_en']}")
    if unmatched:
        w("")
        w("--- Dropdown entries NOT found in the master list (check spelling/aliases) ---")
        for e in sorted(unmatched, key=lambda x: x["order"]):
            w(f"[?] {e['ko']} | {e['en']}")
            if e["notice_ko"]:
                w(f"    긴급공지 (KO): {e['notice_ko']}")
                w(f"    Urgent notice (EN): {e['notice_en']}")
    if duplicates:
        w("")
        w("--- Dropdown entries that map to a master entry already used (check the mapping) ---")
        for e in sorted(duplicates, key=lambda x: x["order"]):
            w(f"[{e['m']['num']}] {e['ko']} | {e['m']['en']}  (duplicate, not counted above)")
            if e["notice_ko"]:
                w(f"    긴급공지 (KO): {e['notice_ko']}")
                w(f"    Urgent notice (EN): {e['notice_en']}")
    w("")
    w("=" * 70)
    w("SECTION 2: SUSPENDED COUNTRIES")
    w("=" * 70)
    w("")
    w(f"--- A) Urgent notice mentions suspension / route unavailable / no service ({len(suspended_a)}) ---")
    for e in suspended_a:
        if "m" in e:
            w(f"[{e['m']['num']}] {e['ko']} | {e['m']['en']}")
        else:
            w(f"[?] {e['ko']} | {e['en']}")
        w(f"    긴급공지 (KO): {e['notice_ko']}")
        w(f"    Urgent notice (EN): {e['notice_en']}")
    w("")
    w(f"--- B) In master list of 248 but missing from the dropdown ({len(missing)}) ---")
    for m in missing:
        w(f"[{m['num']}] {m['ko']} | {m['en']}")
    w("")
    w(f"TOTAL SUSPENDED COUNTRIES: {len(suspended_a) + len(missing)}")
    w("")
    return "\n".join(out)


def main():
    load_cache()
    try:
        results = scrape()
    except Exception as e:
        print(f"SCRAPE FAILED: {e}", file=sys.stderr)
        sys.exit(1)  # leave the previous output file untouched
    report = build_report(results)
    save_cache()
    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        f.write(report)
    print(f"Wrote {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
