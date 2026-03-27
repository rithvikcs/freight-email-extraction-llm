"""Main extraction script - processes emails using Groq API and generates output.json."""

import json
import os
import sys
import time
from pathlib import Path
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
PORT_CODES_FILE = PARENT_DIR / "port_codes_reference.json"
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
    """Load port codes reference. Returns dict {code: name}."""
    if not PORT_CODES_FILE.exists():
        raise FileNotFoundError(
            f"port_codes_reference.json not found at {PORT_CODES_FILE}"
        )
    with open(PORT_CODES_FILE, "r") as f:
        ports = json.load(f)
    # Create {code: name} mapping
    return {port["code"]: port["name"] for port in ports}


def extract_with_groq(
    email_id: str, subject: str, body: str, prompt_version: str = "v2"
) -> Optional[Dict[str, Any]]:
    """Call Groq API to extract shipment data from email."""
    if not GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY not set in .env file. Please add your API key."
        )

    client = Groq(api_key=GROQ_API_KEY)
    prompt = get_extraction_prompt(version=prompt_version, subject=subject, body=body)

    # Replace email ID placeholder
    if "{id}" in prompt or "EMAIL_ID" in prompt:
        # The prompt template will use the actual email ID
        prompt = prompt.replace("EMAIL_ID", email_id)

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
            print(f"DEBUG: API call successful for {email_id}")

            # Extract JSON response
            response_text = response.choices[0].message.content.strip()
            print(f"DEBUG: Raw response for {email_id}: {repr(response_text[:200])}")

            # Try to parse JSON from response
            try:
                # Handle markdown code blocks if present
                if response_text.startswith("```"):
                    # Extract content between ``` markers
                    parts = response_text.split("```")
                    for part in parts:
                        part = part.strip()
                        if part.startswith("{") and part.endswith("}"):
                            response_text = part
                            break
                        elif part.startswith("json") and "{" in part:
                            # Remove "json" prefix if present
                            part = part.replace("json", "", 1).strip()
                            if part.startswith("{"):
                                response_text = part
                                break

                # Try to find JSON object in response (in case there's extra text)
                json_start = response_text.find("{")
                json_end = response_text.rfind("}") + 1

                if json_start != -1 and json_end > json_start:
                    json_content = response_text[json_start:json_end]
                    # Clean up any trailing commas or extra text
                    json_content = json_content.rstrip(", \n\t")
                    if json_content.endswith("},"):
                        json_content = json_content[:-1]
                    result = json.loads(json_content)
                else:
                    result = json.loads(response_text)

                result["id"] = email_id  # Ensure correct ID
                return result

            except json.JSONDecodeError as e:
                print(f"  ⚠️  Failed to parse JSON for {email_id}: {e}")
                print(f"     Response: {response_text[:300]}...")
                return None

        except Exception as e:
            print(f"  ❌ Unexpected error for {email_id} (attempt {attempt + 1}): {type(e).__name__}: {e}")
            # Print more debug info
            try:
                print(f"     Response object: {response}")
                if hasattr(response, 'choices') and response.choices:
                    print(f"     Message content: {repr(response.choices[0].message.content[:100])}")
            except:
                print("     Could not print response details")
            if attempt == MAX_RETRIES - 1:
                return None
            time.sleep(RETRY_DELAY)

    return None


def enrich_with_port_names(
    extraction: Dict[str, Any], port_reference: Dict[str, str]
) -> Dict[str, Any]:
    """Fill in port names from reference using extracted port codes."""
    if extraction.get("origin_port_code"):
        code = extraction["origin_port_code"]
        extraction["origin_port_name"] = port_reference.get(code)

    if extraction.get("destination_port_code"):
        code = extraction["destination_port_code"]
        extraction["destination_port_name"] = port_reference.get(code)

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


def process_emails(
    prompt_version: str = "v2", max_emails: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Process all emails and generate extractions."""
    print(f"\n🚀 Starting extraction (prompt version: {prompt_version})...\n")

    emails = load_emails()
    port_reference = load_port_reference()

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
        extraction = extract_with_groq(email_id, subject, body, prompt_version)

        if not extraction:
            print("❌ Failed")
            failed.append(email_id)
            continue

        # Enrich with port names
        extraction = enrich_with_port_names(extraction, port_reference)

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
        sys.exit(1)


if __name__ == "__main__":
    main()
