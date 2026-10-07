"""Decimal amount contract. Candidates still require the later quality gate before analysis."""

from decimal import Context, Decimal, InvalidOperation

AMOUNT_CONTEXT = Context(prec=100)


def money(value):
    if value is None or len(str(value)) > 128:
        return None
    try:
        result = Decimal(str(value))
        if not result.is_finite() or abs(result.adjusted()) > 28:
            return None
        return result if len(result.as_tuple().digits) <= 28 else None
    except InvalidOperation:
        return None


class OrderAmounts:
    def __init__(self, mode):
        self.mode = mode
        self.orders = {}

    def add(self, row):
        identity = row.get("order_id")
        if not identity:
            return
        state = self.orders.setdefault(
            identity,
            {
                "rows": 0,
                "line_sum": Decimal(0),
                "line_complete": True,
                "totals": set(),
                "invalid_total": False,
                "currencies": set(),
                "customers": set(),
                "times": set(),
            },
        )
        state["rows"] += 1
        for field, destination in [
            ("currency", "currencies"),
            ("customer_id", "customers"),
            ("event_time", "times"),
        ]:
            if row.get(field):
                state[destination].add(row[field])
        total = money(row.get("order_amount"))
        if total is not None:
            state["totals"].add(total)
        elif row.get("order_amount") is not None:
            state["invalid_total"] = True
        line = money(row.get("line_amount"))
        if self.mode == "quantity_unit_price":
            quantity, price = money(row.get("quantity")), money(row.get("unit_price"))
            line = (
                AMOUNT_CONTEXT.multiply(quantity, price)
                if quantity is not None and price is not None else None
            )
        if line is None:
            state["line_complete"] = False
        else:
            state["line_sum"] = AMOUNT_CONTEXT.add(state["line_sum"], line)

    def records(self):
        for identity, state in self.orders.items():
            reasons = []
            for source, label in [
                ("currencies", "mixed_currency"),
                ("customers", "conflicting_customer"),
                ("times", "conflicting_time"),
            ]:
                if len(state[source]) > 1:
                    reasons.append(label)
            amount = None
            if self.mode == "order_amount":
                if state["invalid_total"]:
                    reasons.append("invalid_order_amount")
                if len(state["totals"]) != 1:
                    reasons.append(
                        "conflicting_order_amount" if state["totals"] else "missing_order_amount"
                    )
                else:
                    amount = next(iter(state["totals"]))
            elif self.mode in {"line_amount", "quantity_unit_price"}:
                if state["line_complete"]:
                    amount = state["line_sum"]
                else:
                    reasons.append("incomplete_line_amount")
            if self.mode != "none" and not state["currencies"]:
                reasons.append("unknown_currency")
            yield {
                "order_id": identity,
                "source_rows": state["rows"],
                "amount_candidate": str(amount) if amount is not None and not reasons else None,
                "currency": next(iter(state["currencies"]))
                if len(state["currencies"]) == 1
                else None,
                "issues": ",".join(reasons),
                "quality_gate": "pending",
            }


def scoped_amount(order_amount, original_row_count, selected_lines):
    """Never allocate a full order total to a partial selection of its lines."""
    if len(selected_lines) == original_row_count:
        return money(order_amount)
    amounts = [money(value) for value in selected_lines]
    if not amounts or any(value is None for value in amounts):
        return None
    total = Decimal(0)
    for value in amounts:
        total = AMOUNT_CONTEXT.add(total, value)
    return total
