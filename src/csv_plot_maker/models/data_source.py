from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from csv_plot_maker.data.column_store import ColumnStore

# A small, fixed sequence of muted background tints -- deliberately distinct
# from the saturated per-series line-color palette (style_map.next_default_color)
# so a "which file is this from" background tint never gets mistaken for a
# curve's own color. Cycles once more than 8 files are open.
SOURCE_COLOR_PALETTE = [
    "#dbeafe",  # blue
    "#dcfce7",  # green
    "#fef3c7",  # amber
    "#fce7f3",  # pink
    "#ede9fe",  # violet
    "#fee2e2",  # red
    "#e0f2fe",  # cyan
    "#f3f4f6",  # neutral gray
]


def color_for_index(index: int) -> str:
    return SOURCE_COLOR_PALETTE[index % len(SOURCE_COLOR_PALETTE)]


# Series.source_id's default -- also what a pre-multi-CSV-era saved layout's
# series always have, since source_id didn't exist yet when they were
# written (see ProjectState.reconcile_data_sources, which remaps this
# sentinel to whichever file is open in that fallback case). Named here
# instead of comparing to a bare "" at each call site, since both files rely
# on the same convention with no other structural link between them.
UNASSIGNED_SOURCE_ID = ""


@dataclass
class DataSource:
    """One loaded CSV file: its columns plus the identity needed to tell it
    apart from every other loaded file once more than one is open at a time.

    `id` (not `path`) is what `Series`/`SubplotConfig` reference, since the
    same path could in principle be reopened after being closed and should
    read as a fresh source rather than silently reattaching old series to it.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    path: str = ""
    label: str = ""
    color: str = field(default_factory=lambda: color_for_index(0))
    store: ColumnStore | None = None


@dataclass
class SourceRef:
    """A DataSource's identity as recorded in a saved layout: enough to find
    or re-open the same file and reproduce its label/color, without carrying
    along its `ColumnStore` (which is never serialized -- it's rebuilt fresh
    from the file itself on every load).
    """

    id: str
    path: str
    label: str
    color: str

    @classmethod
    def from_source(cls, source: DataSource) -> SourceRef:
        return cls(id=source.id, path=source.path, label=source.label, color=source.color)
