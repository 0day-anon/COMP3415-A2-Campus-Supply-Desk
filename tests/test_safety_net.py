"""Comprehensive testing covering normal, boundary, invalid, and preserved behaviors."""

from pathlib import Path
import tempfile
import unittest

from supplydesk.service import OrderService


class TestingSafetyNet(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "state.json"
        self.service = OrderService(self.path)

    #Normal Behavior Tests
    def test_normal_quote_and_placement_agreement(self):
        items = [{"product_id": "notebook", "quantity": 2}, {"product_id": "mug", "quantity": 1}]
        quote = self.service.quote("regular", items, fulfillment="delivery")
        order = self.service.place_order("regular", items, fulfillment="delivery")
        
        self.assertEqual(quote["subtotal_cents"], 2500)
        self.assertEqual(quote["delivery_cents"], 600)
        self.assertEqual(quote["total_cents"], 3100)
        self.assertEqual(order["subtotal_cents"], quote["subtotal_cents"])
        self.assertEqual(order["total_cents"], quote["total_cents"])
        self.assertEqual(order["status"], "placed")

    def test_normal_student_discount_application(self):
        quote = self.service.quote("student", [{"product_id": "hoodie", "quantity": 2}])
        self.assertEqual(quote["subtotal_cents"], 8000)
        self.assertEqual(quote["discount_cents"], 800)
        self.assertEqual(quote["total_cents"], 7200)

    #Boundary Behavior Tests
    def test_boundary_student_discount_threshold_exact(self):
        quote = self.service.quote("student", [{"product_id": "notebook", "quantity": 10}])
        self.assertEqual(quote["subtotal_cents"], 5000)
        self.assertEqual(quote["discount_cents"], 500)
        self.assertEqual(quote["total_cents"], 4500)

    def test_boundary_free_delivery_threshold_exact(self):
        quote = self.service.quote("regular", [{"product_id": "notebook", "quantity": 20}], fulfillment="delivery")
        self.assertEqual(quote["subtotal_cents"], 10000)
        self.assertEqual(quote["delivery_cents"], 0)
        self.assertEqual(quote["total_cents"], 10000)

    def test_boundary_quantity_limits(self):
        quote_min = self.service.quote("regular", [{"product_id": "notebook", "quantity": 1}])
        self.assertEqual(quote_min["items"][0]["quantity"], 1)

    #Invalid or Exceptional Behavior Tests
    def test_invalid_insufficient_stock_raises_value_error(self):
        with self.assertRaises(ValueError):
            self.service.place_order("regular", [{"product_id": "hoodie", "quantity": 6}])
        self.assertEqual(len(self.service.list_orders()), 0)

    def test_invalid_quantity_types_and_ranges(self):
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": 0}])
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": 100}])
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": True}])
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": "2"}])

    def test_invalid_customer_and_fulfillment_types(self):
        with self.assertRaises(ValueError):
            self.service.quote("vip", [{"product_id": "notebook", "quantity": 1}])
        with self.assertRaises(ValueError):
            self.service.quote("regular", [{"product_id": "notebook", "quantity": 1}], fulfillment="drone")

    #Behavior Important to Preserve
    def test_preserve_repeated_cancellation(self):
        order = self.service.place_order("regular", [{"product_id": "mug", "quantity": 2}])
        stock_after_place = [p["stock"] 
            for p in self.service.catalog() 
                if p["product_id"] == "mug"][0]
        
        self.service.cancel_order(order["order_id"])
        stock_after_first_cancel = [p["stock"] 
            for p in self.service.catalog() 
                if p["product_id"] == "mug"][0]
        self.assertEqual(stock_after_first_cancel, stock_after_place + 2)

        self.service.cancel_order(order["order_id"])
        stock_after_second_cancel = [p["stock"] 
            for p in self.service.catalog() 
                if p["product_id"] == "mug"][0]
        self.assertEqual(stock_after_second_cancel, stock_after_first_cancel)

    def test_preserve_combined_stock_across_duplicate_lines(self):
        items = [{"product_id": "notebook", "quantity": 12}, {"product_id": "notebook", "quantity": 12}]
        with self.assertRaises(ValueError):
            self.service.place_order("regular", items)


if __name__ == "__main__":
    unittest.main()