from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz


def get_query_enrollments(page: int = 1, per: int = 100) -> str:
    end_date = datetime.now(pytz.utc)
    start_date = end_date - relativedelta(years=1)
    query = f"""{{
        enrollments(
            dateRangeEndDate: "{end_date.strftime("%Y-%m-%dT%H:%M:%SZ")}", 
            dateRangeField: COMPLETED_AT,
            dateRangeStartDate: "{start_date.strftime("%Y-%m-%dT%H:%M:%SZ")}",
            page: {page},
            per: {per}
        ) {{
            nodes {{
                id
                createdAt
                completedAt
                status
                totalScore
                type
                trainingCampaign {{
                    id
                    name
                }}
                user {{
                    id
                }}
            }}
            pagination {{
                totalCount
            }}
        }}
    }}"""

    return query


def get_query_pst(page: int, per: int) -> str:
    """Crea la query la información de los PSTs de la Graph API"""
    query = f"""{{
        phishingCampaignRuns(page: {page}, per: {per}){{
            nodes {{
                id
                createdAt
                phishPronePercentage
                totalOpened
                totalReported
                campaignRecipients {{
                    createdAt
                    clicked
                    clickedCount
                    opened
                    emailTemplate {{
                        id
                        name
                        rating
                        isAida
                        topics {{
                            name
                        }}
                    }}
                    reported
                    user {{
                        id
                        email
                    }}
                }}
            }}
        }}
    }}
    """
    return query


def get_query_user(page: int, per: int) -> str:
    """Crea la query para la información de los usuarios de la Graph API"""
    query = f"""{{
        users(status: ACTIVE, page: {page}, per: {per}) {{
            nodes {{
                id
                email
                firstName
                lastName
                createdAt
                jobTitle
                role
                riskScore
                mandatoryEnrollments{{
                    id
                    completedAt
                    createdAt
                    status
                    totalScore
                    type
                    trainingCampaign {{
                        id
                        name
                    }}
                }}
                optionalEnrollments {{
                    id
                    completedAt
                }}
            }}
        }}
    }}
    """
    return query


def get_query_password_users(page: int, per: int) -> str:
    query = f"""{{
        passwordIqUserStates(pagination: {{ page: {page}, per: {per} }}) {{
            users {{
                id
                emails {{
                    address
                }}
                events {{
                    detectionType {{
                        name
                    }}
                    occurredAt
                    status
                }}
            }}
        }}
    }}"""
    return query


def get_query_assessment(assessmentId: int, campaignId: int) -> str:
    query = f"""{{
        assessmentResults(assessmentId: {assessmentId}, campaignId: {campaignId}){{
            domains {{
                name
                score
            }}
            score
        }}
    }}"""

    return query
