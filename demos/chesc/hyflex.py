"""Access official HyFlex operators and solution memory through JPype."""
import os
from dataclasses import dataclass
from pathlib import Path
from random import Random

import jpype

# Five competition instances per domain, in CompetitionRunner.java order.
DOMAINS = {
    "sat": ("SAT.SAT", (3, 5, 4, 10, 11)),
    "binpacking": ("BinPacking.BinPacking", (7, 1, 9, 10, 11)),
    "personnel": ("PersonnelScheduling.PersonnelScheduling", (5, 9, 8, 10, 11)),
    "flowshop": ("FlowShop.FlowShop", (1, 8, 3, 10, 11)),
    "tsp": ("travelingSalesmanProblem.TSP", (0, 8, 2, 7, 6)),
    "vrp": ("VRP.VRP", (6, 2, 5, 1, 9)),
}


def start_java():
    if jpype.isJVMStarted():
        return
    home = Path(os.environ.get("HYFLEX_HOME", "."))
    jars = [home / name for name in ("chesc-ps.jar", "chesc-fixed-no-ps.jar")]
    if not all(path.is_file() for path in jars):
        raise SystemExit("Set HYFLEX_HOME to the directory containing both corrected JARs.")
    jpype.startJVM("-Xmx1g", "-Djava.awt.headless=true", classpath=list(map(str, jars)))


@dataclass(frozen=True)
class Plan:
    slot: int
    cost: float


def score(plan):
    return plan.cost


class Search:
    def __init__(self, domain, instance, seed):
        start_java()
        self.problem = jpype.JClass(DOMAINS[domain][0])(seed)
        self.problem.loadInstance(instance)
        self.problem.setMemorySize(3)
        self.problem.setDepthOfSearch(0.2)
        self.problem.setIntensityOfMutation(0.2)
        kind = jpype.JClass("AbstractClasses.ProblemDomain$HeuristicType")
        families = {
            int(i): str(family.name())
            for family in kind.values()
            for i in (self.problem.getHeuristicsOfType(family) or ())
        }
        ids = list(range(self.problem.getNumberOfHeuristics()))
        Random(seed).shuffle(ids)
        self.moves = [Move(self.problem, i, families[i]) for i in ids]
        self.initial = None

    def construct(self, incumbent, deadline):
        self.problem.initialiseSolution(0)
        self.initial = self.problem.getFunctionValue(0)
        return Plan(0, self.initial)


@dataclass(eq=False)
class Move:
    problem: object
    operator: int
    family: str

    def __call__(self, incumbent, deadline):
        # Alternate slots so a rejected trial always leaves the incumbent intact.
        target = 1 - incumbent.slot
        if self.family == "CROSSOVER":
            self.problem.initialiseSolution(2)
            self.problem.applyHeuristic(self.operator, incumbent.slot, 2, target)
        else:
            self.problem.applyHeuristic(self.operator, incumbent.slot, target)
        return Plan(target, self.problem.getFunctionValue(target))


def instances():
    return [(domain, i) for domain, (_, ids) in DOMAINS.items() for i in ids]
