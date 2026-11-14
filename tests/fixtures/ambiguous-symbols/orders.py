"""Static ambiguity fixture: this name alone cannot select the intended flow."""


def process_order(order):
    return {'status': 'accepted', 'id': order['id']}
