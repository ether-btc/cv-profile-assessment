"""Integration package — bridges between cv-profile-assessment and other tools.

Currently:
- `scout_adapter`: converts austria-job-scout data → cv-profile-assessment
  job schema. The austria-job-scout import is lazy so this package loads
  cleanly without it.
"""