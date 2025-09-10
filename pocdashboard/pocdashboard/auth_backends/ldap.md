# Backend LDAP extendido — soporte de grupos y permisos desde AD

**backend LDAP ** basado en `ldap3` que:

* autentica usuarios contra Active Directory (NTLM o SIMPLE bind),
* sincroniza atributos básicos en el usuario Django,
* obtiene la pertenencia a grupos desde AD (por `memberOf` o por búsqueda),
* mapea grupos AD a `django.contrib.auth.models.Group` y, opcionalmente, asigna permisos Django por *codename*,
* puede sincronizar (agregar/quitar) grupos en Django según la membresía actual.

Copiár y pegár ldap_backend.py en `pocdashboard/auth_backends/ldap_backend.py` (o la ruta que prefieras).
Ajustar configuración.

## Ejemplo de configuración a agregar en `settings.py`

```python
# Autenticación
AUTHENTICATION_BACKENDS = [
    'pocdashboard.auth_backends.ldap_backend.LDAPBackend',
    'django.contrib.auth.backends.ModelBackend',
]

# Servidor LDAP
LDAP_SERVER_URI = "ldaps://ad.midominio.local"   # usar ldaps:// para SSL
LDAP_USE_SSL = True
LDAP_AUTH_MODE = "NTLM"   # o "SIMPLE"
LDAP_DOMAIN = "MIDOMINIO"  # necesario si NTLM
LDAP_SEARCH_BASE = "DC=midominio,DC=local"
LDAP_USER_SEARCH_FILTER = "(sAMAccountName=%(user)s)"
LDAP_RECEIVE_TIMEOUT = 5

# Si usás SIMPLE bind y tenés que resolver el DN con una cuenta de servicio:
LDAP_RESOLVE_USER_DN = False
LDAP_SERVICE_BIND_DN = "CN=ldapbind,OU=Service Accounts,DC=midominio,DC=local"
LDAP_SERVICE_BIND_PASSWORD = "secreto"

# Grupos
# LDAP_GROUP_SOURCE: 'memberOf' (por defecto) o 'search'
LDAP_GROUP_SOURCE = "memberOf"

# Si usás 'search', definí la base y el filtro (el filtro puede usar %s para el DN)
LDAP_GROUP_SEARCH_BASE = "OU=Groups,DC=midominio,DC=local"
LDAP_GROUP_SEARCH_FILTER = "(member=%s)"  # se formatea con user_dn

# Mapeo de AD group CN -> Django group + permisos
# permisos en formato "app_label.codename"
LDAP_GROUP_MAPPING = {
    "AD_Segment_Admins": {
        "django_group": "admin_segment",
        "permissions": ["auth.add_user", "auth.change_user", "auth.delete_user"]
    },
    "AD_ReadOnly": {
        "django_group": "readonly",
        "permissions": []
    },
    # agregar más mappings según conveniencia
}

# Opciones de sincronización
LDAP_AUTO_CREATE_GROUPS = False    # si True crea grupos Django con mismo nombre cuando no hay mapping
LDAP_SYNC_GROUPS = True           # si True quita al usuario de grupos Django que ya no estén en AD
LDAP_EXEMPT_GROUPS = ["superusers"]  # grupos a proteger de la sincronización
```

---

## Buenas prácticas y consideraciones para entornos regulados

1. **Usar LDAPS** (puerto 636) o StartTLS para cifrar credenciales en tránsito.
2. **Preferir service account** solo si necesitás buscar DNs (SIMPLE+resolver); si usás NTLM y el dominio funciona, es más simple.
3. **Auditoría / logging**: registrar accesos y errores de autenticación en un sistema de logs centralizado (no imprimir en stdout).
4. **No almacenar contraseñas**: el backend establece password unusable en Django y confía en AD para auth.
5. **Revisar permisos**: mapear permisos por `app_label.codename` garantiza control fino.
6. **Cacheo opcional**: si tu AD es lento, cacheá la lista de grupos por usuario en Redis/memcached con expiración corta.
7. **Pruebas**: verificar con varios tipos de usuarios (miembro de grupos, sin grupos, usuarios deshabilitados).
8. **Rollback**: al principio, dejá `LDAP_SYNC_GROUPS = False` para observar cómo se asignan grupos sin quitar ninguno.
9. **Seguridad**: restringir la cuenta de servicio a solo lectura si la usás, y rotar credenciales según políticas.

---

