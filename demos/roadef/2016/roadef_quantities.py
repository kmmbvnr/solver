"""Maximize deliveries on a fixed ROADEF schedule using bounded network flow."""
import argparse
from collections import defaultdict
from itertools import accumulate, count
import json
from pathlib import Path
import time
import xml.etree.ElementTree as ET

from shiftopt import bounded_max_flow


def delivery_flow(problem, plan):
    unit = int(problem.findtext("unit"))
    customers = {int(c.findtext("index")): c for c in problem.find("customers")}
    trailers = list(problem.find("trailers"))
    source, sink = 0, 1
    nodes = count(2)
    edges = []
    visits = defaultdict(list)
    stops = defaultdict(list)
    operations = []
    baseline = 0.

    def edge(a, b, low, high):
        edges.append((a, b, low, high))
        return len(edges) - 1

    for shift in plan.find("Shifts"):
        k = int(shift.findtext("trailer"))
        capacity = float(trailers[k].findtext("Capacity"))
        for op in shift.find("operations"):
            point = int(op.findtext("point"))
            at = int(op.findtext("arrival"))
            node = next(nodes)
            stops[k].append((at, node))
            if point in customers:
                customer = customers[point]
                low = 0. if int(customer.findtext("callIn")) else float(customer.findtext("MinOperationQuantity"))
                receipt = next(nodes)
                visits[point].append((at, receipt))
                if low > capacity:
                    return None
                index = edge(node, receipt, low, capacity)
                operations.append((op, index, 1))
                baseline += float(op.findtext("Quantity"))
            else:
                operations.append((op, edge(source, node, 0., capacity), -1))

    for k, events in stops.items():
        ordered = [node for _, node in sorted(events)]
        capacity = float(trailers[k].findtext("Capacity"))
        opening = float(trailers[k].findtext("InitialQuantity"))
        edge(source, ordered[0], opening, opening)
        for left, right in zip(ordered, ordered[1:]):
            edge(left, right, 0., capacity)
        edge(ordered[-1], source, 0., capacity)

    # All receipt flows together are bounded by the sum of trailer capacities per visit.
    upper = sum(edges[index][3] for _, index, sign in operations if sign == 1)
    for point, customer in customers.items():
        arrivals = visits[point]
        if int(customer.findtext("callIn")):
            matched = []
            for order in customer.find("orders"):
                a, b = (int(order.findtext(k)) for k in ("earliestTime", "latestTime"))
                group = next(nodes)
                target = float(order.findtext("Quantity"))
                edge(group, sink, target * float(order.findtext("orderQuantityFlexibility")) / 100., target)
                for at, receipt in arrivals:
                    if a <= at <= b:
                        edge(receipt, group, 0., upper)
                        matched.append(receipt)
            if sorted(matched) != sorted(receipt for _, receipt in arrivals):
                return None
            continue

        forecast = list(accumulate(float(v.text) for v in customer.find("Forecast")))
        opening = float(customer.findtext("InitialTankQuantity"))
        capacity = float(customer.findtext("Capacity"))
        safety = float(customer.findtext("SafetyLevel"))
        periods = {0: next(nodes)}
        for at, receipt in arrivals:
            tick = at // unit
            if tick not in periods:
                periods[tick] = next(nodes)
            edge(receipt, periods[tick], 0., upper)
        ticks = sorted(periods)
        for tick, following in zip(ticks, ticks[1:] + [len(forecast)]):
            # This edge carries all deliveries up to the current period.
            low = max(0., safety - opening + forecast[following - 1])
            high = capacity - opening + forecast[tick]
            if high < low:
                return None
            edge(periods[tick], periods.get(following, sink), low, high)

    flows = bounded_max_flow(next(nodes), edges, source, sink)
    if flows is None:
        return None
    delivered = sum(flows[index] for _, index, sign in operations if sign == 1)
    for op, index, sign in operations:
        op.find("Quantity").text = f"{sign * flows[index]:.8f}"
    return baseline, delivered, len(operations), len(edges)


def optimize(instance, seed, output):
    begin = time.monotonic()
    plan = ET.parse(seed)
    result = delivery_flow(ET.parse(instance).getroot(), plan.getroot())
    if result is None:
        raise ValueError("No feasible quantities for this schedule")
    baseline, delivered, variables, edges = result
    if delivered < baseline - 1e-5:
        raise ValueError("Warm schedule violates quantity model")
    plan.write(output, encoding="utf-8", xml_declaration=True)
    return dict(start_kg=baseline, optimized_kg=delivered, quantity_variables=variables,
                flow_edges=edges, seconds=time.monotonic() - begin)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('instance',type=Path)
    p.add_argument('seed',type=Path)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(optimize(a.instance,a.seed,a.output)))
