# =============================================================
#   roll_numbers.py  —  EDIT THIS FILE TO ADD YOUR ROLL NOs
#   Keep both files in the SAME folder.
# =============================================================

# ── Individual roll numbers ───────────────────────────────────
# Add specific roll numbers inside the list below.
INDIVIDUAL_ROLLS = [
    # "22101105001",
    # "22101106042",
]

# ── Ranges ────────────────────────────────────────────────────
# Each entry: ("START", "END")  —  both inclusive
# Last 4 digits are the running counter.
# ("22101105001", "22101108060") → generates 3060 roll numbers
RANGES = [
    # ("22101108010", "22101108060"),   # ← change these to your range
    ("22105108001", "22105108060"), # ← full big range (uncomment to use)
]

# ── Where to save PDFs ────────────────────────────────────────
OUTPUT_DIR = "beu_results"

# ── Delay between each roll (seconds) ────────────────────────
# Keep at 3+ to avoid overwhelming the server
DELAY_SECONDS = 3