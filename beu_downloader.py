#!/usr/bin/env python3
"""
BEU Result Downloader — Bihar Engineering University
Run:   python beu_downloader.py           (visible browser)
       python beu_downloader.py --headless (hidden)
       python beu_downloader.py --inspect  (check form fields)
"""

import asyncio
import argparse
import sys
from pathlib import Path

try:
    import roll_numbers as cfg
except ModuleNotFoundError:
    print("\n❌  roll_numbers.py not found! Put it in the same folder.\n")
    sys.exit(1)

BASE_URL = (
    "https://beu-bih.ac.in/result-two/"
    "B.Tech.%206th%20Semester%20Examination,%202025"
    "?semester=6&session=2025&exam_held=November%2F2025"
)

TYPING_DELAY  = 60     # ms between keystrokes
RESULT_WAIT   = 5000   # ms to wait after submit for result to render


# ── Roll number helpers ───────────────────────────────────────────────────────

def expand_range(start: str, end: str) -> list:
    if len(start) != len(end):
        raise ValueError(f"Length mismatch: {start!r} vs {end!r}")
    L      = len(start)
    SUFFIX = 4
    prefix = start[:L - SUFFIX]
    s      = int(start[L - SUFFIX:])
    e      = int(end  [L - SUFFIX:])
    if s > e:
        raise ValueError("Start must be ≤ End")
    return [f"{prefix}{i:0{SUFFIX}d}" for i in range(s, e + 1)]


def build_roll_list() -> list:
    rolls = [r.strip() for r in cfg.INDIVIDUAL_ROLLS]
    for start, end in cfg.RANGES:
        chunk = expand_range(start.strip(), end.strip())
        print(f"  📋  Range {start} → {end}  =  {len(chunk):,} roll numbers")
        rolls += chunk
    if not rolls:
        print("\n❌  No roll numbers in roll_numbers.py!\n")
        sys.exit(1)
    seen, unique = set(), []
    for r in rolls:
        if r not in seen:
            seen.add(r)
            unique.append(r)
    return unique


# ── Safe page loader (never times out on networkidle) ─────────────────────────

async def safe_goto(page, url: str):
    """
    Load a page safely.
    BEU site never reaches 'networkidle' so we use 'domcontentloaded'
    then wait manually for JS to render content.
    """
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
    except Exception as e:
        print(f"     ⚠️  Page load warning (continuing anyway): {e}")
    # Give JS frameworks time to render the UI
    await page.wait_for_timeout(3000)


# ── Inspector ─────────────────────────────────────────────────────────────────

async def inspect_page():
    from playwright.async_api import async_playwright

    print(f"\n🔍  Loading page (please wait ~5 seconds)...")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page    = await context.new_page()

        await safe_goto(page, BASE_URL)

        # Dump all inputs and buttons from the live DOM
        inputs = await page.evaluate("""() =>
            Array.from(document.querySelectorAll('input')).map(el => ({
                type:        el.type,
                id:          el.id,
                name:        el.name,
                placeholder: el.placeholder,
                className:   el.className.substring(0, 80),
            }))
        """)

        buttons = await page.evaluate("""() =>
            Array.from(document.querySelectorAll('button, input[type="submit"]')).map(el => ({
                tag:  el.tagName,
                type: el.type,
                id:   el.id,
                text: (el.innerText || el.value || '').trim().substring(0, 50),
                cls:  el.className.substring(0, 80),
            }))
        """)

        await browser.close()

    # ── Print ──────────────────────────────────────────────────────────────────
    print("\n" + "═" * 70)
    print("  INPUTS FOUND ON BEU PAGE")
    print("═" * 70)
    if inputs:
        for i, el in enumerate(inputs):
            print(f"  [{i}] type={el['type']!r:12}  id={el['id']!r:25}  "
                  f"name={el['name']!r:20}  placeholder={el['placeholder']!r}")
    else:
        print("  ⚠️  No <input> found — page may not have loaded properly.")

    print("\n" + "═" * 70)
    print("  BUTTONS FOUND ON BEU PAGE")
    print("═" * 70)
    if buttons:
        for i, el in enumerate(buttons):
            print(f"  [{i}] {el['tag']:8}  type={el['type']!r:12}  "
                  f"id={el['id']!r:25}  text={el['text']!r}")
    else:
        print("  ⚠️  No <button> found.")

    print("\n  👆  Share this output — I'll hardcode exact selectors for your site.\n")


# ── Smart field finders ───────────────────────────────────────────────────────

async def find_roll_input(page):
    """Try selectors from most specific to least specific."""
    for sel in [
        "input[name='roll_no']",
        "input[name='rollno']",
        "input[name='roll']",
        "input[name='registration']",
        "input[name='reg_no']",
        "input[name='regno']",
        "input[id*='roll']",
        "input[id*='reg']",
        "input[placeholder*='Roll']",
        "input[placeholder*='roll']",
        "input[placeholder*='Reg']",
        "input[placeholder*='Number']",
        "input[type='number']",
        "input[type='text']",
    ]:
        loc = page.locator(sel).first
        try:
            if await loc.count() > 0:
                print(f"     🎯  Roll input found  →  {sel}")
                return loc
        except Exception:
            continue
    return None


async def find_submit(page):
    """Try selectors from most specific to least specific."""
    for sel in [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit')",
        "button:has-text('Search')",
        "button:has-text('Get Result')",
        "button:has-text('View Result')",
        "button:has-text('Check')",
        "button:has-text('Go')",
        "button",
    ]:
        loc = page.locator(sel).first
        try:
            if await loc.count() > 0:
                print(f"     🎯  Submit button found  →  {sel}")
                return loc
        except Exception:
            continue
    return None


# ── Download single roll number ───────────────────────────────────────────────

async def download_one(page, roll: str, out_dir: Path) -> bool:
    # Step 1: Load the page
    await safe_goto(page, BASE_URL)

    # Step 2: Find roll input
    roll_input = await find_roll_input(page)
    if roll_input is None:
        print("     ❌  Roll input not found! Run --inspect to debug.")
        return False

    # Step 3: Clear and type roll number
    await roll_input.click()
    await roll_input.fill("")
    await roll_input.type(roll, delay=TYPING_DELAY)
    print(f"     ✎   Typed roll number: {roll}")

    # Step 4: Submit
    submit = await find_submit(page)
    if submit:
        await submit.click()
        print("     ↵   Clicked submit")
    else:
        await roll_input.press("Enter")
        print("     ↵   Pressed Enter")

    # Step 5: Wait for result to render
    await page.wait_for_timeout(RESULT_WAIT)

    # Step 6: Save as PDF
    pdf_path = out_dir / f"result_{roll}.pdf"
    await page.pdf(
        path=str(pdf_path),
        format="A4",
        print_background=True,
        margin={"top": "10mm", "bottom": "10mm",
                "left": "10mm", "right": "10mm"},
    )
    print(f"     ✔   Saved → {pdf_path}")
    return True


# ── Main loop ─────────────────────────────────────────────────────────────────

async def run_downloader(headless: bool):
    from playwright.async_api import async_playwright

    out_dir = Path(cfg.OUTPUT_DIR)
    delay   = float(cfg.DELAY_SECONDS)
    rolls   = build_roll_list()

    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "═" * 65)
    print("  BEU Result Downloader")
    print(f"  Total rolls   : {len(rolls):,}")
    print(f"  Saving to     : {out_dir.resolve()}")
    print(f"  Browser       : {'HEADLESS' if headless else '👁  VISIBLE'}")
    print(f"  Delay         : {delay}s between rolls")
    print("═" * 65 + "\n")

    success, failed = 0, []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            slow_mo=50 if not headless else 0,
        )
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
                ok = await download_one(page, roll, out_dir)
                if ok:
                    success += 1
                else:
                    failed.append(roll)
            except Exception as e:
                print(f"     ✗   ERROR: {e}")
                failed.append(roll)

            if idx < len(rolls):
                await asyncio.sleep(delay)

        await browser.close()

    print("\n" + "═" * 65)
    print(f"  ✅  Success : {success} / {len(rolls)}")
    print(f"  📁  Folder  : {out_dir.resolve()}")
    if failed:
        print(f"  ❌  Failed  : {len(failed)}")
        fail_path = out_dir / "failed_rolls.txt"
        fail_path.write_text("\n".join(failed))
        print(f"  Failed rolls saved to → {fail_path}")
        print(f"  Retry: add them to INDIVIDUAL_ROLLS in roll_numbers.py")
    print("═" * 65 + "\n")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="BEU Result Downloader")
    parser.add_argument("--headless", action="store_true",
                        help="Run browser hidden (default: visible)")
    parser.add_argument("--inspect",  action="store_true",
                        help="Print all inputs/buttons on the BEU page and exit")
    args = parser.parse_args()

    if args.inspect:
        asyncio.run(inspect_page())
    else:
        asyncio.run(run_downloader(args.headless))


if __name__ == "__main__":
    main()