# certs/

nginx mounts this directory read-only and expects two files that are **not
in git**:

- `origin.crt`: the Cloudflare Origin CA certificate for solusvires.com
- `origin.key`: its private key

Both live only on the machine that runs nginx (the droplet, at
`/root/solusvires/certs/`). The certificate is public, but tracking it made
every reissue on the droplet show up as an uncommitted change and stop
`scripts/deploy.sh` at preflight (2026-10-07). Keep the pair together: a
certificate that does not match the key stops nginx from starting.

To check they match:

    openssl x509 -in certs/origin.crt -noout -pubkey | openssl md5
    openssl pkey -in certs/origin.key -pubout | openssl md5

Reissuing: Cloudflare dashboard, SSL/TLS, Origin Server, Create Certificate;
save both files here and `docker compose exec web nginx -s reload`.

CI generates a self-signed pair in this directory for its own stack; local
development uses `scripts/preview.sh`, which has no nginx and needs no
certificate.
