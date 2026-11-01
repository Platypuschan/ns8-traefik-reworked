Erste Vorabversion des angepassten Traefik-Moduls für NethServer 8, basierend auf ns8-traefik 4.2.5 mit Traefik 3.7.16.

- `set-route` und `get-route` kennen das optionale Feld `client_certificates`. Damit fragt eine Route ein TLS-Clientzertifikat an und reicht es an das Modul weiter. idp-reworked braucht das für die Anmeldung mit Gerätezertifikat. Bestehende Routen ändern sich nicht.
- Installation auf einem Knoten: `api-cli run cluster/update-module --data '{"module_url":"ghcr.io/platypuschan/traefik-reworked:4.2.5-reworked.1","instances":["traefik1"]}'`.
- Danach überspringen Core-Updates das Modul. Upstream-Traefik-Updates kommen nur noch über dieses Repository.

Keine Stable- oder Katalogfreigabe; Vorabversion für Testinstallationen. Geprüft als Update eines bestehenden `traefik1` im NS8-Test (Debian 13, Rocky 9). Nicht abgedeckt: Knoten mit echten Let's-Encrypt-Zertifikaten und mehrere Knoten.
