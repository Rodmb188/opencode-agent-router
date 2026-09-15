import sys

old = """{%- if ns.multi_step_tool %}
    {{- raise_exception('No user query found in messages.') }}
{%- endif %}"""

target_len = len(old.encode("utf-8"))

# Novo bloco, sem raise. Precisamos de exatamente o mesmo comprimento em bytes.
# Usamos um comentário Jinja ({# ... #}) como padding.
header = "{%- if ns.multi_step_tool %}\n    {%- set ns.multi_step_tool = false %}{#"
footer = "#}\n{%- endif %}"

pad_needed = target_len - len(header.encode("utf-8")) - len(footer.encode("utf-8"))
if pad_needed < 0:
    sys.exit("header+footer ja excede tamanho alvo")

new = header + ("-" * pad_needed) + footer
new_bytes = new.encode("utf-8")

print("old len bytes:", target_len)
print("new len bytes:", len(new_bytes))
print("match:", len(new_bytes) == target_len)

if len(new_bytes) != target_len:
    sys.exit(1)

open("/tmp/opencode/replacement_old.bin", "wb").write(old.encode("utf-8"))
open("/tmp/opencode/replacement_new.bin", "wb").write(new_bytes)
print("saved replacement bins")