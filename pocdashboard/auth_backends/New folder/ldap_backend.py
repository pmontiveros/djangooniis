# pocdashboard/auth_backends/ldap_backend.py
import logging
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User, Group, Permission
from django.conf import settings
from ldap3 import Server, Connection, ALL, NTLM, SIMPLE, ALL_ATTRIBUTES, SUBTREE
from django.db import transaction

logger = logging.getLogger(__name__)


class LDAPBackend(BaseBackend):
    """
    Backend LDAP puro usando ldap3.
    Soporta:
      - autenticación NTLM o SIMPLE
      - mapeo de atributos básicos (email, givenName, sn)
      - obtención de grupos por memberOf o búsqueda
      - mapeo de AD groups -> Django Group (auto-creación)
      - asignación de permisos Django por codename (opcional)
    Configuración requerida en settings.py (ver ejemplo al final).
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None

        server = Server(settings.LDAP_SERVER_URI, get_info=ALL)
        auth_mode = getattr(settings, "LDAP_AUTH_MODE", "NTLM").upper()
        use_ssl = getattr(settings, "LDAP_USE_SSL", True)

        # Build bind username depending on auth mode
        if auth_mode == "NTLM":
            if not getattr(settings, "LDAP_DOMAIN", None):
                logger.error("LDAP_DOMAIN is required for NTLM auth_mode")
                return None
            bind_user = f"{settings.LDAP_DOMAIN}\\{username}"
            auth_type = NTLM
        else:
            # SIMPLE bind: use full DN or service user + search for user DN
            bind_user = getattr(settings, "LDAP_BIND_TEMPLATE", None) or username
            auth_type = SIMPLE

        try:
            conn = Connection(
                server,
                user=bind_user,
                password=password,
                authentication=auth_type,
                receive_timeout=getattr(settings, "LDAP_RECEIVE_TIMEOUT", 5),
                auto_bind=False,
                read_only=True,
            )

            # For SIMPLE binds we may need to resolve the user's DN first using a service account
            if auth_mode == "SIMPLE" and getattr(settings, "LDAP_RESOLVE_USER_DN", False):
                # do a service bind first
                svc_dn = getattr(settings, "LDAP_SERVICE_BIND_DN", None)
                svc_pw = getattr(settings, "LDAP_SERVICE_BIND_PASSWORD", None)
                if not svc_dn or not svc_pw:
                    logger.error("Service bind DN and password required to resolve user DN")
                    return None
                svc_conn = Connection(server, user=svc_dn, password=svc_pw, authentication=SIMPLE, auto_bind=True)
                user_dn = self._search_user_dn(svc_conn, username)
                svc_conn.unbind()
                if not user_dn:
                    return None
                # try bind with the found DN and user password
                conn = Connection(server, user=user_dn, password=password, authentication=SIMPLE, auto_bind=False)

            # try to bind with given credentials (NTLM or resolved DN)
            if not conn.bind():
                logger.info("LDAP bind failed for user %s", username)
                return None

            # After bind success, search user attributes (if not already loaded)
            search_base = getattr(settings, "LDAP_SEARCH_BASE")
            user_search_filter = getattr(settings, "LDAP_USER_SEARCH_FILTER", "(sAMAccountName=%(user)s)")
            search_filter = user_search_filter % {"user": username}

            conn.search(search_base=search_base, search_filter=search_filter,
                        search_scope=SUBTREE, attributes=ALL_ATTRIBUTES)
            if not conn.entries:
                logger.info("User %s not found in LDAP after bind", username)
                conn.unbind()
                return None

            entry = conn.entries[0]
            user_dn = entry.entry_dn

            # Build or update Django user atomically
            with transaction.atomic():
                user, created = User.objects.get_or_create(username=username)
                if created:
                    user.is_active = True

                # map attributes if present
                user.email = str(entry.mail) if 'mail' in entry else user.email
                user.first_name = str(entry.givenName) if 'givenName' in entry else user.first_name
                user.last_name = str(entry.sn) if 'sn' in entry else user.last_name
                # We don't store LDAP password in Django; set unusable password
                user.set_unusable_password()
                user.save()

                # Groups & permissions sync
                self._sync_groups_and_permissions(conn, entry, user)

            conn.unbind()
            return user

        except Exception as e:
            logger.exception("LDAP authentication error for %s: %s", username, e)
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    # ---- Helpers ----

    def _search_user_dn(self, conn, username):
        """Search user DN using service connection"""
        base = getattr(settings, "LDAP_SEARCH_BASE")
        user_search_filter = getattr(settings, "LDAP_USER_SEARCH_FILTER", "(sAMAccountName=%(user)s)")
        conn.search(search_base=base, search_filter=user_search_filter % {"user": username},
                    search_scope=SUBTREE, attributes=['distinguishedName'])
        if not conn.entries:
            return None
        return conn.entries[0].entry_dn

    def _get_ad_groups_from_memberof(self, entry):
        """Extract list of group CNs from memberOf attribute in the user entry"""
        groups = []
        if 'memberOf' in entry:
            for raw in entry.memberOf:
                # raw is DN, extract CN=
                dn = str(raw)
                # naive parse: find CN=...,
                try:
                    cn_part = next(part for part in dn.split(',') if part.strip().upper().startswith("CN="))
                    cn = cn_part.split('=', 1)[1]
                    groups.append(cn)
                except StopIteration:
                    continue
        return groups

    def _get_ad_groups_via_search(self, conn, user_dn):
        """
        Search groups where member=user_dn under LDAP_GROUP_SEARCH_BASE.
        Returns list of group CNs.
        """
        groups = []
        group_base = getattr(settings, "LDAP_GROUP_SEARCH_BASE", getattr(settings, "LDAP_SEARCH_BASE"))
        group_filter = getattr(settings, "LDAP_GROUP_SEARCH_FILTER", "(member=%s)" % user_dn)
        conn.search(search_base=group_base, search_filter=group_filter, search_scope=SUBTREE, attributes=['cn'])
        for entry in conn.entries:
            if 'cn' in entry:
                groups.append(str(entry.cn))
        return groups

    def _sync_groups_and_permissions(self, conn, entry, user):
        """
        Map AD groups to Django groups and assign permissions.
        Configuration keys used:
          - LDAP_GROUP_SOURCE: 'memberOf' or 'search' (default 'memberOf')
          - LDAP_GROUP_MAPPING: dict { "AD_CN": { "django_group": "Name", "permissions": ["app.codename", ...] } }
          - LDAP_SYNC_GROUPS: boolean (if True, remove Django groups not present in AD mapping)
        """
        try:
            # Determine AD groups for user
            group_source = getattr(settings, "LDAP_GROUP_SOURCE", "memberOf")
            if group_source == "search":
                user_dn = entry.entry_dn
                ad_groups = self._get_ad_groups_via_search(conn, user_dn)
            else:
                ad_groups = self._get_ad_groups_from_memberof(entry)

            # Mapping from settings
            mapping = getattr(settings, "LDAP_GROUP_MAPPING", {})

            # Build set of Django group names that should be present per AD membership
            target_django_group_names = set()
            for ad_group in ad_groups:
                entry_map = mapping.get(ad_group)
                if entry_map:
                    target_django_group_names.add(entry_map.get("django_group", entry_map.get("group_name", ad_group)))

            # Create/assign Django groups and permissions
            assigned_groups = set()
            for ad_group in ad_groups:
                entry_map = mapping.get(ad_group)
                if not entry_map:
                    # Option: auto-create Django group with same name as AD group
                    if getattr(settings, "LDAP_AUTO_CREATE_GROUPS", False):
                        django_group_name = ad_group
                        group_obj, _ = Group.objects.get_or_create(name=django_group_name)
                        user.groups.add(group_obj)
                        assigned_groups.add(django_group_name)
                    continue

                django_group_name = entry_map.get("django_group")
                if not django_group_name:
                    continue

                group_obj, _ = Group.objects.get_or_create(name=django_group_name)

                # Assign permissions if any (format: ["app_label.codename", ...])
                perms = entry_map.get("permissions", [])
                for perm_full in perms:
                    try:
                        app_label, codename = perm_full.split('.', 1)
                        perm_obj = Permission.objects.get(content_type__app_label=app_label, codename=codename)
                        group_obj.permissions.add(perm_obj)
                    except Exception as e:
                        logger.warning("Failed to add permission %s to group %s: %s", perm_full, django_group_name, e)

                user.groups.add(group_obj)
                assigned_groups.add(django_group_name)

            # Optionally remove groups the user shouldn't be part of
            if getattr(settings, "LDAP_SYNC_GROUPS", False):
                current = set(user.groups.values_list('name', flat=True))
                to_remove = current - assigned_groups
                if to_remove:
                    Group.objects.filter(name__in=to_remove).exclude(name__in=getattr(settings, "LDAP_EXEMPT_GROUPS", [])).update()
                    for gname in to_remove:
                        try:
                            gobj = Group.objects.get(name=gname)
                            user.groups.remove(gobj)
                        except Group.DoesNotExist:
                            continue

        except Exception:
            logger.exception("Error syncing groups for user %s", user.username)
