"""LDAP authentication helpers."""

from __future__ import annotations

from dataclasses import dataclass

from flask import current_app
from ldap3 import ALL, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars


@dataclass(frozen=True)
class LdapUserInfo:
    username: str
    full_name: str


def _build_server():
    uri = current_app.config["LDAP_URI"]
    if not uri:
        raise LDAPException("LDAP URI is not configured")

    tls_config = None
    if current_app.config["LDAP_USE_TLS"]:
        ca_file = current_app.config.get("LDAP_TLS_CA_FILE") or None
        tls_config = Tls(ca_certs_file=ca_file)

    return Server(uri, get_info=ALL, tls=tls_config)


def _extract_attribute(entry, attribute: str) -> str | None:
    if not entry or attribute not in entry:
        return None
    value = entry[attribute].value
    if value is None:
        return None
    return str(value)


def authenticate_ldap_user(username: str, password: str) -> LdapUserInfo | None:
    if not username or not password:
        return None

    escaped_username = escape_filter_chars(username)
    user_filter = current_app.config["LDAP_USER_FILTER"].format(username=escaped_username)
    base_dn = current_app.config["LDAP_USER_BASE_DN"]
    bind_dn = current_app.config["LDAP_BIND_DN"]
    bind_password = current_app.config["LDAP_BIND_PASSWORD"]
    username_attr = current_app.config["LDAP_ATTR_USERNAME"]
    full_name_attr = current_app.config["LDAP_ATTR_FULL_NAME"]

    server = _build_server()

    try:
        with Connection(server, user=bind_dn, password=bind_password, auto_bind=True) as conn:
            conn.search(
                search_base=base_dn,
                search_filter=user_filter,
                search_scope=SUBTREE,
                attributes=[username_attr, full_name_attr],
                size_limit=1,
            )
            if not conn.entries:
                return None

            entry = conn.entries[0]
            user_dn = entry.entry_dn

        with Connection(server, user=user_dn, password=password, auto_bind=True):
            pass
    except LDAPException:
        return None

    resolved_username = _extract_attribute(entry, username_attr) or username
    full_name = _extract_attribute(entry, full_name_attr) or resolved_username
    return LdapUserInfo(username=resolved_username, full_name=full_name)
