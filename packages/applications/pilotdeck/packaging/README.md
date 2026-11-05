# PilotDeck packaging

`source-ref.toml` records the external PilotDeck checkout consumed by this application package. The future packaging step should read that reference, build or stage the product through the supported integration boundary, and emit a reproducible Mint application artifact.

Do not copy the PilotDeck repository into AgentOS. Keep generated build output outside the source tree unless the Mint workflow explicitly requires a checked-in fixture.
