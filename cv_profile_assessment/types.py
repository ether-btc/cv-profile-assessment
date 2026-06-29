"""Type definitions for CV Profile Assessment.

Dataclasses and enums for typed profile and job representations.
Replaces Dict returns with structured, validated types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class SkillCategory(str, Enum):
    """Categories for skills in the taxonomy."""
    PROGRAMMING_LANGUAGES = "programming_languages"
    FRAMEWORKS = "frameworks"
    TOOLS = "tools"
    PLATFORMS = "platforms"
    DATABASES = "databases"
    SOFT_SKILLS = "soft_skills"
    DOMAINS = "domains"


class Proficiency(str, Enum):
    """Skill proficiency levels."""
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SectionKey(str, Enum):
    """CV section identifiers."""
    CONTACT = "contact"
    SUMMARY = "summary"
    EXPERIENCE = "experience"
    EDUCATION = "education"
    SKILLS = "skills"
    PROJECTS = "projects"
    CERTIFICATIONS = "certifications"
    LANGUAGES = "languages"


@dataclass
class Skill:
    """A single skill with metadata."""
    category: SkillCategory
    name: str
    proficiency: Proficiency = Proficiency.INTERMEDIATE
    years_of_experience: Optional[float] = None
    last_used: Optional[str] = None  # ISO 8601 date
    esco_id: Optional[str] = None  # ESCO ontology ID
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "category": self.category.value,
            "name": self.name,
            "proficiency": self.proficiency.value,
            "years_of_experience": self.years_of_experience,
            "last_used": self.last_used,
            "esco_id": self.esco_id,
        }


@dataclass
class Experience:
    """Work experience entry."""
    position: str
    company: str
    location: Optional[str] = None
    start_date: Optional[str] = None  # ISO 8601 date
    end_date: Optional[str] = None  # ISO 8601 date
    current: bool = False
    summary: str = ""
    achievements: list[str] = field(default_factory=list)
    skills_used: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "position": self.position,
            "company": self.company,
            "location": self.location,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "current": self.current,
            "summary": self.summary,
            "achievements": self.achievements,
            "skills_used": self.skills_used,
        }


@dataclass
class Education:
    """Education entry."""
    institution: str = ""
    degree: Optional[str] = None
    field: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    grade: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "institution": self.institution,
            "degree": self.degree,
            "field": self.field,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "grade": self.grade,
        }


@dataclass
class Project:
    """Project entry."""
    name: str = ""
    description: str = ""
    url: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    skills_demonstrated: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "skills_demonstrated": self.skills_demonstrated,
        }


@dataclass
class Certification:
    """Certification entry."""
    name: str = ""
    issuer: str = ""
    date: Optional[str] = None
    credential_id: Optional[str] = None
    url: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "name": self.name,
            "issuer": self.issuer,
            "date": self.date,
            "credential_id": self.credential_id,
            "url": self.url,
        }


@dataclass
class LocationPreference:
    """Location and remote work preferences."""
    preferred_cities: list[str] = field(default_factory=list)
    remote_only: bool = False
    hybrid_ok: bool = True
    relocation_willing: bool = False
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "preferred_cities": self.preferred_cities,
            "remote_only": self.remote_only,
            "hybrid_ok": self.hybrid_ok,
            "relocation_willing": self.relocation_willing,
        }


@dataclass
class SalaryExpectations:
    """Salary expectations."""
    minimum: Optional[float] = None
    target: Optional[float] = None
    currency: str = "EUR"
    period: str = "yearly"  # yearly, monthly, hourly
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "minimum": self.minimum,
            "target": self.target,
            "currency": self.currency,
            "period": self.period,
        }


@dataclass
class RolePreferences:
    """Role and seniority preferences."""
    preferred_titles: list[str] = field(default_factory=list)
    seniority_levels: list[str] = field(default_factory=list)
    company_sizes: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "preferred_titles": self.preferred_titles,
            "seniority_levels": self.seniority_levels,
            "company_sizes": self.company_sizes,
            "industries": self.industries,
        }


@dataclass
class Preferences:
    """Candidate preferences for job matching."""
    location_preference: LocationPreference = field(default_factory=LocationPreference)
    salary_expectations: SalaryExpectations = field(default_factory=SalaryExpectations)
    role_preferences: RolePreferences = field(default_factory=RolePreferences)
    deal_breakers: list[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "location_preference": self.location_preference.to_dict(),
            "salary_expectations": self.salary_expectations.to_dict(),
            "role_preferences": self.role_preferences.to_dict(),
            "deal_breakers": self.deal_breakers,
        }


@dataclass
class Metadata:
    """Profile metadata."""
    version: str = "1.0"
    last_updated: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    source: Optional[str] = None
    confidence_scores: dict = field(default_factory=lambda: {
        "skills_extraction": 0.7,
        "esco_mapping": 0.0,
    })
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "version": self.version,
            "last_updated": self.last_updated,
            "source": self.source,
            "confidence_scores": self.confidence_scores,
        }


@dataclass
class PersonalProfile:
    """Complete personal profile for job matching.
    
    This is the main output of the CV parser and input to the matching engine.
    """
    # Note: 'name' is required by JSON Schema but we use basics.name
    # This field is for dataclass convenience
    name: str = ""
    
    basics: dict = field(default_factory=lambda: {
        "name": "",
        "email": "",
        "phone": "",
        "location": {},
        "summary": "",
        "languages": [],
    })
    skills: list[Skill] = field(default_factory=list)
    experience: list[Experience] = field(default_factory=list)
    education: list[Education] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    certifications: list[Certification] = field(default_factory=list)
    preferences: Preferences = field(default_factory=Preferences)
    metadata: Metadata = field(default_factory=Metadata)
    
    def to_dict(self) -> dict:
        """Convert to dict matching JSON Schema for validation and serialization."""
        return {
            "basics": self.basics,
            "skills": [s.to_dict() for s in self.skills],
            "experience": [e.to_dict() for e in self.experience],
            "education": [e.to_dict() for e in self.education],
            "projects": [p.to_dict() for p in self.projects],
            "certifications": [c.to_dict() for c in self.certifications],
            "preferences": self.preferences.to_dict(),
            "metadata": self.metadata.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> PersonalProfile:
        """Create PersonalProfile from dict (e.g., loaded JSON)."""
        skills = [
            Skill(
                category=SkillCategory(s.get("category", "domains")),
                name=s.get("name", ""),
                proficiency=Proficiency(s.get("proficiency", "intermediate")),
                years_of_experience=s.get("years_of_experience"),
                last_used=s.get("last_used"),
                esco_id=s.get("esco_id"),
            )
            for s in data.get("skills", [])
        ]
        
        experience = [
            Experience(
                position=e.get("position", ""),
                company=e.get("company", ""),
                location=e.get("location"),
                start_date=e.get("start_date"),
                end_date=e.get("end_date"),
                current=e.get("current", False),
                summary=e.get("summary", ""),
                achievements=e.get("achievements", []),
                skills_used=e.get("skills_used", []),
            )
            for e in data.get("experience", [])
        ]
        
        education = [
            Education(
                institution=e.get("institution", ""),
                degree=e.get("degree"),
                field=e.get("field"),
                start_date=e.get("start_date"),
                end_date=e.get("end_date"),
                grade=e.get("grade"),
            )
            for e in data.get("education", [])
        ]
        
        projects = [
            Project(
                name=p.get("name", ""),
                description=p.get("description", ""),
                url=p.get("url"),
                start_date=p.get("start_date"),
                end_date=p.get("end_date"),
                skills_demonstrated=p.get("skills_demonstrated", []),
            )
            for p in data.get("projects", [])
        ]
        
        certifications = [
            Certification(
                name=c.get("name", ""),
                issuer=c.get("issuer", ""),
                date=c.get("date"),
                credential_id=c.get("credential_id"),
                url=c.get("url"),
            )
            for c in data.get("certifications", [])
        ]
        
        pref_data = data.get("preferences", {})
        location_pref_data = pref_data.get("location_preference", {})
        salary_data = pref_data.get("salary_expectations", {})
        role_data = pref_data.get("role_preferences", {})
        
        preferences = Preferences(
            location_preference=LocationPreference(
                preferred_cities=location_pref_data.get("preferred_cities", []),
                remote_only=location_pref_data.get("remote_only", False),
                hybrid_ok=location_pref_data.get("hybrid_ok", True),
                relocation_willing=location_pref_data.get("relocation_willing", False),
            ),
            salary_expectations=SalaryExpectations(
                minimum=salary_data.get("minimum"),
                target=salary_data.get("target"),
                currency=salary_data.get("currency", "EUR"),
                period=salary_data.get("period", "yearly"),
            ),
            role_preferences=RolePreferences(
                preferred_titles=role_data.get("preferred_titles", []),
                seniority_levels=role_data.get("seniority_levels", []),
                company_sizes=role_data.get("company_sizes", []),
                industries=role_data.get("industries", []),
            ),
            deal_breakers=pref_data.get("deal_breakers", []),
        )
        
        metadata_data = data.get("metadata", {})
        metadata = Metadata(
            version=metadata_data.get("version", "1.0"),
            last_updated=metadata_data.get("last_updated", datetime.utcnow().isoformat() + "Z"),
            source=metadata_data.get("source"),
            confidence_scores=metadata_data.get("confidence_scores", {
                "skills_extraction": 0.7,
                "esco_mapping": 0.0,
            }),
        )
        
        basics = data.get("basics", {})
        
        return cls(
            name=basics.get("name", ""),
            basics=basics,
            skills=skills,
            experience=experience,
            education=education,
            projects=projects,
            certifications=certifications,
            preferences=preferences,
            metadata=metadata,
        )


# Job-related types


@dataclass
class Job:
    """Job posting for matching."""
    title: str
    company: str
    location: str
    remote: bool = False
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    min_years_experience: int = 0
    seniority: Optional[str] = None  # junior, mid, senior, lead
    salary_range: Optional[dict] = None
    description: str = ""
    url: Optional[str] = None
    source: Optional[dict] = None  # _source from scout adapter
    
    def to_dict(self) -> dict:
        """Convert to dict for matching engine."""
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "remote": self.remote,
            "required_skills": self.required_skills,
            "preferred_skills": self.preferred_skills,
            "min_years_experience": self.min_years_experience,
            "seniority": self.seniority,
            "salary_range": self.salary_range,
            "description": self.description,
            "url": self.url,
            "_source": self.source,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> Job:
        """Create Job from dict."""
        return cls(
            title=data.get("title", ""),
            company=data.get("company", ""),
            location=data.get("location", ""),
            remote=data.get("remote", False),
            required_skills=data.get("required_skills", []),
            preferred_skills=data.get("preferred_skills", []),
            min_years_experience=data.get("min_years_experience", 0),
            seniority=data.get("seniority"),
            salary_range=data.get("salary_range"),
            description=data.get("description", ""),
            url=data.get("url"),
            source=data.get("_source"),
        )


@dataclass
class MatchResult:
    """Result of matching a profile against a job."""
    job: Job
    overall_score: float
    component_scores: dict
    blocked: bool = False
    block_reason: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON output."""
        result = {
            "title": self.job.title,
            "company": self.job.company,
            "location": self.job.location,
            "remote": self.job.remote,
            "url": self.job.url,
            "overall_score": round(self.overall_score, 4),
            "component_scores": {
                k: round(v, 4) for k, v in self.component_scores.items()
            },
        }
        if self.blocked:
            result["blocked"] = True
            result["block_reason"] = self.block_reason
        return result