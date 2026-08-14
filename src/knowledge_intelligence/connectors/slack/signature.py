from slack_sdk.signature import SignatureVerifier


class SlackRequestVerifier:
    """Validate incoming HTTP requests using the Slack signing secret."""

    def __init__(self, signing_secret: str) -> None:
        if not signing_secret.strip():
            raise ValueError("Slack signing secret cannot be empty.")

        self._verifier = SignatureVerifier(
            signing_secret=signing_secret,
        )

    def verify(
        self,
        *,
        body: bytes,
        timestamp: str | None,
        signature: str | None,
    ) -> bool:
        if not timestamp or not signature:
            return False

        return self._verifier.is_valid(
            body=body,
            timestamp=timestamp,
            signature=signature,
        )
