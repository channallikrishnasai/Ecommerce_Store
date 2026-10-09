import json
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from cart.models import (
    Address,
    Category,
    ColourVariation,
    Order,
    OrderItem,
    Product,
    SizeVariation,
)

User = get_user_model()


class StoreAccessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="shopper",
            email="shopper@example.test",
            password="test-password",
        )
        self.category = Category.objects.create(name="Accessories")
        self.colour = ColourVariation.objects.create(name="Blue")
        self.size = SizeVariation.objects.create(name="One size")
        self.product = Product.objects.create(
            title="Canvas bag",
            description="A simple everyday bag.",
            slug="canvas-bag",
            active=True,
            stock=5,
            price=1250,
            image="products/canvas-bag.jpg",
            primary_category=self.category,
        )
        self.product.available_colours.add(self.colour)
        self.product.available_sizes.add(self.size)

    def make_order_item(self, user=None, quantity=1):
        order = Order.objects.create(user=user)
        item = OrderItem.objects.create(
            order=order,
            product=self.product,
            size=self.size,
            colour=self.colour,
            quantity=quantity,
        )
        return order, item

    def set_cart_session(self, order):
        session = self.client.session
        session["order_id"] = order.pk
        session.save()

    def add_order_addresses(self, order, user):
        addresses = []
        for address_type in (
            Address.BILLING_ADDRESS_TYPE,
            Address.SHIPPING_ADDRESS_TYPE,
        ):
            addresses.append(Address.objects.create(
                user=user,
                address_type=address_type,
                address_line_1="10 Main Street",
                address_line_2="Apartment 2",
                city="Example City",
                zip_code="ZX-407",
            ))
        order.billing_address, order.shipping_address = addresses
        order.save(update_fields=["billing_address", "shipping_address"])

    def test_shop_hides_inactive_products(self):
        inactive = Product.objects.create(
            title="Draft bag",
            description="Not published.",
            slug="draft-bag",
            active=False,
            stock=2,
            price=500,
            image="products/draft-bag.jpg",
        )

        response = self.client.get(reverse("cart:product-list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.product.title)
        self.assertNotContains(response, inactive.title)

    def test_inactive_product_detail_is_not_public(self):
        inactive = Product.objects.create(
            title="Draft bag",
            description="Not published.",
            slug="draft-bag",
            active=False,
            stock=2,
            price=500,
            image="products/draft-bag.jpg",
        )

        response = self.client.get(
            reverse("cart:product-detail", kwargs={"slug": inactive.slug})
        )

        self.assertEqual(response.status_code, 404)

    def test_checkout_requires_authentication(self):
        response = self.client.get(reverse("cart:checkout"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("account_login"), response.url)

    def test_order_details_are_private_to_the_order_owner(self):
        other_user = User.objects.create_user(
            username="another-shopper",
            email="another@example.test",
            password="test-password",
        )
        order, _ = self.make_order_item(user=other_user)
        order.ordered = True
        order.save(update_fields=["ordered"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("cart:order-detail", kwargs={"pk": order.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_cart_mutation_rejects_get_requests(self):
        order, item = self.make_order_item()
        self.set_cart_session(order)

        response = self.client.get(
            reverse("cart:increase-quantity", kwargs={"pk": item.pk})
        )

        self.assertEqual(response.status_code, 405)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 1)

    def test_cart_mutation_is_limited_to_session_order(self):
        first_order, first_item = self.make_order_item()
        _, other_item = self.make_order_item()
        self.set_cart_session(first_order)

        response = self.client.post(
            reverse("cart:increase-quantity", kwargs={"pk": other_item.pk})
        )

        self.assertEqual(response.status_code, 404)
        first_item.refresh_from_db()
        other_item.refresh_from_db()
        self.assertEqual(first_item.quantity, 1)
        self.assertEqual(other_item.quantity, 1)

    @override_settings(
        PAYPAL_ENV="sandbox",
        PAYPAL_CLIENT_ID="test-client",
        PAYPAL_SECRET_KEY="test-secret",
    )
    @patch("cart.views.requests.post")
    def test_paypal_order_amount_is_created_server_side(self, post):
        order, _ = self.make_order_item(user=self.user)
        self.add_order_addresses(order, self.user)
        self.client.force_login(self.user)
        self.set_cart_session(order)
        token_response = Mock()
        token_response.json.return_value = {"access_token": "test-access-token"}
        creation_response = Mock()
        creation_response.json.return_value = {"id": "PAYPAL-ORDER"}
        post.side_effect = [token_response, creation_response]

        response = self.client.post(
            reverse("cart:paypal-create-order"),
            data=json.dumps({"amount": "0.01"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"id": "PAYPAL-ORDER"})
        created_order = post.call_args_list[1].kwargs["json"]
        self.assertEqual(
            created_order["purchase_units"][0]["amount"],
            {"currency_code": "USD", "value": "12.50"},
        )

    @override_settings(
        PAYPAL_ENV="sandbox",
        PAYPAL_CLIENT_ID="test-client",
        PAYPAL_SECRET_KEY="test-secret",
    )
    @patch("cart.views.requests.post")
    def test_paypal_confirmation_captures_and_verifies_payment(self, post):
        order, _ = self.make_order_item(user=self.user)
        self.add_order_addresses(order, self.user)
        self.client.force_login(self.user)
        self.set_cart_session(order)
        token_response = Mock()
        token_response.json.return_value = {"access_token": "test-access-token"}
        capture_response = Mock()
        capture_response.json.return_value = {
            "id": "PAYPAL-ORDER",
            "status": "COMPLETED",
            "purchase_units": [{
                "reference_id": str(order.pk),
                "payments": {
                    "captures": [{
                        "status": "COMPLETED",
                        "amount": {"currency_code": "USD", "value": "12.50"},
                    }],
                },
            }],
        }
        post.side_effect = [token_response, capture_response]

        response = self.client.post(
            reverse("cart:confirm-order"),
            data=json.dumps({"orderID": "PAYPAL-ORDER"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertTrue(order.ordered)
        self.assertEqual(order.payments.get().amount, 12.5)
