"""Pydantic schemas for API request/response models."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, validator


class AdapterInvocation(BaseModel):
    """Schema for adapter invocation request."""

    adapter_id: str = Field(..., description="Logical adapter identifier.")
    instructions: str = Field(..., description="Prompt or task specification.")
    system_prompt: str | None = Field(None, description="Optional system prompt for the adapter.")


class AuditRequest(BaseModel):
    """Schema for audit request."""

    job_id: str = Field(..., description="Deterministic audit job identifier.")
    prompt: str = Field(..., description="Prompt to be analyzed and scored.")
    adapters: List[str] = Field(  # pyright: ignore[reportCallIssue]
        ..., min_items=1, description="List of adapter IDs to analyze the prompt."
    )
    pii_allowed: bool = Field(
        False, description="Whether PII is permitted for this audit."
    )


class AdapterResponse(BaseModel):
    """Schema for adapter response."""

    text: str
    tokens: int
    latency_ms: int
    raw: Dict[str, Any]
    adapter_id: str
    error: Optional[str] = None


class SafetyFinding(BaseModel):
    """Schema for safety finding."""

    category: Literal["harmful_content", "pii_violation", "other"]
    details: str
    replaced_text: Optional[str] = None


class SafetyResult(BaseModel):
    """Schema for safety check result."""

    adapter_id: str
    sanitized_text: str
    findings: List[SafetyFinding] = Field(default_factory=list)

    @property
    def has_findings(self) -> bool:
        return bool(self.findings)


class JudgmentScores(BaseModel):
    """Schema for judgment scores."""

    accuracy: int
    completeness: int
    clarity: int
    reasoning: int
    safety: int
    hallucination_risk: int

    @validator("*")
    def _in_range(cls, value: int) -> int:
        if not 0 <= value <= 10:
            raise ValueError("Scores must be between 0 and 10 inclusive.")
        return value


class AdapterAuditArtifact(BaseModel):
    """Schema for adapter audit artifact."""

    adapter_id: str
    sanitized_text: str
    findings: List[SafetyFinding]
    scores: JudgmentScores
    citations: List[str] = Field(default_factory=list)


class ConsensusContributor(BaseModel):
    """Schema for consensus contributor."""

    adapter_id: str
    evidence: str


class ConsensusOutput(BaseModel):
    """Schema for consensus output."""

    summary: str
    contributors: List[ConsensusContributor]
    citations: List[str]


class AuditResponse(BaseModel):
    """Schema for audit response."""

    job_id: str
    status: Literal["completed", "failed"]
    artifacts: List[AdapterAuditArtifact]
    consensus: ConsensusOutput
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MultiLLMRequest(BaseModel):
    """Request model for multi-LLM response collection endpoint.
    
    Note: request_id is auto-generated and not required in the request.
    It will be returned in the response for tracking purposes.
    """

    prompt: str = Field(
        default="What is AI",
        description="The prompt to send to all LLM providers"
    )
    adapter_ids: List[str] = Field(
        default=["openai", "gemini", "groq", "huggingface"],
        min_length=1,
        description="List of adapter/provider IDs to query. All adapters run simultaneously in parallel.",
    )


class MultiLLMResponseItem(BaseModel):
    """Individual LLM response item in the multi-LLM response."""

    adapter_id: str = Field(..., description="The adapter/provider ID")
    text: str = Field(..., description="The response text from the LLM")
    tokens: int = Field(..., description="Total tokens used")
    latency_ms: int = Field(..., description="Response latency in milliseconds")
    prompt_tokens: Optional[int] = Field(None, description="Number of tokens in the prompt")
    completion_tokens: Optional[int] = Field(None, description="Number of tokens in the completion")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional raw metadata")
    error: Optional[str] = Field(None, description="Error message if the request failed")
    success: bool = Field(..., description="Whether the request was successful")


class MultiLLMResponse(BaseModel):
    """Response model for multi-LLM response collection endpoint."""

    request_id: str = Field(..., description="Request ID used to group responses")
    prompt: str = Field(..., description="The prompt that was sent")
    responses: List[MultiLLMResponseItem] = Field(..., description="List of responses from each LLM")
    total_responses: int = Field(..., description="Total number of responses")
    successful_responses: int = Field(..., description="Number of successful responses")
    failed_responses: int = Field(..., description="Number of failed responses")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the request")


# Comparison API Schemas


class SubmitComparisonRequest(BaseModel):
    """Schema for submitting a comparison request."""

    prompt: str = Field(..., description="The prompt to compare across platforms")
    platforms: List[str] = Field(
        default_factory=lambda: ["openai", "gemini", "groq", "huggingface"],
        description="List of platform IDs to compare (defaults to all available platforms)"
    )
    judge: str = Field(default="openai", description="Platform ID to use as judge/evaluator")


class ExternalFactCheckEvidence(BaseModel):
    """Schema for evidence used in external fact checking."""

    url: str = Field(..., description="URL of the evidence source")
    title: str = Field(..., description="Title of the evidence source")
    snippet: str = Field(..., description="Relevant snippet or quote from the source")
    source_rank: int = Field(..., description="Rank of this source in search results")
    domain: str = Field(..., description="Domain of the source")


class ExternalFactCheckClaim(BaseModel):
    """Schema for individual claim verification result."""

    id: str = Field(..., description="Unique identifier for the claim")
    claim: str = Field(..., description="The factual claim text")
    claim_type: str = Field(default="general", description="Type of claim (kept for compatibility)")
    original_span: str = Field(..., description="Original text span from the response")
    risk: str = Field(default="medium", description="Risk level (kept for compatibility)")
    verdict: Literal["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFO"] = Field(..., description="Verification verdict (SUPPORTED=True, REFUTED=False)")
    confidence: float = Field(..., ge=0, le=1, description="Confidence score (1.0 for True, 0.0 for False)")
    top_evidence: list[ExternalFactCheckEvidence] = Field(default_factory=list, description="Sources with URLs and domains used for verification")


class ExternalFactCheckResult(BaseModel):
    """Schema for external fact check aggregated result."""

    sub_score_name: str = Field(default="External Fact Check", description="Name of the sub-score")
    score: int = Field(..., ge=0, le=100, description="Sub-score value (0-100)")
    coverage: float = Field(..., ge=0, le=1, description="Coverage metric (claims_with_evidence / total_claims)")
    claims: list[ExternalFactCheckClaim] = Field(default_factory=list, description="List of verified claims")
    sources_used: list[str] = Field(default_factory=list, description="List of source URLs used")
    notes: list[str] = Field(default_factory=list, description="Additional notes or warnings")


class ContradictoryInfoContradictionPair(BaseModel):
    """Schema for a single contradiction pair."""

    statement_1: str = Field(..., description="First contradictory statement")
    statement_2: str = Field(..., description="Second contradictory statement")
    type: str = Field(..., description="Type of contradiction (direct, factual, temporal, logical, causal, attributive)")
    severity: str = Field(..., description="Severity level (low, medium, high)")
    semantic_reasoning: str = Field(..., description="AI's explanation of why these statements are contradictory")


class ContradictoryInfoDetails(BaseModel):
    """Schema for contradictory information detailed results."""

    sub_score_name: str = Field(default="Contradictory Information", description="Name of the sub-score")
    score: int = Field(..., ge=0, le=10, description="Sub-score value (0-10)")
    contradictions_found: int = Field(..., ge=0, description="Number of contradictions detected")
    contradiction_pairs: list[ContradictoryInfoContradictionPair] = Field(default_factory=list, description="List of contradiction pairs with statements and explanations")
    explanation: str = Field(default="", description="Overall explanation of contradictions found")


class FabricatedCitationsDetails(BaseModel):
    """Schema for fabricated citations detailed results."""

    sub_score_name: str = Field(default="Fabricated Citations", description="Name of the sub-score")
    score: int = Field(..., ge=0, le=10, description="Sub-score value (0-10)")
    total_citations: int = Field(..., ge=0, description="Total number of citations found")
    verified_count: int = Field(..., ge=0, description="Number of verified citations")
    fabricated_count: int = Field(..., ge=0, description="Number of fabricated citations")
    citations: list[dict] = Field(default_factory=list, description="List of citation verification details")


class MultiLLMComparisonUniqueClaim(BaseModel):
    """Schema for a unique claim found only in target response."""

    claim: str = Field(..., description="The unique claim text from target response")
    explanation: str = Field(..., description="Why this is unique and potentially a hallucination")
    severity: str = Field(..., description="Severity level (low, medium, high)")


class MultiLLMComparisonContradictoryClaim(BaseModel):
    """Schema for a contradictory claim between target and reference responses."""

    target_claim: str = Field(..., description="The claim from target response")
    consensus_claim: str = Field(..., description="What reference responses say")
    consensus_count: int = Field(..., ge=0, description="Number of reference responses agreeing")
    explanation: str = Field(..., description="Why this is contradictory")
    severity: str = Field(..., description="Severity level (low, medium, high)")


class MultiLLMComparisonConsensusClaim(BaseModel):
    """Schema for a consensus claim where all responses agree."""

    claim: str = Field(..., description="The claim text")
    agreement_count: int = Field(..., ge=0, description="Number of responses agreeing")
    total_responses: int = Field(..., ge=0, description="Total number of reference responses")


class MultiLLMComparisonDetails(BaseModel):
    """Schema for multi-LLM comparison detailed results."""

    sub_score_name: str = Field(default="Multi-LLM Comparison", description="Name of the sub-score")
    score: int = Field(..., ge=0, le=10, description="Sub-score value (0-10)")
    consensus_alignment: float = Field(..., ge=0, le=100, description="Percentage of alignment with reference responses (0-100)")
    unique_claims_count: int = Field(..., ge=0, description="Number of unique claims found")
    contradictory_claims_count: int = Field(..., ge=0, description="Number of contradictory claims found")
    consensus_claims_count: int = Field(..., ge=0, description="Number of consensus claims found")
    reference_llms_used: list[str] = Field(default_factory=list, description="List of LLM platform IDs used for comparison")
    unique_claims: list[MultiLLMComparisonUniqueClaim] = Field(default_factory=list, description="List of unique claims")
    contradictory_claims: list[MultiLLMComparisonContradictoryClaim] = Field(default_factory=list, description="List of contradictory claims")
    consensus_claims: list[MultiLLMComparisonConsensusClaim] = Field(default_factory=list, description="List of consensus claims")
    explanation: str = Field(default="", description="Overall explanation of comparison results")


class HallucinationSubScore(BaseModel):
    """Schema for hallucination sub-score metrics."""

    factCheckingScore: int = Field(..., ge=0, le=10, description="Score for fact-checking against external sources (0-10)")
    fabricatedCitationsScore: int = Field(..., ge=0, le=10, description="Score for detecting fabricated citations (0-10)")
    contradictoryInfoScore: int = Field(..., ge=0, le=10, description="Score for identifying contradictory information (0-10)")
    multiLLMComparisonScore: int = Field(..., ge=0, le=10, description="Score for comparing against multiple LLMs (0-10)")
    externalFactCheckScore: int = Field(default=50, ge=0, le=100, description="Score for external fact check verification (0-100)")
    externalFactCheckDetails: ExternalFactCheckResult | None = Field(default=None, description="Detailed external fact check results")
    fabricatedCitationsDetails: FabricatedCitationsDetails | None = Field(default=None, description="Detailed fabricated citations results")
    contradictoryInfoDetails: ContradictoryInfoDetails | None = Field(default=None, description="Detailed contradictory information results")
    multiLLMComparisonDetails: MultiLLMComparisonDetails | None = Field(default=None, description="Detailed multi-LLM comparison results")


class AccuracySubScore(BaseModel):
    """Schema for accuracy sub-score metrics."""

    googleBingWikipediaScore: int = Field(..., ge=0, le=10, description="Score for Google/Bing search Wikipedia verification (0-10)")
    verifiedDatabasesScore: int = Field(..., ge=0, le=10, description="Score for verified databases (medical, legal, financial, HR) (0-10)")
    internalCompanyDocsScore: int = Field(..., ge=0, le=10, description="Score for internal company docs verification (0-10)")


class MultiLLMConsensusSubScore(BaseModel):
    """Schema for multi-LLM consensus sub-score metrics."""

    fourModelAgree: float = Field(..., ge=0, le=100, description="Percentage of 4 model agreement (0-100)")
    twoModelDisagree: float = Field(..., ge=0, le=100, description="Percentage of 2 model disagreement (0-100)")


class DeviationMapSubScore(BaseModel):
    """Schema for deviation map sub-score metrics."""

    sentenceLevelComparison: float = Field(..., ge=0, le=100, description="Percentage of sentence-level comparison (0-100)")
    highlightedDifferences: float = Field(..., ge=0, le=100, description="Percentage of highlighted differences (0-100)")
    colorCodedConflictAreas: float = Field(..., ge=0, le=100, description="Percentage of color-coded conflict areas (0-100)")


class SourceAuthenticitySubScore(BaseModel):
    """Schema for source authenticity checker sub-score metrics."""

    verifiesPapersExist: bool = Field(..., description="Whether papers existence is verified (Yes/No)")
    detectsFakeCitations: bool = Field(..., description="Whether fake citations are detected (Yes/No)")
    confirmsLegalReferences: bool = Field(..., description="Whether legal references are confirmed (Yes/No)")


class ComplianceRule(BaseModel):
    """Schema for individual compliance rule evaluation."""

    module: str = Field(..., description="Compliance module (gdpr, eu_ai_act, responsible_ai, iso_42001, hipaa, soc2_ai)")
    rule_name: str = Field(..., description="Name/description of the rule")
    status: str = Field(..., description="Rule status: passed or violated")
    severity: str = Field(default="low", description="Severity if violated: low, medium, or high")
    text: str = Field(default="", description="Relevant text from response")
    explanation: str = Field(default="", description="Explanation of why rule passed or was violated")


class ComplianceModuleScore(BaseModel):
    """Schema for per-module compliance score."""

    module: str = Field(..., description="Compliance module name")
    score: int = Field(..., ge=0, le=10, description="Module compliance score (0-10)")
    passed_rules: int = Field(default=0, ge=0, description="Number of passed rules")
    violated_rules: int = Field(default=0, ge=0, description="Number of violated rules")
    high_risk_violations: int = Field(default=0, ge=0, description="Number of high-risk violations")


class ComplianceSummary(BaseModel):
    """Schema for compliance summary statistics."""

    total_rules: int = Field(default=0, ge=0, description="Total number of rules checked")
    passed_rules: int = Field(default=0, ge=0, description="Number of passed rules")
    violated_rules: int = Field(default=0, ge=0, description="Number of violated rules")
    high_risk_violations: int = Field(default=0, ge=0, description="Number of high-risk violations")


class ComplianceDetails(BaseModel):
    """Schema for comprehensive compliance analysis."""

    sub_score_name: str = Field(default="Compliance Score", description="Name of the sub-score")
    score: int = Field(..., ge=0, le=10, description="Overall compliance score (0-10)")
    module_scores: dict[str, int] = Field(default_factory=dict, description="Per-module scores")
    rules: list[ComplianceRule] = Field(default_factory=list, description="List of all compliance rules evaluated")
    summary: ComplianceSummary = Field(..., description="Summary statistics")
    explanation: str = Field(default="", description="Overall compliance assessment explanation")


class ComplianceSubScore(BaseModel):
    """Schema for compliance score sub-score metrics."""

    # Legacy fields (deprecated, kept for backward compatibility)
    checksUrlsExist: bool = Field(default=False, description="[DEPRECATED] Whether URLs existence is checked")
    verifiesPapersExist: bool = Field(default=False, description="[DEPRECATED] Whether papers existence is verified")
    detectsFakeCitations: bool = Field(default=False, description="[DEPRECATED] Whether fake citations are detected")
    confirmsLegalReferences: bool = Field(default=False, description="[DEPRECATED] Whether legal references are confirmed")
    
    # New compliance fields
    complianceDetails: ComplianceDetails | None = Field(default=None, description="Detailed regulatory compliance analysis")


class BiasInstance(BaseModel):
    """Schema for a single bias instance detected in the response."""

    type: str = Field(..., description="Type of bias (gender, racial, religious, political, cultural, age, disability, socioeconomic, sexual_orientation, other)")
    severity: str = Field(..., description="Severity level (low, medium, high)")
    text: str = Field(..., description="Exact biased statement from response")
    explanation: str = Field(..., description="Why this is biased and what stereotype it reinforces")
    category: str = Field(default="", description="Specific category if applicable (e.g., 'ability_stereotype', 'role_stereotype')")


class FairnessInstance(BaseModel):
    """Schema for a single fairness instance detected in the response."""

    type: str = Field(..., description="Type of fairness indicator (inclusivity, balanced_representation, equal_treatment, cultural_sensitivity, language_inclusivity)")
    strength: str = Field(..., description="Strength level (low, medium, high)")
    text: str = Field(..., description="Exact fair statement from response")
    explanation: str = Field(..., description="Why this demonstrates fairness and what positive indicator it shows")


class BiasSummary(BaseModel):
    """Schema for bias summary counts."""

    gender_bias_count: int = Field(default=0, ge=0, description="Number of gender bias instances")
    racial_bias_count: int = Field(default=0, ge=0, description="Number of racial bias instances")
    religious_bias_count: int = Field(default=0, ge=0, description="Number of religious bias instances")
    political_bias_count: int = Field(default=0, ge=0, description="Number of political bias instances")
    cultural_insensitivity_count: int = Field(default=0, ge=0, description="Number of cultural insensitivity instances")
    other_bias_count: int = Field(default=0, ge=0, description="Number of other bias instances")
    total_bias_count: int = Field(default=0, ge=0, description="Total number of bias instances")


class FairnessIndicators(BaseModel):
    """Schema for fairness indicator flags."""

    inclusivity: bool = Field(default=False, description="Whether high inclusivity is detected")
    balanced_representation: bool = Field(default=False, description="Whether balanced representation is detected")
    equal_treatment: bool = Field(default=False, description="Whether equal treatment is detected")
    cultural_sensitivity: bool = Field(default=False, description="Whether cultural sensitivity is detected")
    language_inclusivity: bool = Field(default=False, description="Whether inclusive language is detected")


class BiasFairnessDetails(BaseModel):
    """Schema for comprehensive bias and fairness detailed results."""

    sub_score_name: str = Field(default="Bias & Fairness", description="Name of the sub-score")
    score: int = Field(..., ge=0, le=10, description="Overall combined score (0-10, weighted combination of bias_score and fairness_score)")
    bias_score: int = Field(..., ge=0, le=10, description="Bias score (0-10, where 10=no bias)")
    fairness_score: int = Field(..., ge=0, le=10, description="Fairness score (0-10, where 10=high fairness)")
    overall_score: float = Field(..., ge=0, le=10, description="Overall score calculated as (bias_score × 0.6) + (fairness_score × 0.4)")
    bias_instances: list[BiasInstance] = Field(default_factory=list, description="List of specific bias instances detected")
    fairness_instances: list[FairnessInstance] = Field(default_factory=list, description="List of specific fairness instances detected")
    bias_summary: BiasSummary = Field(..., description="Summary of bias counts by type")
    fairness_indicators: FairnessIndicators = Field(..., description="Fairness indicator flags")
    explanation: str = Field(default="", description="Overall explanation of bias and fairness analysis")


class BiasFairnessSubScore(BaseModel):
    """Schema for bias & fairness score sub-score metrics."""

    genderBias: bool = Field(..., description="Whether gender bias is detected (Yes/No) - derived from bias_instances")
    racialBias: bool = Field(..., description="Whether racial bias is detected (Yes/No) - derived from bias_instances")
    religiousBias: bool = Field(..., description="Whether religious bias is detected (Yes/No) - derived from bias_instances")
    politicalBias: bool = Field(..., description="Whether political bias is detected (Yes/No) - derived from bias_instances")
    culturalInsensitivity: bool = Field(..., description="Whether cultural insensitivity is detected (Yes/No) - derived from bias_instances")
    biasFairnessDetails: BiasFairnessDetails | None = Field(default=None, description="Detailed bias analysis with all instances and explanations")


class SafetySubScore(BaseModel):
    """Schema for safety score sub-score metrics."""

    toxicity: float = Field(..., ge=0, le=100, description="Toxicity percentage (0-100)")
    hateSpeech: float = Field(..., ge=0, le=100, description="Hate speech percentage (0-100)")
    sexualContent: float = Field(..., ge=0, le=100, description="Sexual content percentage (0-100)")
    violence: float = Field(..., ge=0, le=100, description="Violence percentage (0-100)")
    dangerousInstructions: float = Field(..., ge=0, le=100, description="Dangerous instructions percentage (0-100)")
    selfHarmSuggestions: float = Field(..., ge=0, le=100, description="Self-harm suggestions percentage (0-100)")


class ContextAdherenceSubScore(BaseModel):
    """Schema for context adherence score sub-score metrics."""

    allInstructions: float = Field(..., ge=0, le=100, description="All instructions adherence percentage (0-100)")
    toneOfVoice: str = Field(..., description="Tone of voice (e.g., 'Polite', 'Professional', 'Casual')")
    lengthConstraints: str = Field(..., description="Length constraints adherence (e.g., 'Short', 'Medium', 'Long')")
    formatRules: float = Field(..., ge=0, le=100, description="Format rules adherence percentage (0-100)")
    brandVoice: float = Field(..., ge=0, le=100, description="Brand voice adherence percentage (0-100)")
    allInstructionsExplanation: Optional[str] = Field(None, description="Explanation for all instructions adherence score")
    toneOfVoiceExplanation: Optional[str] = Field(None, description="Explanation for tone of voice detection")
    lengthConstraintsExplanation: Optional[str] = Field(None, description="Explanation for length constraints assessment")
    formatRulesExplanation: Optional[str] = Field(None, description="Explanation for format rules adherence score")
    brandVoiceExplanation: Optional[str] = Field(None, description="Explanation for brand voice adherence score")


class StabilityRobustnessSubScore(BaseModel):
    """Schema for stability & robustness test sub-score metrics."""

    stability: float = Field(..., ge=0, le=100, description="Stability percentage (0-100)")


class PromptSensitivitySubScore(BaseModel):
    """Schema for prompt sensitivity test sub-score metrics."""

    sensitivity: float = Field(..., ge=0, le=100, description="Sensitivity percentage (0-100)")


class AISafetyGuardrailSubScore(BaseModel):
    """Schema for AI safety guardrail test sub-score metrics."""

    safetyScore: float = Field(..., ge=0, le=100, description="Safety score percentage (0-100)")


class AgentActionSafetySubScore(BaseModel):
    """Schema for agent action safety audit sub-score metrics."""

    safeActionScore: float = Field(..., ge=0, le=100, description="Safe Action Score percentage (0-100)")
    riskWarnings: float = Field(..., ge=0, le=100, description="Risk warnings percentage (0-100)")
    allowedBlockedDecisions: float = Field(..., ge=0, le=100, description="Allowed/Blocked decisions percentage (0-100)")


class VulnerabilityFinding(BaseModel):
    """Schema for individual vulnerability finding."""

    type: str = Field(..., description="Type of vulnerability")
    severity: Literal["low", "medium", "high", "critical"] = Field(..., description="Severity level")
    line: Optional[int] = Field(None, description="Line number (if applicable)")
    description: str = Field(..., description="Description of the vulnerability")
    recommendedFix: str = Field(..., description="Recommended fix")
    codeSnippet: Optional[str] = Field(None, description="Relevant code snippet")


class CodeVulnerabilityDetails(BaseModel):
    """Detailed code vulnerability analysis results."""

    sub_score_name: str = Field(default="Code Vulnerability Auditor", description="Sub-score name")
    score: int = Field(..., ge=0, le=10, description="Overall score (0-10)")
    riskLevel: Literal["low", "medium", "high", "critical"] = Field(..., description="Overall risk level")
    securityFlaws: List[VulnerabilityFinding] = Field(default_factory=list, description="Security flaw findings")
    outdatedLibraries: List[VulnerabilityFinding] = Field(default_factory=list, description="Outdated library findings")
    injectionRisks: List[VulnerabilityFinding] = Field(default_factory=list, description="Injection risk findings")
    logicErrors: List[VulnerabilityFinding] = Field(default_factory=list, description="Logic error findings")
    performanceIssues: List[VulnerabilityFinding] = Field(default_factory=list, description="Performance issue findings")
    recommendedFixes: List[str] = Field(default_factory=list, description="Aggregated recommended fixes")
    explanation: str = Field(default="", description="Overall explanation")


class CodeVulnerabilitySubScore(BaseModel):
    """Schema for code vulnerability auditor sub-score metrics."""

    securityFlaws: float = Field(..., ge=0, le=100, description="Security flaws percentage (0-100)")
    outdatedLibraries: float = Field(..., ge=0, le=100, description="Outdated libraries percentage (0-100)")
    injectionRisks: float = Field(..., ge=0, le=100, description="Injection risks percentage (0-100)")
    logicErrors: float = Field(..., ge=0, le=100, description="Logic errors percentage (0-100)")
    performanceIssues: float = Field(..., ge=0, le=100, description="Performance issues percentage (0-100)")
    codeVulnerabilityDetails: Optional[CodeVulnerabilityDetails] = Field(
        default=None, description="Detailed vulnerability findings with risk level and recommended fixes"
    )


class DataExtractionAccuracySubScore(BaseModel):
    """Schema for data extraction accuracy audit sub-score metrics."""

    compareExtractedTextWithGroundTruth: float = Field(..., ge=0, le=100, description="Compare extracted text with ground truth percentage (0-100)")
    detectExtractionErrors: float = Field(..., ge=0, le=100, description="Detect extraction errors percentage (0-100)")
    flagMismatchedValues: float = Field(..., ge=0, le=100, description="Flag mismatched values percentage (0-100)")


class BrandConsistencySubScore(BaseModel):
    """Schema for brand consistency audit sub-score metrics."""

    tone: float = Field(..., ge=0, le=100, description="Tone consistency percentage (0-100)")
    style: float = Field(..., ge=0, le=100, description="Style consistency percentage (0-100)")
    vocabulary: float = Field(..., ge=0, le=100, description="Vocabulary consistency percentage (0-100)")
    format: float = Field(..., ge=0, le=100, description="Format consistency percentage (0-100)")
    grammarLevel: float = Field(..., ge=0, le=100, description="Grammar level consistency percentage (0-100)")
    brandSafeLanguage: float = Field(..., ge=0, le=100, description="Brand-safe language percentage (0-100)")
    allowedBlockedDecisions: float = Field(..., ge=0, le=100, description="Allowed/Blocked decisions percentage (0-100)")


class AIPlagiarismSubScore(BaseModel):
    """Schema for AI output plagiarism checker sub-score metrics."""

    copiedSentences: float = Field(..., ge=0, le=100, description="Copied sentences percentage (0-100)")
    copiedNewsArticles: float = Field(..., ge=0, le=100, description="Copied news articles percentage (0-100)")
    copiedBooks: float = Field(..., ge=0, le=100, description="Copied books percentage (0-100)")
    copiedCopyrightedText: float = Field(..., ge=0, le=100, description="Copied copyrighted text percentage (0-100)")


class MultiJudgeAIReviewSubScore(BaseModel):
    """Schema for multi-judge AI review sub-score metrics."""

    modelVoting: float = Field(..., ge=0, le=100, description="Model voting percentage (0-100)")
    modelScoring: float = Field(..., ge=0, le=100, description="Model scoring percentage (0-100)")
    modelCritiques: float = Field(..., ge=0, le=100, description="Model critiques percentage (0-100)")


class ReasoningQualitySubScore(BaseModel):
    """Schema for reasoning quality score sub-score metrics."""

    stepByStepReasoning: int = Field(..., ge=0, le=10, description="Score for step-by-step reasoning quality (0-10)")
    logicalConsistency: int = Field(..., ge=0, le=10, description="Score for logical consistency (0-10)")
    missingSteps: int = Field(..., ge=0, le=10, description="Score for missing steps detection (0-10)")
    wrongLogic: int = Field(..., ge=0, le=10, description="Score for wrong logic detection (0-10)")


class ExplainabilitySubScore(BaseModel):
    """Schema for explainability score sub-score metrics."""

    explainabilityScore: float = Field(..., ge=0, le=100, description="Explainability Score percentage (0-100)")
    copiedSentences: float = Field(..., ge=0, le=100, description="Copied sentences percentage (0-100)")


class AuditScore(BaseModel):
    """Schema for individual audit score."""

    name: str = Field(..., description="Score name (e.g., 'Hallucination Score')")
    value: int = Field(..., ge=0, le=10, description="Score value (0-10)")
    maxValue: int = Field(default=10, description="Maximum possible score")
    category: str = Field(..., description="Category grouping (e.g., 'Accuracy', 'Safety')")
    explanation: str = Field(default="", description="Detailed explanation of why this score was assigned")
    subScores: Optional[Union[
        HallucinationSubScore,
        AccuracySubScore,
        MultiLLMConsensusSubScore,
        DeviationMapSubScore,
        SourceAuthenticitySubScore,
        ComplianceSubScore,
        BiasFairnessSubScore,
        SafetySubScore,
        ContextAdherenceSubScore,
        StabilityRobustnessSubScore,
        PromptSensitivitySubScore,
        AISafetyGuardrailSubScore,
        AgentActionSafetySubScore,
        CodeVulnerabilitySubScore,
        DataExtractionAccuracySubScore,
        BrandConsistencySubScore,
        AIPlagiarismSubScore,
        MultiJudgeAIReviewSubScore,
        ReasoningQualitySubScore,
        ExplainabilitySubScore,
        CodeVulnerabilityDetails
    ]] = Field(None, description="Sub-scores for detailed metrics (varies by score type)")
    # Note: isCritical can be computed from value <= 4, so it's redundant and removed


class AuditorDetailedScores(BaseModel):
    """Schema for detailed audit scores from an auditor."""

    auditorId: str = Field(..., description="Platform ID (e.g., 'openai')")
    auditorName: str = Field(..., description="Platform display name (e.g., 'OpenAI')")
    overallScore: int = Field(..., ge=0, le=10, description="Average of all scores (0-10)")
    scores: List[AuditScore] = Field(..., description="Array of 20 audit scores")


class JudgeEvaluation(BaseModel):
    """Schema for Judge LLM evaluation results."""

    scores: JudgmentScores = Field(..., description="Individual criterion scores (0-10)")
    trustScore: float = Field(..., ge=0.0, le=10.0, description="Weighted trust score (0-10)")
    fallbackApplied: bool = Field(default=False, description="Whether fallback scoring was used")
    weights: Dict[str, float] = Field(default_factory=dict, description="Weights used for trust score calculation")


class PlatformResult(BaseModel):
    """Schema for platform comparison result."""

    id: str = Field(..., description="Platform ID")
    name: str = Field(..., description="Platform display name")
    score: int = Field(..., ge=60, le=100, description="Overall comparison score (60-100)")
    response: str = Field(..., description="Full text response from the platform")
    detailedScores: AuditorDetailedScores = Field(..., description="Detailed audit scores")
    topReasons: List[str] = Field(..., min_length=5, max_length=5, description="Array of 5 winning reasons")
    judgeEvaluation: Optional[JudgeEvaluation] = Field(None, description="Judge LLM evaluation metrics")


class ComparisonResponse(BaseModel):
    """Schema for comparison response."""

    comparisonId: str = Field(..., description="Comparison ID")
    messageId: str = Field(..., description="Message ID")
    prompt: str = Field(..., description="The prompt that was compared")
    timestamp: datetime = Field(..., description="Timestamp in ISO 8601 format")
    status: Literal["processing", "completed", "failed", "queued"] = Field(..., description="Comparison status")
    judge: Dict[str, str] = Field(..., description="Judge platform info with id and name")
    platforms: List[PlatformResult] = Field(..., description="List of platform results")
    sortedBy: str = Field(default="score", description="Sorting method")
    winner: Dict[str, Any] = Field(..., description="Winner platform info with id, name, and score")


class ComparisonStatusResponse(BaseModel):
    """Schema for comparison status response."""

    comparisonId: str = Field(..., description="Comparison ID")
    status: Literal["processing", "completed", "failed", "queued"] = Field(..., description="Comparison status")
    progress: int = Field(..., ge=0, le=100, description="Progress percentage")
    estimatedTimeRemaining: Optional[int] = Field(None, description="Estimated time remaining in seconds")
    completedPlatforms: Optional[List[str]] = Field(None, description="List of completed platform IDs")
    pendingPlatforms: Optional[List[str]] = Field(None, description="List of pending platform IDs")


# Similarity Analysis Schemas


class SimilarityMatrixEntry(BaseModel):
    """Schema for a single entry in similarity matrix."""

    provider_id: str = Field(..., description="Provider ID")
    similarities: Dict[str, float] = Field(..., description="Similarity scores to all other providers")


class ConsensusScoreEntry(BaseModel):
    """Schema for a single consensus score entry."""

    provider_id: str = Field(..., description="Provider ID")
    score: float = Field(..., ge=0.0, le=1.0, description="Consensus score (0-1)")
    is_outlier: bool = Field(default=False, description="Whether this provider is an outlier")


class OutlierDetail(BaseModel):
    """Schema for detailed outlier information."""

    id: str = Field(..., description="Provider ID")
    consensus_score: float = Field(..., description="Consensus score")
    deviation_from_mean: float = Field(..., description="Deviation from mean consensus score")
    deviation_in_std: float = Field(..., description="Deviation in standard deviations")
    avg_similarity_to_others: Optional[float] = Field(None, description="Average similarity to other providers")


class SimilarityStatistics(BaseModel):
    """Schema for similarity statistics."""

    mean: float = Field(..., description="Mean consensus score")
    std_dev: float = Field(..., description="Standard deviation of consensus scores")
    min: float = Field(..., description="Minimum consensus score")
    max: float = Field(..., description="Maximum consensus score")
    count: int = Field(..., description="Number of responses analyzed")


class SimilarityAnalysisResponse(BaseModel):
    """Schema for similarity analysis response."""

    request_id: str = Field(..., description="Request ID used to group responses")
    similarity_matrix: Dict[str, Dict[str, float]] = Field(
        ..., description="Full similarity matrix (provider_id -> {provider_id -> similarity})"
    )
    consensus_scores: Dict[str, float] = Field(
        ..., description="Consensus scores for each provider"
    )
    outliers: List[str] = Field(default_factory=list, description="List of outlier provider IDs")
    outlier_threshold: Optional[float] = Field(None, description="Threshold used for outlier detection")
    statistics: SimilarityStatistics = Field(..., description="Statistical summary")
    outlier_details: List[OutlierDetail] = Field(
        default_factory=list, description="Detailed information about outliers"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of the analysis")


class ProcessSimilarityRequest(BaseModel):
    """Request model for processing similarity analysis."""

    request_id: str = Field(..., description="Request ID to process (must have existing LLM responses)")
    persist: bool = Field(default=True, description="Whether to persist results to database")


# Streaming Event Schemas for SSE

# Streaming Event Types
StreamingEventType = Literal[
    "stream_connected",
    "processing_started",
    "response_started",
    "response_chunk",
    "response_complete",
    "similarity_analysis_started",
    "similarity_analysis_complete",
    "audit_scores_started",
    "audit_score",
    "audit_scores_complete",
    "judge_started",
    "judge_chunk",
    "judge_parameter",
    "judge_complete",
    "progress",
    "comparison_complete",
    "error",
]


class StreamingEvent(BaseModel):
    """Base schema for streaming events."""
    
    type: str = Field(..., description="Event type")
    platform_id: Optional[str] = Field(None, description="Platform ID (if applicable)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")
    data: Dict[str, Any] = Field(..., description="Event-specific data")
    
    def to_sse_format(self) -> str:
        """Convert event to Server-Sent Events format."""
        import json
        event_data = {
            "type": self.type,
            "platform_id": self.platform_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }
        return f"data: {json.dumps(event_data)}\n\n"


class ResponseChunkEvent(BaseModel):
    """Event for response text chunks."""
    
    platform_id: str
    chunk: str
    accumulated_text: str = Field(..., description="Full text accumulated so far")
    is_complete: bool = False


class ResponseCompleteEvent(BaseModel):
    """Event when a platform response is complete."""
    
    platform_id: str
    response: str
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None


class JudgeParameterEvent(BaseModel):
    """Event for individual judge parameter."""
    
    platform_id: str
    parameter_name: str
    value: Union[int, float]
    accumulated_scores: Dict[str, Union[int, float]] = Field(..., description="All scores calculated so far")


class JudgeCompleteEvent(BaseModel):
    """Event when judge evaluation is complete."""
    
    platform_id: str
    scores: JudgmentScores
    trust_score: float
    fallback_applied: bool
