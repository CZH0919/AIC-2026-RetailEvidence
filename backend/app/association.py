"""Market-basket association rules and held-out completion evaluation."""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import association_rules, fpgrowth
from scipy import sparse

from .data_api import write_json


def _basket_sets(frame: pd.DataFrame) -> dict[str, set[str]]:
    compact = frame[["order_id", "item_id"]].dropna().drop_duplicates()
    grouped = compact.groupby("order_id", sort=True)["item_id"]
    return {str(order): set(items.map(str)) for order, items in grouped}


def _stable_split(order_ids: list[str], seed: int):
    rng = np.random.default_rng(seed)
    shuffled = np.array(sorted(order_ids), dtype=object)
    rng.shuffle(shuffled)
    n = len(shuffled)
    train_end = int(n * 0.6)
    valid_end = int(n * 0.8)
    return {
        "train": shuffled[:train_end].tolist(),
        "validation": shuffled[train_end:valid_end].tolist(),
        "test": shuffled[valid_end:].tolist(),
    }


def _one_hot(baskets: list[set[str]], vocabulary: list[str]):
    item_index = {item: idx for idx, item in enumerate(vocabulary)}
    rows, cols = [], []
    for row, basket in enumerate(baskets):
        for item in basket:
            col = item_index.get(item)
            if col is not None:
                rows.append(row)
                cols.append(col)
    matrix = sparse.csr_matrix(
        ([True] * len(rows), (rows, cols)), shape=(len(baskets), len(vocabulary)), dtype=bool
    )
    return pd.DataFrame.sparse.from_spmatrix(matrix, columns=vocabulary)


def _mine_rules(baskets_by_id: dict[str, set[str]], order_ids: list[str], parameters: dict):
    train_baskets = [baskets_by_id[order] for order in order_ids]
    vocabulary = sorted({item for basket in train_baskets for item in basket})
    if not train_baskets or len(vocabulary) < 2:
        return vocabulary, pd.DataFrame(), pd.DataFrame()
    encoded = _one_hot(train_baskets, vocabulary)
    denominator = len(train_baskets)
    min_support = max(parameters["min_support"], parameters["min_count"] / denominator)
    itemsets = fpgrowth(
        encoded,
        min_support=min_support,
        use_colnames=True,
        max_len=parameters["max_length"],
    )
    if itemsets.empty:
        return vocabulary, itemsets, pd.DataFrame()
    rules = association_rules(
        itemsets, metric="confidence", min_threshold=parameters["min_confidence"]
    )
    if rules.empty:
        return vocabulary, itemsets, rules
    support_lookup = {
        frozenset(row["itemsets"]): int(round(float(row["support"]) * denominator))
        for _, row in itemsets.iterrows()
    }
    rows = []
    for _, row in rules.iterrows():
        antecedents = frozenset(row["antecedents"])
        consequents = frozenset(row["consequents"])
        if not antecedents or not consequents or antecedents & consequents:
            continue
        rows.append(
            {
                "antecedents": " | ".join(sorted(antecedents)),
                "consequents": " | ".join(sorted(consequents)),
                "antecedent_items": sorted(antecedents),
                "consequent_items": sorted(consequents),
                "support": float(row["support"]),
                "confidence": float(row["confidence"]),
                "lift": float(row["lift"]),
                "n_ab": support_lookup.get(antecedents | consequents, 0),
                "n_a": support_lookup.get(antecedents, 0),
                "n_b": support_lookup.get(consequents, 0),
                "denominator": denominator,
            }
        )
    result = pd.DataFrame(rows)
    if result.empty:
        return vocabulary, itemsets, result
    result = result.sort_values(
        ["confidence", "lift", "n_ab", "antecedents", "consequents"],
        ascending=[False, False, False, True, True],
    ).reset_index(drop=True)
    if len(result) > 20000:
        result = result.head(20000).copy()
    return vocabulary, itemsets, result


def _recommend(known: set[str], rules: pd.DataFrame, vocabulary: set[str]) -> list[str]:
    scores: dict[str, tuple[float, float, int, str]] = {}
    for _, row in rules.iterrows():
        antecedents = set(row["antecedent_items"])
        if not antecedents.issubset(known):
            continue
        for item in row["consequent_items"]:
            if item in known or item not in vocabulary:
                continue
            score = (float(row["confidence"]), float(row["lift"]), int(row["n_ab"]), item)
            if item not in scores or score > scores[item]:
                scores[item] = score
    ranked = sorted(scores.values(), key=lambda value: (-value[0], -value[1], -value[2], value[3]))
    return [item for *_score, item in ranked[:5]]


def _evaluate(
    split_name: str,
    baskets_by_id: dict[str, set[str]],
    order_ids: list[str],
    vocabulary: list[str],
    rules: pd.DataFrame,
    popularity: list[str],
    seed: int,
):
    vocab = set(vocabulary)
    rng = np.random.default_rng(seed)
    cases = []
    hits = rule_recommendations = pop_hits = pop_recommendations = 0
    for order in sorted(order_ids):
        basket = sorted(baskets_by_id[order])
        if len(basket) < 2:
            continue
        target = basket[int(rng.integers(0, len(basket)))]
        known = set(basket) - {target}
        projected_known = known & vocab
        recs = _recommend(projected_known, rules, vocab) if projected_known else []
        pop = [item for item in popularity if item not in known][:5]
        hit = target in recs
        pop_hit = target in pop
        hits += int(hit)
        pop_hits += int(pop_hit)
        rule_recommendations += int(bool(recs))
        pop_recommendations += int(bool(pop))
        cases.append(
            {
                "order_id": order,
                "target": target,
                "known": sorted(known),
                "recommendations": recs,
            }
        )
    total = len(cases)
    return {
        "split": split_name,
        "baskets": total,
        "precision_at_5": hits / (total * 5) if total else None,
        "recall_at_5": hits / total if total else None,
        "hit_rate_at_5": hits / total if total else None,
        "recommendation_coverage": rule_recommendations / total if total else None,
        "popularity_hit_rate_at_5": pop_hits / total if total else None,
        "popularity_coverage": pop_recommendations / total if total else None,
        "cases": cases[:200],
    }


def process_association(job, progress):
    output = Path(job["output"])
    parameters = job["analysis_input"]["parameters"]
    progress("preparing_baskets", 10)
    frame = pd.read_parquet(job["source"])
    baskets_by_id = _basket_sets(frame)
    order_ids = sorted(baskets_by_id)
    split = _stable_split(order_ids, parameters["random_state"])

    progress("mining_rules", 35)
    vocabulary, itemsets, rules = _mine_rules(baskets_by_id, split["train"], parameters)
    if not itemsets.empty:
        export_itemsets = itemsets.copy()
        export_itemsets["itemsets"] = export_itemsets["itemsets"].map(
            lambda values: " | ".join(sorted(values))
        )
        export_itemsets.to_csv(output / "frequent_itemsets.csv", index=False)
    else:
        pd.DataFrame(columns=["support", "itemsets"]).to_csv(
            output / "frequent_itemsets.csv", index=False
        )

    export_rules = rules.drop(columns=["antecedent_items", "consequent_items"], errors="ignore")
    export_rules.to_csv(output / "association_rules.csv", index=False)

    progress("evaluating_rules", 68)
    train_counts: dict[str, int] = {}
    for order in split["train"]:
        for item in baskets_by_id[order]:
            train_counts[item] = train_counts.get(item, 0) + 1
    popularity = sorted(train_counts, key=lambda item: (-train_counts[item], item))
    evaluations = [
        _evaluate(
            "validation", baskets_by_id, split["validation"], vocabulary, rules, popularity, 42
        ),
        _evaluate("test", baskets_by_id, split["test"], vocabulary, rules, popularity, 43),
    ]
    with (output / "completion_evaluation.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "split",
                "baskets",
                "precision_at_5",
                "recall_at_5",
                "hit_rate_at_5",
                "recommendation_coverage",
                "popularity_hit_rate_at_5",
                "popularity_coverage",
            ],
        )
        writer.writeheader()
        for row in evaluations:
            writer.writerow({key: row[key] for key in writer.fieldnames})

    progress("writing_results", 88)
    n_baskets = len(order_ids)
    reasons = []
    if n_baskets < 200:
        reasons.append("完整购物篮少于 200 个。")
    if len(vocabulary) < 2:
        reasons.append("训练集商品种类不足。")
    if rules.empty:
        reasons.append("当前阈值下没有形成关联规则。")
    report = {
        "context": job["context"],
        "analysis": {
            "kind": "association",
            "random_state": parameters["random_state"],
            "min_support": max(
                parameters["min_support"],
                parameters["min_count"] / max(1, len(split["train"])),
            ),
            "min_count": parameters["min_count"],
            "min_confidence": parameters["min_confidence"],
            "max_length": parameters["max_length"],
        },
        "summary": {
            "baskets": n_baskets,
            "train_baskets": len(split["train"]),
            "validation_baskets": len(split["validation"]),
            "test_baskets": len(split["test"]),
            "items": len(vocabulary),
            "itemsets": int(len(itemsets)),
            "rules": int(len(rules)),
            "publishable": not reasons,
            "reasons": reasons,
        },
        "top_rules": rules.head(50).drop(
            columns=["antecedent_items", "consequent_items"], errors="ignore"
        ).to_dict("records"),
        "evaluations": [
            {key: value for key, value in row.items() if key != "cases"}
            for row in evaluations
        ],
        "artifacts": {
            "rules": "association_rules.csv",
            "itemsets": "frequent_itemsets.csv",
            "evaluation": "completion_evaluation.csv",
        },
    }
    write_json(output / "association_report.json", report)
    progress("publishing", 96)
    return report
