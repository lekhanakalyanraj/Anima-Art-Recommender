"""Culture/region + category normalization across heterogeneous art sources.

Every source labels geography differently — the Met has a free-text ``culture``
field, Cleveland has ``culture`` arrays, AIC has ``place_of_origin``, WikiArt has
none. We map all of them onto a small, controlled set of world regions so
"coverage by region" is a number we can report, not an assumption.
"""

from __future__ import annotations

# Controlled vocabulary of world regions. Deliberately coarse — enough to prove
# and measure global balance without pretending to encode every culture.
REGIONS: tuple[str, ...] = (
    "african",
    "east_asian",
    "south_asian",       # India, Nepal, Sri Lanka, Himalayan, Tibet
    "southeast_asian",
    "central_asian",
    "west_asian",        # incl. Islamic world / Middle East
    "european",
    "north_american",
    "latin_american",    # incl. Pre-Columbian
    "oceanian",
    "ancient_mediterranean",  # Greek, Roman, Egyptian
    "space",                  # cosmic / astronomical imagery (a-cultural)
    "unknown",
)

# Substring -> region. Matched case-insensitively against a source's raw culture,
# place, or nationality string. Order matters: earlier, more specific wins.
_REGION_RULES: list[tuple[str, str]] = [
    # South Asian
    ("india", "south_asian"), ("indian", "south_asian"), ("mughal", "south_asian"),
    ("rajput", "south_asian"), ("pahari", "south_asian"), ("nepal", "south_asian"),
    ("tibet", "south_asian"), ("himalaya", "south_asian"), ("sri lanka", "south_asian"),
    ("pakistan", "south_asian"), ("gandhara", "south_asian"), ("bengal", "south_asian"),
    ("deccan", "south_asian"),
    # East Asian
    ("china", "east_asian"), ("chinese", "east_asian"), ("japan", "east_asian"),
    ("japanese", "east_asian"), ("korea", "east_asian"), ("korean", "east_asian"),
    ("ukiyo", "east_asian"),
    # Southeast Asian
    ("thai", "southeast_asian"), ("thailand", "southeast_asian"), ("cambodia", "southeast_asian"),
    ("khmer", "southeast_asian"), ("vietnam", "southeast_asian"), ("indonesia", "southeast_asian"),
    ("java", "southeast_asian"), ("burma", "southeast_asian"), ("myanmar", "southeast_asian"),
    ("laos", "southeast_asian"),
    # West Asian / Islamic
    ("islam", "west_asian"), ("iran", "west_asian"), ("persia", "west_asian"),
    ("ottoman", "west_asian"), ("turkey", "west_asian"), ("arab", "west_asian"),
    ("syria", "west_asian"), ("iraq", "west_asian"), ("mesopotam", "west_asian"),
    # Central Asian
    ("central asia", "central_asian"), ("uzbek", "central_asian"), ("silk road", "central_asian"),
    # Ancient Mediterranean
    ("egypt", "ancient_mediterranean"), ("greek", "ancient_mediterranean"),
    ("greece", "ancient_mediterranean"), ("roman", "ancient_mediterranean"),
    ("rome", "ancient_mediterranean"), ("byzant", "ancient_mediterranean"),
    # African
    ("africa", "african"), ("nigeria", "african"), ("yoruba", "african"),
    ("benin", "african"), ("congo", "african"), ("mali", "african"), ("ethiopia", "african"),
    ("egyptian modern", "african"),
    # Oceanian
    ("oceania", "oceanian"), ("polynesia", "oceanian"), ("maori", "oceanian"),
    ("papua", "oceanian"), ("aboriginal", "oceanian"), ("melanesia", "oceanian"),
    # Latin American / Pre-Columbian
    ("mexico", "latin_american"), ("maya", "latin_american"), ("aztec", "latin_american"),
    ("inca", "latin_american"), ("peru", "latin_american"), ("pre-columbian", "latin_american"),
    ("mesoamerica", "latin_american"), ("brazil", "latin_american"),
    # North American
    ("united states", "north_american"), ("american", "north_american"),
    ("canada", "north_american"), ("native american", "north_american"),
    # --- City / place gazetteer (sources like AIC give a city, not a country) ---
    # South Asian places
    ("nagapattinam", "south_asian"), ("tamil nadu", "south_asian"), ("thanjavur", "south_asian"),
    ("tanjore", "south_asian"), ("madras", "south_asian"), ("chennai", "south_asian"),
    ("kolkata", "south_asian"), ("calcutta", "south_asian"), ("delhi", "south_asian"),
    ("agra", "south_asian"), ("rajasthan", "south_asian"), ("gujarat", "south_asian"),
    ("kashmir", "south_asian"), ("mysore", "south_asian"), ("kerala", "south_asian"),
    ("odisha", "south_asian"), ("orissa", "south_asian"), ("mathura", "south_asian"),
    # East Asian places
    ("kyoto", "east_asian"), ("edo", "east_asian"), ("tokyo", "east_asian"),
    ("beijing", "east_asian"), ("kingdom of joseon", "east_asian"),
    # Southeast Asian places
    ("angkor", "southeast_asian"), ("bangkok", "southeast_asian"), ("bali", "southeast_asian"),
    # West Asian places
    ("isfahan", "west_asian"), ("istanbul", "west_asian"), ("constantinople", "west_asian"),
    ("cairo", "west_asian"), ("damascus", "west_asian"),
    # African places
    ("ikere", "african"), ("ife", "african"), ("kongo", "african"), ("ashanti", "african"),
    # Latin American / Pre-Columbian places
    ("tenochtitlan", "latin_american"), ("oaxaca", "latin_american"), ("cusco", "latin_american"),
    ("cuzco", "latin_american"), ("teotihuacan", "latin_american"),
    # European cities (checked before the broad European block)
    ("paris", "european"), ("provence", "european"), ("florence", "european"),
    ("venice", "european"), ("amsterdam", "european"), ("london", "european"),
    ("madrid", "european"), ("vienna", "european"), ("rémy", "european"),
    # European (broad, checked late so specifics above win)
    ("europe", "european"), ("french", "european"), ("france", "european"),
    ("italian", "european"), ("italy", "european"), ("dutch", "european"),
    ("netherlands", "european"), ("german", "european"), ("spain", "european"),
    ("spanish", "european"), ("british", "european"), ("english", "european"),
    ("flemish", "european"), ("russian", "european"), ("austrian", "european"),
]

# Category taxonomy — lets paintings, sculpture and temple architecture share one
# corpus while staying filterable at retrieval time.
CATEGORIES: tuple[str, ...] = (
    "painting",
    "drawing_print",
    "sculpture",
    "textile",
    "ceramic",
    "architecture",   # temples, monuments
    "folk_art",
    "photograph",
    "other",
)

_CATEGORY_RULES: list[tuple[str, str]] = [
    ("temple", "architecture"), ("architect", "architecture"), ("monument", "architecture"),
    ("painting", "painting"), ("mural", "painting"),
    ("print", "drawing_print"), ("woodblock", "drawing_print"), ("drawing", "drawing_print"),
    ("etching", "drawing_print"), ("engraving", "drawing_print"),
    ("sculpture", "sculpture"), ("statue", "sculpture"), ("relief", "sculpture"),
    ("bronze", "sculpture"), ("figure", "sculpture"),
    ("textile", "textile"), ("tapestry", "textile"), ("carpet", "textile"), ("rug", "textile"),
    ("ceramic", "ceramic"), ("porcelain", "ceramic"), ("pottery", "ceramic"), ("vase", "ceramic"),
    ("photograph", "photograph"),
]


def normalize_region(*raw: str | None) -> str:
    """Map any combination of culture/place/nationality strings to a REGION.

    Accepts several candidate strings (a source may supply culture *and* place);
    the first that matches a rule wins.
    """
    haystack = " ".join(s for s in raw if s).lower()
    if not haystack.strip():
        return "unknown"
    for needle, region in _REGION_RULES:
        if needle in haystack:
            return region
    return "unknown"


def normalize_category(*raw: str | None) -> str:
    """Map a medium/classification/object-type string to a CATEGORY."""
    haystack = " ".join(s for s in raw if s).lower()
    if not haystack.strip():
        return "other"
    for needle, category in _CATEGORY_RULES:
        if needle in haystack:
            return category
    return "other"
