"""Improve one timed route at a time and rebalance the resulting delivery plan."""
from functools import lru_cache
from time import monotonic

from instance_xml import table
from roadef_quantities import delivery_flow
from roadef_route_pool import plan_tree, read_routes, route_cost_end, terminal_stops, variations


class RouteSearch:
    def __init__(self, problem):
        self.problem = problem
        self.drivers = list(problem.find("drivers"))
        self.trailers = list(problem.find("trailers"))
        self.sites = {int(c.findtext("index")): c for c in problem.find("customers")}
        self.setup = {int(c.findtext("index")): int(c.findtext("setupTime"))
                      for group in ("sources", "customers") for c in problem.find(group)}
        self.travel = table(problem, "timeMatrices")
        self.km = table(problem, "DistMatrices")
        self.horizon = int(problem.findtext("unit")) * int(problem.findtext("horizon"))
        self.cost_end = lru_cache(maxsize=4096)(
            lambda r: route_cost_end(r, self.drivers, self.trailers, self.setup, self.travel, self.km))

    def score(self, plan):
        delivered = sum(q for r, amounts in plan.items() for (p, _), q in zip(r.ops, amounts)
                        if p in self.sites)
        return sum(self.cost_end(r)[0] for r in plan) / delivered

    def compatible(self, route, remaining):
        end = self.cost_end(route)[1]
        for other in remaining:
            if other.driver == route.driver:
                rest = int(self.drivers[route.driver].findtext("minInterSHIFTDURATION"))
            elif other.trailer == route.trailer:
                rest = 0
            else:
                continue
            if route.start < self.cost_end(other)[1] + rest and other.start < end + rest:
                return False
        return True

    def improve(self, plan, deadline):
        best = plan
        score = self.score(plan)
        for original in plan:
            if original.start >= 4 * 1440:
                continue
            options = terminal_stops([original], 4, self.drivers, self.trailers, self.sites,
                                     self.setup, self.travel, self.km, self.horizon, True)
            options = variations(options, (-60, 60), self.drivers, self.sites,
                                 self.setup, self.travel, self.horizon)
            remaining = best.copy()
            del remaining[original]
            for route in options:
                if monotonic() >= deadline:
                    return best
                if route == original or not self.compatible(route, remaining):
                    continue
                trial = plan_tree({**remaining, route: (0.,) * len(route.ops)})
                if delivery_flow(self.problem, trial) is None:
                    continue
                candidate = read_routes(trial)
                value = self.score(candidate)
                if value < score:
                    best, score = candidate, value
        return best
