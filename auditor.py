from typing import List, Dict, Any


def calculate_leak(transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Calculate downgrade leakage for a list of transactions.

    Rules:
      - If interchange_code contains "STND" or "STANDARD": leak is 0.95% of amount
      - If interchange_code contains "EIRF": leak is 0.50% of amount
      - If interchange_code contains "L2" or "LEVEL 2": leak is 0.75% of amount
        and status should be "WARNING: L2 Sunset"
      - If it contains "L3", "P3" or "CEDP": leak is $0 (Status: "PASS")
    """
    total_volume = 0.0
    total_lost = 0.0
    failed_count = 0
    failed_transactions: List[Dict[str, Any]] = []

    saw_stnd_or_standard = False
    saw_eirf = False
    saw_l2 = False

    for tx in transactions:
        amount = float(tx.get("amount", 0.0) or 0.0)
        code_raw = str(tx.get("interchange_code", "") or "")
        code = code_raw.upper()

        total_volume += amount

        # Qualified/optimized codes override downgrade detection
        if "L3" in code or "P3" in code or "CEDP" in code:
            loss = 0.0
            status = "PASS"
        elif "STND" in code or "STANDARD" in code:
            loss = amount * 0.0095
            status = "DOWNGRADE: STANDARD"
            saw_stnd_or_standard = True
        elif "EIRF" in code:
            loss = amount * 0.0050
            status = "DOWNGRADE: EIRF"
            saw_eirf = True
        elif "L2" in code or "LEVEL 2" in code:
            loss = amount * 0.0075
            status = "WARNING: L2 Sunset"
            saw_l2 = True
        else:
            loss = 0.0
            status = "UNCLASSIFIED"

        if loss > 0:
            failed_count += 1
            total_lost += loss
            failed_tx = dict(tx)
            failed_tx["loss_amount"] = round(loss, 2)
            failed_tx["status"] = status
            failed_transactions.append(failed_tx)

    recommended_fixes: List[str] = []
    if saw_stnd_or_standard:
        recommended_fixes.append(
            "Investigate STANDARD downgrades: ensure CEDP/Level 3 data and proper authorization parameters are passed."
        )
    if saw_eirf:
        recommended_fixes.append(
            "Investigate EIRF downgrades: verify settlement timeliness and AVS data quality."
        )
    if saw_l2:
        recommended_fixes.append(
            "Review L2/Level 2 interchange: migrate clients to CEDP-compliant Level 3 data before the April 18th sunset."
        )
    if not recommended_fixes:
        recommended_fixes.append("No downgrade leakage detected under current rules.")

    return {
        "total_processed_volume": round(total_volume, 2),
        "total_money_lost": round(total_lost, 2),
        "count_of_failed_transactions": failed_count,
        "recommended_fixes": recommended_fixes,
        "failed_transactions": failed_transactions,
    }

