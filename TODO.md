# Paytm Debugging TODO

## Plan Steps:
- [x] Step 1: Install paytmchecksum if missing (`pip install paytmchecksum`)
- [x] Step 2: Add debug prints to api/paytm.py (INIT response, SENT ORDER ID)
- [x] Step 3: Add debug prints to users/orders.py (CALLBACK PARAMS)
- [x] Step 4: Add debug prints to api/paytm_notifications.py (STATUS BODY, RESULT)
- [x] Step 5: Test payment flow locally, check diagnostics on orders page (diagnostics good: prod, checksum loaded)
- [ ] Step 6: Add to Render .env: `PAYTM_CALLBACK_URL=https://www.svdagencies.shop/users/paytm/callback/`
- [ ] Step 7: Deploy (git push heroku main), check Render logs for callback prints
- [ ] Step 8: Review logs, remove prints after fix


