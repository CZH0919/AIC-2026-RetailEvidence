"""Save real-model answers for an existing public-data run."""

import argparse
import json
import time
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='90277e64-3e8c-4063-b564-37c018da5283')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    url = f'http://127.0.0.1:8000/api/projects/e1711757-601a-4e9a-a05f-037d7e6909e6/sales/runs/{args.run_id}/ask'
    results = []
    for question in ['请解释本月销量，并告诉我下次进货前先看什么。',
                     '这些销售异常是不是说明已经缺货了？',
                     '只看这份销售表，能确定我应该订货多少吗？']:
        started = time.monotonic()
        request = urllib.request.Request(url, data=json.dumps({'question': question}).encode(),
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=90) as response:
            answer = json.load(response)
        assert answer['run_id'] == args.run_id
        if answer['ai_used']:
            assert answer['references']
        results.append({'question': question, 'answer': answer['answer'],
                        'ai_used': answer['ai_used'], 'references': answer.get('references'),
                        'run_id': args.run_id, 'seconds': round(time.monotonic() - started, 2),
                        'prompt_version': answer.get('prompt_version')})
    output = {'model': 'qwen2.5-1.5b-instruct-q4_k_m', 'cpu': True, 'results': results,
              'limitations': 'Small real-evidence smoke test, not a general hallucination accuracy estimate.'}
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(output, ensure_ascii=False))


if __name__ == '__main__':
    main()
