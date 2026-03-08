#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════╗
║         BEU Result Downloader  (Headed / Visible)        ║
║         Bihar Engineering University – B.Tech            ║
╚══════════════════════════════════════════════════════════╝

INSTALL (once):
    pip install playwright
    playwright install chromium

RUN EXAMPLES:
    # Single roll number
    python beu_result_downloader.py --roll 22101105001

    # Multiple roll numbers
    python beu_result_downloader.py --roll 22101105001 22101105002 22101106010

    # Range  (e.g. 22101105001 to 22101105060)
    python beu_result_downloader.py --range 22101105001 22101105060

    # BIG range across branches (22101105001 to 22101108060)
    python beu_result_downloader.py --range 22101105001 22101108060

    # Multiple separate ranges
    python beu_result_downloader.py --range 22101105001 22101105060 --range 22101107001 22101107050

    # From a text file (one roll number per line)
    python beu_result_downloader.py --roll-file rolls.txt

    # Custom output folder
    python beu_result_downloader.py --range 22101105001 22101108060 --out-dir D:/BEU_Results

HOW ROLL RANGES WORK:
    BEU roll numbers look like:  2210110 | 5 | 001
                                  prefix  branch  serial
    --range 22101105001 22101108060
    The last 4 digits (branch + serial) are treated as a running
    counter. Every number from 5001 to 8060 is generated:
    22101105001, 22101105002 ... 22101108059, 22101108060
"""

import asyncio
import argparse
import sys
from pathlib import Path

# ─── CONFIGURATION (edit if needed) ──────────────────────────────────────────

BASE_URL = (
    "https://beu-bih.ac.in/result-two/"
    "B.Tech.%206th%20Semester%20Examination,%202025"
    "?semester=6&session=2025&exam_held=November%2F2025"
)

# CSS selectors for the roll-number input and submit button.
# Open the page in Chrome → F12 → inspect the form elements and update if needed.
ROLL_INPUT_SELECTOR = "input[name='roll_no'], input[placeholder*='Roll'], input[id*='roll'], input[type='text']"
SUBMIT_BTN_SELECTOR = "button[type='submit'], input[type='submit'], button:has-text('Submit'), button:has-text('Search'), button:has-text('Get Result')"

DEFAULT_OUT_DIR     = Path("beu_results")
DELAY_SECONDS       = 3      # wait between each roll number (be kind to server)
PAGE_LOAD_WAIT_MS   = 5000   # ms to wait after submitting form

# ─────────────────────────────────────────────────────────────────────────────


# ── Roll-number helpers ───────────────────────────────────────────────────────

def roll_range(start: str, end: str) -> list:
    """
    Generate all roll numbers from start to end inclusive.

    The last 4 digits are used as the running counter,
    the remaining prefix is kept fixed.

    Example:
        roll_range("22101105001", "22101108060")
        → ["22101105001", "22101105002", ..., "22101108060"]
          (3060 roll numbers total)
    """
    if len(start) != len(end):
        raise ValueError(
            f"Roll number lengths differ: {start!r} ({len(start)}) vs {end!r} ({len(end)})"
        )

    suffix_len = 4
    n          = len(start)
    prefix     = start[: n - suffix_len]
    s          = int(start[n - suffix_len :])
    e          = int(end  [n - suffix_len :])

    if s > e:
        raise ValueError(f"Start {start} must be <= end {end}")

    return [f"{prefix}{i:0{suffix_len}d}" for i in range(s, e + 1)]


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="BEU Result Downloader – saves each result as a PDF",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    src = p.add_argument_group("Roll-number sources  (combine any of these freely)")
    src.add_argument(
        "--roll", nargs="+", metavar="ROLL",
        help="One or more individual roll numbers",
    )
    src.add_argument(
        "--range", nargs=2, metavar=("START", "END"),
        action="append", dest="ranges",
        help="A start–end range  e.g. --range 22101105001 22101108060  (repeatable)",
    )
    src.add_argument(
        "--roll-file", metavar="FILE",
        help="Path to a text file with one roll number per line",
    )

    p.add_argument(
        "--out-dir", default=str(DEFAULT_OUT_DIR),
        help=f"Folder to save PDFs (default: {DEFAULT_OUT_DIR})",
    )
    p.add_argument(
        "--delay", type=float, default=DELAY_SECONDS,
        help=f"Seconds to wait between roll numbers (default: {DELAY_SECONDS})",
    )
    p.add_argument(
        "--headless", action="store_true",
        help="Run browser in headless (hidden) mode. Default: HEADED (you see the browser).",
    )
    return p.parse_args()


def build_roll_list(args) -> list:
    rolls = []

    if args.roll:
        rolls += [r.strip() for r in args.roll]

    if args.ranges:
        for start, end in args.ranges:
            chunk = roll_range(start.strip(), end.strip())
            print(f"  Range {start} → {end}  ({len(chunk)} roll numbers)")
            rolls += chunk

    if args.roll_file:
        path = Path(args.roll_file)
        if not path.exists():
            print(f"❌  Roll file not found: {path}")
            sys.exit(1)
        with open(path) as f:
            rolls += [line.strip() for line in f if line.strip()]

    if not rolls:
        print("\n❌  No roll numbers supplied!\n")
        print("Examples:")
        print("  python beu_result_downloader.py --roll 22101105001")
        print("  python beu_result_downloader.py --range 22101105001 22101108060")
        print("  python beu_result_downloader.py --roll-file my_rolls.txt\n")
        sys.exit(1)

    # Deduplicate while preserving order
    seen, unique = set(), []
    for r in rolls:
        if r not in seen:
            seen.add(r)
            unique.append(r)

    if len(unique) < len(rolls):
        print(f"  (Removed {len(rolls) - len(unique)} duplicate roll numbers)")

    return unique


# ── Core download ─────────────────────────────────────────────────────────────

async def download_result(page, roll: str, out_dir: Path):
    """Open result page, fill roll number, submit, save PDF."""

    await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60_000)
    await page.wait_for_timeout(1500)

    # Find roll-number input
    roll_input = page.locator(ROLL_INPUT_SELECTOR).first

    if await roll_input.count() > 0:
        await roll_input.fill("")
        await roll_input.type(roll, delay=50)      # type slowly (more human-like)

        # Submit
        submit_btn = page.locator(SUBMIT_BTN_SELECTOR).first
        if await submit_btn.count() > 0:
            await submit_btn.click()
            print("     ↵  Form submitted")
        else:
            await roll_input.press("Enter")
            print("     ↵  Pressed Enter on input")

        await page.wait_for_timeout(PAGE_LOAD_WAIT_MS)
    else:
        print("     ⚠  Could not find roll-number input — saving raw page")

    # Save to PDF
    pdf_path = out_dir / f"result_{roll}.pdf"
    await page.pdf(
        path=str(pdf_path),
        format="A4",
        print_background=True,
        margin={"top": "10mm", "bottom": "10mm", "left": "10mm", "right": "10mm"},
    )
    print(f"     ✔  Saved → {pdf_path.name}")
    return pdf_path


# ── Main runner ───────────────────────────────────────────────────────────────

async def run(rolls: list, out_dir: Path, delay: float, headless: bool):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("\n❌  Playwright is not installed. Run:\n")
        print("        pip install playwright")
        print("        playwright install chromium\n")
        sys.exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 62)
    print("  BEU Result Downloader")
    print(f"  Total roll numbers : {len(rolls)}")
    print(f"  Output folder      : {out_dir.resolve()}")
    print(f"  Browser mode       : {'headless (hidden)' if headless else '🖥  HEADED – browser window is VISIBLE'}")
    print(f"  Delay between rolls: {delay} s")
    print("=" * 62)

    failed = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--start-maximized"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        for idx, roll in enumerate(rolls, 1):
            print(f"\n[{idx:>4}/{len(rolls)}]  Roll: {roll}")
            try:
                await download_result(page, roll, out_dir)
            except Exception as exc:
                print(f"     ✗  ERROR: {exc}")
                failed.append(roll)

            if idx < len(rolls):
                await asyncio.sleep(delay)

        await browser.close()

    # ── Summary ───────────────────────────────────────────────────────────────
    ok = len(rolls) - len(failed)
    print("\n" + "=" * 62)
    print(f"  ✅  Success : {ok}/{len(rolls)}")
    print(f"  📁  Folder  : {out_dir.resolve()}")

    if failed:
        print(f"  ❌  Failed  : {len(failed)}")
        fail_file = out_dir / "failed_rolls.txt"
        fail_file.write_text("\n".join(failed))
        print(f"\n  Failed rolls saved to: {fail_file.name}")
        print(f"  Retry failed ones with:")
        print(f"      python {Path(sys.argv[0]).name} --roll-file \"{fail_file}\"")

    print("=" * 62 + "\n")


def main():
    args    = parse_args()
    rolls   = build_roll_list(args)
    out_dir = Path(args.out_dir)
    asyncio.run(run(rolls, out_dir, args.delay, args.headless))


if __name__ == "__main__":
    main()