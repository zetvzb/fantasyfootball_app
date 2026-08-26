# Portfolio demo walkthrough

The Portfolio Auction Lab is synthetic data designed to exercise the app without exposing a real league. It includes eight managers, unequal entering budgets and traded dollars, seven keeper candidates for the user's team, opponent keeper candidates, two devy rights, and two years of example auction prices.

## Start the demo

From a configured Python 3.9 environment:

```bash
python -m src.portfolio_demo --data-root data
FANTASYFOOTBALL_DEMO_MODE=1 streamlit run app.py
```

Or open **Add League → Portfolio Demo → Load Portfolio Demo** in the sidebar. Installing again is safe and resets only the synthetic demo profile/setup; it does not touch other leagues.

## Five-minute walkthrough

1. Open **League Setup**. Compare the eight entering budgets and their traded-dollar provenance. Confirm the demo has six keeper slots and three devy slots.
2. Open **Pre-Draft**. Select Hybrid, then inspect the typed keeper table and best-four/five/six comparison. The seeded example recommends six keepers while retaining the minimum-bid reserve.
3. In **Decision Narrative**, choose Brock Bowers. The default text is deterministic. With `OPENAI_API_KEY` set, click **Generate optional AI explanation** to polish the same computed facts; the model cannot alter the numeric result.
4. Review the taxi recommendation section. The college players remain separate rights and never appear in the regular auction pool.
5. Open **Draft Mode**. Enter a current bid and follow Target Value, Soft Cap, and Hard Cap. The demo cap card uses the same reserve-aware dynamic-cap service exercised by the app.
6. Record a manual sale, refresh, and open **Draft History** to see the persisted decision trail. Use only the demo league when presenting so real private preferences remain out of view.

## Expected seeded decisions

- Eight teams have entering budgets ranging from $378 to $424.
- The user's seven keeper candidates produce legal best-four, best-five, and best-six scenarios.
- The seeded Hybrid recommendation favors six keepers and retains $202 before filling the remaining roster spots.
- The live example computes Target $49, Soft Cap $54, and Hard Cap $59.
- Screens in `docs/assets/` were captured from this fixture and can be regenerated using the commands in [Screenshots](../docs/SCREENSHOTS.md).

All players, values, costs, and historical prices in the demo are illustrative and are not current fantasy-football advice.
