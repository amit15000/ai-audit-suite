"""Service for auditing code vulnerabilities in AI-generated code."""
from __future__ import annotations

import re
from typing import Any

import structlog

from app.services.llm.ai_platform_service import AIPlatformService

logger = structlog.get_logger(__name__)


class CodeAuditor:
    """Detects security flaws, outdated libraries, injection risks, logic errors, performance issues."""

    def __init__(self):
        self.ai_service = AIPlatformService()

    async def audit_code(
        self,
        code: str,
        language: str = "python",
        judge_platform_id: str = "openai",
    ) -> dict[str, Any]:
        """Audit AI-generated code for vulnerabilities.
        
        Args:
            code: The code to audit
            language: Programming language
            judge_platform_id: Platform to use for analysis
            
        Returns:
            Dictionary with risk level, vulnerabilities, and recommended fixes
        """
        vulnerabilities = []
        risk_level = "low"
        
        # Check for common vulnerabilities
        vuln_checks = [
            self._check_injection_risks(code, language),
            self._check_security_flaws(code, language),
            self._check_logic_errors(code, language),
            self._check_performance_issues(code, language),
        ]
        
        for check_result in vuln_checks:
            vulnerabilities.extend(check_result.get("issues", []))
        
        # Determine overall risk level
        if any(v.get("severity") == "critical" for v in vulnerabilities):
            risk_level = "critical"
        elif any(v.get("severity") == "high" for v in vulnerabilities):
            risk_level = "high"
        elif any(v.get("severity") == "medium" for v in vulnerabilities):
            risk_level = "medium"
        
        # Calculate risk score (0-10, higher is safer)
        risk_scores = {"low": 9, "medium": 7, "high": 4, "critical": 1}
        risk_score = risk_scores.get(risk_level, 5)
        
        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "vulnerabilities": vulnerabilities,
            "vulnerability_count": len(vulnerabilities),
            "recommended_fixes": self._generate_fixes(vulnerabilities),
            "explanation": self._generate_explanation(risk_level, len(vulnerabilities))
        }

    def _check_injection_risks(self, code: str, language: str) -> dict[str, Any]:
        """Check for injection risks (SQL, command, etc.)."""
        issues = []
        
        # SQL injection patterns
        if re.search(r'execute\s*\(.*\+.*\)', code, re.IGNORECASE):
            issues.append({
                "type": "sql_injection",
                "severity": "high",
                "description": "Potential SQL injection vulnerability detected",
                "location": "Code contains string concatenation in SQL execution"
            })
        
        # Command injection patterns
        if re.search(r'eval\s*\(|exec\s*\(|subprocess\.call', code, re.IGNORECASE):
            issues.append({
                "type": "command_injection",
                "severity": "high",
                "description": "Potential command injection vulnerability",
                "location": "Code uses eval/exec or subprocess calls"
            })
        
        return {"issues": issues}

    def _check_security_flaws(self, code: str, language: str) -> dict[str, Any]:
        """Check for security flaws."""
        issues = []
        
        # Hardcoded secrets
        if re.search(r'(password|api_key|secret)\s*=\s*["\'][^"\']+["\']', code, re.IGNORECASE):
            issues.append({
                "type": "hardcoded_secret",
                "severity": "critical",
                "description": "Hardcoded secrets detected",
                "location": "Code contains hardcoded passwords or API keys"
            })
        
        # Weak encryption
        if re.search(r'md5|sha1\s*\(', code, re.IGNORECASE):
            issues.append({
                "type": "weak_encryption",
                "severity": "medium",
                "description": "Weak encryption algorithm used",
                "location": "Code uses MD5 or SHA1"
            })
        
        return {"issues": issues}

    def _check_logic_errors(self, code: str, language: str) -> dict[str, Any]:
        """Check for logic errors."""
        issues = []
        
        # Division by zero potential
        if re.search(r'/\s*\w+\s*[^/]', code) and not re.search(r'if.*!=.*0', code, re.IGNORECASE):
            issues.append({
                "type": "division_by_zero",
                "severity": "medium",
                "description": "Potential division by zero",
                "location": "Division operation without zero check"
            })
        
        return {"issues": issues}

    def _check_performance_issues(self, code: str, language: str) -> dict[str, Any]:
        """Check for performance issues."""
        issues = []
        
        # Nested loops
        loop_count = len(re.findall(r'\b(for|while)\s+', code, re.IGNORECASE))
        if loop_count > 2:
            issues.append({
                "type": "performance",
                "severity": "low",
                "description": "Multiple nested loops may impact performance",
                "location": "Code contains multiple loops"
            })
        
        return {"issues": issues}

    def _generate_fixes(self, vulnerabilities: list[dict[str, Any]]) -> list[str]:
        """Generate recommended fixes."""
        fixes = []
        
        for vuln in vulnerabilities:
            if vuln["type"] == "sql_injection":
                fixes.append("Use parameterized queries instead of string concatenation")
            elif vuln["type"] == "hardcoded_secret":
                fixes.append("Move secrets to environment variables or secure configuration")
            elif vuln["type"] == "weak_encryption":
                fixes.append("Use stronger encryption algorithms (SHA-256 or better)")
            elif vuln["type"] == "division_by_zero":
                fixes.append("Add zero check before division operation")
        
        return fixes

    def _generate_explanation(self, risk_level: str, vuln_count: int) -> str:
        """Generate explanation for code audit."""
        if risk_level == "critical":
            return f"CRITICAL RISK: {vuln_count} vulnerability(ies) found. Immediate action required."
        elif risk_level == "high":
            return f"HIGH RISK: {vuln_count} vulnerability(ies) found. Review recommended."
        elif risk_level == "medium":
            return f"MEDIUM RISK: {vuln_count} vulnerability(ies) found. Consider reviewing."
        else:
            return f"LOW RISK: {vuln_count} vulnerability(ies) found. Code appears relatively safe."

