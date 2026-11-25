"""Sort a signed permutation by reversing intervals and flipping their signs."""


def problem(stream):
    original = list(map(int, stream.read().split()))
    if sorted(map(abs, original)) != list(range(1, len(original) + 1)):
        raise ValueError("expected a signed permutation of 1..n")

    def place_in_order(backwards):
        values = original.copy()
        moves = []
        positions = {abs(v): i for i, v in enumerate(values)}

        def reverse(left, right):
            values[left:right + 1] = [-v for v in reversed(values[left:right + 1])]
            for i in range(left, right + 1):
                positions[abs(values[i])] = i
            moves.append([left + 1, right + 1])

        order = range(len(values))
        for i in reversed(order) if backwards else order:
            j = positions[i + 1]
            if i != j:
                reverse(min(i, j), max(i, j))
            if values[i] < 0:
                reverse(i, i)
        return moves

    def from_left(plan, deadline):
        return place_in_order(False)

    def from_right(plan, deadline):
        return place_in_order(True)

    return [from_left, from_right], len
