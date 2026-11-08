---
parent: Connecting to LLMs
nav_order: 500
---

# OpenAI compatible APIs

Aider can connect to any LLM which is accessible via an OpenAI compatible API endpoint.

First, install aider:

{% include install.md %}

Then configure your API key and endpoint:

```
# Mac/Linux:
export OPENAI_API_BASE=<endpoint>
export OPENAI_API_KEY=<key>

# Windows:
setx OPENAI_API_BASE <endpoint>
setx OPENAI_API_KEY <key>
# ... restart shell after setx commands
```

Start working with aider and your OpenAI compatible API on your codebase:

```bash
# Change directory into your codebase
cd /to/your/project

# Prefix the model name with openai/
aider --model openai/<model-name>
```

See the [model warnings](warnings.html)
section for information on warnings which will occur
when working with models that aider is not familiar with.

## One endpoint, many models

Gateways, proxies and self-hosted routers commonly serve many models — from
many vendors — behind a single base URL and a single API key.
Aider works with any of them, because the base URL and the key are
*endpoint-wide* settings:
they apply to every model name you use, no matter which vendor actually
serves that model.
That makes it possible to benchmark and mix models without
opening an account with each provider.

```bash
export OPENAI_API_BASE=https://your-endpoint.example.com/v1
export OPENAI_API_KEY=<key>
```

Use the full URL your endpoint expects, including its version path
(often `/v1`).

### Name the model exactly as the endpoint does

Always keep the `openai/` prefix in the model name.
Aider strips the prefix before sending the request,
so your endpoint receives the bare model name:

```
POST https://your-endpoint.example.com/v1/chat/completions
{"model": "qwen3-coder-plus", ...}
```

The prefix is what tells aider to speak the OpenAI protocol to
`OPENAI_API_BASE`.
Without it, aider has no provider to attribute the model to,
and the request fails before it leaves your machine:

```
litellm.BadRequestError: LLM Provider NOT provided. Pass in the LLM provider you
are trying to call. You passed model=qwen3-coder-plus
```

So `--model openai/qwen3-coder-plus` works even though `qwen3-coder-plus`
isn't an OpenAI model — for aider the name is just a string to pass to
your endpoint, and the model must be named the way that endpoint names it.

### Teach aider about the models

Models served by a gateway are usually unknown to aider, which means:

- A *Unknown context window size and costs* warning
  (see [model warnings](warnings.html)).
- No cost accounting, since aider doesn't know the token prices.
- The generic `whole` edit format, rather than a diff-based format
  tuned for the model.

All three can be fixed declaratively, without touching aider's code.
Context window and costs go in a `.aider.model.metadata.json` file:

```json
{
    "openai/qwen3-coder-plus": {
        "max_tokens": 32000,
        "max_input_tokens": 128000,
        "max_output_tokens": 32000,
        "input_cost_per_token": 0.0000003,
        "output_cost_per_token": 0.0000012,
        "litellm_provider": "openai",
        "mode": "chat"
    }
}
```

And the edit format goes in a `.aider.model.settings.yml` file:

```yaml
- name: openai/qwen3-coder-plus
  edit_format: diff
  use_repo_map: true
```

Keep the `openai/` prefix on the keys in both files,
and set `litellm_provider` to `openai`.
See
[advanced model settings](/docs/config/adv-model-settings.html)
for the other settings you can set, and for the other places these files
can live.

### Architect and editor through one endpoint

[Architect mode](/docs/usage/modes.html) pairs a planner model with an editor
model, and both models can come from the same endpoint:

```bash
aider --architect \
    --model openai/<planner-model> \
    --editor-model openai/<editor-model>
```

Each name is passed to `OPENAI_API_BASE` with the same key,
so a cross-model pairing doesn't require a second account:

```
Model: openai/<planner-model> with architect edit format
Editor model: openai/<editor-model> with editor-whole edit format
```

The `/editor-model` and `/weak-model` commands take the same
`openai/<model-name>` form, and can be used mid-session.

### Switching models mid-session

`/model openai/<other-model>` switches the main model at any point
(see [in-chat commands](/docs/usage/commands.html)).
Because the base URL and key belong to the endpoint rather than to a
single model, switching between models — including models from different
vendors — keeps working with no reconfiguration.
Aider re-resolves settings and warnings for the new name, so models you
haven't described in the files above will print the unknown model warning
again each time you switch to them.
