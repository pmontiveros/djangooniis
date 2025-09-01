# python-ldap vs ldap3 En resumen:

* **`python-ldap`** es un *wrapper* directo sobre la librería nativa **OpenLDAP** escrita en C.
* **`ldap3`** es una implementación 100% Python, sin dependencias compiladas.

---

## **Ventajas y desventajas**

| Aspecto                                | `python-ldap`                                                                                                         | `ldap3`                                                                                                                       |
| -------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **Velocidad**                          | ✅ Muy rápido, porque usa código C nativo.                                                                             | ❌ Un poco más lento, porque todo es Python puro.                                                                              |
| **Compatibilidad con AD**              | ✅ Soporta todas las operaciones LDAP estándar y extensiones de AD, incluidas algunas más complejas (ej. SASL/GSSAPI). | ✅ Compatible con AD, pero algunas funciones avanzadas de autenticación (ej. Kerberos integrado) requieren más trabajo manual. |
| **Dependencias**                       | ❌ Requiere compilador (Visual C++ en Windows) y librerías OpenLDAP, lo que complica la instalación.                   | ✅ Instalación sencilla con `pip install ldap3`, sin compilación.                                                              |
| **Soporte histórico**                  | ✅ Muy maduro, usado en entornos empresariales por años.                                                               | ✅ Activo y moderno, con API más limpia y orientada a objetos.                                                                 |
| **Integración con `django-auth-ldap`** | ✅ Soporte oficial y probado.                                                                                          | ⚠ Funciona, pero internamente `django-auth-ldap` está más pensado para `python-ldap`. Con `ldap3` hay que ajustar un poco.    |
| **Manejo de grandes volúmenes**        | ✅ Mejor rendimiento en consultas grandes.                                                                             | ⚠ Más lento si manejas muchos registros en una sola consulta.                                                                 |

* `python-ldap` requiere instalar **Microsoft Visual C++ Build Tools**

En un **servidor productivo de Windows Server**, instalar **Microsoft Visual C++ Build Tools** no es lo más común ni lo más “limpio”, pero tampoco es un problema grave si toman ciertas precauciones.

* `python-ldap` Tambien necesita en Windows:

Librerías y headers de OpenLDAP

Librerías y headers de SASL y OpenSSL (dependencias indirectas)

---

## **Pros**

* ✅ Es el método oficial para compilar extensiones como `python-ldap` en python.

---

## **Contras / Riesgos**

* ⚠ **Peso adicional**: la instalación completa de “Desktop development with C++” puede ocupar varios GB.
* ⚠ **Superficie de ataque**: como cualquier software adicional, aumenta un poco la superficie de seguridad (nuevos binarios instalados).
* ⚠ **Cambios en PATH**: puede añadir rutas a las variables de entorno que, en entornos muy controlados, podrían ser cuestionadas por el equipo de seguridad.
* ⚠ **Políticas de compliance**: en entornos bancarios o gubernamentales, a veces no se permite instalar herramientas de desarrollo en producción.

---

## **Buenas prácticas si lo haces en un servidor productivo**

1. 📋 **Documentar la necesidad**: dejar claro que `python-ldap` lo requiere para compilar.
2. 🛠 **Instalar solo lo mínimo**: en el instalador, desmarcar todo lo que no sea **MSVC compiler** y librerías estándar de C++.
3. 🔒 **Limitar permisos**: no dar permisos de desarrollo a usuarios que no lo necesiten.
4. 🧹 **Desinstalar si ya no se necesita**: una vez compilado e instalado `python-ldap`, podrías desinstalar Build Tools y seguir usando el paquete ya compilado.

---

💡 Alternativa para evitar instalar compilador en productivo:
Compilar `python-ldap` en **otro servidor Windows** (con el mismo Python y arquitectura), generar un **wheel** (`.whl`), y luego instalar ese wheel en el servidor productivo con:

```bash
pip install python_ldap-X.Y.Z-cp39-cp39-win_amd64.whl
```

Esto deja tu servidor limpio y sin herramientas de desarrollo.

---

