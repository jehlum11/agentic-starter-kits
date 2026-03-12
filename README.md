<div style="text-align: center;">

![Agentic Starter Kits](/images/ask_logo.png)

# Agentic Starter Kits

</div>

## Purpose

Production-ready agent templates to build and deploy LLM-powered agents. Run locally (e.g. with Ollama/Llama Stack) or
deploy to Red Hat OpenShift. Each agent has step-by-step docs.

## Agents

Choose an agent and follow its README for setup and deployment:

- **[LangGraph ReAct](./agents/base/langgraph_react_agent/README.md)** – General-purpose agent using a ReAct loop: it
  reasons and calls tools (e.g. search, math) step by step. Built with LangGraph and LangChain.
- **[LlamaIndex WebSearch](./agents/base/llamaindex_websearch_agent/README.md)** – Agent built on LlamaIndex that uses a
  web search tool to query the internet and use the results in its answers.
- **[OpenAI Responses](./agents/base/openai_responses_agent/README.md)** – Minimal agent with no framework: only the
  OpenAI Python client and an Action/Observation loop with tools. Use with OpenAI or any compatible API.
- **[LangGraph Agentic RAG](./agents/community/langgraph_agentic_rag/README.md)** – RAG agent that indexes documents in
  a vector store (Milvus) and retrieves relevant chunks to augment the LLM’s answers with your own data.
- **[LangGraph ReAct with Database Memory](./agents/community/langgraph_react_with_database_memory/README.md)** – ReAct
  agent with PostgreSQL-backed conversation memory. Full chat history is persisted in the database while a FIFO sliding
  window keeps only the last N messages in the LLM context. Built with LangGraph and `create_agent` middleware.

## Deployment Options

Agents in this repository can support two deployment modes:

### 🖥️ Local Development

- Run agents on your local machine
- Use Llama Stack server with Ollama for model serving
- Ideal for development, testing, and experimentation
- No cloud infrastructure required

### ☁️ Production Deployment

- Deploy agents to Red Hat OpenShift Cluster
- Containerized deployment with Kubernetes
- Production-grade scaling and monitoring
- CI/CD ready

## Repository Structure

```
Agentic-Starter-Kits/
├── agents/
│   ├── base/
│   │   ├── langgraph_react_agent/       # LangGraph ReAct agent 
│   │   └── llamaindex_websearch_agent/  # LlamaIndex web search agent
│   │   └── openai_responses_agent/      # OpenAI Responses API (no framework)
│   └── community/
│       ├── langgraph_agentic_rag/       # RAG agent with Milvus vector store
│       └── langgraph_react_with_database_memory/  # ReAct agent with PostgreSQL memory (FIFO)
├── run_llama_server.yaml                # Llama Stack server configuration
├── utils.py                             # Shared utilities
└── README.md                            # This file
```

---

## How to Use This Repository

1. **Start Here**: Read this README to understand the overall structure and install core dependencies
2. **Choose an Agent**: Select an agent from the `agents/` directory based on your use case
3. **Follow Agent README**: Navigate to the agent's directory and follow its specific README for:
    - Agent-specific dependencies installation
    - Configuration and setup
    - Local development or OpenShift deployment
    - Usage examples and API endpoints

### Pre-requisitions to run that repo

Run this script to set up repo stuff with a use of [UV](https://docs.astral.sh/uv/) and python 3.12

Download repo

```bash
git clone https://github.com/red-hat-data-services/agentic-starter-kits
```

Get into root dir

```bash
cd agentic-starter-kits
```

Install UV

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Additional Resources

- **Llama Stack Documentation**: https://llama-stack.readthedocs.io/
- **Ollama Documentation**: https://docs.ollama.com/
- **OpenShift Documentation**: https://docs.openshift.com/
- **Kubernetes**: https://kubernetes.io/docs/

## Contributing

Contributions are welcome! Please see individual agent READMEs for specific guidelines.

## License

MIT License

Copyright (c) 2026