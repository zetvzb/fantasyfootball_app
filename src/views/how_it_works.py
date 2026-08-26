from __future__ import annotations

import streamlit as st


def render_how_it_works_view() -> None:
    st.header("💡 How This Works")
    st.caption(
        "A plain-language walkthrough of how a recommendation gets made -- "
        "what's math, what's AI, and why the two are kept strictly separate."
    )

    st.markdown(
        """
### The short version

Every dollar figure this app shows you -- a player's value, the price you
should stop bidding at, a keeper's break-even year -- comes from
**deterministic math**: the same inputs always produce the same number,
every time, and you can trace exactly why. An **optional AI layer** can
turn those already-computed numbers into a readable sentence, but it is
never allowed to invent or change a number itself.
"""
    )

    st.divider()
    st.markdown("### From raw information to a recommendation")

    stage_columns = st.columns(5)
    stages = [
        ("📰", "Sources", "Sleeper rosters, your spreadsheet, rankings, news, injury reports, depth charts, anything you upload."),
        ("🔍", "Evidence check", "Every piece of information is graded: hard evidence, strong signal, or soft signal -- and it decays over time."),
        ("📈", "Value adjustment", "Graded evidence nudges a player's baseline market value up or down, inside hard caps so no single report can swing it wildly."),
        ("🎯", "Live caps", "Your cash, roster needs, and the room's bidding behavior turn that value into a Target, Soft Cap, and Hard Cap."),
        ("✅", "Recommendation", "BID or PASS, with the reasons listed in plain terms -- never a black box."),
    ]
    for column, (icon, title, body) in zip(stage_columns, stages):
        with column:
            st.markdown(f"**{icon} {title}**")
            st.caption(body)

    st.divider()
    st.markdown("### A worked example")
    st.markdown(
        """
Say a beat reporter posts that a running back is dealing with a minor
hamstring issue three days before your draft.

1. **Evidence check** -- a single beat-reporter post is classified as a
   *strong signal*, not *hard evidence* (that tier is reserved for things
   like an official injury report or a confirmed transaction).
2. **Value adjustment** -- the system nudges that player's value down by a
   small, bounded amount. It cannot erase most of his value over one
   report, and the adjustment fades on its own if no update follows.
3. **If a follow-up report says he's cleared to play** -- the newer,
   more specific update supersedes the older one automatically. The
   system always prefers the most recent, most specific evidence.
4. **At the auction table** -- if you're deciding whether to bid, the
   recommendation shows the adjusted price *and* the reason: e.g.
   *"Target lowered ~4% -- soft signal: hamstring report, 2 days old."*
   You see the number and the reason it moved, together.
"""
    )

    st.divider()
    st.markdown("### A deeper example: a team change plus a depth-chart bump")
    st.caption(
        "This uses the app's real formulas and real numeric caps. The "
        "player is a stand-in (\"Player X\") rather than a specific real "
        "athlete -- an accurate answer needs this week's actual news and "
        "depth chart, which this static page can't verify, and a portfolio "
        "page shouldn't state something concrete about a real person "
        "without that. The mechanics below are exactly what runs in "
        "production, just with a placeholder name."
    )

    st.markdown(
        """
**Setup:** Player X, a 25-year-old WR, is traded to a new team three weeks
before your draft. A week later, the new team's depth chart moves him into
the WR1 role after an injury to the incumbent.

**Step 1 -- Start from a base value.** Say the ensemble of ranking sources
(Sleeper-derived data, your imported spreadsheet, and any third source you
have) puts his base market value at **$38**.

**Step 2 -- Apply the age curve.** For a WR, the deterministic age table
used for keeper/future-value math looks like this:
"""
    )
    st.dataframe(
        {
            "Age": ["≤ 24", "25 - 27", "28 - 29", "30+"],
            "Future-value multiplier": ["1.10x", "1.03x", "0.95x", "0.90x and declining"],
        },
        width="stretch",
        hide_index=True,
    )
    st.markdown(
        """
At 25, Player X gets the **1.03x** multiplier -- a small bump for being
early in his prime, not a subjective guess.

**Step 3 -- Classify the new information.** Two things happened:
- *He was traded* -- that's a confirmed transaction, so it's treated as
  **hard evidence**, not a rumor.
- *He moved into the WR1 role on the new team's depth chart* -- the depth
  chart tracker sees his positional rank move up and raises a **ROLE_UP**
  signal, treated as a **strong analytical signal**.

**Step 4 -- Turn that into a bounded price adjustment.** Every positive
signal has a small, fixed weight, scaled by how confident the system is in
the evidence ("strength", 0-1):
- Role improvement: **+2% x strength**
- Usage/opportunity improvement (if snaps/targets data confirms it):
  **+1.25% x strength**

Even if every positive signal fired at full strength, the total increase
is hard-capped at **+6%** of base value for that player -- no single
report, or combination of reports, can blow past that ceiling. (The
equivalent cap on the downside is **-8%**, since injuries and role losses
can matter more.)

**Step 5 -- The result.** With strong-confidence role-up evidence, Player
X's adjusted ceiling lands around **$38 x 1.03 x 1.05 ≈ $41**, and the
recommendation shows the reason alongside the number: *"+5% -- role
change: moved into starting role after trade, high confidence."* If a
week goes by with no confirming snap-count data, that confidence decays
and the adjustment shrinks back down on its own -- old news stops
mattering as much, automatically.
"""
    )

    st.divider()
    st.markdown("### Where AI actually gets used (and where it doesn't)")

    ai_col, math_col = st.columns(2)
    with math_col:
        st.success("**Always deterministic math**")
        st.markdown(
            "- Player values, Target/Soft Cap/Hard Cap\n"
            "- Keeper cost, surplus, break-even year\n"
            "- Legal keeper/roster/budget checks\n"
            "- Every simulation and every historical grade"
        )
    with ai_col:
        st.info("**Optional AI (off by default)**")
        st.markdown(
            "- Turning already-computed facts into a readable sentence\n"
            "- Never sees or changes a number, cap, or legal check\n"
            "- If it's off, or fails, you still get the full deterministic "
            "explanation -- nothing about the app stops working"
        )

    st.caption(
        "In short: the AI is a narrator, never a decision-maker. If you "
        "turned it off entirely, every recommendation, cap, and grade in "
        "this app would be identical -- just described a little more "
        "tersely."
    )

    st.markdown(
        "**So, is an LLM used in the example above?** No. Evidence "
        "classification, the age curve, the role/usage signal weights, and "
        "the ±6%/8% caps are all plain Python arithmetic -- no API call, "
        "no model, nothing that could hallucinate a number. The one place "
        "an LLM can optionally get involved is turning the finished "
        "explanation into a slightly more natural sentence, after every "
        "number above is already final."
    )

    st.divider()
    st.markdown("### Why it's built this way")
    st.markdown(
        """
An auction draft is a live, time-pressured negotiation with real money on
the line. A recommendation you can't audit in the moment isn't useful --
you need to know *why* a number is what it is, instantly, under a bidding
clock. Keeping the math deterministic and the AI strictly narrative means
every recommendation is explainable, reproducible, and never dependent on
an external API being up.
"""
    )
