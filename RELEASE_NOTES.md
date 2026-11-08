Stabile Version 4.2.6 des angepassten Traefik-Moduls für NethServer 8, im Katalog `platypuschan` gelistet. Inhaltlich identisch zu 4.2.5-reworked.2 (basierend auf ns8-traefik 4.2.5, Traefik 3.7.17); neu ist nur die Versionsnummer ohne Suffix, weil der NS8-Katalog Versionen mit Suffix als Testversionen behandelt.

- Sicherheitsupdate gegenüber 3.7.16: [GHSA-xv5x-242w-7hf7](https://github.com/traefik/traefik/security/advisories/GHSA-xv5x-242w-7hf7) (hoch, Ressourcen-DoS über `Authorization: NTLM`/`Negotiate`). Die Runtime bleibt auf den geprüften Multi-Arch-Digest gepinnt.
- `client_certificates` (Route-Option für idp-reworked): Zertifikat-Header werden als erste Middlewares der Route bereinigt und gesetzt; fehlendes `host`/`http2https` ergibt eine strukturierte Validierung; widersprüchliche Routen eines Hosts erzeugen eine Journal-Warnung.
- Versionsschema: ab jetzt normales SemVer dieses Forks (`4.2.6`, `4.2.7`, ...). Die Zahl folgt nicht mehr der Upstream-Version; der Upstream-Stand steht in den Release-Notes.

Installation oder Update eines Knotens: Katalog `platypuschan` aktivieren, dann erscheint das Update in den Core-Apps. Ohne Katalog: `api-cli run cluster/update-module --data '{"module_url":"ghcr.io/platypuschan/traefik-reworked:4.2.6","instances":["traefik1"]}'`. Traefik ist ein Core-Modul und wird im Software-Center nicht als installierbare App angezeigt. Ist der Katalog aktiv, aktualisiert ein Core-Update das Modul mit.

Geprüft per CI (Python-Tests, Build, QEMU Debian 13 und Rocky 9 als Update eines bestehenden `traefik1`). Nicht abgedeckt: Knoten mit echten Let's-Encrypt-Zertifikaten, mehrere Knoten, Live-Test mit einem Browser-Clientzertifikat.
