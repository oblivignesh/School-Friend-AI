"""Fast, rule-based pre-filter for strictly banned topic categories.

This runs *before* the LLM call as a cheap first line of defense. It is
intentionally conservative (keyword/phrase based) and is meant to complement
-- not replace -- the strict system-prompt instructions given to the model.
"""
import re
from typing import Optional

# Each category maps to a list of keywords/phrases. Matching is whole-word /
# whole-phrase, case-insensitive, so short substrings don't cause false
# positives (e.g. "sport" won't match inside "transportation").
BANNED_CATEGORIES: dict[str, list[str]] = {
    "religion": [
        "religion", "religious", "god", "allah", "jesus", "christ", "bible",
        "quran", "koran", "hindu", "hinduism", "islam", "muslim", "christianity",
        "buddhism", "buddhist", "sikh", "sikhism", "temple", "church sermon",
        "prayer", "praying", "atheism", "atheist",
    ],
    "politics": [
        "politics", "political", "election", "president", "prime minister",
        "government policy", "political party", "senator", "congress",
        "parliament", "vote for", "campaign rally", "democrat", "republican",
        "communism", "socialism", "capitalism debate", "geopolitics",
    ],
    "entertainment": [
        "movie", "movies", "film", "films", "celebrity", "celebrities",
        "actor", "actress", "netflix", "hollywood", "bollywood", "tv show",
        "television show", "web series", "singer", "song lyrics", "music album",
        "concert", "gossip",
    ],
    "sports": [
        "cricket", "football", "soccer", "basketball", "nba", "fifa",
        "olympics", "tennis", "badminton", "hockey match", "sports team",
        "world cup", "ipl", "wrestling", "boxing match",
    ],
    "adult_content": [
        "porn", "sex", "sexual", "nude", "nudity", "explicit content",
        "adult content", "erotic",
    ],
    "tourism": [
        "vacation", "holiday trip", "tourist", "tourism", "places to visit",
        "travel itinerary", "trip to", "sightseeing", "best beaches",
        "honeymoon",
    ],
    "party_planning": [
        "birthday party", "party planning", "party ideas", "wedding planning",
        "bachelor party", "bachelorette party", "party theme", "party invite",
    ],
}

_COMPILED: list[tuple[str, re.Pattern]] = [
    (category, re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE))
    for category, phrases in BANNED_CATEGORIES.items()
    for phrase in phrases
]


def check_banned(text: str) -> Optional[str]:
    """Return the matched banned category name, or None if the text looks fine."""
    for category, pattern in _COMPILED:
        if pattern.search(text):
            return category
    return None


REFUSAL_MESSAGE = (
    "I'm School Friend AI, and I can only help with K-12 school subjects "
    "(math, science, English, social studies, geography, computer science, "
    "and study skills). That topic is outside what I'm allowed to discuss. "
    "Feel free to ask me a school-related question instead!"
)
