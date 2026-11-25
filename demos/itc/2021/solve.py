"""Build and improve double round-robin schedules using the RobinX validator."""
import argparse
import os
import re
import subprocess
from collections import Counter
from functools import partial
from itertools import combinations
from operator import itemgetter
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from xml.etree import ElementTree as ET

from ortools.sat.python import cp_model

from shiftopt import run_pipeline


def solution(name, games, cost):
    root = ET.Element("Solution")
    meta = ET.SubElement(root, "MetaData")
    ET.SubElement(meta, "InstanceName").text = name
    ET.SubElement(meta, "Contributor").text = "ShiftOpt"
    ET.SubElement(meta, "ObjectiveValue", infeasibility="0", objective=str(cost))
    group = ET.SubElement(root, "Games")
    for home, away, slot in games:
        ET.SubElement(group, "ScheduledMatch", home=home, away=away, slot=slot)
    return ET.tostring(root, encoding="utf-8")


def evaluate(instance, name, work, games, deadline):
    if monotonic() >= deadline:
        return None
    work.write_bytes(solution(name, games, 0))
    try:
        result = subprocess.run([os.environ["ROBINX"], "-i", instance, "-s", work],
                                capture_output=True, check=False, text=True,
                                timeout=max(0, deadline - monotonic()))
    except subprocess.TimeoutExpired:
        return None
    match = re.search(r"^\s*Objective:\s+(\d+)\s+(\d+)\s*$", result.stdout, re.MULTILINE)
    if match is None:
        raise ValueError("RobinX returned no integer objective")
    if int(match[1]) == 0:
        return int(match[2]), games
    return None


def seed_schedule(check, teams, slots, path, incumbent, deadline):
    games = [(g.attrib["home"], g.attrib["away"], g.attrib["slot"])
             for g in ET.parse(path).findall("Games/ScheduledMatch")]
    pairs = Counter((h, v) for h, v, _ in games)
    appearances = Counter((team, s) for h, v, s in games for team in (h, v))
    if pairs != {(h, v): 1 for h in teams for v in teams if h != v} or appearances != {
        (team, s): 1 for team in teams for s in slots
    }:
        raise ValueError("Seed must schedule every directed fixture and one match per team per round")
    return check(games, deadline)


def pairings(teams, slots):
    order = list(teams)
    games = []
    for week in range(len(order) - 1):
        for i in range(len(order) // 2):
            home, away = order[i], order[-i - 1]
            if (i + week) % 2:
                home, away = away, home
            games.extend(((home, away, slots[week]), (away, home, slots[week + len(order) - 1])))
        order = [order[0], order[-1], *order[1:-1]]
    return games


def circle(check, teams, slots, incumbent, deadline):
    return check(pairings(teams, slots), deadline)


def orient(check, tree, teams, slots, incumbent, deadline):
    model = cp_model.CpModel()
    games = incumbent[1] if incumbent else [(h, v, s) for h in teams for v in teams
                                            if h != v for s in slots]
    options = set(games)
    if incumbent:
        options.update((v, h, s) for h, v, s in games)
    play = {game: model.new_bool_var("") for game in sorted(options)}
    at_home = {}
    for h in teams:
        for v in teams:
            if h != v:
                model.add_exactly_one(x for s in slots if (x := play.get((h, v, s))) is not None)
        for s in slots:
            home = [play[h, v, s] for v in teams if (h, v, s) in play]
            away = [play[v, h, s] for v in teams if (v, h, s) in play]
            model.add_exactly_one(home + away)
            at_home[h, s] = sum(home)
    if tree.findtext(".//gameMode") == "P":
        for a, b in combinations(teams, 2):
            model.add_exactly_one(play[h, v, s] for h, v in ((a, b), (b, a))
                                  for s in slots[:len(slots) // 2] if (h, v, s) in play)
    penalties = []
    for rule in tree.findall(".//CA1"):
        selected = rule.get("slots").split(";")
        for team in rule.get("teams").split(";"):
            count = sum(at_home[team, s] for s in selected)
            if rule.get("mode") == "A":
                count = len(selected) - count
            if rule.get("mode") not in ("H", "A"):
                continue
            low, high = int(rule.get("min")), int(rule.get("max"))
            if rule.get("type") == "HARD":
                model.add_linear_constraint(count, low, high)
            else:
                excess = model.new_int_var(0, len(selected), "")
                model.add_max_equality(excess, [0, low - count, count - high])
                penalties.append(excess * int(rule.get("penalty")))
    model.minimize(sum(penalties))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = min(3, max(0, deadline - monotonic()))
    solver.parameters.num_search_workers = 1
    if solver.solve(model) in (cp_model.FEASIBLE, cp_model.OPTIMAL):
        proposal = [game for game, x in play.items() if solver.value(x)]
        return check(proposal, deadline)
    return None


def improve(check, values, change, incumbent, deadline):
    if incumbent is None:
        return None
    best = incumbent
    for a, b in combinations(values, 2):
        if monotonic() >= deadline:
            break
        candidate = check(change(best[1], a, b), deadline)
        if candidate is not None and candidate[0] < best[0]:
            best = candidate
    return best


def exchange_rounds(games, a, b):
    swap = {a: b, b: a}
    return [(h, v, swap.get(t, t)) for h, v, t in games]


def reverse_pair(games, a, b):
    return [(v, h, t) if (h, v) in ((a, b), (b, a)) else (h, v, t) for h, v, t in games]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--seconds", type=float, default=30)
    args = parser.parse_args()
    tree = ET.parse(args.input)
    name = tree.findtext("MetaData/InstanceName")
    teams = [t.get("id") for t in tree.findall("Resources/Teams/team")]
    slots = [s.get("id") for s in tree.findall("Resources/Slots/slot")]
    if not teams or len(teams) % 2 or len(slots) != 2 * (len(teams) - 1):
        parser.error("expected an even-team compact double round robin")
    with TemporaryDirectory() as tmp:
        work = Path(tmp) / "candidate.xml"
        check = partial(evaluate, args.input, name, work)
        steps = [partial(circle, check, teams, slots)]
        if args.seed:
            steps.append(partial(seed_schedule, check, teams, slots, args.seed))
        steps.append(partial(orient, check, tree, teams, slots))
        steps.extend((partial(improve, check, teams, reverse_pair),
                      partial(improve, check, slots, exchange_rounds)))
        best = run_pipeline(steps, itemgetter(0), seconds=args.seconds)
    if best is None:
        parser.exit(1, "No feasible calendar found. Supply a feasible --seed for this instance.\n")
    args.output.write_bytes(solution(name, best[1], best[0]))
    print(best[0])


if __name__ == "__main__":
    main()
