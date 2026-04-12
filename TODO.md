# Paytm JS Checkout Redevelopment ✅ COMPLETE

## Changes Applied:
- ✅ customer_portal/views.py: Added `_paytm_diagnostics`, refactored `start_collect_payment` to JSON API (initiate_paytm_transaction + full response)
- ✅ templates/customer_portal/collect_payment.html: Modern UI/JS matching orders.html (modal, diagnostics, dynamic merchant JS, error handling)

## Test Instructions:
1. `python manage.py runserver`
2. Login as customer → /customer/collect-payment/
3. Verify diagnostics → Enter amount → Modal → "Pay with Paytm" → Staging checkout
4. Test callback (use Paytm staging sandbox)

## Prod Deploy:
- Set `PAYTM_ENV=production` + merchant keys in env
- Callback verifies checksum → updates CustomerPayment/Customer.due

Task complete. Matches official Paytm JS Checkout docs.
