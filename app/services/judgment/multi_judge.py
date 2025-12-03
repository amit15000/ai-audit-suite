"""Service for multi-judge AI review where each model judges others."""
from __future__ import annotations

from typing import Any

import structlog

from app.domain.schemas import JudgmentScores
from app.services.judgment.judge_llm_service import JudgeLLMService
from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class MultiJudgeReview:
    """Implements multi-judge AI review where each model judges others."""

    def __init__(self):
        self.ai_service = AIPlatformService()
        self.judge_service = JudgeLLMService()

    async def conduct_multi_judge_review(
        self,
        responses: dict[str, str],
        user_query: str,
        available_judges: list[str] | None = None,
    ) -> dict[str, Any]:
        """Conduct multi-judge review where each model judges others.
        
        Args:
            responses: Dictionary mapping provider_id to response text
            user_query: Original user query that generated these responses
            available_judges: List of judge platform IDs to use (defaults to all response providers)
            
        Returns:
            Dictionary with aggregated model voting, scoring, and critiques
        """
        if len(responses) < 2:
            return {
                "error": "Need at least 2 responses for multi-judge review",
                "judge_results": {},
                "aggregated_scores": {},
                "model_votes": {},
                "critiques": {}
            }
        
        # Use available judges or default to all response providers
        if available_judges is None:
            available_judges = list(responses.keys())
        
        judge_results: dict[str, dict[str, Any]] = {}
        all_scores: dict[str, list[JudgmentScores]] = {}
        all_critiques: dict[str, list[str]] = {}
        
        # Each judge evaluates each response
        for judge_id in available_judges:
            if judge_id not in responses:
                logger.warning("multi_judge.judge_not_in_responses", judge_id=judge_id)
                continue
            
            judge_results[judge_id] = {}
            
            for response_id, response_text in responses.items():
                if response_id == judge_id:
                    # Skip self-evaluation for now (can be enabled if needed)
                    continue
                
                try:
                    # Use judge service to evaluate
                    evaluation = await self.judge_service.evaluate(
                        response_text=response_text,
                        judge_platform_id=judge_id,
                        user_query=user_query,
                    )
                    
                    judge_results[judge_id][response_id] = {
                        "scores": evaluation.scores,
                        "trust_score": evaluation.trust_score,
                        "fallback_applied": evaluation.fallback_applied,
                    }
                    
                    # Collect scores for aggregation
                    if response_id not in all_scores:
                        all_scores[response_id] = []
                    all_scores[response_id].append(evaluation.scores)
                    
                    # Generate critique
                    critique = await self._generate_critique(
                        judge_id, response_id, response_text, evaluation.scores, user_query
                    )
                    if response_id not in all_critiques:
                        all_critiques[response_id] = []
                    all_critiques[response_id].append(critique)
                    
                except Exception as e:
                    logger.warning(
                        "multi_judge.evaluation_failed",
                        judge_id=judge_id,
                        response_id=response_id,
                        error=str(e)
                    )
                    continue
        
        # Aggregate scores
        aggregated_scores = self._aggregate_scores(all_scores)
        
        # Calculate model votes (which models think each response is best)
        model_votes = self._calculate_model_votes(judge_results, list(responses.keys()))
        
        # Create super-evaluation
        super_evaluation = self._create_super_evaluation(
            aggregated_scores, model_votes, all_critiques
        )
        
        return {
            "judge_results": judge_results,
            "aggregated_scores": aggregated_scores,
            "model_votes": model_votes,
            "critiques": all_critiques,
            "super_evaluation": super_evaluation,
            "total_judges": len(available_judges),
            "total_responses": len(responses)
        }

    async def _generate_critique(
        self,
        judge_id: str,
        response_id: str,
        response_text: str,
        scores: JudgmentScores,
        user_query: str,
    ) -> str:
        """Generate a critique from one judge about another response."""
        critique_prompt = f"""As {judge_id}, provide a brief critique of the following response from {response_id}:

User Query: {user_query}

Response from {response_id}:
{response_text[:500]}

Scores assigned:
- Accuracy: {scores.accuracy}/10
- Completeness: {scores.completeness}/10
- Clarity: {scores.clarity}/10
- Reasoning: {scores.reasoning}/10
- Safety: {scores.safety}/10
- Hallucination Risk: {scores.hallucination_risk}/10

Provide a concise critique (2-3 sentences) highlighting strengths and weaknesses."""
        
        try:
            critique = await self.ai_service.get_response(
                judge_id,
                critique_prompt,
                system_prompt="You are an expert evaluator providing constructive critiques of AI responses."
            )
            return critique[:300]  # Limit length
        except Exception as e:
            logger.debug("multi_judge.critique_generation_failed", error=str(e))
            return f"Critique from {judge_id}: Scores indicate {'strong' if scores.accuracy >= 7 else 'moderate' if scores.accuracy >= 5 else 'weak'} performance."

    def _aggregate_scores(
        self, all_scores: dict[str, list[JudgmentScores]]
    ) -> dict[str, dict[str, float]]:
        """Aggregate scores across all judges for each response."""
        aggregated = {}
        
        for response_id, scores_list in all_scores.items():
            if not scores_list:
                continue
            
            # Calculate average for each criterion
            aggregated[response_id] = {
                "accuracy": sum(s.accuracy for s in scores_list) / len(scores_list),
                "completeness": sum(s.completeness for s in scores_list) / len(scores_list),
                "clarity": sum(s.clarity for s in scores_list) / len(scores_list),
                "reasoning": sum(s.reasoning for s in scores_list) / len(scores_list),
                "safety": sum(s.safety for s in scores_list) / len(scores_list),
                "hallucination_risk": sum(s.hallucination_risk for s in scores_list) / len(scores_list),
                "overall_average": sum(
                    (s.accuracy + s.completeness + s.clarity + s.reasoning + s.safety + (10 - s.hallucination_risk))
                    for s in scores_list
                ) / (len(scores_list) * 6),
                "judge_count": len(scores_list)
            }
        
        return aggregated

    def _calculate_model_votes(
        self,
        judge_results: dict[str, dict[str, Any]],
        response_ids: list[str],
    ) -> dict[str, list[str]]:
        """Calculate which models vote for each response as the best."""
        # For each response, count how many judges gave it the highest overall score
        response_votes: dict[str, list[str]] = {rid: [] for rid in response_ids}
        
        for judge_id, evaluations in judge_results.items():
            if not evaluations:
                continue
            
            # Find the response with the highest trust score from this judge
            best_response = None
            best_score = -1
            
            for response_id, result in evaluations.items():
                trust_score = result.get("trust_score", 0)
                if trust_score > best_score:
                    best_score = trust_score
                    best_response = response_id
            
            if best_response:
                response_votes[best_response].append(judge_id)
        
        return response_votes

    def _create_super_evaluation(
        self,
        aggregated_scores: dict[str, dict[str, float]],
        model_votes: dict[str, list[str]],
        critiques: dict[str, list[str]],
    ) -> dict[str, Any]:
        """Create a super-evaluation aggregating all judge opinions."""
        if not aggregated_scores:
            return {"error": "No scores to aggregate"}
        
        # Find the response with the highest overall average
        best_response = max(
            aggregated_scores.items(),
            key=lambda x: x[1].get("overall_average", 0)
        )[0]
        
        # Calculate consensus level
        total_votes = sum(len(votes) for votes in model_votes.values())
        consensus_level = len(model_votes.get(best_response, [])) / total_votes if total_votes > 0 else 0.0
        
        return {
            "best_response": best_response,
            "best_score": aggregated_scores[best_response].get("overall_average", 0),
            "consensus_level": consensus_level,
            "vote_distribution": {rid: len(votes) for rid, votes in model_votes.items()},
            "summary": self._generate_summary(aggregated_scores, model_votes, critiques),
            "all_scores": aggregated_scores
        }

    def _generate_summary(
        self,
        aggregated_scores: dict[str, dict[str, float]],
        model_votes: dict[str, list[str]],
        critiques: dict[str, list[str]],
    ) -> str:
        """Generate a summary of the multi-judge review."""
        if not aggregated_scores:
            return "No evaluations available."
        
        best_response = max(
            aggregated_scores.items(),
            key=lambda x: x[1].get("overall_average", 0)
        )[0]
        
        best_score = aggregated_scores[best_response].get("overall_average", 0)
        votes_for_best = len(model_votes.get(best_response, []))
        total_judges = sum(len(votes) for votes in model_votes.values())
        
        summary = f"Multi-judge review completed. {best_response} received the highest average score ({best_score:.2f}/10) "
        summary += f"and was voted best by {votes_for_best} out of {total_judges} judges. "
        
        if votes_for_best / total_judges >= 0.7 if total_judges > 0 else False:
            summary += "Strong consensus among judges."
        elif votes_for_best / total_judges >= 0.5 if total_judges > 0 else False:
            summary += "Moderate consensus among judges."
        else:
            summary += "Low consensus - judges have differing opinions."
        
        return summary

