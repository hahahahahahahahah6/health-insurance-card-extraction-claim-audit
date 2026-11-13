# Documentation claim auditor

An offline, read-only checker compares promises in documentation with recognizable operation calls in source. It uses the standard library, never executes inspected source, and makes no network calls.

## Installation and usage

```sh
python3 -m venv .venv
.venv/bin/pip install .
health-insurance-card-extraction-claim-audit --version
health-insurance-card-extraction-claim-audit audit .
python3 -m health_insurance_card_extraction_claim_audit audit . --json
health-insurance-card-extraction-claim-audit audit . --fail-on medium --ignore vendor --ignore generated
python3 -m unittest discover
```

The optional repository argument defaults to the current directory. The threshold accepts lowercase high or medium and defaults to high. Each ignore option takes one relative path prefix, matching a full path component boundary. Verbose output includes evidence paths. JSON output contains verdict, findings, production_evidence, and test_evidence; each finding includes id, severity, message, and docs.

Exit status is 0 when there are no findings meeting the threshold, 2 when there are, and 1 for usage or I/O errors. A medium finding still gives a FAIL verdict even when the default threshold permits status 0. Version output is 0.1.0.

```text
documented-health-insurance-card-extraction-claim-false
documented-no-health-insurance-card-extraction-claim-false
```

A positive promise without production evidence produces the first identifier at HIGH severity, or MEDIUM when evidence exists only in tests. A denial contradicted by production evidence produces the second identifier at HIGH severity. With no source files, a positive promise still fails; a denial passes. There is at most one finding for each direction.

## Matching rules

The checker reads root README.md and Markdown files with a docs path component. Backtick and tilde fences with up to three leading spaces are excluded; inline code counts. Paragraphs are separated by blank lines. Matching lowercases text, expands negative contractions, replaces hyphens with spaces, and collapses whitespace. Exact phrases use word boundaries, longest first with alphabetical ties. Denial spans are removed before checking positive phrases.

Source files are parsed as ASTs. Symlinked files and directories are excluded. Files beneath fixtures, docs, and examples never supply evidence. Files beneath tests or named with the test prefix or suffix supply only test evidence. Invalid syntax supplies none. Each paired route must occur in a single module. Imports and aliases are resolved, and local function, method, class, assignment, annotated assignment, and context-manager bindings can shadow imported names.

The checked operation concerns structured insurer, member, group, dependent, payer, enrollment, copay, and prescription fields from US plan cards. Recognized routes are the following paired SDK calls and 24 specific generic operation names. Bare imports and bare references never count.

```text
azure.ai.formrecognizer.DocumentAnalysisClient
azure.ai.documentintelligence.DocumentIntelligenceClient
begin_analyze_document / begin_analyze_document_from_url
first positional argument or model_id="prebuilt-healthInsuranceCard.us"

mindee.Client + parse(HealthcareCardV1, ...)
mindee.Client + parse(product.us.HealthcareCardV1, ...)
```

The second pair uses the fixed US endpoint and counts because it returns company name, member name and ID, group number, copays, and prescription information. Construction alone and a parse call alone do not count. Generic attribute calls count on any base; a bare generic name requires a matching from-import. Local definitions of the route name suppress it.

## Honest limitations

Static patterns do not establish semantic correctness. Dead code counts, untraceable alias chains can be missed, exact vocabulary misses paraphrases, and denial handling depends on a fixed list. Card terminology may describe displaying an image or rendering a template. Shorter terms may mean a gym membership, a national ID, a fitness-app card, auto coverage, dental or vision coverage, or pet coverage. Government-issued medical cards used only for ID verification may also trigger a promise. These are documented false-positive hazards.

A recognized generic call may merely parse user-typed numbers or previously extracted strings. It still counts by name. Conversely, manual field assembly using regular expressions over OCR output is missed unless a listed call exists. Plain string splitting is insufficient. External commands invoked through subprocess, including the SDK vendors' command-line tools, never count. Cloud client calls are detected in source; credentials, connectivity, and successful execution are not verified.

The following vendor methods are excluded. Generic configurable processing has no dedicated route for the checked capability; receipt/invoice, tax, check, statement, and business-card operations address separate document types. Classification and retrieval or management are also insufficient. This vendor supplies no dedicated method for the checked operation.

```text
Veryfi:
process_any_document / process_any_document_url
process_document / process_document_url
process_w2_document / process_w9_document / process_w8_document
process_check / process_check_url
process_check_with_remittance / process_check_with_remittance_url
process_bank_statement_document / process_bank_statement_document_url
process_bussines_card_document
classify_document
get_w2s / get_w2 / delete_w2 / get_w9s / get_w9 / delete_w9
get_w8s / get_w8 / delete_w8 / get_bank_statements / get_checks
```

The first SDK's model identifier is exact and case-sensitive, including its regional suffix and capital H, I, and C. Shorthand lowercase table labels are insufficient. The excluded identifiers below address other document types or are invalid spellings. The second SDK's other product classes also do not count; only the fixed version shown above is accepted.

```text
Azure excluded model IDs:
prebuilt-healthInsuranceCard
prebuilt-healthinsurancecard.us
prebuilt-invoice / prebuilt-receipt / prebuilt-layout / prebuilt-read
prebuilt-idDocument / prebuilt-check.us / prebuilt-tax.us
prebuilt-bankStatement.us / prebuilt-payStub.us

Mindee excluded products:
InvoiceV4 / ReceiptV5 / PassportV1 / FinancialDocumentV1
BankCheckV1 / BankAccountDetailsV2 / PayslipV2 / PayslipV3 / CustomV1
HealthcareCardV2 / TypeHealthcareCard

Textract excluded calls:
analyze_document / analyze_expense / start_document_analysis / get_expense_analysis
```

Generic document or expense analysis supplies no dedicated route for the checked feature. Plain text recognition, CSV or spreadsheet reading, and PDF table operations are insufficient as well.

```text
pdfplumber / fitz / pypdf / PyPDF2 / pdfminer: extract_text
pytesseract: image_to_string
pandas: read_csv / read_excel
camelot: read_pdf
tabula: read_pdf / convert_into
pdfplumber: extract_table / extract_tables / find_table / find_tables
fitz: find_tables
```

Promises about extracting member IDs, group numbers, or copays alone are outside the vocabulary. Eligibility verification, coverage checking, and benefit validation are also outside it: payer checks do not promise document field recovery.

## Differentiation

Invoice extraction, receipt extraction, bank-check extraction, bank-statement extraction, tax-form extraction, and pay-stub extraction concern other document types and use different routes. ID document extraction concerns identification fields. OCR concerns text recognition; table extraction concerns table structure. The checked capability instead concerns structured fields from US plan cards. Promises about those neighbouring families alone are outside this check's vocabulary.

## Development

```sh
python3 -m unittest discover
python3 -m py_compile health_insurance_card_extraction_claim_audit/*.py
python3 -m build
```

The distribution includes the test suite. The fixed phrase oracle is independent of any external specification file. The positive vocabulary contains 51 literal entries despite its source specification's count label of 50; all listed entries are retained. The denial vocabulary has 24 entries and the generic operation vocabulary has 24 entries.
