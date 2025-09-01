## **Plan de laboratorio – Django + IIS + Waitress + LDAP (PoC)**

### **1️⃣ Preparación del servidor**

* Servidor Windows con IIS instalado. Ver [How to Enable IIS and Key Features on Windows Server: A Step-by-Step Guide](https://techcommunity.microsoft.com/blog/iis-support-blog/how-to-enable-iis-and-key-features-on-windows-server-a-step-by-step-guide/4229883)
* Conda instalado.
* Crear ambiente virtual para Django (ej. `djangoiis`).

---

### **2️⃣ Crear la app Django mínima**

* `django-admin startproject pocdashboard`
* Configurar `ALLOWED_HOSTS = ['*']` para pruebas locales.
* Configurar superusuario para dashboard admin.
* Probar localmente:

  ```bash
  python manage.py runserver
  ```

  * Confirmar acceso a `/admin`.

---

### **3️⃣ Integración con Active Directory (LDAP) usando ldap3**

* Decidimos **no usar `django-auth-ldap`** (incompatible con Windows / problemas de compilación).
* Implementar **backend de autenticación propio** usando `ldap3`.
* Nota en plan:

  > Se elimina django-auth-ldap y se reemplaza por ldap3 puro. Esto permite compatibilidad con Windows y evita dependencias de C++/python-ldap.
* Confirmar autenticación de usuarios y lectura de grupos/roles desde AD.

  Ver [python-ldap vs ldap3](https://github.com/pmontiveros/djangooniis/blob/main/python-ldap%20vs%20ldap3.md#python-ldap-vs-ldap3-en-resumen)

---

### **4️⃣ Configuración para correr Django en Windows como servicio**

* Instalar Waitress (`pip install waitress`).
* Crear script `runwaitress.py` para ejecutar la app Django en el puerto 8000.
* Instalar **servicio Windows** con pywin32:

  ```bash
  python waitress_service.py install
  ```
* Confirmar que el servicio se inicia y Django responde en `http://localhost:8000/admin`.

---
### **5️⃣ Instalación de ARR y habilitación de proxy inverso**

* Descargar e instalar **Application Request Routing (ARR v3)**. Ver [Instalar application-request-routing en Microsoft IIS](https://www.iis.net/downloads/microsoft/application-request-routing)
* IIS Manager → nodo raíz del servidor → **Application Request Routing Cache → Server Proxy Settings**:

  * `[x] Enable proxy`
  * `[x] Preserve client IP`

**Nota en plan:**

> URL Rewrite necesita ARR + proxy inverso habilitado para funcionar como reverse proxy. Sin esto, IIS intenta procesar las requests localmente y se generan errores de handler.

* Instalar **URL Rewrite Module** Ver [URL Rewrite] (https://www.iis.net/downloads/microsoft/url-rewrite):

   * Nota: después de instalar URL Rewrite (o cualquier modulo para el caso), **cerrar IIS Manager completamente y volver a abrir** para que aparezca el icono.

* Habilitar variables de URL Rewrite en servidor en IIS

  Abre una consola de Administrador de IIS. 
  Ve a tu Sitio → URL Rewrite → View Server Variables. 
  Si no ves la opción, hacé clic en el sitio → Features View → buscá "Server Variables".
  Dale a Add... y agrega:
  
    HTTP_X_FORWARDED_FOR
  
    HTTP_X_FORWARDED_PROTO

⚡ Alternativa rápida con PowerShell
Import-Module WebAdministration

* Agregar HTTP_X_FORWARDED_FOR
```Bash
  Add-WebConfigurationProperty `
     -pspath 'MACHINE/WEBROOT/APPHOST' `
     -filter "system.webServer/rewrite/allowedServerVariables" `
     -name "." `
     -value @{name='HTTP_X_FORWARDED_FOR'}
```

* Agregar HTTP_X_FORWARDED_PROTO
```Bash
Add-WebConfigurationProperty `
   -pspath 'MACHINE/WEBROOT/APPHOST' `
   -filter "system.webServer/rewrite/allowedServerVariables" `
   -name "." `
   -value @{name='HTTP_X_FORWARDED_PROTO'}
```
* Reiniciar IIS: `iisreset`.

---
** 6️⃣ Configuración IIS**

1. Crear **sitio** apuntando a `C:\inetpub\pocdashboard`.
2. Confirmar que **Application Pool** usa `ApplicationPoolIdentity`.

3. Crear `web.config` minimo en raíz del sitio:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>

    <!-- URL Rewrite: proxy hacia Waitress en localhost:8000 -->
    <rewrite>
      <rules>
        <rule name="ReverseProxyToDjango" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://localhost:8000/{R:1}" />
        </rule>
      </rules>
    </rewrite>

    <!-- Handlers: permitir que todas las requests pasen -->
    <handlers>
      <clear />
      <add name="ProxyAll" path="*" verb="*" modules="RewriteModule" resourceType="Unspecified" requireAccess="None" />
      <add name="StaticFile" path="*" verb="*" modules="StaticFileModule,DefaultDocumentModule,DirectoryListingModule" resourceType="Either" requireAccess="Read" />
    </handlers>

    <!-- Request Filtering: permitir extensiones desconocidas -->
    <security>
      <requestFiltering allowUnlistedFileExtensions="true" />
    </security>

    <!-- Opcional: mostrar errores detallados -->
    <httpErrors errorMode="Detailed" />
    <asp scriptErrorSentToBrowser="true"/>

    <!-- Habilitar proxy para URL Rewrite (solo con ARR) -->
    <proxy enabled="true" preserveHostHeader="true" />

  </system.webServer>
</configuration>
```

   * Nota: Es web.config es minimo para probar la redirección de IIS

Sí no se ven los archivos estaticos y foramtos CCS agregar

```xml
        <!-- Excluir /static/ -->
        <rule name="StaticFiles" stopProcessing="true">
          <match url="^static/(.*)" />
          <action type="None" />
        </rule>
```
---

### **7️⃣ Pruebas finales**

* Acceder a `http://localhost:8080/admin` (proxy IIS → Waitress).
* Confirmar:

  1. El sitio carga sin errores de “handler no configurado”.
  2. LDAP funciona (login de usuarios y grupos).
  3. Static/media servidos correctamente si agregás reglas específicas de rewrite para ellos (opcional para PoC).

---

### **Notas de seguridad y buenas prácticas**

1. **Server Variables**:

   * Solo habilitar `HTTP_X_FORWARDED_FOR` y `HTTP_X_FORWARDED_PROTO` si realmente se usan.
   * No habilitar variables sensibles innecesarias.
2. **Handlers**:

   * Mantener `<clear />` + wildcard handler (`ProxyAll`) evita conflictos con herencia de `ApplicationHost.config`.
3. **URL Rewrite**:

   * El icono puede no aparecer hasta reiniciar IIS Manager tras instalación.
   * ARR debe estar habilitado para que el rewrite funcione como proxy inverso.

