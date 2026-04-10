# Paytm Debugging TODO

## Plan Steps:
- [x] Step 1: Install paytmchecksum if missing (`pip install paytmchecksum`)
- [x] Step 2: Add debug prints to api/paytm.py (INIT response, SENT ORDER ID)
- [x] Step 3: Add debug prints to users/orders.py (CALLBACK PARAMS)
- [x] Step 4: Add debug prints to api/paytm_notifications.py (STATUS BODY, RESULT)
- [ ] Step 5: Test payment flow locally, check diagnostics on orders page
- [ ] Step 6: Set PAYTM_CALLBACK_URL in .env for Render (https://svd-dqw3.onrender.com/users/paytm/callback/)
- [ ] Step 7: Deploy to Render, test end-to-end
- [ ] Step 8: Review logs, remove prints after fix


