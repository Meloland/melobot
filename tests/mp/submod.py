from asyncio import run


async def get_sum(r_bound: int) -> int:
    return sum(range(1, r_bound + 1))


def sync_get_sum(r_bound: int) -> int:
    return sum(range(1, r_bound + 1))


def main():
    r_bound = 10000
    result = run(get_sum(r_bound))
    print(f"\nSum of numbers from 1 to {r_bound} is: {result}")
