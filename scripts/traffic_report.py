#!/usr/bin/env python3
"""Private ObraSignal traffic report. No HTTP/customer-facing endpoint is exposed."""
import argparse
import json

from app import db
from traffic_analytics import private_summary, purge_raw_events


def main():
    parser = argparse.ArgumentParser(description="Private obrasignal.com traffic analytics")
    parser.add_argument("--days", type=int, default=30, help="reporting window, default 30")
    parser.add_argument("--purge", action="store_true", help="purge raw events older than retention")
    parser.add_argument("--retain-days", type=int, default=90, help="raw event retention, default 90")
    args = parser.parse_args()
    conn = db()
    try:
        purged = purge_raw_events(conn, retain_days=args.retain_days) if args.purge else 0
        report = private_summary(conn, days=max(1, args.days))
        report["purged"] = purged
        print(json.dumps(report, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
