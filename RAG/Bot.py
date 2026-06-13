"""
RAG Bot - Terminal Backend  (improved)
Uses: FAISS (.bin index) + pickle (.pkl chunks) + Groq API (free tier)
Run: python Bot.py
"""

import os
import sys
import re
import pickle
import hashlib
import numpy as np
import faiss
from difflib import get_close_matches
from groq import Groq
from sentence_transformers import SentenceTransformer

# ─── CONFIG ────────────────────────────────────────────────────────────────────
FAISS_INDEX_PATH  = r"..\RAG_Data\faiss_index.bin"
CHUNKS_PKL_PATH   = r"..\RAG_Data\docs.pkl"
EMBED_MODEL       = "all-MiniLM-L6-v2"

TOP_K             = 50       # FAISS candidates per query variant
FINAL_TOP_K       = 10       # chunks sent to LLM after reranking (raised)
MIN_CHUNK_WORDS   = 15       # drop micro-chunks
SIMILARITY_CUTOFF = 2.2      # slightly relaxed to catch more candidates
MAX_CONTEXT_CHARS = 14000    # raised — 70b handles more context fine

# Per-intent TOP_K overrides — some intents need broader search
INTENT_TOP_K = {
    "tiering":      70,
    "tier_explain": 70,
    "general":      70,
    "viability":    60,
    "usage":        60,
}

# FIX #9: use the stronger free Groq model for much better synthesis
GROQ_API_KEY = "Apk_key"   # ← paste your key here
GROQ_MODEL   = "your_model"
MAX_HISTORY = 6              # conversation turns to keep (3 user + 3 bot)
DEBUG       = False

# Generation keywords — used to penalise cross-gen chunks
GEN_MARKERS = {
    "sv":  ["sv", "gen 9", "gen9", "scarlet", "violet", "s/v", "scarlet and violet",
            "scarlet & violet", "generation 9"],
    "old": ["oras", "sm", "usum", "ss", "swsh", "bdsp", "gen 6", "gen 7", "gen 8",
            "gen6", "gen7", "gen8", "omega ruby", "sun and moon", "sword and shield",
            "brilliant diamond"],
}

# ─── LOAD ──────────────────────────────────────────────────────────────────────

def load_index_and_chunks():
    for path in (FAISS_INDEX_PATH, CHUNKS_PKL_PATH):
        if not os.path.exists(path):
            print(f"[ERROR] Not found: {path}")
            sys.exit(1)
    print("[*] Loading FAISS index...")
    index = faiss.read_index(FAISS_INDEX_PATH)
    print("[*] Loading text chunks...")
    with open(CHUNKS_PKL_PATH, "rb") as f:
        chunks = pickle.load(f)
    print(f"[✓] Loaded {index.ntotal} vectors | {len(chunks)} chunks\n")
    return index, chunks


def load_embedder():
    print(f"[*] Loading embedding model: {EMBED_MODEL} ...")
    model = SentenceTransformer(EMBED_MODEL)
    print(f"[✓] Embedding model ready\n")
    return model


# ─── QUERY PARSING ─────────────────────────────────────────────────────────────

TIER_PATTERN = re.compile(r"\b(ou|uu|ru|nu|lc|ubers|ag|pu|natdex|nfe)\b", re.I)
GEN_PATTERN  = re.compile(r"\b(sv|gen\s*9|oras|gen\s*6|sm|gen\s*7|swsh|gen\s*8|ss)\b", re.I)

# FIX #6: added common sentence-starting words that are capitalised but not mon names
STOPWORDS = {
    "best","set","for","in","ou","uu","ru","nu","lc","ubers","ag","pu","nfe",
    "sv","gen","the","a","an","is","what","why","how","tier","current","good",
    "great","top","pokemon","smogon","team","sample","build","natdex","national",
    "dex","difference","between","and","most","used","recommend","me","can","you",
    "give","tell","about","please","vs","versus","or","are","was","were","its",
    "it","this","that","which","who","where","when","would","could","should",
    "banned","ban","suspect","did","do","does","will","has","have",
    "therain","therian","incarnate",
    # sentence starters often capitalised
    "what","tell","give","show","explain","describe","find","list","which",
    "who","why","how","can","could","would","should","is","are","was",
}

# ─── POKEMON NAME FUZZY CORRECTION ────────────────────────────────────────────
# Canonical list of Gen 9 / commonly asked Smogon mons for typo correction.
# Add more names here as needed.
KNOWN_MONS = [
    "Gholdengo","Great Tusk","Iron Valiant","Kingambit","Dragapult","Garchomp",
    "Landorus","Gliscor","Zapdos","Volcarona","Primarina","Toxapex","Slowking",
    "Corviknight","Ferrothorn","Heatran","Clefable","Skeledirge","Palafin",
    "Roaring Moon","Iron Bundle","Flutter Mane","Chi-Yu","Chien-Pao","Wo-Chien",
    "Ting-Lu","Baxcalibur","Dragonite","Gyarados","Tyranitar","Excadrill",
    "Mimikyu","Sableye","Blissey","Chansey","Urshifu","Ursaluna","Manaphy",
    "Pelipper","Torkoal","Ninetales","Venusaur","Cinderace","Incineroar",
    "Rillaboom","Greninja","Blaziken","Meowscarada","Skeledirge","Quaquaval",
    "Annihilape","Clodsire","Dondozo","Tatsugiri","Orthworm","Garganacl",
    "Sandy Shocks","Iron Moth","Iron Hands","Iron Jugulis","Iron Thorns",
    "Scream Tail","Brute Bonnet","Flutter Mane","Slither Wing","Sandy Shocks",
    "Mega Rayquaza","Mega Blaziken","Enamorus","Tornadus","Thundurus",
    "Weavile","Aegislash","Kartana","Celesteela","Tapu Koko","Tapu Fini",
    "Tapu Lele","Tapu Bulu","Magearna","Zygarde","Marshadow","Naganadel",
    "Blaziken","Darkrai","Shaymin","Genesect","Deoxys","Calyrex",
    "Spectrier","Glastrier","Kyogre","Groudon","Rayquaza","Zacian","Zamazenta",
    "Eternatus","Necrozma","Solgaleo","Lunala","Xerneas","Yveltal",
]
KNOWN_MONS_LOWER = {m.lower(): m for m in KNOWN_MONS}

def correct_pokemon_name(name: str) -> str:
    """
    Fuzzy-correct a possibly misspelled Pokémon name.
    Returns the corrected canonical name, or the original if no close match.
    """
    if not name:
        return name
    nl = name.lower()
    # Exact match
    if nl in KNOWN_MONS_LOWER:
        return KNOWN_MONS_LOWER[nl]
    # Fuzzy match — cutoff 0.75 catches common typos like baxaclibar → Baxcalibur
    matches = get_close_matches(nl, KNOWN_MONS_LOWER.keys(), n=1, cutoff=0.72)
    if matches:
        corrected = KNOWN_MONS_LOWER[matches[0]]
        if corrected.lower() != nl:
            print(f"  [~] Corrected '{name}' → '{corrected}'")
        return corrected
    return name  # unknown mon, return as-is


def parse_query(query: str, history: list[dict] | None = None) -> dict:
    """
    Extract tier, gen, mon name, and intent from the query.
    FIX #8: if the current query is a follow-up (short, no mon/tier detected),
    pull context from the most recent turn in history.
    """
    ql = query.lower().strip()

    tier_m = TIER_PATTERN.search(ql)
    tier   = tier_m.group(1).upper() if tier_m else None

    gen_m  = GEN_PATTERN.search(ql)
    gen    = gen_m.group(1).upper() if gen_m else "SV"

    # FIX #6: only accept tokens that are NOT at the very start of the sentence
    # and not obviously a sentence-starter
    tokens     = re.findall(r"[A-Za-z][a-zA-Z\-]*", query)
    mon_tokens = [
        t for t in tokens
        if t.lower() not in STOPWORDS and len(t) > 2
    ]
    # Prefer tokens that look like Pokémon names (mixed or title case, not all-caps stopwords)
    cap_tokens = [t for t in mon_tokens if t[0].isupper() and not t.isupper()]
    mon        = correct_pokemon_name(" ".join((cap_tokens or mon_tokens)[:2]))

    # FIX #8: inherit mon/tier from recent history if this looks like a follow-up
    if history and (not mon or not tier):
        for turn in reversed(history):
            prev_parsed = turn.get("parsed", {})
            if not mon and prev_parsed.get("mon"):
                mon = prev_parsed["mon"]
            if not tier and prev_parsed.get("tier"):
                tier = prev_parsed["tier"]
            if mon and tier:
                break

    # Intent detection
    intent = "general"
    if any(w in ql for w in ["best set","good set","moveset","set for","ev spread","what set","build","moves"]):
        intent = "moveset"
    elif any(w in ql for w in ["most used","usage stat","how common","popular","usage"]):
        intent = "usage"
    elif any(w in ql for w in ["best pokemon","top pokemon","best mon","top tier","top mon","most viable","rank"]):
        intent = "viability"
    elif any(w in ql for w in ["banned","ban","suspect","quickban","why banned","tiering","dropped","rose"]):
        intent = "tiering"
    elif any(w in ql for w in ["counter","check","how to beat","dealing with","beat","wall","stop"]):
        intent = "checks"
    elif any(w in ql for w in ["sample team","team for","team build","build a team","offense team","stall team","balance team","hyper offense"]):
        intent = "teams"
    elif any(w in ql for w in ["difference","explain tier","what is ou","what is uu","what is ru","what is ru","what is nu","what is lc","what is ubers","what is ag","how does tier","tiering system","what does ou","what does uu"]):
        intent = "tier_explain"
    elif mon:
        intent = "mon_info"

    return {"tier": tier, "gen": gen, "mon": mon, "intent": intent, "raw": query}


def expand_query(parsed: dict) -> list[str]:
    """
    FIX #7: accept pre-parsed dict instead of re-parsing the raw query.
    Generate diverse query variants based on intent.
    """
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
        # Use the detected tier name in variants if present, else generic
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

    # Deduplicate preserving order
    seen, unique = set(), []
    for v in variants:
        k = v.lower().strip()
        if k not in seen:
            seen.add(k)
            unique.append(v)
    return unique


# ─── SCORING ───────────────────────────────────────────────────────────────────

def keyword_score(text: str, query: str, parsed: dict) -> float:
    """
    Multi-factor keyword score:
    - Query keyword overlap
    - Tier match bonus
    - Gen match/mismatch (SV-specific)
    - Mon name exact match bonus
    """
    tl = text.lower()
    score = 0.0

    qwords = {w.lower() for w in re.findall(r"[a-zA-Z]+", query)
              if w.lower() not in STOPWORDS and len(w) > 2}
    if qwords:
        hits = sum(1 for w in qwords if w in tl)
        score += (hits / len(qwords)) * 0.5

    if parsed["tier"] and parsed["tier"].lower() in tl:
        score += 0.2

    user_gen = parsed["gen"].lower()
    if user_gen in ("sv", "gen9", "gen 9"):
        sv_hits  = sum(1 for m in GEN_MARKERS["sv"]  if m in tl)
        old_hits = sum(1 for m in GEN_MARKERS["old"] if m in tl)
        if sv_hits > 0:
            score += 0.15
        if old_hits > 0 and sv_hits == 0:
            score -= 0.25

    if parsed["mon"] and parsed["mon"].lower() in tl:
        score += 0.15

    return score


# ─── RETRIEVAL ─────────────────────────────────────────────────────────────────

def get_chunk_text(chunk) -> str:
    if isinstance(chunk, dict):
        return chunk.get("text", chunk.get("page_content", str(chunk)))
    return str(chunk)


def retrieve(query: str, index, chunks, embedder,
             history: list[dict] | None = None) -> list[str]:
    """
    1. Parse + expand query (with history context for follow-ups)
    2. FIX #1: Batch-encode all variants in one call  ← big speedup
    3. FAISS search, merge, filter
    4. FIX #5: Min-max normalise L2 distances properly
    5. Rerank and return best FINAL_TOP_K chunks
    """
    parsed   = parse_query(query, history)
    variants = expand_query(parsed)  # FIX #7: pass parsed dict, not raw string

    # Use a wider search for intents where relevant data is sparse/scattered
    top_k = INTENT_TOP_K.get(parsed["intent"], TOP_K)

    if DEBUG:
        print(f"\n  [DEBUG] Parsed: intent={parsed['intent']} tier={parsed['tier']} "
              f"gen={parsed['gen']} mon='{parsed['mon']}'")
        print(f"  [DEBUG] {len(variants)} variants:")
        for v in variants:
            print(f"    • {v}")

    # FIX #1: encode all variants in a single batch — much faster
    vecs = embedder.encode(variants, convert_to_numpy=True, batch_size=16).astype("float32")

    # FIX #4: use full-text hash for deduplication, not fragile 100-char prefix
    seen_hashes: set[str] = set()
    all_candidates: list[tuple[float, float, str]] = []

    for vec in vecs:
        distances, indices = index.search(vec[np.newaxis, :], top_k)

        for dist, idx in zip(distances[0], indices[0]):
            if not (0 <= idx < len(chunks)):
                continue
            text    = get_chunk_text(chunks[idx])
            text_id = hashlib.md5(text.encode()).hexdigest()  # FIX #4
            if text_id in seen_hashes:
                continue
            seen_hashes.add(text_id)

            if len(text.split()) < MIN_CHUNK_WORDS:
                continue
            if dist > SIMILARITY_CUTOFF:
                continue

            ks = keyword_score(text, query, parsed)
            all_candidates.append((dist, ks, text))

    if not all_candidates:
        return []

    # FIX #5: proper min-max normalisation so the best chunk always scores 1.0
    dists    = [c[0] for c in all_candidates]
    min_dist = min(dists)
    max_dist = max(dists)
    dist_range = (max_dist - min_dist) or 1.0

    scored = []
    for dist, ks, text in all_candidates:
        norm_sim    = 1.0 - (dist - min_dist) / dist_range  # higher = more similar
        final_score = norm_sim * 0.55 + ks * 0.45
        scored.append((final_score, text))

    scored.sort(key=lambda x: x[0], reverse=True)

    if DEBUG:
        print(f"\n  [DEBUG] Top {min(FINAL_TOP_K, len(scored))} after reranking:\n")
        for i, (sc, t) in enumerate(scored[:FINAL_TOP_K]):
            print(f"  [{i+1}] score={sc:.3f} | {t[:160]}\n")

    # Token-safe selection
    selected, total_chars = [], 0
    for score, text in scored:
        if len(selected) >= FINAL_TOP_K:
            break
        if total_chars + len(text) > MAX_CONTEXT_CHARS:
            remaining = MAX_CONTEXT_CHARS - total_chars
            if remaining > 400:
                selected.append(text[:remaining])
            break
        selected.append(text)
        total_chars += len(text)

    return selected


# ─── LLM ───────────────────────────────────────────────────────────────────────

def build_messages(question: str, context_chunks: list[str],
                   history: list[dict]) -> list[dict]:
    """
    FIX #2: Build full message list including conversation history.
    System prompt is sent once; prior turns are replayed as user/assistant pairs.
    """
    parsed  = parse_query(question)
    gen_note = (
        "The user is asking about SV (Gen 9). Ignore context about older gens "
        "(ORAS, SM, USUM, SWSH) unless directly comparing them to SV."
        if parsed["gen"].upper() in ("SV", "GEN9", "GEN 9")
        else "Answer using the provided context."
    )

    system_prompt = f"""You are a Smogon competitive Pokémon assistant specialising in Generation 9 (Scarlet & Violet).

{gen_note}

RULES:
1. PRIMARY SOURCE: Use the provided Smogon forum context as your main source.
2. GENERAL KNOWLEDGE FALLBACK: For well-established, stable competitive facts — tier definitions (what OU/UU/RU means), how Smogon tiering works, base stat facts, type matchups — you MAY use your training knowledge if the context does not cover it. Clearly say "(general knowledge)" when doing so.
3. NEVER invent or guess: specific movesets, EV spreads, ban outcomes, suspect test results, or viability rankings not present in the context. These change frequently.
4. Do NOT mix NatDex data with standard SV tiers unless the user explicitly asks about NatDex.
5. If context partially answers, give what you have and clearly note what is missing.
6. Only say "I couldn't find clear data" if you have NOTHING useful from context OR general knowledge.
7. You MAY synthesise and summarise across multiple context chunks.
8. Format responses clearly. Use bullet points for movesets/sets. Keep answers concise."""

    context = "\n\n---\n\n".join(context_chunks)

    messages = [{"role": "system", "content": system_prompt}]

    # Replay history (last MAX_HISTORY turns)
    for turn in history[-MAX_HISTORY:]:
        messages.append({"role": "user",      "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["bot"]})

    # Current turn — context is injected here
    messages.append({
        "role": "user",
        "content": f"Context from Smogon forums:\n{context}\n\nQuestion: {question}"
    })

    return messages


def ask_groq(client: Groq, question: str, context_chunks: list[str],
             history: list[dict]) -> str:
    """FIX #3: client is passed in (created once), not recreated per call."""
    messages = build_messages(question, context_chunks, history)

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.0,
            max_tokens=900,   # slightly raised for 70b model
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        err = str(e)
        # FIX #10: smarter fallback — trim context progressively, not just to 3
        if "413" in err or "rate_limit" in err or "too_large" in err.lower():
            for n_chunks in (5, 3, 2):
                if n_chunks >= len(context_chunks):
                    continue
                try:
                    trimmed_msgs = build_messages(question, context_chunks[:n_chunks], history)
                    response = client.chat.completions.create(
                        model=GROQ_MODEL,
                        messages=trimmed_msgs,
                        temperature=0.0,
                        max_tokens=700,
                    )
                    return response.choices[0].message.content.strip()
                except Exception:
                    continue
        raise


# ─── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    global DEBUG

    api_key = os.environ.get("GROQ_API_KEY", GROQ_API_KEY).strip()
    if not api_key or api_key == "your-groq-api-key-here":
        print("[ERROR] Set your Groq API key in the GROQ_API_KEY constant at the top of the file.")
        sys.exit(1)

    index, chunks = load_index_and_chunks()
    embedder      = load_embedder()

    # FIX #3: create Groq client once and reuse it
    client  = Groq(api_key=api_key)
    history: list[dict] = []   # FIX #2: conversation memory

    print("=" * 60)
    print("  Smogon RAG Bot  |  'quit' to exit | 'debug' to toggle | 'clear' to reset history")
    print("=" * 60)

    while True:
        try:
            question = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Bye!]")
            break

        if not question:
            continue
        if question.lower() in {"quit", "exit", "q"}:
            print("[Bye!]")
            break
        if question.lower() == "debug":
            DEBUG = not DEBUG
            print(f"[Debug: {'ON' if DEBUG else 'OFF'}]")
            continue
        if question.lower() == "clear":
            history.clear()
            print("[Conversation history cleared]")
            continue

        print("[*] Expanding & retrieving...")
        # FIX #8: pass history so follow-up queries inherit mon/tier context
        relevant_chunks = retrieve(question, index, chunks, embedder, history)

        if not relevant_chunks:
            print("Bot: No relevant chunks found.")
            print("     Tip: Be specific — e.g. 'Gholdengo SV OU moveset' or 'why was X banned from SV OU'")
            continue

        print(f"[*] Sending {len(relevant_chunks)} chunks to LLM ({GROQ_MODEL})...\n")
        try:
            # FIX #2, #3: pass client and history
            answer = ask_groq(client, question, relevant_chunks, history)
            print(f"Bot: {answer}")

            # Store turn in history with parsed context for follow-up resolution
            parsed = parse_query(question, history)
            history.append({"user": question, "bot": answer, "parsed": parsed})

        except Exception as e:
            print(f"[ERROR] {e}")


if __name__ == "__main__":
    main()