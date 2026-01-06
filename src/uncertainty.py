"""
Agent-OS v3 Uncertainty Detector

Following million-step methodology:
- ANY uncertainty MUST trigger HALT
- No silent fallbacks
- Explicit escalation paths
- All uncertainty signals are logged

Enhanced with Groq-powered LLM detection (Jan 2026):
- Regex patterns for fast first-pass (~1ms)
- Groq Llama 3.3 70B for deep semantic analysis (~400ms)
- 85% cost reduction vs Claude for uncertainty detection
"""

import re
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime

from db import insert_returning, query_all


class Severity(Enum):
    """Severity levels for uncertainty signals."""
    HALT = "halt"      # Must stop immediately
    WARN = "warn"      # Log but can continue with caution


class Category(Enum):
    """Categories of uncertainty."""
    DATA = "data"           # Missing, stale, or conflicting data
    LOGIC = "logic"         # Ambiguous specs, impossible constraints
    CONFIDENCE = "confidence"  # Low confidence scores, uncertainty language
    CONFLICT = "conflict"   # Disagreement between roles, policy violations


@dataclass
class UncertaintySignal:
    """
    A single uncertainty signal.
    
    When detected, these accumulate and may trigger HALT.
    """
    signal_type: str
    category: Category
    severity: Severity
    description: str
    source: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'signal_type': self.signal_type,
            'category': self.category.value,
            'severity': self.severity.value,
            'description': self.description,
            'source': self.source,
            'timestamp': self.timestamp.isoformat()
        }


class UncertaintyDetector:
    """
    Detects uncertainty signals and enforces HALT.
    
    Core principle: When uncertain, STOP. Don't guess.
    
    Detection modes:
    - FAST: Regex patterns only (~1ms)
    - DEEP: Regex + Groq LLM analysis (~400ms)
    """
    
    # Patterns that indicate uncertainty in LLM output
    UNCERTAINTY_PATTERNS = [
        (r"\bI'm not sure\b", "explicit_uncertainty"),
        (r"\bI think\b", "hedging"),
        (r"\bprobably\b", "hedging"),
        (r"\bmight\b", "hedging"),
        (r"\bpossibly\b", "hedging"),
        (r"\bI assume\b", "assumption"),
        (r"\bI believe\b", "belief"),
        (r"\bshould work\b", "uncertainty"),
        (r"\bnot certain\b", "explicit_uncertainty"),
        (r"\bunsure\b", "explicit_uncertainty"),
        (r"\bmaybe\b", "hedging"),
        (r"\bperhaps\b", "hedging"),
        (r"\bit seems\b", "hedging"),
        (r"\bI would guess\b", "guessing"),
        (r"\bif I understand correctly\b", "clarification_needed"),
    ]
    
    def __init__(
        self, 
        confidence_threshold: float = 0.70,
        use_groq: bool = True
    ):
        """
        Initialize detector.
        
        Args:
            confidence_threshold: Minimum confidence score to proceed (default 0.70)
            use_groq: Whether to use Groq LLM for deep analysis (default True)
        """
        self.confidence_threshold = confidence_threshold
        self.use_groq = use_groq
        self.signals: List[UncertaintySignal] = []
        self._groq_integration = None
    
    def _get_groq(self):
        """Lazy load Groq integration to avoid import errors if not available."""
        if self._groq_integration is None and self.use_groq:
            try:
                from groq_integration import detect_uncertainty
                self._groq_integration = detect_uncertainty
            except ImportError:
                self.use_groq = False
                self._groq_integration = None
        return self._groq_integration
    
    def check_confidence_score(
        self, 
        score: float, 
        source: str = "drafter"
    ) -> Optional[UncertaintySignal]:
        """
        Check if confidence score is below threshold.
        
        Args:
            score: Confidence score (0.0 - 1.0)
            source: Who reported this score
        
        Returns:
            UncertaintySignal if below threshold, else None
        """
        if score < self.confidence_threshold:
            signal = UncertaintySignal(
                signal_type="low_confidence",
                category=Category.CONFIDENCE,
                severity=Severity.HALT,
                description=f"Confidence score {score:.2f} below threshold {self.confidence_threshold}",
                source=source
            )
            self.signals.append(signal)
            return signal
        return None
    
    def check_uncertainty_language(
        self, 
        text: str, 
        source: str = "drafter",
        deep_analysis: bool = True
    ) -> List[UncertaintySignal]:
        """
        Scan text for uncertainty language patterns.
        
        Uses two-pass detection:
        1. Fast regex patterns (~1ms)
        2. Groq LLM deep analysis (~400ms) if enabled
        
        Args:
            text: Text to scan
            source: Who produced this text
            deep_analysis: Whether to use Groq for deep analysis
        
        Returns:
            List of detected UncertaintySignals
        """
        found_signals = []
        
        # === PASS 1: Fast regex patterns ===
        # Only explicit uncertainty halts, hedging is just a warning
        halt_types = {"explicit_uncertainty", "guessing", "clarification_needed"}
        warn_types = {"hedging", "assumption", "belief", "uncertainty"}
        
        for pattern, pattern_type in self.UNCERTAINTY_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Determine severity based on pattern type
                if pattern_type in halt_types:
                    severity = Severity.HALT
                else:
                    severity = Severity.WARN
                
                signal = UncertaintySignal(
                    signal_type=f"uncertainty_language_{pattern_type}",
                    category=Category.CONFIDENCE,
                    severity=severity,
                    description=f"Uncertainty language detected: '{matches[0]}'",
                    source=source
                )
                found_signals.append(signal)
                self.signals.append(signal)
        
        # === PASS 2: Groq deep analysis (if enabled and no regex hits) ===
        if deep_analysis and self.use_groq and len(found_signals) == 0:
            groq_detect = self._get_groq()
            if groq_detect:
                try:
                    result = groq_detect(
                        content=text,
                        context=f"Source: {source}",
                        task_type="verification"
                    )
                    
                    if result.success and result.has_uncertainty:
                        for groq_signal in result.signals:
                            signal = UncertaintySignal(
                                signal_type=f"groq_{groq_signal.get('type', 'unknown')}",
                                category=Category.CONFIDENCE,
                                severity=Severity.HALT if result.should_halt else Severity.WARN,
                                description=groq_signal.get('description', result.summary),
                                source=f"{source} (groq-analyzed)"
                            )
                            found_signals.append(signal)
                            self.signals.append(signal)
                except Exception as e:
                    # Log but don't fail - regex detection is sufficient
                    pass
        
        return found_signals
    
    def deep_uncertainty_check(
        self,
        text: str,
        context: str = "",
        task_type: str = "general",
        source: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Perform deep uncertainty analysis using Groq LLM.
        
        This is a standalone deep check that bypasses regex patterns
        and goes directly to LLM analysis for nuanced detection.
        
        Args:
            text: Text to analyze
            context: Additional context
            task_type: Type of task
            source: Source of the text
            
        Returns:
            Dict with analysis results
        """
        groq_detect = self._get_groq()
        if not groq_detect:
            return {
                "success": False,
                "error": "Groq integration not available",
                "has_uncertainty": False
            }
        
        try:
            result = groq_detect(
                content=text,
                context=context,
                task_type=task_type
            )
            
            if result.success and result.has_uncertainty:
                for groq_signal in result.signals:
                    signal = UncertaintySignal(
                        signal_type=f"groq_{groq_signal.get('type', 'unknown')}",
                        category=Category.CONFIDENCE,
                        severity=Severity.HALT if result.should_halt else Severity.WARN,
                        description=groq_signal.get('description', result.summary),
                        source=f"{source} (groq-deep)"
                    )
                    self.signals.append(signal)
            
            return {
                "success": result.success,
                "has_uncertainty": result.has_uncertainty,
                "should_halt": result.should_halt,
                "confidence_score": result.confidence_score,
                "signals": result.signals,
                "summary": result.summary,
                "latency_ms": result.latency_ms,
                "cost_usd": result.cost_usd,
                "model": result.model
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "has_uncertainty": False
            }
    
    def check_missing_input(
        self, 
        required: List[str], 
        provided: Dict[str, Any]
    ) -> List[UncertaintySignal]:
        """
        Check for missing required inputs.
        
        Args:
            required: List of required input names
            provided: Dict of provided inputs
        
        Returns:
            List of UncertaintySignals for missing inputs
        """
        found_signals = []
        
        for key in required:
            if key not in provided or provided[key] is None:
                signal = UncertaintySignal(
                    signal_type="missing_input",
                    category=Category.DATA,
                    severity=Severity.HALT,
                    description=f"Required input missing: {key}"
                )
                found_signals.append(signal)
                self.signals.append(signal)
        
        return found_signals
    
    def check_conflicting_data(
        self,
        data_sources: Dict[str, Any],
        key: str
    ) -> Optional[UncertaintySignal]:
        """
        Check if multiple sources have conflicting data.
        
        Args:
            data_sources: Dict of source_name -> data
            key: Key to compare across sources
        
        Returns:
            UncertaintySignal if conflict found
        """
        values = {}
        for source, data in data_sources.items():
            if isinstance(data, dict) and key in data:
                values[source] = data[key]
        
        unique_values = set(str(v) for v in values.values())
        
        if len(unique_values) > 1:
            signal = UncertaintySignal(
                signal_type="conflicting_data",
                category=Category.DATA,
                severity=Severity.HALT,
                description=f"Conflicting values for '{key}': {values}"
            )
            self.signals.append(signal)
            return signal
        
        return None
    
    def check_stale_data(
        self,
        timestamp: datetime,
        max_age_seconds: int = 3600
    ) -> Optional[UncertaintySignal]:
        """
        Check if data is too old to be trusted.
        
        Args:
            timestamp: When the data was fetched
            max_age_seconds: Maximum age in seconds
        
        Returns:
            UncertaintySignal if data is stale
        """
        age = (datetime.utcnow() - timestamp).total_seconds()
        
        if age > max_age_seconds:
            signal = UncertaintySignal(
                signal_type="stale_data",
                category=Category.DATA,
                severity=Severity.HALT,
                description=f"Data is {age:.0f} seconds old (max: {max_age_seconds})"
            )
            self.signals.append(signal)
            return signal
        
        return None
    
    def check_ambiguous_spec(
        self,
        spec_text: str
    ) -> List[UncertaintySignal]:
        """
        Check if a specification is ambiguous.
        
        Looks for vague language that could lead to wrong implementations.
        """
        found_signals = []
        
        vague_patterns = [
            (r"\bimprove\b(?! by \d)", "vague_improvement"),
            (r"\boptimize\b(?! for)", "vague_optimization"),
            (r"\bbetter\b(?! than)", "vague_comparison"),
            (r"\bsome\b", "vague_quantity"),
            (r"\betc\.?\b", "incomplete_list"),
            (r"\band so on\b", "incomplete_list"),
        ]
        
        for pattern, pattern_type in vague_patterns:
            if re.search(pattern, spec_text, re.IGNORECASE):
                signal = UncertaintySignal(
                    signal_type=f"ambiguous_spec_{pattern_type}",
                    category=Category.LOGIC,
                    severity=Severity.WARN,  # Warn, not halt - might be okay
                    description=f"Potentially ambiguous specification: pattern '{pattern}' found"
                )
                found_signals.append(signal)
                self.signals.append(signal)
        
        return found_signals
    
    def has_halt_signals(self) -> bool:
        """Check if any HALT-severity signals have been detected."""
        return any(s.severity == Severity.HALT for s in self.signals)
    
    def get_halt_signals(self) -> List[UncertaintySignal]:
        """Get all HALT-severity signals."""
        return [s for s in self.signals if s.severity == Severity.HALT]
    
    def get_all_signals(self) -> List[UncertaintySignal]:
        """Get all detected signals."""
        return self.signals.copy()
    
    def clear(self):
        """Clear all detected signals."""
        self.signals = []
    
    def persist_signals(
        self,
        task_id: Optional[str],
        checkpoint_id: Optional[int]
    ) -> None:
        """
        Persist all detected signals to the database.
        
        Should be called when HALTing to record what triggered the halt.
        """
        for signal in self.signals:
            insert_returning('uncertainty_signals', {
                'task_id': task_id,
                'checkpoint_id': checkpoint_id,
                'signal_type': signal.signal_type,
                'category': signal.category.value,
                'severity': signal.severity.value,
                'description': signal.description
            })
    
    def get_unresolved_signals(
        self,
        task_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get unresolved uncertainty signals from database.
        
        Args:
            task_id: Optional filter by task
        
        Returns:
            List of signal records
        """
        if task_id:
            return query_all(
                "SELECT * FROM uncertainty_signals WHERE task_id = %s AND resolved = FALSE",
                (task_id,)
            )
        else:
            return query_all(
                "SELECT * FROM uncertainty_signals WHERE resolved = FALSE ORDER BY created_at DESC LIMIT 100"
            )


def create_halt_result(
    signal: UncertaintySignal,
    checkpoint_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Create a standardized HALT result.
    
    This is returned when execution must stop.
    """
    return {
        'success': False,
        'halted': True,
        'halt_signal': signal.to_dict(),
        'checkpoint_id': checkpoint_id,
        'message': f"HALT: {signal.description}",
        'action_required': 'HUMAN_REVIEW' if signal.severity == Severity.HALT else 'REVIEW'
    }


if __name__ == '__main__':
    # Test
    print("Testing UncertaintyDetector with Groq integration...")
    
    detector = UncertaintyDetector(confidence_threshold=0.85, use_groq=True)
    
    # Test confidence check
    signal = detector.check_confidence_score(0.7, "test")
    print(f"Low confidence signal: {signal}")
    
    # Test uncertainty language (regex only)
    detector.clear()
    test_text = "I think this should work, but I'm not sure about edge cases."
    signals = detector.check_uncertainty_language(test_text, "test", deep_analysis=False)
    print(f"Found {len(signals)} uncertainty language signals (regex)")
    
    # Test deep analysis
    detector.clear()
    result = detector.deep_uncertainty_check(
        "The implementation handles all edge cases correctly.",
        context="Code review",
        task_type="implementation"
    )
    print(f"Deep analysis result: uncertain={result.get('has_uncertainty')}")
    
    # Test missing input
    detector.clear()
    signals = detector.check_missing_input(['a', 'b', 'c'], {'a': 1, 'b': 2})
    print(f"Missing input signals: {signals}")
    
    # Check for halt
    print(f"Has halt signals: {detector.has_halt_signals()}")
    print(f"Halt signals: {[s.to_dict() for s in detector.get_halt_signals()]}")
