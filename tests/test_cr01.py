"""Verification for Client Change Request CR-01: Express Delivery."""

from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService


class ExpressDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    def test_cr01_example1_regular_notebooks_express(self):
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 2}], fulfillment="express")
        self.assertEqual(quote["subtotal_cents"], 1000)
        self.assertEqual(quote["discount_cents"], 0)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 2200)

    def test_cr01_example2_student_hoodies_express(self):
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}], fulfillment="express")
        self.assertEqual(quote["subtotal_cents"], 8000)
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["delivery_cents"], 1200)
        self.assertEqual(quote["total_cents"], 8400)

    def test_cr01_example3_express_fee_never_waived(self):
        std_quote = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 3}], fulfillment="delivery")
        self.assertEqual(std_quote["delivery_cents"], 0)
        self.assertEqual(std_quote["total_cents"], 12000)

        exp_quote = self.service.quote("regular", [{"product_id": "hoodie", "quantity": 3}], fulfillment="express")
        self.assertEqual(exp_quote["delivery_cents"], 1200)
        self.assertEqual(exp_quote["total_cents"], 13200)

    def test_cr01_placed_order_lifecycle_with_express(self):
        order = self.service.place_order("student", [{"product_id": "hoodie", "quantity": 2}], fulfillment="express")
        self.assertEqual(order["fulfillment"], "express")
        self.assertEqual(order["delivery_cents"], 1200)
        self.assertEqual(order["total_cents"], 8400)

        retrieved = self.service.get_order(order["order_id"])
        self.assertEqual(retrieved["fulfillment"], "express")
        self.assertEqual(retrieved["total_cents"], 8400)

        cancelled = self.service.cancel_order(order["order_id"])
        self.assertEqual(cancelled["fulfillment"], "express")
        self.assertEqual(cancelled["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()