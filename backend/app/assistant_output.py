"""Validate whole user explanations before binding program facts; never trim model prose."""

import re

INTERNAL_LANGUAGE = re.compile(
    r"系统提示词|内部提示词|system\s*prompt|开发助手|开发者(?:指令|要求)|"
    r"我将.{0,30}(?:执行|读取|调用|遵循|按照|处理)|工具调用|function_call|"
    r"模型角色|角色声明|schema|traceback|stack\s*trace|private_plan|"
    r"(?:服务器|本地).{0,10}(?:内部路径|文件路径|端口)|"
    r"(?:/home/|/etc/|[A-Za-z]:\\)|```|^\s*[\[{]",
    re.IGNORECASE,
)
UNSUPPORTED_CLAIMS = re.compile(
    r"库存不足|库存紧张|库存告急|库存不够|可能缺货|存在缺货|"
    r"经营情况很好|销量表现优秀|可以放心(?:采购|进货)|保证|确保"
)


def validate_explanation(parsed, allowed_references):
    if not isinstance(parsed, dict) or set(parsed) != {"answer", "references"}:
        raise ValueError("Unexpected explanation structure")
    answer, references = parsed["answer"], parsed["references"]
    if not isinstance(answer, str) or not 12 <= len(answer) <= 500:
        raise ValueError("Invalid explanation text")
    if not isinstance(references, list) or not 1 <= len(references) <= 5:
        raise ValueError("Invalid explanation references")
    if any(not isinstance(ref, str) or ref not in allowed_references for ref in references):
        raise ValueError("Unverified explanation references")
    if INTERNAL_LANGUAGE.search(answer) or UNSUPPORTED_CLAIMS.search(answer):
        raise ValueError("Explanation is not supported user language")
    return answer, list(dict.fromkeys(references))


def failure_answer(mode, fields=False):
    next_step = (
        "请按预览人工核对，无法确定的字段留空。"
        if fields
        else "可以继续查看月报中的计算结果和商品依据。"
    )
    reason = {
        "inference_timeout": "这次回答等待超时，请稍后再试。",
        "inference_unavailable": "销售助手暂时无法回答，请稍后再试。",
        "rejected_model_output": "这次解释未通过核对，请以实际计算结果为准。",
    }.get(mode, "这次未能完成AI回答。")
    return reason + next_step
