# Admin Lab Run Bridge

> Come far avviare i Lab da THIA Assistant quando l'admin e' loggato sul
> sito principale `d-nd.com`, non sul sottodominio del Lab.

## Confine

Il login admin vive sul sito principale. Il sottodominio Lab non deve
replicare quel login e non deve ricevere cookie/sessioni admin dal browser.

La forma sicura e':

```text
admin browser -> d-nd.com THIA backend -> lab.d-nd.com Lab API
```

Il backend THIA verifica la sessione admin sul sito. Solo dopo chiama la Lab
API con un token privato server-to-server.

Il token non deve mai essere esposto nel frontend.

## Variabili Lab API

Sul servizio dashboard Lab:

```bash
DND_LAB_ADMIN_TOKEN=<secret server-to-server>
DND_LAB_ADMIN_WRITE_GUARD=enabled
```

`DND_LAB_ADMIN_WRITE_GUARD=enabled` e' il default. Con guard attivo,
operazioni write come run cycle e inject tension richiedono admin token.

## Chiamata run cycle

Da backend THIA dopo aver verificato admin:

```bash
curl -X POST "https://lab.d-nd.com/api/domains/finance/run" \
  -H "Authorization: Bearer $DND_LAB_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"direction_override": null}'
```

Risposta:

```json
{
  "cycle_id": "...",
  "domain": "finance",
  "status": "running"
}
```

## Monitoraggio realtime

Il log live e' gia' disponibile via WebSocket:

```text
wss://lab.d-nd.com/api/cycles/<cycle_id>/log
```

Frame tipici:

```json
{"type":"log","data":"..."}
{"type":"status","status":"completed","return_code":0,"finished_at":"..."}
```

Se il monitor realtime non serve, il backend puo' interrogare:

```text
GET /api/cycles/<cycle_id>
```

## THIA Assistant

Quando THIA riconosce un admin loggato su `d-nd.com`, puo':

1. chiedere conferma esplicita;
2. chiamare il bridge server-to-server;
3. mostrare `cycle_id`;
4. aprire o collegare lo stream log realtime;
5. non promettere risultati prima della fine ciclo.

Quando l'utente non e' admin, THIA deve solo spiegare che l'avvio ciclo
richiede superficie admin.

## Endpoint protetti

Oggi il guard protegge:

- `POST /api/domains/{domain}/run`
- `POST /api/domains/{domain}/inject_tension`

Le letture restano disponibili secondo la configurazione dashboard/demo.
