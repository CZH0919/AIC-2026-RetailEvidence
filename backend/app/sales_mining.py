"""Time-bounded, CPU-only sales mining; predictions never see future labels."""

from collections import defaultdict
from datetime import date, timedelta

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest

MODEL_VERSION = "sales-v2.1.1"
FORECAST_DAYS = 90
ANOMALY_DAYS = 56
MAX_MODEL_ITEMS = 1000


def features(values, origin, dates=None):
    past = values[:origin]
    recent = past[-28:]
    scale = max(float(recent.mean()), 0.1)
    vector = [
        float(past[-7:].mean()) / scale,
        float(past[-14:].mean()) / scale,
        float(recent.std()) / scale,
        float(np.count_nonzero(recent)) / 28,
        float(past[-7:].sum()) / (scale * 7),
        float(past[-14:-7].sum()) / (scale * 7),
        float(recent.max()) / scale,
        next((i for i, v in enumerate(past[::-1]) if v > 0), 28) / 28,
    ]
    if dates is not None:
        current = dates[origin] if origin < len(dates) else dates[-1] + timedelta(days=1)
        vector += [current.weekday() / 6, current.month / 12]
    return vector, scale


def score(actual, predicted):
    a, p = np.asarray(actual), np.asarray(predicted)
    return {
        "mae": float(np.abs(a - p).mean()) if len(a) else None,
        "wape": float(np.abs(a - p).sum() / a.sum()) if a.sum() else None,
        "samples": len(a),
    }


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
    if n < FORECAST_DAYS:
        return result
    eligible = {k: np.asarray(v, dtype=float) for k, v in series.items()}
    final_eligible = {
        k
        for k, v in eligible.items()
        if np.count_nonzero(v[-28:]) >= 8
        and np.count_nonzero(v[:-28]) >= 8
        and len(v) - int(np.flatnonzero(v)[0]) >= FORECAST_DAYS
    }
    result["eligible_items"] = len(final_eligible)
    selection_origin = n - 42
    candidates = {
        k: v
        for k, v in eligible.items()
        if np.count_nonzero(v[selection_origin - 28 : selection_origin]) >= 8
        and np.count_nonzero(v[: selection_origin - 28]) >= 8
    }
    ranked = sorted(
        candidates,
        key=lambda k: (-float(candidates[k][selection_origin - 28 : selection_origin].sum()), k),
    )
    keys = ranked[:MAX_MODEL_ITEMS]
    result["tested_items"] = len(keys)
    result["selection_origin"] = dates[selection_origin].isoformat()
    result["historical_candidates"] = len(candidates)
    result["resource_excluded_items"] = max(0, len(ranked) - len(keys))
    if not keys:
        return result
    origins = list(range(n - 42, n, 7))
    names = ["gradient_boosting", "last_week", "four_week_mean"]
    records = []
    for index, origin in enumerate(origins):
        progress("forecasting", 35 + index * 5)
        x, y = [], []
        # A training label ends no later than the forecasting origin.
        for key in keys:
            values = eligible[key]
            for t in range(max(28, origin - 180), origin - 6, 7):
                f, scale = features(values, t, dates)
                x.append(f)
                y.append(float(values[t : t + 7].sum()) / (scale * 7))
        if len(x) < 30:
            continue
        model = HistGradientBoostingRegressor(
            max_iter=80,
            max_leaf_nodes=15,
            min_samples_leaf=15,
            l2_regularization=2,
            random_state=42,
            early_stopping=False,
        ).fit(x, y)
        tests, scales = zip(*(features(eligible[k], origin, dates) for k in keys), strict=True)
        estimates = np.maximum(0, model.predict(tests)) * np.asarray(scales) * 7
        for j, key in enumerate(keys):
            values = eligible[key]
            records.append(
                {
                    "item_id": key,
                    "origin": dates[origin].isoformat(),
                    "training_label_end": dates[origin - 1].isoformat(),
                    "target_end": dates[origin + 6].isoformat(),
                    "split": "validation" if index < 3 else "test",
                    "actual": float(values[origin : origin + 7].sum()),
                    "gradient_boosting": float(estimates[j]),
                    "last_week": float(values[origin - 7 : origin].sum()),
                    "four_week_mean": float(values[origin - 28 : origin].sum() / 4),
                }
            )
    validation = [r for r in records if r["split"] == "validation"]
    test = [r for r in records if r["split"] == "test"]
    if not validation or not test:
        result["reason"] = "可回测的历史样本不足，暂不发布预测。"
        return result
    metrics = [
        {
            "method": name,
            "split": split,
            **score([r["actual"] for r in rows], [r[name] for r in rows]),
        }
        for split, rows in [("validation", validation), ("test", test)]
        for name in names
    ]
    chosen = min(
        (m for m in metrics if m["split"] == "validation"),
        key=lambda m: (m["mae"], names.index(m["method"])),
    )["method"]
    result.update(
        status="evaluated",
        reason="",
        selected_method=chosen,
        metrics=metrics,
        cutoffs=sorted({r["origin"] for r in records}),
        backtests=records,
    )
    x, y, final_x, scales = [], [], [], []
    for key in keys:
        values = eligible[key]
        for t in range(max(28, n - 180), n - 6, 7):
            f, scale = features(values, t, dates)
            x.append(f)
            y.append(float(values[t : t + 7].sum()) / (scale * 7))
        f, scale = features(values, n, dates)
        final_x.append(f)
        scales.append(scale)
    final_model = HistGradientBoostingRegressor(
        max_iter=80,
        max_leaf_nodes=15,
        min_samples_leaf=15,
        l2_regularization=2,
        random_state=42,
        early_stopping=False,
    ).fit(x, y)
    estimates = np.maximum(0, final_model.predict(final_x)) * np.asarray(scales) * 7
    by_item = defaultdict(list)
    for row in validation:
        by_item[row["item_id"]].append(row)
    for j, key in enumerate(keys):
        if key not in final_eligible:
            continue
        rows = by_item[key]
        error = score([r["actual"] for r in rows], [r[chosen] for r in rows])["mae"]
        recent = float(eligible[key][-28:].sum() / 4)
        # Versioned engineering gate, not a statistical confidence statement.
        if error > max(2, recent * 0.5):
            continue
        prediction = {
            "gradient_boosting": float(estimates[j]),
            "last_week": float(eligible[key][-7:].sum()),
            "four_week_mean": recent,
        }[chosen]
        result["predictions"][key] = {
            "quantity": round(prediction, 3),
            "method": chosen,
            "validation_mae": round(error, 3),
            "start": (dates[-1] + timedelta(days=1)).isoformat(),
            "end": (dates[-1] + timedelta(days=7)).isoformat(),
            "notice": "七天累计销量估计；历史误差不是保证，未计入未知缺货和未来促销。",
        }
    result["published_items"] = len(result["predictions"])
    return result


def anomaly_series(series, dates, month, closed_dates=()):
    result = {
        "version": MODEL_VERSION,
        "status": "unavailable",
        "items": {},
        "reason": "需要至少 56 天完整日记录，才能检查异常销售。",
    }
    if len(dates) < ANOMALY_DAYS:
        return result
    cutoff = next((i for i, d in enumerate(dates) if d.strftime("%Y-%m") == month), len(dates))
    if cutoff < 28:
        return result
    train, probes, meta = [], [], []
    closed = set(closed_dates)
    for key, raw in series.items():
        values = np.asarray(raw, dtype=float)
        if np.count_nonzero(values[:cutoff]) < 8:
            continue
        for t in range(max(14, cutoff - 90), len(dates)):
            if dates[t].isoformat() in closed:
                continue
            history = values[max(0, t - 28) : t]
            scale = max(float(history.mean()), 1)
            vector = [
                float(values[t]) / scale,
                float(values[max(0, t - 7) : t].mean()) / scale,
                float(history.std()) / scale,
            ]
            if t < cutoff:
                train.append(vector)
            else:
                probes.append(vector)
                med = float(np.median(history))
                mad = float(np.median(np.abs(history - med)))
                meta.append(
                    {
                        "item_id": key,
                        "date": dates[t].isoformat(),
                        "actual": float(values[t]),
                        "reference": round(med, 3),
                        "difference": round(float(values[t]) - med, 3),
                        "simple_rule": abs(float(values[t]) - med) > max(3, 3 * mad),
                        "scale": scale,
                    }
                )
    if len(train) < 200 or not probes:
        return result
    model = IsolationForest(
        n_estimators=100, max_samples=256, contamination="auto", random_state=42, n_jobs=2
    ).fit(train)
    scores = model.score_samples(probes)
    items = defaultdict(list)
    for row, score_value in zip(meta, scores, strict=True):
        # Require a substantial absolute and relative deviation; never force alert quotas.
        if score_value < -0.60 and abs(row["difference"]) > max(3, row["scale"] * 0.7):
            row.pop("scale")
            items[row["item_id"]].append({**row, "score": round(float(score_value), 4)})
    result.update(
        status="evaluated",
        reason="",
        items=dict(items),
        train_samples=len(train),
        tested_samples=len(probes),
        flagged_samples=sum(map(len, items.values())),
        simple_rule_flags=sum(r["simple_rule"] for r in meta),
        training_end=dates[cutoff - 1].isoformat(),
        warning="标出值得检查的销售变化，不判断缺货或促销原因，也不保证识别率。",
    )
    return result


def calendar(start, end):
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if (last - first).days > 1095:
        first = last - timedelta(days=1095)
    return [first + timedelta(days=i) for i in range((last - first).days + 1)]
