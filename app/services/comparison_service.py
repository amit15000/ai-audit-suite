"""Service for processing comparisons."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.models import Comparison, ComparisonStatus, User
from app.domain.schemas import (
    ComparisonResponse,
    PlatformResult,
    SubmitComparisonRequest,
)
from app.services.ai_platform_service import AIPlatformService
from app.services.audit_scorer import AuditScorer
from app.utils.platform_mapping import get_platform_name


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


async def process_comparison(db: Session, comparison: Comparison) -> None:
    """Process comparison: get responses and calculate scores."""
    try:
        # Access model attributes directly - they're Python values at runtime
        comparison.status = ComparisonStatus.PROCESSING.value  # type: ignore[assignment]
        comparison.progress = 0  # type: ignore[assignment]
        db.commit()

        ai_service = AIPlatformService()
        scorer = AuditScorer()

        # Get responses from all platforms
        # selected_platforms is JSON column storing a list - cast for type checker
        selected_platforms_list: list[str] = comparison.selected_platforms if isinstance(comparison.selected_platforms, list) else []  # type: ignore[assignment]
        responses: dict[str, str] = {}
        total_platforms = len(selected_platforms_list)

        for idx, platform_id in enumerate(selected_platforms_list):
            try:
                prompt_text = str(comparison.prompt)  # type: ignore[arg-type]
                response = await ai_service.get_response(platform_id, prompt_text)
                responses[platform_id] = response
            except Exception as e:
                # Store error but continue with other platforms
                responses[platform_id] = f"Error: {str(e)}"
            
            comparison.progress = int((idx + 1) / total_platforms * 50)  # 50% for responses  # type: ignore[assignment]
            db.commit()

        # Calculate scores for each platform
        platform_results: list[PlatformResult] = []
        for idx, platform_id in enumerate(selected_platforms_list):
            if platform_id not in responses or responses[platform_id].startswith("Error:"):
                # Skip failed platforms
                continue

            platform_name = get_platform_name(platform_id)
            judge_platform_id = str(comparison.judge_platform)  # type: ignore[arg-type]
            detailed_scores = await scorer.calculate_scores(
                platform_id,
                platform_name,
                responses[platform_id],
                judge_platform_id,
                responses,
            )

            top_reasons = await scorer.generate_top_reasons(
                platform_id,
                platform_name,
                detailed_scores.scores,
                judge_platform_id,
            )

            # Calculate overall score (60-100 range)
            overall_score = 60 + (detailed_scores.overallScore * 4)  # Scale 1-9 to 60-100

            platform_results.append(
                PlatformResult(
                    id=platform_id,
                    name=platform_name,
                    score=overall_score,
                    response=responses[platform_id],
                    detailedScores=detailed_scores,
                    topReasons=top_reasons,
                )
            )

            comparison.progress = 50 + int((idx + 1) / total_platforms * 50)  # 50-100% for scoring  # type: ignore[assignment]
            db.commit()

        # Sort by score
        platform_results.sort(key=lambda x: x.score, reverse=True)

        if not platform_results:
            raise ValueError("No platforms successfully processed")

        # Build results JSON
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

        comparison.results = results  # type: ignore[assignment]
        comparison.status = ComparisonStatus.COMPLETED.value  # type: ignore[assignment]
        comparison.progress = 100  # type: ignore[assignment]
        comparison.completed_at = datetime.utcnow()  # type: ignore[assignment]
        db.commit()

    except Exception as e:
        comparison.status = ComparisonStatus.FAILED.value  # type: ignore[assignment]
        comparison.error_message = str(e)  # type: ignore[assignment]
        db.commit()
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

