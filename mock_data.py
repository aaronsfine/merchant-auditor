import random
from datetime import datetime, timedelta
from typing import List, Dict


CARD_TYPES = [
    "VISA_CONSUMER",
    "VISA_BUSINESS",
    "MC_CONSUMER",
    "MC_BUSINESS",
]

# Example interchange codes; some represent downgrades
INTERCHANGE_CODES = [
    "VISA BUSN L3",   # qualified
    "VISA BUSN STND", # downgrade
    "MC BUSN L3",     # qualified
    "MC BUSN STND",   # downgrade
    "EIRF",           # downgrade
    "MC CONS L1",     # qualified
]

DOWNGRADE_KEYWORDS = ("STND", "EIRF")


def generate_mock_transactions(n: int = 50) -> List[Dict]:
    """
    Generate a list of mock credit card transactions.

    Each transaction has:
      - date (ISO string)
      - amount (float)
      - card_type (str)
      - interchange_code (str)

    Roughly 30% of transactions will have downgrade codes
    containing either 'STND' or 'EIRF'.
    """
    transactions: List[Dict] = []

    today = datetime.today()

    # First, decide which indices should be downgrades (~30%)
    downgrade_count_target = int(n * 0.3)
    downgrade_indices = set(random.sample(range(n), k=downgrade_count_target))

    downgrade_codes = [code for code in INTERCHANGE_CODES if any(k in code for k in DOWNGRADE_KEYWORDS)]
    qualified_codes = [code for code in INTERCHANGE_CODES if code not in downgrade_codes]

    for i in range(n):
        # Spread dates over the past 60 days
        days_ago = random.randint(0, 59)
        tx_date = (today - timedelta(days=days_ago)).strftime("%Y-%m-%d")

        amount = round(random.uniform(5.0, 500.0), 2)
        card_type = random.choice(CARD_TYPES)

        if i in downgrade_indices and downgrade_codes:
            interchange_code = random.choice(downgrade_codes)
        else:
            # Still allow occasional random downgrade outside the target,
            # but skew toward qualified codes.
            pool = qualified_codes or INTERCHANGE_CODES
            interchange_code = random.choice(pool)

        transactions.append(
            {
                "date": tx_date,
                "amount": amount,
                "card_type": card_type,
                "interchange_code": interchange_code,
            }
        )

    return transactions


if __name__ == "__main__":
    # Simple manual check helper
    txs = generate_mock_transactions()
    downgrade_count = sum(1 for t in txs if any(k in t["interchange_code"] for k in DOWNGRADE_KEYWORDS))
    print(f"Generated {len(txs)} transactions, {downgrade_count} downgrades (~{downgrade_count/len(txs):.0%})")
    for t in txs[:5]:
        print(t)

