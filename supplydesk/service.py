"""Operations used by the command-line order desk."""

from supplydesk.storage import JsonStore

STUDENT_DISCOUNT_PERCENT = 10
STUDENT_DISCOUNT_THRESHOLD_CENTS = 5000
FREE_DELIVERY_THRESHOLD_CENTS = 10000
STANDARD_DELIVERY_FEE_CENTS = 600
EXPRESS_DELIVERY_FEE_CENTS = 1200

QUANTITY_MIN = 1
QUANTITY_MAX = 99
ALLOWED_CUSTOMER_TYPES = ("regular", "student")
ALLOWED_FULFILLMENTS = ("pickup", "delivery", "express")


class OrderService:
    def __init__(self, state_path=".supplydesk/state.json"):
        self.store = JsonStore(state_path)

    def catalog(self):
        return self.store.load()["catalog"]

    def _evaluate_request(self, state, customer_type, items, fulfillment):
        """Unified validation, inventory verification, and pricing calculation engine."""
        if customer_type not in ALLOWED_CUSTOMER_TYPES:
            raise ValueError("Customer type must be regular or student.")
        if fulfillment not in ALLOWED_FULFILLMENTS:
            raise ValueError(f"Fulfillment must be one of {ALLOWED_FULFILLMENTS}.")
        if not isinstance(items, list) or not items:
            raise ValueError("An order must contain at least one item.")

        #indexed lookup for catalog items
        catalog_map = {product["product_id"]: product for product in state["catalog"]}

        #Cumulative quantity validation to prevent duplicate-line inventory overbooking
        requested_totals = {}
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("Each item must contain a product_id and quantity.")
            pid = item.get("product_id")
            qty = item.get("quantity")
            if type(qty) is not int or qty < QUANTITY_MIN or qty > QUANTITY_MAX:
                raise ValueError(f"Quantity must be an integer from {QUANTITY_MIN} to {QUANTITY_MAX}.")
            requested_totals[pid] = requested_totals.get(pid, 0) + qty

        for pid, total_qty in requested_totals.items():
            product = catalog_map.get(pid)
            if product is None:
                raise ValueError("Unknown product.")
            if total_qty > product["stock"]:
                raise ValueError(f"Not enough stock for {product['product_id']}.")

        #Snapshot line items and calculate subtotal
        lines = []
        subtotal = 0
        for item in items:
            product = catalog_map[item["product_id"]]
            quantity = item["quantity"]
            line_total = product["unit_price_cents"] * quantity
            subtotal += line_total
            lines.append({
                "product_id": product["product_id"],
                "name": product["name"],
                "unit_price_cents": product["unit_price_cents"],
                "quantity": quantity,
                "line_total_cents": line_total,
            })

        #Calculate student discount (at least 5,000 cents merchandise)
        discount = 0
        if customer_type == "student" and subtotal >= STUDENT_DISCOUNT_THRESHOLD_CENTS:
            discount = (subtotal * STUDENT_DISCOUNT_PERCENT + 50) // 100

        #Calculate fulfillment charge
        delivery = 0
        if fulfillment == "delivery":
            if subtotal - discount < FREE_DELIVERY_THRESHOLD_CENTS:
                delivery = STANDARD_DELIVERY_FEE_CENTS
        elif fulfillment == "express":
            delivery = EXPRESS_DELIVERY_FEE_CENTS

        return {
            "customer_type": customer_type,
            "fulfillment": fulfillment,
            "items": lines,
            "subtotal_cents": subtotal,
            "discount_cents": discount,
            "delivery_cents": delivery,
            "total_cents": subtotal - discount + delivery,
        }

    def quote(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        return self._evaluate_request(state, customer_type, items, fulfillment)

    def place_order(self, customer_type, items, fulfillment="pickup"):
        state = self.store.load()
        pricing = self._evaluate_request(state, customer_type, items, fulfillment)

        order = {
            "order_id": "ORD-" + str(state["next_order_number"]).zfill(4),
            "status": "placed",
            **pricing,
        }

        #Deduct ordered inventory
        catalog_map = {product["product_id"]: product for product in state["catalog"]}
        for line in pricing["items"]:
            catalog_map[line["product_id"]]["stock"] -= line["quantity"]

        state["next_order_number"] += 1
        state["orders"].append(order)
        self.store.save(state)
        return order

    def list_orders(self):
        return self.store.load()["orders"]

    def get_order(self, order_id):
        state = self.store.load()
        for order in state["orders"]:
            if order["order_id"] == order_id:
                return order
        raise ValueError("Unknown order: " + order_id)

    def cancel_order(self, order_id):
        state = self.store.load()
        order = None
        for candidate in state["orders"]:
            if candidate["order_id"] == order_id:
                order = candidate
                break
        if order is None:
            raise ValueError("Unknown order: " + order_id)

        #prevent restocking already cancelled orders
        if order.get("status") == "cancelled":
            return order

        catalog_map = {product["product_id"]: product for product in state["catalog"]}
        for line in order["items"]:
            if line["product_id"] in catalog_map:
                catalog_map[line["product_id"]]["stock"] += line["quantity"]

        order["status"] = "cancelled"
        self.store.save(state)
        return order