import html
from pathlib import Path
from string import Template


def render_report(report, project_name, all_attention=False):
    def esc(value):
        return html.escape(str(value))

    summary = report["summary"]
    products = {p["id"]: p for p in report["products"]}
    ids = report["highlights"]
    product_rows = "".join(
        f"<tr><td>{esc(products[k]['name'])}</td><td>{products[k]['quantity']:g}</td>"
        f"<td>{esc(products[k]['reason'])}</td></tr>"
        for k in ids
    )
    actions = "".join(
        f"<li><strong>{esc(a['title'])}</strong>"
        f"<p>{esc(a['text'].split(' 另有 ', 1)[0])}</p>"
        f"<small>{esc(a['reason'])} · {esc(a['review'])}</small></li>"
        for a in report["actions"]
    )
    extra = ""
    if all_attention:
        rows = "".join(
            f"<tr><td>{esc(products[k]['name'])}</td><td>{products[k]['quantity']:g}</td>"
            f"<td>{esc(products[k]['reason'])}</td></tr>"
            for k in report["attention_ids"]
        )
        extra = (
            "<section class='appendix'><h2>全部待关注商品</h2><table>"
            "<thead><tr><th>商品</th><th>销量</th><th>原因</th></tr></thead>"
            f"<tbody>{rows}</tbody></table></section>"
        )
    amount = (
        f"{summary['amount']:,.2f} {esc(summary['currency'])}"
        if summary["amount"] is not None
        else "未提供完整金额"
    )
    notice = " ".join(report["notices"])
    context = esc(report["context"]["run_id"])
    sources = "、".join(esc(s["filename"]) for s in report["sources"])
    chart = ""
    if report["chart"]:
        field = (
            "amount"
            if summary["amount"] is not None
            and any(p["amount"] is not None for p in report["chart"])
            else "quantity"
        )
        maximum = max([p[field] or 0 for p in report["chart"]] + [1])
        bars = "".join(
            f'<span title="{p["date"]}: {p[field] if p[field] is not None else "未知"}" '
            f'style="height:{100 * (p[field] or 0) / maximum:.1f}%;'
            f'background:{"#27866e" if p[field] is not None else "#ddd"}"></span>'
            for p in report["chart"]
        )
        chart = (
            f'<div class="chart">{bars}</div><small>{report["month"]} '
            f"每日{'销售额' if field == 'amount' else '销量'}；未知日期不按零计。</small>"
        )
    template = Template(Path(__file__).with_name("retail_report.html").read_text(encoding="utf-8"))
    return template.substitute(
        title=f"{esc(project_name)} · {esc(report['month'])} 销售月报",
        amount=amount,
        quantity=f"{summary['quantity']:g} {esc(summary['unit'])}",
        products=summary["products"],
        chart=chart,
        product_rows=product_rows,
        attention=summary["attention_total"],
        shown=len(ids),
        actions=actions or "<li>当前没有足够依据提出特别行动，继续记录销售情况。</li>",
        notice=f"{esc(summary['amount_label'])}。{esc(notice)}",
        sources=sources,
        context=context,
        appendix=extra,
    )
