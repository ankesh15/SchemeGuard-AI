"""One explainable, non-persistent matching service for guests and citizens.

Category/occupation mappings are project relevance heuristics, never policy rules.
No age, income or demographic thresholds exist in these mappings.
"""

from math import ceil

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.assessment.templates import assessment_mode
from app.core.enums import Applicability
from app.eligibility.engine import Result, evaluate
from app.eligibility.expressions import Comparison, Group, ProfileError, Program, Scalar, normalize_profile
from app.models import Scheme
from app.repositories.rule import RuleRepository
from app.repositories.scheme import SchemeRepository
from app.schemas.citizen import ProfileData
from app.schemas.recommendations import RecommendationOptions, RecommendationPage, RecommendationRead
from app.schemas.scheme import SchemeRead
from app.services.citizen import profile_values
from app.services.currency import outdated_schemes
from app.services.eligibility import EligibilityService

# Group related catalog categories without replacing the actual taxonomy.
INTEREST_GROUPS: dict[str, tuple[str, list[str]]] = {
    "education": ("Scholarships and Education", ["scholarship", "education"]),
    "agriculture": ("Agriculture", ["agriculture", "fisheries"]),
    "health": ("Healthcare", ["health"]),
    "employment": ("Employment and Skill Development", ["skills", "employment"]),
    "business": ("Business and Entrepreneurship", ["business"]),
    "housing": ("Housing", ["housing"]),
    "women_child": ("Women and Child Development", ["women_child"]),
    "social_welfare": ("Social Welfare", ["social_welfare", "food_security", "disability"]),
    "pension": ("Pensions", ["pension"]),
}
ALIASES = {
    "scholarships": "education",
    "scholarship": "education",
    "healthcare": "health",
    "skill_development": "employment",
}
OCCUPATION_CATEGORIES = {
    "student": {"scholarship", "education"},
    "self_employed": {"business"},
    "unemployed": {"skills", "employment"},
    "employed": {"skills"},
    "retired": {"pension"},
}


def interest_categories(interests: list[str]) -> set[str]:
    categories: set[str] = set()
    for value in interests:
        key = ALIASES.get(value, value)
        categories.update(INTEREST_GROUPS[key][1] if key in INTEREST_GROUPS else [key])
    return categories


def approved_answers(program: Program, profile: ProfileData) -> dict[str, str | int | float | bool | None]:
    """Reuse only exact compatible inputs. Unsupported values remain unknown."""
    values = profile_values(profile)
    answers: dict[str, str | int | float | bool | None] = {}
    for field in program.fields:
        value = values.get(field.key)
        if value is None or not isinstance(value, (str, int, float, bool)):
            continue
        try:
            normalize_profile(program, {field.key: value})
        except ProfileError:
            continue
        answers[field.key] = value
    return answers


def reviewed_education_matches(program: Program, answers: dict[str, Scalar]) -> bool:
    """Only a positive, directly declared course condition can signal education relevance.

    Do not lift comparisons from exclusions, conditionals or nested trees into
    independent requirements. Their meaning depends on the full expression.
    """
    children = program.expression.children if isinstance(program.expression, Group) else [program.expression]
    return any(
        isinstance(child, Comparison)
        and child.field == "course_level"
        and child.operator in {"==", "IN"}
        and evaluate(Program(fields=program.fields, expression=child), answers).result == Result.PASS
        for child in children
    )


class RecommendationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SchemeRepository(session)

    async def recommend(self, profile: ProfileData, options: RecommendationOptions) -> RecommendationPage:
        # All matching is against the current PostgreSQL catalog, never a copied scheme list.
        schemes = list(
            await self.session.scalars(
                select(Scheme)
                .options(selectinload(Scheme.sources))
                .where(Scheme.is_demo.is_(False), Scheme.status != "inactive")
            )
        )
        interests = interest_categories(profile.interests)
        occupational = OCCUPATION_CATEGORIES.get(profile.occupation or "", set())
        employment = {
            "unemployed": {"skills", "employment"},
            "part_time": {"skills"},
            "full_time": {"skills"},
            "self_employed": {"business"},
            "retired": {"pension"},
        }.get(profile.employment_status or "", set())
        eligible_ids = await self.repository.availability([scheme.id for scheme in schemes])
        outdated = await outdated_schemes(self.session, [scheme.id for scheme in schemes])
        ranked: list[RecommendationRead] = []
        for scheme in schemes:
            reasons: list[str] = []
            missing: list[str] = []
            factors: dict[str, int] = {}
            category = scheme.category
            if category in interests:
                factors["interest_category"] = 60
                reasons.append(f"Matches your interest in {category.replace('_', ' ')}")
            if category in occupational | employment:
                factors["occupation_or_employment"] = 20
                reasons.append("Related to your occupation or employment interests")
            if profile.current_student is True and category in {"education", "scholarship"}:
                factors["student_status"] = 20
                reasons.append("Relevant to your student status")
            # Education alone needs structured approved evidence, never a category guess.
            category_match = bool(factors)
            if not category_match and scheme.id not in eligible_ids:
                continue
            if profile.state and scheme.applicability == Applicability.STATES and scheme.applicable_states:
                if profile.state.value not in scheme.applicable_states:
                    continue
                factors["verified_geography"] = 8
                reasons.append("Verified scheme coverage includes your state")
            elif profile.state and scheme.applicability == Applicability.NATIONAL:
                factors["verified_geography"] = 8
                reasons.append("Verified national coverage includes your state")
            elif scheme.applicability == Applicability.UNKNOWN:
                missing.append("State coverage has not been verified; the scheme remains discoverable")
            elif not profile.state:
                missing.append("Your state or union territory")
            approved = scheme.id in eligible_ids
            mode = assessment_mode(scheme, approved)
            rule_version = None
            if approved:
                # The same approved version selector, typed expressions and evidence checks as assessments.
                try:
                    _, rule, program = await EligibilityService(
                        self.repository, RuleRepository(self.session)
                    ).load(scheme.id)
                    if rule and program:
                        answers = approved_answers(program, profile)
                        trace = evaluate(program, answers)
                        if trace.result != Result.FAIL and reviewed_education_matches(program, answers):
                            factors["reviewed_education"] = 15
                            reasons.append("Your education matches a condition in the reviewed policy")
                        rule_version = rule.version_number
                        factors["approved_assessment"] = 5
                        reasons.append("A reviewed policy assessment is available")
                        if trace.result == Result.PASS:
                            factors["approved_conditions"] = 12
                            reasons.append(
                                "Supplied information satisfies the known reviewed conditions; check the full assessment"
                            )
                        elif trace.result == Result.FAIL:
                            factors["approved_conditions"] = -20
                            reasons.append(
                                "Some reviewed requirements are not satisfied; inspect the assessment before applying"
                            )
                        missing.extend(
                            field.label for field in program.fields if field.key in trace.missing_fields
                        )
                except HTTPException as error:
                    if error.status_code not in {409, 503}:
                        raise
                    # Never hide an ambiguous/broken approved policy behind an illustrative template.
                    approved, mode = False, "UNSUPPORTED"
                    missing.append("The approved policy needs administrative review before assessment")
            else:
                missing.append("Scheme-specific verified eligibility conditions")
                if mode == "ILLUSTRATIVE":
                    reasons.append(
                        "An illustrative category assessment is available; it does not verify government eligibility"
                    )
            if not (
                category_match
                or factors.get("reviewed_education")
                or factors.get("approved_conditions", 0) > 0
            ):
                continue
            if scheme.id in outdated:
                missing.append("Current official policy verification")
            score = sum(factors.values())
            relevance = "HIGH" if score >= 75 else "POTENTIAL"
            if "approved_conditions" in factors and factors["approved_conditions"] < 0:
                relevance = "MORE_INFORMATION"
            ranked.append(
                RecommendationRead.model_validate(
                    SchemeRead.model_validate(scheme).model_dump()
                    | {
                        "eligibility_available": approved,
                        "assessment_available": mode != "UNSUPPORTED",
                        "assessment_mode": mode,
                        "policy_currency": "POTENTIALLY_OUTDATED"
                        if scheme.id in outdated
                        else "APPROVED"
                        if approved
                        else "UNVERIFIED",
                        "relevance": relevance,
                        "matching_reasons": reasons,
                        "missing_information": missing,
                        "ranking_points": score,
                        "ranking_factors": factors,
                        "approved_rule_version": rule_version,
                    }
                )
            )
        categories = sorted({item.category for item in ranked})
        if options.category:
            ranked = [item for item in ranked if item.category == options.category]
        ranked.sort(
            key=lambda item: (
                ((-item.ranking_points,) if options.sort_by == "relevance" else ())
                + (item.name.casefold(), str(item.id))
            )
        )
        start = (options.page - 1) * options.page_size
        return RecommendationPage(
            items=ranked[start : start + options.page_size],
            total=len(ranked),
            page=options.page,
            page_size=options.page_size,
            pages=ceil(len(ranked) / options.page_size),
            categories=categories,
        )
