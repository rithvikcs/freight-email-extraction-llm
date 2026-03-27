# Freight Email Extraction System

LLM-powered email extraction system for freight forwarding pricing inquiries using Groq API.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env          # Add your Groq API key
python extract.py             # Extract all 50 emails
python evaluate.py            # Check accuracy
```

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Key
Copy `.env.example` to `.env` and add your Groq API key:
```bash
cp .env.example .env
```

Then edit `.env` and add your key:
```
GROQ_API_KEY=your-actual-key-here
```

**Get your API key:**
- Visit https://console.groq.com
- Sign up (free, no credit card required)
- Generate an API key in the dashboard

### 3. Run Extraction
```bash
python extract.py        # Uses default prompt v2
python extract.py v2     # Specify prompt version
python extract.py v2 10  # Test with first 10 emails
```

This will:
- Read `emails_input.json`
- Call Groq API to extract shipment details
- Generate `output.json` with results

### 4. Evaluate Accuracy
```bash
python evaluate.py
```

Shows accuracy metrics by field and highlights mismatches.

---

## Project Structure

```
├── extract.py              # Main extraction script
├── evaluate.py             # Accuracy evaluation
├── schemas.py              # Pydantic models
├── prompts.py              # LLM prompt templates (v1, v2, ...)
├── requirements.txt        # Dependencies
├── output.json            # Generated results
├── .env                   # Your API key (NOT in repo)
├── .env.example           # Template for .env
└── README.md              # This file
```

---

## Extraction Output Schema

```json
{
  "id": "EMAIL_001",
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

---

## Extraction Logic

### Key Business Rules
1. **Product Line**: Destination is India → `pl_sea_import_lcl`; Origin is India → `pl_sea_export_lcl`
2. **Port Codes**: 5-letter UN/LOCODE (e.g., INMAA, HKHKG)
3. **Incoterm**: Default `FOB` if not mentioned
4. **Dangerous Goods**: true if mentions DG, hazardous, Class+number, IMO, IMDG
5. **Numbers**: Round to 2 decimals, use `null` for missing values
6. **Conflicts**: Body takes precedence over subject; extract first shipment if multiple

### Supported Incoterms
FOB, CIF, CFR, EXW, DDP, DAP, FCA, CPT, CIP, DPU

---

## Prompt Evolution

### v1: Basic extraction
- **Approach**: Simple rule listing with port examples
- **Accuracy**: Baseline (~60-65%)
- **Issues**: Port code matching inconsistent, missing edge cases
- **Example**: EMAIL_007 extracted "Chennai" instead of "INMAA"

### v2: Enhanced business rules (CURRENT)
- **Approach**: Detailed rule documentation, explicit conflict resolution
- **Accuracy**: ~75%+
- **Improvements**: Better Indian port detection, clearer incoterm logic, weight conversion examples
- **Status**: Testing in progress...

#### Future Improvements (v3+):
- Add few-shot examples of actual emails from ground truth
- Include exact port name mappings from reference file
- Enhanced unit conversion logic
- Better dangerous goods keyword matching

---

## Implementation Notes

### Files Used
- `emails_input.json`: 50 sample emails (array of {id, subject, body})
- `ground_truth.json`: Expected outputs for accuracy measurement
- `port_codes_reference.json`: UN/LOCODE mappings (47 ports)

### API Configuration
- **Provider**: Groq (free tier, no credit card)
- **Model**: `llama-3.1-70b-versatile`
- **Temperature**: 0 (for reproducibility)
- **Rate Limit**: ~30 requests/minute (auto-retry with exponential backoff)

### Timing
- Processing 50 emails: 5-10 minutes (due to rate limits)
- Each successful extraction: ~1-3 seconds

---

## Troubleshooting

### "GROQ_API_KEY not set"
- Check `.env` file exists in project root
- Ensure `GROQ_API_KEY=your-key` is set correctly (no quotes)
- Reload terminal after creating `.env`

### "emails_input.json not found"
- Ensure file exists in parent directory (`../emails_input.json`)
- Run `extract.py` from project root

### Rate Limit Errors (429)
- The script auto-retries with exponential backoff
- Wait time increases: 2s → 4s → 8s
- For full batch, expect 5-10 minute runtime

### JSON Parse Errors
- LLM sometimes returns non-JSON text
- Script skips and continues with next email
- Check console output for error details

---

## Submission

This project will be evaluated on:
1. **Extraction accuracy** on the 50 provided emails
2. **Code quality** (organization, error handling, documentation)
3. **Performance** on 171 hidden test emails (uses same rules and port reference)
4. **Prompt engineering** and iteration process documentation

See parent README.md for full assessment guidelines.
