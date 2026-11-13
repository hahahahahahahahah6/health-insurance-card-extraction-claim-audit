import ast
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from health_insurance_card_extraction_claim_audit import phrases
from health_insurance_card_extraction_claim_audit.audit import audit, evidence, claims
from health_insurance_card_extraction_claim_audit.__main__ import main

class AuditTests(unittest.TestCase):
    def setUp(self):
            self.temp = tempfile.TemporaryDirectory()
            self.addCleanup(self.temp.cleanup)
            self.root = Path(self.temp.name)
    def put(self, name, text):
            path = self.root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            return path
    def cli(self, *args):
            with contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()):
                code = main(['audit', str(self.root), *args])
            return code, out.getvalue()
    def test_bad(self):
            self.put('README.md', 'We extract health insurance cards.')
            result = audit(self.root)
            self.assertEqual(result['findings'][0]['id'], 'documented-health-insurance-card-extraction-claim-false')
            self.assertEqual(result['findings'][0]['severity'], 'HIGH')
            self.assertEqual(self.cli()[0], 2)
    def test_good(self):
            self.put('README.md', 'We extract health insurance cards.')
            self.put('app.py', 'x.extract_health_insurance_card(doc)')
            self.assertEqual(self.cli()[0], 0)
            self.assertEqual(audit(self.root)['verdict'], 'PASS')
    def test_denial(self):
            self.put('README.md', 'Does not extract health insurance cards.')
            self.assertEqual(audit(self.root)['verdict'], 'PASS')
            self.put('app.py', 'x.extract_health_insurance_card(doc)')
            f = audit(self.root)['findings'][0]
            self.assertEqual(f['id'], 'documented-no-health-insurance-card-extraction-claim-false')
            self.assertEqual(f['severity'], 'HIGH')
            self.assertEqual(self.cli()[0], 2)
    def test_test_only(self):
            self.put('README.md', 'extract health insurance cards')
            self.put('tests/test_app.py', 'x.extract_health_insurance_card(doc)')
            self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')
            self.assertEqual(self.cli()[0], 0)
            self.assertEqual(self.cli('--fail-on', 'medium')[0], 2)
    def test_no_claim(self):
            self.put('README.md', 'A utility.')
            self.put('app.py', 'x.extract_health_insurance_card(doc)')
            self.assertEqual(audit(self.root)['verdict'], 'PASS')
    def test_json(self):
            self.put('README.md', 'extract health insurance cards')
            code, text = self.cli('--json')
            self.assertEqual(code, 2)
            result = json.loads(text)
            self.assertEqual(result['verdict'], 'FAIL')
            self.assertIn('message', result['findings'][0])
    def test_split_modules(self):
            self.put('README.md', 'extract health insurance cards')
            self.put('one.py', 'import mindee\nc = mindee.Client()')
            self.put('two.py', 'c.parse(HealthcareCardV1, doc)')
            self.assertEqual(self.cli()[0], 2)
    def test_symlinks(self):
            self.put('README.md', 'extract health insurance cards')
            target = self.put('fixtures/source.py', 'x.extract_health_insurance_card(doc)')
            (self.root/'app.py').symlink_to(target)
            (self.root/'linked').symlink_to(target.parent, target_is_directory=True)
            self.assertEqual(self.cli()[0], 2)
    def test_docs_and_ignore(self):
            self.put('nested/docs/a.md', 'extract health insurance cards')
            self.assertEqual(self.cli()[0], 2)
            self.assertEqual(self.cli('--ignore', 'nested/docs')[0], 0)
            self.assertEqual(self.cli('--ignore', 'nested/doc')[0], 2)
    def test_usage(self):
            for args in ([], ['oops'], ['audit', '--fail-on', 'HIGH'], ['audit', '--ignore', 'a', 'b', 'c']):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                    main(args)
                self.assertEqual(caught.exception.code, 1)
    def test_bad_path(self):
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['audit', str(self.root/'missing')]), 1)
    def test_entry_points(self):
            result = subprocess.run([sys.executable, '-m', 'health_insurance_card_extraction_claim_audit', '--version'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), '0.1.0')
    def test_console_entry(self):
            import shutil
            executable = shutil.which('health-insurance-card-extraction-claim-audit')
            if executable:
                result = subprocess.run([executable, '--version'], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout.strip(), '0.1.0')
            else:
                project = Path(__file__).resolve().parents[1]/'pyproject.toml'
                self.assertIn('health-insurance-card-extraction-claim-audit = "health_insurance_card_extraction_claim_audit.__main__:main"', project.read_text())
                with contextlib.redirect_stdout(io.StringIO()) as output, self.assertRaises(SystemExit) as caught:
                    main(['--version'])
                self.assertEqual(caught.exception.code, 0)
                self.assertEqual(output.getvalue().strip(), '0.1.0')
    def test_excluded_005(self):
            self.assertEqual(evidence('def extract_health_insurance_card(doc): pass\nextract_health_insurance_card(doc)'), False)
    def test_excluded_006(self):
            self.assertEqual(evidence('def extract_health_insurance_card(doc): pass\nx.extract_health_insurance_card(doc)'), False)
    def test_excluded_007(self):
            self.assertEqual(evidence('class extract_health_insurance_card: pass\nx.extract_health_insurance_card(doc)'), False)
    def test_excluded_008(self):
            self.assertEqual(evidence('class X:\n def extract_health_insurance_card(self): pass\nx.extract_health_insurance_card(doc)'), False)
    def test_excluded_009(self):
            self.assertEqual(evidence('extract_health_insurance_card(doc)'), False)
    def test_excluded_010(self):
            self.assertEqual(evidence('x.extract_health_insurance_card'), False)
    def test_excluded_011(self):
            self.assertEqual(evidence('# x.extract_health_insurance_card(doc)\ns="x.extract_health_insurance_card(doc)"'), False)
    def test_excluded_012(self):
            self.assertEqual(evidence('def broken('), False)
    def test_excluded_013(self):
            self.assertEqual(evidence('extract_health_insurance_card = callback\nextract_health_insurance_card(doc)'), False)
    def test_excluded_014(self):
            self.assertEqual(evidence('from engine import extract_health_insurance_card\nextract_health_insurance_card: object = callback\nextract_health_insurance_card(doc)'), False)
    def test_excluded_015(self):
            self.assertEqual(evidence('from engine import extract_health_insurance_card\nwith context() as extract_health_insurance_card:\n extract_health_insurance_card(doc)'), False)
    def test_excluded_016(self):
            self.assertEqual(evidence('from engine import extract_health_insurance_card\nasync def f():\n async with context() as extract_health_insurance_card:\n  extract_health_insurance_card(doc)'), False)
    def test_fence_0(self):
            self.assertEqual(claims('```\nextract health insurance cards\n```'), (False, False))
    def test_fence_1(self):
            self.assertEqual(claims('   ~~~~\nextract health insurance cards\n   ~~~~'), (False, False))
    def test_fence_2(self):
            self.assertEqual(claims('```text\nextract health insurance cards\n```'), (False, False))
    def test_inline_and_contraction(self):
            self.assertEqual(claims('We `extract health insurance cards`.'), (True, False))
            self.assertEqual(claims("doesn't extract health insurance cards"), (False, True))
            self.assertEqual(claims('health-insurance-card extraction'), (True, False))
    def test_excluded_paths(self):
            self.put('README.md', 'extract health insurance cards')
            for path in ('fixtures/app.py', 'docs/app.py', 'examples/app.py'):
                self.put(path, 'x.extract_health_insurance_card(doc)')
            self.assertEqual(self.cli()[0], 2)
    def test_test_filename(self):
            self.put('README.md', 'extract health insurance cards')
            self.put('app_test.py', 'x.extract_health_insurance_card(doc)')
            self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')
    def test_split_azure(self):
            self.put('README.md', 'extract health insurance cards')
            self.put('one.py', 'from azure.ai.formrecognizer import DocumentAnalysisClient\nc=DocumentAnalysisClient()')
            self.put('two.py', "c.begin_analyze_document('prebuilt-healthInsuranceCard.us')")
            self.assertEqual(self.cli()[0], 2)
    def test_readme_self_audit(self):
            self.assertEqual(claims((Path(__file__).resolve().parents[1]/'README.md').read_text()), (False, False))
    def test_boundaries(self):
            self.assertEqual(claims('preextract health insurance cardsuffix'), (False, False))
            self.assertEqual(claims('extract pay\n\nstubs'), (False, False))
    def test_phrase_oracle(self):
        tree = ast.parse(Path(phrases.__file__).read_text())
        values = {n.targets[0].id: ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)}
        self.assertEqual(values['HEALTHINSURANCECARDEXTRACTION'], ('health insurance card extraction', 'extract health insurance cards', 'extracts health insurance cards', 'extracting health insurance cards', 'extract health insurance card', 'extracts health insurance card', 'extracting health insurance card', 'health insurance card parsing', 'health insurance card parser', 'parse health insurance cards', 'parses health insurance cards', 'parse health insurance card', 'parses health insurance card', 'health card extraction', 'extract health cards', 'extracts health cards', 'extracting health cards', 'extract health card', 'extracts health card', 'extracting health card', 'health card parsing', 'health card parser', 'parse health cards', 'parses health cards', 'parse health card', 'parses health card', 'insurance card extraction', 'extract insurance cards', 'extracts insurance cards', 'extracting insurance cards', 'extract insurance card', 'extracts insurance card', 'extracting insurance card', 'insurance card parsing', 'insurance card parser', 'parse insurance cards', 'parses insurance cards', 'parse insurance card', 'parses insurance card', 'medical insurance card extraction', 'extract medical insurance cards', 'extracts medical insurance cards', 'extracting medical insurance cards', 'extract medical insurance card', 'extracts medical insurance card', 'extracting medical insurance card', 'health insurance card data extraction', 'extract health insurance card data', 'health insurance card field extraction', 'health insurance card document extraction', 'extract health insurance card documents'))
        self.assertEqual(values['NOHEALTHINSURANCECARDEXTRACTION'], ('no health insurance card extraction', 'does not extract health insurance cards', 'does not extract health insurance card', 'does not support health insurance card extraction', 'without health insurance card extraction', 'no health card extraction', 'does not extract health cards', 'does not extract health card', 'does not support health card extraction', 'without health card extraction', 'no insurance card extraction', 'does not extract insurance cards', 'does not extract insurance card', 'does not support insurance card extraction', 'without insurance card extraction', 'no medical insurance card extraction', 'does not extract medical insurance cards', 'does not extract medical insurance card', 'health insurance card extraction not supported', 'health card extraction not supported', 'insurance card extraction not supported', 'no health insurance card parser', 'does not parse health insurance cards', 'does not parse health insurance card'))
        self.assertEqual(values['GENERIC_NAMES'], ('extract_health_insurance_card', 'extract_health_insurance_cards', 'parse_health_insurance_card', 'parse_health_insurance_cards', 'extract_health_card', 'extract_health_cards', 'parse_health_card', 'parse_health_cards', 'extract_insurance_card', 'extract_insurance_cards', 'parse_insurance_card', 'parse_insurance_cards', 'extract_medical_insurance_card', 'extract_medical_insurance_cards', 'parse_medical_insurance_card', 'parse_medical_insurance_cards', 'extract_health_insurance_card_data', 'parse_health_insurance_card_data', 'health_insurance_card_extraction', 'health_insurance_card_extractor', 'health_insurance_card_parser', 'insurance_card_extraction', 'extract_health_card_data', 'parse_health_card_data'))
        self.assertEqual(values['AZURE_MODEL_IDS'], ('prebuilt-healthInsuranceCard.us',))
        self.assertEqual(values['MINDEE_PRODUCTS'], ('HealthcareCardV1',))
    def test_positive_000(self):
        self.assertEqual(claims('health insurance card extraction'), (True, False))
    def test_positive_001(self):
        self.assertEqual(claims('extract health insurance cards'), (True, False))
    def test_positive_002(self):
        self.assertEqual(claims('extracts health insurance cards'), (True, False))
    def test_positive_003(self):
        self.assertEqual(claims('extracting health insurance cards'), (True, False))
    def test_positive_004(self):
        self.assertEqual(claims('extract health insurance card'), (True, False))
    def test_positive_005(self):
        self.assertEqual(claims('extracts health insurance card'), (True, False))
    def test_positive_006(self):
        self.assertEqual(claims('extracting health insurance card'), (True, False))
    def test_positive_007(self):
        self.assertEqual(claims('health insurance card parsing'), (True, False))
    def test_positive_008(self):
        self.assertEqual(claims('health insurance card parser'), (True, False))
    def test_positive_009(self):
        self.assertEqual(claims('parse health insurance cards'), (True, False))
    def test_positive_010(self):
        self.assertEqual(claims('parses health insurance cards'), (True, False))
    def test_positive_011(self):
        self.assertEqual(claims('parse health insurance card'), (True, False))
    def test_positive_012(self):
        self.assertEqual(claims('parses health insurance card'), (True, False))
    def test_positive_013(self):
        self.assertEqual(claims('health card extraction'), (True, False))
    def test_positive_014(self):
        self.assertEqual(claims('extract health cards'), (True, False))
    def test_positive_015(self):
        self.assertEqual(claims('extracts health cards'), (True, False))
    def test_positive_016(self):
        self.assertEqual(claims('extracting health cards'), (True, False))
    def test_positive_017(self):
        self.assertEqual(claims('extract health card'), (True, False))
    def test_positive_018(self):
        self.assertEqual(claims('extracts health card'), (True, False))
    def test_positive_019(self):
        self.assertEqual(claims('extracting health card'), (True, False))
    def test_positive_020(self):
        self.assertEqual(claims('health card parsing'), (True, False))
    def test_positive_021(self):
        self.assertEqual(claims('health card parser'), (True, False))
    def test_positive_022(self):
        self.assertEqual(claims('parse health cards'), (True, False))
    def test_positive_023(self):
        self.assertEqual(claims('parses health cards'), (True, False))
    def test_positive_024(self):
        self.assertEqual(claims('parse health card'), (True, False))
    def test_positive_025(self):
        self.assertEqual(claims('parses health card'), (True, False))
    def test_positive_026(self):
        self.assertEqual(claims('insurance card extraction'), (True, False))
    def test_positive_027(self):
        self.assertEqual(claims('extract insurance cards'), (True, False))
    def test_positive_028(self):
        self.assertEqual(claims('extracts insurance cards'), (True, False))
    def test_positive_029(self):
        self.assertEqual(claims('extracting insurance cards'), (True, False))
    def test_positive_030(self):
        self.assertEqual(claims('extract insurance card'), (True, False))
    def test_positive_031(self):
        self.assertEqual(claims('extracts insurance card'), (True, False))
    def test_positive_032(self):
        self.assertEqual(claims('extracting insurance card'), (True, False))
    def test_positive_033(self):
        self.assertEqual(claims('insurance card parsing'), (True, False))
    def test_positive_034(self):
        self.assertEqual(claims('insurance card parser'), (True, False))
    def test_positive_035(self):
        self.assertEqual(claims('parse insurance cards'), (True, False))
    def test_positive_036(self):
        self.assertEqual(claims('parses insurance cards'), (True, False))
    def test_positive_037(self):
        self.assertEqual(claims('parse insurance card'), (True, False))
    def test_positive_038(self):
        self.assertEqual(claims('parses insurance card'), (True, False))
    def test_positive_039(self):
        self.assertEqual(claims('medical insurance card extraction'), (True, False))
    def test_positive_040(self):
        self.assertEqual(claims('extract medical insurance cards'), (True, False))
    def test_positive_041(self):
        self.assertEqual(claims('extracts medical insurance cards'), (True, False))
    def test_positive_042(self):
        self.assertEqual(claims('extracting medical insurance cards'), (True, False))
    def test_positive_043(self):
        self.assertEqual(claims('extract medical insurance card'), (True, False))
    def test_positive_044(self):
        self.assertEqual(claims('extracts medical insurance card'), (True, False))
    def test_positive_045(self):
        self.assertEqual(claims('extracting medical insurance card'), (True, False))
    def test_positive_046(self):
        self.assertEqual(claims('health insurance card data extraction'), (True, False))
    def test_positive_047(self):
        self.assertEqual(claims('extract health insurance card data'), (True, False))
    def test_positive_048(self):
        self.assertEqual(claims('health insurance card field extraction'), (True, False))
    def test_positive_049(self):
        self.assertEqual(claims('health insurance card document extraction'), (True, False))
    def test_positive_050(self):
        self.assertEqual(claims('extract health insurance card documents'), (True, False))
    def test_negative_000(self):
        self.assertEqual(claims('no health insurance card extraction'), (False, True))
    def test_negative_001(self):
        self.assertEqual(claims('does not extract health insurance cards'), (False, True))
    def test_negative_002(self):
        self.assertEqual(claims('does not extract health insurance card'), (False, True))
    def test_negative_003(self):
        self.assertEqual(claims('does not support health insurance card extraction'), (False, True))
    def test_negative_004(self):
        self.assertEqual(claims('without health insurance card extraction'), (False, True))
    def test_negative_005(self):
        self.assertEqual(claims('no health card extraction'), (False, True))
    def test_negative_006(self):
        self.assertEqual(claims('does not extract health cards'), (False, True))
    def test_negative_007(self):
        self.assertEqual(claims('does not extract health card'), (False, True))
    def test_negative_008(self):
        self.assertEqual(claims('does not support health card extraction'), (False, True))
    def test_negative_009(self):
        self.assertEqual(claims('without health card extraction'), (False, True))
    def test_negative_010(self):
        self.assertEqual(claims('no insurance card extraction'), (False, True))
    def test_negative_011(self):
        self.assertEqual(claims('does not extract insurance cards'), (False, True))
    def test_negative_012(self):
        self.assertEqual(claims('does not extract insurance card'), (False, True))
    def test_negative_013(self):
        self.assertEqual(claims('does not support insurance card extraction'), (False, True))
    def test_negative_014(self):
        self.assertEqual(claims('without insurance card extraction'), (False, True))
    def test_negative_015(self):
        self.assertEqual(claims('no medical insurance card extraction'), (False, True))
    def test_negative_016(self):
        self.assertEqual(claims('does not extract medical insurance cards'), (False, True))
    def test_negative_017(self):
        self.assertEqual(claims('does not extract medical insurance card'), (False, True))
    def test_negative_018(self):
        self.assertEqual(claims('health insurance card extraction not supported'), (False, True))
    def test_negative_019(self):
        self.assertEqual(claims('health card extraction not supported'), (False, True))
    def test_negative_020(self):
        self.assertEqual(claims('insurance card extraction not supported'), (False, True))
    def test_negative_021(self):
        self.assertEqual(claims('no health insurance card parser'), (False, True))
    def test_negative_022(self):
        self.assertEqual(claims('does not parse health insurance cards'), (False, True))
    def test_negative_023(self):
        self.assertEqual(claims('does not parse health insurance card'), (False, True))
    def test_not_evidence_000(self):
            self.assertEqual(evidence('import mindee'), False)
    def test_not_evidence_001(self):
            self.assertEqual(evidence('import veryfi'), False)
    def test_not_evidence_002(self):
            self.assertEqual(evidence('import boto3'), False)
    def test_not_evidence_003(self):
            self.assertEqual(evidence('import azure.ai.formrecognizer'), False)
    def test_not_evidence_004(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()'), False)
    def test_not_evidence_005(self):
            self.assertEqual(evidence('import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()'), False)
    def test_not_evidence_006(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()'), False)
    def test_not_evidence_007(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-invoice')"), False)
    def test_not_evidence_008(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-receipt')"), False)
    def test_not_evidence_009(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-layout')"), False)
    def test_not_evidence_010(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-read')"), False)
    def test_not_evidence_011(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-idDocument')"), False)
    def test_not_evidence_012(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-check.us')"), False)
    def test_not_evidence_013(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-tax.us')"), False)
    def test_not_evidence_014(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-bankStatement.us')"), False)
    def test_not_evidence_015(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-payStub')"), False)
    def test_not_evidence_016(self):
            self.assertEqual(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-paystub.us')"), False)
    def test_not_evidence_017(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(InvoiceV4, doc)'), False)
    def test_not_evidence_018(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(ReceiptV5, doc)'), False)
    def test_not_evidence_019(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(PassportV1, doc)'), False)
    def test_not_evidence_020(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(FinancialDocumentV1, doc)'), False)
    def test_not_evidence_021(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(BankCheckV1, doc)'), False)
    def test_not_evidence_022(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(BankAccountDetailsV2, doc)'), False)
    def test_not_evidence_023(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(CustomV1, doc)'), False)
    def test_not_evidence_024(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(TypeHealthcareCardV1, doc)'), False)
    def test_not_evidence_025(self):
            self.assertEqual(evidence('import mindee\nc=mindee.Client()\nc.parse(TypeHealthcareCardV1, doc)'), False)
    def test_not_evidence_026(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_any_document(doc)'), False)
    def test_not_evidence_027(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_any_document_url(doc)'), False)
    def test_not_evidence_028(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_document(doc)'), False)
    def test_not_evidence_029(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_document_url(doc)'), False)
    def test_not_evidence_030(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_w2_document(doc)'), False)
    def test_not_evidence_031(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_w2_document_url(doc)'), False)
    def test_not_evidence_032(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_w9_document(doc)'), False)
    def test_not_evidence_033(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_w9_document_url(doc)'), False)
    def test_not_evidence_034(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_w8_document(doc)'), False)
    def test_not_evidence_035(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_w8_document_url(doc)'), False)
    def test_not_evidence_036(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_check(doc)'), False)
    def test_not_evidence_037(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_check_url(doc)'), False)
    def test_not_evidence_038(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_check_with_remittance(doc)'), False)
    def test_not_evidence_039(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_check_with_remittance_url(doc)'), False)
    def test_not_evidence_040(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_bank_statement_document(doc)'), False)
    def test_not_evidence_041(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_bank_statement_document_url(doc)'), False)
    def test_not_evidence_042(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_bussines_card_document(doc)'), False)
    def test_not_evidence_043(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.classify_document(doc)'), False)
    def test_not_evidence_044(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.get_w2s(doc)'), False)
    def test_not_evidence_045(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.get_w2(doc)'), False)
    def test_not_evidence_046(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.delete_w2(doc)'), False)
    def test_not_evidence_047(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.get_w9s(doc)'), False)
    def test_not_evidence_048(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.get_w9(doc)'), False)
    def test_not_evidence_049(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.delete_w9(doc)'), False)
    def test_not_evidence_050(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.get_w8s(doc)'), False)
    def test_not_evidence_051(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.get_w8(doc)'), False)
    def test_not_evidence_052(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.delete_w8(doc)'), False)
    def test_not_evidence_053(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.get_bank_statements(doc)'), False)
    def test_not_evidence_054(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.get_checks(doc)'), False)
    def test_not_evidence_055(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_pay_stub(doc)'), False)
    def test_not_evidence_056(self):
            self.assertEqual(evidence('import veryfi\nc=veryfi.Client()\nc.process_payslip(doc)'), False)
    def test_not_evidence_057(self):
            self.assertEqual(evidence('textract.analyze_document(doc)'), False)
    def test_not_evidence_058(self):
            self.assertEqual(evidence('textract.analyze_expense(doc)'), False)
    def test_not_evidence_059(self):
            self.assertEqual(evidence('textract.start_document_analysis(doc)'), False)
    def test_not_evidence_060(self):
            self.assertEqual(evidence('textract.get_expense_analysis(doc)'), False)
    def test_not_evidence_061(self):
            self.assertEqual(evidence('pdfplumber.extract_text(doc)'), False)
    def test_not_evidence_062(self):
            self.assertEqual(evidence('pdfplumber.extract_table(doc)'), False)
    def test_not_evidence_063(self):
            self.assertEqual(evidence('pdfplumber.extract_tables(doc)'), False)
    def test_not_evidence_064(self):
            self.assertEqual(evidence('pdfplumber.find_table(doc)'), False)
    def test_not_evidence_065(self):
            self.assertEqual(evidence('pdfplumber.find_tables(doc)'), False)
    def test_not_evidence_066(self):
            self.assertEqual(evidence('fitz.extract_text(doc)'), False)
    def test_not_evidence_067(self):
            self.assertEqual(evidence('fitz.find_tables(doc)'), False)
    def test_not_evidence_068(self):
            self.assertEqual(evidence('pypdf.extract_text(doc)'), False)
    def test_not_evidence_069(self):
            self.assertEqual(evidence('PyPDF2.extract_text(doc)'), False)
    def test_not_evidence_070(self):
            self.assertEqual(evidence('pdfminer.extract_text(doc)'), False)
    def test_not_evidence_071(self):
            self.assertEqual(evidence('pytesseract.image_to_string(doc)'), False)
    def test_not_evidence_072(self):
            self.assertEqual(evidence('pandas.read_csv(doc)'), False)
    def test_not_evidence_073(self):
            self.assertEqual(evidence('pandas.read_excel(doc)'), False)
    def test_not_evidence_074(self):
            self.assertEqual(evidence('camelot.read_pdf(doc)'), False)
    def test_not_evidence_075(self):
            self.assertEqual(evidence('tabula.read_pdf(doc)'), False)
    def test_not_evidence_076(self):
            self.assertEqual(evidence('tabula.convert_into(doc)'), False)
    def test_not_evidence_077(self):
            self.assertEqual(evidence('re.search("gross", text)\nre.findall("net", text)\nfields={"net": 1}'), False)
    def test_not_evidence_078(self):
            self.assertEqual(evidence('text="health insurance card"\nfields=text.split()'), False)
    def test_not_evidence_079(self):
            self.assertEqual(evidence('subprocess.run(["mindee", "parse", "doc"])'), False)
    def test_not_evidence_080(self):
            self.assertEqual(evidence('subprocess.run(["veryfi", "process", "doc"])'), False)
    def test_not_evidence_081(self):
            self.assertEqual(evidence('import mindee as m\nc=m.Client()\nc.parse(HealthcareCardV1, doc)'), False)
    def test_not_evidence_082(self):
            self.assertEqual(evidence('from engine import extract_health_insurance_card as op\ndef extract_health_insurance_card(): pass\nop(doc)'), False)
    def test_route_000(self):
        self.assertTrue(evidence('x.extract_health_insurance_card(doc)'))
    def test_route_001(self):
        self.assertTrue(evidence('from engine import extract_health_insurance_card as operation\noperation(doc)'))
    def test_route_002(self):
        self.assertTrue(evidence('x.extract_health_insurance_cards(doc)'))
    def test_route_003(self):
        self.assertTrue(evidence('from engine import extract_health_insurance_cards as operation\noperation(doc)'))
    def test_route_004(self):
        self.assertTrue(evidence('x.parse_health_insurance_card(doc)'))
    def test_route_005(self):
        self.assertTrue(evidence('from engine import parse_health_insurance_card as operation\noperation(doc)'))
    def test_route_006(self):
        self.assertTrue(evidence('x.parse_health_insurance_cards(doc)'))
    def test_route_007(self):
        self.assertTrue(evidence('from engine import parse_health_insurance_cards as operation\noperation(doc)'))
    def test_route_008(self):
        self.assertTrue(evidence('x.extract_health_card(doc)'))
    def test_route_009(self):
        self.assertTrue(evidence('from engine import extract_health_card as operation\noperation(doc)'))
    def test_route_010(self):
        self.assertTrue(evidence('x.extract_health_cards(doc)'))
    def test_route_011(self):
        self.assertTrue(evidence('from engine import extract_health_cards as operation\noperation(doc)'))
    def test_route_012(self):
        self.assertTrue(evidence('x.parse_health_card(doc)'))
    def test_route_013(self):
        self.assertTrue(evidence('from engine import parse_health_card as operation\noperation(doc)'))
    def test_route_014(self):
        self.assertTrue(evidence('x.parse_health_cards(doc)'))
    def test_route_015(self):
        self.assertTrue(evidence('from engine import parse_health_cards as operation\noperation(doc)'))
    def test_route_016(self):
        self.assertTrue(evidence('x.extract_insurance_card(doc)'))
    def test_route_017(self):
        self.assertTrue(evidence('from engine import extract_insurance_card as operation\noperation(doc)'))
    def test_route_018(self):
        self.assertTrue(evidence('x.extract_insurance_cards(doc)'))
    def test_route_019(self):
        self.assertTrue(evidence('from engine import extract_insurance_cards as operation\noperation(doc)'))
    def test_route_020(self):
        self.assertTrue(evidence('x.parse_insurance_card(doc)'))
    def test_route_021(self):
        self.assertTrue(evidence('from engine import parse_insurance_card as operation\noperation(doc)'))
    def test_route_022(self):
        self.assertTrue(evidence('x.parse_insurance_cards(doc)'))
    def test_route_023(self):
        self.assertTrue(evidence('from engine import parse_insurance_cards as operation\noperation(doc)'))
    def test_route_024(self):
        self.assertTrue(evidence('x.extract_medical_insurance_card(doc)'))
    def test_route_025(self):
        self.assertTrue(evidence('from engine import extract_medical_insurance_card as operation\noperation(doc)'))
    def test_route_026(self):
        self.assertTrue(evidence('x.extract_medical_insurance_cards(doc)'))
    def test_route_027(self):
        self.assertTrue(evidence('from engine import extract_medical_insurance_cards as operation\noperation(doc)'))
    def test_route_028(self):
        self.assertTrue(evidence('x.parse_medical_insurance_card(doc)'))
    def test_route_029(self):
        self.assertTrue(evidence('from engine import parse_medical_insurance_card as operation\noperation(doc)'))
    def test_route_030(self):
        self.assertTrue(evidence('x.parse_medical_insurance_cards(doc)'))
    def test_route_031(self):
        self.assertTrue(evidence('from engine import parse_medical_insurance_cards as operation\noperation(doc)'))
    def test_route_032(self):
        self.assertTrue(evidence('x.extract_health_insurance_card_data(doc)'))
    def test_route_033(self):
        self.assertTrue(evidence('from engine import extract_health_insurance_card_data as operation\noperation(doc)'))
    def test_route_034(self):
        self.assertTrue(evidence('x.parse_health_insurance_card_data(doc)'))
    def test_route_035(self):
        self.assertTrue(evidence('from engine import parse_health_insurance_card_data as operation\noperation(doc)'))
    def test_route_036(self):
        self.assertTrue(evidence('x.health_insurance_card_extraction(doc)'))
    def test_route_037(self):
        self.assertTrue(evidence('from engine import health_insurance_card_extraction as operation\noperation(doc)'))
    def test_route_038(self):
        self.assertTrue(evidence('x.health_insurance_card_extractor(doc)'))
    def test_route_039(self):
        self.assertTrue(evidence('from engine import health_insurance_card_extractor as operation\noperation(doc)'))
    def test_route_040(self):
        self.assertTrue(evidence('x.health_insurance_card_parser(doc)'))
    def test_route_041(self):
        self.assertTrue(evidence('from engine import health_insurance_card_parser as operation\noperation(doc)'))
    def test_route_042(self):
        self.assertTrue(evidence('x.insurance_card_extraction(doc)'))
    def test_route_043(self):
        self.assertTrue(evidence('from engine import insurance_card_extraction as operation\noperation(doc)'))
    def test_route_044(self):
        self.assertTrue(evidence('x.extract_health_card_data(doc)'))
    def test_route_045(self):
        self.assertTrue(evidence('from engine import extract_health_card_data as operation\noperation(doc)'))
    def test_route_046(self):
        self.assertTrue(evidence('x.parse_health_card_data(doc)'))
    def test_route_047(self):
        self.assertTrue(evidence('from engine import parse_health_card_data as operation\noperation(doc)'))
    def test_route_048(self):
        self.assertTrue(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-healthInsuranceCard.us', doc)"))
    def test_route_049(self):
        self.assertTrue(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document_from_url('prebuilt-healthInsuranceCard.us', url)"))
    def test_route_050(self):
        self.assertTrue(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document(model_id='prebuilt-healthInsuranceCard.us', body=doc)"))
    def test_route_051(self):
        self.assertTrue(evidence("import azure.ai.formrecognizer as az\nc=az.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-healthInsuranceCard.us', doc)"))
    def test_route_052(self):
        self.assertTrue(evidence("import azure.ai.formrecognizer as az\nc=az.DocumentAnalysisClient()\nc.begin_analyze_document_from_url('prebuilt-healthInsuranceCard.us', url)"))
    def test_route_053(self):
        self.assertTrue(evidence("import azure.ai.formrecognizer as az\nc=az.DocumentAnalysisClient()\nc.begin_analyze_document(model_id='prebuilt-healthInsuranceCard.us', body=doc)"))
    def test_route_054(self):
        self.assertTrue(evidence("from azure.ai.formrecognizer import DocumentAnalysisClient as C\nc=C()\nc.begin_analyze_document('prebuilt-healthInsuranceCard.us', doc)"))
    def test_route_055(self):
        self.assertTrue(evidence("from azure.ai.formrecognizer import DocumentAnalysisClient as C\nc=C()\nc.begin_analyze_document_from_url('prebuilt-healthInsuranceCard.us', url)"))
    def test_route_056(self):
        self.assertTrue(evidence("from azure.ai.formrecognizer import DocumentAnalysisClient as C\nc=C()\nc.begin_analyze_document(model_id='prebuilt-healthInsuranceCard.us', body=doc)"))
    def test_route_057(self):
        self.assertTrue(evidence("import azure.ai.documentintelligence\nc=azure.ai.documentintelligence.DocumentIntelligenceClient()\nc.begin_analyze_document('prebuilt-healthInsuranceCard.us', doc)"))
    def test_route_058(self):
        self.assertTrue(evidence("import azure.ai.documentintelligence\nc=azure.ai.documentintelligence.DocumentIntelligenceClient()\nc.begin_analyze_document_from_url('prebuilt-healthInsuranceCard.us', url)"))
    def test_route_059(self):
        self.assertTrue(evidence("import azure.ai.documentintelligence\nc=azure.ai.documentintelligence.DocumentIntelligenceClient()\nc.begin_analyze_document(model_id='prebuilt-healthInsuranceCard.us', body=doc)"))
    def test_route_060(self):
        self.assertTrue(evidence("import azure.ai.documentintelligence as az\nc=az.DocumentIntelligenceClient()\nc.begin_analyze_document('prebuilt-healthInsuranceCard.us', doc)"))
    def test_route_061(self):
        self.assertTrue(evidence("import azure.ai.documentintelligence as az\nc=az.DocumentIntelligenceClient()\nc.begin_analyze_document_from_url('prebuilt-healthInsuranceCard.us', url)"))
    def test_route_062(self):
        self.assertTrue(evidence("import azure.ai.documentintelligence as az\nc=az.DocumentIntelligenceClient()\nc.begin_analyze_document(model_id='prebuilt-healthInsuranceCard.us', body=doc)"))
    def test_route_063(self):
        self.assertTrue(evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nc=C()\nc.begin_analyze_document('prebuilt-healthInsuranceCard.us', doc)"))
    def test_route_064(self):
        self.assertTrue(evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nc=C()\nc.begin_analyze_document_from_url('prebuilt-healthInsuranceCard.us', url)"))
    def test_route_065(self):
        self.assertTrue(evidence("from azure.ai.documentintelligence import DocumentIntelligenceClient as C\nc=C()\nc.begin_analyze_document(model_id='prebuilt-healthInsuranceCard.us', body=doc)"))
    def test_route_066(self):
        self.assertTrue(evidence('import mindee\nc=mindee.Client()\nc.parse(HealthcareCardV1, doc)'))
    def test_route_067(self):
        self.assertTrue(evidence('import mindee\nc=mindee.Client()\nc.parse(product=HealthcareCardV1, document=doc)'))
    def test_route_068(self):
        self.assertTrue(evidence('import mindee\nc=mindee.Client()\nc.parse(product.us.HealthcareCardV1, doc)'))
    def test_route_069(self):
        self.assertTrue(evidence('import mindee\nc=mindee.Client()\nc.parse(product=product.us.HealthcareCardV1, document=doc)'))
    def test_route_070(self):
        self.assertTrue(evidence('import mindee\nc=mindee.Client()\nc.parse(mindee.product.us.HealthcareCardV1, doc)'))
    def test_route_071(self):
        self.assertTrue(evidence('import mindee\nc=mindee.Client()\nc.parse(product=mindee.product.us.HealthcareCardV1, document=doc)'))
    def test_route_072(self):
        self.assertTrue(evidence('from mindee import Client as C\nc=C()\nc.parse(HealthcareCardV1, doc)'))
    def test_route_073(self):
        self.assertTrue(evidence('from mindee import Client as C\nc=C()\nc.parse(product=HealthcareCardV1, document=doc)'))
    def test_route_074(self):
        self.assertTrue(evidence('from mindee import Client as C\nc=C()\nc.parse(product.us.HealthcareCardV1, doc)'))
    def test_route_075(self):
        self.assertTrue(evidence('from mindee import Client as C\nc=C()\nc.parse(product=product.us.HealthcareCardV1, document=doc)'))
    def test_route_076(self):
        self.assertTrue(evidence('from mindee import Client as C\nc=C()\nc.parse(mindee.product.us.HealthcareCardV1, doc)'))
    def test_route_077(self):
        self.assertTrue(evidence('from mindee import Client as C\nc=C()\nc.parse(product=mindee.product.us.HealthcareCardV1, document=doc)'))
    def test_extra_negative_000(self):
        self.assertFalse(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-payStub.us')"))
    def test_extra_negative_001(self):
        self.assertFalse(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-healthInsuranceCard')"))
    def test_extra_negative_002(self):
        self.assertFalse(evidence("import azure.ai.formrecognizer\nc=azure.ai.formrecognizer.DocumentAnalysisClient()\nc.begin_analyze_document('prebuilt-healthinsurancecard.us')"))
    def test_extra_negative_003(self):
        self.assertFalse(evidence('import mindee\nc=mindee.Client()\nc.parse(PayslipV2,doc)'))
    def test_extra_negative_004(self):
        self.assertFalse(evidence('import mindee\nc=mindee.Client()\nc.parse(PayslipV3,doc)'))
    def test_extra_negative_005(self):
        self.assertFalse(evidence('import mindee\nc=mindee.Client()\nc.parse(HealthcareCardV2,doc)'))
    def test_extra_negative_006(self):
        self.assertFalse(evidence('import mindee\nc=mindee.Client()\nc.parse(TypeHealthcareCard,doc)'))
    def test_extra_negative_007(self):
        self.assertFalse(evidence('x.process_health_insurance_card(doc)'))
    def test_extra_negative_008(self):
        self.assertFalse(evidence('x.process_health_card(doc)'))
    def test_extra_negative_009(self):
        self.assertFalse(evidence('x.process_insurance_card(doc)'))
    def test_extra_negative_010(self):
        self.assertFalse(evidence('extract_health_insurance_card(doc)'))
    def test_extra_negative_011(self):
        self.assertFalse(evidence('x.extract_health_insurance_card'))
    def test_extra_negative_012(self):
        self.assertFalse(evidence('"extract health insurance cards"'))
    def test_extra_negative_013(self):
        self.assertFalse(evidence('# x.extract_health_insurance_card(doc)'))
    def test_extra_negative_014(self):
        self.assertFalse(evidence('def broken('))
    def test_bindings(self):
        for binding in ['C = other', 'C: object = other', 'with manager() as C: pass', 'async def f():\n    async with manager() as C: pass']:
            with self.subTest(binding=binding):
                self.assertFalse(evidence('from mindee import Client as C\n'+binding+'\nc=C()\nc.parse(HealthcareCardV1,doc)'))
    def test_local_definitions(self):
        for definition in ['def extract_health_insurance_card(): pass', 'class extract_health_insurance_card: pass', 'class X:\n    def extract_health_insurance_card(self): pass']:
            self.assertFalse(evidence(definition+'\nx.extract_health_insurance_card(doc)'))
    def test_source_locations(self):
        self.put('README.md', 'extract health insurance cards')
        for name in ['fixtures/a.py', 'docs/a.py', 'examples/a.py']:
            self.put(name, 'x.extract_health_insurance_card(doc)')
        self.assertEqual(audit(self.root)['test_evidence'], [])
        self.assertEqual(self.cli()[0], 2)
        for name in ['test_app.py', 'app_test.py', 'nested/tests/a.py']:
            self.put(name, 'x.extract_health_insurance_card(doc)')
        self.assertEqual(len(audit(self.root)['test_evidence']), 3)
        self.assertEqual(audit(self.root)['findings'][0]['severity'], 'MEDIUM')
    def test_no_source(self):
        self.put('README.md', 'extract health insurance cards')
        self.assertEqual(self.cli()[0], 2)
        self.put('README.md', 'does not extract health insurance cards')
        self.assertEqual(self.cli()[0], 0)

if __name__ == '__main__':
    unittest.main()
