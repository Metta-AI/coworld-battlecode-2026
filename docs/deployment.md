# Deployment evidence

Target: the separate `battlecode-2026` Coworld and JVM league, using game-hosted
source-file policies on the existing Kubernetes infrastructure.

## Local verification

- 21 focused tests pass (archive validation, source packaging, staged-seat
  integrity, failure attribution, and artifact completion ordering).
- The original scaffold and unchanged SPAARK run successfully in Docker.
- Identical packages on opposing sides work.
- A deliberately infinite-loop Java player completes a match under the original
  bytecode enforcement.
- Unchanged SPAARK versus Gravy completed on DefaultSmall in 219 rounds; Gravy won.
- Current Coworld certification passed all 10 steps, including the real
  game-hosted episode and WebSocket Ping/Pong. Tooling source revision:
  `18b4a69bdffbb9efa8c3577ebd4a3f41a534f30e`.

Hosted identifiers and league evidence will be added after registration and the
first completed hosted round. Local success alone does not establish deployment.
