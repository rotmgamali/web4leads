
import sys
from unittest.mock import MagicMock

# Mock logger_util BEFORE importing email_generator
sys.modules['logger_util'] = MagicMock()
from email_generator import EmailGenerator

def test_prompt_construction():
    print("Testing Prompt Logic (Internal)...")
    
    # Mock dependencies
    generator = EmailGenerator(client=MagicMock())
    
    # Mock template file load
    generator._load_template_file = MagicMock(return_value="Hi {{first_name}},\n\nI noticed you are doing great things at {{school_name}}.")
    
    # Test Case 1: Valid Name
    lead_valid = {
        "first_name": "Andrew",
        "role": "Principal", 
        "school_name": "Ivy Academy",
        "city": "Boston",
        "state": "MA"
    }
    
    # Mock sanitize to return Andrew
    generator._sanitize_name = MagicMock(return_value="Andrew")
    
    sys_prompt, user_prompt, envelope = generator._prepare_school_prompts(
        template_content="Hi {{first_name}},\n\nTest body.",
        lead_data=lead_valid,
        website_content="Specific research about robotics.",
        sequence_number=1,
        sender_email="mark@test.com"
    )
    
    print("\n--- TEST 1: Valid Name (Mark) ---")
    print(f"[SYSTEM]:\n{sys_prompt}")
    print(f"\n[USER]:\n{user_prompt}")
    
    if "Hi Andrew," not in user_prompt:
        print("✅ SUCCESS: Greeting STRIPPED from User Prompt")
    else:
        print("❌ FAIL: Greeting still in prompt")

    if "Hi {{first_name}}" in user_prompt:
         print("❌ FAIL: Placeholder still exists!")

    # Test Case 2: No Name (Time based)
    lead_empty = {
        "first_name": "",
        "role": "Admin",
        "school_name": "Generic School"
    }
    generator._sanitize_name = MagicMock(return_value="")
    
    sys_prompt_2, user_prompt_2, _ = generator._prepare_school_prompts(
        template_content="Hi {{first_name}},\n\nTest body.",
        lead_data=lead_empty,
        website_content="",
        sequence_number=1,
        sender_email="andrew@test.com"
    )
    
    print("\n--- TEST 2: Empty Name (Time Fallback) ---")
    
    if "Hi {{first_name}}" in user_prompt_2:
        print("❌ FAIL: Placeholder still exists in fallback!")
    elif "Good " in user_prompt_2:
        print("✅ SUCCESS: Swapped to time-based greeting.")

    # Test Case 3: Religious Title + Town + Scrape
    # RESET MOCK (Crucial fix)
    generator._sanitize_name = MagicMock(return_value="Andrew")
    
    lead_pastor = {
        "first_name": "Andrew",
        "role": "Senior Pastor",
        "school_name": "Faith Academy",
        "city": "Daytona Beach",
        "state": "FL",
        "subtypes": "Private, Christian",
        "description": "A great school."
    }
    
    sys_prompt_3, user_prompt_3, envelope_3 = generator._prepare_school_prompts(
        template_content="Hi {{first_name}},\n\nI see you are busy...",
        lead_data=lead_pastor,
        website_content="We have a new STEM wing opening next fall.",
        sequence_number=1,
        sender_email="mark@test.com"
    )
    
    print("\n--- TEST 3: Custom Vars (Pastor + City + Scrape) ---")
    if "Hi Pastor Andrew," in envelope_3['greeting']:
        print("✅ SUCCESS: 'Pastor' added to Envelope greeting.")
    else:
        print(f"❌ FAIL: Envelope Greeting is '{envelope_3['greeting']}'")
        
    if "Daytona Beach, FL" in user_prompt_3:
         print("✅ SUCCESS: City/State present in VERIFIED DATA.")
         
    if "STEM wing" in user_prompt_3:
         print("✅ SUCCESS: Scraped content present in RESEARCH HIGHLIGHTS.")

    # Test Case 4: Regex Spaces {{ school_name }}
    sys_prompt_4, user_prompt_4, envelope_4 = generator._prepare_school_prompts(
        template_content="Hi {{ first_name }}, how is {{ school_name }}?",
        lead_data={"first_name": "Sarah", "school_name": "Spaced Academy", "role": "Dean", "city": "TestCity"},
        website_content="...",
        sequence_number=1,
        sender_email="mark@test.com"
    )
    print("\n--- TEST 4: Regex Spaces & Envelope ---")
    if "Spaced Academy" in user_prompt_4:
        print("✅ SUCCESS: {{ school_name }} replaced via Regex.")
    else:
        print(f"❌ FAIL: {{ school_name }} NOT replaced. Content: {user_prompt_4}")
        
    # ENVELOPE CHECKS
    if "Hi Sarah," not in user_prompt_4:
        print("✅ SUCCESS: Greeting STRIPPED from User Prompt (AI won't see it).")
    else:
        print("❌ FAIL: Greeting still leaked into AI prompt.")
        
    if envelope_4['greeting'] == "Hi Sarah,":
        print("✅ SUCCESS: Envelope preserved greeting 'Hi Sarah,'.")
        
    if "Best,\nMark Greenstein" in envelope_4['sign_off']:
        print("✅ SUCCESS: Envelope correct sign-off.")

    # Test Case 5: Public vs Private Context
    sys_prompt_5, user_prompt_5, _ = generator._prepare_school_prompts(
        template_content="Hi {{first_name}}, public test.",
        lead_data={"school_type": "Public", "role": "Principal", "school_name": "Public High"},
        website_content="...",
        sequence_number=1,
        sender_email="mark@test.com"
    )
    print("\n--- TEST 5: Public School Context ---")
    if "IF PUBLIC:" in sys_prompt_5:
        print("✅ SUCCESS: System Prompt includes PUBLIC context.")
    else:
        print(f"❌ FAIL: Context missing in System Prompt: {sys_prompt_5}")

if __name__ == "__main__":
    test_prompt_construction()
