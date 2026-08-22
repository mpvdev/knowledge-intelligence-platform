"""Light-hearted holding messages shown while an answer is being prepared."""

from __future__ import annotations

import random
import re

GENERAL: tuple[str, ...] = (
    "Got it 👋 Thinking this through…",
    "On it 👋 Give me a moment…",
    "Right then 👋 Let me pull this together…",
    "Good question 👋 Gathering my thoughts…",
)

GREETING: tuple[str, ...] = (
    "Hello 👋 Let me get my bearings…",
    "Hey 👋 Give me two seconds to wake up properly…",
    "Hi there 👋 Straightening my tie…",
)

ONBOARDING: tuple[str, ...] = (
    "Onboarding — my favourite subject 🚀 One moment…",
    "Rolling out the welcome mat 🚀 Just a sec…",
    "Let me map out the journey for you 🚀",
    "New here? Excellent 🚀 Let me line up the steps…",
)

COMPARISON: tuple[str, ...] = (
    "Ooh, a head-to-head ⚖️ Weighing them up…",
    "Let me line those two up side by side ⚖️",
    "Comparing notes ⚖️ One moment…",
)

WORKFLOW: tuple[str, ...] = (
    "Let me trace this one end to end 🧭",
    "Joining the dots 🧭 Won't be a moment…",
    "Following the thread 🧭",
)

OWNERSHIP: tuple[str, ...] = (
    "Let me find the right name for you 🧭",
    "Checking who looks after that 🧭",
)

TROUBLESHOOTING: tuple[str, ...] = (
    "Deep breath — let me find you the runbook 🧰",
    "Right, let's get you unstuck 🧰",
    "Rolling my sleeves up 🧰 One moment…",
)

PREREQUISITES: tuple[str, ...] = (
    "Let me count up what you'll need 📋",
    "Building you a checklist 📋 One moment…",
)

CATEGORIES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (
        re.compile(
            r"\b(hi|hello|hey|thanks|thank you|good (morning|afternoon|evening))\b",
            re.IGNORECASE,
        ),
        GREETING,
    ),
    (
        re.compile(
            r"\b(onboard\w*|get started|getting started|join\w*|new joiner|new to|"
            r"sign up|adopt\w*|migrat\w*|access)\b",
            re.IGNORECASE,
        ),
        ONBOARDING,
    ),
    (
        re.compile(
            r"\b(compare|comparison|versus|vs\.?|difference\w*|differ|better|"
            r"instead of)\b",
            re.IGNORECASE,
        ),
        COMPARISON,
    ),
    (
        re.compile(
            r"\b(runbook|incident|troubleshoot\w*|debug|broken|failing|failure|"
            r"error|stuck|not working|fix)\b",
            re.IGNORECASE,
        ),
        TROUBLESHOOTING,
    ),
    (
        re.compile(
            r"\b(prerequisite\w*|pre-?req\w*|require\w*|need to have|checklist)\b",
            re.IGNORECASE,
        ),
        PREREQUISITES,
    ),
    (
        re.compile(r"\b(who owns|who is responsible|owner|ownership|which team)\b", re.IGNORECASE),
        OWNERSHIP,
    ),
    (
        re.compile(
            r"\b(how does|how do|architecture|workflow|lifecycle|process|flow|"
            r"pipeline|works?|end to end)\b",
            re.IGNORECASE,
        ),
        WORKFLOW,
    ),
)


def waiting_message(question: str) -> str:
    """Pick a holding line that suits what was asked."""
    text = question.strip()
    if not text:
        return random.choice(GENERAL)
    for pattern, messages in CATEGORIES:
        if pattern.search(text):
            return random.choice(messages)
    return random.choice(GENERAL)
