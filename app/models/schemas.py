from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.core.time_utils import ist_now


class ParticipationMode(str, Enum):
    INDIVIDUAL = "individual"
    TEAM = "team"


class TeamRole(str, Enum):
    LEADER = "leader"
    MEMBER = "member"


# Public models for API


class AssignedChallenge(BaseModel):
    category: str
    title: str
    description: str
    # Difficulty removed from public API responses per product decision


class TeamMember(BaseModel):
    fullName: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    mobile: str = Field(..., pattern=r"^\d{10}$")
    rollNumber: str = Field(..., min_length=2, max_length=60)
    githubProfile: Optional[str] = None
    collegeName: Optional[str] = None
    branch: Optional[str] = None
    projectSelected: Optional[str] = None
    role: TeamRole = TeamRole.MEMBER

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("Branch cannot be empty")
        return value

    @field_validator("projectSelected")
    @classmethod
    def validate_project_selected(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        if not value.strip():
            raise ValueError("Project category cannot be empty")
        return value


# Fix M-08: StudentRegister now only contains fields a student legitimately submits.
# Admin-only fields (is_reviewed, is_selected, Reviewedby, user_feedback, password_hashed,
# feedback, github_link) have been removed from the public request schema.
class StudentRegister(BaseModel):
    fullName: str = Field(..., min_length=2, max_length=120)
    email: EmailStr
    mobile: str = Field(..., pattern=r"^\d{10}$")
    branch: str = Field(..., min_length=2, max_length=80)
    collegeName: str = Field(..., min_length=2, max_length=180)
    otherCollegeName: Optional[str] = Field(default=None, min_length=2, max_length=180)
    city: str = Field(..., min_length=2, max_length=80)
    rollNumber: str = Field(..., min_length=2, max_length=60)
    githubProfile: Optional[str] = None
    projectSelected: str = Field(..., min_length=2, max_length=120)
    participationMode: ParticipationMode
    registrationDate: datetime = Field(default_factory=ist_now)
    teamId: Optional[str] = None
    teamName: Optional[str] = None
    isTeamLeader: bool = False
    teamMembers: Optional[List[TeamMember]] = None
    # Payment fields (set by the client after Razorpay checkout)
    payment_gateway: Optional[str] = "razorpay"
    rzp_payment_id: Optional[str] = None
    rzp_order_id: Optional[str] = None
    payment_amount: Optional[float] = None
    payment_currency: Optional[str] = "INR"

    @field_validator("branch")
    @classmethod
    def validate_branch(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Branch cannot be empty")
        return value

    @field_validator("projectSelected")
    @classmethod
    def validate_project_selected(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project category cannot be empty")
        return value

    @field_validator("collegeName")
    @classmethod
    def normalize_college_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("otherCollegeName")
    @classmethod
    def normalize_other_college_name(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        cleaned = value.strip().lower()
        return cleaned or None

    @field_validator("teamMembers")
    @classmethod
    def validate_team_members(cls, value: Optional[List[TeamMember]]) -> Optional[List[TeamMember]]:
        if value is None:
            return value
        if len(value) > 4:
            raise ValueError("Maximum 4 team members allowed")
        return value


class PaymentOrderRequest(BaseModel):
    participationMode: ParticipationMode
    teamMembersCount: int = Field(default=0, ge=0, le=4)
    email: EmailStr
    fullName: str
    mobile: str = Field(..., pattern=r"^\d{10}$")
    projectSelected: Optional[str] = None

    @field_validator("projectSelected")
    @classmethod
    def validate_payment_project_selected(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value
        normalized = value.strip()
        if not normalized:
            return None
        return normalized

    @model_validator(mode="after")
    def validate_team_size(self) -> "PaymentOrderRequest":
        if self.participationMode == ParticipationMode.TEAM:
            total = 1 + self.teamMembersCount
            if total < 2:
                raise ValueError("Team must have at least 2 members including the leader. Please add at least 1 team member.")
            if total > 5:
                raise ValueError("Team cannot exceed 5 members including the leader.")
        return self


class PaymentOrderResponse(BaseModel):
    orderId: str
    amount: float
    currency: str
    paymentSessionId: str
    paymentGateway: str = "razorpay"
    # Fix H-01: environment is now dynamic based on key prefix, not hardcoded "PRODUCTION"
    environment: str = "PRODUCTION"
    razorpayKeyId: Optional[str] = None
    mockMode: bool = False
    mockPaymentId: Optional[str] = None
    message: Optional[str] = None


class PaymentVerification(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class StudentResponse(BaseModel):
    registrationId: str
    fullName: str
    email: str
    participantId: Optional[str] = None
    teamLeaderId: Optional[str] = None
    teamMemberIds: Optional[List[str]] = None
    teamId: Optional[str] = None
    transactionId: Optional[str] = None
    paymentStatus: Optional[str] = None
    taskSelected: Optional[str] = None
    assignedChallenge: Optional[AssignedChallenge] = None
    message: str
    teamMemberEmails: Optional[List[str]] = None
    teamMemberNames: Optional[List[str]] = None


# Fix M-07 / M-08: Remove admin-only internal fields from the public summary response.
# password_hashed, feedback, github_link are NOT returned to users.
# Reviewedby renamed to reviewed_by (L-01) for consistent casing.
class RegistrationSummaryResponse(BaseModel):
    registrationId: str
    fullName: str
    email: str
    participantId: Optional[str] = None
    teamId: Optional[str] = None
    teamName: Optional[str] = None
    transactionId: Optional[str] = None
    paymentStatus: Optional[str] = None
    taskSelected: Optional[str] = None
    assignedChallenge: Optional[AssignedChallenge] = None
    teamMemberEmails: Optional[List[str]] = None
    teamMemberNames: Optional[List[str]] = None
    is_reviewed: bool = False
    is_selected: bool = False
    # Fix L-01: Renamed from Reviewedby to reviewed_by for consistent snake_case
    reviewed_by: Optional[str] = None
    user_feedback: Optional[str] = None
    # Removed: password_hashed, feedback, github_link (internal fields must not be in public API)


class CollegeCreate(BaseModel):
    name: str
    city: Optional[str] = ""
    state: Optional[str] = ""


class CollegeResponse(BaseModel):
    name: str
    city: str
    state: str


class DuplicateCheck(BaseModel):
    email: Optional[str] = None
    rollNumber: Optional[str] = None
    githubProfile: Optional[str] = None
    mobile: Optional[str] = None


class LeaderDetailsResponse(BaseModel):
    teamId: str
    leaderEmail: str
    collegeName: str
    branch: str
    projectSelected: str
    taskSelected: Optional[str] = None
    assignedChallenge: Optional[AssignedChallenge] = None
