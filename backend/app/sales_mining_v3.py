"""Rolling evaluation and strictly past-only anomaly evidence."""

from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest

from .sales_mining_baseline import calendar as calendar

MODEL_VERSION = "sales-v3.0.0"
METHODS = [
    "gradient_boosting",
    "last_week",
    "four_week_mean",
    "exponential_smoothing",
    "croston_sba",
]


def features(values, origin, dates=None):
    past = np.asarray(values[:origin], dtype=float)
    recent = past[-28:]
    scale = max(float(recent.mean()), 0.1)
    weeks = recent.reshape(4, 7).sum(axis=1)
    nonzero = np.flatnonzero(past > 0)
    gaps = np.diff(nonzero[-20:])
    vector = [
        float(past[-7:].mean()) / scale,
        float(past[-14:].mean()) / scale,
        float(recent.std()) / scale,
        float(np.count_nonzero(recent)) / 28,
        float(past[-14:-7].mean()) / scale,
        float(recent.max()) / scale,
        min(origin - 1 - int(nonzero[-1]) if len(nonzero) else 28, 90) / 28,
        float(weeks[-1] - weeks[0]) / (scale * 7),
        float(np.median(gaps)) / 28 if len(gaps) else 1,
    ]
    if dates is not None:
        current = dates[origin] if origin < len(dates) else dates[-1] + timedelta(days=1)
        vector += [current.weekday() / 6, current.month / 12]
    return vector, scale


def score(actual, predicted):
    a, p = np.asarray(actual, dtype=float), np.asarray(predicted, dtype=float)
    return {
        "mae": float(np.abs(a - p).mean()) if len(a) else None,
        "wape": float(np.abs(a - p).sum() / a.sum()) if a.sum() else None,
        "bias": float((p - a).mean()) if len(a) else None,
        "samples": len(a),
    }


def _stratum(past):
    recent = past[-28:]
    return ("intermittent" if np.count_nonzero(recent) < 14 else "regular") + (
        "_small" if np.mean(recent) < 5 else "_large"
    )


def _simple(past):
    past = past[np.isfinite(past)]
    level = float(past[0])
    for value in past[1:]:
        level += 0.2 * (value - level)
    positive = np.flatnonzero(past > 0)
    croston = 0.0
    if len(positive):
        demand, interval = float(past[positive[0]]), float(positive[0] + 1)
        last = positive[0]
        for t in positive[1:]:
            demand += 0.1 * (past[t] - demand)
            interval += 0.1 * (t - last - interval)
            last = t
        croston = 0.95 * demand / interval * 7
    return {
        "last_week": float(past[-7:].sum()),
        "four_week_mean": float(past[-28:].sum() / 4),
        "exponential_smoothing": max(0, level * 7),
        "croston_sba": max(0, croston),
    }


def _model(series, keys, origin, dates):
    x, y = [], []
    for key in keys:
        values = series[key]
        finite = np.flatnonzero(np.isfinite(values))
        first = int(finite[0]) if len(finite) else origin
        for t in range(max(first + 28, origin - 180), origin - 6, 7):
            if not np.isfinite(values[t - 28 : t + 7]).all():
                continue
            f, scale = features(values, t, dates)
            x.append(f)
            y.append(float(values[t : t + 7].sum()) / (scale * 7))
    if len(x) < 30:
        return None
    return HistGradientBoostingRegressor(
        max_iter=80,
        max_leaf_nodes=15,
        min_samples_leaf=15,
        l2_regularization=2,
        random_state=42,
        early_stopping=False,
    ).fit(x, y)


def forecast_series(series, dates, progress=lambda *_: None):
    result = {
        "version": MODEL_VERSION,
        "horizon_days": 7,
        "status": "unavailable",
        "reason": "需要至少 90 天完整日记录，并有足够重复成交。",
        "predictions": {},
        "eligible_items": 0,
        "tested_items": 0,
        "metrics": [],
        "cutoffs": [],
    }
    n = len(dates)
    if n < 90:
        return result
    arrays = {k: np.asarray(v, dtype=float) for k, v in series.items()}
    validation_count = min(12, max(1, (n - 56) // 7 - 3))
    calibration_count = 20 if n >= 56 + (validation_count + 23) * 7 else 0
    origins = list(range(n - (validation_count + calibration_count + 3) * 7, n, 7))
    selection = origins[0]
    candidates = {
        k: v
        for k, v in arrays.items()
        if np.isfinite(v[selection - 28 : selection]).all()
        and np.count_nonzero(v[selection - 28 : selection]) >= 4
        and np.isfinite(v[np.flatnonzero(np.isfinite(v))[0] : selection]).all()
    }
    keys = sorted(
        candidates, key=lambda k: (-float(candidates[k][selection - 28 : selection].sum()), k)
    )[:1000]
    final_eligible = {
        k
        for k in keys
        if np.isfinite(arrays[k][-90:]).all() and np.count_nonzero(arrays[k][-28:]) >= 4
    }
    result.update(
        eligible_items=len(final_eligible),
        tested_items=len(keys),
        historical_candidates=len(candidates),
        resource_excluded_items=max(0, len(candidates) - len(keys)),
        selection_origin=dates[selection].isoformat(),
        validation_origins=validation_count,
        calibration_origins=calibration_count,
        excluded_missing_or_short=len(arrays) - len(final_eligible),
    )
    if not keys:
        return result
    records = []
    for index, origin in enumerate(origins):
        progress("forecasting", 35 + int(index * 30 / len(origins)))
        model = _model(arrays, keys, origin, dates)
        usable = [
            k
            for k in keys
            if np.isfinite(arrays[k][np.flatnonzero(np.isfinite(arrays[k]))[0] : origin + 7]).all()
        ]
        fs = [features(arrays[k], origin, dates) for k in usable]
        estimates_gb = model.predict([f for f, _ in fs]) if model is not None and fs else None
        for j, key in enumerate(usable):
            values = arrays[key]
            estimates = _simple(values[:origin])
            estimates["gradient_boosting"] = (
                max(0, float(estimates_gb[j])) * fs[j][1] * 7
                if estimates_gb is not None
                else estimates["four_week_mean"]
            )
            records.append(
                {
                    "item_id": key,
                    "origin": dates[origin].isoformat(),
                    "training_label_end": dates[origin - 1].isoformat(),
                    "target_end": dates[origin + 6].isoformat(),
                    "split": "validation"
                    if index < validation_count
                    else (
                        "calibration" if index < validation_count + calibration_count else "test"
                    ),
                    "stratum": _stratum(values[:origin]),
                    "actual": float(values[origin : origin + 7].sum()),
                    "gradient_fitted": model is not None,
                    **estimates,
                }
            )
    validation = [r for r in records if r["split"] == "validation"]
    test = [r for r in records if r["split"] == "test"]
    if not validation or not test:
        result["reason"] = "可回测的历史样本不足，暂不发布预测。"
        return result
    available_methods = [
        m
        for m in METHODS
        if m != "gradient_boosting" or all(r["gradient_fitted"] for r in validation + test)
    ]
    metrics = [
        {
            "method": method,
            "split": split,
            **score([r["actual"] for r in rows], [r[method] for r in rows]),
        }
        for split, rows in [("validation", validation), ("test", test)]
        for method in available_methods
    ]

    def error(rows, method):
        return score([r["actual"] for r in rows], [r[method] for r in rows])["mae"]

    baseline = min(
        [m for m in METHODS[:3] if m in available_methods],
        key=lambda m: (error(validation, m), METHODS.index(m)),
    )
    selection_rules = {}
    for stratum in ["all", *sorted({r["stratum"] for r in validation})]:
        rows = (
            validation if stratum == "all" else [r for r in validation if r["stratum"] == stratum]
        )
        if stratum != "all" and (len(rows) < 30 or len({r["origin"] for r in rows}) < 6):
            continue
        allowed = (
            METHODS if stratum.startswith("intermittent") or stratum == "all" else METHODS[:-1]
        )
        allowed = [m for m in allowed if m in available_methods]
        candidate = min(allowed, key=lambda m: (error(rows, m), METHODS.index(m)))
        base_error = error(rows, baseline)
        passed = (
            validation_count >= 6 and base_error > 0 and error(rows, candidate) <= 0.95 * base_error
        )
        if stratum == "all" and passed:
            for group in sorted({r["stratum"] for r in rows}):
                subset = [r for r in rows if r["stratum"] == group]
                if len(subset) >= 30 and error(subset, candidate) > 1.05 * error(subset, baseline):
                    passed = False
        selection_rules[stratum] = {
            "baseline": baseline,
            "candidate": candidate,
            "validation_adopted": passed,
            "selected": candidate if passed else baseline,
        }
    for stratum, rule in selection_rules.items():
        rows = test if stratum == "all" else [r for r in test if r["stratum"] == stratum]
        stable = bool(rows) and error(rows, rule["selected"]) <= error(rows, baseline)
        rule["test_supported"] = stable
        if not stable:
            rule["selected"] = baseline

    def policy_error(rows):
        return float(
            np.mean(
                [
                    abs(
                        r[selection_rules.get(r["stratum"], selection_rules["all"])["selected"]]
                        - r["actual"]
                    )
                    for r in rows
                ]
            )
        )

    policy_passed = policy_error(validation) <= 0.95 * error(validation, baseline) and policy_error(
        test
    ) <= error(test, baseline)
    if not policy_passed:
        for rule in selection_rules.values():
            rule["selected"] = baseline
            rule["policy_gate"] = "整体未达到采用门槛，保留基线"
    by_item = defaultdict(list)
    for row in validation:
        by_item[row["item_id"]].append(row)
    final_model = _model(arrays, keys, n, dates)
    fs = [features(arrays[k], n, dates) for k in keys if np.isfinite(arrays[k][-28:]).all()]
    final_keys = [k for k in keys if np.isfinite(arrays[k][-28:]).all()]
    final_gb = final_model.predict([f for f, _ in fs]) if final_model is not None and fs else None
    gb = (
        {k: max(0, float(final_gb[j])) * fs[j][1] * 7 for j, k in enumerate(final_keys)}
        if final_gb is not None
        else {}
    )
    for key in keys:
        if key not in final_eligible or not by_item[key]:
            continue
        values = arrays[key]
        stratum = _stratum(values)
        chosen = selection_rules.get(stratum, selection_rules["all"])["selected"]
        rows = by_item[key]
        mae = error(rows, chosen)
        item_test = [row for row in test if row["item_id"] == key]
        recent = float(values[-28:].sum() / 4)
        if mae > max(2, recent * 0.5):
            continue
        estimates = {**_simple(values), "gradient_boosting": gb.get(key, recent)}
        prediction = {
            "quantity": round(estimates[chosen], 3),
            "method": chosen,
            "validation_mae": round(mae, 3),
            "validation_origins": len(rows),
            "test_mae": round(error(item_test, chosen), 3) if item_test else None,
            "test_origins": len(item_test),
            "stratum": stratum,
            "start": (dates[-1] + timedelta(days=1)).isoformat(),
            "end": (dates[-1] + timedelta(days=7)).isoformat(),
            "range": None,
            "range_reason": "独立历史误差不足，暂不提供预测范围。",
            "notice": "七天累计销量参考；历史误差不保证未来表现，未计入未知缺货和未来活动。",
        }
        calibration = [
            r for r in records if r["split"] == "calibration" and r["stratum"] == stratum
        ]
        grouped_errors = defaultdict(list)
        for r in calibration:
            grouped_errors[r["origin"]].append(abs(r[chosen] - r["actual"]))
        if len(grouped_errors) >= 20:
            block_errors = [float(np.median(e)) for e in grouped_errors.values()]
            radius = float(np.quantile(block_errors, 0.9))
            coverage = float(np.mean([abs(r[chosen] - r["actual"]) <= radius for r in calibration]))
            drift = np.mean(block_errors[-5:]) <= max(1, 1.5 * np.mean(block_errors[:10]))
            heldout = [r for r in test if r["stratum"] == stratum]
            heldout_coverage = (
                float(np.mean([abs(r[chosen] - r["actual"]) <= radius for r in heldout]))
                if heldout
                else 0
            )
            if (
                coverage >= 0.8
                and heldout_coverage >= 0.8
                and drift
                and radius <= max(2, estimates[chosen])
            ):
                prediction.update(
                    range={
                        "lower": max(0, round(estimates[chosen] - radius, 3)),
                        "upper": round(estimates[chosen] + radius, 3),
                        "calibration_coverage": coverage,
                        "calibration_origins": len(grouped_errors),
                        "heldout_coverage": heldout_coverage,
                    },
                    range_reason="同类商品历史误差形成的经验参考范围，不保证未来覆盖。",
                )
        result["predictions"][key] = prediction
    for row in records:
        row["selected_method"] = selection_rules.get(row["stratum"], selection_rules["all"])[
            "selected"
        ]
        row["selected"] = row[row["selected_method"]]
    metrics += [
        {
            "method": "selected_policy",
            "split": split,
            **score([r["actual"] for r in rows], [r["selected"] for r in rows]),
        }
        for split, rows in [("validation", validation), ("test", test)]
    ]
    result.update(
        status="evaluated",
        reason="",
        selected_method=selection_rules["all"]["selected"],
        selection_rules=selection_rules,
        stratified_policy_adopted=policy_passed,
        metrics=metrics,
        cutoffs=[dates[t].isoformat() for t in origins],
        backtests=records,
        published_items=len(result["predictions"]),
        evaluation_notice="方法在历史验证期选择，最后三个时间段用于独立检验。短历史不更换方法。",
    )
    return result


def weekday_reference(values, dates, t, closed=()):
    indices = [
        j
        for j in range(max(0, t - 84), t)
        if dates[j].weekday() == dates[t].weekday()
        and dates[j].isoformat() not in closed
        and np.isfinite(values[j])
    ]
    if len(indices) < 6:
        return None
    history = np.asarray([values[j] for j in indices])
    median = float(np.median(history))
    return median, float(np.median(np.abs(history - median)))


def anomaly_series(series, dates, month, closed_dates=()):
    result = {
        "version": MODEL_VERSION,
        "status": "unavailable",
        "items": {},
        "reason": "需要至少 56 天完整日记录，才能检查异常销售。",
    }
    if len(dates) < 56:
        return result
    closed = set(closed_dates)
    cutoff = next((i for i, d in enumerate(dates) if d.strftime("%Y-%m") == month), len(dates))
    train, probes, meta = [], [], []
    legacy_train, legacy_probes = [], []
    for key, raw in series.items():
        values = np.asarray(raw, dtype=float)
        if np.count_nonzero(values[:cutoff] > 0) >= 8:
            for t in range(max(14, cutoff - 90), cutoff):
                if dates[t].isoformat() in closed or not np.isfinite(values[t]):
                    continue
                history = values[max(0, t - 28) : t]
                if not np.isfinite(history).all():
                    continue
                scale_old = max(float(history.mean()), 1)
                legacy_train.append(
                    [
                        float(values[t]) / scale_old,
                        float(values[max(0, t - 7) : t].mean()) / scale_old,
                        float(history.std()) / scale_old,
                    ]
                )
        for t in range(max(42, cutoff - 90), len(dates)):
            if dates[t].isoformat() in closed or not np.isfinite(values[t]):
                continue
            ref = weekday_reference(values, dates, t, closed)
            if ref is None:
                continue
            reference, mad = ref
            past = values[max(0, t - 28) : t]
            if not np.isfinite(past).all() or np.count_nonzero(values[:t] > 0) < 8:
                continue
            scale = max(reference, float(past.mean()), 1)
            diff = float(values[t]) - reference
            vector = [diff / scale, abs(diff) / max(1, mad * 1.4826), float(past.std()) / scale]
            legacy_scale = max(float(past.mean()), 1)
            legacy_vector = [
                float(values[t]) / legacy_scale,
                float(values[max(0, t - 7) : t].mean()) / legacy_scale,
                float(past.std()) / legacy_scale,
            ]
            if t < cutoff:
                train.append(vector)
            elif dates[t].strftime("%Y-%m") == month:
                probes.append(vector)
                legacy_probes.append(legacy_vector)
                meta.append(
                    {
                        "item_id": key,
                        "date": dates[t].isoformat(),
                        "actual": float(values[t]),
                        "reference": round(reference, 3),
                        "difference": round(diff, 3),
                        "threshold": max(3, 0.7 * scale, 3 * 1.4826 * mad),
                        "simple_rule": abs(diff) > max(3, 0.7 * scale, 3 * 1.4826 * mad),
                        "legacy_substantial": abs(float(values[t]) - float(np.median(past)))
                        > max(3, 0.7 * legacy_scale),
                    }
                )
    if not probes:
        return result
    if len(train) < 200:
        result["reason"] = "可比较的历史商品日记录不足，暂不发布异常提醒。"
        return result
    model_scores = legacy_scores = None
    if len(train) >= 200:
        model = IsolationForest(
            n_estimators=100, max_samples=256, contamination="auto", random_state=42, n_jobs=2
        ).fit(train)
        model_scores = model.score_samples(probes)
        legacy_model = IsolationForest(
            n_estimators=100, max_samples=256, contamination="auto", random_state=42, n_jobs=2
        ).fit(legacy_train)
        legacy_scores = legacy_model.score_samples(legacy_probes)
    items = defaultdict(list)
    for index, row in enumerate(meta):
        corroborated = (
            legacy_scores is not None and legacy_scores[index] < -0.60 and row["legacy_substantial"]
        )
        extreme = abs(row["difference"]) > max(10, 3 * row["threshold"])
        if row["simple_rule"] and (corroborated or extreme):
            row["strength"] = abs(row["difference"]) / row.pop("threshold")
            row["score"] = round(float(legacy_scores[index]), 4)
            row["residual_score"] = round(float(model_scores[index]), 4)
            row["method"] = "weekday_confirmed_isolation_forest"
            items[row["item_id"]].append(row)
    events = {}
    for key, rows in items.items():
        groups = []
        for row in rows:
            if (
                groups
                and (
                    date.fromisoformat(row["date"]) - date.fromisoformat(groups[-1][-1]["date"])
                ).days
                == 1
            ):
                groups[-1].append(row)
            else:
                groups.append([row])
        events[key] = sorted(
            [
                {
                    "start": g[0]["date"],
                    "end": g[-1]["date"],
                    "days": len(g),
                    "actual": sum(r["actual"] for r in g),
                    "reference": sum(r["reference"] for r in g),
                    "difference": sum(r["difference"] for r in g),
                    "strength": max(r["strength"] for r in g),
                    "dates": [r["date"] for r in g],
                }
                for g in groups
            ],
            key=lambda e: (-e["strength"], -abs(e["difference"])),
        )
    result.update(
        status="evaluated",
        reason="",
        items=dict(items),
        events=events,
        method="weekday_confirmed_isolation_forest",
        candidate_method="weekday_residual_isolation_forest",
        train_samples=len(train),
        tested_samples=len(probes),
        flagged_samples=sum(map(len, items.values())),
        simple_rule_flags=sum(r["simple_rule"] for r in meta),
        residual_if_flags=int(np.sum(model_scores < -0.6)) if model_scores is not None else None,
        training_end=dates[cutoff - 1].isoformat() if cutoff else None,
        warning="与此前相同星期的销量比较，只提醒核对记录，不判断缺货或活动原因。",
    )
    return result
