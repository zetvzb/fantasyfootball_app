import sys
from pathlib import Path


sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1]),
)


from src.recommendation import (
    calculate_bid_recommendations,
    build_recommendation_index,
)


print()
print("=" * 70)
print("RECOMMENDATION ENGINE")
print("=" * 70)

print(
    "DO NOT EXCEED engine imports successfully."
)

print(
    "Next step: calculate recommendations "
    "inside the Streamlit draft state."
)