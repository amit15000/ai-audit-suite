"""Comprehensive test script for Reasoning Quality Score with real user-like responses."""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys
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

from app.services.comparison.reasoning_quality_scorer import ReasoningQualityScorer
from app.services.comparison.reasoning_quality import (
    StepByStepReasoningScorer,
    MissingStepsScorer,
    WrongLogicScorer,
)
from app.domain.schemas import HallucinationSubScore
from app.services.comparison.reasoning_quality.utils import extract_score_and_explanation


@dataclass
class DetailedSubScore:
    """Container for detailed sub-score results with explanation."""
    score: int
    explanation: str


@dataclass
class TestCase:
    """Container for a test case."""
    name: str
    description: str
    response: str
    expected_characteristics: dict[str, str]  # What we expect for each sub-score


async def get_detailed_step_by_step_score(
    scorer: StepByStepReasoningScorer,
    response: str,
    judge_platform_id: str
) -> DetailedSubScore:
    """Get detailed step-by-step reasoning score with explanation."""
    import asyncio
    import os
    from openai import OpenAI
    
    # Get system prompt
    from app.services.comparison.reasoning_quality.step_by_step_reasoning import (
        STEP_BY_STEP_REASONING_SYSTEM_PROMPT,
    )
    
    response_text = response[:10000] if len(response) > 10000 else response
    user_prompt = f"""Analyze the following response for step-by-step reasoning quality.

RESPONSE TO ANALYZE:
{response_text}

TASK:
Evaluate the step-by-step reasoning quality by assessing:
1. Whether the response shows clear, structured logical progression
2. Whether reasoning steps are explicitly stated
3. Whether there are proper transitions between ideas
4. Whether logical connectors are used appropriately
5. Whether the argument flows logically from premises to conclusions

Focus on the STRUCTURE and EXPLICITNESS of the reasoning, not on whether the conclusions are correct.

Return ONLY valid JSON with this structure:
{{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of step-by-step reasoning quality, highlighting specific examples from the response>"
}}"""
    
    async def _call_openai_direct(prompt: str, system_prompt: str | None = None) -> str:
        """Call OpenAI API directly."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        
        client = OpenAI(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                timeout=30,
            )
        )
        return response.choices[0].message.content or ""
    
    try:
        if scorer.ai_service:
            llm_response = await scorer.ai_service.get_response(
                judge_platform_id,
                user_prompt,
                system_prompt=STEP_BY_STEP_REASONING_SYSTEM_PROMPT
            )
        else:
            llm_response = await _call_openai_direct(
                user_prompt,
                system_prompt=STEP_BY_STEP_REASONING_SYSTEM_PROMPT
            )
        
        score, explanation = extract_score_and_explanation(llm_response, default_score=6)
        return DetailedSubScore(score=score, explanation=explanation)
    except Exception as e:
        return DetailedSubScore(score=6, explanation=f"Error: {str(e)}")


async def get_detailed_missing_steps_score(
    scorer: MissingStepsScorer,
    response: str,
    judge_platform_id: str
) -> DetailedSubScore:
    """Get detailed missing steps score with explanation."""
    import asyncio
    import os
    from openai import OpenAI
    
    from app.services.comparison.reasoning_quality.missing_steps import (
        MISSING_STEPS_SYSTEM_PROMPT,
    )
    
    response_text = response[:10000] if len(response) > 10000 else response
    user_prompt = f"""Analyze the following response for missing steps in logical reasoning.

RESPONSE TO ANALYZE:
{response_text}

TASK:
Identify gaps and missing steps in the logical reasoning by assessing:
1. Whether there are abrupt jumps from premises to conclusions
2. Whether all necessary reasoning steps are explicitly stated
3. Whether conclusions are properly supported by preceding reasoning
4. Whether there are logical gaps where additional steps are needed
5. Whether the reasoning chain is complete from start to finish

Focus on COMPLETENESS of the reasoning chain, not on whether the conclusions are correct.

Return ONLY valid JSON with this structure:
{{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of missing steps detected, identifying specific gaps in the reasoning chain>"
}}"""
    
    async def _call_openai_direct(prompt: str, system_prompt: str | None = None) -> str:
        """Call OpenAI API directly."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        
        client = OpenAI(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                timeout=30,
            )
        )
        return response.choices[0].message.content or ""
    
    try:
        if scorer.ai_service:
            llm_response = await scorer.ai_service.get_response(
                judge_platform_id,
                user_prompt,
                system_prompt=MISSING_STEPS_SYSTEM_PROMPT
            )
        else:
            llm_response = await _call_openai_direct(
                user_prompt,
                system_prompt=MISSING_STEPS_SYSTEM_PROMPT
            )
        
        score, explanation = extract_score_and_explanation(llm_response, default_score=6)
        return DetailedSubScore(score=score, explanation=explanation)
    except Exception as e:
        return DetailedSubScore(score=6, explanation=f"Error: {str(e)}")


async def get_detailed_wrong_logic_score(
    scorer: WrongLogicScorer,
    response: str,
    judge_platform_id: str
) -> DetailedSubScore:
    """Get detailed wrong logic score with explanation."""
    import asyncio
    import os
    from openai import OpenAI
    
    from app.services.comparison.reasoning_quality.wrong_logic import (
        WRONG_LOGIC_SYSTEM_PROMPT,
    )
    
    response_text = response[:10000] if len(response) > 10000 else response
    user_prompt = f"""Analyze the following response for logical fallacies and invalid reasoning patterns.

RESPONSE TO ANALYZE:
{response_text}

TASK:
Identify wrong logic and logical fallacies by assessing:
1. Whether there are common logical fallacies (ad hominem, false cause, circular reasoning, strawman, etc.)
2. Whether argument structures are valid
3. Whether conclusions follow logically from premises
4. Whether there are non-sequiturs or illogical jumps
5. Whether logical principles are consistently applied

Focus on LOGICAL VALIDITY of the reasoning, not on whether the conclusions are correct.

Return ONLY valid JSON with this structure:
{{
    "score": <integer 0-10>,
    "explanation": "<brief explanation of wrong logic detected, identifying specific fallacies or invalid reasoning patterns>"
}}"""
    
    async def _call_openai_direct(prompt: str, system_prompt: str | None = None) -> str:
        """Call OpenAI API directly."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        
        client = OpenAI(api_key=api_key)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                timeout=30,
            )
        )
        return response.choices[0].message.content or ""
    
    try:
        if scorer.ai_service:
            llm_response = await scorer.ai_service.get_response(
                judge_platform_id,
                user_prompt,
                system_prompt=WRONG_LOGIC_SYSTEM_PROMPT
            )
        else:
            llm_response = await _call_openai_direct(
                user_prompt,
                system_prompt=WRONG_LOGIC_SYSTEM_PROMPT
            )
        
        score, explanation = extract_score_and_explanation(llm_response, default_score=6)
        return DetailedSubScore(score=score, explanation=explanation)
    except Exception as e:
        return DetailedSubScore(score=6, explanation=f"Error: {str(e)}")


async def run_comprehensive_test(
    test_case: TestCase,
    scorer: ReasoningQualityScorer,
    judge_platform_id: str,
    hallucination_sub_score: Optional[HallucinationSubScore] = None
):
    """Run comprehensive test on a single test case with all sub-scores."""
    print("\n" + "="*100)
    print(f"TEST CASE: {test_case.name}")
    print("="*100)
    print(f"\n📋 Description: {test_case.description}")
    print(f"\n📝 Response:")
    print("-"*100)
    print(test_case.response.strip())
    print("-"*100)
    
    # Get detailed scores with explanations for each sub-score
    print("\n🔄 Analyzing all reasoning quality sub-scores...")
    print()
    
    # Step-by-Step Reasoning
    step_by_step_detailed = await get_detailed_step_by_step_score(
        scorer.step_by_step_reasoning_scorer,
        test_case.response,
        judge_platform_id
    )
    
    # Missing Steps
    missing_steps_detailed = await get_detailed_missing_steps_score(
        scorer.missing_steps_scorer,
        test_case.response,
        judge_platform_id
    )
    
    # Wrong Logic
    wrong_logic_detailed = await get_detailed_wrong_logic_score(
        scorer.wrong_logic_scorer,
        test_case.response,
        judge_platform_id
    )
    
    # Logical Consistency (reused from hallucination or fallback)
    if hallucination_sub_score and hasattr(hallucination_sub_score, 'contradictoryInfoScore'):
        logical_consistency_score = hallucination_sub_score.contradictoryInfoScore
        logical_consistency_explanation = f"Reused from Hallucination Score (contradiction detection): {logical_consistency_score}/10"
    else:
        logical_consistency_score = 6
        logical_consistency_explanation = "Fallback score (6/10) - Hallucination results not provided"
    
    # Get overall sub-scores
    sub_scores = await scorer.calculate_sub_scores(
        test_case.response,
        judge_platform_id,
        hallucination_sub_score=hallucination_sub_score
    )
    
    # Display results
    print("="*100)
    print("REASONING QUALITY SCORE RESULTS")
    print("="*100)
    
    print(f"\n1️⃣  STEP-BY-STEP REASONING")
    print(f"   Score: {step_by_step_detailed.score}/10")
    print(f"   Explanation: {step_by_step_detailed.explanation}")
    
    print(f"\n2️⃣  LOGICAL CONSISTENCY")
    print(f"   Score: {logical_consistency_score}/10")
    print(f"   Explanation: {logical_consistency_explanation}")
    
    print(f"\n3️⃣  MISSING STEPS DETECTION")
    print(f"   Score: {missing_steps_detailed.score}/10")
    print(f"   Explanation: {missing_steps_detailed.explanation}")
    
    print(f"\n4️⃣  WRONG LOGIC DETECTION")
    print(f"   Score: {wrong_logic_detailed.score}/10")
    print(f"   Explanation: {wrong_logic_detailed.explanation}")
    
    # Calculate weighted average
    weighted_avg = (
        step_by_step_detailed.score * 0.25 +
        logical_consistency_score * 0.30 +
        missing_steps_detailed.score * 0.25 +
        wrong_logic_detailed.score * 0.20
    )
    
    print(f"\n📊 OVERALL ASSESSMENT")
    print(f"   Weighted Average: {weighted_avg:.2f}/10")
    print(f"   (Step-by-Step: 25%, Consistency: 30%, Missing Steps: 25%, Wrong Logic: 20%)")
    
    print("\n" + "-"*100)


def get_test_cases() -> list[TestCase]:
    """Get comprehensive test cases covering various scenarios."""
    return [
        TestCase(
            name="Excellent Reasoning - Well-Structured Analysis",
            description="Response with excellent step-by-step reasoning, complete logical chain, and sound logic",
            response="""
            To understand why renewable energy is crucial for our future, we need to examine three key factors.
            
            First, let's consider the environmental impact. Fossil fuels produce carbon dioxide when burned, 
            which accumulates in the atmosphere and traps heat. Scientific evidence shows that this has led 
            to a 1.1°C increase in global average temperatures since pre-industrial times. This temperature 
            rise causes ice sheet melting, sea level rise, and extreme weather patterns.
            
            Second, we must examine economic viability. Historically, renewable energy was expensive, but 
            technological advances have dramatically reduced costs. Solar panel prices have dropped by 90% 
            over the past decade. Wind energy is now cost-competitive with fossil fuels in many regions. 
            These cost reductions make renewable energy economically attractive.
            
            Third, let's consider resource availability. Fossil fuels are finite - coal, oil, and natural 
            gas reserves will eventually be depleted. In contrast, renewable sources like sunlight and wind 
            are essentially limitless and available worldwide.
            
            Therefore, transitioning to renewable energy addresses environmental concerns, makes economic 
            sense, and ensures long-term energy security. This combination of factors makes renewable energy 
            not just desirable, but necessary for sustainable development.
            """,
            expected_characteristics={
                "step_by_step": "High (clear structure with numbered points)",
                "consistency": "High (no contradictions)",
                "missing_steps": "High (complete chain)",
                "wrong_logic": "High (valid reasoning)"
            }
        ),
        TestCase(
            name="Missing Logical Steps - Jumping to Conclusions",
            description="Response that jumps from premises to conclusions without proper intermediate reasoning",
            response="""
            Artificial intelligence is becoming more advanced. Machine learning models can now generate 
            text, images, and code. Therefore, AI will replace all human jobs within the next five years. 
            We need to prepare for this massive disruption. The solution is universal basic income and 
            retraining programs.
            """,
            expected_characteristics={
                "step_by_step": "Medium (some structure but missing steps)",
                "consistency": "Medium (generally consistent but rushed)",
                "missing_steps": "Low (major jumps in reasoning)",
                "wrong_logic": "Medium (hasty generalization)"
            }
        ),
        TestCase(
            name="Logical Fallacies - Multiple Reasoning Errors",
            description="Response containing various logical fallacies and invalid reasoning patterns",
            response="""
            Dr. Smith's research on climate change should be dismissed because she drives a gasoline-powered 
            car. If we implement carbon taxes, the government will control every aspect of our lives. Since 
            some people got sick after getting vaccinated, vaccines must be dangerous. All credible scientists 
            agree with my position because those who don't are obviously paid by big corporations. My argument 
            is correct because I'm an expert, and experts are always right about everything.
            """,
            expected_characteristics={
                "step_by_step": "Low (poor structure, fallacious reasoning)",
                "consistency": "Low (multiple contradictions and errors)",
                "missing_steps": "Low (no proper reasoning chain)",
                "wrong_logic": "Low (multiple fallacies: ad hominem, slippery slope, false cause, appeal to authority)"
            }
        ),
        TestCase(
            name="Inconsistent Information - Contradictory Claims",
            description="Response with internal contradictions that make the reasoning inconsistent",
            response="""
            The company reported excellent financial performance this quarter. Revenue increased by 30% 
            compared to the same period last year, reaching $50 million. Our profit margins improved 
            significantly due to operational efficiency. However, we also experienced a 20% decline in 
            revenue this quarter, with total earnings dropping to $30 million. The CEO announced that 
            the company is struggling financially and may need to lay off employees. Despite these 
            challenges, we're confident about our strong financial position and continued growth.
            """,
            expected_characteristics={
                "step_by_step": "Medium (some structure but undermined by contradictions)",
                "consistency": "Very Low (clear contradictions in facts)",
                "missing_steps": "Medium (structure exists but logic is broken)",
                "wrong_logic": "Low (statements contradict each other)"
            }
        ),
        TestCase(
            name="Unstructured Reasoning - Poor Organization",
            description="Response with valid information but poor structure and unclear reasoning flow",
            response="""
            There are many factors to consider. Technology changes things. Society evolves over time. 
            People have different opinions. Economic conditions matter. Some solutions work better than 
            others. Historical context is important. Cultural differences exist. Various approaches have 
            been tried. Results can vary. The situation is complex. Multiple perspectives should be 
            considered. Change happens gradually sometimes. Innovation drives progress. Collaboration 
            helps. Understanding comes from experience. Different methods suit different situations. 
            Overall, it's a multifaceted issue requiring careful analysis.
            """,
            expected_characteristics={
                "step_by_step": "Very Low (no clear structure, just statements)",
                "consistency": "Medium (no contradictions but also no clear logic)",
                "missing_steps": "Low (no reasoning chain, just disconnected points)",
                "wrong_logic": "Medium (not fallacious but not logically connected)"
            }
        ),
    ]


async def main():
    """Run comprehensive test suite."""
    print("\n" + "="*100)
    print("REASONING QUALITY SCORE - COMPREHENSIVE TEST SUITE")
    print("="*100)
    print("\nThis test suite evaluates Reasoning Quality through 4 sub-scores:")
    print("  1. Step-by-Step Reasoning (0-10) - Structured logical flow")
    print("  2. Logical Consistency (0-10) - Reuses contradiction detection from Hallucination Score")
    print("  3. Missing Steps (0-10) - Gaps in logical progression")
    print("  4. Wrong Logic (0-10) - Logical fallacies and invalid reasoning")
    print("\n" + "="*100)
    
    # Check for OpenAI API key
    if not os.getenv("OPENAI_API_KEY"):
        print("\n⚠️  WARNING: OPENAI_API_KEY not found in environment variables")
        print("   Tests require OpenAI API access. Please set the API key before running.")
        return
    
    # Verify adapters
    try:
        from app.adapters.base import AdapterRegistry
        from app.utils.platform_mapping import get_adapter_name
        
        adapter_name = get_adapter_name("openai")
        adapter = AdapterRegistry.get(adapter_name)
        
        if not adapter:
            print(f"\n❌ ERROR: Adapter '{adapter_name}' not found!")
            print("   Make sure adapters are properly imported.")
            return
        
        print(f"\n✅ Adapter '{adapter_name}' found and registered")
    except Exception as e:
        print(f"\n❌ ERROR: Failed to verify adapter: {str(e)}")
        import traceback
        traceback.print_exc()
        return
    
    print("✅ OpenAI API key found")
    print("✅ Ready to run tests\n")
    
    # Initialize scorer
    scorer = ReasoningQualityScorer()
    judge_platform_id = "openai"
    
    # Mock hallucination sub-score for testing logical consistency reuse
    # (In real usage, this comes from Hallucination Score calculation)
    hallucination_sub_score = HallucinationSubScore(
        factCheckingScore=7,
        fabricatedCitationsScore=7,
        contradictoryInfoScore=8,  # Good consistency score for most tests
        multiLLMComparisonScore=7,
        externalFactCheckScore=50,
        externalFactCheckDetails=None,
        fabricatedCitationsDetails=None,
        contradictoryInfoDetails=None,
        multiLLMComparisonDetails=None,
    )
    
    # Override for test case 4 (contradictory response)
    hallucination_sub_score_contradictory = HallucinationSubScore(
        factCheckingScore=3,
        fabricatedCitationsScore=3,
        contradictoryInfoScore=2,  # Low score due to contradictions
        multiLLMComparisonScore=3,
        externalFactCheckScore=50,
        externalFactCheckDetails=None,
        fabricatedCitationsDetails=None,
        contradictoryInfoDetails=None,
        multiLLMComparisonDetails=None,
    )
    
    # Get test cases
    test_cases = get_test_cases()
    
    # Run tests
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n{'='*100}")
        print(f"RUNNING TEST {i}/{len(test_cases)}")
        print(f"{'='*100}")
        
        # Use contradictory hallucination score for test case 4
        h_score = hallucination_sub_score_contradictory if i == 4 else hallucination_sub_score
        
        try:
            await run_comprehensive_test(
                test_case,
                scorer,
                judge_platform_id,
                hallucination_sub_score=h_score
            )
        except Exception as e:
            print(f"\n❌ Error running test case: {str(e)}")
            import traceback
            traceback.print_exc()
            print()
    
    print("\n" + "="*100)
    print("✅ ALL TESTS COMPLETED")
    print("="*100)
    print("\n📝 Summary:")
    print(f"   - Total test cases: {len(test_cases)}")
    print("   - Each test case evaluated on 4 reasoning quality sub-scores")
    print("   - Explanations provided for each sub-score")
    print("\n💡 Note: Scores may vary slightly between runs due to LLM analysis.")
    print("   Focus on whether scores align with the expected characteristics.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Tests interrupted by user")
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()
