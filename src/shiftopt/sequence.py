"""Compose moves that are evaluated together by the enclosing pipeline."""
from time import monotonic


def move_sequence(*moves):
    """Forward each proposal to the next move. A declined move abandons the sequence."""
    if not moves:
        raise ValueError("supply at least one move")

    def propose(plan, deadline):
        for move in moves:
            if monotonic() >= deadline:
                return None
            plan = move(plan, deadline)
            if plan is None:
                return None
        return plan
    return propose
