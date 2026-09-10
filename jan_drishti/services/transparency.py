"""Model transparency engine - explains how risk scores are calculated.

This module provides full transparency into the AI risk assessment model,
showing judges and officers exactly how each score is computed.
"""

from __future__ import annotations

from typing import Dict, List, Any
from jan_drishti.models import ProjectRecord, Finding
from jan_drishti.config import CONFIG


def get_model_documentation() -> Dict[str, Any]:
    """Return complete documentation of the risk scoring model."""
    
    thresholds = CONFIG.thresholds
    
    return {
        "model_name": "JAN-DRISHTI Explainable Risk Scoring Model v1.0",
        "model_type": "Rule-based expert system with transparent scoring",
        "description": "A fully explainable, non-black-box model that calculates risk scores based on government audit best practices",
        "risk_components": [
            {
                "component": "Cost Overrun Risk",
                "weight": 25,
                "description": "Measures whether project spending exceeds sanctioned budget",
                "formula": "If (spent - sanctioned) / sanctioned > threshold%",
                "thresholds": {
                    "low": f"{thresholds.low_cost_overrun_pct}%",
                    "medium": f"{thresholds.medium_cost_overrun_pct}%",
                    "high": f"{thresholds.high_cost_overrun_pct}%",
                    "critical": f"{thresholds.critical_cost_overrun_pct}%"
                },
                "points_awarded": "Low: 10, Medium: 15, High: 25, Critical: 30"
            },
            {
                "component": "Schedule Delay Risk",
                "weight": 20,
                "description": "Identifies projects running behind planned completion date",
                "formula": "Days delayed = today - planned_end_date (if still in progress)",
                "thresholds": {
                    "medium": f"{thresholds.medium_delay_days} days",
                    "high": f"{thresholds.high_delay_days} days",
                    "critical": f"{thresholds.critical_delay_days} days"
                },
                "points_awarded": "Medium: 10, High: 20, Critical: 25"
            },
            {
                "component": "Financial-Physical Mismatch",
                "weight": 25,
                "description": "Detects suspicious gaps between payment progress and physical work completion",
                "formula": "Gap = |financial_progress% - physical_progress%|",
                "thresholds": {
                    "medium": f"{thresholds.medium_financial_physical_gap_pct}%",
                    "high": f"{thresholds.high_financial_physical_gap_pct}%"
                },
                "points_awarded": "Medium: 15, High: 25"
            },
            {
                "component": "Duplicate Work Detection",
                "weight": 15,
                "description": "Flags potentially duplicate projects in same location with similar amounts",
                "formula": "Name similarity > 88% AND amount within 7.5% AND same district",
                "thresholds": {
                    "name_similarity": f"{thresholds.duplicate_name_similarity * 100}%",
                    "amount_tolerance": f"{thresholds.duplicate_amount_tolerance_pct}%"
                },
                "points_awarded": "High: 20, Critical: 25"
            },
            {
                "component": "Stale Reporting",
                "weight": 10,
                "description": "Identifies projects with outdated progress reports",
                "formula": "Days since last update = today - last_updated",
                "thresholds": {
                    "medium": f"{thresholds.stale_update_days} days",
                    "high": f"{thresholds.very_stale_update_days} days"
                },
                "points_awarded": "Medium: 8, High: 12"
            },
            {
                "component": "Data Quality Issues",
                "weight": 5,
                "description": "Penalizes projects with missing critical fields",
                "formula": "Missing fields count × 5 points",
                "thresholds": {
                    "info": "Applies to all projects with missing data"
                },
                "points_awarded": "5 points per missing field (name, amount, dates)"
            }
        ],
        "fraud_score_components": [
            {
                "component": "Payment-Progress Inflation",
                "description": "Financial progress exceeds physical progress by large margin",
                "points": 30
            },
            {
                "component": "Excessive Cost Overrun",
                "description": "Spending exceeds budget by >25%",
                "points": 25
            },
            {
                "component": "Duplicate Project Match",
                "description": "Strong evidence of duplicate work in same area",
                "points": 20
            },
            {
                "component": "Contractor Concentration",
                "description": "Same contractor appears unusually often",
                "points": 15
            },
            {
                "component": "Amount Outlier",
                "description": "Project budget is statistical outlier",
                "points": 10
            }
        ],
        "risk_level_classification": {
            "Low": f"0-{thresholds.medium_risk}",
            "Medium": f"{thresholds.medium_risk}-{thresholds.high_risk}",
            "High": f"{thresholds.high_risk}-{thresholds.critical_risk}",
            "Critical": f"{thresholds.critical_risk}+"
        },
        "total_score_range": "0-100 (higher = higher risk)",
        "key_principles": [
            "Fully transparent - no hidden layers or neural networks",
            "Rule-based - every point can be explained",
            "Auditable - all thresholds are documented and configurable",
            "Expert-driven - based on government audit manuals and CAG guidelines",
            "Explainable - every finding includes evidence and recommendations"
        ]
    }


def explain_project_score_breakdown(
    project: ProjectRecord,
    findings: List[Finding],
    risk_score: int,
    fraud_score: int
) -> Dict[str, Any]:
    """Generate detailed breakdown of how a specific project's scores were calculated."""
    
    breakdown = {
        "project_id": project.project_id,
        "project_name": project.project_name,
        "total_risk_score": risk_score,
        "total_fraud_score": fraud_score,
        "score_components": [],
        "total_points_breakdown": {
            "cost_overrun": 0,
            "schedule_delay": 0,
            "mismatch": 0,
            "duplicate": 0,
            "stale_data": 0,
            "data_quality": 0
        }
    }
    
    # Analyze each finding and map to score components
    for finding in findings:
        component = {
            "finding_type": finding.type,
            "severity": finding.severity,
            "title": finding.title,
            "points_contributed": _calculate_finding_points(finding),
            "evidence": finding.evidence
        }
        breakdown["score_components"].append(component)
        
        # Update breakdown categories
        if "cost" in finding.type or "overrun" in finding.type:
            breakdown["total_points_breakdown"]["cost_overrun"] += component["points_contributed"]
        elif "delay" in finding.type or "schedule" in finding.type:
            breakdown["total_points_breakdown"]["schedule_delay"] += component["points_contributed"]
        elif "mismatch" in finding.type:
            breakdown["total_points_breakdown"]["mismatch"] += component["points_contributed"]
        elif "duplicate" in finding.type:
            breakdown["total_points_breakdown"]["duplicate"] += component["points_contributed"]
        elif "stale" in finding.type:
            breakdown["total_points_breakdown"]["stale_data"] += component["points_contributed"]
        else:
            breakdown["total_points_breakdown"]["data_quality"] += component["points_contributed"]
    
    # Add explanation of calculation
    breakdown["calculation_explanation"] = (
        f"Total risk score of {risk_score}/100 is the sum of individual risk components. "
        f"Each finding contributes points based on its severity: "
        f"Low (5-10 pts), Medium (10-15 pts), High (20-25 pts), Critical (25-30 pts)."
    )
    
    breakdown["fraud_explanation"] = (
        f"Fraud likelihood score of {fraud_score}/100 specifically measures "
        f"indicators associated with potential fraud: payment-progress inflation, "
        f"excessive overruns, duplicate works, and contractor concentration patterns."
    )
    
    return breakdown


def _calculate_finding_points(finding: Finding) -> int:
    """Calculate points contributed by a single finding."""
    severity_points = {
        "low": 5,
        "medium": 12,
        "high": 22,
        "critical": 28
    }
    
    base_points = severity_points.get(finding.severity, 5)
    
    # Add type-specific adjustments
    if finding.type in ["financial_physical_mismatch", "cost_overrun"]:
        base_points += 3
    elif finding.type in ["possible_duplicate_work", "duplicate_project_id"]:
        base_points += 5
    
    return min(base_points, 30)  # Cap at 30 points per finding


def get_score_calculation_example() -> Dict[str, Any]:
    """Provide a worked example of score calculation for educational purposes."""
    
    return {
        "example_title": "Sample Risk Score Calculation",
        "scenario": "Road construction project with cost overrun and delay",
        "project_details": {
            "sanctioned_amount": "₹50 Crore",
            "spent_amount": "₹68 Crore",
            "physical_progress": "65%",
            "days_delayed": 120,
            "last_updated": "45 days ago"
        },
        "findings_identified": [
            {
                "finding": "Cost overrun of 36%",
                "severity": "High",
                "points": 25,
                "reason": "Spending exceeds budget by 36%, above 25% threshold"
            },
            {
                "finding": "Schedule delay of 120 days",
                "severity": "Medium", 
                "points": 10,
                "reason": "Delay between 60-180 days threshold"
            },
            {
                "finding": "Stale reporting (45 days)",
                "severity": "Medium",
                "points": 8,
                "reason": "Last updated 45 days ago, at threshold"
            }
        ],
        "calculation": {
            "cost_overrun_points": 25,
            "schedule_delay_points": 10,
            "stale_reporting_points": 8,
            "total_risk_score": 43,
            "risk_level": "Medium Risk"
        },
        "interpretation": "Score of 43/100 places this project in Medium Risk category (35-60 range), requiring enhanced monitoring and field verification."
    }
