from __future__ import annotations


def trim_headers(names: list[str], keywords: list[str], reserved: tuple[str, ...] = ("Sequential",)) -> list[str]:
    """Remove every occurrence of each keyword substring from each header name.

    Real-world CSV exports often prefix/suffix every column with a fixed,
    noisy token (a message namespace like "AVS_TC_AILDA::", a decoded-field
    marker like "_Value", a stray leading space from a ", " separator) that
    the user wants stripped for readability. Keywords are applied in list
    order, each as a plain substring removal (no regex) -- simplest to
    reason about for a manually-curated list.

    Collisions (two different original names trimming down to the same
    result, or a trim landing on a name already reserved for a synthetic
    column) are disambiguated with a numeric suffix rather than silently
    overwriting one column with another.
    """
    trimmed = []
    for name in names:
        result = name
        for keyword in keywords:
            if keyword:
                result = result.replace(keyword, "")
        trimmed.append(result or name)

    used = set(reserved)
    counts: dict[str, int] = {}
    deduped = []
    for name in trimmed:
        candidate = name
        # A bumped suffix can itself collide with another trimmed name that
        # already happens to look like "<name>_<n>" (e.g. one column trims to
        # "RESERVED" while another already reads "RESERVED_2") -- keep
        # bumping until the candidate is actually free instead of assuming
        # the first bump is unused.
        while candidate in used:
            counts[name] = counts.get(name, 0) + 1
            candidate = f"{name}_{counts[name]}"
        used.add(candidate)
        deduped.append(candidate)
    return deduped
