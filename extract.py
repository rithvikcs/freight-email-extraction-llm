"""Main extraction script - processes emails using Groq API and generates output.json."""

import json
import os
import sys
import time
from pathlib import Path
import traceback
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from groq import Groq
from pydantic import ValidationError

from prompts import SYSTEM_PROMPT, get_extraction_prompt
from schemas import ShipmentExtraction

# Load environment variables
load_dotenv()

# Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"  # Updated from decommissioned model
TEMPERATURE = 0  # Required for reproducibility
MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds

# Paths (relative to parent directory)
PARENT_DIR = Path(__file__).parent.parent
EMAILS_INPUT_FILE = PARENT_DIR / "emails_input.json"
print("email path", EMAILS_INPUT_FILE)
PORT_CODES_FILE = PARENT_DIR / "port_codes_reference.json"
print("port codes", PORT_CODES_FILE)
OUTPUT_FILE = Path(__file__).parent / "output.json"

# Global rate limit tracker
rate_limit_hit = False


def load_emails() -> List[Dict[str, Any]]:
    """Load sample emails from emails_input.json."""
    if not EMAILS_INPUT_FILE.exists():
        raise FileNotFoundError(f"emails_input.json not found at {EMAILS_INPUT_FILE}")
    with open(EMAILS_INPUT_FILE, "r") as f:
        return json.load(f)


def load_port_reference() -> Dict[str, str]:
    """Returns both code->name AND name->code mappings."""
    with open(PORT_CODES_FILE, "r") as f:
        ports = json.load(f)
    
    code_to_names = {}  # code → list of all valid names
    name_to_code = {}   # name (lowercase) → code
    
    for port in ports:
        code = port["code"]
        name = port["name"]
        if code not in code_to_names:
            code_to_names[code] = []
        code_to_names[code].append(name)
        name_to_code[name.lower()] = code
    
    return code_to_names, name_to_code


def safe_parse_json(response_text: str) -> Optional[Dict[str, Any]]:
    """Safely extract and parse JSON from LLM response, fixing common issues."""
    import re
    try:
        # Remove markdown code fences
        response_text = re.sub(r"```(?:json)?", "", response_text, flags=re.IGNORECASE).strip()

        response_text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", response_text)
        response_text = response_text.replace("\r\n", "\n").replace("\r", "\n")

        # Find the first JSON object in text
        start = response_text.find("{")
        end = response_text.rfind("}")

        if start == -1 or end == -1 or end < start:
            print("\n❌ Invalid JSON boundaries")
            print("RAW RESPONSE:\n", response_text)
            return None

        json_str = response_text[start:end+1]

        # Remove trailing commas before closing braces/brackets
        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

        # Remove any non-printable/control characters
        # json_str = re.sub(r"[\x00-\x1f\x7f]", "", json_str)

        return json.loads(json_str)

    except Exception as e:
        print("\n❌ JSON parsing failed:", e)
        print("RAW RESPONSE:\n", response_text)
        return None


def extract_with_groq(
    email_id: str, subject: str, body: str, port_reference: Dict[str, str], prompt_version: str = "v2"
) -> Optional[Dict[str, Any]]:
    """Call Groq API to extract shipment data from email."""
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY not set in .env file. Please add your API key."
        )

    client = Groq(api_key=GROQ_API_KEY)
    prompt = get_extraction_prompt(
        version=prompt_version, 
        subject=subject, 
        body=body,
        port_reference=port_reference
    )
    # prompt = prompt + f'\nInclude this field: "id": "{email_id}"'

    # Replace email ID placeholder
    # if "{id}" in prompt or "EMAIL_ID" in prompt:
    #     prompt = prompt.replace("EMAIL_ID", email_id)

    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=TEMPERATURE,
            )

            print(f"\n✅ API call successful for {email_id}")

            response_text = response.choices[0].message.content.strip()

            # 🔥 FULL DEBUG (VERY IMPORTANT)
            print("\n================ FULL LLM RESPONSE ================\n")
            print(response_text)
            print("\n==================================================\n")

            # 🔧 SAFE PARSE
            result = safe_parse_json(response_text)

            if not result:
                print(f"❌ Skipping {email_id} due to invalid JSON")
                return None

            result["id"] = email_id
            return result

        except Exception as e:
            print(f"\n❌ Unexpected error for {email_id} (attempt {attempt + 1}): {type(e).__name__}: {e}")
            traceback.print_exc()

            try:
                if hasattr(response, 'choices') and response.choices:
                    print("PARTIAL RESPONSE:", response.choices[0].message.content[:200])
            except:
                pass

            if attempt == MAX_RETRIES - 1:
                return None

            time.sleep(RETRY_DELAY)

    return None


def enrich_with_port_names(extraction, code_to_names, name_to_code):
    for code_field, name_field in [
        ("origin_port_code", "origin_port_name"),
        ("destination_port_code", "destination_port_name")
    ]:
        code = extraction.get(code_field)
        llm_name = extraction.get(name_field, "")
        
        # Validate code exists in reference
        if code and code not in code_to_names:
            extraction[code_field] = None
            extraction[name_field] = None
            continue
        
        if code:
            valid_names = code_to_names[code]
            # Try to match LLM's name against valid names for this code
            llm_lower = (llm_name or "").lower().strip()
            matched = next((n for n in valid_names if n.lower() == llm_lower), None)
            # Use matched name if found, otherwise use first valid name
            extraction[name_field] = matched if matched else valid_names[0]
        else:
            extraction[name_field] = None
    
    return extraction


def validate_extraction(extraction: Dict[str, Any]) -> Optional[ShipmentExtraction]:
    """Validate extraction against Pydantic schema."""
    try:
        return ShipmentExtraction(**extraction)
    except ValidationError as e:
        print(f"  ⚠️  Validation failed for {extraction.get('id', 'unknown')}")
        for error in e.errors():
            print(f"     {error['loc']}: {error['msg']}")
        return None


def process_emails(prompt_version: str = "v2", max_emails: Optional[int] = None) -> List[Dict[str, Any]]:
    """Process all emails and generate extractions."""
    print(f"\n🚀 Starting extraction (prompt version: {prompt_version})...\n")

    emails = load_emails()
    code_to_names, name_to_code  = load_port_reference()

    if max_emails:
        emails = emails[:max_emails]
        print(f"   Processing first {max_emails} emails (for testing)")

    print(f"   Total emails to process: {len(emails)}\n")

    results = []
    failed = []

    for i, email in enumerate(emails, 1):
        email_id = email.get("id")
        subject = email.get("subject", "")
        body = email.get("body", "")

        print(f"[{i}/{len(emails)}] Processing {email_id}...", end=" ")

        # Extract from LLM
        extraction = extract_with_groq(email_id, subject, body, code_to_names, prompt_version)

        if not extraction:
            print("❌ Failed")
            failed.append(email_id)
            continue

        # Enrich with port names
        extraction = enrich_with_port_names(extraction, code_to_names, name_to_code)

        # Validate
        validated = validate_extraction(extraction)
        if validated:
            results.append(validated.model_dump())
            print("✓")
        else:
            print("❌ Validation failed")
            failed.append(email_id)

    print(f"\n✅ Extraction complete!")
    print(f"   Successfully extracted: {len(results)}/{len(emails)}")
    if failed:
        print(f"   Failed: {failed}")

    return results


def save_output(results: List[Dict[str, Any]]) -> None:
    """Save results to output.json."""
    output_file = OUTPUT_FILE
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📁 Results saved to: {output_file}")


def main():
    """Main entry point."""
    try:
        # Get prompt version (default v2)
        prompt_version = sys.argv[1] if len(sys.argv) > 1 else "v2"
        max_emails = int(sys.argv[2]) if len(sys.argv) > 2 else None

        results = process_emails(prompt_version=prompt_version, max_emails=max_emails)
        save_output(results)

    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
