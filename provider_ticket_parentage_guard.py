"""Integration-only provider-ticket parentage guard.

This module overlays the existing Notification owner implementation without
claiming device/user delivery. It prevents one provider receipt from becoming
acceptance evidence for multiple local logical delivery parents. Duplicate
historical ticket ownership remains explicit UNKNOWN/ambiguous rather than
choosing an arbitrary winner.
"""


def install(module):
    def reconcile_push_receipts(
        conn,
        account_id,
        limit=1000,
        post=module.requests.post,
        min_age_seconds=900,
    ):
        """Reconcile only provider tickets with one unambiguous local parent."""
        module.ensure_push_tables(conn)
        candidates = conn.execute(
            """SELECT pd.id,pd.event_id,pd.push_device_id,pd.ticket_id,pd.submitted_at,
                      pd.receipt_checked_at,pd.expo_push_token,pd.attempt_count
               FROM push_deliveries pd
               JOIN opportunity_events e ON e.id=pd.event_id
               WHERE e.account_id=?
                 AND pd.ticket_id IS NOT NULL
                 AND pd.submitted_at IS NOT NULL
                 AND pd.receipt_status IS NULL
               ORDER BY pd.submitted_at ASC
               LIMIT ?""",
            (str(account_id), max(1, min(1000, int(limit)))),
        ).fetchall()
        if not candidates:
            return 0

        now_dt = module.datetime.now(module.timezone.utc)
        due = []
        for row in candidates:
            reference = module._parse_iso(row["receipt_checked_at"]) or module._parse_iso(row["submitted_at"])
            if reference is None or (now_dt - reference).total_seconds() >= max(0, int(min_age_seconds)):
                due.append(row)
        if not due:
            return 0

        # Ticket ids are provider-global correlation identities. Count every
        # durable local owner, not just the current account or due batch. Any
        # duplicate mapping is ambiguous and must not consume receipt evidence.
        ticket_ids = sorted({str(row["ticket_id"]) for row in due if row["ticket_id"]})
        placeholders = ",".join("?" for _ in ticket_ids)
        ambiguous = set()
        if ticket_ids:
            ambiguous = {
                str(row["ticket_id"])
                for row in conn.execute(
                    f"""SELECT ticket_id
                        FROM push_deliveries
                        WHERE ticket_id IN ({placeholders})
                        GROUP BY ticket_id
                        HAVING COUNT(*) > 1""",
                    ticket_ids,
                ).fetchall()
            }

        now = now_dt.isoformat()
        if ambiguous:
            for row in due:
                if str(row["ticket_id"]) not in ambiguous:
                    continue
                conn.execute(
                    """UPDATE push_deliveries
                       SET receipt_checked_at=?,
                           last_error='receipt_parent_ambiguous',
                           receipt_error='receipt_parent_ambiguous'
                       WHERE id=?""",
                    (now, row["id"]),
                )
            conn.commit()

        unique_due = [row for row in due if str(row["ticket_id"]) not in ambiguous]
        if not unique_due:
            return 0

        try:
            response = post(
                module.EXPO_RECEIPTS_URL,
                json={"ids": [row["ticket_id"] for row in unique_due]},
                headers=module._push_headers(),
                timeout=8,
            )
            response.raise_for_status()
            payload = response.json() or {}
            receipts = payload.get("data") or {}
            if not isinstance(receipts, dict):
                receipts = {}
        except Exception as exc:
            error = f"receipt_transport_{type(exc).__name__}"[:240]
            for row in unique_due:
                conn.execute(
                    "UPDATE push_deliveries SET receipt_checked_at=?,last_error=? WHERE id=?",
                    (now, error, row["id"]),
                )
            conn.commit()
            return 0

        reconciled = 0
        for row in unique_due:
            receipt = receipts.get(row["ticket_id"])
            if not isinstance(receipt, dict):
                conn.execute(
                    "UPDATE push_deliveries SET receipt_checked_at=?,last_error=? WHERE id=?",
                    (now, "receipt_not_available", row["id"]),
                )
                continue

            status = receipt.get("status")
            if status == "ok":
                # This remains provider acceptance only, never device/user delivery.
                conn.execute(
                    """UPDATE push_deliveries
                       SET receipt_status='provider_accepted',receipt_checked_at=?,
                           receipt_error=NULL,last_error=NULL,next_attempt_at=NULL
                       WHERE id=?""",
                    (now, row["id"]),
                )
                reconciled += 1
                continue

            details = receipt.get("details") or {}
            error = str(details.get("error") or receipt.get("message") or "receipt_error")[:240]
            if error == "MessageRateExceeded" and int(row["attempt_count"]) < module.MAX_PUSH_ATTEMPTS:
                retry_at = module._next_retry_at(int(row["attempt_count"]) + 1, now_dt)
                conn.execute(
                    """UPDATE push_deliveries
                       SET ticket_id=NULL,submitted_at=NULL,last_error=?,next_attempt_at=?,
                           receipt_status=NULL,receipt_checked_at=?,receipt_error=?,failed_at=NULL
                       WHERE id=?""",
                    (error, retry_at, now, error, row["id"]),
                )
            else:
                conn.execute(
                    """UPDATE push_deliveries
                       SET receipt_status='error',receipt_checked_at=?,receipt_error=?,
                           last_error=?,failed_at=?,next_attempt_at=NULL
                       WHERE id=?""",
                    (now, error, error, now, row["id"]),
                )
                if error == "DeviceNotRegistered" and row["expo_push_token"]:
                    module._revoke_device_row(
                        conn,
                        row["push_device_id"],
                        expected_token=row["expo_push_token"],
                        error=error,
                    )
            reconciled += 1
        conn.commit()
        return reconciled

    module.reconcile_push_receipts = reconcile_push_receipts
    return module
