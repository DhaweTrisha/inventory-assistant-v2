"""A hand-written description of the database for the LLM.

The tables are not normalised and some columns are messy, so the notes below
tell the model how to interpret them instead of letting it guess.
"""

SCHEMA_NOTES = """
Database: PostgreSQL, schema public. All ids are text. Amounts are in INR. Today is CURRENT_DATE.

INVENTORY TABLES
- inv_items(id, item_code, name, category_id -> inv_categories.id, sub_category_id -> inv_sub_categories.id,
  sub_category_2_id -> inv_sub_categories_2.id, status 'active'/'inactive', unit (pcs/kg/mtr/set/pair/roll), hsn_code, is_spare)
- inv_categories(id, name): Bought Out, Raw Material, Finished Goods, Sub-Assembly
- inv_sub_categories(id, name, category_id -> inv_categories.id)
- inv_sub_categories_2(id, name, sub_category_id -> inv_sub_categories.id)
- inv_locations(id, name, is_active): stores / warehouses named 132-1, 132-2, 132-3, 103-1, C-84, Unassigned
- inv_current_stock(id, item_id -> inv_items.id, location_id -> inv_locations.id, quantity, min_stock_level,
  max_stock_level, last_transaction_at): stock on hand right now, one row per item per location.
- inv_transactions(id, item_id -> inv_items.id, location_id -> inv_locations.id, transaction_type, quantity,
  reference_type, reference_id, transfer_location_id, unit_cost, currency, issued_to_id -> inv_issued_to_targets.id,
  created_by, created_at): every stock movement. created_at is the movement date. Data starts late April 2026.
    * transaction_type is one of: inbound, outbound, transfer_in, transfer_out
    * quantity is POSITIVE for inbound/transfer_in and NEGATIVE for outbound/transfer_out.
      Use ABS(quantity) when you want movement volumes, SUM(quantity) when you want net change.
    * reference_type is one of: purchase_order, unexpected_receipt, warehouse_issue, transfer
    * unit_cost is only filled for purchase-order receipts, so it cannot value all stock.
- inv_issued_to_targets(id, name): teams that stock is issued to, e.g. 'D132 Shop Floor', 'Dispatch team', 'C84 FM assembly'
- inv_field_definitions: config for custom fields, not useful for questions

PROCUREMENT TABLES
- proc_vendors(id, name, code, city, payment_terms, is_active)
- proc_purchase_orders(id, po_number, vendor_id -> proc_vendors.id, status, placed_on DATE, currency, subtotal,
  tax_amount, total_amount, payment_terms, delivery_location_id -> inv_locations.id, expected_delivery_date JSON,
  expected_dispatch_date JSON, created_by, created_at). Data covers August 2026.
    * status is one of: placed (nothing received yet), partial (some lines received), received (complete).
      "Open" POs means status IN ('placed', 'partial').
    * expected_delivery_date is a JSON array of date strings like ["2026-08-13"].
      Use (expected_delivery_date->>0)::date to get the first expected date.
- proc_po_lines(id, po_id -> proc_purchase_orders.id, inv_item_id -> inv_items.id, quantity_ordered, quantity_received,
  unit, unit_price, tax_percentage, line_subtotal, line_tax, line_total, is_regularised, expected_delivery_date JSON)
- proc_po_receipts(id, po_line_id -> proc_po_lines.id, quantity, location_id -> inv_locations.id,
  inv_transaction_id -> inv_transactions.id, received_by, received_at): goods received against a PO line.
- proc_po_payment_tranches(id, po_id -> proc_purchase_orders.id, sequence, stage, percentage, amount, is_advance,
  cleared_at, cleared_by): payment milestones per PO. cleared_at IS NULL means not yet paid.
    * Unpaid / outstanding amount = all tranches with cleared_at IS NULL. Do NOT filter by PO status here:
      a fully received PO can still have unpaid tranches.
    * amount is usually NULL, so compute the due amount as percentage / 100.0 * proc_purchase_orders.total_amount.
    * stage is free text with inconsistent spelling ('10 Days PDC Against Dispatch', '30 Days Credit', 'Advance'...).
      Use ILIKE when filtering on it.
- proc_po_line_regularisations(id, po_id, po_line_id, ordered_qty, received_qty_before, regularised_qty,
  received_qty_after, qty_variance, unit_price, actual_amount, expected_amount, amount_variance, regularised_at,
  reviewed_at): cases where the received quantity differed from the ordered quantity.
- proc_unexpected_receipts(id, inv_item_id -> inv_items.id, quantity, location_id -> inv_locations.id,
  inv_transaction_id, received_at, received_by, resolved_po_id -> proc_purchase_orders.id, resolved_at,
  header_id -> proc_unexpected_receipt_headers.id): goods that arrived without a PO.
  resolved_po_id IS NULL means still not matched to a PO.
- proc_unexpected_receipt_headers(id, vendor_name, received_at, received_by, notes)
- po_templates, po_template_lines, user_alert_emails: empty tables, ignore them.

NOTES
- created_by / received_by hold user ids that cannot be turned into names.
- For "last N months" use created_at >= date_trunc('month', CURRENT_DATE) - interval 'N months'.
"""
