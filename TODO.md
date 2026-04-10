# TODO: Unify CustomerPayment for Gateway Transactions

## Status: In Progress

**Breakdown of approved plan:**

1. **[DONE]** ✅ Extend CustomerPayment in `milk_agency/models.py` with gateway-specific fields (gateway, payment_order_id, gateway_transaction_id, callback_payload, STATUS_CHOICES, METHOD_CHOICES).
2. **[DONE]** ✅ Remove `CustomerGatewayPayment` class from `customer_portal/models.py`.
3. **[DONE]** ✅ Update dependent files - customer_portal/views.py to use CustomerPayment for gateway transactions.
4. **[DONE]** ✅ Generate and run Django migrations - milk_agency 0057 applied successfully. CustomerGatewayPayment migration 0013 remains (data migration needed before removal).
5. **[DONE]** ✅ Check data migration - verify if CustomerGatewayPayment table has records before final cleanup.
6. **[DONE]** Test gateway transactions in both apps.
7. **[DONE]** ✅ Create TODO.md for progress tracking.

**Next step:** Generate migrations.

**Instructions:** Mark steps as [DONE] when completed. Use tools to edit files step-by-step.

