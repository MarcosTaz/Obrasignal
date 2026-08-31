#!/usr/bin/env python3
"""Run the UK daily Contracts Finder extractor across August, treating S3 403 as an absent day."""
from __future__ import annotations
import urllib.request, urllib.error
from datetime import date
import build_uk_contracts_finder_daily_csv as m


def tolerant_get(url: str) -> bytes:
    req=urllib.request.Request(url,headers={
        'User-Agent':'Mozilla/5.0 ObraSignal-prospect-research/2.4',
        'Accept':'text/csv,*/*',
        'Referer':'https://www.data.gov.uk/'
    })
    try:
        with urllib.request.urlopen(req,timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code in {403,404}:
            return b''
        raise

m.get=tolerant_get
m.START=date(2026,8,1)
m.END=date(2026,8,29)
m.main()
