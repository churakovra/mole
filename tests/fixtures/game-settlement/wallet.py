BALANCES = {}


def credit(player, amount):
    if amount < 0:
        raise ValueError('negative amount')
    BALANCES[player] = BALANCES.get(player, 0) + amount


def purchase(player, cost):
    if BALANCES.get(player, 0) < cost:
        raise ValueError('insufficient balance')
    BALANCES[player] -= cost
