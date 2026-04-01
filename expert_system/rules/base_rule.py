"""Base rule interface for expert system."""

from abc import ABC, abstractmethod
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext


class BaseRule(ABC):
    """
    Abstract base class for all clinical decision rules.

    Each rule implements:
    - condition: checks if rule should fire
    - action: modifies decision context when rule fires
    - explanation: provides human-readable reasoning
    """

    def __init__(self):
        """Initialize rule with name and category."""
        self.name = self.__class__.__name__
        self.category = "general"
        self.enabled = True

    @abstractmethod
    def condition(self, patient: PatientContext) -> bool:
        """
        Evaluate if this rule's condition is met.

        Args:
            patient: Patient clinical context

        Returns:
            True if rule should fire, False otherwise
        """

    @abstractmethod
    def action(self, patient: PatientContext, decision: DecisionContext) -> None:
        """
        Execute rule action - modify decision context.

        Args:
            patient: Patient clinical context
            decision: Decision context to modify
        """

    @abstractmethod
    def explanation(self, patient: PatientContext) -> str:
        """
        Generate human-readable explanation for why rule fired.

        Args:
            patient: Patient clinical context

        Returns:
            Explanation string
        """

    def evaluate(self, patient: PatientContext, decision: DecisionContext) -> bool:
        """
        Evaluate rule: check condition, execute action if met, add explanation.

        Args:
            patient: Patient clinical context
            decision: Decision context to modify

        Returns:
            True if rule fired, False otherwise
        """
        if not self.enabled:
            return False

        if self.condition(patient):
            self.action(patient, decision)
            decision.add_explanation(self.explanation(patient))
            return True

        return False

    def __repr__(self) -> str:
        return f"<Rule: {self.name} (category: {self.category}, enabled: {self.enabled})>"
