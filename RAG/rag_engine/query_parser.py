"""
rag_engine.query_parser
──────────────────────────
Parses a raw user question into {tier, gen, mon, intent}, and expands it into
several search-query variants tuned per intent. This is unchanged in behavior
from the original Bot.py — only reorganised to import shared regex/lists from
entities.py instead of duplicating them.
"""

import re

from .entities import (
    TIER_PATTERN, GEN_PATTERN, STOPWORDS, correct_pokemon_name,
)


def parse_query(query: str, history: list[dict] | None = None) -> dict:
    """
    Extract tier, gen, mon name, and intent from the query. If the current
    query looks like a short follow-up with no mon/tier detected, inherit
    them from the most recent turn in history.
    """
    ql = query.lower().strip()

    tier_m = TIER_PATTERN.search(ql)
    tier   = tier_m.group(1).upper() if tier_m else "OU"

    gen_m  = GEN_PATTERN.search(ql)
    gen    = gen_m.group(1).upper() if gen_m else "SV"

    tokens     = re.findall(r"[A-Za-z][a-zA-Z\-]*", query)
    mon_tokens = [t for t in tokens if t.lower() not in STOPWORDS and len(t) > 2]
    cap_tokens = [t for t in mon_tokens if t[0].isupper() and not t.isupper()]
    mon        = correct_pokemon_name(" ".join((cap_tokens or mon_tokens)[:2]))

    if history and (not mon or not tier):
        for turn in reversed(history):
            prev_parsed = turn.get("parsed", {})
            if not mon and prev_parsed.get("mon"):
                mon = prev_parsed["mon"]
            if not tier and prev_parsed.get("tier"):
                tier = prev_parsed["tier"]
            if mon and tier:
                break

    intent = "general"
    if any(w in ql for w in ["best set", "good set", "moveset", "set for", "ev spread", "what set", "build", "moves"]):
        intent = "moveset"
    elif any(w in ql for w in ["most used", "usage stat", "how common", "popular", "usage"]):
        intent = "usage"
    elif any(w in ql for w in ["best pokemon", "top pokemon", "best mon", "top tier", "top mon", "most viable", "rank"]):
        intent = "viability"
    elif any(w in ql for w in ["banned", "ban", "suspect", "quickban", "why banned", "tiering", "dropped", "rose"]):
        intent = "tiering"
    elif any(w in ql for w in ["counter", "check", "how to beat", "dealing with", "beat", "wall", "stop"]):
        intent = "checks"
    elif any(w in ql for w in ["sample team", "team for", "team build", "build a team", "offense team", "stall team", "balance team", "hyper offense"]):
        intent = "teams"
    elif any(w in ql for w in ["difference", "explain tier", "what is ou", "what is uu", "what is ru", "what is nu", "what is lc", "what is ubers", "what is ag", "how does tier", "tiering system", "what does ou", "what does uu"]):
        intent = "tier_explain"
    elif mon:
        intent = "mon_info"

    return {"tier": tier, "gen": gen, "mon": mon, "intent": intent, "raw": query}


def expand_query(parsed: dict) -> list[str]:
    """Generate diverse query variants for vector search, tuned per intent."""
    query  = parsed["raw"]
    mon    = parsed["mon"]
    tier   = parsed["tier"] or "OU"
    gen    = parsed["gen"]
    intent = parsed["intent"]

    variants = [query]

    if intent == "moveset":
        variants += [
            f"{mon} {tier} moveset {gen}",
            f"{mon} {tier} analysis {gen}",
            f"{mon} competitive set Scarlet Violet",
            f"{mon} EV spread {tier}",
            f"{mon} Smogon {tier} set",
            f"{mon} recommended moves {tier}",
        ]
    elif intent == "viability":
        variants += [
            f"SV {tier} viability ranking S tier A tier",
            f"SV {tier} best Pokemon tier list",
            f"SV {tier} top threats meta",
            f"viability rankings {tier} Scarlet Violet",
            f"SV {tier} S rank A rank tier list",
            f"{tier} most powerful pokemon SV meta",
        ]
    elif intent == "usage":
        variants += [
            f"SV {tier} usage statistics",
            f"SV {tier} most used Pokemon stats",
            f"{tier} usage stats Scarlet Violet",
            f"SV {tier} usage top 10",
            f"most common {tier} Pokemon SV ladder",
            f"SV {tier} meta staples",
        ]
    elif intent == "tiering":
        variants += [
            f"{mon} suspect test SV {tier}",
            f"{mon} banned SV {tier}",
            f"why {mon} banned {tier} SV",
            f"{mon} tiering discussion Scarlet Violet",
            f"{mon} quickban {tier} SV",
            f"{mon} overcentralising {tier}",
            f"{mon} broken SV {tier}",
        ]
    elif intent == "checks":
        variants += [
            f"counters to {mon} SV {tier}",
            f"how to deal with {mon} {tier}",
            f"{mon} checks {tier} SV",
            f"what beats {mon} SV {tier}",
            f"{mon} best checks walls {tier}",
        ]
    elif intent == "teams":
        variants += [
            f"SV {tier} sample teams",
            f"SV {tier} offense team hyper offense",
            f"SV {tier} bulky offense balance team",
            f"SV {tier} stall team example",
            f"SV {tier} approved teams",
            f"SV {tier} team building cores",
        ]
    elif intent == "tier_explain":
        t = tier if parsed["tier"] else "OU"
        variants += [
            f"what is {t} Smogon tier explanation",
            f"{t} tier definition Smogon competitive",
            f"Smogon {t} overused underused tier meaning",
            "Smogon tiering system how it works OU UU RU",
            "usage threshold OU UU Smogon SV",
            "how Pokemon get placed in tiers Smogon",
            f"SV {t} tier explained competitive",
            f"{t} what pokemon are allowed Smogon",
        ]
    elif intent == "mon_info":
        variants += [
            f"{mon} {tier} SV",
            f"{mon} SV analysis Smogon",
            f"{mon} competitive SV {tier}",
            f"{mon} role in {tier} SV",
            f"{mon} strengths weaknesses {tier}",
        ]
    else:
        variants += [
            f"{query} SV {tier}",
            f"{query} Smogon SV",
            f"{query} Scarlet Violet competitive",
        ]

    seen, unique = set(), []
    for v in variants:
        k = v.lower().strip()
        if k not in seen:
            seen.add(k)
            unique.append(v)
    return unique
