#!/usr/bin/env python3
"""K-Startup 사업공고 수집 -> data/kstartup/YYYY-MM-DD.json (표준 라이브러리만 사용)

- 모집 진행 중인 공고만 받아 온다.
- 서버가 느리거나 일시 오류가 나면 최대 3번까지 다시 시도한다.
- 응답 구조가 예상과 다르면 원본 앞부분을 출력하고 실패 처리한다(조용히 0건으로 끝나지 않게).
"""
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

URL = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
KEY = os.environ.get("KSTARTUP_SERVICE_KEY", "").strip()
if not KEY:
    sys.exit("KSTARTUP_SERVICE_KEY 없음")
# Secrets에 Encoding 키를 넣어도 되도록 한 번 디코딩
KEY = urllib.parse.unquote(KEY)
now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
PER_PAGE = 100
MAX_PAGES = 20


def fetch(page):
    q = {
        "serviceKey": KEY,
        "page": page,
        "perPage": PER_PAGE,
        "returnType": "json",
        "cond[rcrt_prgs_yn::EQ]": "Y",  # 모집 진행 중만
    }
    req = urllib.request.Request(
        URL + "?" + urllib.parse.urlencode(q), headers={"User-Agent": "Mozilla/5.0"}
    )
    last = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            try:
                return json.loads(raw)
            except ValueError:
                head = raw[:300].decode("utf-8", "replace")
                sys.exit(f"JSON이 아닌 응답(인증키·활용신청 상태 확인): {head}")
        except urllib.error.HTTPError as e:
            if e.code < 500:  # 401/403/404 등은 다시 해도 소용없음
                sys.exit(f"HTTP {e.code}: 인증키 또는 요청 주소를 확인하세요")
            last = e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
        print(f"(응답 지연/오류, {attempt}번째 재시도) {last}", flush=True)
        time.sleep(5 * attempt)
    sys.exit(f"3번 시도했지만 실패: {last}")


items = []
page = 1
while page <= MAX_PAGES:
    j = fetch(page)
    if "data" not in j:
        sys.exit("응답에 data 항목이 없음: " + json.dumps(j, ensure_ascii=False)[:300])
    rows = j.get("data") or []
    items += rows
    if len(rows) < PER_PAGE:
        break
    page += 1


def g(d, *ks):
    for k in ks:
        if d.get(k) not in (None, ""):
            return d[k]
    return ""


out = []
for d in items:
    region = str(g(d, "supt_regin"))
    out.append(
        {
            "id": g(d, "pbanc_sn", "id"),
            "title": g(d, "biz_pbanc_nm", "intg_pbanc_biz_nm"),
            "org": g(d, "pbanc_ntrp_nm", "sprv_inst"),
            "region": region,
            "start": g(d, "pbanc_rcpt_bgng_dt"),
            "end": g(d, "pbanc_rcpt_end_dt"),
            "target": g(d, "aply_trgt", "aply_trgt_ctnt"),
            "career": g(d, "biz_enyy"),  # 창업업력(예: 3년미만)
            "url": g(d, "detl_pg_url"),
            "gangwon": ("강원" in region) or ("전국" in region) or region == "",
        }
    )

os.makedirs("data/kstartup", exist_ok=True)
fn = f"data/kstartup/{now:%Y-%m-%d}.json"
with open(fn, "w", encoding="utf-8") as f:
    json.dump(
        {
            "generated_at": now.isoformat(),
            "date": f"{now:%Y-%m-%d}",
            "count": len(out),
            "items": out,
            # 첫 실행 때 응답 필드명이 맞는지 확인하는 용도
            "sample_raw_keys": sorted(items[0].keys()) if items else [],
            "sample_raw": items[0] if items else {},
        },
        f,
        ensure_ascii=False,
        indent=1,
    )
print(fn, len(out))
