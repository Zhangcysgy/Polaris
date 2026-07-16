"""引擎二 — 深度理论验证

Polaris 的"审查系统"——跨领域专家模拟审查 + 方法论溯源 + 红队模式 + 竞争假设 + 敏感性热图。
"""

from .trace import MethodologyTracer, TraceReport, AssumptionCheck
from .redteam import RedTeamReviewer, RedTeamReport, RedTeamFinding
from .debate import MultiExpertDebate, DebateReport, ExpertOpinion, DebatePoint
from .competition import CompetitionHypothesis, CompetitionReport, CompetitionModel
from .sensitivity import SensitivityHeatmap, SensitivityReport, SensitivityResult
from .orchestrator import ReviewOrchestrator, ReviewResult

__all__ = [
    "MethodologyTracer", "TraceReport", "AssumptionCheck",
    "RedTeamReviewer", "RedTeamReport", "RedTeamFinding",
    "MultiExpertDebate", "DebateReport", "ExpertOpinion", "DebatePoint",
    "CompetitionHypothesis", "CompetitionReport", "CompetitionModel",
    "SensitivityHeatmap", "SensitivityReport", "SensitivityResult",
    "ReviewOrchestrator", "ReviewResult",
]
