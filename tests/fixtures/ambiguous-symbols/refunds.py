"""Independent flow sharing a callable basename with the orders module."""


def process_order(order):
    return {'status': 'refund_queued', 'id': order['id']}
