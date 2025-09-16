from django.core.management.base import BaseCommand
from django.conf import settings
import ldap3
import logging
import getpass

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Check LDAP connectivity, bind, and search"

    def add_arguments(self, parser):
        parser.add_argument(
            "--username", "-u",
            type=str,
            help="Username to authenticate against LDAP"
        )
        parser.add_argument(
            "--password", "-p",
            type=str,
            help="Password (omit to prompt securely)"
        )
        parser.add_argument(
            "--service", "-s",
            action="store_true",
            help="Test LDAP connectivity using the service account (LDAP_SERVICE_BIND_DN / PASSWORD)"
        )

    def handle(self, *args, **options):
        username = options.get("username")
        password = options.get("password")
        use_service = options.get("service")

        if use_service:
            if not hasattr(settings, "LDAP_SERVICE_BIND_DN") or not hasattr(settings, "LDAP_SERVICE_BIND_PASSWORD"):
                self.stdout.write(self.style.ERROR("Service account not configured in settings"))
                return
            user_dn = settings.LDAP_SERVICE_BIND_DN
            password = settings.LDAP_SERVICE_BIND_PASSWORD
            self.stdout.write(self.style.NOTICE("Testing LDAP connectivity with service account..."))
        else:
            if not username:
                self.stdout.write(self.style.ERROR("Username required (or use --service)"))
                return
            if not password:
                password = getpass.getpass("Password: ")
            if hasattr(settings, "LDAP_DOMAIN") and settings.LDAP_DOMAIN:
                user_dn = f"{username}@{settings.LDAP_DOMAIN}"
            else:
                user_dn = username
            self.stdout.write(self.style.NOTICE(f"Testing LDAP connectivity with user {user_dn}"))

        # Conexión al servidor
        try:
            server = ldap3.Server(
                settings.LDAP_SERVER_URI,
                get_info=ldap3.ALL,
                connect_timeout=getattr(settings, "LDAP_CONNECT_TIMEOUT", 5),
            )
            conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)
            self.stdout.write(self.style.SUCCESS(f"✅ Bind successful for {user_dn}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ LDAP bind failed for {user_dn}: {e}"))
            logger.exception("LDAP check failed at bind stage")
            return

        # Solo buscar si no es test de service account
        if not use_service:
            try:
                search_filter = settings.LDAP_USER_SEARCH_FILTER % {"user": username}
                self.stdout.write(self.style.NOTICE(f"Searching with filter: {search_filter}"))

                conn.search(
                    search_base=settings.LDAP_SEARCH_BASE,
                    search_filter=search_filter,
                    attributes=["cn", "mail", "memberOf"]
                )

                if conn.entries:
                    self.stdout.write(self.style.SUCCESS(f"✅ Found {len(conn.entries)} entries"))
                    for entry in conn.entries:
                        self.stdout.write(f"  - {entry.entry_dn}")
                        if "mail" in entry:
                            self.stdout.write(f"    mail: {entry.mail}")
                        if "memberOf" in entry:
                            self.stdout.write(f"    memberOf: {entry.memberOf}")
                else:
                    self.stdout.write(self.style.WARNING("⚠️ No entries found for that user"))

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ LDAP search failed: {e}"))
                logger.exception("LDAP check failed at search stage")
