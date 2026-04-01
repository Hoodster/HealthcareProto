"""Rule engine for evaluating patient context against clinical rules."""

from typing import List, Optional
import logging

from expert_system.rules.base_rule import BaseRule
from expert_system.models.patient_context import PatientContext
from expert_system.models.decision_context import DecisionContext

# Import concrete rules
from expert_system.rules.qtc_rules import HighQTcRule, ModerateQTcRule, MildQTcRule
from expert_system.rules.renal_rules import (
    SevereRenalImpairmentRule,
    ModerateRenalImpairmentRule,
    MildRenalImpairmentRule
)
from expert_system.rules.interaction_rules import (
    QTProlongingDrugInteractionRule,
    CYPInhibitorInteractionRule,
    BetaBlockerInteractionRule
)

logger = logging.getLogger(__name__)


class RuleEngine:
    """
    Rule-based decision engine for drug safety evaluation.

    Evaluates patient context against a set of clinical rules and generates
    a decision with alerts, explanations, and recommendations.
    """

    def __init__(self, rules: Optional[List[BaseRule]] = None):
        """
        Initialize rule engine with rules.

        Args:
            rules: List of rules to evaluate. If None, uses default ruleset.
        """
        if rules is None:
            self.rules = self._load_default_rules()
        else:
            self.rules = rules

        logger.info(f"RuleEngine initialized with {len(self.rules)} rules")

    def _load_default_rules(self) -> List[BaseRule]:
        """Load default clinical ruleset."""
        return [
            # QTc rules (order by severity)
            HighQTcRule(),
            ModerateQTcRule(),
            MildQTcRule(),

            # Renal rules (order by severity)
            SevereRenalImpairmentRule(),
            ModerateRenalImpairmentRule(),
            MildRenalImpairmentRule(),

            # Drug interaction rules
            QTProlongingDrugInteractionRule(),
            CYPInhibitorInteractionRule(),
            BetaBlockerInteractionRule(),
        ]

    def add_rule(self, rule: BaseRule) -> None:
        """Add a rule to the engine."""
        self.rules.append(rule)
        logger.info(f"Added rule: {rule.name}")

    def remove_rule(self, rule_name: str) -> bool:
        """
        Remove a rule by name.

        Args:
            rule_name: Name of rule to remove

        Returns:
            True if rule was found and removed, False otherwise
        """
        initial_count = len(self.rules)
        self.rules = [r for r in self.rules if r.name != rule_name]
        removed = len(self.rules) < initial_count

        if removed:
            logger.info(f"Removed rule: {rule_name}")
        else:
            logger.warning(f"Rule not found: {rule_name}")

        return removed

    def get_rule(self, rule_name: str) -> Optional[BaseRule]:
        """Get a rule by name."""
        for rule in self.rules:
            if rule.name == rule_name:
                return rule
        return None

    def enable_rule(self, rule_name: str) -> bool:
        """Enable a rule by name."""
        rule = self.get_rule(rule_name)
        if rule:
            rule.enabled = True
            logger.info(f"Enabled rule: {rule_name}")
            return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        """Disable a rule by name."""
        rule = self.get_rule(rule_name)
        if rule:
            rule.enabled = False
            logger.info(f"Disabled rule: {rule_name}")
            return True
        return False

    def evaluate(self, patient: PatientContext) -> DecisionContext:
        """
        Evaluate patient context against all rules.

        Args:
            patient: Patient clinical context

        Returns:
            DecisionContext with evaluation results
        """
        logger.info(f"Evaluating patient: {patient.patient_id or 'unknown'}")

        # Initialize decision context
        decision = DecisionContext(dose_adjustment=None)

        # Evaluate each rule
        fired_count = 0
        for rule in self.rules:
            try:
                if rule.evaluate(patient, decision):
                    fired_count += 1
                    logger.debug(f"Rule fired: {rule.name}")
            except Exception as e:
                logger.error(f"Error evaluating rule {rule.name}: {str(e)}", exc_info=True)
                # Continue with other rules even if one fails

        # Calculate overall risk score
        decision.calculate_risk_score()

        logger.info(
            f"Evaluation complete: {fired_count}/{len(self.rules)} rules fired, "
            f"contraindicated={decision.contraindicated}, "
            f"alerts={len(decision.alerts)}, "
            f"risk_score={decision.risk_score}"
        )

        return decision

    def evaluate_batch(self, patients: List[PatientContext]) -> List[DecisionContext]:
        """
        Evaluate multiple patients.

        Args:
            patients: List of patient contexts

        Returns:
            List of decision contexts
        """
        logger.info(f"Batch evaluation: {len(patients)} patients")
        return [self.evaluate(patient) for patient in patients]

    def get_rules_summary(self) -> dict:
        """Get summary of loaded rules."""
        return {
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules if r.enabled]),
            "disabled_rules": len([r for r in self.rules if not r.enabled]),
            "rules_by_category": self._get_rules_by_category(),
            "rules": [
                {
                    "name": r.name,
                    "category": r.category,
                    "enabled": r.enabled
                }
                for r in self.rules
            ]
        }

    def _get_rules_by_category(self) -> dict:
        """Group rules by category."""
        categories = {}
        for rule in self.rules:
            if rule.category not in categories:
                categories[rule.category] = 0
            categories[rule.category] += 1
        return categories

    def __repr__(self) -> str:
        return f"<RuleEngine: {len(self.rules)} rules ({len([r for r in self.rules if r.enabled])} enabled)>"
