import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, system_prompt: str, user_prompt: str, context: Optional[str] = None) -> str:
        pass

class MockLLMProvider(BaseLLMProvider):
    """Deterministic local LLM provider for rapid development, testing, and offline evaluation."""
    async def generate_response(self, system_prompt: str, user_prompt: str, context: Optional[str] = None) -> str:
        q_lower = user_prompt.lower()

        # Policy & Law queries: Carry forward / Accumulation
        if "carry forward" in q_lower or "carried forward" in q_lower or "accumulation" in q_lower or "accumulate" in q_lower:
            return (
                "Under Company Policy Section 4.1 and Section 18(1) of the Maharashtra Shops and Establishments Act, 2017:\n"
                "• Earned Leave (EL) can be accumulated and carried forward up to a maximum statutory ceiling of 45 days.\n"
                "• Any accrued EL beyond 45 days is subject to encashment or lapses at the end of the calendar year.\n"
                "• Casual Leave (CL) cannot be carried forward and lapses on December 31st."
            )

        # Notice period
        if "notice period" in q_lower or "resignation" in q_lower:
            return (
                "Under Company Policy and Section 18 of the Maharashtra Shops and Establishments Act, 2017:\n"
                "• Confirmed full-time personnel require a notice period of 30 days prior to exit.\n"
                "• Employees on probation require a notice period of 15 days.\n"
                "• Buyout of notice period requires approval from Department Head and HR Compliance."
            )

        # Rest intervals / Section 15
        if "section 15" in q_lower or "interval" in q_lower or ("rest" in q_lower and "hours" in q_lower):
            return (
                "Under Section 15 of the Maharashtra Shops and Establishments Act, 2017:\n"
                "• Continuous work cannot exceed 5 hours without a mandatory rest interval of at least 30 minutes.\n"
                "• The overall daily spread-over including work and rest intervals is capped at 10.5 hours."
            )

        # Section 18 statutory mandate overview
        if "section 18" in q_lower:
            return (
                "Section 18 of the Maharashtra Shops and Establishments Act, 2017 governs employee leave entitlements:\n"
                "• Earned Leave (EL): 1 day for every 20 days worked (18 days/year), accumulation capped at 45 days.\n"
                "• Casual Leave (CL): 8 days/year, non-cumulative, lapses on Dec 31.\n"
                "• Public Holidays: 8 mandatory paid national and festival holidays."
            )

        # Bereavement leave
        if "bereavement" in q_lower or "compassionate" in q_lower:
            return (
                "Under the Enterprise Compassionate Leave Policy 2026:\n"
                "• Employees are entitled to up to 5 days of paid Bereavement Leave for immediate family.\n"
                "• Bereavement absence does not debit from your Earned Leave or Casual Leave balances."
            )

        # Policy & Law general leave queries
        has_leave_token = "leave" in q_lower or bool(re.search(r"\b(cl|el|sl|lwp|holiday)\b", q_lower))
        if ("policy" in q_lower or "rule" in q_lower or "statutory" in q_lower or "maharashtra" in q_lower or "act" in q_lower or "handbook" in q_lower or "entitlement" in q_lower or "rules" in q_lower) and has_leave_token:
            if re.search(r"\b(cl|casual)\b", q_lower):
                return (
                    "Under Company Policy 2026 (Section 4.2) and Section 18(2) of the Maharashtra Shops and Establishments Act, 2017:\n"
                    "- Allocation: You receive 8 days of Casual Leave (CL) per calendar year.\n"
                    "- Carry Forward: CL lapses on December 31st and cannot be carried forward or encashed.\n"
                    "- Notice Period: At least 1 day prior notice is recommended."
                )
            elif re.search(r"\b(el|earned|privilege)\b", q_lower):
                return (
                    "Under Company Policy 2026 (Section 4.1) in accordance with Section 18(1) of the Maharashtra Act LXI of 2017:\n"
                    "- Allocation: 18 days of Earned Leave (EL) annually, credited at 1.5 days per month.\n"
                    "- Carry Forward: Up to 45 days can be accumulated and carried over into the next year.\n"
                    "- Encashment: Permitted up to 30 days upon exit/resignation."
                )
            elif re.search(r"\b(lwp|without pay)\b", q_lower):
                return (
                    "Under Company Policy Section 4.4:\n"
                    "- Eligibility: Leave Without Pay (LWP) is applicable only when EL, CL, and SL balances are completely exhausted.\n"
                    "- Approvals: Requires dual approval from your Reporting Manager and HR Manager."
                )
            else:
                return (
                    "Here is a summary of the leave categories:\n"
                    "1. Earned Leave (EL): 18 days/year, max accumulation of 45 days (Maharashtra Act 2017 Sec 18(1)).\n"
                    "2. Casual Leave (CL): 8 days/year, non-cumulative (Maharashtra Act 2017 Sec 18(2)).\n"
                    "3. Sick Leave (SL): 10 days/year, cumulative up to 20 days.\n"
                    "4. Leave Without Pay (LWP): Uncapped discretionary leave requiring manager and HR concurrence."
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

class GroqLLMProvider(BaseLLMProvider):
    """Production provider using Groq via LiteLLM with automatic multi-model failover."""
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")

    async def generate_response(self, system_prompt: str, user_prompt: str, context: Optional[str] = None) -> str:
        import litellm
        messages = [
            {"role": "system", "content": system_prompt},
        ]
        if context:
            messages.append({"role": "system", "content": f"Context:\n{context}"})
        messages.append({"role": "user", "content": user_prompt})

        os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
        key = self.api_key or settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
        if not key:
            key = settings.OPENAI_API_KEY if (settings.OPENAI_API_KEY or "").startswith("gsk_") else None
        if key:
            os.environ["GROQ_API_KEY"] = key

        from app.core.llm_bridge import get_active_groq_model, GROQ_FALLBACK_MODELS, switch_groq_fallback_model
        primary = get_active_groq_model()
        candidates = [primary] + [m for m in GROQ_FALLBACK_MODELS if m != primary]

        last_exc = None
        for model in candidates:
            try:
                resp = await litellm.acompletion(
                    model=model,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=1024,
                    api_key=key
                )
                return resp.choices[0].message.content or ""
            except Exception as e:
                last_exc = e
                logger.warning("Groq model '%s' completion failed (%s), switching to fallback candidate...", model, e)
                switch_groq_fallback_model(model)
                continue

        logger.error("All Groq models failed: %s", last_exc)
        if settings.MOCK_LLM_ENABLED:
            mock = MockLLMProvider()
            return await mock.generate_response(system_prompt, user_prompt, context)
        raise RuntimeError(f"All live Groq models failed: {last_exc}")

class OpenAILLMProvider(BaseLLMProvider):
    """Production provider using OpenAI (e.g. gpt-4o-mini via LiteLLM)."""
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")

    async def generate_response(self, system_prompt: str, user_prompt: str, context: Optional[str] = None) -> str:
        key = self.api_key or settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")
        if key and key.startswith("gsk_"):
            groq = GroqLLMProvider(api_key=key)
            return await groq.generate_response(system_prompt, user_prompt, context)

        try:
            import litellm
            messages = [
                {"role": "system", "content": system_prompt},
            ]
            if context:
                messages.append({"role": "system", "content": f"Context:\n{context}"})
            messages.append({"role": "user", "content": user_prompt})

            os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
            if key:
                os.environ["OPENAI_API_KEY"] = key

            resp = await litellm.acompletion(
                model=settings.OPENAI_MODEL or "gpt-4o-mini",
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            logger.error("OpenAI LLM provider call failed: %s", e)
            if settings.MOCK_LLM_ENABLED:
                mock = MockLLMProvider()
                return await mock.generate_response(system_prompt, user_prompt, context)
            raise

class VertexGeminiProvider(BaseLLMProvider):
    """Production provider using Google Vertex AI / Gemini via Google GenAI SDK."""
    def __init__(self):
        # Initialized lazily if GCP credentials are configured
        pass

    async def generate_response(self, system_prompt: str, user_prompt: str, context: Optional[str] = None) -> str:
        try:
            from google import genai
            client = genai.Client()
            full_prompt = f"System: {system_prompt}\nContext: {context or 'None'}\nUser: {user_prompt}"
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=full_prompt,
            )
            return response.text
        except Exception as e:
            logger.error("Vertex Gemini provider call failed: %s", e)
            if settings.MOCK_LLM_ENABLED:
                mock = MockLLMProvider()
                return await mock.generate_response(system_prompt, user_prompt, context)
            raise

def get_llm_provider() -> BaseLLMProvider:
    if settings.MOCK_LLM_ENABLED:
        return MockLLMProvider()

    groq_key = getattr(settings, "GROQ_API_KEY", None) or os.getenv("GROQ_API_KEY")
    openai_key = settings.OPENAI_API_KEY or os.getenv("OPENAI_API_KEY")

    if groq_key or (openai_key and openai_key.startswith("gsk_")):
        return GroqLLMProvider(api_key=groq_key or openai_key)

    if (settings.LLM_PROVIDER.lower() == "openai" or openai_key) and openai_key:
        return OpenAILLMProvider()

    if getattr(settings, "VERTEX_PROJECT_ID", None):
        return VertexGeminiProvider()

    return MockLLMProvider()

