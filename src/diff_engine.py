"""
Rate Diff & Comparison Engine.
Compares portal rates with official rates, calculates hikes/cuts/new slabs,
and produces structured summary metrics and HTML reports.
"""

from typing import List, Dict, Any, Tuple
from src.models import BankRecord, DepositTable, RateSlab, AuditSummary


class DiffEngine:
    @staticmethod
    def match_and_diff_table(etm_table: DepositTable, official_slabs: List[RateSlab]) -> DepositTable:
        """
        Merges official slabs into an ET Money table, calculating diffs for each row.
        """
        has_changes = False
        updated_rows: List[RateSlab] = []

        # Map official slabs by day range or tenure string
        matched_official = set()

        for r in etm_table.rows:
            best_off = None
            # 1. Match by exact or overlapping day interval
            if r.min_days is not None and r.max_days is not None:
                for idx, o in enumerate(official_slabs):
                    if idx in matched_official:
                        continue
                    if o.min_days == r.min_days and o.max_days == r.max_days:
                        best_off = o
                        matched_official.add(idx)
                        break

            # 2. Fallback: match by tenure text snippet
            if not best_off:
                clean_t = r.tenure.lower()
                for idx, o in enumerate(official_slabs):
                    if idx in matched_official:
                        continue
                    if o.tenure.lower() == clean_t or (clean_t in o.tenure.lower() and len(clean_t) > 5):
                        best_off = o
                        matched_official.add(idx)
                        break

            # Copy official rates if matched, else retain existing if already present
            off_g = best_off.off_gen if best_off else r.off_gen
            off_s = best_off.off_sr if best_off else r.off_sr

            # Calculate diff
            status = "IN_SYNC"
            details = "In Sync"

            diff_g = round(off_g - r.etm_gen, 2) if (off_g is not None and r.etm_gen is not None) else 0.0
            diff_s = round(off_s - r.etm_sr, 2) if (off_s is not None and r.etm_sr is not None) else 0.0

            if r.etm_gen is None and off_g is not None:
                status = "NEW_SLAB"
                details = "New Special Scheme on Official Portal"
                has_changes = True
            elif diff_g > 0 or diff_s > 0:
                status = "RATE_HIKE"
                g_txt = f"+{diff_g}%" if diff_g > 0 else "Same"
                s_txt = f"+{diff_s}%" if diff_s > 0 else "Same"
                details = f"Rate Hike (Gen: {g_txt}, Sr: {s_txt})"
                has_changes = True
            elif diff_g < 0 or diff_s < 0:
                status = "RATE_CUT"
                g_txt = f"{diff_g}%" if diff_g < 0 else "Same"
                s_txt = f"{diff_s}%" if diff_s < 0 else "Same"
                details = f"Rate Cut (Gen: {g_txt}, Sr: {s_txt})"
                has_changes = True

            updated_rows.append(RateSlab(
                tenure=r.tenure,
                min_days=r.min_days,
                max_days=r.max_days,
                etm_gen=r.etm_gen,
                etm_sr=r.etm_sr,
                off_gen=off_g,
                off_sr=off_s,
                status=status,
                change_details=details
            ))

        # Check for unmapped official slabs (New Slabs)
        for idx, o in enumerate(official_slabs):
            if idx not in matched_official and (o.off_gen or o.off_sr):
                updated_rows.append(RateSlab(
                    tenure=o.tenure,
                    min_days=o.min_days,
                    max_days=o.max_days,
                    etm_gen=None,
                    etm_sr=None,
                    off_gen=o.off_gen,
                    off_sr=o.off_sr,
                    status="NEW_SLAB",
                    change_details="New Official Tenure Slab"
                ))
                has_changes = True

        etm_table.rows = updated_rows
        etm_table.has_changes = has_changes
        return etm_table

    @staticmethod
    def compute_summary(dataset: List[BankRecord], timestamp: str) -> AuditSummary:
        total_hikes = 0
        total_cuts = 0
        total_new_slabs = 0
        changed_banks = set()

        for b in dataset:
            b_changed = False
            for t in b.tables:
                for r in t.rows:
                    if r.status == "RATE_HIKE":
                        total_hikes += 1
                        b_changed = True
                    elif r.status == "RATE_CUT":
                        total_cuts += 1
                        b_changed = True
                    elif r.status == "NEW_SLAB":
                        total_new_slabs += 1
                        b_changed = True
            if b_changed:
                changed_banks.add(b.bank_name)

        return AuditSummary(
            generated_at=timestamp,
            total_banks=len(dataset),
            changed_banks=sorted(list(changed_banks)),
            total_hikes=total_hikes,
            total_cuts=total_cuts,
            total_new_slabs=total_new_slabs
        )
