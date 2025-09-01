# Diagrama de Flujo
* Mostrando cómo fluye la petición desde el navegador hasta Django, incluyendo IIS, ARR/Rewrite y LDAP.

+-----------------+
|   Navegador     |
|  (usuario)      |
+--------+--------+
         |
         | HTTP/HTTPS
         v
+-----------------+
|       IIS       |
|  (Puerto 8080)  |
|  - URL Rewrite  |
|  - Handlers     |
+--------+--------+
         |
         | Proxy (ARR)
         v
+-----------------+
|  ARR / Proxy    |
|  (Reverse Proxy)|
+--------+--------+
         |
         | HTTP (localhost:8000)
         v
+-----------------+
|   Waitress      |
|  Servicio Win   |
|  Ejecutando     |
|  Django         |
+--------+--------+
         |
         | Consulta LDAP (autenticación / grupos)
         v
+-----------------+
|    Active       |
|    Directory    |
|  (Windows AD)   |
+-----------------+

🔹 Explicación

Navegador → IIS:

Todo llega a IIS en el puerto público (ej: 8080).

IIS → URL Rewrite:

La regla de rewrite intercepta todas las URLs (.*) y las redirige hacia el backend (localhost:8000).

Los handlers y Request Filtering permiten que IIS no bloquee la request.

ARR / Proxy Inverso:

Necesario para que IIS haga de reverse proxy y reenvíe requests hacia Waitress correctamente.

Preserva cabeceras importantes (X-Forwarded-For, etc.).

Waitress → Django:

Ejecuta la app Django, responde la request.

Django → LDAP:

Cuando hay login, Django consulta AD vía ldap3 para autenticar usuarios y verificar grupos/permisos.

Respuesta:

Django genera la respuesta → Waitress → ARR → IIS → navegador.

Este diagrama sirve para tener claro qué capa hace qué y dónde pueden aparecer errores:

Error de handler → problema entre IIS y Rewrite/ARR.

Error de login → problema entre Django y LDAP.

Error de static/media → falta de reglas específicas en Rewrite o handlers.
