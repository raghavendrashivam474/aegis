# P2.S2 — Anomaly & Degradation Detection: Requirements

> **Phase:** 2 (Intelligence Layer)
> **Sprint:** S2 (Anomaly & Degradation Detection)
> **Baseline:** P2.S1 complete (92 passed, 4 skipped)
> **Status:** DRAFT → FINAL

---

## 1. Context & Objective
While P2.S1 assesses overall asset health and operational state ("What is the asset condition?"), P2.S2 establishes the anomaly and progressive degradation detection engine ("Is current behavior abnormal or degrading, why, and how severely?").

The detector must:
1. Provide explainable, multi-signal evidence for every flagged anomaly (no black-box LLM dependencies).
2. Measure anomaly score ($0.0 \dots 1.0$), confidence ($0.0 \dots 1.0$), and structured severity (`NONE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
3. Evaluate detection metrics against NASA C-MAPSS ground-truth failure trajectories (Precision, Recall, Detection Lead Time).

---

## 2. Architecture & Data Structures

### 2.1 Domain Types (`packages/domain/intelligence.py`)
```python
class AnomalyStatus(StrEnum):
    NOMINAL = "NOMINAL"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    DEGRADATION_DETECTED = "DEGRADATION_DETECTED"
    UNKNOWN = "UNKNOWN"

class AnomalySeverity(StrEnum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

@dataclass(frozen=True)
class SignalEvidence:
    sensor_id: str
    measurement_type: str
    deviation_sigma: float
    trend: TrendDirection
    persistence_count: int
    contribution_score: float
    reason: str

@dataclass(frozen=True)
class AnomalyDetectionResult:
    asset_id: str
    device_id: str
    status: AnomalyStatus
    anomaly_score: float         # 0.0 to 1.0
    confidence: float            # 0.0 to 1.0
    severity: AnomalySeverity
    evidence_list: tuple[SignalEvidence, ...]
    evaluated_at: datetime
    detection_method: str
    lead_cycles_estimate: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
3. Detection Methodology: Explainable Multivariate Deviation & Persistence
3.1 Persistence & Statistical Robustness
Transient noise rejection: An individual observation exceeding 
3
σ
3σ is flagged as transient if it does not persist across at least 
K
K consecutive evaluation cycles (
K
=
3
K=3 default).
Progressive degradation detection: Consistent multi-sensor drift (>2.0σ on 
≥
2
≥2 sensors with monotonic trend) triggers DEGRADATION_DETECTED.
Severity assignment:
NONE: Anomaly score 
<
0.25
<0.25
LOW: 
0.25
≤
score
<
0.50
0.25≤score<0.50 (1 sensor deviating slightly)
MEDIUM: 
0.50
≤
score
<
0.75
0.50≤score<0.75 (2 sensors deviating or persistent drift)
HIGH: 
0.75
≤
score
<
0.90
0.75≤score<0.90 (multi-sensor persistent degradation)
CRITICAL: 
score
≥
0.90
score≥0.90 (widespread severe subsystem deviation)
4. Requirements & Scenarios Matrix
Requirement ID    Scenario    Description    Target Evaluation Metric
REQ-P2-S2-001    S2-NORMAL    Nominal operation produces NOMINAL status    False Positive Rate 
<
5
%
<5%
REQ-P2-S2-002    S2-EARLY-DEGRADATION    Early degradation signal flagged with low/medium severity    Confidence calibrated, no false certainty
REQ-P2-S2-003    S2-CLEAR-DEGRADATION    Late stage failure trajectory detected with HIGH/CRITICAL severity    Recall 
>
95
%
>95% on end-of-life windows
REQ-P2-S2-004    S2-NOISY-DATA    White noise / sensor jitter does not trigger false anomalies    Stable anomaly score
REQ-P2-S2-005    S2-MISSING-DATA    Gaps in telemetry reduce detection confidence appropriately    Confidence penalty
REQ-P2-S2-006    S2-RECOVERY    Returning to nominal bounds transitions status back to NOMINAL    Zero false latching
REQ-P2-S2-007    S2-REPLAY    Replay of same dataset yields deterministic detection    100% deterministic
REQ-P2-S2-008    S2-GROUND-TRUTH-CMAPSS    Evaluation across full C-MAPSS FD001 fleet lifecycle    Precision, Recall, Mean Lead Time measured
