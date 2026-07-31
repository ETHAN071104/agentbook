# MCP Diagnostics Demo Plan

## Recommended 10–15 second segment

1. Show a terminal titled **Protected MCP diagnostics**.
2. Run the fixed local diagnostics command.
3. Show a pre-generated, sanitized example report with:
   - MCP connected;
   - required schema detected;
   - document vector index detected;
   - learner-memory vector index detected;
   - workspace-safe weak-topic query verified;
   - fixed `EXPLAIN` completed.
4. End on:

   > No learner content was returned.

Until read-only OAuth is renewed, label the example **synthetic demonstration**
and describe the current command as **developer-operated protected MCP
diagnostics; authentication pending**.

## Do not show

- OAuth identity or consent details;
- cluster or organization identifiers;
- API keys or tokens;
- database URLs or hostnames;
- raw SQL rows;
- embeddings;
- full raw query plans;
- private schema dumps;
- arbitrary prompt, SQL, or MCP tool inputs.
