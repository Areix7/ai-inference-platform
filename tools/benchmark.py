#!/usr/bin/env python3
# vllm load test, prints TTFT percentiles

import argparse
import asyncio
import json
import statistics
import sys
import time

try:
    import aiohttp
except ImportError:
    sys.exit("need aiohttp: pip3 install aiohttp")


async def one_req(sess, url, model, prompt, max_tokens):
    body = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "stream": True,
        "temperature": 0.0,
    }
    t0 = time.perf_counter()
    ttft = None
    ntok = 0
    try:
        async with sess.post(url, json=body) as r:
            if r.status != 200:
                return {"err": f"http_{r.status}", "ttft": None, "total": None, "tok": 0}
            async for raw in r.content:
                raw = raw.strip()
                if not raw or not raw.startswith(b"data: "):
                    continue
                chunk = raw[6:]
                if chunk == b"[DONE]":
                    break
                try:
                    obj = json.loads(chunk)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                text = choices[0].get("text", "")
                if ttft is None and text:
                    ttft = time.perf_counter() - t0
                if text:
                    ntok += 1
        total = time.perf_counter() - t0
        return {"err": None, "ttft": ttft, "total": total, "tok": ntok}
    except Exception as e:
        return {"err": type(e).__name__, "ttft": None, "total": None, "tok": 0}


def pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


async def run(args):
    url = f"{args.url.rstrip('/')}/v1/completions"
    prompt = "Explain what a GPU is in one paragraph. " * max(1, args.prompt_len // 40)

    conn = aiohttp.TCPConnector(limit=args.concurrency)
    timeout = aiohttp.ClientTimeout(total=args.timeout)

    ttfts = []
    totals = []
    toks = 0
    errs = {}
    t_start = time.perf_counter()

    sem = asyncio.Semaphore(args.concurrency)

    async def worker(i):
        nonlocal toks
        async with sem:
            r = await one_req(sess, url, args.model, prompt, args.max_tokens)
        if r["err"]:
            errs[r["err"]] = errs.get(r["err"], 0) + 1
            return
        if r["ttft"] is not None:
            ttfts.append(r["ttft"])
        if r["total"] is not None:
            totals.append(r["total"])
        toks += r["tok"]

    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as sess:
        await asyncio.gather(*(worker(i) for i in range(args.requests)))

    wall = time.perf_counter() - t_start
    ok = len(totals)

    result = {
        "config": {
            "url": url,
            "model": args.model,
            "concurrency": args.concurrency,
            "requests": args.requests,
            "prompt_len": args.prompt_len,
            "max_tokens": args.max_tokens,
        },
        "summary": {
            "wall_s": round(wall, 3),
            "ok": ok,
            "failed": sum(errs.values()),
            "rps": round(ok / wall, 2) if wall > 0 else 0,
            "tokens": toks,
            "tok_per_s": round(toks / wall, 2) if wall > 0 else 0,
        },
        "ttft_s": {
            "p50": round(pct(ttfts, 50), 4),
            "p90": round(pct(ttfts, 90), 4),
            "p99": round(pct(ttfts, 99), 4),
            "mean": round(statistics.mean(ttfts), 4) if ttfts else 0,
        },
        "latency_s": {
            "p50": round(pct(totals, 50), 4),
            "p90": round(pct(totals, 90), 4),
            "p99": round(pct(totals, 99), 4),
            "mean": round(statistics.mean(totals), 4) if totals else 0,
        },
        "errors": errs,
    }
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--model", default="Qwen3-8B")
    p.add_argument("--concurrency", type=int, default=8)
    p.add_argument("--requests", type=int, default=32)
    p.add_argument("--prompt-len", type=int, default=256)
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument("--timeout", type=int, default=120)
    p.add_argument("--out", default=None)
    args = p.parse_args()

    r = asyncio.run(run(args))

    print()
    print(f"requests     {r['summary']['ok']} ok / {r['summary']['failed']} failed")
    print(f"wall         {r['summary']['wall_s']} s")
    print(f"rps          {r['summary']['rps']}")
    print(f"tokens       {r['summary']['tokens']}  ({r['summary']['tok_per_s']} tok/s)")
    print()
    print(f"ttft p50     {r['ttft_s']['p50']} s")
    print(f"ttft p90     {r['ttft_s']['p90']} s")
    print(f"ttft p99     {r['ttft_s']['p99']} s")
    print()
    print(f"total p50    {r['latency_s']['p50']} s")
    print(f"total p90    {r['latency_s']['p90']} s")
    print(f"total p99    {r['latency_s']['p99']} s")

    if r["errors"]:
        print()
        print("errors:")
        for k, v in r["errors"].items():
            print(f"  {k}: {v}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(r, f, indent=2)
        print(f"\nsaved to {args.out}")


if __name__ == "__main__":
    main()
