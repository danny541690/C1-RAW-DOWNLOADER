"""JARVIS C1 v0.93: independent RAW first-layer historical continuation.

Start from verified prior checkpoint: 2015-04 month-closed; 2015-03 partial.
Do not modify prior workflow cursors. Reuse only verified RAW bytes in shared
01_RAW, keep native sources separate, and queue FinMind for explicit gaps.
"""
import argparse
import scripts.v093_independent_raw as raw

START = "2015-03"
END = "2000-01"
MONTHS = [f"{y}-{m:02d}" for y in range(2015, 1999, -1)
          for m in range(12, 0, -1)
          if END <= f"{y}-{m:02d}" <= START]
assert len(MONTHS) == 183 and MONTHS[0] == START and MONTHS[-1] == END

def run(minutes):
    raw.RUN = "RAW_201503_TO_200001_V1"
    raw.WORKFLOW = "v093-raw-2015-to-2000.yml"
    raw.month_plan = lambda today: list(MONTHS)
    raw.Independent(minutes).run()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=40)
    args = parser.parse_args()
    run(args.minutes)
