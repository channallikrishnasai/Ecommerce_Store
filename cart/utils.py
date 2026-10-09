from typing import Optional

from django.db.models import Q

from .models import Order


def get_or_set_order_session(request) -> Order:
    order_id: Optional[int] = request.session.get('order_id', None)
    if order_id is not None:
        orders = Order.objects.filter(id=order_id, ordered=False)
        if request.user.is_authenticated:
            orders = orders.filter(Q(user=request.user) | Q(user__isnull=True))
        else:
            orders = orders.filter(user__isnull=True)
        order = orders.first()
    else:
        order = None

    if order is None:
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
        )
        request.session['order_id'] = order.id

    if request.user.is_authenticated and order.user is None:
        order.user = request.user
        order.save(update_fields=['user', ])
    return order


__all__ = ('get_or_set_order_session',)
