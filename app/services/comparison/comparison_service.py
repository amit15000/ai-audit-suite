"""Service for processing comparisons."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.models import Comparison, ComparisonStatus, User
from app.domain.schemas import (
    ComparisonResponse,
    JudgeEvaluation,
    PlatformResult,
    SubmitComparisonRequest,
)
from app.services.llm.ai_platform_service import AIPlatformService
from app.services.comparison.audit_scorer import AuditScorer
from app.services.comparison.event_manager import ComparisonEventManager
from app.services.embedding.similarity_processor import SimilarityProcessor
from app.services.judgment.judge_llm_service import JudgeLLMService
from app.utils.platform_mapping import get_platform_name


def _update_partial_results(
    db: Session,
    comparison: Comparison,
    partial_data: dict[str, Any],
) -> None:
    """Update partial results in database.
    
    Args:
        db: Database session
        comparison: Comparison record
        partial_data: Dictionary with partial results to merge
    """
    try:
        current_results = comparison.results if isinstance(comparison.results, dict) else {}
        updated_results = {**current_results, **partial_data}
        comparison.results = updated_results  # type: ignore[assignment]
        db.commit()
    except Exception as e:
        import structlog
        logger = structlog.get_logger(__name__)
        logger.warning(
            "comparison.partial_results_update_failed",
            comparison_id=str(comparison.id),
            error=str(e),
        )


def create_comparison(
    db: Session,
    user_id: str,
    request: SubmitComparisonRequest,
) -> Comparison:
    """Create a new comparison record."""
    comparison = Comparison(
        id=f"comp_{uuid.uuid4().hex[:12]}",
        message_id=f"msg_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        prompt=request.prompt,
        judge_platform=request.judge,
        selected_platforms=request.platforms,
        status=ComparisonStatus.QUEUED.value,
        progress=0,
    )
    db.add(comparison)
    db.commit()
    db.refresh(comparison)
    return comparison


async def process_comparison(
    db: Session,
    comparison: Comparison,
    event_manager: ComparisonEventManager | None = None,
) -> None:
    """Process comparison: get responses and calculate scores.
    
    Args:
        db: Database session
        comparison: Comparison record to process
        event_manager: Optional event manager for streaming events
    """
    try:
        # Access model attributes directly - they're Python values at runtime
        comparison.status = ComparisonStatus.PROCESSING.value  # type: ignore[assignment]
        comparison.progress = 0  # type: ignore[assignment]
        db.commit()

        # Emit processing started event
        if event_manager:
            await event_manager.emit_event("processing_started", data={
                "comparison_id": str(comparison.id),
                "platforms": comparison.selected_platforms if isinstance(comparison.selected_platforms, list) else [],
            })

        ai_service = AIPlatformService()
        scorer = AuditScorer()
        judge_service = JudgeLLMService()

        # Get responses from all platforms in parallel
        # selected_platforms is JSON column storing a list - cast for type checker
        selected_platforms_list: list[str] = comparison.selected_platforms if isinstance(comparison.selected_platforms, list) else []  # type: ignore[assignment]
        responses: dict[str, str] = {}
        total_platforms = len(selected_platforms_list)

        # Lock for database updates to prevent race conditions
        db_lock = asyncio.Lock()

        # CRITICAL: Emit ALL response_started events simultaneously BEFORE starting any API calls
        # This ensures all platforms appear to start within 100ms of each other
        if event_manager:
            import structlog
            logger = structlog.get_logger(__name__)
            import time
            start_time = time.time()
            
            # Emit all response_started events in parallel
            start_tasks = [
                event_manager.emit_event("response_started", platform_id=platform_id, data={
                    "platform_name": get_platform_name(platform_id),
                })
                for platform_id in selected_platforms_list
            ]
            await asyncio.gather(*start_tasks)  # All events sent simultaneously
            
            elapsed = (time.time() - start_time) * 1000  # Convert to milliseconds
            logger.info(
                "comparison.all_response_started_emitted",
                comparison_id=str(comparison.id),
                platform_count=len(selected_platforms_list),
                elapsed_ms=elapsed,
            )

        async def process_platform_response(platform_id: str) -> tuple[str, str]:
            """Process a single platform's response asynchronously.
            
            Returns:
                tuple of (platform_id, response_text) or (platform_id, error_message)
            """
            try:
                prompt_text = str(comparison.prompt)  # type: ignore[arg-type]
                
                # Note: response_started event already emitted above for all platforms simultaneously
                
                # Use streaming to get response with proper event emission
                accumulated_text = ""
                first_chunk_received = False
                api_call_start_time = None
                import structlog
                import time
                logger = structlog.get_logger(__name__)
                
                async def on_chunk(chunk: str, accumulated: str) -> None:
                    """Async callback for each chunk - emits events immediately."""
                    nonlocal accumulated_text, first_chunk_received, api_call_start_time
                    accumulated_text = accumulated
                    
                    # Log first chunk timing
                    if not first_chunk_received and api_call_start_time:
                        first_chunk_received = True
                        elapsed = (time.time() - api_call_start_time) * 1000  # ms
                        logger.info(
                            "comparison.first_chunk_received",
                            platform_id=platform_id,
                            elapsed_ms=elapsed,
                            chunk_preview=chunk[:50] if chunk else "",
                        )
                    
                    if event_manager:
                        # Emit chunk event immediately (awaited) - no buffering
                        # This ensures word-by-word streaming to the frontend
                        await event_manager.emit_event(
                            "response_chunk",
                            platform_id=platform_id,
                            data={
                                "chunk": chunk,
                                "accumulated_text": accumulated,
                            },
                        )
                        # Yield control to allow event to be sent immediately
                        await asyncio.sleep(0)
                
                # Log API call start
                api_call_start_time = time.time()
                logger.info(
                    "comparison.api_call_started",
                    platform_id=platform_id,
                    timestamp=api_call_start_time,
                )
                
                # Stream response word-by-word
                full_response = ""
                async for chunk in ai_service.get_response_streaming(
                    platform_id,
                    prompt_text,
                    on_chunk=on_chunk,
                ):
                    full_response += chunk
                
                # Update partial results in database - preserve response text with normal and expanded views
                # Use lock to prevent race conditions with concurrent database updates
                async with db_lock:
                    current_partial = comparison.results if isinstance(comparison.results, dict) else {}
                    existing_partial_responses = current_partial.get("partial_responses", {})
                    existing_partial_responses[platform_id] = {
                        "normal": full_response[:500] if len(full_response) > 500 else full_response,  # Summary view (first 500 chars)
                        "expanded": full_response,  # Full response view
                        "platform_name": get_platform_name(platform_id),
                    }
                    _update_partial_results(db, comparison, {
                        "partial_responses": existing_partial_responses
                    })
                
                # Emit response complete event
                if event_manager:
                    await event_manager.emit_event("response_complete", platform_id=platform_id, data={
                        "response": full_response,
                        "platform_name": get_platform_name(platform_id),
                    })
                
                return (platform_id, full_response)
                
            except Exception as e:
                # Store error but continue with other platforms
                error_msg = f"Error: {str(e)}"
                
                # Emit error event
                if event_manager:
                    await event_manager.emit_event("error", platform_id=platform_id, data={
                        "error": str(e),
                        "stage": "response_generation",
                    })
                
                return (platform_id, error_msg)
        
        # Process all platforms in parallel
        # Create tasks explicitly to ensure all platforms start simultaneously
        # Using create_task() ensures coroutines are scheduled immediately
        tasks = [asyncio.create_task(process_platform_response(platform_id)) for platform_id in selected_platforms_list]
        
        # Wait for all tasks to complete (they all run concurrently)
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect responses and handle exceptions
        completed_count = 0
        for result in results:
            if isinstance(result, Exception):
                # Task raised an exception - log it but continue
                import structlog
                logger = structlog.get_logger(__name__)
                logger.error("Platform processing exception", error=str(result), exc_info=result)
                completed_count += 1
            else:
                platform_id, response_text = result
                responses[platform_id] = response_text
                completed_count += 1
        
        # Update progress after all platforms complete
        comparison.progress = int(completed_count / total_platforms * 40) if total_platforms > 0 else 40  # 40% for responses  # type: ignore[assignment]
        
        # Emit progress event
        if event_manager:
            await event_manager.emit_event("progress", data={
                "progress": comparison.progress,
                "stage": "response_generation",
            })
        
        db.commit()

        # Process similarity analysis (embedding & similarity)
        similarity_analysis = None
        valid_responses = {
            pid: resp
            for pid, resp in responses.items()
            if pid in responses and not resp.startswith("Error:")
        }
        
        if len(valid_responses) >= 2:  # Need at least 2 responses for similarity
            if event_manager:
                await event_manager.emit_event("similarity_analysis_started", data={
                    "valid_responses_count": len(valid_responses),
                })
            
            try:
                similarity_processor = SimilarityProcessor()
                comparison_id_str = str(comparison.id)  # type: ignore[arg-type]
                similarity_analysis = await similarity_processor.process_responses(
                    request_id=comparison_id_str,
                    responses=valid_responses,
                    persist=True,
                )
                comparison.progress = 50  # type: ignore[assignment]
                
                if event_manager:
                    await event_manager.emit_event("similarity_analysis_complete", data={
                        "consensus_scores": similarity_analysis.get("consensus_scores", {}),
                        "outliers": similarity_analysis.get("outliers", []),
                    })
                
                db.commit()
            except Exception as e:
                # Log error but don't fail the comparison
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning(
                    "comparison.similarity_analysis_failed",
                    comparison_id=str(comparison.id),  # type: ignore[arg-type]
                    error=str(e),
                )
                comparison.progress = 50  # type: ignore[assignment]
                
                if event_manager:
                    await event_manager.emit_event("error", data={
                        "error": str(e),
                        "stage": "similarity_analysis",
                    })
                
                db.commit()

        # Calculate scores for each platform
        platform_results: list[PlatformResult] = []
        for idx, platform_id in enumerate(selected_platforms_list):
            if platform_id not in responses or responses[platform_id].startswith("Error:"):
                # Skip failed platforms
                continue

            platform_name = get_platform_name(platform_id)
            judge_platform_id = str(comparison.judge_platform)  # type: ignore[arg-type]
            prompt_text = str(comparison.prompt)  # type: ignore[arg-type]
            
            # Emit audit scores started event
            if event_manager:
                await event_manager.emit_event("audit_scores_started", platform_id=platform_id, data={
                    "platform_name": platform_name,
                    "total_categories": len(scorer.AUDIT_CATEGORIES),
                })
            
            # Calculate detailed audit scores with streaming
            detailed_scores = await scorer.calculate_scores(
                platform_id,
                platform_name,
                responses[platform_id],
                judge_platform_id,
                responses,
                event_manager=event_manager,
            )

            top_reasons = await scorer.generate_top_reasons(
                platform_id,
                platform_name,
                detailed_scores.scores,
                judge_platform_id,
            )

            # Evaluate with Judge LLM (fixed JSON rubric evaluation)
            judge_evaluation = None
            try:
                if event_manager:
                    await event_manager.emit_event("judge_started", platform_id=platform_id, data={
                        "judge_platform": judge_platform_id,
                    })
                
                # Use streaming judge evaluation
                judge_result = await judge_service.evaluate_streaming(
                    response_text=responses[platform_id],
                    judge_platform_id=judge_platform_id,
                    user_query=prompt_text,
                    event_manager=event_manager,
                    platform_id=platform_id,
                )
                
                judge_evaluation = JudgeEvaluation(
                    scores=judge_result.scores,
                    trustScore=judge_result.trust_score,
                    fallbackApplied=judge_result.fallback_applied,
                    weights=judge_result.weights_used,
                )
                
                # Update partial results with judge evaluation
                current_partial = comparison.results if isinstance(comparison.results, dict) else {}
                partial_judge = current_partial.get("partial_judge_evaluations", {})
                partial_judge[platform_id] = {
                    "scores": judge_result.scores.model_dump(),
                    "trust_score": judge_result.trust_score,
                    "fallback_applied": judge_result.fallback_applied,
                }
                _update_partial_results(db, comparison, {
                    "partial_judge_evaluations": partial_judge,
                })
                
                if event_manager:
                    await event_manager.emit_event("judge_complete", platform_id=platform_id, data={
                        "scores": judge_result.scores.model_dump(),
                        "trust_score": judge_result.trust_score,
                        "fallback_applied": judge_result.fallback_applied,
                    })
            except Exception as e:
                # Log error but don't fail the comparison
                import structlog
                logger = structlog.get_logger(__name__)
                logger.warning(
                    "comparison.judge_evaluation_failed",
                    platform_id=platform_id,
                    error=str(e),
                )
                
                if event_manager:
                    await event_manager.emit_event("error", platform_id=platform_id, data={
                        "error": str(e),
                        "stage": "judge_evaluation",
                    })

            # Calculate overall score (60-100 range)
            # Prefer judge trust score if available and valid, otherwise use detailed scores average
            if judge_evaluation and not judge_evaluation.fallbackApplied and judge_evaluation.trustScore > 0:
                # Scale trust score (0-10) to 60-100 range
                overall_score = 60 + int(judge_evaluation.trustScore * 4)
            else:
                # Use detailed scores average (20 categories)
                overall_score = 60 + (detailed_scores.overallScore * 4)  # Scale 0-10 to 60-100

            platform_results.append(
                PlatformResult(
                    id=platform_id,
                    name=platform_name,
                    score=overall_score,
                    response=responses[platform_id],
                    detailedScores=detailed_scores,
                    topReasons=top_reasons,
                    judgeEvaluation=judge_evaluation,
                )
            )

            comparison.progress = 50 + int((idx + 1) / total_platforms * 50)  # 50-100% for scoring  # type: ignore[assignment]
            
            if event_manager:
                await event_manager.emit_event("progress", data={
                    "progress": comparison.progress,
                    "stage": "scoring",
                })
            
            db.commit()

        # Sort by score
        platform_results.sort(key=lambda x: x.score, reverse=True)

        if not platform_results:
            raise ValueError("No platforms successfully processed")

        # Build results JSON - ensure responses are preserved
        judge_platform_id = str(comparison.judge_platform)  # type: ignore[arg-type]
        results = {
            "comparisonId": str(comparison.id),  # type: ignore[arg-type]
            "messageId": str(comparison.message_id),  # type: ignore[arg-type]
            "prompt": str(comparison.prompt),  # type: ignore[arg-type]
            "timestamp": datetime.utcnow().isoformat(),
            "status": "completed",
            "judge": {
                "id": judge_platform_id,
                "name": get_platform_name(judge_platform_id),
            },
            "platforms": [p.model_dump() for p in platform_results],
            "sortedBy": "score",
            "winner": {
                "id": platform_results[0].id,
                "name": platform_results[0].name,
                "score": platform_results[0].score,
            },
        }
        
        # Preserve partial responses in final results for frontend compatibility
        if comparison.results and isinstance(comparison.results, dict):
            partial_responses = comparison.results.get("partial_responses", {})
            if partial_responses:
                results["partialResponses"] = partial_responses

        # Add similarity analysis to results if available
        if similarity_analysis:
            results["similarityAnalysis"] = {
                "consensusScores": similarity_analysis["consensus_scores"],
                "outliers": similarity_analysis["outliers"],
                "statistics": similarity_analysis["outlier_analysis"]["statistics"],
            }

        comparison.results = results  # type: ignore[assignment]
        comparison.status = ComparisonStatus.COMPLETED.value  # type: ignore[assignment]
        comparison.progress = 100  # type: ignore[assignment]
        comparison.completed_at = datetime.utcnow()  # type: ignore[assignment]
        db.commit()
        
        # Emit completion event
        if event_manager:
            await event_manager.emit_event("comparison_complete", data={
                "results": results,
            })
            event_manager.close()

    except Exception as e:
        comparison.status = ComparisonStatus.FAILED.value  # type: ignore[assignment]
        comparison.error_message = str(e)  # type: ignore[assignment]
        db.commit()
        
        # Emit error event
        if event_manager:
            await event_manager.emit_event("error", data={
                "error": str(e),
                "stage": "processing",
            })
            event_manager.close()
        
        raise


def get_comparison_results(
    db: Session,
    comparison_id: str,
    judge: str | None = None,
) -> ComparisonResponse | None:
    """Get comparison results."""
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if comparison is None:
        return None

    status_value = str(comparison.status)  # type: ignore[arg-type]
    if status_value != ComparisonStatus.COMPLETED.value:
        # Return status response for incomplete comparisons
        return None

    results_data = comparison.results  # type: ignore[assignment]
    if results_data is None or not isinstance(results_data, dict):
        return None

    # Convert results dict to ComparisonResponse
    # Ensure timestamp is parsed correctly if it's a string
    results_dict: dict[str, Any] = dict(results_data)
    if "timestamp" in results_dict and isinstance(results_dict["timestamp"], str):
        from datetime import datetime
        results_dict = results_dict.copy()
        results_dict["timestamp"] = datetime.fromisoformat(results_dict["timestamp"])
    
    return ComparisonResponse(**results_dict)


def get_comparison_status(
    db: Session,
    comparison_id: str,
) -> dict | None:
    """Get comparison status."""
    comparison = db.query(Comparison).filter(Comparison.id == comparison_id).first()
    if comparison is None:
        return None

    completed_platforms: list[str] = []
    pending_platforms: list[str] = []
    
    status_value = str(comparison.status)  # type: ignore[arg-type]
    progress_value = int(comparison.progress)  # type: ignore[arg-type]
    
    if status_value == ComparisonStatus.PROCESSING.value:
        # Estimate based on progress
        selected_platforms_raw = comparison.selected_platforms  # type: ignore[assignment]
        if isinstance(selected_platforms_raw, list):
            selected_platforms_list: list[str] = selected_platforms_raw
        else:
            selected_platforms_list = []
        total = len(selected_platforms_list)
        completed_count = int((progress_value / 100) * total) if total > 0 else 0
        completed_platforms = selected_platforms_list[:completed_count]  # type: ignore[assignment]
        pending_platforms = selected_platforms_list[completed_count:]  # type: ignore[assignment]

    comparison_id_str = str(comparison.id)  # type: ignore[arg-type]
    estimated_time = None
    if status_value == ComparisonStatus.PROCESSING.value:
        estimated_time = max(0, 30 - (progress_value * 30 // 100))

    return {
        "comparisonId": comparison_id_str,
        "status": status_value,
        "progress": progress_value,
        "estimatedTimeRemaining": estimated_time,
        "completedPlatforms": completed_platforms,
        "pendingPlatforms": pending_platforms,
    }

