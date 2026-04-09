<div align="center">

<h1>🧠 AutoForze Engine</h1>

<h3>The core AI autonomous orchestration and execution engine powering TaskForze.</h3>

<p>
  <img src="https://img.shields.io/badge/Go-1.25+-00ADD8?style=flat&logo=go&logoColor=white" alt="Go">
  <img src="https://img.shields.io/badge/Architecture-x86__64%20|%20ARM64-blue" alt="Hardware">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
</p>

</div>

---

**AutoForze** is an ultra-lightweight, high-performance personal AI agent engine written entirely in **Go**. It serves as the intelligent brain behind [TaskForze](https://github.com/balaraj74/TaskForze), providing continuous autonomous action, background task execution, and multi-channel communication capabilities.

## ✨ Features

🪶 **Ultra-lightweight**: Core memory footprint <10MB.
⚡️ **Lightning-fast boot**: Highly optimized Go execution. Boots in milliseconds.
🧠 **Smart routing**: Rule-based model routing allows simple queries to go to lightweight models, saving API costs and reducing latency.
🔌 **MCP Support**: Native [Model Context Protocol](https://modelcontextprotocol.io/) integration to seamlessly connect the agent with local filesystems, tools, and databases.
👁️ **Vision Pipeline**: Built-in support for analyzing images and files automatically alongside text queues.
🤝 **Multi-Channel**: Directly hooks into messaging platforms like Telegram, Discord, and WhatsApp.

## 📦 Integrating AutoForze

The engine is primarily designed to be run as an embedded background service within the broader TaskForze ecosystem, but it can be built and run standalone.

### Build from source

```bash
cd autoforze
make deps

# Build core binary
make build

# The binary will be available in the bin/ directory
./bin/autoforze
```

## ⚙️ Configuration

AutoForze uses a `config.json` (typically located in `autoforze_data/config.json`) to define:

1. **LLM Providers:** (OpenAI, Gemini, Anthropic, local models via Ollama/vLLM)
2. **Tools & MCP Servers:** Connecting AutoForze to the outside world
3. **Channels:** Exposing the agent to WhatsApp, Telegram, etc.

Example configuration snippet:
```json
{
  "model_list": [
    {
      "model_name": "primary-agent",
      "model": "gemini/gemini-3.1-pro-preview"
    }
  ],
  "tools": {
    "mcp": {
      "enabled": true
    }
  }
}
```

## 💬 Hooks & Events

AutoForze utilizes an event-driven hook system (Observer, Interceptor, Approval constraints) to allow the primary TaskForze Python backend to safely steer the agent, provide runtime context, or intercept dangerous commands before they execute.

## 🤝 Contribution

This engine is part of the `TaskForze` project. For core engine modifications, please open pull requests targeting this subdirectory conforming to the standard Go `.golangci-lint` guidelines.
