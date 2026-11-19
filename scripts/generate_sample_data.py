"""Generate deterministic, fully synthetic sample data for local runs and tests.

Nothing here is real. The labor export deliberately includes fake personal
fields (name, SSN, hourly rate) so the PII guard has something to remove.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORES = [  # (POS location_code, labor store_number)
    ("NYC-014", "1014"),
    ("NYC-022", "1022"),
    ("CHI-003", "2003"),
    ("ATL-007", "3007"),
    ("ATL-011", "3011"),
]
DAYS = [date(2026, 11, 13) + timedelta(days=i) for i in range(3)]
FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Casey", "Riley", "Morgan", "Jamie"]
LAST = ["Lee", "Patel", "Garcia", "Kim", "Nguyen", "Brown", "Lopez", "Chen"]


def main() -> None:
    rng = random.Random(42)
    pos_dir, labor_dir = ROOT / "sample_data" / "pos", ROOT / "sample_data" / "labor"
    pos_dir.mkdir(parents=True, exist_ok=True)
    labor_dir.mkdir(parents=True, exist_ok=True)

    check_seq, shift_seq = 100000, 500000
    for day in DAYS:
        checks = []
        shifts = []
        for loc, store_no in STORES:
            for _ in range(rng.randint(40, 70)):
                check_seq += 1
                closed = datetime.combine(day, datetime.min.time()) + timedelta(minutes=rng.randint(11 * 60, 22 * 60))
                net = round(rng.uniform(8, 120), 2)
                checks.append(
                    {
                        "check_id": str(check_seq),
                        "location_code": loc,
                        "business_date": day.isoformat(),
                        "closed_at": closed.isoformat(),
                        "net_sales": net,
                        "tax": round(net * 0.0875, 2),
                        "guest_count": rng.randint(1, 6),
                        "order_channel": rng.choice(["dine_in", "takeout", "delivery"]),
                        # Fields the warehouse must never receive:
                        "card_last4": f"{rng.randint(0, 9999):04d}",
                        "customer_email": f"guest{check_seq}@example.com",
                    }
                )
            for _ in range(rng.randint(8, 14)):
                shift_seq += 1
                start = datetime.combine(day, datetime.min.time()) + timedelta(hours=rng.choice([7, 10, 15, 17]))
                emp = rng.randint(1, 40)
                shifts.append(
                    {
                        "shift_id": f"S{shift_seq}",
                        "store_number": store_no,
                        "work_date": day.isoformat(),
                        "employee_id": f"E{store_no}{emp:03d}",
                        "employee_name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
                        "ssn": f"999-{rng.randint(10, 99)}-{rng.randint(1000, 9999)}",
                        "hourly_rate": round(rng.uniform(16, 26), 2),
                        "job_code": rng.choice(["COOK", "SERVER", "HOST", "MGR", "DISH"]),
                        "clock_in": start.isoformat(),
                        "clock_out": (start + timedelta(hours=rng.choice([4, 6, 8]))).isoformat(),
                    }
                )

        (pos_dir / f"sales_{day.isoformat()}.json").write_text(json.dumps(checks, indent=1))
        with (labor_dir / f"shifts_{day.isoformat()}.csv").open("w", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(shifts[0]))
            writer.writeheader()
            writer.writerows(shifts)

    print(f"Wrote sample data for {len(DAYS)} days x {len(STORES)} stores")


if __name__ == "__main__":
    main()
