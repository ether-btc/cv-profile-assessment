#!/usr/bin/env python3
"""Demo: CV Profile Assessment new features (v0.2.0).

This script demonstrates:
1. Dataclass usage (PersonalProfile, Job, Skill, etc.)
2. Enums (SkillCategory, Proficiency, SectionKey)
3. Helper functions (read_json, write_json, iter_nonblank_lines)
4. Parallel job matching for large batches
5. Backward compatibility with dict-based API

Usage:
    source venv/bin/activate
    python scripts/demo_v020.py
"""

import sys
from pathlib import Path

# Make project root importable
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cv_profile_assessment.types import (  # noqa: E402
    Experience,
    Job,
    PersonalProfile,
    Proficiency,
    Skill,
    SkillCategory,
)
from cv_profile_assessment.helpers import (  # noqa: E402
    iter_nonblank_lines,
    read_json,
    write_json,
)
from matching import (  # noqa: E402
    score_jobs_parallel,
    score_many_jobs,
    score_one_job,
)


def demo_dataclasses():
    """Demonstrate dataclass usage."""
    print("=" * 70)
    print("1. DATACLASS USAGE")
    print("=" * 70)
    
    # Create a skill using dataclass
    skill = Skill(
        category=SkillCategory.PROGRAMMING_LANGUAGES,
        name="Python",
        proficiency=Proficiency.EXPERT,
        years_of_experience=8.0,
        esco_id="http://data.europa.eu/esco/skill/123",
    )
    print(f"\nCreated skill: {skill.name}")
    print(f"  Category: {skill.category.value}")
    print(f"  Proficiency: {skill.proficiency.value}")
    print(f"  Years: {skill.years_of_experience}")
    print(f"  ESCO ID: {skill.esco_id}")
    
    # Convert to dict for JSON serialization
    skill_dict = skill.to_dict()
    print(f"  As dict: {skill_dict}")
    
    # Create a full profile
    profile = PersonalProfile(
        name="Demo User",
        basics={
            "name": "Demo User",
            "email": "demo@example.com",
            "location": {"city": "Vienna"},
        },
        skills=[skill],
        experience=[
            Experience(
                position="Senior Engineer",
                company="TechCorp",
                start_date="2020-01-01",
                current=True,
                summary="Leading backend development",
            )
        ],
    )
    
    print(f"\nCreated profile: {profile.name}")
    print(f"  Skills: {len(profile.skills)}")
    print(f"  Experience entries: {len(profile.experience)}")
    
    # Convert to dict for validation/serialization
    profile_dict = profile.to_dict()
    print(f"  Profile as dict (keys): {list(profile_dict.keys())}")
    
    # Create from dict (round-trip)
    profile_from_dict = PersonalProfile.from_dict(profile_dict)
    print(f"  Round-trip successful: {profile_from_dict.name == profile.name}")
    
    return profile


def demo_enums():
    """Demonstrate enum usage."""
    print("\n" + "=" * 70)
    print("2. ENUM USAGE")
    print("=" * 70)
    
    print("\nSkillCategory values:")
    for cat in SkillCategory:
        print(f"  - {cat.value}")
    
    print("\nProficiency levels:")
    for prof in Proficiency:
        print(f"  - {prof.value}")
    
    print("\nSectionKey values:")
    from cv_profile_assessment.types import SectionKey
    for section in SectionKey:
        print(f"  - {section.value}")


def demo_helpers():
    """Demonstrate helper functions."""
    print("\n" + "=" * 70)
    print("3. HELPER FUNCTIONS")
    print("=" * 70)
    
    # Demonstrate read_json/write_json
    test_data = {"name": "Test", "value": 42}
    test_file = PROJECT_ROOT / "data" / "demo_test.json"
    
    print(f"\nWriting test data to {test_file}")
    write_json(test_file, test_data)
    
    print("Reading back...")
    loaded = read_json(test_file)
    print(f"  Loaded: {loaded}")
    print(f"  Round-trip OK: {loaded == test_data}")
    
    # Clean up
    test_file.unlink()
    print("  Cleaned up temp file")
    
    # Demonstrate iter_nonblank_lines
    sample_text = """
    Line 1
    
      
    Line 2
    Line 3
    
    """
    print("\niter_nonblank_lines example:")
    print(f"  Input: {repr(sample_text)}")
    lines = list(iter_nonblank_lines(sample_text))
    print(f"  Output: {lines}")


def demo_matching():
    """Demonstrate matching with dataclasses and dicts."""
    print("\n" + "=" * 70)
    print("4. MATCHING (BACKWARD COMPATIBLE)")
    print("=" * 70)
    
    # Create profile as dataclass
    profile = PersonalProfile(
        name="Backend Dev",
        basics={"name": "Backend Dev", "email": "dev@example.com"},
        skills=[
            Skill(category=SkillCategory.PROGRAMMING_LANGUAGES, name="Python", proficiency=Proficiency.EXPERT),
            Skill(category=SkillCategory.FRAMEWORKS, name="FastAPI", proficiency=Proficiency.ADVANCED),
            Skill(category=SkillCategory.TOOLS, name="Docker", proficiency=Proficiency.ADVANCED),
        ],
        experience=[
            Experience(position="Senior Dev", company="TechCorp", start_date="2018-01-01", current=True),
        ],
    )
    
    # Create jobs as dataclasses
    jobs = [
        Job(
            title="Senior Backend Engineer",
            company="Company A",
            location="Vienna",
            required_skills=["Python", "FastAPI", "Docker"],
            min_years_experience=5,
        ),
        Job(
            title="DevOps Engineer",
            company="Company B",
            location="Vienna",
            required_skills=["Kubernetes", "AWS", "Terraform"],
            min_years_experience=3,
        ),
        Job(
            title="Frontend Developer",
            company="Company C",
            location="Vienna",
            required_skills=["React", "TypeScript", "CSS"],
            min_years_experience=2,
        ),
    ]
    
    # Test 1: Dict-based (backward compatible)
    print("\nDict-based matching (v0.1.0 style):")
    profile_dict = profile.to_dict()
    job_dicts = [j.to_dict() for j in jobs]
    
    result = score_one_job(profile_dict, job_dicts[0])
    print(f"  Job: {result['job_title']}")
    print(f"  Score: {result['overall_score']:.4f}")
    
    # Test 2: Dataclass-based (v0.2.0 style)
    print("\nDataclass-based matching (v0.2.0 style):")
    result = score_one_job(profile, jobs[0])
    print(f"  Job: {result['job_title']}")
    print(f"  Score: {result['overall_score']:.4f}")
    
    # Test 3: Batch sequential (optimized)
    print("\nBatch sequential matching (score_many_jobs):")
    results = score_many_jobs(profile, jobs)
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r['job_title']}: {r['overall_score']:.4f}")
    
    # Test 4: Batch parallel (for large batches)
    print("\nBatch parallel matching (score_jobs_parallel):")
    results_parallel = score_jobs_parallel(profile, jobs, max_workers=2)
    for i, r in enumerate(results_parallel, 1):
        print(f"  {i}. {r['job_title']}: {r['overall_score']:.4f}")
    
    print(f"\n  Sequential == Parallel: {results == results_parallel}")


def main():
    """Run all demos."""
    print("\n" + "=" * 70)
    print("CV PROFILE ASSESSMENT v0.2.0 — NEW FEATURES DEMO")
    print("=" * 70)
    
    demo_dataclasses()
    demo_enums()
    demo_helpers()
    demo_matching()
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    print("\nKey improvements in v0.2.0:")
    print("  ✓ Type-safe dataclasses (PersonalProfile, Job, Skill, etc.)")
    print("  ✓ Enums for SkillCategory, Proficiency, SectionKey")
    print("  ✓ Helper utilities (read_json, write_json, iter_nonblank_lines)")
    print("  ✓ Optimized batch matching (score_many_jobs)")
    print("  ✓ Parallel matching for large batches (score_jobs_parallel)")
    print("  ✓ Full backward compatibility with dict-based API")
    print("\nNext: Phase 2 (ESCO integration + German BERT)")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()