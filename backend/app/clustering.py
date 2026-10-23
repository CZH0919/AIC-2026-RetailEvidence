"""Customer RF/RFM clustering from published quality views."""

from __future__ import annotations

import csv
from decimal import Decimal
from math import ceil
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, RobustScaler

from .data_api import write_json


def _reference_time(frame: pd.DataFrame, quality_parameters: dict) -> pd.Timestamp:
    scope = quality_parameters.get("scope", {})
    if scope.get("date_end"):
        return pd.Timestamp(scope["date_end"], tz="UTC") + pd.Timedelta(days=1)
    latest = pd.to_datetime(frame["event_time"], utc=True).max()
    return latest.normalize() + pd.Timedelta(days=1)


def _decimal_sum(values) -> str:
    total = Decimal("0")
    for value in values:
        if value is not None and value == value:
            total += Decimal(str(value))
    return format(total, "f")


def _make_features(
    frame: pd.DataFrame, kind: str, quality_parameters: dict
) -> tuple[pd.DataFrame, str]:
    frame = frame.copy()
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True)
    reference = _reference_time(frame, quality_parameters)
    grouped = frame.groupby("customer_id", sort=True)
    features = grouped.agg(
        last_purchase=("event_time", "max"),
        frequency=("order_id", "nunique"),
    ).reset_index()
    features["recency_days"] = (
        (reference - features["last_purchase"]).dt.total_seconds() / 86400
    ).clip(lower=0).astype(int)
    if kind == "rfm":
        money = grouped["amount"].agg(_decimal_sum).reset_index(name="monetary")
        features = features.merge(money, on="customer_id", how="left")
        features["monetary_value"] = features["monetary"].map(lambda value: float(Decimal(value)))
    else:
        features["monetary"] = None
    return features, reference.isoformat()


def _candidate_model(values: np.ndarray, labels_count: int, random_state: int, n_init: int):
    return make_pipeline(
        FunctionTransformer(np.log1p, validate=False),
        RobustScaler(),
        KMeans(n_clusters=labels_count, random_state=random_state, n_init=n_init),
    ).fit(values)


def _score_candidate(values: np.ndarray, labels: np.ndarray, sample_seed: int) -> float | None:
    if len(set(labels.tolist())) < 2 or len(labels) <= len(set(labels.tolist())):
        return None
    sample_size = min(2000, len(labels))
    if sample_size < len(labels):
        rng = np.random.default_rng(sample_seed)
        sample = rng.choice(len(labels), sample_size, replace=False)
        return float(silhouette_score(values[sample], labels[sample]))
    return float(silhouette_score(values, labels))


def process_clustering(job, progress):
    progress("building_features", 8)
    output = Path(job["output"])
    parameters = job["analysis_input"]["parameters"]
    analysis_kind = parameters["kind"]
    frame = pd.read_parquet(job["source"])
    quality_parameters = job["analysis_input"]["quality_manifest"]["parameters"]
    features, reference_time = _make_features(frame, analysis_kind, quality_parameters)
    feature_names = ["recency_days", "frequency"]
    if analysis_kind == "rfm":
        feature_names.append("monetary_value")
    model_values = features[feature_names].to_numpy(dtype=float)
    visible_columns = ["customer_id", "recency_days", "frequency", "monetary"]
    if analysis_kind == "rfm":
        visible_columns.append("monetary_value")
    visible = features[visible_columns].copy()
    pq.write_table(
        pa.Table.from_pandas(visible, preserve_index=False),
        output / "customer_features.parquet",
    )

    progress("fitting_candidates", 24)
    n_customers = len(features)
    unique_vectors = int(
        pd.DataFrame(model_values, columns=feature_names).drop_duplicates().shape[0]
    )
    cluster_floor = max(5, ceil(n_customers * 0.01))
    candidates = []
    best = None
    if n_customers >= 2 and unique_vectors >= 2:
        k_max = min(parameters["k_max"], n_customers, unique_vectors)
        for k in range(parameters["k_min"], k_max + 1):
            model = _candidate_model(
                model_values, k, parameters["random_state"], parameters["n_init"]
            )
            labels = model.predict(model_values)
            counts = pd.Series(labels).value_counts().sort_index()
            silhouette = _score_candidate(model_values, labels, parameters["random_state"] + k)
            ari_values = []
            if n_customers >= 10:
                for offset in range(5):
                    rng = np.random.default_rng(parameters["random_state"] + 100 + offset)
                    sample = np.sort(
                        rng.choice(n_customers, max(2, int(n_customers * 0.8)), replace=False)
                    )
                    sub_model = _candidate_model(
                        model_values[sample],
                        k,
                        parameters["random_state"] + 10 + offset,
                        parameters["n_init"],
                    )
                    sub_labels = sub_model.predict(model_values[sample])
                    ari_values.append(float(adjusted_rand_score(labels[sample], sub_labels)))
            ari_median = float(np.median(ari_values)) if ari_values else None
            publishable = (
                counts.min() >= cluster_floor
                and silhouette is not None
                and silhouette >= 0.15
                and (ari_median is None or ari_median >= 0.65)
            )
            row = {
                "k": k,
                "cluster_count": int(len(counts)),
                "min_cluster_size": int(counts.min()),
                "silhouette": silhouette,
                "ari_median": ari_median,
                "publishable": publishable,
            }
            candidates.append(row)
            if best is None or (
                row["publishable"],
                row["silhouette"] if row["silhouette"] is not None else -1,
                -row["k"],
            ) > (
                best["publishable"],
                best["silhouette"] if best["silhouette"] is not None else -1,
                -best["k"],
            ):
                best = {**row, "labels": labels}

    progress("writing_results", 72)
    if best is None:
        assignments = visible.copy()
        assignments["cluster"] = None
        clusters = []
    else:
        assignments = visible.copy()
        assignments["cluster"] = best["labels"].astype(int)
        clusters = []
        for cluster_id, group in assignments.groupby("cluster", sort=True):
            clusters.append(
                {
                    "cluster": int(cluster_id),
                    "customers": int(len(group)),
                    "share": round(len(group) / n_customers, 6),
                    "recency_median": float(group["recency_days"].median()),
                    "frequency_median": float(group["frequency"].median()),
                    "monetary_median": (
                        float(group["monetary_value"].median()) if analysis_kind == "rfm" else None
                    ),
                }
            )
    assignments.to_csv(output / "cluster_assignments.csv", index=False)
    with (output / "cluster_candidates.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "k",
                "cluster_count",
                "min_cluster_size",
                "silhouette",
                "ari_median",
                "publishable",
            ],
        )
        writer.writeheader()
        writer.writerows(candidates)

    reasons = []
    if n_customers < 50:
        reasons.append("有效客户少于 50 个。")
    if unique_vectors < 2:
        reasons.append("客户特征几乎没有差异。")
    if best and not best["publishable"]:
        if best["min_cluster_size"] < cluster_floor:
            reasons.append("至少一个群体规模过小。")
        if best["silhouette"] is None or best["silhouette"] < 0.15:
            reasons.append("群体区分度不足。")
        if best["ari_median"] is not None and best["ari_median"] < 0.65:
            reasons.append("重复抽样后的结果不够稳定。")
    if not candidates:
        reasons.append("没有可评估的候选分群数。")
    publishable = bool(best and best["publishable"] and n_customers >= 50 and unique_vectors >= 2)
    report = {
        "context": job["context"],
        "analysis": {
            "kind": analysis_kind,
            "mode": analysis_kind.upper(),
            "feature_names": feature_names,
            "reference_time": reference_time,
            "random_state": parameters["random_state"],
            "n_init": parameters["n_init"],
        },
        "summary": {
            "customers": int(n_customers),
            "unique_feature_vectors": unique_vectors,
            "selected_k": int(best["k"]) if best else None,
            "publishable": publishable,
            "reasons": [] if publishable else reasons,
        },
        "candidates": [{k: v for k, v in row.items() if k != "labels"} for row in candidates],
        "clusters": clusters,
        "quality_capability": job["analysis_input"]["capability"],
        "artifacts": {
            "features": "customer_features.parquet",
            "assignments": "cluster_assignments.csv",
            "candidates": "cluster_candidates.csv",
        },
    }
    write_json(output / "cluster_report.json", report)
    progress("publishing", 96)
    return report
