"""Market-basket association rules and held-out completion evaluation."""

from __future__ import annotations

import csv
import math
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
    return vocabulary, itemsets, result


def _wilson(successes, trials):
    if not trials:
        return 0.0, 1.0
    z = 1.959963984540054
    p = successes / trials
    denominator = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denominator
    margin = z * math.sqrt(p * (1 - p) / trials + z * z / (4 * trials * trials)) / denominator
    return max(0, center - margin), min(1, center + margin)


def _qualified_rules(rules, baskets, validation_ids):
    rows = []
    validation = [baskets[k] for k in validation_ids]
    for _, raw in rules.iterrows():
        row = raw.to_dict()
        a, b = set(row["antecedent_items"]), set(row["consequent_items"])
        n_a = sum(a <= basket for basket in validation)
        n_b = sum(b <= basket for basket in validation)
        n_ab = sum(a | b <= basket for basket in validation)
        n = len(validation)
        validation_lift = n_ab * n / (n_a * n_b) if n_a and n_b else 0
        lower, upper = _wilson(row["n_ab"], row["n_a"])
        leverage = row["support"] - row["n_a"] * row["n_b"] / row["denominator"] ** 2
        row.update(
            leverage=leverage,
            confidence_lower=lower,
            confidence_upper=upper,
            validation_n_a=n_a,
            validation_n_b=n_b,
            validation_n_ab=n_ab,
            validation_denominator=n,
            validation_lift=validation_lift,
        )
        if (
            row["lift"] > 1
            and leverage > 0
            and lower > row["n_b"] / row["denominator"]
            and n_ab >= 3
            and validation_lift > 1
        ):
            rows.append(row)
    if not rows:
        return rules.head(0).copy()
    return (
        pd.DataFrame(rows)
        .sort_values(
            ["confidence_lower", "leverage", "n_ab", "lift", "antecedents", "consequents"],
            ascending=[False, False, False, False, True, True],
        )
        .reset_index(drop=True)
    )


def _card_rules(rules):
    result, seen, appearances = [], set(), {}
    for _, row in rules.iterrows():
        union = tuple(sorted(set(row["antecedent_items"]) | set(row["consequent_items"])))
        if union in seen or any(appearances.get(item, 0) >= 5 for item in union):
            continue
        seen.add(union)
        for item in union:
            appearances[item] = appearances.get(item, 0) + 1
        result.append(row.to_dict())
        if len(result) >= 50:
            break
    return result


def _recommend(known: set[str], rules: pd.DataFrame, vocabulary: set[str]) -> list[str]:
    scores: dict[str, tuple[float, float, int, str]] = {}
    for _, row in rules.iterrows():
        antecedents = set(row["antecedent_items"])
        if not antecedents.issubset(known):
            continue
        for item in row["consequent_items"]:
            if item in known or item not in vocabulary:
                continue
            score = (
                float(row.get("confidence_lower", row["confidence"])),
                float(row["lift"]),
                int(row["n_ab"]),
                item,
            )
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
    order_blocks=None,
):
    vocab = set(vocabulary)
    rng = np.random.default_rng(seed)
    cases = []
    hits = rule_recommendations = pop_hits = pop_recommendations = hybrid_hits = 0
    lengths, hybrid_lengths, differences = [], [], []
    strata = {"popular": [], "other": []}
    paired_blocks = {}
    head = set(popularity[: max(1, int(len(popularity) * 0.2))])
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
        hybrid = (recs + [item for item in pop if item not in recs])[:5]
        hybrid_hits += int(target in hybrid)
        lengths.append(len(recs))
        hybrid_lengths.append(len(hybrid))
        differences.append(int(hit) - int(pop_hit))
        block = (order_blocks or {}).get(order, order)
        paired_blocks.setdefault(block, []).append(int(hit) - int(pop_hit))
        strata["popular" if target in head else "other"].append((int(hit), int(pop_hit)))
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
                "popularity": pop,
                "hybrid": hybrid,
                "paired_difference": int(hit) - int(pop_hit),
            }
        )
    total = len(cases)
    interval = None
    if len(paired_blocks) >= 20:
        sums = np.asarray([sum(v) for v in paired_blocks.values()])
        sizes = np.asarray([len(v) for v in paired_blocks.values()])
        draws = np.random.default_rng(seed + 1000).integers(0, len(sums), (500, len(sums)))
        estimates = sums[draws].sum(axis=1) / sizes[draws].sum(axis=1)
        interval = {
            "lower": float(np.quantile(estimates, 0.025)),
            "upper": float(np.quantile(estimates, 0.975)),
            "blocks": len(sums),
            "method": "paired_block_bootstrap_500",
        }
    return {
        "split": split_name,
        "baskets": total,
        "precision_at_5": hits / (total * 5) if total else None,
        "recall_at_5": hits / total if total else None,
        "hit_rate_at_5": hits / total if total else None,
        "recommendation_coverage": rule_recommendations / total if total else None,
        "popularity_hit_rate_at_5": pop_hits / total if total else None,
        "popularity_coverage": pop_recommendations / total if total else None,
        "hybrid_hit_rate_at_5": hybrid_hits / total if total else None,
        "mean_list_length": float(np.mean(lengths)) if total else None,
        "hybrid_mean_list_length": float(np.mean(hybrid_lengths)) if total else None,
        "paired_hit_difference": float(np.mean(differences)) if total else None,
        "paired_difference_interval": interval,
        "strata": {
            k: {
                "cases": len(v),
                "rule_hit_rate": float(np.mean([a for a, _ in v])) if v else None,
                "popular_hit_rate": float(np.mean([b for _, b in v])) if v else None,
            }
            for k, v in strata.items()
        },
        "cases": cases[:200],
    }


def process_association(job, progress):
    output = Path(job["output"])
    parameters = job["analysis_input"]["parameters"]
    progress("preparing_baskets", 10)
    frame = pd.read_parquet(job["source"])
    baskets_by_id = _basket_sets(frame)
    order_ids = sorted(baskets_by_id)
    split_mode = "random_60_20_20"
    split = _stable_split(order_ids, parameters["random_state"])
    if "event_time" in frame and frame["event_time"].notna().all():
        times = frame.groupby("order_id")["event_time"].agg(["min", "max"])
        if (times["min"] == times["max"]).all():
            ordered = sorted(order_ids, key=lambda k: (times.loc[k, "min"], k))
            unique_times = sorted(set(times["min"]))
            if len(unique_times) >= 10:
                cut1 = unique_times[min(len(unique_times) - 1, int(len(unique_times) * 0.6))]
                cut2 = unique_times[min(len(unique_times) - 1, int(len(unique_times) * 0.8))]
                split = {
                    "train": [k for k in ordered if times.loc[k, "min"] < cut1],
                    "validation": [k for k in ordered if cut1 <= times.loc[k, "min"] < cut2],
                    "test": [k for k in ordered if times.loc[k, "min"] >= cut2],
                }
                split_mode = "chronological_by_order_time"

    progress("mining_rules", 35)
    vocabulary, itemsets, rules = _mine_rules(baskets_by_id, split["train"], parameters)
    mined_count = len(rules)
    rules = _qualified_rules(rules, baskets_by_id, split["validation"])
    cards = _card_rules(rules)
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
    order_blocks = None
    block_basis = "order"
    if "customer_id" in frame and frame["customer_id"].notna().all():
        order_blocks = frame.groupby("order_id")["customer_id"].first().astype(str).to_dict()
        block_basis = "customer"
    elif split_mode.startswith("chronological"):
        order_blocks = {
            k: str(pd.Timestamp(times.loc[k, "min"]).date().isocalendar()[:2]) for k in order_ids
        }
        block_basis = "calendar_week"
    evaluations = [
        _evaluate(
            "validation",
            baskets_by_id,
            split["validation"],
            vocabulary,
            rules,
            popularity,
            42,
            order_blocks,
        ),
        _evaluate(
            "test", baskets_by_id, split["test"], vocabulary, rules, popularity, 43, order_blocks
        ),
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
            "version": "association-v2",
            "split_mode": split_mode,
            "comparison_block_basis": block_basis,
        },
        "summary": {
            "baskets": n_baskets,
            "train_baskets": len(split["train"]),
            "validation_baskets": len(split["validation"]),
            "test_baskets": len(split["test"]),
            "items": len(vocabulary),
            "itemsets": int(len(itemsets)),
            "rules": int(len(rules)),
            "mined_rules": mined_count,
            "displayed_rules": len(cards),
            "publishable": not reasons,
            "reasons": reasons,
        },
        "top_rules": [
            {k: v for k, v in row.items() if k not in {"antecedent_items", "consequent_items"}}
            for row in cards
        ],
        "notice": "这些是历史共同购买的线索，不能保证组合销售带来收益。",
        "evaluation_notice": "按订单日期先后检验。"
        if split_mode.startswith("chronological")
        else "订单未提供可靠日期，使用固定随机留出；结果不代表未来表现。",
        "reliability_notice": "比例范围辅助判断单组订单证据，不证明因果或排除偶然结果。",
        "evaluations": [
            {key: value for key, value in row.items() if key != "cases"} for row in evaluations
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
