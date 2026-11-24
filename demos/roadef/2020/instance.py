"""Read the large scenario arrays one intervention at a time."""

import ijson
import numpy as np
from ijson.common import ObjectBuilder


def read(path):
    result = {"Interventions": {}}
    with path.open("rb") as stream:
        events = iter(ijson.parse(stream, use_float=True))
        for prefix, event, key in events:
            if event != "map_key" or prefix not in ("", "Interventions"):
                continue
            if not prefix and key == "Interventions":
                continue
            _, event, value = next(events)
            builder = ObjectBuilder()
            builder.event(event, value)
            if event in ("start_map", "start_array"):
                level = 1
                while level:
                    _, event, value = next(events)
                    builder.event(event, value)
                    level += (event in ("start_map", "start_array")) - (
                        event in ("end_map", "end_array")
                    )
            obj = builder.value
            if prefix:
                obj["risk"] = {
                    int(t) - 1: (
                        np.array(list(rows), dtype=int) - 1,
                        np.asarray(list(rows.values()), dtype=float),
                    )
                    for t, rows in obj["risk"].items()
                }
                result["Interventions"][key] = obj
            else:
                result[key] = obj
    return result
