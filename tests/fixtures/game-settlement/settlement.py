from wallet import credit


def eligible(score):
    return score >= 10


def settle(player, score):
    if not eligible(score):
        return {'status': 'ineligible'}
    try:
        credit(player, score)
    except ValueError:
        return {'status': 'wallet_failed'}
    return {'status': 'rewarded'}
