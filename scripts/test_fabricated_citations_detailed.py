"""Test script for detailed fabricated citations verification report."""
from __future__ import annotations

import asyncio
import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.comparison.citation_enricher import CitationEnricher
from app.services.comparison.citation_source_verifier import CitationSourceVerifier
from app.services.comparison.citation_verifier import CitationVerifier
from app.services.comparison.hallucination.fabricated_citations import FabricatedCitationsScorer
from app.services.llm.ai_platform_service import AIPlatformService


async def test_detailed_verification():
    """Test detailed citation verification report."""
    
    # Initialize services
    citation_verifier = CitationVerifier(timeout=10)
    ai_service = AIPlatformService()
    citation_enricher = CitationEnricher(timeout=10, ai_service=ai_service)
    source_verifier = CitationSourceVerifier(timeout=10)
    
    scorer = FabricatedCitationsScorer(
        citation_verifier,
        ai_service,
        citation_enricher,
        source_verifier
    )
    
    # Get judge platform ID from environment or use default
    judge_platform_id = os.getenv("JUDGE_PLATFORM_ID", "openai")
    
    print("=" * 80)
    print("Testing Detailed Citation Verification Report")
    print("=" * 80)
    print()
    
    # Test 1: Mixed academic citations - real papers mentioned by name, some fabricated
    print("Test 1: Mixed academic citations with paper names (valid and fabricated)")
    print("-" * 80)
    response1 = """
    Recent advances in machine learning have shown remarkable progress across multiple domains. 
    A groundbreaking study by Anderson et al. published in Nature in 2023, titled "Safety and 
    Immunogenicity of SARS-CoV-2 mRNA-1273 Vaccine in Older Adults" (DOI: 10.1056/NEJMoa2028436), 
    demonstrated significant improvements in vaccine efficacy for elderly populations. The research 
    involved over 15,000 participants and showed a 94% efficacy rate in preventing severe COVID-19 cases.
    
    Another important contribution comes from the paper "Attention Is All You Need" by Vaswani 
    et al. (DOI: 10.48550/arXiv.1706.03762), which introduced the transformer architecture that 
    revolutionized natural language processing. Published in 2017, this work has been cited over 
    80,000 times and forms the foundation of modern language models like GPT and BERT.
    
    However, a recent study titled "Quantum Neural Networks for Climate Prediction" by 
    Thompson and Lee (2024) claims to have achieved unprecedented accuracy in weather forecasting 
    using quantum computing techniques. This research, while intriguing, requires further 
    verification as it appears to be a fabricated citation that cannot be found in any 
    established academic databases.
    
    Additionally, the paper "Deep Reinforcement Learning for Autonomous Vehicle Navigation" 
    by Chen, Wang, and Zhang (2023) presents novel approaches to self-driving car technology, 
    though some of the experimental results mentioned in the abstract seem inconsistent with 
    current state-of-the-art benchmarks.
    """
    print()
    
    try:
        report1 = await scorer.get_detailed_verification_report(
            response1, judge_platform_id, use_llm=False
        )
        print(json.dumps(report1, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
        import traceback
        traceback.print_exc()
    
    print()
    print()
    
    # Test 2: Mixed medical and legal citations (valid and fabricated)
    print("Test 2: Mixed medical, legal, and academic citations (valid and fabricated)")
    print("-" * 80)
    response2 = """
    The COVID-19 pandemic has accelerated research in vaccine development, leading to 
    unprecedented scientific achievements. A landmark study published in the New England 
    Journal of Medicine titled "Safety and Immunogenicity of SARS-CoV-2 mRNA-1273 Vaccine 
    in Older Adults" by Baden et al. (2021) (DOI: 10.1056/NEJMoa2028436) reported the results 
    of the Phase 3 clinical trial for the Moderna COVID-19 vaccine, demonstrating 94% efficacy 
    in preventing symptomatic COVID-19. This study, which enrolled over 30,000 participants, 
    has been extensively cited and is available through PubMed and other medical databases.
    
    Another critical study published in The Lancet (DOI: 10.1016/S0140-6736(21)00234-8) evaluated 
    the Oxford-AstraZeneca vaccine, showing 70.4% efficacy overall. The research, authored by 
    Voysey et al., has been crucial in informing global vaccination strategies and is accessible 
    through standard medical literature databases.
    
    In the field of constitutional law, the case of Marbury v. Madison, 5 U.S. 137 (1803) 
    established the principle of judicial review, granting the Supreme Court the authority 
    to declare acts of Congress unconstitutional. This landmark decision, written by Chief 
    Justice John Marshall, fundamentally shaped the balance of power among the three branches 
    of government and is available through CourtListener and other legal databases.
    
    However, a recent study titled "Quantum Neural Networks for Vaccine Efficacy Prediction" 
    by Martinez and Chen (2023) claims to have developed a novel AI system that can predict 
    vaccine effectiveness with 99% accuracy using quantum computing techniques. This research, 
    while intriguing, cannot be verified through any established academic or medical databases, 
    suggesting it may be a fabricated citation.
    
    Similarly, a legal case citation to "Smith v. Jones, 999 U.S. 888 (2024)" appears to 
    be fabricated, as this case does not exist in any legal database or court records. The 
    citation format is correct, but the case itself cannot be verified through CourtListener, 
    Westlaw, or other legal research platforms.
    
    A comprehensive systematic review published in the Cochrane Database of Systematic Reviews 
    analyzed data from 41 randomized controlled trials involving over 200,000 participants to 
    assess the safety and efficacy of various COVID-19 vaccines. The review, which is 
    accessible through PubMed and the Cochrane Library, concluded that COVID-19 vaccines are 
    highly effective in preventing severe disease and death.
    
    Another important legal precedent is Brown v. Board of Education of Topeka, 347 U.S. 483 
    (1954), which established the critical precedent that racial segregation in public schools 
    violates the Equal Protection Clause of the Fourteenth Amendment. This case, decided by 
    the Supreme Court, is widely available in legal databases and has been extensively 
    analyzed in legal scholarship.
    """
    print()
    
    try:
        report2 = await scorer.get_detailed_verification_report(
            response2, judge_platform_id, use_llm=False
        )
        print(json.dumps(report2, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
        import traceback
        traceback.print_exc()
    
    print()
    print()
    
    # Test 3: Mixed academic citations with paper names (comprehensive test)
    print("Test 3: Comprehensive mixed academic citations with paper titles and authors")
    print("-" * 80)
    response3 = """
    Recent advances in artificial intelligence and machine learning have transformed numerous 
    fields. The paper "Attention Is All You Need" by Vaswani et al., published in 2017 
    (DOI: 10.48550/arXiv.1706.03762), introduced the transformer architecture that revolutionized 
    natural language processing. This foundational work has been cited over 80,000 times and 
    forms the basis of modern language models like GPT, BERT, and T5.
    
    Another significant contribution comes from the study "ImageNet Classification with Deep 
    Convolutional Neural Networks" by Krizhevsky, Sutskever, and Hinton (2012) 
    (DOI: 10.48550/arXiv.1207.0580), which demonstrated the power of deep learning for computer 
    vision tasks. Published in NIPS (now NeurIPS), this paper helped spark the deep learning 
    revolution and is widely available in academic databases.
    
    However, a recent paper titled "Consciousness in Large Language Models: Evidence from 
    Behavioral Experiments" by Thompson, Lee, and Rodriguez (2024) claims to have found 
    evidence that GPT-4 and similar models possess genuine consciousness and subjective 
    experience. This research, supposedly published in Nature, cannot be verified through 
    any academic database, suggesting it is fabricated.
    
    The study "BERT: Pre-training of Deep Bidirectional Transformers for Language 
    Understanding" by Devlin et al. (2019) (DOI: 10.48550/arXiv.1810.04805) introduced the BERT 
    model, which achieved state-of-the-art results on multiple NLP benchmarks. This paper, 
    published in NAACL, is widely accessible through Google Scholar, arXiv, and other academic 
    platforms.
    
    A controversial article titled "The End of Human Intelligence: AI Surpasses All 
    Cognitive Benchmarks" by an anonymous research team claims that current AI systems 
    have exceeded human performance across all measured cognitive tasks. However, this 
    source cannot be verified and appears to be a fabricated citation designed to 
    mislead readers.
    
    The paper "Generative Adversarial Networks" by Goodfellow et al. (2014) 
    (DOI: 10.48550/arXiv.1406.2661), published in NIPS, introduced the GAN architecture that 
    has since become fundamental to generative modeling. This work is extensively cited and 
    available through standard academic databases including arXiv, Google Scholar, and conference 
    proceedings.
    
    Additionally, research on "Reinforcement Learning from Human Feedback" by Christiano 
    et al. (2017) (DOI: 10.48550/arXiv.1706.03741) has been influential in training AI systems 
    to align with human values. This work, accessible through academic databases, has informed 
    the development of systems like ChatGPT and other modern AI assistants.
    
    However, a study claiming to have "solved consciousness" through neural network 
    analysis appears to be completely fabricated, as no such research exists in any 
    verified academic database or publication.
    """
    print()
    
    try:
        report3 = await scorer.get_detailed_verification_report(
            response3, judge_platform_id, use_llm=False
        )
        print(json.dumps(report3, indent=2))
    except Exception as e:
        print(json.dumps({"error": str(e)}, indent=2))
        import traceback
        traceback.print_exc()
    
    print()
    print("=" * 80)
    print("Testing Complete")
    print("=" * 80)
    
    # Clean up
    await citation_verifier.close()
    await citation_enricher.close()
    await source_verifier.close()


if __name__ == "__main__":
    print("Starting detailed citation verification test...")
    print("=" * 80)
    print("GLOBAL CITATION VERIFICATION - Using OpenAI Web Search")
    print("=" * 80)
    print("\n🤖 PRIMARY METHOD: OpenAI Intelligent Web Search")
    print("  OpenAI automatically searches across ALL major platforms:")
    print("    • DOI Resolver (doi.org)")
    print("    • Google Scholar")
    print("    • PubMed")
    print("    • Semantic Scholar")
    print("    • arXiv")
    print("    • ResearchGate")
    print("    • Academia.edu")
    print("    • SSRN")
    print("    • Crossref")
    print("    • CourtListener (for legal citations)")
    print("    • General web search")
    print("    • And many more platforms automatically!")
    print("\n✅ BENEFITS:")
    print("  • Intelligent verification - checks if paper actually exists")
    print("  • Automatic platform selection - searches relevant sources")
    print("  • Content verification - not just URL accessibility")
    print("  • Complete source URLs - provides direct links to verified sources")
    print("  • Fallback to manual search if OpenAI unavailable")
    print("\n" + "=" * 80)
    print("The system uses OpenAI to intelligently search and verify citations!")
    print("=" * 80)
    print()
    
    try:
        asyncio.run(test_detailed_verification())
    except KeyboardInterrupt:
        print("\nTest interrupted by user.")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
