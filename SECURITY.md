# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| Latest  | :white_check_mark: |
| Older   | :x:                |

Only the latest release on the `main` branch receives security fixes.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

To report a security vulnerability, please send an email to:

**security@outpace.ai**

Include as much detail as possible:

- A description of the vulnerability and its potential impact
- Steps to reproduce the issue
- Any relevant logs, screenshots, or proof-of-concept code

## Response Timeline

- **Acknowledgement**: Within 48 hours of receiving your report
- **Initial assessment**: Within 5 business days
- **Resolution or mitigation**: Depends on severity — critical issues are prioritized and targeted for resolution within 14 days

You will be kept informed as the issue is investigated and resolved.

## Scope

This security policy covers the OutPace B2B Intelligence Platform, including:

- FastAPI backend (`backend/`)
- React frontend (`frontend/`)
- Authentication and authorization logic
- Tenant isolation mechanisms
- API endpoints and data handling

Out of scope:

- Third-party dependencies (report those to the respective upstream projects)
- Denial-of-service attacks without a realistic exploitation scenario
- Issues in infrastructure or hosting providers

## Disclosure

We follow a coordinated disclosure model. Please allow us reasonable time to address a reported issue before any public disclosure. We will credit reporters who follow responsible disclosure practices.
