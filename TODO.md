# SVD Paytm Callback URL Fix - TODO
Status: ✅ Plan Approved

## Steps to Complete:
- [x] 1. Create TODO.md with approved plan steps
- [x] 2. Read milk_agency/paytm.py contents (already done via previous tools)
- [x] 3. Edit milk_agency/paytm.py: Fix reverse() namespace in **build_paytm_callback_url** ✅ (`milk_agency:` added)
- [x] 4. Verify edit success (read back, namespace fixed, minor indentation normalized)
- [ ] 5. Test locally: Visit /customer/collect-payment/ and check diagnostics
- [ ] 6. Complete task with attempt_completion

## Progress Notes:
- Root cause: Missing `milk_agency:` namespace in reverse('users_paytm_callback')
- URL exists correctly in milk_agency/urls.py with proper namespace include in SVD/urls.py

