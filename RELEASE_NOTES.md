Stabile Version 4.2.7 des angepassten Traefik-Moduls für NethServer 8, im Katalog `platypuschan` gelistet. Update von 4.2.6.

- **Traefik 3.7.19** (vorher 3.7.17), weiterhin auf den geprüften Digest gepinnt. Ein Upstream-Patch-Release; ich habe die Änderungen von Traefik selbst nicht einzeln bewertet.
- **Update von Traefik 2 auf 3 fehlertolerant:** Wenn beim Umstellen der Zertifikatskonfiguration etwas schiefgeht, wird die Migration nicht mehr als erledigt markiert. Der Neustart schützt zusätzlich: Ohne den v3-Marker startet `20restart` Traefik nicht. So läuft kein halb umgestellter Proxy an.
- **Backup:** `module-cleanup-state` räumt jetzt das Verzeichnis auf, das `module-dump-state` anlegt (`state-backup`); vorher blieb es liegen.

Installation oder Update eines Knotens: Katalog `platypuschan` aktivieren, dann erscheint das Update in den Core-Apps. Ohne Katalog: `api-cli run cluster/update-module --data '{"module_url":"ghcr.io/platypuschan/traefik-reworked:4.2.7","instances":["traefik1"]}'`. Traefik ist ein Core-Modul und wird im Software-Center nicht als installierbare App angezeigt. Ist der Katalog aktiv, aktualisiert ein Core-Update das Modul mit.

Geprüft: Python-Tests (21), Build, QEMU Debian 13 und Rocky 9 als Update eines bestehenden `traefik1`, dazu eine Live-Abnahme auf einem Testknoten (Update von v2 auf v3, unlesbare Zertifikatsdatei, Neustartschutz).

Nicht abgedeckt: eine echte v2-Installation mit Produktivdaten, Let's-Encrypt-Zertifikate, Rollback, mehrere Knoten, Live-Test mit einem Browser-Clientzertifikat.
