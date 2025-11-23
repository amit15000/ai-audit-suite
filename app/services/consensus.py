from __future__ import annotations

from typing import List

from app.models import (
    AdapterAuditArtifact,
    ConsensusContributor,
    ConsensusOutput,
)


class ConsensusEngine:
    def build(self, artifacts: List[AdapterAuditArtifact]) -> ConsensusOutput:
        summary_parts = []
        contributors: List[ConsensusContributor] = []
        citations: List[str] = []

        for artifact in artifacts:
            summary_parts.append(
                f"{artifact.adapter_id}: accuracy={artifact.scores.accuracy}, "
                f"safety={artifact.scores.safety}"
            )
            contributors.append(
                ConsensusContributor(
                    adapter_id=artifact.adapter_id,
                    evidence=f"artifact:{artifact.adapter_id}",
                )
            )
            citations.extend(artifact.citations or [f"artifact:{artifact.adapter_id}"])

        summary = "; ".join(summary_parts) if summary_parts else "No artifacts."

        return ConsensusOutput(
            summary=summary,
            contributors=contributors,
            citations=list(dict.fromkeys(citations)),
        )

