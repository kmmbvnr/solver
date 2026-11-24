"""Rank a checker output using the official winner vector and pairwise comparison log."""
import argparse
import csv
import json
import re
from collections import Counter
from decimal import Decimal
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("instance")
parser.add_argument("checker_output", type=Path)
parser.add_argument("official_table", type=Path)
parser.add_argument("official_log", type=Path)
parser.add_argument("winner_vectors", type=Path)
args = parser.parse_args()
table = args.official_table.read_text().split("## Rank Table for Instances")[1].split("## Values")[0]
rows = [[v.strip() for v in line.strip().strip("|").split("|")]
        for line in table.splitlines() if line.startswith("|")]
column = rows[0].index(args.instance)
ranks = {row[0]: row[column] for row in rows if re.fullmatch(r"[JS]\d+", row[0])}
with args.winner_vectors.open() as f:
    ref = next(row for row in csv.DictReader(f) if row["Instance"] == args.instance)
winner = ref["Best team"]
if ranks[winner] != "1":
    raise ValueError("Inconsistent winner")
report = json.loads(args.checker_output.read_text(), parse_float=Decimal)
if not report["valid"]:
    raise ValueError("Invalid submission")
ours = sorted((x["sat"] for x in report["saturations"]), reverse=True)
reference = [Decimal(ref[str(i)]) for i in range(1, len(ours) + 1)]
number = int(args.instance.rsplit("-", 1)[1])
scored = {team for team, rank in ranks.items() if rank != "N/A"}
known = {t: {} for t in sorted(scored)}
team = period = None
for line in args.official_log.read_text().splitlines():
    if m := re.search(r"Computing scores for team (\w+)", line):
        team, period = m[1], None
    if m := re.search(r"Instance (\d+):", line):
        period = int(m[1])
    if period != number:
        continue
    m = re.search(r"than team (\w+) \(load number (\d+): ([\d.e+-]+) [<>] ([\d.e+-]+)\)", line)
    if m:
        other, k, left, right = m.groups()
        idx = int(k) - 1
        for t, value in ((team, left), (other, right)):
            if known[t].setdefault(idx, Decimal(value)) != Decimal(value):
                raise ValueError(f"Inconsistent evidence for {t}")
        if team == winner:
            known[other].update(enumerate(reference[:idx]))
known[winner].update(enumerate(reference))
outcomes = {}
indices = Counter()
for t, values in known.items():
    for i, value in enumerate(ours):
        if i not in values:
            raise ValueError(f"Insufficient public evidence for {t} at component {i+1}")
        if values[i] != value:
            outcomes[t] = "better" if values[i] < value else "worse"
            indices[i+1] += 1
            break
    else:
        outcomes[t] = "tied"
first_difference = next((i for i, (our, best) in enumerate(zip(ours, reference)) if our != best), None)
counts = Counter(outcomes.values())
print(json.dumps(dict(instance=args.instance, rank=1+counts["better"], official_teams=len(ranks),
                      ranked_teams=len(scored), better=counts["better"], worse=counts["worse"],
                      tied=counts["tied"], invalid=len(ranks)-len(scored),
                      peak=str(ours[0]), best_peak=str(reference[0]), best_team=winner,
                      winner_comparison=(None if first_difference is None else {
                          "component": first_difference + 1, "ours": str(ours[first_difference]),
                          "winner": str(reference[first_difference])}),
                      decisive_component=dict(sorted(indices.items())), comparisons=outcomes), indent=2))
