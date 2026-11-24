Vorabversion 4.2.8-reworked.1 des angepassten Traefik-Moduls für NethServer 8 (Prerelease, nicht im stabilen Katalogkanal). Update von 4.2.7.

- **User-Agent im Zugriffslog:** Traefik verwirft standardmäßig alle Request-Header im Zugriffslog. Jetzt bleibt nur der `User-Agent` erhalten; Cookie, Authorization, Referer und alle anderen Header bleiben weiterhin draußen. Dadurch kann CrowdSec (Modul Guardian) bekannte Scanner-Werkzeuge erkennen. Dieselbe Änderung ist upstream als NethServer/ns8-traefik#152 offen.
  - Neue Module bekommen die Einstellung bei der Installation, bestehende beim Update, aber nur wenn `accessLog` noch der Standard `{}` ist. Ein abgeschaltetes oder eigens konfiguriertes Zugriffslog bleibt unverändert.
  - Das Zugriffslog enthält danach den User-Agent der Clients (Clientdaten, von Traefik maskiert). Wer Logs weitergibt, sollte das wissen.
  - Beim Update wird Traefik neu gestartet (kurze Unterbrechung der Routen).

Geprüft: Python-Tests (26), Build, QEMU Debian 13 und Rocky 9 (Update eines bestehenden `traefik1`), dazu der Logeintrag gegen die gepinnte Traefik-Runtime 3.7.19 (User-Agent erhalten, Cookie/Authorization/Referer nicht im Log).

Nicht abgedeckt: Live-Test auf einem Produktivknoten, Update mit eigens angepasstem `accessLog`.
