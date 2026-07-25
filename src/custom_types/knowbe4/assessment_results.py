from typing import TypedDict

# Assessment results


class AssessmentDomain(TypedDict):
    name: str
    score: int


class AssessmentResults(TypedDict):
    domains: list[AssessmentDomain]
    score: int


class AssessmentResultsResponse(TypedDict):
    assessmentResults: AssessmentResults
