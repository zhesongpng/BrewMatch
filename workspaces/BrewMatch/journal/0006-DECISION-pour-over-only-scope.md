# DECISION: Pour-Only Scope (Confirmed)

Date: 2026-05-09
Phase: /analyze
Source: User confirmation + red team finding F-01

## Decision

BrewMatch v1 is pour-over only: V60, Kalita Wave, and Origami. AeroPress is explicitly out of scope.

## Why

The user referenced AeroPrecipe.com and initially seemed to want AeroPress included. After discussion, the user confirmed: "remove AeroPress from scope. I want to focus on pour-over coffee."

The three drippers (V60, Kalita Wave, Origami) share ~90% of the parameter space. Adding all three gives recipe variety and demonstrates RAG retrieval across dripper types without significantly expanding the ML scope.

## Confirmed Scope Decisions

| Decision                                   | Rationale                                                |
| ------------------------------------------ | -------------------------------------------------------- |
| Pour-over only (V60, Kalita Wave, Origami) | Shared parameter space, all ML concepts demonstrated     |
| Manual text entry only (no photo/OCR)      | OCR unreliable, no ML value, adds 2 weeks                |
| 50-80 curated recipes                      | Sufficient for RAG retrieval                             |
| Feedback: thumbs + directional flags       | Anyone can identify "too sour"; no 1-10 expertise needed |
| Synthetic data for training                | Only viable path for timeline                            |
| Streamlit web app                          | Fastest to build, easiest to demo                        |

## How to Apply

- All specs, data models, and flows use the 3-dripper scope
- Onboarding quiz offers V60 / Kalita Wave / Origami (not AeroPress)
- Recipe knowledge base contains only pour-over recipes
