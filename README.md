<div align="center">

# ChatMock

**Allows Codex to work in your favourite chat apps and coding tools.**

[![PyPI](https://img.shields.io/pypi/v/chatmock?color=blue&label=pypi)](https://pypi.org/project/chatmock/)
[![Python](https://img.shields.io/pypi/pyversions/chatmock)](https://pypi.org/project/chatmock/)
[![License](https://img.shields.io/github/license/RayBytes/ChatMock)](LICENSE)
[![Stars](https://img.shields.io/github/stars/RayBytes/ChatMock?style=flat)](https://github.com/RayBytes/ChatMock/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/RayBytes/ChatMock)](https://github.com/RayBytes/ChatMock/commits/main)
[![Issues](https://img.shields.io/github/issues/RayBytes/ChatMock)](https://github.com/RayBytes/ChatMock/issues)

<br>


</div>

<br>

## Install

#### Homebrew
```bash
brew tap RayBytes/chatmock
brew install chatmock
```

#### pipx / pip
```bash
pipx install chatmock
```

#### GUI
Download from [releases](https://github.com/RayBytes/ChatMock/releases) (macOS & Windows)

#### Docker
See [DOCKER.md](DOCKER.md)

<br>

## Getting Started

```bash
# 1. Sign in with your ChatGPT account
# If you are running this on a headless server, append --headless
chatmock login

# 2. Start the server
chatmock serve
```


The server runs at `http://127.0.0.1:8000` by default. Use `http://127.0.0.1:8000/v1` as your base URL for OpenAI-compatible apps.

<br>

## Example usage

<details>
<summary><strong>Raycast Integration</strong></summary>

1. **Configure the Host URL**  
   Open your Raycast Extensions preferences, navigate to the **Ollama** settings section, and input the host URL (default is `127.0.0.1:8000`).  
   <img width="587" height="211" alt="Raycast Ollama Host URL configuration" src="https://github.com/user-attachments/assets/012c576b-189a-4b96-832d-bb054d484f2b" />

2. **Sync Your Models**  
   Click the **Sync Models** button, which will register all available models.

3. **Start Chatting**  
   Open the Raycast AI Chat interface. You will now see model slugs which you can chat with. 
</details>

<details>
<summary><strong>Terax (Agentic Terminal) Integration</strong></summary>

1. **Configure the provider settings**  
   Open your Terax settings, and switch to the **Models** tab, add a new provider (**OpenAI Compatible**), and input the host URL (default is `http://127.0.0.1:8000/v1`), along with the model IDs you wish to use (API key may be anything).  
   <img width="700" height="337" alt="image" src="https://github.com/user-attachments/assets/d1faf4e2-1969-417d-881e-5fb72f9aa252" />

2. **Favourite, and start using it!** <br>
   Go back to your main chat window, select the model by going to the OpenAI Compatible icon, and clicking the model there (you may favourite it here to quickly select it the next time if you switch between models)
   <img width="456" height="465" alt="image" src="https://github.com/user-attachments/assets/b9d2ba22-5747-4335-b095-8ec0fb2bb30c" />
</details>

<br>

## Supported Models

- `gpt-5.5`
- `gpt-5.5-pro`
- `gpt-5.5-instant`
- `gpt-5.6` (preconfigured for rollout)
- `gpt-5.4`
- `gpt-5.4-pro`
- `gpt-5.4-mini`
- `gpt-5.4-nano`
- `gpt-5.2-pro`
- `gpt-5-pro`
- `gpt-5-mini`
- `gpt-5-nano`
- `gpt-5.3-codex-spark`
- External provider models when enabled: Z.AI GLM, Xiaomi MiMo, DeepSeek, Ollama, LM Studio, and custom OpenAI-compatible providers

<br>

## Features

- Tool / function calling
- Vision / image input
- OpenAI-compatible `/v1/images/generations` with `b64_json` output
- Thinking summaries (via think tags)
- Configurable thinking effort
- Fast mode for supported models
- Web search tool
- External provider routing via `.env`
- OpenAI-compatible `/v1/responses` (HTTP + WebSocket)
- Ollama-compatible endpoints
- Reasoning effort exposed as separate models (optional)

<br>

## Configuration

All flags go after `chatmock serve`. These can also be set as environment variables.

| Flag | Env var | Options | Default | Description |
|------|---------|---------|---------|-------------|
| `--reasoning-effort` | `CHATGPT_LOCAL_REASONING_EFFORT` | none, minimal, low, medium, high, xhigh | medium | How hard the model thinks |
| `--reasoning-summary` | `CHATGPT_LOCAL_REASONING_SUMMARY` | auto, concise, detailed, none | auto | Thinking summary verbosity |
| `--reasoning-compat` | `CHATGPT_LOCAL_REASONING_COMPAT` | legacy, o3, think-tags | think-tags | How reasoning is returned to the client |
| `--fast-mode` | `CHATGPT_LOCAL_FAST_MODE` | true/false | false | Priority processing for supported models |
| `--enable-web-search` | `CHATGPT_LOCAL_ENABLE_WEB_SEARCH` | true/false | false | Allow the model to search the web |
| `--expose-reasoning-models` | `CHATGPT_LOCAL_EXPOSE_REASONING_MODELS` | true/false | false | List each reasoning level as its own model |

### Provider routing

ChatMock routes ChatGPT/Codex model IDs through your ChatGPT login. When an enabled provider model is requested, ChatMock proxies it to that provider's OpenAI-compatible endpoint instead.

| Provider | Enable with | Default base URL | Default models |
|----------|-------------|------------------|----------------|
| Z.AI GLM Coding Plan | `CHATMOCK_ZAI_API_KEY` | `https://api.z.ai/api/coding/paas/v4` | `glm-5.2`, `glm-5.1`, `glm-5`, `glm-5-turbo`, `glm-4.7`, `glm-4.5-air` |
| Xiaomi MiMo Token Plan | `CHATMOCK_XIAOMI_API_KEY` | `https://token-plan-sgp.xiaomimimo.com/v1` | `mimo-v2.5-pro`, `mimo-v2.5` |
| DeepSeek API | `CHATMOCK_DEEPSEEK_API_KEY` | `https://api.deepseek.com` | `deepseek-v4-flash`, `deepseek-v4-pro`, `deepseek-chat`, `deepseek-reasoner` |
| Ollama | `CHATMOCK_ENABLE_OLLAMA=true` | `http://localhost:11434/v1` | set `CHATMOCK_OLLAMA_MODELS` |
| LM Studio | `CHATMOCK_ENABLE_LM_STUDIO=true` | `http://localhost:1234/v1` | set `CHATMOCK_LM_STUDIO_MODELS` |

You can also add providers with `CHATMOCK_PROVIDERS_JSON`:

```json
[
  {
    "name": "my",
    "base_url": "https://example.com/v1",
    "api_key_env": "MY_API_KEY",
    "models": ["my-model"]
  }
]
```

Provider models work with `/v1/chat/completions`; `/v1/responses` is passed through when the provider supports it, otherwise ChatMock wraps a chat completion as a Responses object.
For Z.AI, use `glm-5.2` on the OpenAI-compatible endpoint; the `glm-5.2[1m]` suffix is for Anthropic-compatible Claude Code configuration and is not accepted by the OpenAI-compatible coding endpoint.

<details>
<summary><b>Web search in a request</b></summary>

```json
{
  "model": "gpt-5.4",
  "messages": [{"role": "user", "content": "latest news on ..."}],
  "responses_tools": [{"type": "web_search"}],
  "responses_tool_choice": "auto"
}
```

</details>

<details>
<summary><b>Image generation</b></summary>

```json
{
  "prompt": "a clean product render of a translucent keyboard on a dark desk",
  "model": "gpt-image-1.5",
  "quality": "high",
  "size": "2k"
}
```

POST this to `/v1/images/generations`. The response returns `data[0].b64_json`.

</details>

<details>
<summary><b>Fast mode in a request</b></summary>

```json
{
  "model": "gpt-5.4",
  "input": "summarize this",
  "fast_mode": true
}
```

</details>

<br>

## Important notice

Use responsibly and at your own risk. This project is not affiliated with OpenAI.

<br>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=RayBytes/ChatMock&type=Timeline)](https://www.star-history.com/#RayBytes/ChatMock&Timeline)
