"""Read the downloaded NCSE v2.0 files into one table per periodical.

What an NCSE "entry" is (see reports/01-data-inspection.md):
each row of the NCSE files is one *box* on a printed page, found by a layout
model and read by an OCR model. A box has a class (text, title, figure, table),
a place in the page's reading order, and its OCR text. The text type and topic
labels are stored in separate files and are joined here by the box identifier
(`bbox_uid` = page_id + "_" + box_page_id).
"""

import json
from pathlib import Path

import polars as pl


def _mapping(raw: Path, name: str) -> dict[int, str]:
    data = json.loads((raw / "class_mappings" / name).read_text())
    return {int(k): v for k, v in data.items()}


def load_boxes(cfg: dict, periodical: dict, all_series: bool = False) -> pl.DataFrame:
    """All boxes of one periodical with their labels, in reading order.

    Columns added to the NCSE ones:
      bbox_uid, series, issue_date, n_chars,
      text_type (name), topics (list of names), selected (bool: meets D-002).
    Only the configured issue series are kept unless all_series=True.
    """
    raw: Path = cfg["paths"]["raw"]
    name = periodical["file"]
    boxes = pl.read_parquet(raw / "NCSE_v2" / "post_processed" / f"{name}_issue_PDF_files.parquet")
    types = pl.read_parquet(
        raw / "classification_data" / "text_type_classified" / f"classified_{name}_issue_PDF_files.parquet"
    )
    topics = pl.read_parquet(
        raw / "classification_data" / "IPTC_type_classified" / f"classified_{name}_issue_PDF_files.parquet"
    )

    type_names = _mapping(raw, "text_type_class_mapping.json")
    topic_names = _mapping(raw, "IPTC_class_mapping.json")

    types = types.select(
        "bbox_uid",
        text_type=pl.col("predicted_class").replace_strict(type_names, return_dtype=pl.String),
    )
    # Topics are multi-label: column class_<k> is 1 when topic k applies to the box.
    topics = topics.select(
        "bbox_uid",
        topics=pl.concat_list(
            [pl.when(pl.col(f"class_{k}") == 1).then(pl.lit(v)) for k, v in sorted(topic_names.items())]
        ).list.drop_nulls(),
    )

    boxes = boxes.with_columns(
        bbox_uid=pl.col("page_id") + "_" + pl.col("box_page_id"),
        series=pl.col("issue_id").str.extract(r"^([A-Z]+)-"),
        issue_date=pl.col("issue_id").str.extract(r"-(\d{4}-\d{2}-\d{2})$"),
        n_chars=pl.col("content").str.len_chars(),
    )
    n = boxes.height
    boxes = boxes.join(types, on="bbox_uid", how="left").join(topics, on="bbox_uid", how="left")
    if boxes.height != n or boxes["text_type"].null_count() or boxes["topics"].null_count():
        raise ValueError(f"{name}: labels do not join one-to-one with boxes")

    sel = cfg["selection"]
    boxes = boxes.with_columns(
        selected=(pl.col("text_type") == sel["text_type"]) & pl.col("topics").list.contains(sel["topic"])
    )
    if not all_series:
        boxes = boxes.filter(pl.col("series").is_in(periodical["series"]))
    return boxes.sort("issue_id", "page_number", "reading_order")
