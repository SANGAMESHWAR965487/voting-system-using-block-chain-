"""
analytics.py
------------
Pure Python ML/stats helpers for the voting analytics page.
Import this in app.py:  from analytics import compute_analytics
"""

import json


def softmax(scores):
    """Simple softmax to convert raw vote counts to win probabilities."""
    if not scores or sum(scores) == 0:
        n = len(scores) or 1
        return [round(1 / n, 4)] * n
    total = sum(scores)
    return [round(s / total, 4) for s in scores]


def predict_winner(candidates):
    """
    Logistic-style win prediction based on current vote share.
    Returns list of dicts with name, votes, probability, predicted_winner flag.
    """
    if not candidates:
        return []
    scores  = [c["votes"] for c in candidates]
    probs   = softmax(scores)
    max_prob = max(probs)
    result  = []
    for i, c in enumerate(candidates):
        result.append({
            "name":             c["name"],
            "votes":            c["votes"],
            "probability":      round(probs[i] * 100, 1),
            "predicted_winner": probs[i] == max_prob
        })
    return result


def compute_margin(candidates):
    """Returns vote gap between top 2 candidates."""
    if len(candidates) < 2:
        return None
    sorted_cands = sorted(candidates, key=lambda x: x["votes"], reverse=True)
    return sorted_cands[0]["votes"] - sorted_cands[1]["votes"]


def detect_anomalies(vote_data, total_registered):
    """
    Simple rule-based anomaly / insight detection.
    Returns list of insight dicts with type and text.
    """
    insights = []
    total_votes = sum(
        sum(c["votes"] for c in cands)
        for cands in vote_data.values()
    ) // max(len(vote_data), 1)

    turnout = round((total_votes / total_registered * 100) if total_registered else 0)

    if turnout < 20:
        insights.append({"type": "alert",
            "text": f"Very low turnout ({turnout}%). Voting may not have opened yet or participation is critically low."})
    elif turnout < 40:
        insights.append({"type": "warn",
            "text": f"Low turnout at {turnout}%. Consider sending reminders to registered students."})
    else:
        insights.append({"type": "ok",
            "text": f"Healthy turnout at {turnout}% of registered students."})

    for pos, cands in vote_data.items():
        if not cands:
            continue
        margin = compute_margin(cands)
        leader = max(cands, key=lambda x: x["votes"])
        if margin is None:
            continue
        if leader["votes"] == 0:
            insights.append({"type": "info",
                "text": f"{pos}: No votes cast yet."})
        elif margin <= 2:
            insights.append({"type": "alert",
                "text": f"{pos}: Extremely tight race — {leader['name']} leads by only {margin} vote(s). Outcome uncertain."})
        elif margin <= 5:
            insights.append({"type": "warn",
                "text": f"{pos}: Close race — {leader['name']} leads by {margin} votes. Could swing either way."})
        else:
            insights.append({"type": "ok",
                "text": f"{pos}: {leader['name']} has a comfortable lead of {margin} votes."})

    return insights


def build_hourly_trend(total_votes):
    """
    Placeholder hourly trend. Replace with real DB query if you store timestamps.
    Distributes total_votes across a bell-curve-style day.
    """
    weights = [0.02, 0.05, 0.12, 0.18, 0.16, 0.14, 0.12, 0.10, 0.07, 0.04]
    cumulative = 0
    counts = []
    for w in weights:
        cumulative += round(total_votes * w)
        counts.append(min(cumulative, total_votes))
    counts[-1] = total_votes  # ensure last point matches actual total
    return {
        "labels": ["08:00","09:00","10:00","11:00","12:00",
                   "13:00","14:00","15:00","16:00","17:00"],
        "counts": counts
    }


def compute_analytics(get_results_fn, get_all_users_fn,
                      blockchain_chain, pending_transactions,
                      is_chain_valid_fn, positions):
    """
    Main entry point called from app.py visualize() route.
    Returns a dict that is json.dumps()-safe (all plain Python types).
    """
    # ── Vote data ─────────────────────────────────────────────
    vote_data = {}
    for pos in positions:
        raw = get_results_fn(pos)
        rows = []
        for c in raw:
            if isinstance(c, dict):
                name  = c.get("name") or c.get("candidate_name") or "Unknown"
                votes = c.get("vote_count") or c.get("votes") or 0
            else:
                name  = getattr(c, "name", None) or getattr(c, "candidate_name", "Unknown")
                votes = getattr(c, "vote_count", None) or getattr(c, "votes", 0)
            try:
                votes = int(votes)
            except (TypeError, ValueError):
                votes = 0
            rows.append({"name": str(name), "votes": votes})
        rows.sort(key=lambda x: x["votes"], reverse=True)
        vote_data[pos] = rows

    # ── ML predictions ────────────────────────────────────────
    predictions = {}
    for pos, cands in vote_data.items():
        predictions[pos] = predict_winner(cands)

    # ── Blockchain ────────────────────────────────────────────
    block_count   = len(blockchain_chain)
    pending_count = len(pending_transactions)
    chain_valid   = bool(is_chain_valid_fn())

    # ── Turnout ───────────────────────────────────────────────
    all_users        = get_all_users_fn()
    total_registered = len(all_users)
    voted_users      = [u for u in all_users if (
                            getattr(u, "has_voted", None) in (1, True) or
                            (isinstance(u, dict) and u.get("has_voted") in (1, True))
                        )]
    total_votes  = len(voted_users)
    turnout_pct  = round((total_votes / total_registered * 100) if total_registered else 0)
    recent_votes = min(total_votes, 12)

    # ── Hourly trend ──────────────────────────────────────────
    hourly_data = build_hourly_trend(total_votes)

    # ── Dept participation (placeholder) ─────────────────────
    dept_data = {
        "labels": ["CSE", "AIML", "DS", "ECE", "EEE", "Civil"],
        "counts": [42, 31, 28, 18, 11, 6]
    }

    # ── Insights ──────────────────────────────────────────────
    insights = []
    if chain_valid:
        insights.append({"type": "ok",
            "text": f"Blockchain integrity passed — {block_count} block(s) verified, no tampering detected."})
    else:
        insights.append({"type": "alert",
            "text": "Blockchain validation FAILED. Possible tampering detected!"})

    insights += detect_anomalies(vote_data, total_registered)

    if pending_count > 0:
        insights.append({"type": "info",
            "text": f"{pending_count} transaction(s) pending in mempool. Auto-mines when 5 accumulate."})

    return {
        "vote_data":        vote_data,
        "predictions":      predictions,
        "hourly_data":      hourly_data,
        "dept_data":        dept_data,
        "insights":         insights,
        "block_count":      block_count,
        "pending_count":    pending_count,
        "chain_valid":      chain_valid,
        "total_votes":      total_votes,
        "total_registered": total_registered,
        "turnout_pct":      turnout_pct,
        "recent_votes":     recent_votes,
    }