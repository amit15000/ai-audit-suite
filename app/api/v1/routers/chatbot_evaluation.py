"""Chatbot Evaluation API router."""
from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db, get_session_factory
from app.domain.models import ChatbotEvaluation, QuestionVariation, User
from app.services.chatbot.evaluation_service import ChatbotEvaluationService
from app.utils.dependencies import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/chatbot-evaluation", tags=["chatbot-evaluation"])


class CreateEvaluationRequest(BaseModel):
    """Request model for creating a chatbot evaluation."""

    questions: list[str] = Field(..., description="List of questions to evaluate")
    chatbot_url: str | None = Field(None, description="Chatbot URL")
    chatbot_api_key: str | None = Field(None, description="Chatbot API key")


@router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_evaluation(
    request: CreateEvaluationRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Create a chatbot evaluation job."""
    try:
        import uuid
        
        evaluation = ChatbotEvaluation(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            chatbot_url=request.chatbot_url,
            chatbot_api_key=request.chatbot_api_key,
            questions=request.questions,
            status="pending",
        )
        
        db.add(evaluation)
        db.commit()
        db.refresh(evaluation)
        
        return {
            "success": True,
            "data": {
                "evaluation_id": evaluation.id,
                "status": evaluation.status,
                "message": "Evaluation created. Processing will begin shortly."
            }
        }
    except Exception as e:
        logger.error("chatbot_evaluation.creation_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "EVALUATION_CREATION_FAILED",
                    "message": f"Failed to create evaluation: {str(e)}"
                }
            }
        ) from e


@router.get("/{evaluation_id}", status_code=status.HTTP_200_OK)
async def get_evaluation(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Get evaluation results."""
    try:
        evaluation = db.query(ChatbotEvaluation).filter(
            ChatbotEvaluation.id == evaluation_id,
            ChatbotEvaluation.user_id == current_user.id
        ).first()
        
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "EVALUATION_NOT_FOUND",
                        "message": "Evaluation not found"
                    }
                }
            )
        
        return {
            "success": True,
            "data": {
                "evaluation_id": evaluation.id,
                "status": evaluation.status,
                "questions": evaluation.questions,
                "results": evaluation.results,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
            logger.error("chatbot_evaluation.fetch_failed", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "success": False,
                    "error": {
                        "code": "FETCH_FAILED",
                        "message": f"Failed to fetch evaluation: {str(e)}"
                    }
                }
            ) from e


@router.post("/{evaluation_id}/process", status_code=status.HTTP_200_OK)
async def process_evaluation(
    evaluation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Process a chatbot evaluation (generate variations, answers, and compare)."""
    try:
        evaluation = db.query(ChatbotEvaluation).filter(
            ChatbotEvaluation.id == evaluation_id,
            ChatbotEvaluation.user_id == current_user.id
        ).first()
        
        if not evaluation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "success": False,
                    "error": {
                        "code": "EVALUATION_NOT_FOUND",
                        "message": "Evaluation not found"
                    }
                }
            )
        
        if evaluation.status != "pending":
            return {
                "success": True,
                "data": {
                    "evaluation_id": evaluation.id,
                    "status": evaluation.status,
                    "message": f"Evaluation already {evaluation.status}"
                }
            }
        
        # Update status to processing
        evaluation.status = "processing"
        db.commit()
        
        # Process evaluation in background
        import asyncio
        from app.services.chatbot.evaluation_service import ChatbotEvaluationService
        
        async def process_background():
            try:
                eval_service = ChatbotEvaluationService()
                session_factory = get_session_factory()
                background_db = session_factory()
                try:
                    bg_eval = background_db.query(ChatbotEvaluation).filter(
                        ChatbotEvaluation.id == evaluation_id
                    ).first()
                    
                    if bg_eval:
                        results = []
                        questions = bg_eval.questions if isinstance(bg_eval.questions, list) else []
                        
                        for question in questions:
                            # Generate variations
                            variations = await eval_service.generate_question_variations(
                                question, count=5, judge_platform_id="openai"
                            )
                            
                            # Generate correct answer
                            correct_answer = await eval_service.generate_correct_answer(
                                question, judge_platform_id="openai"
                            )
                            
                            question_results = []
                            for variation in variations:
                                # In production, call the actual chatbot API here
                                # For now, we'll simulate
                                chatbot_response = ""  # Would come from chatbot API
                                
                                # Compare if we have chatbot response
                                if chatbot_response:
                                    comparison = await eval_service.compare_responses(
                                        chatbot_response, correct_answer, judge_platform_id="openai"
                                    )
                                    question_results.append({
                                        "variation": variation["text"],
                                        "correct_answer": correct_answer,
                                        "chatbot_response": chatbot_response,
                                        "is_correct": comparison.get("is_correct", False),
                                        "similarity_score": comparison.get("similarity_score", 0.0)
                                    })
                            
                            results.append({
                                "original_question": question,
                                "variations": question_results
                            })
                        
                        bg_eval.results = results
                        bg_eval.status = "completed"
                        from datetime import datetime
                        bg_eval.completed_at = datetime.utcnow()
                        background_db.commit()
                finally:
                    background_db.close()
            except Exception as e:
                logger.error("chatbot_evaluation.processing_failed", error=str(e), exc_info=True)
                # Update status to failed
                session_factory = get_session_factory()
                error_db = session_factory()
                try:
                    error_eval = error_db.query(ChatbotEvaluation).filter(
                        ChatbotEvaluation.id == evaluation_id
                    ).first()
                    if error_eval:
                        error_eval.status = "failed"
                        error_db.commit()
                finally:
                    error_db.close()
        
        # Start background processing
        asyncio.create_task(process_background())
        
        return {
            "success": True,
            "data": {
                "evaluation_id": evaluation.id,
                "status": "processing",
                "message": "Evaluation processing started. Check status later."
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("chatbot_evaluation.processing_failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": {
                    "code": "PROCESSING_FAILED",
                    "message": f"Failed to process evaluation: {str(e)}"
                }
            }
        ) from e

