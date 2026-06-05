import sys
import os
import unittest

# Ensure the backend directory is in the import path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Now we can import guardrails from app
# But wait, guardrails is inside backend/app/guardrails.py. Since sys.path has backend/,
# we import from app.guardrails
from app.guardrails import (
    is_pii,
    is_advisory,
    normalize_query,
    get_pii_response,
    get_advisory_response
)

class TestGuardrails(unittest.TestCase):

    # ----------------------------------------------------
    # PII Scanner Tests
    # ----------------------------------------------------

    def test_email_pii(self):
        self.assertTrue(is_pii("my email is test@example.com"))
        self.assertTrue(is_pii("Contact: contact.us@groww.co.in"))
        self.assertFalse(is_pii("No email here at all"))

    def test_phone_pii_standard(self):
        self.assertTrue(is_pii("My phone number is 9876543210"))
        self.assertTrue(is_pii("Call me on +919876543210 please"))
        self.assertTrue(is_pii("Call me on +91 8765432109 please"))
        self.assertTrue(is_pii("Call 07654321098"))

    def test_phone_pii_obfuscated(self):
        # Spaced digits
        self.assertTrue(is_pii("my phone number is 9 8 7 6 5 4 3 2 1 0"))
        self.assertTrue(is_pii("number: 8-7-6-5-4-3-2-1-0-9"))
        self.assertTrue(is_pii("Call 7.6.5.4.3.2.1.0.9.8"))

    def test_phone_pii_word_based(self):
        # Word digits
        self.assertTrue(is_pii("My phone is nine eight seven six five four three two one zero"))
        self.assertTrue(is_pii("phone: Nine Eight Seven Six Five Four Three Two One Zero"))
        self.assertTrue(is_pii("call me at +91 nine eight seven six five four three two one zero"))

    def test_aadhaar_pii_standard(self):
        self.assertTrue(is_pii("Aadhaar: 200030004000"))
        self.assertTrue(is_pii("Aadhaar 9999 8888 7777"))
        self.assertTrue(is_pii("Here is card 4567-8901-2345"))

    def test_aadhaar_pii_obfuscated(self):
        # Aadhaar obfuscation with spaces/hyphens
        self.assertTrue(is_pii("Aadhaar 2-0-0-0-3-0-0-0-4-0-0-0"))
        self.assertTrue(is_pii("aadhaar: 9 9 9 9 8 8 8 8 7 7 7 7"))

    def test_pan_pii_standard(self):
        self.assertTrue(is_pii("PAN: ABCDE1234F"))
        self.assertTrue(is_pii("my PAN is abcde1234f"))
        self.assertTrue(is_pii("My PAN is ABCDE-1234-F"))

    def test_pan_pii_obfuscated(self):
        self.assertTrue(is_pii("PAN: A-B-C-D-E-1-2-3-4-F"))
        self.assertTrue(is_pii("PAN: A B C D E 1 2 3 4 F"))

    def test_pan_pii_partial(self):
        # Partial PAN card (5 letters + 4 digits)
        self.assertTrue(is_pii("Here is my PAN: ABCDE1234"))
        self.assertTrue(is_pii("partial: abcde-1234"))
        self.assertTrue(is_pii("partial PAN: A B C D E 1 2 3 4"))

    def test_pii_false_positives(self):
        # Legitimate queries shouldn't trigger PII check
        self.assertFalse(is_pii("Does Axis Bluechip Fund have a Scheme Code like 120456?"))
        self.assertFalse(is_pii("Is the minimum SIP amount 500 rupees?"))
        self.assertFalse(is_pii("What is the exit load if I withdraw in 6 months?"))
        self.assertFalse(is_pii("Axis code 123456"))
        self.assertFalse(is_pii("Fund details 9876"))
        # Verify email-like text but without valid domain suffix is not blocked
        self.assertFalse(is_pii("test@example"))

    # ----------------------------------------------------
    # Advisory Keyword Scanner Tests
    # ----------------------------------------------------

    def test_advisory_queries(self):
        # Mutual fund advisory
        self.assertTrue(is_advisory("should I invest in Axis Bluechip Fund?"))
        self.assertTrue(is_advisory("Which is a better returns comparison: Axis or SBI?"))
        self.assertTrue(is_advisory("buy fund Parag Parikh Flexi Cap"))
        self.assertTrue(is_advisory("recommend small cap mutual funds"))
        
        # Stock advisory
        self.assertTrue(is_advisory("should I buy AU bank shares?"))
        self.assertTrue(is_advisory("what is the price prediction of Glenmark?"))
        self.assertTrue(is_advisory("is Federal better than Indian bank?"))
        self.assertTrue(is_advisory("What is the market direction for Indian Bank?"))
        
        # Speculative slang
        self.assertTrue(is_advisory("Is Glenmark going to the moon?"))
        self.assertTrue(is_advisory("Is AU Small Finance Bank a multibagger?"))
        self.assertTrue(is_advisory("Will the stock market crash?"))
        self.assertTrue(is_advisory("Are promoters dumping shares of Max Financial?"))

    def test_factual_non_advisory_queries(self):
        # Clean queries should return False
        self.assertFalse(is_advisory("What is the exit load of Axis Bluechip Fund?"))
        self.assertFalse(is_advisory("Who is the fund manager for Axis Bluechip Fund?"))
        self.assertFalse(is_advisory("What is the P/E ratio of The Federal Bank Ltd?"))
        self.assertFalse(is_advisory("Show me the management team of Glenmark Pharmaceuticals Ltd"))
        self.assertFalse(is_advisory("What is the dividend yield of Max Financial Services Ltd?"))

    def test_mixed_intent_queries(self):
        # If there is mixed intent, the advisory detector should still catch it
        self.assertTrue(is_advisory("What is the exit load of Axis Bluechip Fund, and do you think I should buy it?"))
        self.assertTrue(is_advisory("Tell me the PE ratio of AU Bank and price forecast for tomorrow."))

    # ----------------------------------------------------
    # Response Templates Verification
    # ----------------------------------------------------

    def test_response_templates(self):
        pii_resp = get_pii_response()
        self.assertIn("For your security, please do not share personal information", pii_resp)
        self.assertIn("PAN, Aadhaar, phone numbers", pii_resp)
        
        advisory_resp = get_advisory_response()
        self.assertIn("I am a facts-only assistant designed to provide official stock and fund details", advisory_resp)
        self.assertIn("https://www.amfiindia.com", advisory_resp)
        self.assertIn("groww.in/academy", advisory_resp)

if __name__ == "__main__":
    unittest.main()
