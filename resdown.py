#!/usr/bin/env python3
"""
BEU Result Downloader — Bihar Engineering University
Run:   python beu_downloader.py            (visible browser)
       python beu_downloader.py --headless  (hidden browser)
"""

import asyncio
import argparse
import sys
import random
from pathlib import Path

try:
    import roll_numbers as cfg
except ModuleNotFoundError:
    print("\n❌  roll_numbers.py not found! Put it in the same folder.\n")
    sys.exit(1)

RESULT_URL_TEMPLATE = (
    "https://beu-bih.ac.in/result-three"
    "?name=B.Tech.%206th%20Semester%20Examination%2C%202025"
    "&semester=VI"
    "&session=2025"
    "&regNo={regNo}"
    "&exam_held=November%2F2025"
)

# Exact backend API confirmed from debug output
API_URL_PATTERN = "/backend/v1/result/get-result"

MIN_DELAY_SEC = 2
MAX_DELAY_SEC = 4
API_TIMEOUT   = 20
RENDER_WAIT   = 1500


# ── Roll helpers ──────────────────────────────────────────────────────────────

def expand_range(start: str, end: str) -> list:
    if len(start) != len(end):
        raise ValueError(f"Length mismatch: {start!r} vs {end!r}")
    L = len(start)
    SUFFIX = 4
    prefix = start[:L - SUFFIX]
    s = int(start[L - SUFFIX:])
    e = int(end[L - SUFFIX:])
    if s > e:
        raise ValueError("Start must be ≤ End")
    return [f"{prefix}{i:0{SUFFIX}d}" for i in range(s, e + 1)]


def build_roll_list() -> list:
    rolls = [r.strip() for r in cfg.INDIVIDUAL_ROLLS]
    for start, end in cfg.RANGES:
        chunk = expand_range(start.strip(), end.strip())
        print(f"  📋  Range {start} → {end}  =  {len(chunk):,} rolls")
        rolls += chunk
    if not rolls:
        print("\n❌  No roll numbers in roll_numbers.py!\n")
        sys.exit(1)
    seen, unique = set(), []
    for r in rolls:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    avg = (MIN_DELAY_SEC + MAX_DELAY_SEC) / 2
    print(f"  ⏱️   ~{(len(unique) * avg / 60):.0f} min for {len(unique)} rolls\n")
    return unique


# ── Download one roll ─────────────────────────────────────────────────────────

async def download_one(page, roll: str, out_dir: Path) -> str:

    url = RESULT_URL_TEMPLATE.format(regNo=roll)
    api_done   = asyncio.Event()
    api_result = {"status": None}

    async def on_response(response):
        if API_URL_PATTERN in response.url:
            try:
                data = await response.json()
                api_result["status"] = data.get("status")
            except Exception:
                try:
                    text = await response.text()
                    api_result["status"] = 200 if '"status":200' in text else 404
                except Exception:
                    api_result["status"] = 0
            api_done.set()

    page.on("response", on_response)

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as e:
        print(f"     ⚠️  Load warning: {e}")

    print(f"     ⏳  Waiting for API...")
    try:
        await asyncio.wait_for(api_done.wait(), timeout=API_TIMEOUT)
    except asyncio.TimeoutError:
        print(f"     ⚠️  API timed out")
        page.remove_listener("response", on_response)
        return "error"

    page.remove_listener("response", on_response)

    if api_result["status"] != 200:
        print(f"     ⚠️  No result found (API status: {api_result['status']})")
        return "notfound"

    # API returned 200 — wait for Angular to render data into DOM
    print(f"     ✅  API status 200 — waiting for render...")
    await page.wait_for_timeout(RENDER_WAIT)

    # Measure actual page size
    dims = await page.evaluate("""() => ({
        width:  document.documentElement.scrollWidth,
        height: document.documentElement.scrollHeight
    })""")
    pw = max(794, dims["width"])
    ph = dims["height"] + 40

    pdf_path = out_dir / f"result_{roll}.pdf"
    await page.pdf(
        path=str(pdf_path),
        width=f"{pw}px",
        height=f"{ph}px",
        print_background=True,
        margin={"top": "8mm", "bottom": "8mm",
                "left": "8mm", "right": "8mm"},
    )
    print(f"     💾  Saved → {pdf_path.name}")
    return "found"


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run_downloader(headless: bool):
    from playwright.async_api import async_playwright

    out_dir = Path(cfg.OUTPUT_DIR)
    rolls   = build_roll_list()
    out_dir.mkdir(parents=True, exist_ok=True)

    print("═" * 60)
    print("  BEU Result Downloader")
    print(f"  Total rolls  : {len(rolls):,}")
    print(f"  Saving to    : {out_dir.resolve()}")
    print(f"  Browser      : {'HEADLESS' if headless else '👁  VISIBLE'}")
    print(f"  Delay        : {MIN_DELAY_SEC}–{MAX_DELAY_SEC}s random per roll")
    print("═" * 60 + "\n")

    found = notfound = errors = 0
    error_rolls = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        for idx, roll in enumerate(rolls, 1):
            print(f"\n[{idx:>4} / {len(rolls)}]  Roll: {roll}")
            try:
                status = await download_one(page, roll, out_dir)
                if status == "found":
                    found += 1
                elif status == "notfound":
                    notfound += 1
                else:
                    errors += 1
                    error_rolls.append(roll)
            except Exception as e:
                print(f"     ✗   ERROR: {e}")
                errors += 1
                error_rolls.append(roll)

            if idx < len(rolls):
                delay = random.uniform(MIN_DELAY_SEC, MAX_DELAY_SEC)
                print(f"     ⏸️   Next in {delay:.1f}s...")
                await asyncio.sleep(delay)

        await browser.close()

    print("\n" + "═" * 60)
    print(f"  ✅  Found     : {found}")
    print(f"  ⚠️   Not found : {notfound}")
    print(f"  ❌  Errors    : {errors}")
    print(f"  📁  Folder    : {out_dir.resolve()}")
    if error_rolls:
        fail_path = out_dir / "failed_rolls.txt"
        fail_path.write_text("\n".join(error_rolls))
        print(f"  Failed rolls → {fail_path.name}")
    print("═" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="BEU Result Downloader")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser hidden (default: visible)")
    args = parser.parse_args()
    asyncio.run(run_downloader(args.headless))


if __name__ == "__main__":
    main()