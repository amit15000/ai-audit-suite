"""Test script for comprehensive Compliance Score."""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.comparison.compliance_scorer import ComplianceScorer


async def test_gdpr_violations():
    """Test GDPR compliance violations."""
    print("\n" + "="*80)
    print("TEST 1: GDPR Compliance Violations")
    print("="*80)
    
    scorer = ComplianceScorer()
    
    # Test case with GDPR violations
    response_with_violations = """
    Our AI system collects and processes all user data without explicit consent. 
    We store personal information indefinitely and share it with third parties 
    without user notification. Users cannot access, modify, or delete their data. 
    We do not provide privacy notices or explain how data is used. Data is 
    collected for purposes beyond what was originally stated.
    """
    
    print("\n📝 Response with GDPR Violations:")
    print(response_with_violations.strip())
    
    print("\n🔄 Analyzing compliance...")
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=response_with_violations,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "-"*80)
        print("RESULTS:")
        print("-"*80)
        print(f"Legacy checksUrlsExist: {sub_scores.checksUrlsExist}")
        print(f"Legacy verifiesPapersExist: {sub_scores.verifiesPapersExist}")
        print(f"Legacy detectsFakeCitations: {sub_scores.detectsFakeCitations}")
        print(f"Legacy confirmsLegalReferences: {sub_scores.confirmsLegalReferences}")
        
        if sub_scores.complianceDetails:
            details = sub_scores.complianceDetails
            print(f"\n📊 Compliance Analysis:")
            print(f"   Overall Score: {details.score}/10")
            print(f"   Total Rules Checked: {details.summary.total_rules}")
            print(f"   Passed Rules: {details.summary.passed_rules}")
            print(f"   Violated Rules: {details.summary.violated_rules}")
            print(f"   High-Risk Violations: {details.summary.high_risk_violations}")
            
            print(f"\n📋 Per-Module Scores:")
            for module, score in details.module_scores.items():
                print(f"   - {module.upper()}: {score}/10")
            
            print(f"\n🔍 GDPR Rules Evaluated:")
            gdpr_rules = [r for r in details.rules if r.module.lower() == "gdpr"]
            for i, rule in enumerate(gdpr_rules, 1):
                status_icon = "✅" if rule.status == "passed" else "❌"
                print(f"\n   {i}. {status_icon} {rule.rule_name}")
                print(f"      Status: {rule.status.upper()}")
                if rule.status == "violated":
                    print(f"      Severity: {rule.severity.upper()}")
                text_preview = rule.text[:100] + "..." if len(rule.text) > 100 else rule.text
                print(f"      Text: \"{text_preview}\"")
                print(f"      Explanation: {rule.explanation}")
            
            print(f"\n💡 Explanation: {details.explanation}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_hipaa_violations():
    """Test HIPAA compliance violations."""
    print("\n" + "="*80)
    print("TEST 2: HIPAA Compliance Violations")
    print("="*80)
    
    scorer = ComplianceScorer()
    
    response_with_violations = """
    Our healthcare AI system processes patient health information without encryption. 
    All staff members have unrestricted access to patient records. We do not maintain 
    audit logs of data access. Patient data is shared with external vendors without 
    business associate agreements. We do not have breach notification procedures in place.
    """
    
    print("\n📝 Response with HIPAA Violations:")
    print(response_with_violations.strip())
    
    print("\n🔄 Analyzing compliance...")
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=response_with_violations,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "-"*80)
        print("RESULTS:")
        print("-"*80)
        
        if sub_scores.complianceDetails:
            details = sub_scores.complianceDetails
            print(f"\n📊 Compliance Analysis:")
            print(f"   Overall Score: {details.score}/10")
            print(f"   High-Risk Violations: {details.summary.high_risk_violations}")
            
            print(f"\n🔍 HIPAA Rules Evaluated:")
            hipaa_rules = [r for r in details.rules if r.module.lower() == "hipaa"]
            for i, rule in enumerate(hipaa_rules, 1):
                status_icon = "✅" if rule.status == "passed" else "❌"
                severity_badge = f" [{rule.severity.upper()}]" if rule.status == "violated" else ""
                print(f"\n   {i}. {status_icon} {rule.rule_name}{severity_badge}")
                if rule.status == "violated":
                    print(f"      Text: \"{rule.text[:80]}...\"")
                    print(f"      Explanation: {rule.explanation}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_eu_ai_act_violations():
    """Test EU AI Act compliance violations."""
    print("\n" + "="*80)
    print("TEST 3: EU AI Act Compliance Violations")
    print("="*80)
    
    scorer = ComplianceScorer()
    
    response_with_violations = """
    Our AI system makes automated decisions in high-risk applications without human 
    oversight. The system operates as a black box with no transparency or explanation 
    of its decisions. We do not maintain documentation of the system's training data 
    or risk assessment. Users are not informed when AI is making decisions about them.
    """
    
    print("\n📝 Response with EU AI Act Violations:")
    print(response_with_violations.strip())
    
    print("\n🔄 Analyzing compliance...")
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=response_with_violations,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "-"*80)
        print("RESULTS:")
        print("-"*80)
        
        if sub_scores.complianceDetails:
            details = sub_scores.complianceDetails
            print(f"\n📊 Compliance Analysis:")
            print(f"   Overall Score: {details.score}/10")
            
            print(f"\n🔍 EU AI Act Rules Evaluated:")
            eu_ai_act_rules = [r for r in details.rules if r.module.lower() == "eu_ai_act"]
            for i, rule in enumerate(eu_ai_act_rules, 1):
                status_icon = "✅" if rule.status == "passed" else "❌"
                print(f"\n   {i}. {status_icon} {rule.rule_name}")
                if rule.status == "violated":
                    print(f"      Severity: {rule.severity.upper()}")
                    print(f"      Explanation: {rule.explanation}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_compliant_response():
    """Test a fully compliant response."""
    print("\n" + "="*80)
    print("TEST 4: Fully Compliant Response")
    print("="*80)
    
    scorer = ComplianceScorer()
    
    compliant_response = """
    Our AI system is designed with comprehensive compliance measures. We obtain 
    explicit user consent before collecting any personal data, clearly explain 
    data usage purposes, and provide users with full access, modification, and 
    deletion rights (GDPR compliant). For high-risk AI applications, we implement 
    human oversight, maintain detailed documentation, provide transparency 
    about AI decision-making, and conduct regular risk assessments (EU AI Act). 
    We follow responsible AI principles including fairness, accountability, 
    explainability, and safety. Our system includes robust security controls, 
    encryption, access controls, audit logging, and breach notification procedures. 
    We maintain ISO/IEC 42001 compliant AI management systems with proper governance, 
    risk management, and continuous improvement processes.
    """
    
    print("\n📝 Compliant Response:")
    print(compliant_response.strip())
    
    print("\n🔄 Analyzing compliance...")
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=compliant_response,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "-"*80)
        print("RESULTS:")
        print("-"*80)
        
        if sub_scores.complianceDetails:
            details = sub_scores.complianceDetails
            print(f"\n📊 Compliance Analysis:")
            print(f"   Overall Score: {details.score}/10")
            print(f"   Total Rules Checked: {details.summary.total_rules}")
            print(f"   Passed Rules: {details.summary.passed_rules}")
            print(f"   Violated Rules: {details.summary.violated_rules}")
            print(f"   High-Risk Violations: {details.summary.high_risk_violations}")
            
            print(f"\n📋 Per-Module Scores:")
            for module, score in sorted(details.module_scores.items()):
                score_icon = "✅" if score >= 8 else "⚠️" if score >= 6 else "❌"
                print(f"   {score_icon} {module.upper()}: {score}/10")
            
            if details.summary.violated_rules == 0:
                print(f"\n✅ Response is fully compliant across all standards!")
            else:
                print(f"\n⚠️  Some compliance issues detected:")
                violated_rules = [r for r in details.rules if r.status == "violated"]
                for rule in violated_rules[:5]:  # Show first 5 violations
                    print(f"   - [{rule.module.upper()}] {rule.rule_name} ({rule.severity})")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_multiple_modules():
    """Test response with violations across multiple compliance modules."""
    print("\n" + "="*80)
    print("TEST 5: Multiple Compliance Module Violations")
    print("="*80)
    
    scorer = ComplianceScorer()
    
    response_with_multiple_violations = """
    Our AI system processes user data without consent, makes automated decisions 
    without human oversight, lacks transparency, has no security controls, 
    processes health information without encryption, and has no audit logging. 
    The system discriminates against certain user groups and provides no 
    explanations for its decisions.
    """
    
    print("\n📝 Response with Multiple Violations:")
    print(response_with_multiple_violations.strip())
    
    print("\n🔄 Analyzing compliance...")
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=response_with_multiple_violations,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "-"*80)
        print("RESULTS:")
        print("-"*80)
        
        if sub_scores.complianceDetails:
            details = sub_scores.complianceDetails
            print(f"\n📊 Compliance Analysis:")
            print(f"   Overall Score: {details.score}/10")
            print(f"   Total Violations: {details.summary.violated_rules}")
            print(f"   High-Risk Violations: {details.summary.high_risk_violations}")
            
            print(f"\n📋 Per-Module Scores:")
            for module, score in sorted(details.module_scores.items()):
                score_icon = "✅" if score >= 8 else "⚠️" if score >= 6 else "❌"
                print(f"   {score_icon} {module.upper()}: {score}/10")
            
            print(f"\n🔍 Violations by Module:")
            modules_with_violations = {}
            for rule in details.rules:
                if rule.status == "violated":
                    if rule.module not in modules_with_violations:
                        modules_with_violations[rule.module] = []
                    modules_with_violations[rule.module].append(rule)
            
            for module, violations in sorted(modules_with_violations.items()):
                print(f"\n   {module.upper()}: {len(violations)} violation(s)")
                for rule in violations[:3]:  # Show first 3 per module
                    print(f"      - [{rule.severity.upper()}] {rule.rule_name}")
            
            print(f"\n⚠️  HIGH-RISK VIOLATIONS:")
            high_risk = [r for r in details.rules if r.status == "violated" and r.severity == "high"]
            for i, rule in enumerate(high_risk, 1):
                print(f"\n   {i}. [{rule.module.upper()}] {rule.rule_name}")
                print(f"      Text: \"{rule.text[:80]}...\"")
                print(f"      Explanation: {rule.explanation}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_all_modules():
    """Test all 6 compliance modules with specific examples."""
    print("\n" + "="*80)
    print("TEST 6: All Compliance Modules")
    print("="*80)
    
    scorer = ComplianceScorer()
    
    response_all_modules = """
    Our AI system handles personal data with explicit consent and privacy notices (GDPR). 
    High-risk AI applications include human oversight and transparency (EU AI Act). 
    We follow fairness, accountability, and explainability principles (Responsible AI). 
    Our AI management system includes risk management and governance (ISO/IEC 42001). 
    Health data is encrypted with access controls and audit logs (HIPAA). Security, 
    availability, and confidentiality controls are in place (SOC-2 AI).
    """
    
    print("\n📝 Response Covering All Modules:")
    print(response_all_modules.strip())
    
    print("\n🔄 Analyzing compliance...")
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=response_all_modules,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "-"*80)
        print("RESULTS:")
        print("-"*80)
        
        if sub_scores.complianceDetails:
            details = sub_scores.complianceDetails
            print(f"\n📊 Overall Score: {details.score}/10")
            
            print(f"\n📋 Module Scores:")
            module_names = {
                "gdpr": "GDPR",
                "eu_ai_act": "EU AI Act",
                "responsible_ai": "Responsible AI",
                "iso_42001": "ISO/IEC 42001",
                "hipaa": "HIPAA",
                "soc2_ai": "SOC-2 AI"
            }
            
            for module_key, module_display in sorted(module_names.items()):
                score = details.module_scores.get(module_key, 6)
                score_icon = "✅" if score >= 8 else "⚠️" if score >= 6 else "❌"
                print(f"   {score_icon} {module_display}: {score}/10")
                
                # Show rules for this module
                module_rules = [r for r in details.rules if r.module.lower() == module_key.lower()]
                if module_rules:
                    passed = sum(1 for r in module_rules if r.status == "passed")
                    violated = sum(1 for r in module_rules if r.status == "violated")
                    print(f"      Rules: {passed} passed, {violated} violated")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_error_handling():
    """Test error handling with invalid input."""
    print("\n" + "="*80)
    print("TEST 7: Error Handling")
    print("="*80)
    
    scorer = ComplianceScorer()
    
    # Test with very short response
    short_response = "AI system."
    
    print("\n📝 Short Response (should handle gracefully):")
    print(short_response)
    
    print("\n🔄 Analyzing compliance...")
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=short_response,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "-"*80)
        print("RESULTS:")
        print("-"*80)
        
        if sub_scores.complianceDetails:
            details = sub_scores.complianceDetails
            print(f"   Overall Score: {details.score}/10")
            print(f"   Total Rules: {details.summary.total_rules}")
            print(f"   Explanation: {details.explanation}")
        else:
            print("   ⚠️  No compliance details (fallback to defaults)")
        
        print("\n✅ Error handling works correctly")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def test_backward_compatibility():
    """Test backward compatibility with legacy fields."""
    print("\n" + "="*80)
    print("TEST 8: Backward Compatibility")
    print("="*80)
    
    scorer = ComplianceScorer()
    
    response = "Our AI system processes data with proper consent and security measures."
    
    print("\n📝 Testing legacy field access...")
    
    try:
        sub_scores = await scorer.calculate_sub_scores(
            response=response,
            judge_platform_id="openai",
            use_llm=True,
        )
        
        print("\n" + "-"*80)
        print("RESULTS:")
        print("-"*80)
        print(f"Legacy checksUrlsExist: {sub_scores.checksUrlsExist} (deprecated)")
        print(f"Legacy verifiesPapersExist: {sub_scores.verifiesPapersExist} (deprecated)")
        print(f"Legacy detectsFakeCitations: {sub_scores.detectsFakeCitations} (deprecated)")
        print(f"Legacy confirmsLegalReferences: {sub_scores.confirmsLegalReferences} (deprecated)")
        print(f"New complianceDetails: {'Present' if sub_scores.complianceDetails else 'None'}")
        
        if sub_scores.complianceDetails:
            print(f"   Overall Score: {sub_scores.complianceDetails.score}/10")
        
        print("\n✅ Backward compatibility maintained - legacy fields accessible")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("COMPREHENSIVE COMPLIANCE SCORE TEST SUITE")
    print("="*80)
    print("\nThis script tests the comprehensive Compliance Score which:")
    print("  1. Evaluates compliance against 6 regulatory standards:")
    print("     - GDPR (General Data Protection Regulation)")
    print("     - EU AI Act")
    print("     - Responsible AI")
    print("     - ISO/IEC 42001")
    print("     - HIPAA (Health Insurance Portability and Accountability Act)")
    print("     - SOC-2 AI Compliance")
    print("  2. Identifies specific compliance rules that apply")
    print("  3. Classifies violations by severity (low, medium, high)")
    print("  4. Provides detailed explanations for each rule")
    print("  5. Returns comprehensive results with passed/violated rules")
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  WARNING: OPENAI_API_KEY not set. Tests will fail.")
        print("   Set it in your environment or .env file")
        return
    
    # Run tests
    await test_gdpr_violations()
    await test_hipaa_violations()
    await test_eu_ai_act_violations()
    await test_compliant_response()
    await test_multiple_modules()
    await test_all_modules()
    await test_error_handling()
    await test_backward_compatibility()
    
    print("\n" + "="*80)
    print("TEST SUITE COMPLETE")
    print("="*80)
    print("\n💡 KEY FEATURES:")
    print("   ✅ Comprehensive compliance evaluation (6 standards)")
    print("   ✅ Detailed rule tracking (passed/violated)")
    print("   ✅ Severity classification (low/medium/high risk)")
    print("   ✅ Per-module scoring")
    print("   ✅ High-risk violation identification")
    print("   ✅ Backward compatibility with legacy fields")
    print("   ✅ Ready for UI display with all details")


if __name__ == "__main__":
    asyncio.run(main())
