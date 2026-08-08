"""
rag_engine.entities
─────────────────────
Pokémon/tier/generation recognition, shared by:
  - query_parser.py       (what did the USER ask about)
  - scripts/build_index.py (what does each CHUNK mention — needed to build the graph)

Previously this list + regex lived only in Bot.py and was used solely for query
parsing. Reusing it at index-build time is what makes the entity graph possible:
a chunk becomes a graph node's neighbor by having the same entities extracted
from its text as we extract from the user's query.
"""

import re
from difflib import get_close_matches

TIER_PATTERN = re.compile(r"\b(ou|uu|ru|nu|lc|ubers|ag|pu|natdex|nfe)\b", re.I)
GEN_PATTERN  = re.compile(r"\b(sv|gen\s*9|oras|gen\s*6|sm|gen\s*7|swsh|gen\s*8|ss)\b", re.I)

GEN_MARKERS = {
    "sv":  ["sv", "gen 9", "gen9", "scarlet", "violet", "s/v", "scarlet and violet",
            "scarlet & violet", "generation 9"],
    "old": ["oras", "sm", "usum", "ss", "swsh", "bdsp", "gen 6", "gen 7", "gen 8",
            "gen6", "gen7", "gen8", "omega ruby", "sun and moon", "sword and shield",
            "brilliant diamond"],
}

STOPWORDS = {
    "best", "set", "for", "in", "ou", "uu", "ru", "nu", "lc", "ubers", "ag", "pu", "nfe",
    "sv", "gen", "the", "a", "an", "is", "what", "why", "how", "tier", "current", "good",
    "great", "top", "pokemon", "smogon", "team", "sample", "build", "natdex", "national",
    "dex", "difference", "between", "and", "most", "used", "recommend", "me", "can", "you",
    "give", "tell", "about", "please", "vs", "versus", "or", "are", "was", "were", "its",
    "it", "this", "that", "which", "who", "where", "when", "would", "could", "should",
    "banned", "ban", "suspect", "did", "do", "does", "will", "has", "have",
    "therain", "therian", "incarnate", "show", "list", "find", "explain", "describe",
}

KNOWN_MONS = [
    "Gholdengo", "Great Tusk", "Iron Valiant", "Kingambit", "Dragapult", "Garchomp",
    "Landorus", "Gliscor", "Zapdos", "Volcarona", "Primarina", "Toxapex", "Slowking",
    "Corviknight", "Ferrothorn", "Heatran", "Clefable", "Skeledirge", "Palafin",
    "Roaring Moon", "Iron Bundle", "Flutter Mane", "Chi-Yu", "Chien-Pao", "Wo-Chien",
    "Ting-Lu", "Baxcalibur", "Dragonite", "Gyarados", "Tyranitar", "Excadrill",
    "Mimikyu", "Sableye", "Blissey", "Chansey", "Urshifu", "Ursaluna", "Manaphy",
    "Pelipper", "Torkoal", "Ninetales", "Venusaur", "Cinderace", "Incineroar",
    "Rillaboom", "Greninja", "Blaziken", "Meowscarada", "Skeledirge", "Quaquaval",
    "Annihilape", "Clodsire", "Dondozo", "Tatsugiri", "Orthworm", "Garganacl",
    "Sandy Shocks", "Iron Moth", "Iron Hands", "Iron Jugulis", "Iron Thorns",
    "Scream Tail", "Brute Bonnet", "Slither Wing",
    "Mega Rayquaza", "Mega Blaziken", "Enamorus", "Tornadus", "Thundurus",
    "Weavile", "Aegislash", "Kartana", "Celesteela", "Tapu Koko", "Tapu Fini",
    "Tapu Lele", "Tapu Bulu", "Magearna", "Zygarde", "Marshadow", "Naganadel",
    "Darkrai", "Shaymin", "Genesect", "Deoxys", "Calyrex",
    "Spectrier", "Glastrier", "Kyogre", "Groudon", "Rayquaza", "Zacian", "Zamazenta",
    "Eternatus", "Necrozma", "Solgaleo", "Lunala", "Xerneas", "Yveltal",
]
KNOWN_MONS_LOWER = {m.lower(): m for m in KNOWN_MONS}


def correct_pokemon_name(name: str) -> str:
    """Fuzzy-correct a possibly misspelled Pokémon name to its canonical form."""
    if not name:
        return name
    nl = name.lower()
    if nl in KNOWN_MONS_LOWER:
        return KNOWN_MONS_LOWER[nl]
    matches = get_close_matches(nl, KNOWN_MONS_LOWER.keys(), n=1, cutoff=0.72)
    if matches:
        return KNOWN_MONS_LOWER[matches[0]]
    return name


def extract_mons(text: str) -> list[str]:
    """
    Find every KNOWN_MONS name mentioned in a block of text (case-insensitive,
    whole-phrase match). Used at index-build time to tag chunks for the graph.
    """
    tl = text.lower()
    found = []
    for mon_lower, canonical in KNOWN_MONS_LOWER.items():
        # word-boundary match so "Tusk" inside "Great Tusk" doesn't double count
        # against unrelated substrings, and multi-word names match as a phrase.
        if re.search(rf"\b{re.escape(mon_lower)}\b", tl):
            found.append(canonical)
    return found


def extract_tiers(text: str) -> list[str]:
    return sorted({m.upper() for m in TIER_PATTERN.findall(text)})


def extract_gen_tag(text: str) -> str | None:
    """
    Return 'SV' or 'OLD' if the text clearly belongs to one generation bucket,
    else None if ambiguous/undetected. Used to penalise cross-gen chunks.
    """
    tl = text.lower()
    sv_hits  = sum(1 for m in GEN_MARKERS["sv"] if m in tl)
    old_hits = sum(1 for m in GEN_MARKERS["old"] if m in tl)
    if sv_hits and not old_hits:
        return "SV"
    if old_hits and not sv_hits:
        return "OLD"
    return None


def extract_entities(text: str) -> dict:
    """Bundle of everything build_index.py needs to tag a chunk for the graph."""
    return {
        "mons":    extract_mons(text),
        "tiers":   extract_tiers(text),
        "gen_tag": extract_gen_tag(text),
    }
