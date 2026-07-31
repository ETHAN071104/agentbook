# Reliability Agent Demo Plan

Target duration: 10-15 seconds.

## Shot sequence

1. Show a terminal with the administrator already logged in. Do not show
   `ccloud auth whoami` output.
2. Run:

   ```powershell
   python -m ops.reliability_agent.cli check
   ```

3. Show the fixed check labels and the generated Markdown report.
4. Hold briefly on:
   - cluster availability;
   - managed backups enabled;
   - latest backup freshness;
   - failed/pending restore count;
   - running-version support.
5. End on:

   > No learner content was accessed.

## Capture safety

Use a pre-inspected sanitized report. Crop or blur any unrelated terminal
history.

Never display:

- the real cluster or organization ID;
- organization name;
- administrator email;
- auth token or API key;
- connection URL or SQL hostname;
- backup or restore IDs;
- raw `ccloud auth whoami` output;
- local authentication-cache paths.

If a check is unavailable, show `unknown` honestly rather than substituting a
healthy fixture result as live evidence.
