# Rebuilding the local models

Everything here targets **your own** Qwen3-family GGUF files. The two 27B models
(`nothink-v2`, `megabrain-v2`) share one **patched** base blob; they differ only
in whether *thinking* is enabled at request time (controlled by opencode, via
`config/opencode.jsonc` → `body.think`).

## 1. Obtain the base

Pull a Qwen3.6-3/6.5-class 27B abliterated GGUF and import it into Ollama.

```bash
ollama create <base-name> -f <path-to-your-modelfile>
```

## 2. Apply the chat-template fix (required for tool calls)

The stock template crashes with `No user query provided` during tool-calling
rounds. We fix it by rewriting the chat template **inside the GGUF**:

| File | Role |
|---|---|
| `qwen3_template.jinja` | the replacement (minimal, crash-free) template |
| `build_replacement.py` | reads a GGUF, swaps the `tokenizer.chat_template` string, writes a new blob |

```bash
python3 build_replacement.py <original.gguf> <patched.gguf> --template qwen3_template.jinja
```

## 3. Create the two 27B models

`nothink-v2` first — it is the base for `megabrain-v2`:

```bash
# nothink-v2.Modelfile expects FROM to point at your patched blob.
ollama create nothink-v2 -f models/nothink-v2.Modelfile

# megabrain inherits the same blob + template + context from nothink-v2.
ollama create megabrain-v2 -f models/megabrain-v2.Modelfile
```

### Why the context override is in the Modelfile and not the environment

`OLLAMA_CONTEXT_LENGTH` only changes the *default* context. A model with a baked
`PARAMETER num_ctx` **wins over the env var** — verified empirically on this
setup after the env-var alone left `qwen3-local` at 8192 and the 27B at 16384.
To actually cap the 27B models at 12288 we recreated them with:

```
PARAMETER num_ctx 12288
```

`ollama-start` still pins `OLLAMA_CONTEXT_LENGTH=12288` as a safety cap for any
model that has no explicit `num_ctx` (e.g. the vision model).

## The Modelfiles

**`nothink-v2.Modelfile`**
```
FROM <patched-blob-path>
TEMPLATE {{ .Prompt }}
PARAMETER stop <|im_end|>
PARAMETER num_ctx 12288
```

**`megabrain-v2.Modelfile`**
```
FROM nothink-v2:latest      # inherits blob + template + num_ctx
PARAMETER stop <|im_end|>
```

> The blob itself is ~16 GB and intentionally git-ignored — treat this directory
> as the *recipe*, not the artifact.