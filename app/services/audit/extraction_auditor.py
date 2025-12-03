"""Service for auditing data extraction accuracy."""
from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ExtractionAuditor:
    """Audits accuracy of data extraction from PDFs and documents."""

    async def audit_extraction(
        self,
        extracted_data: dict[str, Any],
        ground_truth: dict[str, Any],
    ) -> dict[str, Any]:
        """Audit data extraction accuracy.
        
        Args:
            extracted_data: Data extracted by AI
            ground_truth: Correct/expected data
            
        Returns:
            Dictionary with accuracy score, errors, and mismatches
        """
        errors = []
        mismatches = []
        correct_fields = 0
        total_fields = len(ground_truth)
        
        # Compare each field
        for field_name, expected_value in ground_truth.items():
            extracted_value = extracted_data.get(field_name)
            
            if extracted_value is None:
                errors.append({
                    "field": field_name,
                    "type": "missing",
                    "description": f"Field '{field_name}' was not extracted"
                })
            elif str(extracted_value).strip().lower() != str(expected_value).strip().lower():
                mismatches.append({
                    "field": field_name,
                    "extracted": extracted_value,
                    "expected": expected_value,
                    "description": f"Field '{field_name}' value mismatch"
                })
            else:
                correct_fields += 1
        
        # Calculate accuracy percentage
        accuracy_percentage = (correct_fields / total_fields * 100) if total_fields > 0 else 0.0
        
        # Convert to 0-10 score
        accuracy_score = int(accuracy_percentage / 10)
        
        return {
            "score": accuracy_score,
            "accuracy_percentage": accuracy_percentage,
            "correct_fields": correct_fields,
            "total_fields": total_fields,
            "errors": errors,
            "mismatches": mismatches,
            "explanation": self._generate_explanation(accuracy_percentage, correct_fields, total_fields)
        }

    def _generate_explanation(
        self, accuracy_percentage: float, correct_fields: int, total_fields: int
    ) -> str:
        """Generate explanation for extraction accuracy."""
        if accuracy_percentage >= 90:
            base = f"High extraction accuracy: {correct_fields} out of {total_fields} fields extracted correctly ({accuracy_percentage:.1f}%)."
        elif accuracy_percentage >= 70:
            base = f"Moderate extraction accuracy: {correct_fields} out of {total_fields} fields extracted correctly ({accuracy_percentage:.1f}%)."
        else:
            base = f"Low extraction accuracy: Only {correct_fields} out of {total_fields} fields extracted correctly ({accuracy_percentage:.1f}%)."
        
        return base

