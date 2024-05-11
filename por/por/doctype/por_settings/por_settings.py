# Copyright (c) 2024, IT get it! and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PORSettings(Document):
	pass
@frappe.whitelist()
def calculate_daily_divisor(doc, method):
	if doc.overage_billing_interval:
		doc.daily_divisor = 24 / doc.overage_billing_interval