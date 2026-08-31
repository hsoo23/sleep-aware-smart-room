# Security and Privacy

- Never commit Gmail app passwords, API tokens, SSH keys, private IP details, or participant identifiers.
- Store runtime secrets in `.env`; use `.env.example` only for variable names and safe defaults.
- Keep consented raw participant data outside Git. The `data/raw` and `data/processed` contents are ignored.
- Use participant codes in logs and results. Keep the re-identification key separately with restricted access.
- Revoke and rotate a credential immediately if it is accidentally committed.

