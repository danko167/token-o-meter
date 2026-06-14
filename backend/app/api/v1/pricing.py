from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.pricing import ModelPricing, PricingResult
from app.services.llm_models import (
    COMMERCIAL_REFERENCE_MODELS,
    DIRECT_OPENAI_MODELS,
    OPENAI_PROVIDER,
    OPENROUTER_MODELS,
    OPENROUTER_PROVIDER,
    find_direct_openai_model,
    find_openrouter_model,
    is_provider_configured,
    provider_disabled_note,
    provider_display_name,
    selectable_notes,
)

router = APIRouter(prefix="/pricing", tags=["pricing"])


@router.get("", response_model=PricingResult)
async def get_pricing() -> PricingResult:
    settings = get_settings()
    configured_model = settings.llm_model
    openrouter_enabled = is_provider_configured(OPENROUTER_PROVIDER, settings)
    openai_enabled = is_provider_configured(OPENAI_PROVIDER, settings)
    rows = [
        ModelPricing(
            provider=provider_display_name(OPENROUTER_PROVIDER),
            model=model.id,
            display_name=model.name,
            input_cost_per_million_tokens_usd=model.input_cost_per_million,
            output_cost_per_million_tokens_usd=model.output_cost_per_million,
            active=model.id == configured_model,
            selectable=openrouter_enabled,
            is_free=model.is_free,
            notes=selectable_notes(model.notes, OPENROUTER_PROVIDER, settings),
        )
        for model in OPENROUTER_MODELS
    ]

    rows.extend(
        ModelPricing(
            provider=provider_display_name(OPENAI_PROVIDER),
            model=model.id,
            display_name=model.name,
            input_cost_per_million_tokens_usd=model.input_cost_per_million,
            output_cost_per_million_tokens_usd=model.output_cost_per_million,
            active=model.api_model == settings.openai_model,
            selectable=openai_enabled,
            is_free=False,
            notes=selectable_notes(model.notes, OPENAI_PROVIDER, settings),
        )
        for model in DIRECT_OPENAI_MODELS
    )

    rows.extend(
        ModelPricing(
            provider=model.provider,
            model=model.id,
            display_name=model.name,
            input_cost_per_million_tokens_usd=model.input_cost_per_million,
            output_cost_per_million_tokens_usd=model.output_cost_per_million,
            active=False,
            selectable=False,
            is_free=False,
            notes=model.notes,
        )
        for model in COMMERCIAL_REFERENCE_MODELS
    )

    configured_openai_model = f"openai:{settings.openai_model}"
    if (
        openai_enabled
        and find_direct_openai_model(configured_openai_model) is None
    ):
        rows.insert(
            0,
            ModelPricing(
                provider=provider_display_name(OPENAI_PROVIDER),
                model=configured_openai_model,
                display_name=settings.openai_model,
                input_cost_per_million_tokens_usd=None,
                output_cost_per_million_tokens_usd=None,
                active=True,
                selectable=True,
                is_free=False,
                notes="Configured by JEAI_OPENAI_MODEL. Pricing not known.",
            ),
        )

    if find_openrouter_model(configured_model) is None:
        rows.insert(
            0,
            ModelPricing(
                provider=provider_display_name(OPENROUTER_PROVIDER),
                model=configured_model,
                display_name=configured_model,
                input_cost_per_million_tokens_usd=settings.llm_input_cost_per_million,
                output_cost_per_million_tokens_usd=settings.llm_output_cost_per_million,
                active=True,
                selectable=openrouter_enabled,
                is_free=(
                    settings.llm_input_cost_per_million == 0
                    and settings.llm_output_cost_per_million == 0
                ),
                notes=(
                    "Configured by JEAI_OPENROUTER_MODEL."
                    if openrouter_enabled
                    else "Configured by JEAI_OPENROUTER_MODEL. "
                    f"{provider_disabled_note(OPENROUTER_PROVIDER)}"
                ),
            ),
        )

    return PricingResult(models=rows)
