# VirtuAI: TypeHype

VirtuAI is a Bahçeşehir University capstone project. TypeHype is the application developed within it. The project addresses the coordination of trend research, content planning, generation, review and publishing for a virtual persona.

Developed by a three-person team, the project combines agent workflows with a web application and publishing integrations. My contributions focused on service architecture and agent orchestration. See the [VirtuAI case study](https://ayhangurbangeldiyev.com/work/virtuai) for further context.

## Capabilities

- A React interface and FastAPI backend for trend and content workflows
- Sequential CrewAI agents for trend selection and content planning
- Style-example retrieval using vector similarity and additional ranking signals
- Account-scoped agent memory with a semantic-recall integration
- Draft review and a guarded Postiz integration for scheduling content
- An MCP endpoint exposing selected application tools

## Architecture

```text
Trend signals + account context     Style examples + agent memory
              |                                  |
              v                                  v
  CrewAI: TrendScout -> Planner <--------- Retrieval and context
              |
              v
  Content generation -> compliance checks
              |
              +--> optional visual / video steps
              |
              +--> dry run / skip / failure
              |
              +--> draft review or configured publishing via Postiz
```

The CrewAI crew runs two sequential tasks: TrendScout selects a trend and Planner prepares the content brief. The surrounding flow handles generation, compliance checks and publishing so the crew can focus on selection and planning.

An optional LangGraph execution path wraps the content flow in a state graph with checkpoint and resume support. It is enabled through configuration and is not used for every run. A separate executive graph coordinates role-based decisions and can interrupt for human approval.

Style retrieval embeds the topic and searches stored examples by vector similarity. It can also combine similarity with engagement and other ranking signals. Agent memory is a separate integration. The planner can query account-scoped memory through a semantic-recall tool.

Review and publishing behavior depends on configuration. The publishing wrapper checks gate outcomes before scheduling. Non-UI publishing requires an explicit configuration override. The RSS GitHub Actions workflow supports manual dispatch. Its former schedule is disabled.

## Technology

| Responsibility | Technologies |
| --- | --- |
| Frontend | React, React Router, Supabase client |
| Backend and APIs | Python, FastAPI, MCP |
| Agent orchestration | CrewAI, optional LangGraph execution path |
| Database and retrieval | Supabase, PostgreSQL, pgvector |
| Integrations | Postiz, Xquik |
| Development and testing | pytest, GitHub Actions |

## Repository guide

- [`frontend/`](frontend/): interface and client-side application
- [`backend/`](backend/): API, services, migrations and tests
- [`hype_crew/`](hype_crew/): content agents, flow, memory tools and tests
- [`hype_exec/`](hype_exec/): separate executive graph and tests
- [`deploy/`](deploy/): service and timer definitions
- [`n8n/`](n8n/): workflow artifacts
- [`docs/`](docs/): technical documentation

## Setup and reproducibility

The project uses Python, Node.js and a Supabase project. Each workflow also requires configuration for its external services. Backend, content workflow and executive workflow dependencies are listed in separate requirements files. The root requirements file does not provide a complete backend installation.

Review the [backend environment example](backend/.env.example), [frontend environment example](frontend/.env.example) and [system guide](SYSTEM_GUIDE.md) before attempting setup. Use an isolated environment and avoid production credentials or live publishing accounts while exploring.

## Tests and limitations

Test code is available in [`backend/tests/`](backend/tests/), [`hype_crew/tests/`](hype_crew/tests/) and [`hype_exec/tests/`](hype_exec/tests/). The [faithfulness CI workflow](.github/workflows/faithfulness-ci.yml) defines a structural check and a separate benchmark. The benchmark requires external model access and can be skipped when credentials are unavailable. The repository also contains a [secret-scan workflow](.github/workflows/secret-scan.yml).

These tests and workflows were not executed as part of this README update. Their presence does not establish model performance or current deployment status. A clean end-to-end installation, the full migration sequence and external integrations remain unverified. The repository calls the `match_hype_memory` database function, but its complete SQL definition was not found in the inspected migrations.

## Documentation and rights

- [System guide](SYSTEM_GUIDE.md)
- [System documentation](docs/SYSTEM_DOCUMENTATION.md)
- [Deprecated modules](docs/DEPRECATED_MODULES.md)
- [Project roadmap](docs/specs/ROADMAP.md)
- [Product requirements](memory/PRD.md)

All rights reserved. No open-source license is currently provided in this repository. Contact the project maintainers regarding reuse or redistribution.
