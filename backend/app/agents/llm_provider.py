import os
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.core.config import settings

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, system_prompt: str, user_prompt: str, context: Optional[str] = None) -> str:
        pass

class MockLLMProvider(BaseLLMProvider):
    """Deterministic local LLM provider for rapid development, testing, and offline evaluation."""
    async def generate_response(self, system_prompt: str, user_prompt: str, context: Optional[str] = None) -> str:
        q_lower = user_prompt.lower()

        # Policy & Law queries
        if "leave" in q_lower and ("policy" in q_lower or "rule" in q_lower or "statutory" in q_lower or "maharashtra" in q_lower or "how many" in q_lower or "can i" in q_lower):
            if "cl" in q_lower or "casual" in q_lower:
                return (
                    "Under Company Policy 2026 (Section 4.2) and Section 18(2) of the Maharashtra Shops and Establishments Act, 2017:\n"
                    "- **Allocation**: You receive 8 days of Casual Leave (CL) per calendar year.\n"
                    "- **Carry Forward**: CL lapses on December 31st and cannot be carried forward or encashed.\n"
                    "- **Notice Period**: At least 1 day prior notice is recommended."
                )
            elif "el" in q_lower or "earned" in q_lower or "privilege" in q_lower:
                return (
                    "Under Company Policy 2026 (Section 4.1) in accordance with Section 18(1) of the Maharashtra Act LXI of 2017:\n"
                    "- **Allocation**: 18 days of Earned Leave (EL) annually, credited at 1.5 days per month.\n"
                    "- **Carry Forward**: Up to 45 days can be accumulated and carried over into the next year.\n"
                    "- **Encashment**: Permitted up to 30 days upon exit/resignation."
                )
            elif "lwp" in q_lower or "without pay" in q_lower:
                return (
                    "Under Company Policy Section 4.4:\n"
                    "- **Eligibility**: Leave Without Pay (LWP) is applicable only when EL, CL, and SL balances are completely exhausted.\n"
                    "- **Approvals**: Requires dual approval from your Reporting Manager and HR Manager."
                )
            else:
                return (
                    "Here is a summary of the leave categories:\n"
                    "1. **Earned Leave (EL)**: 18 days/year, max accumulation of 45 days (Maharashtra Act 2017 Sec 18(1)).\n"
                    "2. **Casual Leave (CL)**: 8 days/year, non-cumulative (Maharashtra Act 2017 Sec 18(2)).\n"
                    "3. **Sick Leave (SL)**: 10 days/year, cumulative up to 20 days.\n"
                    "4. **Leave Without Pay (LWP)**: Uncapped discretionary leave requiring manager and HR concurrence."
                )

        # Overtime & Working hours
        if "overtime" in q_lower or "working hours" in q_lower or "spread-over" in q_lower:
            return (
                "In compliance with Section 13 & 15 of the Maharashtra Shops and Establishments Act, 2017:\n"
                "- **Standard Hours**: Maximum 9 hours/day and 48 hours/week.\n"
                "- **Company Standard**: 8 hours/day and 40 hours/week.\n"
                "- **Overtime Rate**: Work beyond standard limits is compensable at twice the ordinary wage rate (2.0x)."
            )

        # Balance inquiries
        if "balance" in q_lower:
            return "You can check your real-time verified leave ledger below. The system maintains authoritative balances directly in the database."

        # Timesheet inquiries
        if "timesheet" in q_lower or "log hours" in q_lower or "report" in q_lower:
            return (
                "Timesheets are governed by the Enterprise Working Hours Policy:\n"
                "- Standard hours: 8 hours/day.\n"
                "- Daily logging limit: 16 hours max across projects.\n"
                "- Submission window: Weekly by Monday 12:00 PM."
            )

        return (
            "I am your AI HR Assistant. I can assist you with:\n"
            "1. Checking leave balances and submitting leave applications (EL, CL, SL, LWP).\n"
            "2. Explaining company policies and statutory provisions under Maharashtra Labour Law.\n"
            "3. Logging project hours and generating timesheet reports."
        )

class VertexGeminiProvider(BaseLLMProvider):
    """Production provider using Google Vertex AI / Gemini via Google GenAI SDK."""
    def __init__(self):
        # Initialized lazily if GCP credentials are configured
        pass

    async def generate_response(self, system_prompt: str, user_prompt: str, context: Optional[str] = None) -> str:
        # If Vertex AI credentials are not active, fall back to mock provider gracefully
        try:
            from google import genai
            client = genai.Client()
            full_prompt = f"System: {system_prompt}\nContext: {context or 'None'}\nUser: {user_prompt}"
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=full_prompt,
            )
            return response.text
        except Exception:
            mock = MockLLMProvider()
            return await mock.generate_response(system_prompt, user_prompt, context)

def get_llm_provider() -> BaseLLMProvider:
    if settings.MOCK_LLM_ENABLED or not settings.VERTEX_PROJECT_ID:
        return MockLLMProvider()
    return VertexGeminiProvider()
