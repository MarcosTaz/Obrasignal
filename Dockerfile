FROM caddy:2.11.4-alpine

COPY Caddyfile /etc/caddy/Caddyfile
COPY vertical_apps/industrial_claims/public_site/ /srv/

RUN test -f /srv/index.html \
    && test -f /srv/release.json \
    && grep -q 'VINDORUM' /srv/index.html \
    && ! grep -Eiq 'CausLedger|Certactum|Supplier Recovery|ObraSignal' /srv/index.html

EXPOSE 8080
