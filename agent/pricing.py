"""Model prices in USD per million tokens, as (input, output).

Update these from openrouter.ai/models when prices change.
A model that is not listed is counted as cost 0.
"""

PRICES = {
    "anthropic/claude-sonnet-5": (3.00, 15.00),
    "google/gemma-4-31b-it": (0.13, 0.38),
    "google/gemma-4-31b-it:free": (0.0, 0.0),
    "nvidia/nemotron-3.5-lightning:free": (0.0, 0.0),
}
REFERENCE_MODEL = "anthropic/claude-sonnet-5"


def cost_of(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price, out_price = PRICES.get(model, (0.0, 0.0))
    return (input_tokens * in_price + output_tokens * out_price) / 1_000_000