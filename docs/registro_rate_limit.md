_## Registro del ensayo de rate limit
 
- Fecha: 2026-10-26
- Peticiones enviadas: 20
- Petición donde apareció el primer 429: la número 14
- Esperas observadas: 2.1s, 4.3s, 8.2s (backoff exponencial con jitter, correcto)
- Costo total del ensayo: $0.00146
- Resultado: todas las peticiones terminaron con éxito tras reintentar