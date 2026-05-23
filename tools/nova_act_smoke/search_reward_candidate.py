"""
Nova Act スモークテスト CLI

要件整理.md §10 準拠 — Nova Act 単体検証スクリプト。

Usage:
    python tools/nova_act_smoke/search_reward_candidate.py \\
        --query "抹茶 プリン" \\
        --max-results 3 \\
        --output sample_output.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# プロジェクトの layer/python を sys.path に追加
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "layer" / "python"))
sys.path.insert(0, str(ROOT / "src"))


def main():
    parser = argparse.ArgumentParser(description="Nova Act スモークテスト")
    parser.add_argument("--query", required=True, help="検索クエリ（例: 抹茶 プリン）")
    parser.add_argument("--max-results", type=int, default=3, help="最大候補数")
    parser.add_argument("--output", default=None, help="結果JSONファイル出力先")
    parser.add_argument("--verbose", action="store_true", help="詳細出力")
    args = parser.parse_args()

    # デフォルトで Nova Act 有効化
    os.environ.setdefault("ENABLE_NOVA_ACT", "true")
    os.environ.setdefault("ENABLE_NOVA_ACT_SMOKE", "true")

    try:
        from services.reward_candidate_provider import run_nova_act_smoke
    except Exception as e:
        print(f"[ERROR] reward_candidate_provider import 失敗: {e}", file=sys.stderr)
        print("依存ライブラリ (cryptography, requests, etc.) を確認してください", file=sys.stderr)
        sys.exit(1)

    print(f"[INFO] query={args.query!r}, max_results={args.max_results}")
    candidates, meta = run_nova_act_smoke(args.query, max_results=args.max_results)

    print(f"\n[META] status={meta.get('status')} provider={meta.get('provider')} duration_ms={meta.get('duration_ms')}")
    if meta.get("failure_reason"):
        print(f"[META] failure_reason={meta.get('failure_reason')}")

    print(f"\n[RESULT] {len(candidates)} candidate(s):")
    for i, c in enumerate(candidates, start=1):
        print(f"  {i}. {c.get('name')} — ¥{c.get('amount'):,} ({c.get('source')}, conf={c.get('confidence'):.2f})")
        if args.verbose:
            print(f"     url: {c.get('url')}")
            print(f"     tags: {c.get('tags')}")

    output = {"query": args.query, "candidates": candidates, "meta": meta}
    if args.output:
        Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n[OK] saved to {args.output}")
    else:
        print("\n[JSON]")
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
