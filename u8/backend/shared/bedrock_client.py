"""
BedrockClient - Claude Sonnet invocation via Amazon Bedrock.
"""
import json
import boto3
from shared.config import get_config


class BedrockClient:
    def __init__(self):
        config = get_config()
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=config.get("bedrock_region", "us-east-1"),
        )
        self._model_id = config.get(
            "bedrock_model_id",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",
        )

    def invoke(self, prompt: str, system: str = None, max_tokens: int = 2000, temperature: float = 0.3) -> str:
        """Invoke Claude Sonnet and return text response."""
        messages = [{"role": "user", "content": prompt}]

        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system:
            body["system"] = system

        response = self._client.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )

        result = json.loads(response["body"].read())
        return result["content"][0]["text"]

    def invoke_json(self, prompt: str, system: str = None, max_tokens: int = 2000, temperature: float = 0.3):
        """Invoke Claude Sonnet and parse JSON response."""
        text = self.invoke(prompt, system=system, max_tokens=max_tokens, temperature=temperature)

        # Extract JSON from response (handle markdown code blocks)
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())
