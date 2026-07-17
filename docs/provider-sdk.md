# Provider SDK

Providers implement the protocol in `packages/providers/base.py`. Capabilities are data, not UI assumptions. A feature must be disabled or clearly labeled when a provider flag is false.

MiniMax configuration is environment-driven:

- `MINIMAX_API_BASE`
- `MINIMAX_API_KEY`
- `MINIMAX_MUSIC_MODEL`
- `MINIMAX_COVER_MODEL`

The adapter is deliberately conservative. It does not map “cover” to “continuation”, does not claim stems or voice conversion, and returns provider metadata/trace IDs for auditability.
