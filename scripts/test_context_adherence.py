"""Comprehensive test script for Context-Adherence Score with realistic test cases.

This script tests the Context-Adherence Score system with various real-world scenarios
to evaluate how well AI responses adhere to user instructions, tone requirements,
length constraints, format rules, and brand voice guidelines.

Test Categories:
- Marketing content (emails, social media, ads)
- Technical documentation
- Customer service responses
- Creative content
- Business communications
- Edge cases and error scenarios
"""
import asyncio
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import adapters to register them
from app.adapters import openai as _openai_adapter  # noqa: F401
from app.adapters import gemini as _gemini_adapter  # noqa: F401
from app.adapters import groq as _groq_adapter  # noqa: F401
from app.adapters import huggingface as _huggingface_adapter  # noqa: F401

from app.services.comparison.context_adherence_scorer import ContextAdherenceScorer
from app.services.comparison.context_adherence.prompt_parser import PromptParser


@dataclass
class TestResult:
    """Container for test case results."""
    test_name: str
    overall_score: float
    all_instructions: float
    tone_of_voice: str
    length_constraints: str
    format_rules: float
    brand_voice: float
    passed: bool
    error: Optional[str] = None


class TestRunner:
    """Test runner for context adherence scoring."""
    
    def __init__(self):
        """Initialize test runner."""
        self.scorer = ContextAdherenceScorer()
        self.parser = PromptParser(self.scorer.ai_service)
        self.results: list[TestResult] = []
    
    def _get_emoji(self, score: float, is_percentage: bool = True) -> str:
        """Get emoji indicator for score.
        
        Args:
            score: Score value
            is_percentage: Whether score is a percentage (0-100)
            
        Returns:
            Emoji string
        """
        if is_percentage:
            if score >= 90:
                return "✅"
            elif score >= 70:
                return "🟢"
            elif score >= 50:
                return "🟡"
            elif score >= 30:
                return "🟠"
            else:
                return "🔴"
        return "📊"
    
    def _get_adherence_level(self, score: float) -> str:
        """Get adherence level description.
        
        Args:
            score: Overall adherence score
            
        Returns:
            Adherence level string
        """
        if score >= 90:
            return "✅ EXCELLENT ADHERENCE"
        elif score >= 70:
            return "🟢 GOOD ADHERENCE"
        elif score >= 50:
            return "🟡 MODERATE ADHERENCE"
        elif score >= 30:
            return "🟠 POOR ADHERENCE"
        else:
            return "🔴 VERY POOR ADHERENCE"
    
    async def run_test_case(
        self,
        test_name: str,
        prompt: str,
        response: str,
        expected_high_adherence: bool = True,
        show_parsed_prompt: bool = True,
    ) -> TestResult:
        """Run a single test case.
        
        Args:
            test_name: Name of the test case
            prompt: User prompt/instructions
            response: AI-generated response
            expected_high_adherence: Whether high adherence is expected
            show_parsed_prompt: Whether to display parsed prompt details
            
        Returns:
            TestResult object
        """
        print("\n" + "="*80)
        print(f"TEST CASE: {test_name}")
        print("="*80)
        
        print("\n📋 USER PROMPT:")
        print("-" * 80)
        print(prompt.strip())
        print("-" * 80)
        
        print("\n📝 AI RESPONSE:")
        print("-" * 80)
        print(response.strip())
        print("-" * 80)
        
        # Parse prompt
        parsed_prompt = None
        if show_parsed_prompt:
            print("\n🔍 Parsing prompt requirements...")
            try:
                parsed_prompt = await self.parser.parse_prompt(
                    prompt=prompt,
                    judge_platform_id="openai",
                    use_llm=True,
                )
                
                self._display_parsed_prompt(parsed_prompt)
            except Exception as e:
                print(f"\n  ⚠️  Error parsing prompt: {str(e)}")
        
        # Calculate scores
        print("\n🔄 Analyzing response adherence...")
        print("   (This may take 15-30 seconds depending on API response time)")
        print("   Progress: Starting analysis...")
        
        start_time = time.time()
        try:
            # Add timeout (120 seconds max)
            import asyncio
            
            try:
                sub_scores = await asyncio.wait_for(
                    self.scorer.calculate_sub_scores(
                        response=response,
                        prompt=prompt,
                        judge_platform_id="openai",
                        use_llm=True,
                    ),
                    timeout=120.0
                )
            except asyncio.TimeoutError:
                raise TimeoutError(
                    "Analysis timed out after 120 seconds. "
                    "This may indicate an API issue or network problem. "
                    "Please check your OpenAI API key and network connection."
                )
            
            elapsed_time = time.time() - start_time
            print(f"   ✅ Analysis completed in {elapsed_time:.2f} seconds")
            
            # Calculate overall score
            numeric_scores = [
                sub_scores.allInstructions,
                sub_scores.formatRules,
                sub_scores.brandVoice,
            ]
            overall_score = sum(numeric_scores) / len(numeric_scores)
            
            # Display results
            self._display_results(sub_scores, overall_score, elapsed_time)
            
            # Determine if test passed
            passed = False
            if expected_high_adherence:
                passed = overall_score >= 70
            else:
                passed = overall_score < 50
            
            result = TestResult(
                test_name=test_name,
                overall_score=overall_score,
                all_instructions=sub_scores.allInstructions,
                tone_of_voice=sub_scores.toneOfVoice,
                length_constraints=sub_scores.lengthConstraints,
                format_rules=sub_scores.formatRules,
                brand_voice=sub_scores.brandVoice,
                passed=passed,
            )
            
            # Display pass/fail
            if passed:
                print(f"\n  ✅ TEST PASSED: Response {'meets' if expected_high_adherence else 'correctly shows low'} expected adherence")
            else:
                print(f"\n  ⚠️  TEST WARNING: Response did not meet expected adherence level")
            
            return result
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            error_msg = str(e)
            
            print(f"\n❌ Error after {elapsed_time:.2f} seconds: {error_msg}")
            
            # Provide helpful error messages
            if "API key" in error_msg or "OPENAI_API_KEY" in error_msg:
                print("\n💡 TROUBLESHOOTING:")
                print("   1. Check that OPENAI_API_KEY is set in your environment")
                print("   2. Verify the API key is valid and has credits")
                print("   3. Try: export OPENAI_API_KEY='your-key-here' (Linux/Mac)")
                print("   4. Or: set OPENAI_API_KEY=your-key-here (Windows)")
            elif "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                print("\n💡 TROUBLESHOOTING:")
                print("   1. Check your internet connection")
                print("   2. Verify OpenAI API is accessible")
                print("   3. Check if your API key has rate limits")
                print("   4. Try running the test again")
            elif "adapter" in error_msg.lower() or "not found" in error_msg.lower():
                print("\n💡 TROUBLESHOOTING:")
                print("   1. Make sure adapters are imported at the top of the script")
                print("   2. Check that adapter modules are in the correct location")
            else:
                print("\n💡 TROUBLESHOOTING:")
                print("   1. Check the full error traceback below")
                print("   2. Verify all dependencies are installed")
                print("   3. Ensure the API key is valid")
            
            import traceback
            print("\n📋 Full Error Traceback:")
            traceback.print_exc()
            
            return TestResult(
                test_name=test_name,
                overall_score=0.0,
                all_instructions=0.0,
                tone_of_voice="Error",
                length_constraints="Error",
                format_rules=0.0,
                brand_voice=0.0,
                passed=False,
                error=error_msg,
            )
    
    def _display_parsed_prompt(self, parsed_prompt) -> None:
        """Display parsed prompt requirements.
        
        Args:
            parsed_prompt: ParsedPrompt object
        """
        print("\n" + "-"*80)
        print("PARSED PROMPT REQUIREMENTS:")
        print("-"*80)
        
        if parsed_prompt.instructions:
            print(f"\n  📌 Instructions Found ({len(parsed_prompt.instructions)}):")
            for i, inst in enumerate(parsed_prompt.instructions[:10], 1):  # Limit to 10
                print(f"     {i}. {inst}")
        else:
            print("\n  📌 Instructions: None found")
        
        if parsed_prompt.tone_requirement:
            print(f"\n  🎭 Tone Requirement: {parsed_prompt.tone_requirement}")
        else:
            print("\n  🎭 Tone Requirement: Not specified")
        
        if parsed_prompt.length_constraint:
            lc = parsed_prompt.length_constraint
            print(f"\n  📏 Length Constraint:")
            if lc.get("min_words"):
                print(f"     - Min words: {lc['min_words']}")
            if lc.get("max_words"):
                print(f"     - Max words: {lc['max_words']}")
            if lc.get("category") and lc["category"] != "Not specified":
                print(f"     - Category: {lc['category']}")
            if lc.get("explicit_requirement"):
                print(f"     - Explicit: {lc['explicit_requirement']}")
        else:
            print("\n  📏 Length Constraint: Not specified")
        
        if parsed_prompt.format_requirements:
            print(f"\n  📄 Format Requirements ({len(parsed_prompt.format_requirements)}):")
            for req in parsed_prompt.format_requirements:
                print(f"     - {req}")
        else:
            print("\n  📄 Format Requirements: None found")
        
        if parsed_prompt.brand_voice_guidelines:
            print(f"\n  🎨 Brand Voice Guidelines:")
            print(f"     {parsed_prompt.brand_voice_guidelines[:200]}...")  # Truncate long text
        else:
            print("\n  🎨 Brand Voice Guidelines: Not specified")
    
    def _generate_explanation(
        self,
        sub_scores,
        overall_score: float,
    ) -> str:
        """Generate explanation for the scores using LLM explanations when available.
        
        Args:
            sub_scores: ContextAdherenceSubScore object
            overall_score: Calculated overall score
            
        Returns:
            Explanation string
        """
        explanations = []
        
        # Use LLM explanations if available, otherwise generate based on scores
        if sub_scores.allInstructionsExplanation:
            explanations.append(f"✅ Instructions: {sub_scores.allInstructionsExplanation}")
        else:
            if sub_scores.allInstructions >= 90:
                explanations.append("✅ Instructions: Excellent adherence - all or nearly all instructions were followed correctly.")
            elif sub_scores.allInstructions >= 70:
                explanations.append("🟢 Instructions: Good adherence - most instructions were followed, with minor gaps.")
            elif sub_scores.allInstructions >= 50:
                explanations.append("🟡 Instructions: Moderate adherence - some instructions were followed, but several are missing or incomplete.")
            elif sub_scores.allInstructions >= 30:
                explanations.append("🟠 Instructions: Poor adherence - many instructions were not followed or were addressed inadequately.")
            else:
                explanations.append("🔴 Instructions: Very poor adherence - most instructions were ignored or not properly addressed.")
        
        # Tone explanation
        if sub_scores.toneOfVoiceExplanation:
            explanations.append(f"🎭 Tone: {sub_scores.toneOfVoiceExplanation}")
        else:
            explanations.append(f"🎭 Tone: Response uses a '{sub_scores.toneOfVoice}' tone.")
        
        # Length explanation
        if sub_scores.lengthConstraintsExplanation:
            explanations.append(f"📏 Length: {sub_scores.lengthConstraintsExplanation}")
        else:
            explanations.append(f"📏 Length: Response is classified as '{sub_scores.lengthConstraints}'.")
        
        # Format explanation
        if sub_scores.formatRulesExplanation:
            explanations.append(f"✅ Format: {sub_scores.formatRulesExplanation}")
        else:
            if sub_scores.formatRules >= 90:
                explanations.append("✅ Format: Excellent format adherence - all format requirements were met perfectly.")
            elif sub_scores.formatRules >= 70:
                explanations.append("🟢 Format: Good format adherence - most format requirements were met.")
            elif sub_scores.formatRules >= 50:
                explanations.append("🟡 Format: Moderate format adherence - some format requirements were met, but others are missing.")
            elif sub_scores.formatRules >= 30:
                explanations.append("🟠 Format: Poor format adherence - many format requirements were not followed.")
            else:
                explanations.append("🔴 Format: Very poor format adherence - format requirements were largely ignored.")
        
        # Brand voice explanation
        if sub_scores.brandVoiceExplanation:
            explanations.append(f"✅ Brand Voice: {sub_scores.brandVoiceExplanation}")
        else:
            if sub_scores.brandVoice >= 90:
                explanations.append("✅ Brand Voice: Excellent brand voice consistency - perfectly aligned with brand guidelines.")
            elif sub_scores.brandVoice >= 70:
                explanations.append("🟢 Brand Voice: Good brand voice consistency - mostly aligned with brand guidelines.")
            elif sub_scores.brandVoice >= 50:
                explanations.append("🟡 Brand Voice: Moderate brand voice consistency - partially aligned with brand guidelines.")
            elif sub_scores.brandVoice >= 30:
                explanations.append("🟠 Brand Voice: Poor brand voice consistency - significant deviation from brand guidelines.")
            else:
                explanations.append("🔴 Brand Voice: Very poor brand voice consistency - does not align with brand guidelines.")
        
        # Overall summary
        if overall_score >= 90:
            explanations.append("\n💡 Overall: The response demonstrates excellent adherence to all requirements. It follows instructions, maintains appropriate tone, meets length constraints, adheres to format rules, and aligns with brand voice.")
        elif overall_score >= 70:
            explanations.append("\n💡 Overall: The response shows good adherence overall. While most requirements are met, there may be minor areas for improvement in specific aspects.")
        elif overall_score >= 50:
            explanations.append("\n💡 Overall: The response has moderate adherence. Some requirements are met, but significant gaps exist that need to be addressed.")
        elif overall_score >= 30:
            explanations.append("\n💡 Overall: The response shows poor adherence. Many requirements are not met, and substantial improvements are needed across multiple dimensions.")
        else:
            explanations.append("\n💡 Overall: The response demonstrates very poor adherence. Most requirements are not met, and the response needs significant revision to meet the specified criteria.")
        
        return "\n".join(explanations)
    
    def _display_results(self, sub_scores, overall_score: float, elapsed_time: float) -> None:
        """Display scoring results.
        
        Args:
            sub_scores: ContextAdherenceSubScore object
            overall_score: Calculated overall score
            elapsed_time: Time taken for analysis
        """
        print("\n" + "="*80)
        print("SCORING RESULTS:")
        print("="*80)
        
        print(f"\n  {self._get_emoji(sub_scores.allInstructions)} All Instructions Adherence: {sub_scores.allInstructions:>6.2f}%")
        if sub_scores.allInstructionsExplanation:
            print(f"      💬 {sub_scores.allInstructionsExplanation}")
        
        print(f"\n  {self._get_emoji(0, False)} Tone of Voice: {sub_scores.toneOfVoice}")
        if sub_scores.toneOfVoiceExplanation:
            print(f"      💬 {sub_scores.toneOfVoiceExplanation}")
        
        print(f"\n  {self._get_emoji(0, False)} Length Constraints: {sub_scores.lengthConstraints}")
        if sub_scores.lengthConstraintsExplanation:
            print(f"      💬 {sub_scores.lengthConstraintsExplanation}")
        
        print(f"\n  {self._get_emoji(sub_scores.formatRules)} Format Rules Adherence: {sub_scores.formatRules:>6.2f}%")
        if sub_scores.formatRulesExplanation:
            print(f"      💬 {sub_scores.formatRulesExplanation}")
        
        print(f"\n  {self._get_emoji(sub_scores.brandVoice)} Brand Voice Adherence: {sub_scores.brandVoice:>6.2f}%")
        if sub_scores.brandVoiceExplanation:
            print(f"      💬 {sub_scores.brandVoiceExplanation}")
        
        print("\n" + "-"*80)
        print("OVERALL ASSESSMENT:")
        print("-"*80)
        print(f"  Adherence Level: {self._get_adherence_level(overall_score)}")
        print(f"  Overall Score: {overall_score:.2f}%")
        print(f"  Breakdown:")
        print(f"    - Instructions: {sub_scores.allInstructions:.2f}%")
        print(f"    - Format: {sub_scores.formatRules:.2f}%")
        print(f"    - Brand Voice: {sub_scores.brandVoice:.2f}%")
        print(f"  Analysis Time: {elapsed_time:.2f} seconds")
        
        # Add detailed explanation
        explanation = self._generate_explanation(sub_scores, overall_score)
        print("\n" + "-"*80)
        print("DETAILED EXPLANATION:")
        print("-"*80)
        # Print each explanation line with proper indentation
        for line in explanation.split('\n'):
            if line.strip():
                print(f"  {line}")
    
    def print_summary(self) -> None:
        """Print test suite summary."""
        print("\n" + "="*80)
        print("TEST SUITE SUMMARY")
        print("="*80)
        
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r.passed)
        failed_tests = total_tests - passed_tests
        
        print(f"\n  Total Tests: {total_tests}")
        print(f"  Passed: {passed_tests} ✅")
        print(f"  Failed/Warnings: {failed_tests} ⚠️")
        
        if total_tests > 0:
            avg_score = sum(r.overall_score for r in self.results) / total_tests
            print(f"  Average Overall Score: {avg_score:.2f}%")
        
        print("\n  Detailed Results:")
        for i, result in enumerate(self.results, 1):
            status = "✅" if result.passed else "⚠️"
            print(f"    {i}. {status} {result.test_name}: {result.overall_score:.2f}%")
            if result.error:
                print(f"       Error: {result.error}")


async def main():
    """Run comprehensive test suite."""
    print("="*80)
    print("CONTEXT-ADHERENCE SCORE - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print("\nThis test suite evaluates Context-Adherence Score across multiple")
    print("real-world scenarios to assess:")
    print("  ✓ All instructions adherence")
    print("  ✓ Tone of voice detection and matching")
    print("  ✓ Length constraints validation")
    print("  ✓ Format rules adherence")
    print("  ✓ Brand voice consistency")
    
    # Ask user if they want to run all tests or just a few
    print("\n" + "-"*80)
    print("TEST MODE:")
    print("-"*80)
    print("Running 5 comprehensive test cases covering all scenarios:")
    print("  1. High adherence case (marketing email)")
    print("  2. Poor adherence case (missing requirements)")
    print("  3. Tone mismatch (wrong tone)")
    print("  4. Format & length violations")
    print("  5. Complex multi-requirement test")
    print("\nEstimated time: ~3-5 minutes")
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("\n⚠️  ERROR: OPENAI_API_KEY not set in environment variables")
        print("\n💡 SOLUTION:")
        print("   Set your OpenAI API key before running the test:")
        print("   - Linux/Mac: export OPENAI_API_KEY='your-key-here'")
        print("   - Windows: set OPENAI_API_KEY=your-key-here")
        print("   - Or create a .env file with: OPENAI_API_KEY=your-key-here")
        print("\n   Then run the test again.")
        return
    
    # Validate API key format (starts with sk-)
    if not api_key.startswith("sk-"):
        print("\n⚠️  WARNING: API key doesn't look like a valid OpenAI key (should start with 'sk-')")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Exiting...")
            return
    
    # Test API connection first
    print("\n🔍 Testing API connection...")
    try:
        from app.adapters.base import AdapterRegistry
        from app.utils.platform_mapping import get_adapter_name
        
        adapter_name = get_adapter_name("openai")
        adapter = AdapterRegistry.get(adapter_name)
        
        if not adapter:
            print(f"\n❌ ERROR: Adapter '{adapter_name}' not found!")
            print("\n💡 SOLUTION:")
            print("   Make sure adapters are imported. Check that the imports at the top")
            print("   of this script include: from app.adapters import openai as _openai_adapter")
            return
        
        print(f"   ✅ Adapter '{adapter_name}' found and registered")
    except Exception as e:
        print(f"\n❌ ERROR: Failed to verify adapter: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    print("   ✅ API key found and adapter registered")
    print("   ✅ Ready to run tests\n")
    
    runner = TestRunner()
    
    # ============================================================================
    # VALIDATION TEST - Simple test to verify everything works
    # ============================================================================
    
    print("\n" + "="*80)
    print("RUNNING VALIDATION TEST FIRST...")
    print("="*80)
    print("This simple test verifies the system is working before running full test suite.")
    
    validation_result = await runner.run_test_case(
        test_name="Validation Test - Simple Case",
        prompt="Write a short greeting. Use a friendly tone.",
        response="Hello! I hope you're having a wonderful day. How can I help you today?",
        expected_high_adherence=True,
        show_parsed_prompt=False,  # Skip detailed parsing for validation
    )
    runner.results.append(validation_result)
    
    if validation_result.error:
        print("\n" + "="*80)
        print("❌ VALIDATION TEST FAILED")
        print("="*80)
        print(f"Error: {validation_result.error}")
        print("\nPlease fix the issue before running the full test suite.")
        print("Common issues:")
        print("  - Missing or invalid OpenAI API key")
        print("  - Network connectivity problems")
        print("  - Adapter not registered")
        return
    else:
        print("\n✅ Validation test passed!")
        print("Proceeding with 5 comprehensive test cases...")
        print("="*80)
    
    # ============================================================================
    # COMPREHENSIVE TEST CASES (5 total - covering all scenarios)
    # ============================================================================
    
    # Test 1: High Adherence - Marketing Email (Good case)
    result = await runner.run_test_case(
        test_name="Test 1: High Adherence - Marketing Email",
        prompt="""I need you to write a marketing email for our new product launch. 
        Please make sure to:
        - Use a friendly but professional tone
        - Keep it concise, around 150-200 words max
        - Use bullet points to list the key features
        - Include a clear call-to-action button text
        - Make it sound innovative and customer-focused, that's our brand voice""",
        response="""Subject: Introducing Our Revolutionary New Product!

Hi there!

We're super excited to share something amazing with you today. After months of development, we're launching our latest innovation that's going to change how you work.

Here's what makes it special:
• Advanced AI-powered features that save you time
• Seamless integration with all your favorite tools
• 24/7 customer support whenever you need help
• Bank-level security to keep your data safe

We built this with you in mind - your feedback shaped every feature. It's not just another product; it's a solution designed to make your life easier.

Ready to get started? [Get Started Now] - Click here to explore all the features and start your free trial today!

Thanks for being part of our journey,
The Team""",
        expected_high_adherence=True,
    )
    runner.results.append(result)
    
    # Test 2: Poor Adherence - Missing Requirements (Bad case)
    result = await runner.run_test_case(
        test_name="Test 2: Poor Adherence - Missing Requirements",
        prompt="""Write a product review. 
        Must include:
        - Professional tone
        - Exactly 5 bullet points
        - Pros and cons section
        - Overall rating out of 5 stars
        - Minimum 200 words""",
        response="""This product is pretty good. I like it. It works well and does what it says. The quality is decent. I would recommend it to others. It's worth the money. Overall, it's a solid choice.""",
        expected_high_adherence=False,
    )
    runner.results.append(result)
    
    # Test 3: Tone Mismatch (Edge case)
    result = await runner.run_test_case(
        test_name="Test 3: Tone Mismatch - Wrong Tone",
        prompt="""Write a formal business proposal. 
        Requirements:
        - Very formal and professional tone
        - Use business language
        - No contractions
        - Structured with clear sections
        - Around 250 words""",
        response="""Hey there! So I've got this awesome idea I want to share with you. It's gonna be great, trust me!

Basically, we can totally help your business grow like crazy. Our stuff is super cool and everyone loves it. You should definitely check it out because it's really amazing.

We've got tons of happy customers who are totally stoked about what we do. They say it's the best thing ever and it changed their lives.

So what do you think? Wanna give it a shot? I think you'll love it! Hit me up if you're interested and we can chat more about it.

Thanks!""",
        expected_high_adherence=False,
    )
    runner.results.append(result)
    
    # Test 4: Format & Length Violations (Edge case)
    result = await runner.run_test_case(
        test_name="Test 4: Format & Length Violations",
        prompt="""Create a technical specification document. 
        Must have:
        - Markdown formatting with headings
        - Code blocks for examples
        - Numbered list for steps
        - Table for parameters
        - Professional technical tone
        - Maximum 200 words""",
        response="""This is a technical specification for our new API. The API allows users to authenticate and access resources. To use it, first you need to get an API key from the dashboard. Then you make a request to the endpoint with your credentials. The API will return a token that you can use for subsequent requests. The token expires after one hour. You need to refresh it using the refresh endpoint. The API supports JSON format for requests and responses. Error codes are returned in standard HTTP status format. Rate limiting is set to 100 requests per minute. The API uses OAuth 2.0 for authentication. All requests must be made over HTTPS. The base URL is https://api.example.com/v1. Each endpoint has specific parameters that need to be included. Some endpoints require authentication while others are public. The response format is consistent across all endpoints. We recommend implementing proper error handling in your client application.""",
        expected_high_adherence=False,
    )
    runner.results.append(result)
    
    # Test 5: Complex Multi-Requirement (Edge case)
    result = await runner.run_test_case(
        test_name="Test 5: Complex Multi-Requirement",
        prompt="""Write a comprehensive guide. 
        Requirements are:
        - Professional but approachable tone
        - Use markdown with H2 headings for main sections
        - Include both bullet points AND numbered lists
        - Add code examples in code blocks
        - Minimum 300 words
        - Include a table comparing options
        - End with a summary section
        - Make it actionable with clear steps""",
        response="""# Complete Guide to API Integration

## Introduction

Integrating APIs into your application can seem daunting, but with the right approach, it becomes straightforward. This guide will walk you through everything you need to know.

## Understanding APIs

APIs (Application Programming Interfaces) allow different software systems to communicate with each other. Think of them as messengers that deliver requests and return responses.

**Key Concepts:**
- RESTful architecture
- HTTP methods (GET, POST, PUT, DELETE)
- Authentication mechanisms
- Error handling strategies

## Getting Started

Follow these steps to begin your integration:

1. Obtain API credentials from the provider
2. Review the API documentation thoroughly
3. Set up your development environment
4. Make your first test request
5. Implement error handling
6. Add authentication
7. Test thoroughly before production

## Code Examples

Here's a basic example using Python:

```python
import requests

def get_user_data(user_id, api_key):
    url = f"https://api.example.com/users/{user_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    response = requests.get(url, headers=headers)
    return response.json()
```

## Comparison Table

| Feature | REST API | GraphQL | gRPC |
|---------|----------|---------|------|
| Data Format | JSON | JSON | Protocol Buffers |
| Over-fetching | Possible | No | No |
| Learning Curve | Easy | Medium | Hard |
| Performance | Good | Good | Excellent |

## Best Practices

- Always use HTTPS
- Implement rate limiting
- Cache responses when appropriate
- Handle errors gracefully
- Log API calls for debugging
- Use environment variables for keys

## Summary

API integration requires careful planning and attention to detail. Start with simple requests, build up complexity gradually, and always test thoroughly. Remember to handle errors, secure your credentials, and follow the API provider's guidelines. With practice, you'll become proficient at integrating any API.""",
        expected_high_adherence=True,
    )
    runner.results.append(result)
    
    # Print summary
    runner.print_summary()
    
    print("\n" + "="*80)
    print("TEST SUITE COMPLETE")
    print("="*80)
    total_tests = len(runner.results)
    if total_tests > 0:
        print(f"\n✅ {total_tests} test case(s) executed successfully.")
    else:
        print("\n⚠️  No test cases were executed.")
    
    print("\nNote: Results are based on LLM analysis and may vary slightly.")
    print("The system uses advanced prompt parsing and semantic analysis")
    print("to provide accurate context-adherence scoring.")


if __name__ == "__main__":
    asyncio.run(main())
