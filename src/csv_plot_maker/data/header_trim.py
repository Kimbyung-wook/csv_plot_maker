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

    seen = {name: 0 for name in reserved}
    deduped = []
    for name in trimmed:
        if name not in seen:
            seen[name] = 0
            deduped.append(name)
        else:
            seen[name] += 1
            deduped.append(f"{name}_{seen[name]}")
    return deduped
