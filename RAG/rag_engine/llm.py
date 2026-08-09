"""
rag_engine.llm
──────────────────
Builds the message list (system prompt + history + context-injected question)
and calls Groq, with the same progressive-context-trimming fallback on
413/rate-limit errors as the original Bot.py. Behavior unchanged.
"""

from groq import Groq

from . import config
from .query_parser import parse_query


def build_messages(question: str, context_chunks: list[str], history: list[dict]) -> list[dict]:
    parsed = parse_query(question)
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
2. GENERAL KNOWLEDGE FALLBACK: You may use your general knowledge of competitive Pokémon. Only mention that you are using general knowledge if the answer is entirely based on general knowledge with NO context support. Use it naturally.
3. NEVER invent or guess: specific movesets, EV spreads, ban outcomes, suspect test results, or viability rankings not present in the context. These change frequently.
4. Do NOT mix NatDex data with standard SV tiers unless the user explicitly asks about NatDex.
5. If context partially answers, give what you have and clearly note what is missing.
6. Only say "I couldn't find clear data" as an absolute last resort. If there's any relevant context at all, use it and supplement with knowledge.
7. You MAY synthesise and summarise across multiple context chunks.
8. Format responses clearly. Use bullet points for movesets/sets. Keep answers concise.
9. Present your answer confidently. Don't apologize or hedge unnecessarily. If you know something from competitive knowledge, share it directly."""

    context = "\n\n---\n\n".join(context_chunks)

    messages = [{"role": "system", "content": system_prompt}]
    for turn in history[-config.MAX_HISTORY:]:
        messages.append({"role": "user", "content": turn["user"]})
        messages.append({"role": "assistant", "content": turn["bot"]})

    messages.append({
        "role": "user",
        "content": f"Context from Smogon forums:\n{context}\n\nQuestion: {question}"
    })
    return messages


def ask_groq(client: Groq, question: str, context_chunks: list[str], history: list[dict]) -> str:
    messages = build_messages(question, context_chunks, history)

    try:
        response = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=messages,
            temperature=0.0,
            max_tokens=900,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        err = str(e)
        if "413" in err or "rate_limit" in err or "too_large" in err.lower():
            for n_chunks in (5, 3, 2):
                if n_chunks >= len(context_chunks):
                    continue
                try:
                    trimmed_msgs = build_messages(question, context_chunks[:n_chunks], history)
                    response = client.chat.completions.create(
                        model=config.GROQ_MODEL,
                        messages=trimmed_msgs,
                        temperature=0.0,
                        max_tokens=700,
                    )
                    return response.choices[0].message.content.strip()
                except Exception:
                    continue
        raise
