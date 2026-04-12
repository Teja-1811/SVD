# Customer Portal Advance Payment Input Fix - TODO
Status: 🔄 Bug Confirmed (input resets to 0.00 on edit)

## Steps:
- [x] 1. Diagnose: JS `input` event `toLocaleString` → `parseFloat("1,234")=NaN` → Resets field
- [x] 2. Fix `collect_payment.html` JS: Raw input + format on blur ✅ (`input` validates, `blur` formats)
- [x] 3. Test typing ₹1234.56 → Works (server refresh needed)
- [x] 4. Fix "'Customer' object has no attribute 'email'" → `getattr(customer, 'email', None)` in paytm.py ✅
- [x] 5. Complete ✅

**Root Cause:** `input` event reformats → Typing loop failure
