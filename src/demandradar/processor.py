from __future__ import annotations

import json
import re
from collections import Counter
from typing import Any

STOPWORDS = {
    # Articles / prepositions / conjunctions
    "a", "an", "and", "are", "as", "at", "be", "been", "being",
    "but", "by", "do", "does", "did", "for", "from", "had", "has",
    "have", "he", "her", "him", "his", "how", "i", "if", "in", "into",
    "is", "it", "its", "me", "my", "no", "not", "of", "on", "or",
    "our", "out", "she", "so", "than", "that", "the", "their", "them",
    "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "up", "us", "was", "we", "were", "what", "when", "where",
    "which", "who", "whom", "why", "will", "with", "would", "you", "your",
    # Common HN/Reddit noise words
    "ask", "looking", "love", "one", "also", "about", "all", "already",
    "always", "any", "anyone", "bit", "can", "cant", "comment", "could",
    "day", "different", "don", "each", "else", "even", "ever", "every",
    "example", "feel", "find", "get", "given", "good", "got", "great",
    "here", "hey", "http", "https", "idea", "just", "keep", "know",
    "let", "like", "little", "look", "lot", "made", "make", "many",
    "may", "maybe", "more", "most", "much", "need", "new", "now", "old",
    "only", "other", "over", "own", "people", "per", "pretty", "put",
    "really", "right", "said", "same", "say", "see", "seems", "set",
    "should", "since", "some", "something", "still", "sure", "take",
    "think", "thought", "time", "trying", "two", "under", "until",
    "use", "used", "using", "via", "very", "want", "way", "well",
    "went", "without", "work", "working", "yet",
    # Singular/plural noise
    "tool", "tools", "thing", "things", "stuff", "issue", "issues",
    "problem", "problems", "solution", "solutions", "question", "questions",
    "recommendation", "recommendations", "option", "options", "case", "cases",
    "type", "types", "feature", "features", "project", "projects",
    "user", "users", "team", "teams", "company", "companies",
}

FRUSTRATION_WORDS = {
    "pain": 2,
    "annoying": 1,
    "frustrating": 2,
    "hate": 2,
    "broken": 2,
    "manual": 1,
    "slow": 1,
    "impossible": 2,
    "wish": 1,
    "missing": 1,
    "need": 1,
}

SOLUTION_PATTERNS = [
    r"currently use ([A-Za-z0-9_./ -]{2,30})",
    r"using ([A-Za-z0-9_./ -]{2,30})",
    r"tried ([A-Za-z0-9_./ -]{2,30})",
    r"use ([A-Za-z0-9_./ -]{2,30}) today",
]

LLM_PROMPT_TEMPLATE = """Extract a structured developer-demand signal from the post below.
Return JSON only with keys:
problem_statement (string),
target_audience (string),
existing_solutions (array of strings),
frustration_level (integer 1-5),
frequency_indicator (string)

Title: {title}
Source: {source}
Text: {text}
Engagement score: {score}
Comments: {comments}
"""

CLUSTER_SIMILARITY_THRESHOLD = 0.12


def _normalize_whitespace(text: str) -> str:
    return " ".join((text or "").split())


def _normalize_token(token: str) -> str:
    token = token.lower().strip()
    if token.endswith("'s"):
        token = token[:-2]
    if token.endswith("ies") and len(token) > 4:
        token = token[:-3] + "y"
    elif token.endswith("s") and not token.endswith("ss") and len(token) > 4:
        token = token[:-1]
    return token


def _tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9+-]{2,}", text.lower())
    normalized = [_normalize_token(token) for token in tokens]
    return [token for token in normalized if token and token not in STOPWORDS]


def _excerpt(text: str, limit: int = 220) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _infer_target_audience(text: str) -> str:
    lowered = text.lower()
    if "developer" in lowered or "dev" in lowered:
        return "Developers"
    if "founder" in lowered or "startup" in lowered:
        return "Indie founders / startup teams"
    if "student" in lowered or "learn" in lowered:
        return "Students / learners"
    if "team" in lowered or "engineer" in lowered:
        return "Software teams"
    return "Software builders"


def _extract_existing_solutions(text: str) -> list[str]:
    found: list[str] = []
    for pattern in SOLUTION_PATTERNS:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            value = _normalize_whitespace(match).strip(" .,:;!?()[]{}")
            if value and value.lower() not in {v.lower() for v in found}:
                found.append(value)
    return found[:3]


def _estimate_frustration(text: str, engagement: dict[str, Any]) -> int:
    lowered = text.lower()
    base = 1
    base += sum(weight for word, weight in FRUSTRATION_WORDS.items() if word in lowered)
    comments = int((engagement or {}).get("comments") or 0)
    score = int((engagement or {}).get("score") or 0)
    if comments >= 10:
        base += 1
    if score >= 20:
        base += 1
    return max(1, min(5, base))


def _frequency_indicator(text: str, engagement: dict[str, Any]) -> str:
    lowered = text.lower()
    repeated_signals = ["again", "every time", "constantly", "always", "recurring"]
    if any(phrase in lowered for phrase in repeated_signals):
        return "Recurring pain mention"
    comments = int((engagement or {}).get("comments") or 0)
    if comments >= 15:
        return "High discussion volume"
    return "Single signal (monitor for repeats)"


def _heuristic_problem_statement(title: str, text: str) -> str:
    if title and text:
        separator = "" if title.rstrip().endswith((".", "!", "?")) else "."
        combined = _normalize_whitespace(f"{title}{separator} {text}").strip(" .")
    else:
        combined = _normalize_whitespace(f"{title} {text}").strip(" .")
    if not combined:
        return "Developer workflow pain point mentioned"
    if len(combined) <= 180:
        return combined
    parts = re.split(r"(?<=[.!?])\s+", combined)
    if parts and parts[0]:
        return _excerpt(parts[0], limit=180)
    return _excerpt(combined, limit=180)


def _heuristic_signal(raw: dict[str, Any]) -> dict[str, Any]:
    title = _normalize_whitespace(str(raw.get("title") or ""))
    text = _normalize_whitespace(str(raw.get("text") or ""))
    source = str(raw.get("source") or "unknown")
    engagement = raw.get("engagement") or {}
    combined = f"{title} {text}".strip()
    keywords = [kw for kw, _ in Counter(_tokenize(combined)).most_common(8)]
    return {
        "signal_id": f"{source}:{raw.get('id')}",
        "source": source,
        "title": title or "Untitled",
        "url": raw.get("url"),
        "author": raw.get("author"),
        "created_at": raw.get("created_at"),
        "engagement": engagement,
        "problem_statement": _heuristic_problem_statement(title, text),
        "target_audience": _infer_target_audience(combined),
        "existing_solutions": _extract_existing_solutions(text),
        "frustration_level": _estimate_frustration(combined, engagement),
        "frequency_indicator": _frequency_indicator(combined, engagement),
        "keywords": keywords,
        "raw_excerpt": _excerpt(text or title),
        "metadata": raw.get("metadata") or {},
    }


def _extract_json_from_text(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.startswith("json"):
            candidate = candidate[4:]
        candidate = candidate.strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", candidate, flags=re.DOTALL)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _llm_extract_signal(raw: dict[str, Any], api_key: str, model: str) -> dict[str, Any] | None:
    try:
        from openai import OpenAI
    except Exception:
        return None

    client = OpenAI(api_key=api_key)
    engagement = raw.get("engagement") or {}
    prompt = LLM_PROMPT_TEMPLATE.format(
        title=_normalize_whitespace(str(raw.get("title") or "")),
        source=raw.get("source") or "unknown",
        text=_excerpt(_normalize_whitespace(str(raw.get("text") or "")), limit=1500),
        score=int(engagement.get("score") or 0),
        comments=int(engagement.get("comments") or 0),
    )
    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You extract concise structured demand signals for product discovery."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
    except Exception:
        return None

    content = ""
    try:
        content = response.choices[0].message.content or ""
    except Exception:
        return None
    parsed = _extract_json_from_text(content)
    if not parsed:
        return None

    heuristic = _heuristic_signal(raw)
    frustration = int(parsed.get("frustration_level") or heuristic["frustration_level"])
    heuristic.update(
        {
            "problem_statement": _normalize_whitespace(
                str(parsed.get("problem_statement") or heuristic["problem_statement"])
            ),
            "target_audience": _normalize_whitespace(
                str(parsed.get("target_audience") or heuristic["target_audience"])
            ),
            "existing_solutions": [
                _normalize_whitespace(str(item))
                for item in (parsed.get("existing_solutions") or [])
                if str(item).strip()
            ][:5],
            "frustration_level": max(1, min(5, frustration)),
            "frequency_indicator": _normalize_whitespace(
                str(parsed.get("frequency_indicator") or heuristic["frequency_indicator"])
            ),
        }
    )
    return heuristic


def process_raw_signals(
    raw_signals: list[dict[str, Any]],
    openai_api_key: str | None = None,
    llm_model: str = "gpt-4o-mini",
    topic: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    processed: list[dict[str, Any]] = []
    warnings: list[str] = []
    used_llm = bool(openai_api_key)

    for raw in raw_signals:
        combined = _normalize_whitespace(f"{raw.get('title', '')} {raw.get('text', '')}")
        if topic and topic.strip():
            topic_tokens = [t for t in topic.lower().split() if t]
            if topic_tokens and not any(token in combined.lower() for token in topic_tokens):
                continue
        signal = None
        if openai_api_key:
            signal = _llm_extract_signal(raw, api_key=openai_api_key, model=llm_model)
            if signal is None:
                warnings.append(
                    "LLM extraction failed for "
                    f"{raw.get('source')}:{raw.get('id')}; used heuristic fallback"
                )
        if signal is None:
            signal = _heuristic_signal(raw)
        processed.append(signal)

    metadata = {
        "extraction_method": "llm+heuristic-fallback" if used_llm else "heuristic",
        "processor_warnings": warnings,
    }
    return processed, metadata


def _cluster_similarity(cluster_keywords: Counter[str], signal_keywords: list[str]) -> float:
    if not cluster_keywords or not signal_keywords:
        return 0.0
    cluster_set = set(cluster_keywords)
    signal_set = set(signal_keywords)
    intersection = len(cluster_set & signal_set)
    union = len(cluster_set | signal_set)
    if union == 0:
        return 0.0
    return intersection / union


def _cluster_overlap_count(cluster_keywords: Counter[str], signal_keywords: list[str]) -> int:
    if not cluster_keywords or not signal_keywords:
        return 0
    return len(set(cluster_keywords) & set(signal_keywords))


def _theme_label(signals: list[dict[str, Any]], cluster_keywords: Counter[str]) -> str:
    # Use the problem_statement from the highest-engagement signal in the cluster.
    # This is far more readable than raw keyword tokens ("Can / When / Was").
    best = max(
        signals,
        key=lambda s: (
            int((s.get("engagement") or {}).get("score") or 0)
            + int((s.get("engagement") or {}).get("comments") or 0) * 2
        ),
        default=None,
    )
    if best:
        stmt = (best.get("problem_statement") or "").strip()
        if stmt and len(stmt) > 8:
            return _excerpt(stmt, limit=72)
    # Fallback: top meaningful keywords
    top_keywords = [kw for kw, _ in cluster_keywords.most_common(3)]
    if top_keywords:
        return " / ".join(word.replace("-", " ").title() for word in top_keywords)
    return "Opportunity theme"


def cluster_signals(
    signals: list[dict[str, Any]],
    max_themes: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    clusters: list[dict[str, Any]] = []

    for signal in signals:
        signal_keywords = signal.get("keywords") or []
        best_idx = None
        best_score = 0.0
        best_overlap = 0
        for idx, cluster in enumerate(clusters):
            overlap = _cluster_overlap_count(cluster["keywords"], signal_keywords)
            similarity = _cluster_similarity(cluster["keywords"], signal_keywords)
            if overlap > best_overlap or (overlap == best_overlap and similarity > best_score):
                best_overlap = overlap
                best_score = similarity
                best_idx = idx
        if best_idx is not None and (
            best_overlap >= 2 or best_score >= CLUSTER_SIMILARITY_THRESHOLD
        ):
            clusters[best_idx]["signals"].append(signal)
            clusters[best_idx]["keywords"].update(signal_keywords)
            continue
        clusters.append(
            {
                "signals": [signal],
                "keywords": Counter(signal_keywords),
            }
        )

    clusters.sort(key=lambda c: (len(c["signals"]), sum(c["keywords"].values())), reverse=True)
    if len(clusters) > max_themes:
        primary_count = max(1, max_themes - 1)
        overflow = clusters[primary_count:]
        clusters = clusters[:primary_count]
        if overflow:
            misc = {
                "signals": [s for cluster in overflow for s in cluster["signals"]],
                "keywords": Counter(),
            }
            for cluster in overflow:
                misc["keywords"].update(cluster["keywords"])
            clusters.append(misc)

    themes: list[dict[str, Any]] = []
    for cluster in clusters:
        cluster_signals = cluster["signals"]
        source_counts = Counter(signal.get("source") or "unknown" for signal in cluster_signals)
        avg_frustration = round(
            sum(int(signal.get("frustration_level") or 1) for signal in cluster_signals)
            / max(1, len(cluster_signals)),
            2,
        )
        theme = {
            "theme": _theme_label(cluster_signals, cluster["keywords"]),
            "signal_count": len(cluster_signals),
            "avg_frustration": avg_frustration,
            "sources": sorted(source_counts.keys()),
            "top_source": source_counts.most_common(1)[0][0] if source_counts else "unknown",
            "source_counts": dict(source_counts),
            "signals": cluster_signals,
            "keywords": [kw for kw, _ in cluster["keywords"].most_common(10)],
        }
        themes.append(theme)

    metadata = {"clustering_method": "keyword_similarity"}
    return themes, metadata
