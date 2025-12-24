# Here are your Instructions

## Testing

![CI Status](https://img.shields.io/badge/CI-status-lightgrey)

Testing follows a stratified model across functional categories and six strata to balance happy-path coverage with boundary, invalid, empty, performance, and failure scenarios. The CARFAX runner coordinates these checks and supports Monte Carlo execution for confidence runs across the full matrix. You can run targeted checks locally or bring up the Docker-based stack to mirror the integration environment and mocks. For complete instructions and environment details, see [TESTING.md](TESTING.md) and the full plan in [docs/test-plan.md](docs/test-plan.md).
