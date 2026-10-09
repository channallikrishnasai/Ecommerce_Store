from decimal import Decimal, InvalidOperation
import json
from logging import getLogger
from typing import Any, Dict, List
from urllib.parse import quote

import stripe
import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse, HttpResponse, HttpResponseRedirect
from django.shortcuts import (get_object_or_404, reverse, redirect)
from django.utils import timezone
from django.views import generic
from django.views.decorators.csrf import csrf_exempt

from .forms import (
    AddToCartForm,
    AddressForm,
    StripePaymentForm,
)
from .models import (
    Product,
    OrderItem,
    Address,
    Payment,
    Order,
    Category,
    StripePayment,
)
from .utils import get_or_set_order_session

logger = getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


def _paypal_access_token():
    if settings.PAYPAL_ENV not in {'sandbox', 'live'}:
        raise ValueError("PAYPAL_ENV must be 'sandbox' or 'live'.")
    if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_SECRET_KEY:
        raise ValueError("PayPal credentials are not configured.")

    api_base = (
        "https://api-m.sandbox.paypal.com"
        if settings.PAYPAL_ENV == "sandbox"
        else "https://api-m.paypal.com"
    )
    response = requests.post(
        f"{api_base}/v1/oauth2/token",
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET_KEY),
        data={"grant_type": "client_credentials"},
        timeout=(5, 15),
    )
    response.raise_for_status()
    access_token = response.json()["access_token"]
    if not access_token:
        raise ValueError("PayPal did not return an access token.")
    return api_base, access_token


class ProductListView(generic.ListView):
    template_name: str = 'cart/product_list.html'

    def get_queryset(self):
        qs = Product.objects.filter(active=True)
        category = self.request.GET.get('category', None)
        if not category:
            return qs
        return qs.filter(
            Q(primary_category__name=category) |
            Q(secondary_categories__name=category)
        ).distinct()

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super(ProductListView, self).get_context_data(**kwargs)
        context.update({"categories": Category.objects.values("name")})
        return context


class ProductDetailView(generic.FormView):
    template_name: str = 'cart/product_detail.html'
    form_class = AddToCartForm

    def get_object(self):
        return get_object_or_404(Product, slug=self.kwargs["slug"], active=True)

    def get_success_url(self) -> str:
        return reverse("cart:summary")

    def get_form_kwargs(self):
        kwargs = super(ProductDetailView, self).get_form_kwargs()
        kwargs["product_id"] = self.get_object().id
        return kwargs

    def form_valid(self, form):
        order = get_or_set_order_session(self.request)
        product = self.get_object()

        item_filter = order.items.filter(
            product=product,
            colour=form.cleaned_data['colour'],
            size=form.cleaned_data['size'],
        )
        item = item_filter.first()
        requested_quantity = form.cleaned_data['quantity'] + (
            item.quantity if item else 0
        )
        if requested_quantity > product.stock:
            form.add_error(
                'quantity',
                f"The maximum stock available is {product.stock}.",
            )
            return self.form_invalid(form)

        if item is None:
            new_item = form.save(commit=False)
            new_item.product = product
            new_item.order = order
            new_item.save()
        else:
            item.quantity = requested_quantity
            item.save()

        return super(ProductDetailView, self).form_valid(form)

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super(ProductDetailView, self).get_context_data(**kwargs)
        context['product'] = self.get_object()
        return context


class CartView(generic.TemplateView):
    template_name: str = "cart/cart.html"

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super(CartView, self).get_context_data(**kwargs)
        context["order"] = get_or_set_order_session(self.request)
        return context


class CartItemActionView(generic.View):
    def get_order_item(self, request, pk):
        order = get_or_set_order_session(request)
        return get_object_or_404(
            OrderItem,
            id=pk,
            order=order,
            order__ordered=False,
        )


class IncreaseQuantityView(CartItemActionView):
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        order_item = self.get_order_item(request, kwargs['pk'])
        if order_item.quantity >= order_item.product.stock:
            messages.warning(request, "The maximum available stock is already in your cart.")
        else:
            order_item.quantity += 1
            order_item.save(update_fields=['quantity', ])
        return redirect("cart:summary")


class DecreaseQuantityView(CartItemActionView):
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        order_item = self.get_order_item(request, kwargs['pk'])
        if order_item.quantity <= 1:
            order_item.delete()
        else:
            order_item.quantity -= 1
            order_item.save(update_fields=['quantity', ])
        return redirect("cart:summary")


class RemoveFromCartView(CartItemActionView):
    def post(self, request, *args, **kwargs) -> HttpResponseRedirect:
        order_item = self.get_order_item(request, kwargs['pk'])
        order_item.delete()
        return redirect("cart:summary")


class CheckoutView(LoginRequiredMixin, generic.FormView):
    template_name: str = 'cart/checkout.html'
    form_class = AddressForm

    def get_success_url(self) -> str:
        return reverse("cart:payment")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            order = get_or_set_order_session(request)
            if not order.items.exists():
                messages.info(request, "Add an item to your cart before checkout.")
                return redirect("cart:summary")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        order = get_or_set_order_session(self.request)
        selected_shipping_address = form.cleaned_data.get(
            'selected_shipping_address'
        )
        selected_billing_address = form.cleaned_data.get(
            'selected_billing_address'
        )
        if selected_shipping_address:
            order.shipping_address = selected_shipping_address
        else:
            address = Address.objects.create(
                address_type=Address.SHIPPING_ADDRESS_TYPE,
                user=self.request.user,
                address_line_1=form.cleaned_data['shipping_address_line_1'],
                address_line_2=form.cleaned_data['shipping_address_line_2'],
                zip_code=form.cleaned_data['shipping_zip_code'],
                city=form.cleaned_data['shipping_city'],
            )
            order.shipping_address = address

        if selected_billing_address:
            order.billing_address = selected_billing_address
        else:
            address = Address.objects.create(
                address_type=Address.BILLING_ADDRESS_TYPE,
                user=self.request.user,
                address_line_1=form.cleaned_data['billing_address_line_1'],
                address_line_2=form.cleaned_data['billing_address_line_2'],
                zip_code=form.cleaned_data['billing_zip_code'],
                city=form.cleaned_data['billing_city'],
            )
            order.billing_address = address

        order.save()
        messages.info(self.request, "You have successfully added your addresses")
        return super(CheckoutView, self).form_valid(form)

    def get_form_kwargs(self) -> Dict[str, Any]:
        kwargs = super(CheckoutView, self).get_form_kwargs()
        kwargs["user_id"] = self.request.user.id
        return kwargs

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super(CheckoutView, self).get_context_data(**kwargs)
        context["order"] = get_or_set_order_session(self.request)
        return context


class PaymentView(LoginRequiredMixin, generic.TemplateView):
    template_name: str = 'cart/payment.html'

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        order = get_or_set_order_session(request)
        if not order.items.exists():
            messages.info(request, "Add an item to your cart before payment.")
            return redirect("cart:summary")
        if not order.billing_address or not order.shipping_address:
            messages.info(request, "Complete checkout before choosing a payment method.")
            return redirect("cart:checkout")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        context = super(PaymentView, self).get_context_data(**kwargs)
        context["PAYPAL_CLIENT_ID"] = settings.PAYPAL_CLIENT_ID
        context["paypal_available"] = bool(
            settings.PAYPAL_CLIENT_ID and settings.PAYPAL_SECRET_KEY
        )
        context["stripe_available"] = bool(
            settings.STRIPE_PUBLIC_KEY and settings.STRIPE_SECRET_KEY
        )
        context['order'] = get_or_set_order_session(self.request)
        context['CALLBACK_URL'] = self.request.build_absolute_uri(
            location=reverse("cart:thank-you")
        )
        return context


class StripePaymentView(LoginRequiredMixin, generic.FormView):
    template_name: str = 'cart/stripe_payment.html'
    form_class = StripePaymentForm

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)
        if not settings.STRIPE_PUBLIC_KEY or not settings.STRIPE_SECRET_KEY:
            messages.error(request, "Stripe payments are not configured.")
            return redirect("cart:payment")

        order = get_or_set_order_session(request)
        if (
            not order.items.exists()
            or not order.billing_address
            or not order.shipping_address
        ):
            messages.info(request, "Complete checkout before choosing a payment method.")
            return redirect("cart:checkout")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        payment_method = form.cleaned_data["selectedCard"]
        if payment_method != "newCard":
            try:
                order = get_or_set_order_session(self.request)
                payment_intent = stripe.PaymentIntent.create(
                    amount=int(order.get_raw_total()),
                    currency='usd',
                    customer=self.request.user.customer.stripe_customer_id,
                    payment_method=payment_method,
                    off_session=True,
                    confirm=True,
                )
                payment_record, _ = StripePayment.objects.get_or_create(
                    order=order,
                )
                payment_record.payment_intent_id = payment_intent["id"]
                payment_record.amount = order.get_total()
                payment_record.save(update_fields=['payment_intent_id', 'amount', ])
            except stripe.error.CardError as e:
                err = e.error
                # Error code will be authentication_required if authentication is needed
                logger.debug("Code is: %s" % err.code)
                stripe.PaymentIntent.retrieve(err.payment_intent['id'])
                messages.warning(self.request, "Code is: %s" % err.code)
        return redirect("/")

    def get_context_data(self, **kwargs):
        user = self.request.user
        if not user.customer.stripe_customer_id:
            stripe_customer = stripe.Customer.create(email=user.email)
            user.customer.stripe_customer_id = stripe_customer["id"]
            user.customer.save(update_fields=['stripe_customer_id'], )

        order = get_or_set_order_session(self.request)

        payment_intent = stripe.PaymentIntent.create(
            amount=int(order.get_raw_total()),
            currency='usd',
            customer=user.customer.stripe_customer_id,
        )

        payment_record, _ = StripePayment.objects.get_or_create(order=order, )
        payment_record.payment_intent_id = payment_intent["id"]
        payment_record.amount = order.get_total()
        payment_record.save(update_fields=['amount', 'payment_intent_id', ])

        cards = stripe.PaymentMethod.list(
            customer=user.customer.stripe_customer_id,
            type="card",
        )
        payment_methods: List[Dict[str, Any]] = [{
            "last4": card["card"]["last4"],
            "brand": card["card"]["brand"],
            "exp_month": card["card"]["exp_month"],
            "exp_year": card["card"]["exp_year"],
            "pm_id": card["id"]
        } for card in cards]
        context = super(StripePaymentView, self).get_context_data(**kwargs)
        context["STRIPE_PUBLIC_KEY"] = settings.STRIPE_PUBLIC_KEY
        context["client_secret"] = payment_intent["client_secret"]
        context["payment_methods"] = payment_methods
        return context


class CreatePayPalOrderView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs) -> JsonResponse:
        order = get_or_set_order_session(request)
        if (
            not order.items.exists()
            or order.ordered
            or not order.billing_address
            or not order.shipping_address
        ):
            return JsonResponse({"error": "This order cannot be paid."}, status=400)
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_SECRET_KEY:
            logger.error("PayPal order creation requested without configured credentials")
            return JsonResponse(
                {"error": "PayPal payments are not configured."},
                status=503,
            )

        try:
            api_base, access_token = _paypal_access_token()
            response = requests.post(
                f"{api_base}/v2/checkout/orders",
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "intent": "CAPTURE",
                    "purchase_units": [{
                        "reference_id": str(order.pk),
                        "custom_id": str(order.pk),
                        "amount": {
                            "currency_code": "USD",
                            "value": order.get_total(),
                        },
                    }],
                },
                timeout=(5, 20),
            )
            response.raise_for_status()
            paypal_order_id = response.json()["id"]
        except (requests.RequestException, KeyError, ValueError):
            logger.exception("PayPal could not create an order")
            return JsonResponse(
                {"error": "PayPal could not start this payment."},
                status=502,
            )
        return JsonResponse({"id": paypal_order_id})


class ConfirmOrderView(LoginRequiredMixin, generic.View):
    def post(self, request, *args, **kwargs) -> JsonResponse:
        order = get_or_set_order_session(request)
        if (
            not order.items.exists()
            or order.ordered
            or not order.billing_address
            or not order.shipping_address
        ):
            return JsonResponse({"error": "This order cannot be paid."}, status=400)
        if not settings.PAYPAL_CLIENT_ID or not settings.PAYPAL_SECRET_KEY:
            logger.error("PayPal payment confirmation requested without configured credentials")
            return JsonResponse(
                {"error": "PayPal payments are not configured."},
                status=503,
            )

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({"error": "Invalid payment confirmation."}, status=400)

        paypal_order_id = body.get("orderID") if isinstance(body, dict) else None
        if not isinstance(paypal_order_id, str) or not paypal_order_id:
            return JsonResponse({"error": "Missing PayPal order ID."}, status=400)

        try:
            api_base, access_token = _paypal_access_token()
            capture_response = requests.post(
                f"{api_base}/v2/checkout/orders/{quote(paypal_order_id, safe='')}/capture",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=(5, 20),
            )
            capture_response.raise_for_status()
            capture = capture_response.json()
        except (
            requests.RequestException,
            KeyError,
            ValueError,
        ):
            logger.exception("PayPal could not verify or capture the order")
            return JsonResponse(
                {"error": "PayPal could not confirm this payment."},
                status=502,
            )

        try:
            captured_payment = capture["purchase_units"][0]["payments"]["captures"][0]
            captured_amount = Decimal(captured_payment["amount"]["value"])
            captured_currency = captured_payment["amount"]["currency_code"]
            captured_order_reference = capture["purchase_units"][0]["reference_id"]
        except (KeyError, IndexError, TypeError, InvalidOperation):
            logger.error("PayPal returned an incomplete capture response")
            return JsonResponse(
                {"error": "PayPal returned an invalid payment confirmation."},
                status=502,
            )

        expected_amount = Decimal(order.get_total())
        if (
            capture.get("status") != "COMPLETED"
            or captured_payment.get("status") != "COMPLETED"
            or captured_amount != expected_amount
            or captured_currency != "USD"
            or captured_order_reference != str(order.pk)
        ):
            logger.warning("PayPal capture did not match the expected order total")
            return JsonResponse(
                {"error": "The payment does not match this order."},
                status=400,
            )

        Payment.objects.create(
            order=order,
            successful=True,
            raw_response=json.dumps(capture),
            amount=float(captured_amount),
            payment_method=Payment.PAYPAL_PAYMENT_METHOD,
        )
        order.ordered = True
        order.ordered_date = timezone.now()
        order.save(update_fields=['ordered', 'ordered_date', ])
        return JsonResponse({"data": "Success"})


class ThankYouView(generic.TemplateView):
    template_name: str = 'cart/thanks.html'


class OrderDetailView(LoginRequiredMixin, generic.DetailView):
    template_name: str = 'order.html'
    context_object_name: str = 'order'

    def get_queryset(self):
        if self.request.user.is_staff:
            return Order.objects.filter(ordered=True)
        return Order.objects.filter(user=self.request.user, ordered=True)


# If you are testing your webhook locally with the Stripe CLI you
# can find the endpoint's secret by running `stripe listen`
# Otherwise, find your endpoint's secret in your webhook settings in the Developer Dashboard

@csrf_exempt
def stripe_webhook_view(request):
    endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
    payload = request.body
    sig_header = request.headers.get('Stripe-Signature')
    if not sig_header or not endpoint_secret:
        return HttpResponse(status=400)

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, endpoint_secret
        )
    except ValueError:
        # Invalid payload
        return HttpResponse(status=400)
    except stripe.SignatureVerificationError:
        # Invalid signature
        return HttpResponse(status=400)

    # Handle the event
    if event.type == 'payment_intent.succeeded':
        payment_intent = event.data.object  # contains a stripe.PaymentIntent
        stripe_payment = StripePayment.objects.filter(
            payment_intent_id=payment_intent["id"],
        ).first()
        if stripe_payment is None:
            logger.error("Stripe webhook references an unknown payment intent")
            return HttpResponse(status=400)
        stripe_payment.successful = True
        stripe_payment.save()
        order = stripe_payment.order
        order.ordered = True
        order.ordered_date = timezone.now()
        order.save(update_fields=['ordered', 'ordered_date'])

    return HttpResponse(status=200)


__all__ = (
    'ProductListView',
    'ProductDetailView',
    'CartView',
    'IncreaseQuantityView',
    'DecreaseQuantityView',
    'RemoveFromCartView',
    'CheckoutView',
    'PaymentView',
    'StripePaymentView',
    'ConfirmOrderView',
    'ThankYouView',
    'OrderDetailView',

    'stripe_webhook_view',
)
