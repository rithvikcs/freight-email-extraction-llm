"""LLM prompt templates for email extraction. Track evolution across versions."""

SYSTEM_PROMPT = """You are an expert in logistics and freight forwarding. 
Your task is to extract structured shipment details from pricing inquiry emails.
Return ONLY valid JSON, no additional text."""

EXTRACTION_PROMPT_V1 = """Extract shipment details from the following email.

Business Rules:
1. Port Codes: Use UN/LOCODE format (5 letters: 2-letter country + 3-letter location code)
   - Indian ports start with 'IN' (e.g., INMAA for Chennai, INNSA for Nhava Sheva)
2. Product Line: 
   - If destination is India → "pl_sea_import_lcl"
   - If origin is India → "pl_sea_export_lcl"
3. Incoterm: Default to "FOB" if not mentioned. Valid terms: FOB, CIF, CFR, EXW, DDP, DAP, FCA, CPT, CIP, DPU
4. Dangerous Goods: 
   - Set true if email mentions: "DG", "dangerous", "hazardous", "Class" + number, "IMO", "IMDG"
   - Set false if mentions: "non-DG", "non-hazardous", "not dangerous" or no mention
5. Numbers: Round cargo_weight_kg and cargo_cbm to 2 decimals. Use null for missing values.
6. Conversions:
   - Weight in lbs → multiply by 0.453592
   - Weight in tonnes/MT → multiply by 1000
7. Multiple shipments: Extract the FIRST shipment only
8. Conflicts: Body takes precedence over subject

Return a JSON object with these fields:
{
  "id": "EMAIL_ID",
  "product_line": "pl_sea_import_lcl" or "pl_sea_export_lcl" or null,
  "origin_port_code": "XXXXX" or null,
  "origin_port_name": null,
  "destination_port_code": "XXXXX" or null,
  "destination_port_name": null,
  "incoterm": "FOB" or other or null,
  "cargo_weight_kg": float or null,
  "cargo_cbm": float or null,
  "is_dangerous": boolean
}

Email:
Subject: {subject}
Body: {body}

JSON:"""

EXTRACTION_PROMPT_V2 = """Extract shipment details from the following email.

CRITICAL RULES:
1. Port Code Matching:
   - Indian ports have UN/LOCODE starting with "IN"
   - Examples: INMAA (Chennai), INNSA (Nhava Sheva), INBLR (Bangalore), INCOK (Cochin)
   - Look for port names in email and match to UN/LOCODE format
   - Common abbreviations: HK→Hong Kong (HKHKG), SH→Shanghai (CNSHA), SG→Singapore (SGSIN)

2. Product Line Logic:
   - Destination is India (port code starts with IN) → "pl_sea_import_lcl"
   - Origin is India (port code starts with IN) → "pl_sea_export_lcl"
   - All shipments in this exercise are LCL (Less than Container Load)

3. Incoterm Handling:
   - If email explicitly states an incoterm → use it (normalize to uppercase)
   - If not mentioned → default to "FOB"
   - If ambiguous or multiple mentioned (e.g., "FOB or CIF") → default to "FOB"
   - Valid terms: FOB, CIF, CFR, EXW, DDP, DAP, FCA, CPT, CIP, DPU

4. Dangerous Goods:
   - TRUE if contains: "DG", "dangerous", "hazardous", "Class 3", "Class 4", "Class 9", "IMO", "IMDG"
   - FALSE if contains: "non-hazardous", "non-DG", "not dangerous"
   - FALSE if no mention (default)

5. Weight/CBM:
   - Extract both independently if mentioned
   - Convert: lbs × 0.453592 = kg; tonnes × 1000 = kg
   - Round to 2 decimals
   - If "TBD", "N/A", "to be confirmed" → null
   - Explicit "0" → keep as 0, not null

6. Port Names:
   - Use the canonical port name from your reference list
   - If code is null, name is also null

7. Conflict Resolution:
   - Body text overrides subject line
   - Multiple shipments → extract FIRST one only
   - Multiple origin/destination pairs → use origin→destination pair, not transshipment ports

Extract the shipment details and respond with ONLY a JSON code block like this:

```json
{
  "product_line": "pl_sea_import_lcl",
  "origin_port_code": "HKHKG",
  "origin_port_name": "Hong Kong",
  "destination_port_code": "INMAA",
  "destination_port_name": "Chennai",
  "incoterm": "FOB",
  "cargo_weight_kg": null,
  "cargo_cbm": 5.0,
  "is_dangerous": false
}
```

Email:
Subject: {subject}
Body: {body}

```json
"""


def get_extraction_prompt(version: str = "v2", subject: str = "", body: str = "") -> str:
    if version == "v1":
        template = EXTRACTION_PROMPT_V1
    elif version == "v2":
        template = EXTRACTION_PROMPT_V2
    else:
        template = EXTRACTION_PROMPT_V2  # Default to latest
    return template.format(subject=subject, body=body)
