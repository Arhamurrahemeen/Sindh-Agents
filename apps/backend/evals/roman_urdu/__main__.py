import asyncio
import logging
import sys

from evals.roman_urdu.harness import run_all, summarize


async def main() -> int:
    logger = logging.getLogger("evals.roman_urdu")
    results = await run_all(logger)

    for result in results:
        status = "PASS" if result.passed else "FAIL"
        print(f"[{status}] {result.case_id}")
        for reason in result.reasons:
            print(f"    - {reason}")

    pct, hard_fail_ok = summarize(results)
    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed}/{len(results)} cases passed ({pct:.1f}%)")

    if not hard_fail_ok:
        print("Below the 80% hard-fail threshold — see docs/eval_spec.md")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
